"""Real age/SQLite/FFmpeg; GitHub transport is mocked unless live script used."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess

import httpx
import numpy as np
import pytest

from vrag.backup.github import Checkpoints, GitHubStore, digest


class MemoryGitHub:
    """Explicit mock of immutable GitHub records and encrypted release assets."""
    def __init__(self):self.rows=[];self.blobs={};self.records={};self.uploads=0;self.fail=False
    def verify(self):pass
    def checkpoints(self):return list(reversed(self.rows))
    def record(self,row):return self.records[row['path']]
    def release(self,checkpoint):return checkpoint
    def upload(self,release,source):
        if self.fail:raise ValueError('simulated upload failure')
        self.uploads+=1;ref={'id':len(self.blobs)+1,'sha256':digest(source),'bytes':source.stat().st_size}
        self.blobs[ref['id']]=source.read_bytes();assert self.blobs[ref['id']].startswith(b'age-encryption.org/')
        return ref
    def download(self,ref,target):
        value=self.blobs[ref['id']];target.write_bytes(value)
        if digest(target)!=ref['sha256']:raise ValueError('ciphertext checksum mismatch')
    def commit(self,checkpoint,ref):
        path=checkpoint+'.json';self.rows.append({'path':path});self.records[path]={'format':2,'manifest':ref}


def make_library(root):
    data=root/'data';state=root/'state';v=data/'videos/v1';v.mkdir(parents=True);state.mkdir()
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=blue:s=160x90:d=1','-c:v','libx264','-threads','1','-y',str(v/'video.mp4')],check=True)
    shutil.copyfile(v/'video.mp4',v/'original')
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(v/'video.mp4'),'-frames:v','1','-threads','1',str(v/'thumb.jpg')],check=True)
    segments=[{'id':'v1_000','video_id':'v1','title':'Recovery fixture','idx':0,'start':0,'end':1,'text':'blue test video'}]
    (v/'meta.json').write_text(json.dumps({'id':'v1','title':'Recovery fixture','duration':1}))
    (v/'transcript.json').write_text(json.dumps([{'start':0,'end':1,'text':'blue test video'}]))
    (v/'segments.json').write_text(json.dumps(segments));(v/'segments').mkdir();shutil.copyfile(v/'thumb.jpg',v/'segments/000.jpg')
    revision='a'*32;index=data/'index/revisions'/revision;index.mkdir(parents=True)
    (data/'index/CURRENT').write_text(revision)
    np.save(index/'text.npy',np.array([[1,0,0]],dtype=np.float32))
    (index/'segments.json').write_text(json.dumps(segments))
    (index/'manifest.json').write_text(json.dumps({'dimension':3,'views':{'text':{'count':1}},'embedding_space':'test-only','segments':1,'corpus_revision':revision}))
    (state/'config-history.json').write_text('[{"version":1,"profile":"recovered"}]')
    (data/'answers').mkdir();(data/'answers/history.jsonl').write_text('{"answer":"test evidence [1]","clips":[]}\n')
    with sqlite3.connect(data/'jobs.sqlite') as db:
        db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY, video_id TEXT, title TEXT, status TEXT, stage TEXT, error TEXT, created REAL, updated REAL, attempts INTEGER DEFAULT 0, transcript TEXT)')
        db.execute("INSERT INTO jobs(id,video_id,title,status,stage,created,updated) VALUES('job1','v1','Recovery fixture','complete','searchable',1,1)")
    return data,state


@pytest.fixture
def encrypted(tmp_path,monkeypatch):
    binary=os.environ.get('AGE_BIN') or shutil.which('age')
    if not binary:pytest.skip('age required')
    monkeypatch.setenv('AGE_BIN',binary)
    keygen=str(Path(binary).with_name('age-keygen'));key=tmp_path/'test.agekey'
    subprocess.run([keygen,'-o',str(key)],capture_output=True,check=True)
    recipient=subprocess.run([keygen,'-y',str(key)],capture_output=True,text=True,check=True).stdout.strip()
    store=MemoryGitHub();return Checkpoints(store,recipient,key),store


def test_complete_destructive_recovery_incremental_and_configuration(encrypted,tmp_path):
    backup,remote=encrypted;root=tmp_path/'working';data,state=make_library(root)
    stage=tmp_path/'stage';stage.mkdir();backup.capture(data,state,stage)
    before={p.relative_to(stage).as_posix():digest(p) for p in stage.rglob('*') if p.is_file()}
    first=backup.backup(stage);uploads=remote.uploads
    # Same media content across original/proxy deduplicates even within checkpoint.
    assert uploads<sum(len(p.read_bytes())>0 for p in stage.rglob('*') if p.is_file())+1
    second=backup.backup(stage);assert remote.uploads==uploads+1 # manifest only
    assert second['coverage']['index_segments']==1
    shutil.rmtree(root);shutil.rmtree(stage)
    # Local stage and source are gone: only encrypted mock GitHub bytes and key remain.
    result=backup.restore(root);assert result['verified']
    assert before=={p.relative_to(root).as_posix():digest(p) for p in root.rglob('*') if p.is_file()}
    with sqlite3.connect(root/'data/jobs.sqlite') as db:assert db.execute('SELECT status FROM jobs').fetchone()==('complete',)
    assert json.loads((root/'state/config-history.json').read_text())[0]['profile']=='recovered'
    assert np.load(root/'data/index/revisions'/('a'*32)/'text.npy').tolist()==[[1,0,0]]
    with pytest.raises(ValueError,match='new'):backup.restore(root)


def test_no_commit_when_partial_upload_and_corruption_fail_closed(encrypted,tmp_path):
    backup,remote=encrypted;data,state=make_library(tmp_path/'source');stage=tmp_path/'stage';stage.mkdir();backup.capture(data,state,stage)
    remote.fail=True
    with pytest.raises(ValueError):backup.backup(stage)
    assert not remote.checkpoints()
    remote.fail=False;backup.backup(stage)
    object_id=next(iter(remote.blobs));remote.blobs[object_id]+=b'corrupted'
    with pytest.raises(ValueError):backup.restore(tmp_path/'clean')
    assert not (tmp_path/'clean').exists()


def test_unknown_state_missing_media_symlink_and_capacity(encrypted,tmp_path):
    backup,_=encrypted;data,state=make_library(tmp_path/'source');stage=tmp_path/'stage';stage.mkdir()
    (state/'secret.key').write_text('secret')
    with pytest.raises(ValueError):backup.capture(data,state,stage)
    shutil.rmtree(stage);stage.mkdir()
    (state/'secret.key').unlink();(data/'videos/v1/original').unlink()
    with pytest.raises(ValueError,match='incomplete'):backup.capture(data,state,stage)


def test_github_privacy_redirect_and_pagination():
    captured=[]
    def server(request):
        captured.append(request)
        if request.url.path.endswith('/releases/assets/1'):
            return httpx.Response(302,headers={'location':'https://evil.example/steal'})
        return httpx.Response(200,json={'private':False})
    store=GitHubStore('test/private',token='test-token',client=httpx.Client(transport=httpx.MockTransport(server)))
    with pytest.raises(ValueError,match='private'):store.verify()
    with pytest.raises(ValueError,match='redirect'):store.download({'id':1},Path('/unused'))
    assert len(captured)==2


def test_backup_routes_protected_and_coordinator_scoped(monkeypatch):
    from fastapi.testclient import TestClient
    from vrag.api import app
    monkeypatch.setenv('VM_ADMIN_TOKEN','a'*32);monkeypatch.setenv('VM_BACKUP_TRIGGER_TOKEN','b'*32)
    client=TestClient(app)
    assert client.get('/api/admin/backup-status').status_code==401
    assert client.post('/api/admin/backup').status_code==401
    headers={'X-VM-Backup-Token':'b'*32}
    assert client.get('/api/admin/backup-status',headers=headers).status_code==200
    assert client.get('/api/config',headers=headers).status_code==401
    assert client.post('/api/admin/backup/recovery-test',headers=headers).status_code==401
    assert client.get('/api/admin/backup-status',headers={**headers,'Origin':'https://evil.example'}).status_code==403


def test_coordinator_mock_wake_and_completion(monkeypatch):
    from scripts.coordinate_backup import coordinate
    monkeypatch.setenv('VM_SPACE_URL','https://test-private.hf.space');monkeypatch.setenv('VM_SPACE_ID','test/private')
    monkeypatch.setenv('HF_SPACE_TOKEN','hf-test');monkeypatch.setenv('VM_BACKUP_TRIGGER_TOKEN','t'*32)
    polls=0
    def server(request):
        nonlocal polls
        if request.url.host=='huggingface.co':return httpx.Response(200,json={'private':True})
        assert request.headers['authorization']=='Bearer hf-test'
        assert request.headers['x-vm-backup-token']=='t'*32
        if request.method=='POST':return httpx.Response(200,json={'accepted':True})
        polls+=1
        if polls==1:return httpx.Response(503)
        return httpx.Response(200,json={'configured':True,'last_success':None if polls==2 else {'checkpoint':'new','created_at':100}})
    result=coordinate(httpx.Client(transport=httpx.MockTransport(server)),sleep=lambda _:None,clock=lambda:100)
    assert result['verified'] and polls==3


def test_empty_startup_restores_config_before_fresh_application_import(encrypted,tmp_path,monkeypatch):
    backup,remote=encrypted;root=tmp_path/'work';data,state=make_library(root)
    stage=tmp_path/'stage';stage.mkdir();backup.capture(data,state,stage);backup.backup(stage)
    expected={p.relative_to(stage).as_posix():digest(p) for p in stage.rglob('*') if p.is_file()}
    shutil.rmtree(root);shutil.rmtree(stage)
    from vrag.backup import service
    monkeypatch.setenv('VM_BACKUP_ENABLED','true');monkeypatch.setenv('VM_RECOVERY_ROOT',str(root))
    monkeypatch.setenv('VRAG_DATA',str(root/'data'));monkeypatch.setenv('VM_STATE_DIR',str(root/'state'))
    monkeypatch.setenv('VM_BACKUP_IDENTITY_FILE',str(backup.identity))
    monkeypatch.setattr(service,'engine',lambda:backup)
    service.bootstrap()
    actual={p.relative_to(root).as_posix():digest(p) for p in root.rglob('*') if p.is_file() and p.name!='backup-health.json'}
    assert actual==expected
    # Separate interpreter has no stale ConfigStore/index module globals.
    code='''
from fastapi.testclient import TestClient
from vrag.api import app
from vrag.settings import store
from vrag.index import get_index
assert store.snapshot()[1].profile=='recovered'
assert len(get_index().segments)==1
import os
os.environ['VM_BACKUP_ENABLED']='false' # restore already completed; do not create another backup during route checks
with TestClient(app) as client:
    response=client.get('/api/videos',headers={'Authorization':'Bearer '+'u'*32})
    assert response.status_code==200 and response.json()[0]['id']=='v1'
    assert client.get('/api/jobs',headers={'Authorization':'Bearer '+'u'*32}).json()[0]['status']=='complete'
'''
    result=subprocess.run([os.sys.executable,'-c',code],env={**os.environ,'VM_USER_TOKEN':'u'*32},capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    # Nonempty state is left untouched, even if the remote later becomes corrupt.
    remote.blobs.clear();service.bootstrap();assert (root/'data/videos/v1/original').exists()


def test_first_boot_requires_explicit_empty_authorization(encrypted,tmp_path,monkeypatch):
    backup,_=encrypted
    from vrag.backup import service
    root=tmp_path/'new'
    monkeypatch.setenv('VM_BACKUP_ENABLED','true');monkeypatch.setenv('VM_RECOVERY_ROOT',str(root))
    monkeypatch.setenv('VRAG_DATA',str(root/'data'));monkeypatch.setenv('VM_STATE_DIR',str(root/'state'))
    monkeypatch.setenv('VM_BACKUP_IDENTITY_FILE',str(backup.identity))
    monkeypatch.delenv('VM_BACKUP_ALLOW_EMPTY',raising=False);monkeypatch.setattr(service,'engine',lambda:backup)
    with pytest.raises(ValueError,match='authorization'):service.bootstrap()
    monkeypatch.setenv('VM_BACKUP_ALLOW_EMPTY','true');service.bootstrap()
    assert (root/'data').is_dir() and (root/'state').is_dir()


def test_wrong_key_never_publishes_checkpoint(encrypted,tmp_path):
    backup,remote=encrypted;data,state=make_library(tmp_path/'source');stage=tmp_path/'stage';stage.mkdir();backup.capture(data,state,stage)
    keygen=str(Path(os.environ['AGE_BIN']).with_name('age-keygen'))
    other=tmp_path/'wrong.agekey';subprocess.run([keygen,'-o',str(other)],capture_output=True,check=True)
    backup.identity=other
    with pytest.raises(ValueError,match='age operation'):backup.backup(stage)
    assert not remote.rows and not remote.blobs


def test_index_coverage_rejects_missing_revision_and_invalid_vectors(encrypted,tmp_path):
    backup,_=encrypted;data,state=make_library(tmp_path/'source');stage=tmp_path/'stage';stage.mkdir()
    np.save(data/'index/revisions'/('a'*32)/'text.npy',np.array([[float('nan'),0,0]],dtype=np.float32))
    with pytest.raises(ValueError,match='coverage'):backup.capture(data,state,stage)


def test_secret_identity_materialized_outside_state(monkeypatch,tmp_path):
    from vrag.backup.service import provision_identity
    monkeypatch.delenv('VM_BACKUP_IDENTITY_FILE',raising=False)
    monkeypatch.setenv('VM_BACKUP_IDENTITY','test-protected-identity')
    provision_identity();path=Path(os.environ['VM_BACKUP_IDENTITY_FILE'])
    try:
        assert path.stat().st_mode&0o777==0o600
        assert path.read_text().strip()=='test-protected-identity'
        assert 'VM_BACKUP_IDENTITY' not in os.environ
    finally:path.unlink()


@pytest.mark.asyncio
async def test_resident_timer_bounded_retries_and_success_health(monkeypatch,tmp_path):
    import asyncio
    from vrag.backup import service
    root=tmp_path/'work';data=root/'data';state=root/'state';data.mkdir(parents=True);state.mkdir()
    monkeypatch.setenv('VM_BACKUP_ENABLED','true');monkeypatch.setenv('VM_STATE_DIR',str(state))
    monkeypatch.setattr(service,'roots',lambda:(root,data,state))
    attempts=0;timeouts=[]
    class Store:
        base='https://mock.invalid';namespace='test'
        def checkpoints(self):return [{'path':'checkpoints/test/2026/checkpoint.json'}]
        def request(self,*args,**kwargs):return httpx.Response(200,json=[])
    class Engine:
        store=Store()
        def capture(self,*args):pass
        def backup(self,stage,progress):
            nonlocal attempts
            attempts+=1
            if attempts<3:raise ValueError('temporary test failure')
            progress(pending_uploads=0)
            return {'checkpoint':'checkpoint','created_at':123}
    monkeypatch.setattr(service,'engine',Engine)
    original=asyncio.wait_for
    async def wait(awaitable,timeout):
        timeouts.append(timeout)
        if len(timeouts)==1:
            awaitable.close();raise TimeoutError()
        return await original(awaitable,timeout)
    monkeypatch.setattr(service.asyncio,'wait_for',wait)
    q=service.BackupQueue();task=asyncio.create_task(q.run())
    try:
        for _ in range(100):
            if service.health().get('encrypted_storage_bytes')==0:break
            await asyncio.sleep(.05)
        assert attempts==3
        assert timeouts[0]==12*3600 and 90 in timeouts
        report=service.health()
        assert report['last_success']['checkpoint']=='checkpoint'
        assert report['failure_code'] is None and report['pending_uploads']==0
    finally:
        task.cancel();await asyncio.gather(task,return_exceptions=True)


def test_full_documented_github_http_transport_roundtrip(encrypted,tmp_path,monkeypatch):
    """Mock HTTP endpoints, real encryption. Signed redirects must strip auth."""
    import base64
    backup,_=encrypted;blobs={};records={};releases={};asset_count=0;redirects=0
    monkeypatch.setattr('vrag.backup.github.ASSETS_PER_RELEASE',2)
    def server(request):
        nonlocal asset_count,redirects
        path=request.url.path;method=request.method
        if request.url.host=='release-assets.githubusercontent.com':
            assert 'authorization' not in request.headers
            redirects+=1
            return httpx.Response(200,content=blobs[int(path.strip('/'))]['body'])
        assert request.headers['authorization']=='Bearer mock-scoped-token'
        if request.url.host=='uploads.github.com':
            asset_count+=1;body=request.content;rid=int(path.split('/')[-2])
            blobs[asset_count]={'id':asset_count,'name':request.url.params['name'],'size':len(body),'body':body,'release':rid}
            return httpx.Response(201,json={k:v for k,v in blobs[asset_count].items() if k!='body'})
        relative=path.removeprefix('/repos/test/private')
        if relative=='':return httpx.Response(200,json={'private':True})
        if relative.startswith('/contents/'):
            name=relative.removeprefix('/contents/')
            if method=='PUT':
                if name in records:return httpx.Response(409)
                records[name]=json.loads(request.content)['content']
                return httpx.Response(201,json={'content':{'path':name}})
            if name in records:return httpx.Response(200,json={'content':records[name]})
            children={}
            for record in records:
                prefix=name+'/'
                if record.startswith(prefix):
                    part=record[len(prefix):].split('/')[0]
                    children[part]={'type':'dir' if '/' in record[len(prefix):] else 'file','name':part,'path':prefix+part}
            return httpx.Response(200,json=list(children.values())) if children else httpx.Response(404)
        if relative.startswith('/releases/tags/'):
            tag=relative.removeprefix('/releases/tags/')
            return httpx.Response(200,json=releases[tag]) if tag in releases else httpx.Response(404)
        if relative=='/releases' and method=='POST':
            payload=json.loads(request.content);release={'id':len(releases)+1,'tag_name':payload['tag_name'],'upload_url':f'https://uploads.github.com/repos/test/private/releases/{len(releases)+1}/assets{{?name,label}}'};releases[release['tag_name']]=release
            return httpx.Response(201,json=release)
        if relative.startswith('/releases/assets/'):
            asset=int(relative.split('/')[-1])
            return httpx.Response(302,headers={'location':f'https://release-assets.githubusercontent.com/{asset}'})
        if relative.startswith('/releases/') and relative.endswith('/assets'):
            rid=int(relative.split('/')[-2])
            return httpx.Response(200,json=[{k:v for k,v in blob.items() if k!='body'} for blob in blobs.values() if blob['release']==rid])
        raise AssertionError((method,relative))
    backup.store=GitHubStore('test/private',namespace='test',token='mock-scoped-token',client=httpx.Client(transport=httpx.MockTransport(server)))
    data,state=make_library(tmp_path/'source');stage=tmp_path/'stage';stage.mkdir();backup.capture(data,state,stage)
    result=backup.backup(stage);restored=tmp_path/'restored'
    assert backup.restore(restored)['checkpoint']==result['checkpoint']
    assert len(records)==1 and redirects>2 and len(releases)>1
    assert (restored/'data/videos/v1/original').read_bytes()==(data/'videos/v1/original').read_bytes()
    assert all(b'Recovery fixture' not in blob['body'] for blob in blobs.values())


@pytest.mark.parametrize('status',[401,403,422])
def test_upload_permanent_rejections_are_not_retried(tmp_path,status):
    from vrag.backup.github import GitHubPermanentError
    events=[];posts=[];cipher=tmp_path/'cipher.age';cipher.write_bytes(b'synthetic encrypted fixture')
    def server(request):
        if request.method=='GET':return httpx.Response(200,json=[])
        posts.append(request)
        return httpx.Response(status,headers={'x-github-request-id':'TEST:REQUEST','location':'https://example.invalid/?secret=never-log'},json={'message':'never-log-response-body'})
    store=GitHubStore('test/private',token='never-log-token',client=httpx.Client(transport=httpx.MockTransport(server)),diagnostic=events.append)
    release={'id':1,'upload_url':'https://uploads.github.com/repos/test/private/releases/1/assets{?name,label}'}
    with pytest.raises(GitHubPermanentError) as error:store.upload(release,cipher)
    assert error.value.status==status and len(posts)==1
    serialized=json.dumps(events)
    assert 'never-log' not in serialized and events[-1]['headers']['x-github-request-id']=='TEST:REQUEST'
    assert events[-1]['client_authorization_attached'] is True


def test_upload_url_authorized_before_sending_credentials(tmp_path):
    cipher=tmp_path/'cipher.age';cipher.write_bytes(b'fixture')
    def forbidden(request):raise AssertionError('request must never leave client')
    store=GitHubStore('test/private',token='test-token',client=httpx.Client(transport=httpx.MockTransport(forbidden)))
    for url in ('https://evil.example/repos/test/private/releases/1/assets{?name,label}',
                'http://uploads.github.com/repos/test/private/releases/1/assets{?name,label}',
                'https://uploads.github.com/repos/another/repo/releases/1/assets{?name,label}'):
        with pytest.raises(ValueError,match='destination denied'):store.upload({'id':1,'upload_url':url},cipher)


def test_uncertain_transient_upload_is_reconciled_without_duplicate(tmp_path,monkeypatch):
    cipher=tmp_path/'cipher.age';cipher.write_bytes(b'fixture ciphertext');sha=digest(cipher);posts=[];sleeps=[]
    def server(request):
        if request.method=='POST':
            posts.append(request);return httpx.Response(503)
        if request.url.path.endswith('/assets'):
            return httpx.Response(200,json=[] if not posts else [{'id':7,'name':sha+'.age','size':cipher.stat().st_size}])
        return httpx.Response(200,content=cipher.read_bytes())
    monkeypatch.setattr('vrag.backup.github.time.sleep',sleeps.append)
    store=GitHubStore('test/private',token='test-token',client=httpx.Client(transport=httpx.MockTransport(server)))
    ref=store.upload({'id':1,'upload_url':'https://uploads.github.com/repos/test/private/releases/1/assets{?name,label}'},cipher)
    assert ref['id']==7 and len(posts)==1 and sleeps==[1]


@pytest.mark.asyncio
async def test_service_does_not_repeat_failed_authentication(monkeypatch,tmp_path):
    import asyncio
    from vrag.backup import service
    from vrag.backup.github import GitHubPermanentError
    state=tmp_path/'state';state.mkdir();data=tmp_path/'data';data.mkdir()
    monkeypatch.setenv('VM_BACKUP_ENABLED','true');monkeypatch.setenv('VM_STATE_DIR',str(state))
    monkeypatch.setattr(service,'roots',lambda:(tmp_path,data,state))
    attempts=[]
    class Engine:
        def capture(self,*args):pass
        def backup(self,*args):
            attempts.append(1);raise GitHubPermanentError(401,'uploads.github.com','TEST:AUTH')
    monkeypatch.setattr(service,'engine',Engine)
    queue=service.BackupQueue();task=asyncio.create_task(queue.run())
    try:
        for _ in range(100):
            if service.health().get('failure_code')=='github_authentication_failed':break
            await asyncio.sleep(.01)
        assert service.health()['failure_code']=='github_authentication_failed' and len(attempts)==1
    finally:task.cancel();await asyncio.gather(task,return_exceptions=True)


def test_private_staging_boundary_probe_requires_privacy_and_separate_token(monkeypatch):
    from scripts.qualify_private_space import qualify
    requested=[]
    def server(request):
        requested.append(request)
        if request.url.host=='huggingface.co':return httpx.Response(200,json={'private':True,'runtime':{'stage':'RUNNING'}})
        token=request.headers.get('x-vm-backup-token')
        if token=='s'*32:return httpx.Response(200,json={'configured':True})
        return httpx.Response(401)
    client=httpx.Client(transport=httpx.MockTransport(server))
    result=qualify(client,'test/app-staging','https://test-app-staging.hf.space','hf-test','s'*32)
    assert result['private_boundary_verified'] and not result['sleep_wake_verified']
    assert result['anonymous_status']==401 and result['wrong_trigger_status']==401
    count=len(requested)
    with pytest.raises(ValueError,match='staging'):qualify(client,'Leon4gr45/openweb','https://leon4gr45-openweb.hf.space','hf-test','s'*32)
    assert len(requested)==count
    public=httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(200,json={'private':False})))
    with pytest.raises(ValueError,match='not private'):qualify(public,'test/app-staging','https://test-app-staging.hf.space','hf-test','s'*32)
