#!/usr/bin/env python3
"""Read-only, metadata-only Agent Card qualification. Does not submit research."""

import asyncio
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config.v2 import ProviderV2
from vrag.research import adapter
from vrag.providers import ProviderFailure


async def main():
    raw = os.environ.get("A2A_URL", "")
    record = {
        "kind": "live_external_agent_card",
        "task_submitted": False,
        "host": urlsplit(raw).hostname,
        "credential_present": bool(os.environ.get("A2A_TOKEN")),
    }
    if not raw or not record["credential_present"]:
        print(
            json.dumps(
                record | {"status": "blocked", "error": "secure_environment_missing"}
            )
        )
        return 2
    provider = ProviderV2(
        adapter="a2a",
        model="agent-card-unqualified",
        base_url_env="A2A_URL",
        api_key_secret="A2A_TOKEN",
        auth_mode="path_token" if "/a2a/t-{token}" in raw else "bearer",
        trust="public_only",
        capabilities=["research_dispatch"],
    )
    try:
        info = await adapter.probe(provider)
        print(
            json.dumps(
                record
                | {
                    "status": "passed",
                    "agent_card": info,
                    "research_lifecycle": "not_tested",
                }
            )
        )
        return 0
    except ProviderFailure as exc:
        print(json.dumps(record | {"status": "blocked", "error": exc.code}))
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
