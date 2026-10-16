import asyncio
import json
import numpy as np
import pytest
from fastapi.testclient import TestClient
from config.schema import Configuration, Provider, Route
from vrag.api import app
from vrag.index import get_index
from vrag.providers import Output, ProviderFailure
from vrag.remote import space_id, query, build_messages
from vrag.settings import store

@pytest.fixture
def corpus(tmp_path,monkeypatch):
    monkeypatch.setattr('vrag.remote.DATA',tmp_path)
    index=tmp_path/'index';index.mkdir();videos=tmp_path/'videos';videos.mkdir()
    video=videos/'v1';video.mkdir();(video/'segments').mkdir()
    seg={'id':'v1_000','video_id':'v1','title':'Demo','idx':0,'start':1,'end':3,'text':'a hand'}
    (index/'segments.json').write_text(json.dumps([seg]));np.save(index/'text.npy',np.array([[1.,0.,0.]],dtype='float32'))
    (video/'meta.json').write_text(json.dumps({'id':'v1','title':'Demo','duration':10}))
    (video/'segments.json').write_text(json.dumps([seg]))
    from PIL import Image
    Image.new('RGB',(20,20)).save(video/'segments/000.jpg')
    monkeypatch.setenv('URL','https://example.com/v1');monkeypatch.setenv('VM_USER_TOKEN','u'*32)
    p=Provider(adapter='openai-embeddings',base_url_env='URL',model='embedding',capabilities=['text_embeddings'],trust='approved_sensitive')
    vlm=Provider(adapter='openai-chat-vision',base_url_env='URL',model='vision',capabilities=['image_understanding','reasoning'],trust='approved_sensitive')
    old=store.history,store.version
    store.history=[Configuration(providers={'emb':p,'vlm':vlm},features={'rag.text_embeddings':Route(providers=['emb']),'rag.reasoning':Route(providers=['vlm'])})];store.version=1
    (index/'manifest.json').write_text(json.dumps({'embedding_space':space_id(p),'dimension':3}))
    for mod in ['vrag.index','vrag.api','vrag.remote']:
        monkeypatch.setattr(mod+'.INDEX_DIR',index)
    for mod in ['vrag.api','vrag.remote']:
        monkeypatch.setattr(mod+'.VIDEOS_DIR',videos)
    get_index.cache_clear()
    async def call(name,p,payload,sensitive):
        if name=='emb':return Output(embedding=[1,0,0])
        assert all(not im.startswith('file:') for im in payload.get('images',[]))
        return Output(text='A hand is visible [1].')
    monkeypatch.setattr('vrag.routing.adapter.call',call)
    yield seg,index
    store.history,store.version=old;get_index.cache_clear()

def test_library_search_ask_regression(corpus):
    with TestClient(app,headers={'Authorization':'Bearer '+'u'*32}) as c:
        assert len(c.get('/api/videos').json())==1
        assert c.get('/api/videos/v1').json()['segments'][0]['start']==1
        r=c.get('/api/search?q=hand&view=text&dim=3')
        assert r.status_code==200,r.text
        assert r.json()['hits'][0]['id']=='v1_000'
        r=c.post('/api/ask',json={'question':'what is shown?','view':'text','dim':3})
        assert r.status_code==200,r.text
        assert '[1]' in r.json()['answer'] and r.json()['clips'][0]['start']==1
        assert c.get('/api/search?q=x&view=text&dim=128').status_code==400

@pytest.mark.asyncio
async def test_incompatible_model_and_endpoint_requires_reembedding(corpus,monkeypatch):
    monkeypatch.setenv('URL','https://different.example/v1')
    with pytest.raises(ProviderFailure,match='index_incompatible'):
        await query('hi')

def test_bounded_frame_fallback(corpus):
    payload=build_messages('question',[corpus[0]],True,False)
    assert payload['images'][0].startswith('data:image/jpeg;base64,')
    assert '[1]' in payload['text'] and '1-3 seconds' in payload['text']
    with pytest.raises(ProviderFailure):build_messages('q',[corpus[0]],False,True)

def test_media_range(tmp_path):
    # Same Starlette handler used by production media mounting.
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    (tmp_path/'clip.mp4').write_bytes(b'0123456789')
    a=FastAPI();a.mount('/media',StaticFiles(directory=tmp_path))
    with TestClient(a) as c:
        r=c.get('/media/clip.mp4',headers={'Range':'bytes=2-5'})
        assert r.status_code==206 and r.content==b'2345'
