import pytest
from config.schema import Configuration, parse_yaml
from vrag.settings import ConfigStore

def test_yaml_rejects_code_aliases_duplicates_and_secret_values():
    for text in ['!!python/object/apply:os.system [echo bad]', 'a: &a [*a]', 'version: 1\nversion: 1', 'providers:\n  p:\n    api_key: secret', 'privacy: {record_video: true}']:
        with pytest.raises(Exception):
            parse_yaml(text)

def test_capabilities_and_references():
    with pytest.raises(ValueError):
        parse_yaml('features: {rag.text_embeddings: {providers: [missing]}}')
    with pytest.raises(ValueError):
        parse_yaml('providers: {x: {adapter: openai-chat-vision, base_url_env: URL, model: x, capabilities: [bounding_boxes]}}')

@pytest.mark.asyncio
async def test_atomic_history_snapshot_and_restart(tmp_path):
    s=ConfigStore(tmp_path)
    version, snapshot=s.snapshot()
    await s.apply(Configuration(profile='new'), version)
    assert snapshot.profile == 'unconfigured'
    assert ConfigStore(tmp_path).snapshot()[1].profile == 'new'
    with pytest.raises(ValueError, match='reload'):
        await s.apply(Configuration(), version)
    await s.apply(s.history[0], 2)
    assert ConfigStore(tmp_path).snapshot()[1].profile == 'unconfigured'

@pytest.mark.asyncio
async def test_read_only_defaults(monkeypatch):
    monkeypatch.delenv('VM_STATE_DIR', raising=False)
    with pytest.raises(ValueError, match='read-only'):
        await ConfigStore().apply(Configuration(), 1)

@pytest.mark.asyncio
async def test_backup_is_previous_committed_history(tmp_path):
    import json
    s=ConfigStore(tmp_path)
    await s.apply(Configuration(profile='first'),1)
    await s.apply(Configuration(profile='second'),2)
    previous=json.loads((tmp_path/'config-history.backup.json').read_text())
    assert previous[-1]['profile']=='first'
    assert ConfigStore(tmp_path).snapshot()[1].profile=='second'

def test_placeholder_models_are_never_enabled_by_templates():
    from pathlib import Path
    import yaml
    for path in Path('config/examples').glob('*.yaml'):
        cfg=parse_yaml(path.read_text())
        assert all(not route.enabled for route in cfg.features.values())
    text='''providers:
  p: {adapter: openai-embeddings, model: replace-with-model, base_url_env: URL, capabilities: [text_embeddings]}
features:
  rag.text_embeddings: {providers: [p]}
'''
    with pytest.raises(ValueError,match='placeholder'):parse_yaml(text)

def test_provider_yaml_cannot_repurpose_admin_or_infrastructure_secrets():
    from config.schema import Provider
    for name in ('VM_ADMIN_TOKEN','VM_USER_TOKEN','HF_TOKEN','GITHUB_TOKEN','AWS_SECRET_ACCESS_KEY','RCLONE_CONFIG_BASE64','AGE_RECOVERY_KEY','HTTPS_PROXY'):
        with pytest.raises(ValueError,match='cannot reference'):
            Provider(adapter='openai-embeddings',model='embedding',capabilities=['text_embeddings'],base_url_env='URL',api_key_secret=name)
