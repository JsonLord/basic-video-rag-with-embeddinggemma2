import asyncio
import json
import shutil
import subprocess
import pytest
from fastapi.testclient import TestClient
from vrag.api import app
from vrag import jobs
from vrag.index import get_index
from vrag.providers import Output, ProviderFailure
from vrag.settings import store
from config.schema import parse_yaml

@pytest.fixture
def setup(tmp_path,monkeypatch):
    data=tmp_path/'data';videos=data/'videos';videos.mkdir(parents=True);index=data/'index'
    for module in ('vrag.jobs','vrag.api','vrag.remote'):
        monkeypatch.setattr(module+'.DATA',data)
        monkeypatch.setattr(module+'.VIDEOS_DIR',videos)
        monkeypatch.setattr(module+'.INDEX_DIR',index)
    monkeypatch.setattr('vrag.index.INDEX_DIR',index)
    monkeypatch.setenv('VM_USER_TOKEN','u'*32);monkeypatch.setenv('URL','https://example.com/v1')
    old=store.history,store.version
    store.history=[parse_yaml('''providers:
  emb: {adapter: openai-embeddings, model: test, base_url_env: URL, capabilities: [text_embeddings], trust: approved_sensitive}
  stt: {adapter: openai-transcription, model: whisper-test, base_url_env: URL, capabilities: [transcription], trust: approved_sensitive}
features:
  rag.text_embeddings: {providers: [emb]}
  audio.transcription: {providers: [stt]}
''')];store.version=1
    calls=[]
    async def call(name,provider,payload,sensitive):
        calls.append((name,payload,sensitive))
        if name=='emb':return Output(embedding=[1,0,0])
        assert payload['audio_mime']=='audio/mp4' and payload['audio']
        return Output(text='Clear the workbench.')
    monkeypatch.setattr('vrag.routing.adapter.call',call)
    get_index.cache_clear()
    yield data,calls
    store.history,store.version=old;get_index.cache_clear()

@pytest.fixture
def clip(tmp_path):
    if not shutil.which('ffmpeg'):pytest.skip('FFmpeg required for real CPU media test')
    path=tmp_path/'clip.mp4'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=blue:s=160x120:r=5','-f','lavfi','-i','sine=frequency=440:sample_rate=16000','-t','1','-c:v','libx264','-threads','1','-c:a','aac','-y',str(path)],check=True)
    return path

@pytest.mark.asyncio
async def test_upload_to_search_pipeline_real_ffmpeg_mock_providers(setup,clip):
    c=TestClient(app,headers={'Authorization':'Bearer '+'u'*32})
    r=c.post('/api/ingest?filename=Workshop',content=clip.read_bytes())
    assert r.status_code==200,r.text
    first=r.json();assert c.post('/api/ingest',content=clip.read_bytes()).json()['deduplicated']
    with jobs.connect() as db:job=dict(db.execute('SELECT * FROM jobs WHERE id=?',(first['id'],)).fetchone())
    await jobs.run_job(job)
    result=jobs.listing()[0];assert result['status']=='complete'
    data,calls=setup
    assert (data/'index/CURRENT').exists()
    assert get_index().available_views==['text'] and get_index().dims==[3]
    assert any(name=='stt' for name,_,_ in calls) and all(s for _,_,s in calls)
    response=c.get('/api/search?q=workbench&view=text&dim=3')
    assert response.status_code==200,response.text
    assert response.json()['hits'][0]['start']==0
    assert 'Clear the workbench' in response.json()['hits'][0]['text']
    assert c.get('/api/jobs',headers={'Authorization':''}).status_code==401
    assert c.post('/api/ingest',headers={'Authorization':''},content=b'private').status_code==401

@pytest.mark.asyncio
async def test_failed_provider_preserves_prepared_media_and_retry(setup,clip,monkeypatch):
    c=TestClient(app,headers={'Authorization':'Bearer '+'u'*32});r=c.post('/api/ingest',content=clip.read_bytes()).json()
    async def missing(*a,**k):raise ProviderFailure('credential_missing')
    monkeypatch.setattr('vrag.routing.adapter.call',missing)
    task=asyncio.create_task(jobs.worker())
    try:
        for _ in range(100):
            if jobs.listing()[0]['status']=='blocked':break
            await asyncio.sleep(.05)
        assert jobs.listing()[0]['status']=='blocked'
        assert jobs.listing()[0]['error']=='credential_missing'
        assert (setup[0]/'videos'/r['video_id']/'video.mp4').exists()
        assert not (setup[0]/'index/CURRENT').exists()
        assert c.post('/api/jobs/'+r['id'],json={'action':'retry','transcript':'User supplied evidence'}).status_code==200
        assert c.post('/api/jobs/'+r['id'],json={'action':'cancel'}).status_code==200
        assert jobs.listing()[0]['status']=='cancelled'
    finally:
        task.cancel();await asyncio.gather(task,return_exceptions=True)

def test_auth_and_sample_isolation(setup):
    c=TestClient(app)
    assert c.get('/api/videos').status_code==401
    assert c.get('/api/demo/videos').json()[0]['sample']
    assert c.get('/api/demo/videos/upload-private').status_code==404
    assert c.get('/api/demo/search?q=bench').json()['sample']
    assert c.get('/api/demo/compare?q=bench').status_code==200
    assert c.get('/api/demo/compare-views?q=bench').status_code==200
    r=c.get('/api/demo/experiments')
    assert r.status_code==200 and r.json()['per_query'][0]['ranks']['text@768']==1
    assert c.post('/api/demo/ask',json={'question':'prepare'}).json()['usage_available'] is False
    assert c.get('/media/private/video.mp4').status_code==401
    assert c.get('/api/admin/backup-status').status_code==401
    r=c.post('/api/access',headers={'Authorization':'Bearer '+'u'*32})
    assert r.status_code==204 and 'HttpOnly' in r.headers['set-cookie'] and 'Secure' in r.headers['set-cookie']

def test_actual_media_mount_accepts_secure_cookie_and_range(setup,tmp_path,monkeypatch):
    from fastapi.staticfiles import StaticFiles
    mount=next(r for r in app.routes if getattr(r,'path',None)=='/media')
    media=tmp_path/'media';media.mkdir();(media/'clip.mp4').write_bytes(b'0123456789')
    monkeypatch.setattr(mount,'app',StaticFiles(directory=media))
    c=TestClient(app,base_url='https://testserver')
    assert c.get('/media/clip.mp4').status_code==401
    r=c.post('/api/access',headers={'Authorization':'Bearer '+'u'*32})
    assert r.status_code==204
    response=c.get('/media/clip.mp4',headers={'Range':'bytes=2-5'})
    assert response.status_code==206 and response.content==b'2345'
    # The media cookie is never accepted as API/config authentication.
    assert c.get('/api/videos').status_code==401
    assert c.get('/api/config').status_code==401
    c.delete('/api/access')
    assert c.get('/media/clip.mp4').status_code==401
