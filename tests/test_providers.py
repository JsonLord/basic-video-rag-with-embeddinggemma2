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
