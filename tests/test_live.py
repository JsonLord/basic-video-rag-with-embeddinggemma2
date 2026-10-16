import base64
import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from vrag.api import app
from vrag.providers import Output, Decision, Detection
from vrag.mentor_api import sessions
from config.schema import parse_yaml
from vrag.settings import store

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('VM_USER_TOKEN','u'*32)
    monkeypatch.setenv('VM_ADMIN_TOKEN','a'*32)
    sessions.clear()
    old=store.history,store.version
    store.history=[parse_yaml('''providers:
  vlm: {adapter: openai-chat-vision, base_url_env: URL, model: x, capabilities: [image_understanding], trust: approved_sensitive}
features:
  live.camera1.scene: {providers: [vlm]}
''')];store.version=1
    async def mock(*args,**kwargs):
        return Output(decisions=[Decision(reason='safe observation',source='vlm')])
    monkeypatch.setattr('vrag.routing.adapter.call',mock)
    with TestClient(app,headers={'Authorization':'Bearer '+'u'*32}) as c:
        yield c
    store.history,store.version=old
    sessions.clear()

def frame():
    f=io.BytesIO();Image.new('RGB',(640,480)).save(f,format='JPEG')
    return {'camera_id':'camera1','frame_id':1,'captured_at':1234,'image':'data:image/jpeg;base64,'+base64.b64encode(f.getvalue()).decode(),'feature':'live.camera1.scene','config_version':1,'request_id':'request'}

def test_lifecycle_correlation_and_no_media_storage(client):
    sid=client.post('/api/live/sessions',json={'consent':True}).json()['session_id']
    r=client.post(f'/api/live/sessions/{sid}/frames',json=frame())
    assert r.status_code==200,r.text
    out=r.json()
    assert out['frame_id']==1 and out['camera_id']=='camera1' and out['source_width']==640
    assert out['detections']==[]
    assert 'image' not in str(sessions[sid].events)
    assert client.post(f'/api/live/sessions/{sid}/frames',json=frame()).status_code==409
    assert client.delete(f'/api/live/sessions/{sid}').status_code==200
    assert client.get(f'/api/live/sessions/{sid}/events').status_code==404

def test_consent_version_ownership_and_limits(client,monkeypatch):
    assert client.post('/api/live/sessions',json={'consent':False}).status_code==400
    sid=client.post('/api/live/sessions',json={'consent':True}).json()['session_id']
    assert client.post(f'/api/live/sessions/{sid}/frames',json={**frame(),'config_version':2}).status_code==409
    assert client.post(f'/api/live/sessions/{sid}/frames',json={**frame(),'feature':'live.camera2.scene'}).status_code==422
    sessions[sid].owner='different principal'
    assert client.get(f'/api/live/sessions/{sid}/events').status_code==404
    assert client.post('/api/config/apply',json={'yaml':'{}'}).status_code==401
    assert client.post('/api/live/sessions',content=b'x'*3200000).status_code==413

def test_origin_and_image_validation(client):
    assert client.post('/api/live/sessions',json={'consent':True},headers={'Origin':'https://evil.example'}).status_code==403
    sid=client.post('/api/live/sessions',json={'consent':True}).json()['session_id']
    assert client.post(f'/api/live/sessions/{sid}/frames',json={**frame(),'image':'not-an-image'}).status_code==422

def test_box_coordinates():
    with pytest.raises(ValueError):
        Detection(detection_id='x',label='hand',bbox_xyxy=[0.8,0,0.1,1],confidence=1,source='detector')
    with pytest.raises(ValueError):
        Detection(detection_id='x',label='hand',bbox_xyxy=[0,0,2,1],confidence=1,source='detector')
