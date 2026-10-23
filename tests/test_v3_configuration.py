"""Gate 02: real schema/history/encryption; synthetic endpoints only."""
import asyncio
import json
from pathlib import Path
import shutil

import httpx
import pytest
import yaml
from fastapi.testclient import TestClient
from config.schema import Configuration, Provider, Route, parse_yaml, parse_configuration
from config.v2 import ConfigurationV2, ProviderV2, migrate, FEATURE_ROLES
from vrag.settings import ConfigStore
from vrag.runtime_config import with_environment_defaults, environment_summary
from vrag.providers import Adapter, ProviderFailure, Detection
from vrag.routing import route, fuse_detections
from vrag.api import app
from test_github_checkpoints import encrypted, make_library  # Real age + mock GitHub fixture.

@pytest.fixture
def environment(monkeypatch):
    for name in ('OPENAI_COMPATIBLE_URL','OPENAI_COMPATIBLE_MODEL','OPENAI_COMPATIBLE_API_KEY','A2A_URL','A2A_TOKEN'):
        monkeypatch.delenv(name,raising=False)
    monkeypatch.setenv('VM_ALLOWED_HOSTS','models.example,agents.example')
    monkeypatch.setattr('socket.getaddrinfo',lambda *a,**k:[(2,1,6,'',('8.8.8.8',443))])


def test_migrate_all_legacy_examples_and_unknown_fields(environment):
    for path in Path('config/examples').glob('*.yaml'):
        before=parse_yaml(path.read_text())
        after=migrate(before)
        assert after.version==2
        if before.version==1:
            assert before.version==1 and after.migrated_from==1
            assert {k:r.model_dump() for k,r in before.features.items()}=={k:r.model_dump() for k,r in after.features.items()}
        assert parse_yaml(yaml.safe_dump(after.model_dump()))==after
    # Arbitrary legacy named routes survive explicit migration as well.
    assert migrate(parse_yaml('features: {custom.review: {providers: [p], enabled: false}}\nproviders: {p: {adapter: openai-chat-vision, model: m, base_url_env: URL, capabilities: [reasoning]}}')).features['custom.review']
    for value in ({'version':True},{'version':3},{'version':2,'secret':'no'},
                  {'version':2,'providers':{'p':{'adapter':'nvidia-native','model':'x','base_url_env':'URL','capabilities':[]}}}):
        with pytest.raises(ValueError):parse_configuration(value)
    with pytest.raises(ValueError):ProviderV2(adapter='laya-vision',model='thaitea/laya-vision',base_url_env='URL',capabilities=['bounding_boxes'])
    with pytest.raises(ValueError):ProviderV2(adapter='openai-conversation',model='q',base_url_env='URL',capabilities=['conversation'],capability_version=2)
    with pytest.raises(ValueError):Provider(adapter='openai-conversation',model='q',base_url_env='URL',capabilities=[])
    with pytest.raises(ValueError):ProviderV2(adapter='a2a',model='a',base_url_env='A2A_URL',api_key_secret='VM_ADMIN_TOKEN',capabilities=['research_dispatch'])


@pytest.mark.asyncio
async def test_raw_v1_history_restart_cas_export_and_rollback(tmp_path,environment):
    raw=[{'version':1,'profile':'old-1'}, {'profile':'old-2','privacy':{'record_video':False}}]
    (tmp_path/'config-history.json').write_text(json.dumps(raw))
    s=ConfigStore(tmp_path)
    assert s.version==2 and s.history[0].version==1
    v2=migrate(s.snapshot()[1]);assert v2.version==2
    await s.apply(v2,2)
    assert json.loads((tmp_path/'config-history.json').read_text())[:2]==raw
    s=ConfigStore(tmp_path)
    assert s.version==3 and s.snapshot()[1].version==2 and s.serialized_revision(1)==raw[0]
    with pytest.raises(ValueError,match='reload'):await s.apply(v2,2)
    await s.apply(s.history[0],3)
    s=ConfigStore(tmp_path)
    assert s.snapshot()[1].version==1 and s.version==4 and s.serialized_revision(2)==raw[1]


def test_mixed_v1_v2_history_survives_real_encrypted_restore(encrypted,tmp_path,environment):
    backup,remote=encrypted
    root=tmp_path/'source';data,state=make_library(root)
    raw=[{'version':1,'profile':'historical'}, migrate(Configuration(profile='v2-current')).model_dump()]
    (state/'config-history.json').write_text(json.dumps(raw))
    stage=tmp_path/'staging';stage.mkdir();backup.capture(data,state,stage)
    backup.backup(stage)
    shutil.rmtree(root);shutil.rmtree(stage)
    result=backup.restore(tmp_path/'restored');assert result['verified']
    restored=ConfigStore(tmp_path/'restored/state')
    assert restored.version==2 and restored.serialized_revision(1)==raw[0] and restored.snapshot()[1].version==2
    assert json.loads((tmp_path/'restored/state/config-history.json').read_text())==raw
    assert all(value.startswith(b'age-encryption.org/') for value in remote.blobs.values())


def test_hf_defaults_precedence_redaction_and_no_activation(environment,monkeypatch):
    assert environment_summary()['status']=='unconfigured'
    monkeypatch.setenv('OPENAI_COMPATIBLE_URL','https://models.example/v1')
    monkeypatch.setenv('OPENAI_COMPATIBLE_MODEL','Qwen/Qwen3.6-35B-A3B')
    monkeypatch.setenv('OPENAI_COMPATIBLE_API_KEY','synthetic-secret-never-export')
    monkeypatch.setenv('A2A_URL','https://agents.example/a2a')
    monkeypatch.setenv('A2A_TOKEN','synthetic-agent-secret')
    old=Configuration();cfg=with_environment_defaults(old)
    assert old.providers=={} and cfg.version==2
    assert cfg.providers['hf-conversation'].model_env=='OPENAI_COMPATIBLE_MODEL'
    assert cfg.providers['hf-research'].api_key_secret=='A2A_TOKEN'
    assert not any(r.enabled for r in cfg.features.values())
    text=yaml.safe_dump(cfg.model_dump())+json.dumps(environment_summary())
    assert 'synthetic-secret-never-export' not in text and 'synthetic-agent-secret' not in text
    assert 'https://models.example/v1' not in text # host summary and env reference only
    assert environment_summary()['providers']['hf-conversation']['credential_present'] is True
    assert environment_summary()['live_status']=='not_checked'
    override=cfg.model_copy(deep=True)
    override.providers['hf-conversation']=override.providers['hf-conversation'].model_copy(update={'model':'yaml-model','model_env':None})
    assert with_environment_defaults(override).providers['hf-conversation'].model=='yaml-model'
    monkeypatch.setenv('OPENAI_COMPATIBLE_URL','http://unapproved.invalid')
    assert with_environment_defaults(override).providers['hf-conversation'].model=='yaml-model'
    assert environment_summary()['status']=='configuration_error'
    with pytest.raises(ProviderFailure,match='configuration_invalid'):with_environment_defaults(old)


@pytest.mark.asyncio
@pytest.mark.parametrize('suffix',['','/v1','/v1/'])
async def test_conversation_base_path_model_and_secret_from_environment(environment,monkeypatch,suffix):
    monkeypatch.setenv('OPENAI_COMPATIBLE_URL','https://models.example'+suffix)
    monkeypatch.setenv('OPENAI_COMPATIBLE_MODEL','selected-model')
    monkeypatch.setenv('OPENAI_COMPATIBLE_API_KEY','synthetic-key')
    p=with_environment_defaults(Configuration()).providers['hf-conversation']
    p=p.model_copy(update={'trust':'approved_sensitive'})
    def reply(request):
        assert request.url.path=='/v1/chat/completions'
        assert request.headers['authorization']=='Bearer synthetic-key'
        assert json.loads(request.content)['model']=='new-runtime-model'
        return httpx.Response(200,json={'choices':[{'message':{'content':'synthetic answer'}}]})
    monkeypatch.setenv('OPENAI_COMPATIBLE_MODEL','new-runtime-model')
    out=await Adapter(httpx.MockTransport(reply)).call('qwen',p,{'text':'hello'})
    assert out.text=='synthetic answer'
    with pytest.raises(ProviderFailure,match='capability_mismatch'):
        await Adapter(httpx.MockTransport(reply)).call('qwen',p,{'image':'must-not-send'})


def test_api_migration_preview_mixed_revision_export_auth_and_safe_errors(tmp_path,environment,monkeypatch):
    store=ConfigStore(tmp_path);monkeypatch.setattr('vrag.mentor_api.store',store)
    monkeypatch.setenv('VM_ADMIN_TOKEN','a'*32);monkeypatch.setenv('VM_USER_TOKEN','u'*32)
    monkeypatch.setenv('OPENAI_COMPATIBLE_URL','https://models.example/v1')
    monkeypatch.setenv('OPENAI_COMPATIBLE_MODEL','qwen-fixture')
    monkeypatch.setenv('OPENAI_COMPATIBLE_API_KEY','SENSITIVE_SENTINEL_NEVER_RETURN')
    c=TestClient(app,headers={'Authorization':'Bearer '+'a'*32})
    r=c.post('/api/config/migrate',json={'yaml':'profile: old','include_environment_defaults':True})
    assert r.status_code==200 and not r.json()['persisted'] and store.version==1
    text=r.json()['yaml'];assert 'SENSITIVE_SENTINEL' not in text
    assert c.post('/api/config/apply',json={'yaml':text,'expected_version':1}).status_code==200
    config=c.get('/api/config').json()
    assert config['schema_version']==2 and config['history_revision']==2
    assert set(FEATURE_ROLES)<=set(config['roles'])
    assert 'SENSITIVE_SENTINEL' not in json.dumps(config)
    export=c.get('/api/config/history/1');assert export.json()['schema_version']==1
    assert c.post('/api/config/rollback',json={'version':1,'expected_version':2}).status_code==200
    assert c.get('/api/config').json()['schema_version']==1
    assert c.post('/api/config/migrate',json={'yaml':'{}'},headers={'Authorization':''}).status_code==401
    assert c.get('/api/config/history/1',headers={'Authorization':''}).status_code==401
    monkeypatch.setenv('OPENAI_COMPATIBLE_URL','https://credentials:password@models.example')
    r=c.get('/api/providers',headers={'Authorization':'Bearer '+'u'*32})
    assert r.status_code==422 and 'password' not in r.text
    assert c.get('/api/config').json()['environment_defaults']['status']=='configuration_error'


def test_conservative_fusion_retains_sources_and_distinct_upstream_objects():
    def d(source,ident,confidence,box=(.1,.1,.5,.5),oid=None):
        return Detection(detection_id=ident,source=source,label='tool',bbox_xyxy=box,confidence=confidence,object_id=oid)
    result=fuse_detections([d('a','1',.9),d('b','2',.8),d('a','3',.7,(.7,.7,.9,.9))])
    assert len(result)==2 and {e.source for e in result[0].evidence}=={'a','b'}
    assert len(fuse_detections([d('tracker','1',.9,oid='one'),d('tracker','2',.8,oid='two')]))==2
    assert [x.model_dump() for x in result]==[x.model_dump() for x in fuse_detections([d('a','3',.7,(.7,.7,.9,.9)),d('b','2',.8),d('a','1',.9)])]


def test_environment_default_synthetic_probe_is_text_only(tmp_path,environment,monkeypatch):
    store=ConfigStore(tmp_path);monkeypatch.setattr('vrag.mentor_api.store',store)
    monkeypatch.setenv('VM_ADMIN_TOKEN','a'*32)
    monkeypatch.setenv('OPENAI_COMPATIBLE_URL','https://models.example/v1')
    monkeypatch.setenv('OPENAI_COMPATIBLE_MODEL','qwen-fixture')
    monkeypatch.setenv('OPENAI_COMPATIBLE_API_KEY','synthetic-probe-key')
    requests=[]
    def reply(request):
        from v3_protocol_fixtures import calls,completion
        body=json.loads(request.content);requests.append(body)
        assert all(isinstance(m['content'],str) for m in body['messages'])
        if body['messages'][-1]['role']=='tool':
            assert body['messages'][-1]['tool_call_id']=='call_0'
            content=completion('Synthetic follow-up verified')
        else:content=calls([('retrieve_video_evidence',{'query':'synthetic'})])
        content=content.replace('fixture-qwen','qwen-fixture')
        return httpx.Response(200,headers={'content-type':'text/event-stream'},content=content)
    monkeypatch.setattr('vrag.providers.adapter',Adapter(httpx.MockTransport(reply)))
    c=TestClient(app,headers={'Authorization':'Bearer '+'a'*32})
    result=c.post('/api/providers/hf-conversation/test')
    assert result.status_code==200,result.text
    assert result.json()['synthetic'] is True
    assert result.json()['correlation']=='passed' and result.json()['model_identity']=='matched'
    assert len(requests)==3
