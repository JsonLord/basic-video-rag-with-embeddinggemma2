"""Source and captured-live Laya wire formats, replayed via mock HTTP only."""
import json
from pathlib import Path

import httpx
import pytest
from config.schema import Provider, parse_yaml
from vrag.providers import Adapter, ProviderFailure

@pytest.fixture
def laya(monkeypatch):
    monkeypatch.setenv('LAYA_URL','https://laya.example')
    monkeypatch.setenv('VM_ALLOWED_HOSTS','laya.example')
    monkeypatch.setattr('socket.getaddrinfo',lambda *a,**k:[(2,1,6,'',('8.8.8.8',443))])
    return Provider(adapter='laya-vision',base_url_env='LAYA_URL',model='thaitea/laya-vision',capabilities=['visual_decision','image_understanding'],trust='approved_sensitive')

@pytest.mark.asyncio
@pytest.mark.parametrize('shape',['source','live'])
async def test_documented_and_observed_response_shapes(laya,shape):
    response=json.loads((Path(__file__).parent/'fixtures/laya-live-synthetic.json').read_text())
    if shape=='source':response['results']=response['results']['answers']
    def reply(request):
        assert request.url.path=='/v1/system-one'
        body=json.loads(request.content)
        assert body['imageBase64']=='eA=='
        assert 'image' not in body and isinstance(body['state'],dict)
        assert set(body['questions'])=={'visual_signal'}
        return httpx.Response(200,json=response)
    out=await Adapter(httpx.MockTransport(reply)).call('laya',laya,{'image':'data:image/jpeg;base64,eA=='})
    assert not out.detections and not out.text and out.decisions[0].action=='visual_assessment'

@pytest.mark.asyncio
@pytest.mark.parametrize('bad',['placeholder','text_backend','wrong_model','missing_answer','non_probability','wrong_type'])
async def test_rejects_invalid_or_placeholder_predictions(laya,bad):
    response={'backend':'laya-vision','model':'thaitea/laya-vision','results':{'visual_signal':{'type':'noul','noul':.5}}}
    if bad=='placeholder':response['results']['model']='laya-vision-placeholder'
    if bad=='text_backend':response['backend']='laya'
    if bad=='wrong_model':response['model']='other-model'
    if bad=='missing_answer':response['results']={}
    if bad=='non_probability':response['results']['visual_signal']['noul']=2
    if bad=='wrong_type':response['results']['visual_signal']['type']='choice'
    a=Adapter(httpx.MockTransport(lambda r:httpx.Response(200,json=response)))
    with pytest.raises(ProviderFailure,match='invalid_output'):
        await a.call('laya',laya,{'image':'data:image/jpeg;base64,eA=='})

def test_all_shipped_profiles_are_schema_valid():
    for path in (Path(__file__).parent.parent/'config/examples').glob('*.yaml'):
        parse_yaml(path.read_text())

def test_image_and_detection_capability_declarations_are_consistent():
    for adapter,capabilities in [('laya-vision',['image_understanding']),('detection-http',['object_tracking'])]:
        with pytest.raises(ValueError):
            Provider(adapter=adapter,base_url_env='URL',model='x',capabilities=capabilities)
