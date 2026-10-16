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
