import pytest
from fastapi.testclient import TestClient
from vrag.api import app
from vrag.settings import ConfigStore

@pytest.fixture
def admin_client(tmp_path,monkeypatch):
    store=ConfigStore(tmp_path)
    monkeypatch.setattr('vrag.mentor_api.store',store)
    monkeypatch.setenv('VM_ADMIN_TOKEN','a'*32)
    with TestClient(app,headers={'Authorization':'Bearer '+'a'*32}) as c:yield c

def test_validate_apply_rollback_version_conflict_and_redaction(admin_client):
    c=admin_client
    assert c.post('/api/config/validate',json={'yaml':'profile: changed'}).json()['changed_sections']==['profile']
    r=c.post('/api/config/apply',json={'yaml':'profile: changed','expected_version':1})
    assert r.status_code==200 and r.json()['config_version']==2
    assert c.post('/api/config/apply',json={'yaml':'profile: stale','expected_version':1}).status_code==409
    assert c.post('/api/config/rollback',json={'version':1,'expected_version':2}).status_code==200
    cfg=c.get('/api/config').json()
    assert cfg['config_version']==3 and 'unconfigured' in cfg['yaml']
    assert 'a'*32 not in cfg['yaml']
    bad=c.post('/api/config/validate',json={'yaml':'api_key: TOP_SECRET'})
    assert bad.status_code==422 and 'TOP_SECRET' not in bad.text

def test_all_configuration_paths_require_admin(admin_client):
    c=admin_client
    headers={'Authorization':'Bearer '+'u'*32}
    for path in ['/api/config','/api/config/template','/api/config/profiles']:
        assert c.get(path,headers=headers).status_code==401
    for path,body in [('/api/config/validate',{'yaml':'{}'}),('/api/config/apply',{'yaml':'{}'}),('/api/config/rollback',{'version':1,'expected_version':1}),('/api/providers/x/test',{}),('/api/routing/dry-run',{'feature':'live.camera1.scene'})]:
        assert c.post(path,headers=headers,json=body).status_code==401

def test_unconfigured_disabled_optional_provider_does_not_block_config(admin_client,monkeypatch):
    monkeypatch.delenv('OPTIONAL_URL',raising=False)
    body={'yaml':'''profile: optional-disabled
providers:
  optional: {adapter: openai-transcription, base_url_env: OPTIONAL_URL, model: whisper, capabilities: [transcription]}
features:
  audio.transcription: {providers: [optional], enabled: false}
''','expected_version':1}
    assert admin_client.post('/api/config/apply',json=body).status_code==200
    assert admin_client.get('/api/health').status_code==200
    assert admin_client.post('/api/config/validate',json={**body,'yaml':body['yaml'].replace('enabled: false','enabled: true')}).status_code==422
