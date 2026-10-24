"""Production configuration invariants; no HF settings or live credentials changed."""

import json
from pathlib import Path
import pytest
from config.schema import Route, parse_yaml
from config.v2 import ConfigurationV2
from vrag.runtime_config import with_environment_defaults, environment_summary


@pytest.fixture
def env(monkeypatch):
    values = {
        "OPENAI_COMPATIBLE_URL": "https://models.example/v1",
        "OPENAI_COMPATIBLE_MODEL": "synthetic-model",
        "OPENAI_COMPATIBLE_API_KEY": "gate06-synthetic-openai-key",
        "A2A_URL": "https://agent.example/a2a/t-{token}",
        "A2A_TOKEN": "gate06-synthetic-agent-key",
        "VM_ALLOWED_HOSTS": "models.example,agent.example",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    return values


def test_disabled_environment_defaults_remain_server_side_public_only_and_unqualified(
    env,
):
    cfg = with_environment_defaults(ConfigurationV2())
    assert cfg.providers["hf-research"].auth_mode == "path_token"
    assert all(not r.enabled for r in cfg.features.values())
    assert all(p.trust == "public_only" for p in cfg.providers.values())
    encoded = json.dumps(
        {"configuration": cfg.model_dump(), "summary": environment_summary()}
    )
    for key in ["OPENAI_COMPATIBLE_API_KEY", "A2A_TOKEN"]:
        assert env[key] not in encoded
    assert "t-{token}" not in json.dumps(environment_summary())
    assert environment_summary()["live_status"] == "not_checked"
    assert (
        cfg.providers["hf-conversation"].api_key_secret == "OPENAI_COMPATIBLE_API_KEY"
    )


def test_yaml_precedence_disabled_routes_and_no_automatic_research_identity_activation(
    env,
):
    declared = parse_yaml("""version: 2
providers:
  custom: {adapter: openai-conversation,model: operator-selected,base_url_env: OPENAI_COMPATIBLE_URL,capabilities: [conversation],trust: public_only}
features:
  mentor.conversation: {providers: [custom],enabled: false}
""")
    effective = with_environment_defaults(declared)
    assert effective.features["mentor.conversation"].providers == ["custom"]
    assert not effective.features["mentor.conversation"].enabled
    assert effective.providers["custom"].model == "operator-selected"
    assert "hf-conversation" not in effective.providers
    raw = effective.model_dump()
    raw["features"]["research.dispatch"] = Route(providers=["hf-research"]).model_dump()
    with pytest.raises(ValueError, match="verified Agent Card"):
        ConfigurationV2.model_validate(raw)


def test_frontend_has_no_provider_secret_reads_or_public_secret_environment_names():
    import re

    names = [
        "OPENAI_COMPATIBLE_API_KEY",
        "A2A_TOKEN",
        "VM_USER_TOKEN",
        "VM_ADMIN_TOKEN",
        "VM_BACKUP_GITHUB_TOKEN",
    ]
    for path in Path("web/src").rglob("*"):
        if not path.is_file() or path.suffix not in {".ts", ".tsx", ".js"}:
            continue
        source = path.read_text()
        for name in names:
            assert not re.search(
                r"process\.env(?:\." + name + r"\b|\[\s*[\"\x27]" + name + r"[\"\x27])",
                source,
            ), str(path)
            assert "NEXT_PUBLIC_" + name not in source, str(path)


def test_compiled_asset_scan_detects_leak_without_printing_secret(
    tmp_path, monkeypatch
):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "gate06_scan", "scripts/scan-frontend-secrets.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in module.NAMES:
        monkeypatch.setenv(name, "synthetic-" + name.lower() + "-canary")
    assert module.scan(tmp_path)["status"] == "BLOCKED_ASSETS"
    path = tmp_path / "client.js"
    path.write_text('console.log("public client")')
    assert module.scan(tmp_path)["status"] == "PASS"
    path.write_text('window.leaked="synthetic-a2a_token-canary"')
    result = module.scan(tmp_path)
    assert result["status"] == "FAIL" and result["matches"] == [
        {"variable": "A2A_TOKEN", "asset": "client.js"}
    ]
    assert "synthetic-a2a_token-canary" not in json.dumps(result)
