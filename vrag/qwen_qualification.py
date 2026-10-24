"""Bounded synthetic OpenAI-compatible diagnostics. No app startup or tool side effects."""

import asyncio
import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit
import httpx
from config.v2 import ProviderV2
from .providers import Adapter, ProviderFailure, destination
from .egress import transport_for
from .conversation_tools import ToolRegistry

NAME = "qualification-only"


class ObservedStream(httpx.AsyncByteStream):
    def __init__(self, stream, record):
        self.stream = stream
        self.record = record

    async def __aiter__(self):
        async for chunk in self.stream:
            yield chunk

    async def aclose(self):
        try:
            await self.stream.aclose()
        finally:
            self.record["response_closed"] = True


class ObservedTransport(httpx.AsyncBaseTransport):
    def __init__(self, inner, base, records, phase, key):
        self.inner = inner
        self.base = base
        self.records = records
        self.phase = phase
        self.key = key

    async def handle_async_request(self, request):
        if str(request.url) not in {
            self.base + "/models",
            self.base + "/chat/completions",
        }:
            raise ProviderFailure("destination_denied")
        response = await self.inner.handle_async_request(request)
        row = {
            "phase": self.phase,
            "host": request.url.host,
            "status": response.status_code,
            "response_closed": False,
        }
        for header in ("x-request-id", "x-amzn-requestid", "request-id"):
            value = response.headers.get(header, "")
            if re.fullmatch(r"[a-zA-Z0-9_.:=-]{1,128}", value) and (
                not self.key or self.key not in value
            ):
                row[header] = value
        server = response.headers.get("server", "").lower()
        row["backend_header_hint"] = (
            "ollama"
            if "ollama" in server
            else "vllm"
            if "vllm" in server
            else "unknown"
        )
        self.records.append(row)
        return httpx.Response(
            response.status_code,
            headers=response.headers,
            stream=ObservedStream(response.stream, row),
            extensions=response.extensions,
            request=request,
        )

    async def aclose(self):
        await self.inner.aclose()


async def read_json(client, method, url, **kwargs):
    async with client.stream(method, url, **kwargs) as response:
        if response.status_code in (401, 403):
            raise ProviderFailure("provider_auth_denied")
        if 300 <= response.status_code < 400:
            raise ProviderFailure("destination_denied")
        if response.status_code in (404, 405) and method == "GET":
            return None
        if not 200 <= response.status_code < 300:
            raise ProviderFailure("provider_error")
        buffer = bytearray()
        async for part in response.aiter_bytes():
            buffer.extend(part)
            if len(buffer) > 1048576:
                raise ProviderFailure("invalid_output")
        try:
            return json.loads(buffer)
        except ValueError:
            raise ProviderFailure("invalid_output") from None


async def qualify(
    *,
    transport_factory=None,
    timeout_ms=10000,
    timeout_probe_ms=100,
    backend="unknown",
):
    """Return evidence only. Never save prompts/responses, endpoints or credentials.

    The CLI reads the inherited secure process environment only. Fixture tests
    monkeypatch that environment and inject a protocol transport, never real keys.
    """
    env = os.environ
    run_started = time.perf_counter()
    required = (
        "OPENAI_COMPATIBLE_URL",
        "OPENAI_COMPATIBLE_MODEL",
        "OPENAI_COMPATIBLE_API_KEY",
    )
    record = {
        "kind": "live_external_openai_qualification"
        if transport_factory is None
        else "mock_external_openai_qualification",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "NOT_RUN",
        "configuration_present": {n: bool(env.get(n)) for n in required},
        "checks": {},
        "http": [],
        "backend_declared": backend,
        "backend_identity_verified": False,
        "tool_side_effects": False,
        "private_media_sent": False,
        "remote_compute_cancellation": "NOT_OBSERVABLE",
        "server_authentication_enforcement": "NOT_TESTED",
    }

    def finish():
        record["total_elapsed_ms"] = round(
            (time.perf_counter() - run_started) * 1000, 2
        )
        return record

    if not all(record["configuration_present"].values()):
        record["status"] = "BLOCKED_CREDENTIALS"
        return finish()
    model = env.get("OPENAI_COMPATIBLE_MODEL", "")
    key = env.get("OPENAI_COMPATIBLE_API_KEY", "")
    if not 1 <= len(model) <= 200 or any(ord(c) < 32 for c in model) or key in model:
        record["status"] = "BLOCKED_CONFIGURATION"
        record["error"] = "model_identifier_invalid"
        return finish()
    if not 100 <= timeout_ms <= 60000 or not 100 <= timeout_probe_ms <= min(
        timeout_ms, 1000
    ):
        record["status"] = "BLOCKED_CONFIGURATION"
        record["error"] = "timeout_configuration_invalid"
        return finish()
    p = ProviderV2(
        adapter="openai-conversation",
        model=model,
        base_url_env="OPENAI_COMPATIBLE_URL",
        api_key_secret="OPENAI_COMPATIBLE_API_KEY",
        capabilities=["conversation"],
        trust="public_only",
        timeout_ms=timeout_ms,
        concurrency=1,
    )
    try:
        base = await destination(p, False)
        if not base.endswith("/v1"):
            base += "/v1"
        record["host"] = urlsplit(base).hostname
        record["model"] = model
    except ProviderFailure as exc:
        record["status"] = "BLOCKED_DESTINATION"
        record["error"] = exc.code
        return finish()

    def transport(phase):
        return ObservedTransport(
            transport_factory() if transport_factory else transport_for(base),
            base,
            record["http"],
            phase,
            key,
        )

    headers = {"Authorization": "Bearer " + key}
    checks = record["checks"]
    phase = "model_listing"
    try:
        started = time.perf_counter()
        async with (
            asyncio.timeout(timeout_ms / 1000),
            httpx.AsyncClient(
                transport=transport(phase),
                headers=headers,
                timeout=timeout_ms / 1000,
                follow_redirects=False,
            ) as client,
        ):
            listing = await read_json(client, "GET", base + "/models")
        if listing is None:
            checks[phase] = {
                "status": "UNSUPPORTED",
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        else:
            if not isinstance(listing, dict) or not isinstance(
                listing.get("data"), list
            ):
                raise ProviderFailure("invalid_model_listing")
            matched = any(
                isinstance(item, dict) and item.get("id") == model
                for item in listing["data"]
            )
            checks[phase] = {
                "status": "PASS" if matched else "FAIL",
                "configured_model_listed": matched,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }
            if not matched:
                raise ProviderFailure("configured_model_not_listed")
        phase = "basic_conversation"
        started = time.perf_counter()
        async with (
            asyncio.timeout(timeout_ms / 1000),
            httpx.AsyncClient(
                transport=transport(phase),
                headers=headers,
                timeout=timeout_ms / 1000,
                follow_redirects=False,
            ) as client,
        ):
            response = await read_json(
                client,
                "POST",
                base + "/chat/completions",
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": "Synthetic integration qualification. Reply with a short greeting. No tools or research.",
                        }
                    ],
                    "stream": False,
                    "max_tokens": 64,
                },
            )
        if not isinstance(response, dict):
            raise ProviderFailure("invalid_output")
        choices = response.get("choices", [])
        if not isinstance(choices, list) or len(choices) != 1:
            raise ProviderFailure("invalid_output")
        content = choices[0].get("message", {}).get("content")
        if not isinstance(content, str) or not content or len(content) > 16000:
            raise ProviderFailure("invalid_output")
        reported = response.get("model")
        if reported is not None and reported != model:
            raise ProviderFailure("model_identity_mismatch")
        checks[phase] = {
            "status": "PASS",
            "reported_model_matches": reported == model,
            "response_characters": len(content),
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
        phase = "streaming"
        started = time.perf_counter()
        first = None
        characters = 0
        stream_model = None
        a = Adapter(transport(phase))
        async for event in a.stream(
            NAME,
            p,
            [
                {
                    "role": "user",
                    "content": "Synthetic streaming qualification. Explain in two short sentences why evidence should have citations.",
                }
            ],
            sensitive=False,
        ):
            if event.text:
                if first is None:
                    first = time.perf_counter()
                characters += len(event.text)
            if event.model:
                stream_model = event.model
        if not characters:
            raise ProviderFailure("streaming_text_missing")
        checks[phase] = {
            "status": "PASS",
            "reported_model_matches": stream_model == model,
            "response_characters": characters,
            "time_to_first_token_ms": round((first - started) * 1000, 2),
            "total_latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
        phase = "tool_call_emission"
        started = time.perf_counter()
        calls = []
        assistant = ""
        registry = ToolRegistry(
            lambda *a: False, {"retrieve_video_evidence": None}, connect=lambda: None
        )
        messages = [
            {
                "role": "user",
                "content": "Synthetic tool-protocol qualification only. Call retrieve_video_evidence with query synthetic. Do not perform research. Wait for the tool result before answering.",
            }
        ]
        async for event in Adapter(transport(phase)).stream(
            NAME, p, messages, registry, sensitive=False
        ):
            assistant += event.text
            if event.call:
                calls.append(event.call)
        if not calls:
            raise ProviderFailure("tool_call_capability_unverified")
        checks[phase] = {
            "status": "PASS",
            "validated_calls": len(calls),
            "tools_executed": 0,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
        messages.append(
            {
                "role": "assistant",
                "content": assistant,
                "tool_calls": [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {
                            "name": c.name,
                            "arguments": json.dumps(c.arguments),
                        },
                    }
                    for c in calls
                ],
            }
        )
        messages.extend(
            {
                "role": "tool",
                "tool_call_id": c.id,
                "content": '{"synthetic":true,"result":"Qualification fixture result: no actual video evidence was retrieved."}',
            }
            for c in calls
        )
        phase = "correlated_continuation"
        started = time.perf_counter()
        characters = 0
        async for event in Adapter(transport(phase)).stream(
            NAME, p, messages, registry, sensitive=False
        ):
            if event.call:
                raise ProviderFailure("continuation_capability_unverified")
            characters += len(event.text)
        if not characters:
            raise ProviderFailure("continuation_capability_unverified")
        checks[phase] = {
            "status": "PASS",
            "correlated_results": len(calls),
            "response_characters": characters,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
        phase = "client_cancellation"
        started = time.perf_counter()
        a = Adapter(transport(phase))
        generation = a.stream(
            NAME,
            p,
            [
                {
                    "role": "user",
                    "content": "Synthetic cancellation qualification. Count from one to one hundred, one item per line.",
                }
            ],
            sensitive=False,
        )
        try:
            first_event = await anext(generation)
            if first_event.type != "text" or not first_event.text:
                raise ProviderFailure("cancellation_capability_unverified")
        finally:
            await generation.aclose()
        closed = all(
            r["response_closed"] for r in record["http"] if r["phase"] == phase
        )
        if not closed or a.limits[(NAME, 1)].locked():
            raise ProviderFailure("client_cancellation_failed")
        checks[phase] = {
            "status": "PASS",
            "response_closed": closed,
            "provider_slot_released": True,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
        phase = "timeout_behavior"
        started = time.perf_counter()
        short = p.model_copy(update={"timeout_ms": timeout_probe_ms})
        try:
            async for _ in Adapter(transport(phase)).stream(
                NAME,
                short,
                [
                    {
                        "role": "user",
                        "content": "Synthetic deadline qualification. Count from one to two hundred, one item per line.",
                    }
                ],
                sensitive=False,
            ):
                pass
            checks[phase] = {
                "status": "NOT_OBSERVED_COMPLETED_WITHIN_DEADLINE",
                "deadline_ms": timeout_probe_ms,
            }
        except ProviderFailure as exc:
            if exc.code != "timeout":
                raise
            checks[phase] = {
                "status": "PASS",
                "deadline_ms": timeout_probe_ms,
                "observed": "client_timeout",
                "remote_timeout": "NOT_ASSERTED",
            }
        checks[phase]["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
        model_verified = (
            checks["basic_conversation"]["reported_model_matches"]
            and checks["streaming"]["reported_model_matches"]
        )
        record["model_identity_verified"] = model_verified
        record["status"] = (
            "PASS"
            if model_verified and checks[phase]["status"] == "PASS"
            else "PARTIAL"
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        code = (
            exc.code
            if isinstance(exc, ProviderFailure)
            else "timeout"
            if isinstance(exc, (TimeoutError, httpx.TimeoutException))
            else "provider_transport_error"
            if isinstance(exc, httpx.HTTPError)
            else "qualification_invalid_response"
        )
        checks[phase] = {"status": "FAIL", "error": code}
        record["status"] = "FAIL"
        record["error"] = code
        record["remaining_checks"] = "NOT_RUN_AFTER_FAILURE"
    return finish()
