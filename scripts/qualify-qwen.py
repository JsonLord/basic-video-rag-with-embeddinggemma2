#!/usr/bin/env python3
"""Standalone synthetic Qwen/OpenAI-compatible qualifier; credentials only from secure environment."""

import argparse
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vrag.qwen_qualification import qualify


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="Save sanitized JSON evidence to a new file; never overwrites existing evidence",
    )
    parser.add_argument("--timeout-ms", type=int, default=10000)
    parser.add_argument("--timeout-probe-ms", type=int, default=100)
    parser.add_argument(
        "--backend",
        choices=["unknown", "ollama", "vllm"],
        default="unknown",
        help="Operator-declared server implementation, not proof of identity",
    )
    args = parser.parse_args()
    if args.output and args.output.exists():
        parser.error("evidence output already exists; choose a new filename")
    result = await qualify(
        timeout_ms=args.timeout_ms,
        timeout_probe_ms=args.timeout_probe_ms,
        backend=args.backend,
    )
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as f:
            f.write(encoded)
    print(encoded, end="")
    return (
        0
        if result["status"] == "PASS"
        else 2
        if result["status"].startswith("BLOCKED")
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
