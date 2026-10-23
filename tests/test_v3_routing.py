"""Gate 02 routing qualifications; all remote transports synthetic."""
import asyncio
import base64
import io
import json
from pathlib import Path
import httpx
import pytest
from PIL import Image
from config.schema import Route
from config.v2 import ConfigurationV2
from config.schema import parse_yaml
from vrag.providers import Adapter, ProviderFailure
from vrag.routing import route
from vrag.settings import ConfigStore
from vrag.api import app
from vrag import mentor_api

@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv('VM_ALLOWED_HOSTS','laya.example,detector.example')
    monkeypatch.setenv('LAYA_BASE_URL','https://laya.example')
    monkeypatch.setenv('LAYA_API_KEY','synthetic-laya-credential')
    monkeypatch.setenv('NVIDIA_DETECTION_BASE_URL','https://detector.example')
    monkeypatch.setenv('NVIDIA_DETECTION_API_KEY','synthetic-detector-credential')
    monkeypatch.setattr('socket.getaddrinfo',lambda *a,**k:[(2,1,6,'',('8.8.8.8',443))])
    cfg=parse_yaml(Path('config/examples/v3-hybrid.yaml').read_text())
    cfg.providers['nvidia_gateway']=cfg.providers['nvidia_gateway'].model_copy(update={'model':'synthetic-gateway'})
    cfg.features['live.camera2.scene']=Route(strategy='parallel',providers=['laya','nvidia_gateway'],fusion='spatial_semantic')
    return ConfigurationV2.model_validate(cfg.model_dump())


def laya_reply():
    return {'backend':'laya-vision','model':'thaitea/laya-vision','results':{'visual_signal':{'type':'noul','noul':.7}}}

def detection_reply(frame=7,camera='camera2',width=640,height=480):
    return {'frame_id':frame,'camera_id':camera,'width':width,'height':height,'detections':[{'label':'tool','bbox_xyxy':[.1,.1,.4,.5],'confidence':.9}]}

@pytest.mark.asyncio
@pytest.mark.parametrize('profile',['Laya Fast','NVIDIA Precision','Hybrid','Custom'])
async def test_named_profiles_and_frame_provenance(configured,monkeypatch,profile):
    cfg=configured.model_copy(deep=True)
    rule=Route(providers=['laya']) if profile=='Laya Fast' else Route(providers=['nvidia_gateway']) if profile=='NVIDIA Precision' else Route(strategy='fallback',providers=['nvidia_gateway','laya']) if profile=='Custom' else cfg.features['live.camera2.scene']
    cfg.features['live.camera2.scene']=rule
    entered=set();both=asyncio.Event()
    async def reply(request):
        entered.add(request.url.host)
        if len(entered)==2:both.set()
        if profile=='Hybrid':await asyncio.wait_for(both.wait(),1)
        if request.url.host=='laya.example':
            assert json.loads(request.content)['imageBase64']=='eA=='
            return httpx.Response(200,json=laya_reply())
        if profile=='Custom':raise httpx.ReadTimeout('synthetic timeout')
        return httpx.Response(200,json=detection_reply())
    monkeypatch.setattr('vrag.routing.adapter',Adapter(httpx.MockTransport(reply)))
    payload={'image':'data:image/jpeg;base64,eA==','frame_id':7,'camera_id':'camera2','width':640,'height':480,'captured_at':321.25,'config_version':8}
    out,status=await route(cfg,'live.camera2.scene',payload)
    assert all(s['frame_id']==7 and s['camera_id']=='camera2' and s['captured_at']==321.25 and s['config_version']==8 and s['capability_version']==1 for s in status)
    assert bool(out.detections)==(profile in ('NVIDIA Precision','Hybrid'))
    assert bool(out.decisions)==(profile in ('Laya Fast','Hybrid','Custom'))
    assert all(d.source!='laya' for d in out.detections)
    if profile=='Custom':assert status[0]['status']=='timeout'

@pytest.mark.asyncio
@pytest.mark.parametrize('failed',['laya.example','detector.example'])
async def test_parallel_partial_failure_is_not_success_for_failed_provider(configured,monkeypatch,failed):
    async def reply(request):
        if request.url.host==failed:raise httpx.ReadTimeout('synthetic timeout')
        return httpx.Response(200,json=laya_reply() if request.url.host=='laya.example' else detection_reply())
    monkeypatch.setattr('vrag.routing.adapter',Adapter(httpx.MockTransport(reply)))
    out,status=await route(configured,'live.camera2.scene',{'image':'data:image/jpeg;base64,eA==','frame_id':7,'camera_id':'camera2','width':640,'height':480})
    assert sorted(s['status'] for s in status)==['ok','timeout']
    assert bool(out.detections)==(failed=='laya.example')
    assert bool(out.decisions)==(failed=='detector.example')

@pytest.mark.asyncio
async def test_v2_fallback_never_transfers_sensitive_media_to_public_only(configured,monkeypatch):
    cfg=configured.model_copy(deep=True)
    cfg.providers['laya']=cfg.providers['laya'].model_copy(update={'trust':'public_only'})
    cfg.features['live.camera2.scene']=Route(strategy='fallback',providers=['nvidia_gateway','laya'])
    calls=[]
    def reply(request):calls.append(request.url.host);return httpx.Response(503)
    monkeypatch.setattr('vrag.routing.adapter',Adapter(httpx.MockTransport(reply)))
    out,status=await route(cfg,'live.camera2.scene',{'image':'private'})
    assert calls==['detector.example'] and status[-1]['status']=='destination_denied' and not out.decisions

@pytest.mark.asyncio
async def test_cancelling_parallel_route_closes_all_inference(configured,monkeypatch):
    entered=set();cancelled=set();ready=asyncio.Event()
    async def reply(request):
        host=request.url.host;entered.add(host)
        if len(entered)==2:ready.set()
        try:await asyncio.Event().wait()
        except asyncio.CancelledError:cancelled.add(host);raise
    monkeypatch.setattr('vrag.routing.adapter',Adapter(httpx.MockTransport(reply)))
    task=asyncio.create_task(route(configured,'live.camera2.scene',{'image':'data:image/jpeg;base64,eA=='}))
    await asyncio.wait_for(ready.wait(),1);task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    assert cancelled==entered

@pytest.mark.asyncio
@pytest.mark.parametrize('change',['none','history','session'])
async def test_live_inflight_revision_changes_and_correlation(configured,monkeypatch,tmp_path,change):
    monkeypatch.setenv('VM_USER_TOKEN','u'*32)
    store=ConfigStore(tmp_path);store.history=[configured];store.version=1
    monkeypatch.setattr(mentor_api,'store',store)
    entered=asyncio.Event();release=asyncio.Event()
    async def reply(request):
        entered.set();await release.wait()
        return httpx.Response(200,json=laya_reply() if request.url.host=='laya.example' else detection_reply(1,'camera2',32,32))
    monkeypatch.setattr('vrag.routing.adapter',Adapter(httpx.MockTransport(reply)))
    image=io.BytesIO();Image.new('RGB',(32,32),'white').save(image,format='JPEG')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='https://testserver',headers={'Authorization':'Bearer '+'u'*32}) as client:
        sid=(await client.post('/api/live/sessions',json={'consent':True})).json()['session_id']
        body={'camera_id':'camera2','frame_id':1,'captured_at':456.25,'image':'data:image/jpeg;base64,'+base64.b64encode(image.getvalue()).decode(),'feature':'live.camera2.scene','config_version':1,'routing_revision':0,'request_id':'revision-test'}
        pending=asyncio.create_task(client.post(f'/api/live/sessions/{sid}/frames',json=body))
        await asyncio.wait_for(entered.wait(),1)
        if change=='history':await store.apply(configured.model_copy(update={'profile':'next'}),1)
        if change=='session':
            changed=await client.put(f'/api/live/sessions/{sid}/routing',json={'config_version':1,'feature':'live.camera2.scene','route':{'providers':['laya']}})
            assert changed.status_code==200 and changed.json()['routing_revision']==1
        release.set();result=await pending
        if change!='none':
            assert result.status_code==409 and not mentor_api.sessions[sid].events
        else:
            assert result.status_code==200,result.text
            data=result.json()
            assert data['schema_version']==2 and data['history_revision']==1 and data['routing_revision']==0
            assert data['frame_id']==1 and data['camera_id']=='camera2' and data['captured_at']==456.25
            assert all(s['captured_at']==456.25 for s in data['provider_results'])
        await client.delete(f'/api/live/sessions/{sid}')
