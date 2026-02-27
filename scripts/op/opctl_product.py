#!/usr/bin/env python3
"""Lane C product CLI wrapper for OP workflow + lifecycle commands."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SCRIPTS_ROOT.parent
for candidate in (REPO_ROOT, SCRIPTS_ROOT, SCRIPT_DIR):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from op_router import normalize_command
from scripts.install.common import SCHEMA_VERSION, parse_git_commit
from scripts.install.op_doctor import run_doctor
from scripts.install.op_uninstall import run_uninstall
from scripts.install.op_update import run_update


def _print(payload: dict[str, Any], pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=False))
    else:
        print(json.dumps(payload, separators=(",", ":"), sort_keys=False))


def _resolve_version() -> str:
    path = REPO_ROOT / "VERSION"
    if not path.exists():
        return "0.0.0"
    return path.read_text(encoding="utf-8").strip() or "0.0.0"


def _delegate_op_command(args: list[str]) -> int:
    opctl_py = SCRIPT_DIR / "opctl.py"
    run = subprocess.run(
        ["python3", str(opctl_py), "--command", args[0], *args[1:]],
        cwd=str(Path.cwd()),
        text=True,
        capture_output=False,
        check=False,
    )
    return run.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Optimus Prime product CLI (workflow + install lifecycle).",
        usage=(
            "opctl <command> [args]\n\n"
            "Workflow commands: /op-map-codebase /op-new-project /op-plan /op-initialize /op-build /op-health /op-status /op-resume\n"
            "Lifecycle commands: doctor update uninstall version"
        ),
    )
    parser.add_argument("command")
    parser.add_argument("extra", nargs=argparse.REMAINDER)
    parser.add_argument("--json-pretty", action="store_true")
    return parser.parse_args()


def _payload_from_extra(extra: list[str]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    idx = 0
    while idx < len(extra):
        token = extra[idx]
        if token.startswith("--"):
            key = token[2:].replace("-", "_")
            if idx + 1 < len(extra) and not extra[idx + 1].startswith("--"):
                payload[key] = extra[idx + 1]
                idx += 2
                continue
            payload[key] = True
        idx += 1
    return payload


def main() -> int:
    args = parse_args()
    command = args.command.strip()
    # Route /op-* commands directly to existing opctl contract.
    try:
        normalize_command(command)
        return _delegate_op_command([command, *args.extra])
    except ValueError:
        pass

    payload = _payload_from_extra(args.extra)
    pretty = bool(args.json_pretty or payload.pop("json_pretty", False))

    if command == "doctor":
        out = run_doctor(payload)
        _print(out, pretty)
        return 0 if out.get("ok") else 1
    if command == "update":
        out = run_update(payload)
        _print(out, pretty)
        return 0 if out.get("ok") else 1
    if command == "uninstall":
        out = run_uninstall(payload)
        _print(out, pretty)
        return 0 if out.get("ok") else 1
    if command == "version":
        out = {
            "schema_version": SCHEMA_VERSION,
            "ok": True,
            "status": "completed",
            "summary": "Version resolved.",
            "data": {
                "version": _resolve_version(),
                "build": SCHEMA_VERSION,
                "commit": parse_git_commit(REPO_ROOT),
            },
        }
        _print(out, pretty)
        return 0

    out = {
        "schema_version": SCHEMA_VERSION,
        "ok": False,
        "status": "failed",
        "summary": "Unsupported command.",
        "errors": [
            {
                "code": "input_error",
                "message": "unsupported command; expected /op-* workflow command or doctor|update|uninstall|version",
                "stage": "input",
            }
        ],
        "warnings": [],
        "next_action": "Run `opctl --help` to inspect supported commands.",
    }
    _print(out, pretty)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
