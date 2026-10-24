#!/usr/bin/env python3
"""Scan built browser assets against five server-only environment values; print no values."""

import argparse
import json
import os
from pathlib import Path

NAMES = (
    "OPENAI_COMPATIBLE_API_KEY",
    "A2A_TOKEN",
    "VM_USER_TOKEN",
    "VM_ADMIN_TOKEN",
    "VM_BACKUP_GITHUB_TOKEN",
)


def scan(root):
    keys = {name: os.environ.get(name, "") for name in NAMES}
    evidence = {
        "kind": "compiled_frontend_credential_scan",
        "variables": list(NAMES),
        "missing_variables": [name for name, value in keys.items() if not value],
        "status": "NOT_RUN",
        "files_scanned": 0,
        "bytes_scanned": 0,
        "matches": [],
    }
    if evidence["missing_variables"]:
        evidence["status"] = "BLOCKED_CONFIGURATION"
        return evidence
    if any(len(value) < 12 for value in keys.values()):
        evidence["status"] = "BLOCKED_CONFIGURATION"
        evidence["error"] = "scan_values_must_be_at_least_12_characters"
        return evidence
    if not root.is_dir():
        evidence["status"] = "BLOCKED_ASSETS"
        return evidence
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.stat().st_size > 32 * 1024 * 1024:
            evidence["status"] = "BLOCKED_ASSET_SIZE"
            return evidence
        content = path.read_bytes()
        evidence["files_scanned"] += 1
        evidence["bytes_scanned"] += len(content)
        for name, value in keys.items():
            if value.encode() in content:
                evidence["matches"].append(
                    {"variable": name, "asset": path.relative_to(root).as_posix()}
                )
    evidence["status"] = (
        "FAIL"
        if evidence["matches"]
        else "PASS"
        if evidence["files_scanned"]
        else "BLOCKED_ASSETS"
    )
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, default=Path("web/.next/static"))
    args = parser.parse_args()
    result = scan(args.assets)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
