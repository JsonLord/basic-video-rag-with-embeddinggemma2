"""Read-only official-SDK discovery limits with synthetic compressed/uncompressed responses."""

import gzip
import httpx
import pytest
from config.v2 import ProviderV2
from vrag.research import A2AAdapter
from vrag.providers import ProviderFailure


@pytest.mark.asyncio
@pytest.mark.parametrize("compressed", [False, True])
async def test_agent_card_decoded_response_limit_fails_before_sdk_parsing(
    monkeypatch, compressed
):
    monkeypatch.setenv("A2A_URL", "https://agent.example/a2a/t-{token}")
    monkeypatch.setenv("A2A_TOKEN", "synthetic-gate06-agent-credential")
    monkeypatch.setenv("VM_ALLOWED_HOSTS", "agent.example")
    monkeypatch.setattr(
        "socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("8.8.8.8", 443))]
    )
    provider = ProviderV2(
        adapter="a2a",
        model="unqualified-fixture",
        base_url_env="A2A_URL",
        api_key_secret="A2A_TOKEN",
        auth_mode="path_token",
        capabilities=["research_dispatch"],
    )
    requests = []

    def reply(request):
        requests.append(request)
        assert request.method == "GET" and "authorization" not in request.headers
        data = b"x" * (128 * 1024 + 1)
        return httpx.Response(
            200,
            headers={"content-encoding": "gzip"} if compressed else {},
            content=gzip.compress(data) if compressed else data,
        )

    with pytest.raises(ProviderFailure, match="a2a_response_too_large"):
        await A2AAdapter(httpx.MockTransport(reply)).probe(provider)
    assert len(requests) == 1
