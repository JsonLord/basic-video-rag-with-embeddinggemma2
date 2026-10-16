"""Release regression checks; every network transport here is mocked."""
import asyncio
import json

import httpx
import pytest

from config.schema import Configuration, Provider, Route, parse_yaml
from vrag.egress import PublicAddressTransport
from vrag.providers import Adapter, ProviderFailure
from vrag.routing import route

@pytest.fixture
def network(monkeypatch):
    monkeypatch.setenv('URL', 'https://models.example/v1')
    monkeypatch.setenv('VM_ALLOWED_HOSTS', 'models.example')
    monkeypatch.setattr('socket.getaddrinfo', lambda *a, **k: [(2,1,6,'',('8.8.8.8',443))])

def provider(adapter='openai-chat-vision', caps=None):
    return Provider(adapter=adapter, base_url_env='URL', model='test', capabilities=['image_understanding'] if caps is None else caps, trust='approved_sensitive')

@pytest.mark.asyncio
async def test_direct_transport_pins_validated_ip_and_preserves_tls_hostname(network):
    seen=[]
    def reply(request):
        seen.append(request)
        assert request.url.host=='8.8.8.8'
        assert request.headers['host']=='models.example'
        assert request.extensions['sni_hostname']=='models.example'
        return httpx.Response(200,json={'ok':True})
    async with httpx.AsyncClient(transport=PublicAddressTransport(httpx.MockTransport(reply))) as client:
        assert (await client.get('https://models.example/v1/info')).status_code==200
    assert len(seen)==1

@pytest.mark.asyncio
async def test_rebound_private_address_is_never_connected(network, monkeypatch):
    monkeypatch.setattr('socket.getaddrinfo', lambda *a,**k:[(2,1,6,'',('127.0.0.1',443))])
    def should_not_connect(request):
        pytest.fail('private destination reached the transport')
    async with httpx.AsyncClient(transport=PublicAddressTransport(httpx.MockTransport(should_not_connect))) as client:
        with pytest.raises(httpx.ConnectError,match='denied'):
            await client.get('https://models.example/v1/info')

@pytest.mark.asyncio
@pytest.mark.parametrize('url',['https://[broken','https://models.example:bad/v1','https://models.example:8443','https://user:password@models.example','http://models.example'])
async def test_malformed_or_disallowed_url_is_safe_failure(network,monkeypatch,url):
    monkeypatch.setenv('URL',url)
    with pytest.raises(ProviderFailure,match='destination_denied'):
        await Adapter().call('vlm',provider(),{})

@pytest.mark.asyncio
@pytest.mark.parametrize('detections',[[None],None,{},[{'label':'hand','bbox_xyxy':[0,0,2,1],'confidence':1}]])
async def test_parallel_malformed_detector_is_independent(network,monkeypatch,detections):
    def reply(request):
        if request.url.path.endswith('/detect'):
            return httpx.Response(200,json={'camera_id':'camera2','frame_id':7,'width':640,'height':480,'detections':detections})
        return httpx.Response(200,json={'choices':[{'message':{'content':'A person is present.'}}]})
    a=Adapter(httpx.MockTransport(reply));monkeypatch.setattr('vrag.routing.adapter',a)
    config=Configuration(providers={'vision':provider(),'detector':provider('detection-http',['object_detection','bounding_boxes'])},features={
        'live.camera2.detection':Route(strategy='parallel',providers=['vision','detector'],fusion='spatial_semantic')})
    out,status=await route(config,'live.camera2.detection',{'image':'synthetic','camera_id':'camera2','frame_id':7,'width':640,'height':480})
    assert out.decisions[0].source=='vision' and out.detections==[]
    assert {s['provider']:s['status'] for s in status}=={'vision':'ok','detector':'invalid_output'}

@pytest.mark.asyncio
async def test_parallel_spatial_semantic_fusion_preserves_provenance(network,monkeypatch):
    entered=set();both=asyncio.Event()
    async def reply(request):
        entered.add(request.url.path)
        if len(entered)==2:both.set()
        await asyncio.wait_for(both.wait(),1)
        if request.url.path.endswith('/detect'):
            return httpx.Response(200,json={'camera_id':'camera2','frame_id':7,'width':640,'height':480,'detections':[{'label':'hand','bbox_xyxy':[.1,.2,.3,.4],'confidence':.9}]})
        return httpx.Response(200,json={'choices':[{'message':{'content':'Hand visible; inspect alignment.'}}]})
    a=Adapter(httpx.MockTransport(reply));monkeypatch.setattr('vrag.routing.adapter',a)
    config=Configuration(providers={'semantic':provider(),'nvidia_gateway':provider('detection-http',['object_detection','bounding_boxes'])},features={
        'live.camera2.detection':Route(strategy='parallel',providers=['semantic','nvidia_gateway'],fusion='spatial_semantic')})
    out,status=await route(config,'live.camera2.detection',{'image':'synthetic','camera_id':'camera2','frame_id':7,'width':640,'height':480})
    assert len(status)==2 and all(s['status']=='ok' for s in status)
    assert out.detections[0].source=='nvidia_gateway' and out.detections[0].bbox_xyxy==(.1,.2,.3,.4)
    assert out.detections[0].object_id is None and out.decisions[0].source=='semantic'

@pytest.mark.asyncio
@pytest.mark.parametrize('placeholder',[False,True])
async def test_laya_plus_detector_parallel_real_adapter_contract(network,monkeypatch,placeholder):
    from pathlib import Path
    monkeypatch.setenv('LAYA_URL','https://models.example')
    laya=Provider(adapter='laya-vision',base_url_env='LAYA_URL',model='thaitea/laya-vision',capabilities=['image_understanding','visual_decision'],trust='approved_sensitive')
    detector=provider('detection-http',['object_detection','bounding_boxes'])
    fixture=json.loads((Path(__file__).parent/'fixtures/laya-live-synthetic.json').read_text())
    if placeholder:fixture['model']='laya-vision-placeholder'
    called=set();both=asyncio.Event()
    async def reply(request):
        called.add(request.url.path)
        if len(called)==2:both.set()
        await asyncio.wait_for(both.wait(),1)
        if request.url.path=='/v1/system-one':
            body=json.loads(request.content)
            assert body['imageBase64']=='eA==' and 'image' not in body
            assert body['questions']['visual_signal']['type']=='noul'
            return httpx.Response(200,json=fixture)
        assert request.url.path=='/v1/detect'
        return httpx.Response(200,json={'frame_id':7,'camera_id':'camera2','width':640,'height':480,'detections':[{'label':'hand','bbox_xyxy':[.1,.2,.3,.4],'confidence':.9}]})
    cfg=Configuration(providers={'laya':laya,'nvidia_gateway':detector},features={
        'live.camera2.detection':Route(strategy='parallel',providers=['laya','nvidia_gateway'],fusion='spatial_semantic')})
    monkeypatch.setattr('vrag.routing.adapter',Adapter(httpx.MockTransport(reply)))
    out,status=await route(cfg,'live.camera2.detection',{'image':'data:image/jpeg;base64,eA==','camera_id':'camera2','frame_id':7,'width':640,'height':480})
    assert out.detections[0].source=='nvidia_gateway' and out.detections[0].object_id is None
    assert {s['provider']:s['status'] for s in status}=={'laya':'invalid_output' if placeholder else 'ok','nvidia_gateway':'ok'}
    assert len(out.decisions)==(0 if placeholder else 1)
    if not placeholder:assert out.decisions[0].source=='laya' and '0.3126' in out.decisions[0].reason

@pytest.mark.asyncio
async def test_fallback_reauthorizes_sensitive_destination(network,monkeypatch):
    p=provider();public=p.model_copy(update={'trust':'public_only'})
    calls=[]
    def reply(request):
        calls.append(request)
        return httpx.Response(503)
    monkeypatch.setattr('vrag.routing.adapter',Adapter(httpx.MockTransport(reply)))
    cfg=Configuration(providers={'first':p,'unapproved':public},features={'live.camera1.scene':Route(strategy='fallback',providers=['first','unapproved'])})
    out,status=await route(cfg,'live.camera1.scene',{'image':'sensitive'})
    assert len(calls)==1 and status[-1]['status']=='destination_denied' and not out.decisions

@pytest.mark.asyncio
async def test_changed_provider_does_not_inherit_old_circuit(network):
    a=Adapter(httpx.MockTransport(lambda r:httpx.Response(500)))
    for _ in range(3):
        with pytest.raises(ProviderFailure):await a.call('vision',provider(),{})
    a.transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'choices':[{'message':{'content':'ok'}}]}))
    out=await a.call('vision',provider().model_copy(update={'model':'replacement'}),{})
    assert out.text=='ok'

@pytest.mark.asyncio
@pytest.mark.parametrize('vector',[[[1,2]],[1e100,2],[],[0,0]])
async def test_invalid_embeddings_rejected(network,vector):
    a=Adapter(httpx.MockTransport(lambda r:httpx.Response(200,json={'data':[{'embedding':vector}]})))
    with pytest.raises(ProviderFailure,match='invalid_output'):
        await a.call('emb',provider('openai-embeddings',['text_embeddings']),{'text':'test'})

def test_role_and_predicate_configuration_validation():
    with pytest.raises(ValueError):
        parse_yaml('''providers:
  emb: {adapter: openai-embeddings, base_url_env: URL, model: e, capabilities: [text_embeddings]}
  vlm: {adapter: openai-chat-vision, base_url_env: URL, model: v, capabilities: [reasoning]}
features:
  rag.text_embeddings: {strategy: fallback, providers: [emb, vlm]}
''')
    with pytest.raises(ValueError):
        Route(strategy='conditional',providers=['x'],conditions=[{'field':'has_detections','equals':'false','provider':'x'}])

@pytest.mark.asyncio
async def test_proxy_only_dns_preserves_trusted_path_and_direct_fails_closed(network,monkeypatch):
    import socket
    def unavailable(*args,**kwargs):raise socket.gaierror(socket.EAI_AGAIN,'local DNS unavailable')
    monkeypatch.setattr('socket.getaddrinfo',unavailable)
    monkeypatch.setattr('vrag.providers.proxy_for',lambda base:'http://trusted-proxy:8080')
    a=Adapter(httpx.MockTransport(lambda r:httpx.Response(200,json={'choices':[{'message':{'content':'ok'}}]})))
    assert (await a.call('vision',provider(),{})).text=='ok'
    monkeypatch.setattr('vrag.providers.proxy_for',lambda base:None)
    with pytest.raises(ProviderFailure,match='destination_denied'):await a.call('vision',provider(),{})

@pytest.mark.asyncio
@pytest.mark.parametrize('failed',['laya','nvidia_gateway'])
async def test_laya_nvidia_timeout_preserves_other_typed_output(network,monkeypatch,failed):
    from pathlib import Path
    monkeypatch.setenv('LAYA_URL','https://models.example')
    laya=Provider(adapter='laya-vision',base_url_env='LAYA_URL',model='thaitea/laya-vision',capabilities=['image_understanding','visual_decision'],trust='approved_sensitive')
    detector=provider('detection-http',['object_detection','bounding_boxes'])
    response=json.loads((Path(__file__).parent/'fixtures/laya-live-synthetic.json').read_text())
    async def reply(request):
        is_laya=request.url.path.endswith('/system-one')
        if (is_laya and failed=='laya') or (not is_laya and failed=='nvidia_gateway'):
            raise httpx.ReadTimeout('synthetic timeout')
        if is_laya:return httpx.Response(200,json=response)
        return httpx.Response(200,json={'frame_id':7,'camera_id':'camera2','width':640,'height':480,'detections':[{'label':'hand','bbox_xyxy':[.1,.2,.3,.4],'confidence':.9}]})
    cfg=Configuration(providers={'laya':laya,'nvidia_gateway':detector},features={'live.camera2.detection':Route(strategy='parallel',providers=['laya','nvidia_gateway'],fusion='spatial_semantic')})
    monkeypatch.setattr('vrag.routing.adapter',Adapter(httpx.MockTransport(reply)))
    out,status=await route(cfg,'live.camera2.detection',{'image':'data:image/jpeg;base64,eA==','camera_id':'camera2','frame_id':7,'width':640,'height':480})
    assert next(s for s in status if s['provider']==failed)['status']=='timeout'
    assert bool(out.detections)==(failed=='laya')
    assert bool(out.decisions)==(failed=='nvidia_gateway')
