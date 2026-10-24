"""Real bounded diagnostic runner with synthetic OpenAI-compatible HTTP/SSE."""

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import httpx
import pytest
from vrag.qwen_qualification import qualify
from v3_protocol_fixtures import packet, calls, completion


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPATIBLE_URL", "https://models.example")
    monkeypatch.setenv("OPENAI_COMPATIBLE_MODEL", "fixture-qwen")
    monkeypatch.setenv(
        "OPENAI_COMPATIBLE_API_KEY", "qualification-synthetic-credential"
    )
    monkeypatch.setenv("VM_ALLOWED_HOSTS", "models.example")
    monkeypatch.setattr(
        "socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("8.8.8.8", 443))]
    )


class SlowResponse(httpx.AsyncByteStream):
    def __init__(self):
        self.closed = False

    async def __aiter__(self):
        await asyncio.sleep(1)
        yield completion("late response").encode()

    async def aclose(self):
        self.closed = True


class Server:
    def __init__(self):
        self.requests = []
        self.slow = []
        self.status = None
        self.model_list = True
        self.bad_model = False
        self.no_tools = False
        self.long_basic = False

    def __call__(self, request):
        self.requests.append(request)
        assert request.url.host == "models.example" and request.url.path in (
            "/v1/models",
            "/v1/chat/completions",
        )
        assert (
            request.headers["authorization"]
            == "Bearer qualification-synthetic-credential"
        )
        if self.status:
            return httpx.Response(
                self.status, headers={"location": "https://unapproved.example"}
            )
        if request.method == "GET":
            return (
                httpx.Response(200, json={"data": [{"id": "fixture-qwen"}]})
                if self.model_list
                else httpx.Response(404)
            )
        body = json.loads(request.content)
        assert body["model"] == "fixture-qwen"
        assert all(isinstance(m["content"], str) for m in body["messages"])
        if not body.get("stream"):
            if self.long_basic:
                stream = SlowResponse()
                self.slow.append(stream)
                return httpx.Response(200, stream=stream)
            return httpx.Response(
                200,
                json={
                    "model": "wrong-model" if self.bad_model else "fixture-qwen",
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "A synthetic greeting.",
                            }
                        }
                    ],
                },
            )
        last = body["messages"][-1]
        if last["role"] == "tool":
            assistant = body["messages"][-2]
            assert assistant["tool_calls"][0]["id"] == last["tool_call_id"]
            assert json.loads(last["content"])["synthetic"] is True
            content = completion("Follow-up uses the synthetic fixture result.")
        elif "tool-protocol" in last["content"]:
            content = (
                completion("Tools unavailable")
                if self.no_tools
                else calls([("retrieve_video_evidence", {"query": "synthetic"})])
            )
        elif "deadline qualification" in last["content"]:
            stream = SlowResponse()
            self.slow.append(stream)
            return httpx.Response(
                200, headers={"content-type": "text/event-stream"}, stream=stream
            )
        else:
            content = completion("A bounded synthetic streaming response.")
        return httpx.Response(
            200,
            headers={
                "content-type": "text/event-stream",
                "x-request-id": "fixture-request-123",
                "server": "ollama",
            },
            content=content,
        )


@pytest.mark.asyncio
async def test_complete_qualification_metrics_correlation_and_no_secrets(configured):
    server = Server()
    result = await qualify(
        transport_factory=lambda: httpx.MockTransport(server), backend="ollama"
    )
    assert result["status"] == "PASS", result
    assert result["kind"] == "mock_external_openai_qualification"
    assert len(server.requests) == 7
    assert result["checks"]["streaming"]["time_to_first_token_ms"] >= 0
    assert result["checks"]["timeout_behavior"]["observed"] == "client_timeout"
    assert result["checks"]["client_cancellation"]["response_closed"]
    assert server.slow[0].closed
    assert all(r["response_closed"] for r in result["http"])
    assert (
        result["model_identity_verified"]
        and result["remote_compute_cancellation"] == "NOT_OBSERVABLE"
    )
    assert (
        result["tool_side_effects"] is False and result["private_media_sent"] is False
    )
    encoded = json.dumps(result)
    assert "qualification-synthetic-credential" not in encoded
    assert "A bounded synthetic streaming response" not in encoded
    assert "call_0" not in encoded


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,code",
    [
        (401, "provider_auth_denied"),
        (403, "provider_auth_denied"),
        (302, "destination_denied"),
    ],
)
async def test_permanent_auth_and_redirect_failures_stop_without_retry(
    configured, status, code
):
    server = Server()
    server.status = status
    result = await qualify(transport_factory=lambda: httpx.MockTransport(server))
    assert result["status"] == "FAIL" and result["error"] == code
    assert len(server.requests) == 1
    assert result["remaining_checks"] == "NOT_RUN_AFTER_FAILURE"


@pytest.mark.asyncio
async def test_model_identity_mismatch_and_unsupported_tools_fail_honestly(configured):
    server = Server()
    server.bad_model = True
    result = await qualify(transport_factory=lambda: httpx.MockTransport(server))
    assert result["status"] == "FAIL" and result["error"] == "model_identity_mismatch"
    assert len(server.requests) == 2
    server = Server()
    server.no_tools = True
    result = await qualify(transport_factory=lambda: httpx.MockTransport(server))
    assert (
        result["status"] == "FAIL"
        and result["error"] == "tool_call_capability_unverified"
    )
    assert len(server.requests) == 4


@pytest.mark.asyncio
async def test_optional_models_listing_not_confused_with_model_response_identity(
    configured,
):
    server = Server()
    server.model_list = False
    result = await qualify(transport_factory=lambda: httpx.MockTransport(server))
    assert (
        result["status"] == "PASS"
        and result["checks"]["model_listing"]["status"] == "UNSUPPORTED"
    )
    assert result["model_identity_verified"]


@pytest.mark.asyncio
async def test_missing_credentials_and_disallowed_destination_never_connect(
    configured, monkeypatch
):
    count = []

    def forbidden():
        count.append(1)
        pytest.fail("must not create transport")

    monkeypatch.delenv("OPENAI_COMPATIBLE_API_KEY")
    result = await qualify(transport_factory=forbidden)
    assert result["status"] == "BLOCKED_CREDENTIALS" and not count
    monkeypatch.setenv(
        "OPENAI_COMPATIBLE_API_KEY", "qualification-synthetic-credential"
    )
    monkeypatch.setenv("VM_ALLOWED_HOSTS", "other.example")
    result = await qualify(transport_factory=forbidden)
    assert result["status"] == "BLOCKED_DESTINATION" and not count


@pytest.mark.asyncio
async def test_basic_read_has_total_deadline_and_closes_response(configured):
    server = Server()
    server.long_basic = True
    result = await qualify(
        transport_factory=lambda: httpx.MockTransport(server), timeout_ms=100
    )
    assert result["status"] == "FAIL" and result["error"] == "timeout"
    assert len(server.requests) == 2 and server.slow[0].closed


def test_standalone_cli_blocks_missing_credentials_and_preserves_evidence(tmp_path):
    env = os.environ.copy()
    for name in (
        "OPENAI_COMPATIBLE_URL",
        "OPENAI_COMPATIBLE_MODEL",
        "OPENAI_COMPATIBLE_API_KEY",
    ):
        env.pop(name, None)
    path = tmp_path / "evidence.json"
    cmd = [sys.executable, "scripts/qualify-qwen.py", "--output", str(path)]
    run = subprocess.run(cmd, env=env, text=True, capture_output=True, timeout=10)
    assert (
        run.returncode == 2
        and json.loads(path.read_text())["status"] == "BLOCKED_CREDENTIALS"
    )
    original = path.read_bytes()
    second = subprocess.run(cmd, env=env, text=True, capture_output=True, timeout=10)
    assert second.returncode != 0 and path.read_bytes() == original
    assert "already exists" in second.stderr


def test_complete_qualifier_never_imports_app_database_or_reads_state_directory(
    configured, tmp_path
):
    # A diagnostic run must not depend on or alter the application's working state.
    state = tmp_path / "not-a-directory"
    state.write_text("protected state sentinel")
    env = os.environ.copy()
    env["VM_STATE_DIR"] = str(state)
    env["PYTHONPATH"] = ".:tests"
    code = """
import asyncio,json,sys,socket,httpx
socket.getaddrinfo=lambda *a,**k:[(2,1,6,'',('8.8.8.8',443))]
from test_gate06_qwen_qualification import Server
from vrag.qwen_qualification import qualify
r=asyncio.run(qualify(transport_factory=lambda:httpx.MockTransport(Server())))
assert r['status']=='PASS',r
assert 'vrag.jobs' not in sys.modules
assert 'vrag.mentor_api' not in sys.modules
print(json.dumps({'status':r['status'],'application_state_accessed':False}))
"""
    run = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        text=True,
        capture_output=True,
        timeout=15,
    )
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)["application_state_accessed"] is False
    assert state.read_text() == "protected state sentinel"
