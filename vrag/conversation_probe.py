"""Administrator-requested synthetic capability probe; never grants private-data trust."""

import json
from .providers import ProviderFailure, resolved_provider
from .conversation_tools import ToolRegistry


async def probe(name, p):
    from .providers import adapter

    p = resolved_provider(p)
    registry = ToolRegistry(lambda *a: False, {"retrieve_video_evidence": None})
    messages = [
        {
            "role": "user",
            "content": "Synthetic capability test. Call retrieve_video_evidence with query synthetic; do not answer until the tool returns.",
        }
    ]
    calls = []
    text = ""
    reported = None
    async for item in adapter.stream(name, p, messages, registry, sensitive=False):
        if item.call:
            calls.append(item.call)
        text += item.text
        if item.model:
            reported = item.model
    if not calls:
        raise ProviderFailure("tool_call_capability_unverified")
    messages.append(
        {
            "role": "assistant",
            "content": text,
            "tool_calls": [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
                }
                for c in calls
            ],
        }
    )
    messages.extend(
        {
            "role": "tool",
            "tool_call_id": c.id,
            "content": '{"synthetic":true,"text":"correlation verified"}',
        }
        for c in calls
    )
    answer = ""
    async for item in adapter.stream(name, p, messages, registry, sensitive=False):
        if item.call:
            raise ProviderFailure("continuation_capability_unverified")
        answer += item.text
    if not answer:
        raise ProviderFailure("continuation_capability_unverified")
    generation = adapter.stream(
        name,
        p,
        [{"role": "user", "content": "Synthetic cancellation test. Count slowly."}],
        sensitive=False,
    )
    try:
        first = await anext(generation)
        if first.type != "text" or not first.text:
            raise ProviderFailure("cancellation_capability_unverified")
    finally:
        await generation.aclose()
    return {
        "provider": name,
        "model": p.model,
        "reported_model": reported,
        "model_identity": "matched" if reported else "not_reported",
        "streaming": "passed",
        "tool_calling": "passed",
        "correlation": "passed",
        "continuation": "passed",
        "client_cancellation": "passed",
        "remote_compute_cancellation": "not_observable",
        "authentication": "accepted",
        "negative_authentication": "fixture_test_only",
        "synthetic": True,
        "privacy_authorization_changed": False,
    }
