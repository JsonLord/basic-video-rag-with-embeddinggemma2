import httpx
import pytest
from config.schema import Provider
from vrag.providers import Adapter, ProviderFailure

@pytest.fixture
def remote(monkeypatch):
    monkeypatch.setenv('TEST_URL', 'https://inference.example/v1')
    monkeypatch.setenv('VM_ALLOWED_HOSTS', 'inference.example')
    monkeypatch.setattr('socket.getaddrinfo', lambda *a, **k: [(2, 1, 6, '', ('8.8.8.8', 443))])

def provider(adapter='openai-chat-vision', caps=None):
    return Provider(adapter=adapter, base_url_env='TEST_URL', model='test', capabilities=caps or ['image_understanding'], trust='approved_sensitive')

@pytest.mark.asyncio
async def test_chat_never_invents_boxes(remote):
    async def mock(req):
        assert req.url.path == '/v1/chat/completions'
        return httpx.Response(200, json={'choices': [{'message': {'content': 'a hand at [0,0,1,1]'}}]})
    out = await Adapter(httpx.MockTransport(mock)).call('vlm', provider(), {'image': 'data:image/jpeg;base64,eA=='})
    assert out.detections == []
    assert out.decisions[0].source == 'vlm'

@pytest.mark.asyncio
async def test_embeddings(remote):
    out = await Adapter(httpx.MockTransport(lambda r: httpx.Response(200, json={'data': [{'embedding': [1,2,3]}]}))).call('emb', provider('openai-embeddings', ['text_embeddings']), {'text': 'hello'})
    assert out.embedding == [1,2,3]

@pytest.mark.asyncio
async def test_destination_denied(remote, monkeypatch):
    monkeypatch.setenv('TEST_URL', 'http://169.254.169.254')
    with pytest.raises(ProviderFailure, match='destination_denied'):
        await Adapter().call('x', provider(), {})

@pytest.mark.asyncio
async def test_no_secret_in_errors(remote):
    with pytest.raises(ProviderFailure, match='provider_error'):
        await Adapter(httpx.MockTransport(lambda r: httpx.Response(401, text='secret'))).call('x', provider(), {})

@pytest.mark.asyncio
async def test_remote_whisper_multipart(remote):
    def mock(req):
        assert req.url.path == '/v1/audio/transcriptions'
        assert b'name="file"' in req.content and b'speech.webm' in req.content
        return httpx.Response(200,json={'text':'hello'})
    out=await Adapter(httpx.MockTransport(mock)).call('stt',provider('openai-transcription',['transcription']),{'audio':b'webm'})
    assert out.text=='hello'

@pytest.mark.asyncio
async def test_detector_provenance_and_frame_validation(remote):
    payload={'image':'x','frame_id':1,'camera_id':'camera2','width':640,'height':480}
    data={'frame_id':1,'camera_id':'camera2','width':640,'height':480,'detections':[{'label':'hand','bbox_xyxy':[.1,.2,.4,.6],'confidence':.9}]}
    a=Adapter(httpx.MockTransport(lambda r:httpx.Response(200,json=data)))
    p=provider('detection-http',['object_detection','bounding_boxes'])
    out=await a.call('detector',p,payload)
    assert out.detections[0].source=='detector' and out.detections[0].object_id is None
    data['frame_id']=2
    with pytest.raises(ProviderFailure,match='invalid_output'):
        await a.call('detector',p,payload)

@pytest.mark.asyncio
async def test_private_ip_and_redirect_are_denied(remote,monkeypatch):
    monkeypatch.setattr('socket.getaddrinfo',lambda *a,**k:[(2,1,6,'',('127.0.0.1',443))])
    with pytest.raises(ProviderFailure,match='destination_denied'):
        await Adapter().call('x',provider(),{})
    monkeypatch.setattr('socket.getaddrinfo',lambda *a,**k:[(2,1,6,'',('8.8.8.8',443))])
    calls=[]
    def mock(req):
        calls.append(req.url)
        return httpx.Response(302,headers={'location':'https://evil.example'})
    with pytest.raises(ProviderFailure):
        await Adapter(httpx.MockTransport(mock)).call('x',provider(),{})
    assert len(calls)==1

@pytest.mark.asyncio
async def test_timeout_circuit_breaker_and_concurrency(remote):
    import asyncio
    p=provider().model_copy(update={'timeout_ms':100,'concurrency':1})
    async def slow(req):
        await asyncio.sleep(1)
        return httpx.Response(200,json={})
    a=Adapter(httpx.MockTransport(slow))
    first=asyncio.create_task(a.call('slow',p,{}))
    await asyncio.sleep(.01)
    with pytest.raises(ProviderFailure,match='busy'):
        await a.call('slow',p,{})
    with pytest.raises(ProviderFailure,match='timeout'):
        await first
    for _ in range(2):
        with pytest.raises(ProviderFailure,match='timeout'):
            await a.call('slow',p,{})
    with pytest.raises(ProviderFailure,match='circuit_open'):
        await a.call('slow',p,{})

@pytest.mark.asyncio
async def test_sensitive_destination_checked_on_each_call(remote):
    p=provider().model_copy(update={'trust':'public_only'})
    with pytest.raises(ProviderFailure,match='destination_denied'):
        await Adapter().call('public',p,{'image':'sensitive'})
