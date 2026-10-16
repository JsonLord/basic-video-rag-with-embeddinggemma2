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
