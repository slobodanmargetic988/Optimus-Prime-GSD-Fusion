#!/usr/bin/env python3
"""CLI entrypoint for OP command surface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from op_core import OpError, run_from_payload
from op_router import normalize_command


def _parse_json_input(path: str) -> dict[str, Any]:
    raw = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise OpError("input_error", "input payload must be a JSON object", stage="input")
    return payload


def _print_json(payload: dict[str, Any], pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=False))
    else:
        print(json.dumps(payload, separators=(",", ":"), sort_keys=False))


def _emit_build_start_banner(payload: dict[str, Any]) -> None:
    command_raw = str(payload.get("command") or "").strip()
    try:
        normalized = normalize_command(command_raw)
    except ValueError:
        return
    if str(getattr(normalized, "canonical", "")) != "op-build":
        return
    if not sys.stdout.isatty():
        return
    repo_root = str(payload.get("repo_root") or Path.cwd().resolve())
    print(f"[opctl] /op-build started for {repo_root}.", flush=True)
    print(
        f"[opctl] While waiting, run: opctl /op-report --repo-root {repo_root} --json-pretty",
        flush=True,
    )
    print(
        f"[opctl] Detailed state: opctl /op-status --repo-root {repo_root} --json-pretty",
        flush=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OP command surface (map/new-project/plan/initialize/build/health/status/report/resume)")
    parser.add_argument("--input-json", help="JSON payload path or '-' for stdin")
    parser.add_argument("--command")
    parser.add_argument("--repo-root")
    parser.add_argument("--mission")
    parser.add_argument("--scope")
    parser.add_argument("--constraint", action="append")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--output-mode", choices=["json", "json+text"], default=None)
    parser.add_argument("--max-build-cycles", type=int)
    parser.add_argument("--sleep-minutes", type=float)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json-pretty", action="store_true")
    return parser.parse_args()


def merge_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if args.input_json:
        payload = _parse_json_input(args.input_json)

    if args.command is not None:
        payload["command"] = args.command
    if args.repo_root is not None:
        payload["repo_root"] = args.repo_root
    if args.mission is not None:
        payload["mission"] = args.mission
    if args.scope is not None:
        payload["scope"] = args.scope
    if args.constraint is not None:
        payload["constraints"] = args.constraint
    if args.non_interactive:
        payload["non_interactive"] = True
    if args.output_mode is not None:
        payload["output_mode"] = args.output_mode
    if args.max_build_cycles is not None:
        payload["max_build_cycles"] = args.max_build_cycles
    if args.sleep_minutes is not None:
        payload["sleep_minutes"] = args.sleep_minutes
    if args.dry_run:
        payload["dry_run"] = True

    payload.setdefault("repo_root", str(Path.cwd().resolve()))
    payload.setdefault("non_interactive", True)
    payload.setdefault("output_mode", "json")
    return payload


def main() -> int:
    args = parse_args()
    try:
        payload = merge_payload(args)
        _emit_build_start_banner(payload)
        result = run_from_payload(payload)
        _print_json(result, args.json_pretty)
        return 0 if result.get("ok") else 1
    except OpError as exc:
        out = {
            "schema_version": "1.0",
            "tool": "opctl",
            "tool_version": "0.1.0",
            "ok": False,
            "command": payload.get("command") if "payload" in locals() else args.command,
            "status": "failed",
            "summary": "Command failed.",
            "errors": [{"code": exc.code, "message": exc.message, "stage": exc.stage}],
            "warnings": [],
            "artifacts": [],
            "next_action": None,
            "state_ref": None,
        }
        _print_json(out, args.json_pretty)
        return 1
    except json.JSONDecodeError as exc:
        out = {
            "schema_version": "1.0",
            "tool": "opctl",
            "tool_version": "0.1.0",
            "ok": False,
            "status": "failed",
            "summary": "Invalid JSON input.",
            "errors": [{"code": "input_error", "message": f"invalid JSON: {exc}", "stage": "input"}],
            "warnings": [],
            "artifacts": [],
            "next_action": None,
            "state_ref": None,
        }
        _print_json(out, args.json_pretty)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
