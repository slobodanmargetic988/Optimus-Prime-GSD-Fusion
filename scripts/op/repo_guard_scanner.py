#!/usr/bin/env python3
"""Shared repo guard scanner for OP merge/evidence checks."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

TOOL = "repo-guard-scanner"
TOOL_VERSION = "1.0.0"


class ScannerError(Exception):
    def __init__(self, code: str, message: str, *, stage: str = "runtime") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.stage = stage


def _run(args: list[str], *, cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def _parse_input(path: str) -> dict[str, Any]:
    raw = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ScannerError("input_error", "input must be a JSON object", stage="input")
    return payload


def _as_str(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


def _required_str(payload: dict[str, Any], key: str) -> str:
    text = _as_str(payload.get(key))
    if not text:
        raise ScannerError("input_error", f"{key} is required", stage="input")
    return text


def _merge_source_report_artifacts(repo_root: Path, source_branch: str) -> dict[str, Any]:
    code, out, err = _run(["git", "ls-tree", "-r", "--name-only", source_branch], cwd=repo_root)
    message = (_as_str(err) or _as_str(out)).strip()
    if code != 0:
        lowered = message.lower()
        if "not a valid object name" in lowered or "unknown revision" in lowered:
            return {
                "ok": True,
                "mode": "merge_source_report_artifacts",
                "forbidden_paths": [],
                "inspect_error": None,
            }
        return {
            "ok": False,
            "mode": "merge_source_report_artifacts",
            "forbidden_paths": [],
            "inspect_error": message or "unable to inspect source branch tree",
            "reason_code": "merge_source_scan_failed",
        }

    forbidden = [
        line.strip()
        for line in (_as_str(out) or "").splitlines()
        if line.strip().startswith("reports/optimus-prime/")
    ]
    return {
        "ok": True,
        "mode": "merge_source_report_artifacts",
        "forbidden_paths": forbidden,
        "inspect_error": None,
    }


def _dispatch_commit_link(repo_root: Path, branch_name: str, start_from_commit: str) -> dict[str, Any]:
    head_code, head_out, head_err = _run(["git", "rev-parse", branch_name], cwd=repo_root)
    if head_code != 0:
        return {
            "ok": False,
            "mode": "dispatch_commit_link",
            "head_commit": None,
            "advanced": False,
            "changed_paths": [],
            "forbidden_paths": [],
            "reason_code": "dispatch_commit_link_inspection_failed",
            "inspect_error": (_as_str(head_err) or _as_str(head_out) or "unable to resolve branch").strip(),
        }

    head_commit = _as_str(head_out)
    if not head_commit:
        return {
            "ok": False,
            "mode": "dispatch_commit_link",
            "head_commit": None,
            "advanced": False,
            "changed_paths": [],
            "forbidden_paths": [],
            "reason_code": "dispatch_commit_link_inspection_failed",
            "inspect_error": "unable to resolve branch head commit",
        }

    if head_commit == start_from_commit:
        return {
            "ok": False,
            "mode": "dispatch_commit_link",
            "head_commit": head_commit,
            "advanced": False,
            "changed_paths": [],
            "forbidden_paths": [],
            "reason_code": "dispatch_commit_link_missing",
            "inspect_error": None,
        }

    diff_code, diff_out, diff_err = _run(
        ["git", "diff", "--name-only", f"{start_from_commit}..{head_commit}"],
        cwd=repo_root,
    )
    if diff_code != 0:
        return {
            "ok": False,
            "mode": "dispatch_commit_link",
            "head_commit": head_commit,
            "advanced": True,
            "changed_paths": [],
            "forbidden_paths": [],
            "reason_code": "dispatch_commit_link_inspection_failed",
            "inspect_error": (_as_str(diff_err) or _as_str(diff_out) or "unable to diff commit range").strip(),
        }

    changed_paths = [line.strip() for line in (_as_str(diff_out) or "").splitlines() if line.strip()]
    forbidden_paths = [path for path in changed_paths if path.startswith("reports/optimus-prime/")]
    allowed_paths = [path for path in changed_paths if not path.startswith("reports/optimus-prime/")]

    if not changed_paths:
        return {
            "ok": False,
            "mode": "dispatch_commit_link",
            "head_commit": head_commit,
            "advanced": True,
            "changed_paths": [],
            "forbidden_paths": [],
            "reason_code": "dispatch_commit_link_missing",
            "inspect_error": None,
        }

    if forbidden_paths:
        return {
            "ok": False,
            "mode": "dispatch_commit_link",
            "head_commit": head_commit,
            "advanced": True,
            "changed_paths": changed_paths,
            "forbidden_paths": forbidden_paths,
            "reason_code": "forbidden_op_artifact_commit",
            "inspect_error": None,
        }

    if not allowed_paths:
        return {
            "ok": False,
            "mode": "dispatch_commit_link",
            "head_commit": head_commit,
            "advanced": True,
            "changed_paths": changed_paths,
            "forbidden_paths": forbidden_paths,
            "reason_code": "dispatch_commit_link_missing",
            "inspect_error": None,
        }

    return {
        "ok": True,
        "mode": "dispatch_commit_link",
        "head_commit": head_commit,
        "advanced": True,
        "changed_paths": changed_paths,
        "forbidden_paths": [],
        "reason_code": None,
        "inspect_error": None,
    }


def run(payload: dict[str, Any]) -> dict[str, Any]:
    mode = _required_str(payload, "mode")
    repo_root = Path(_required_str(payload, "repo_root")).expanduser().resolve()

    if mode == "merge_source_report_artifacts":
        source_branch = _required_str(payload, "source_branch")
        return _merge_source_report_artifacts(repo_root, source_branch)

    if mode == "dispatch_commit_link":
        branch_name = _required_str(payload, "branch_name")
        start_from_commit = _required_str(payload, "start_from_commit")
        return _dispatch_commit_link(repo_root, branch_name, start_from_commit)

    raise ScannerError("input_error", f"unsupported mode: {mode}", stage="input")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OP repo guard scanner")
    parser.add_argument("--input-json", required=True, help="JSON payload path or '-' for stdin")
    parser.add_argument("--json-pretty", action="store_true")
    return parser.parse_args()


def _print(obj: dict[str, Any], pretty: bool) -> None:
    if pretty:
        print(json.dumps(obj, indent=2, sort_keys=False))
    else:
        print(json.dumps(obj, separators=(",", ":"), sort_keys=False))


def main() -> int:
    args = parse_args()
    try:
        payload = _parse_input(args.input_json)
        out = run(payload)
        out.setdefault("tool", TOOL)
        out.setdefault("tool_version", TOOL_VERSION)
        _print(out, args.json_pretty)
        return 0 if out.get("ok") else 1
    except ScannerError as exc:
        out = {
            "ok": False,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "reason_code": exc.code,
            "error": {"code": exc.code, "message": exc.message, "stage": exc.stage},
        }
        _print(out, args.json_pretty)
        return 1
    except json.JSONDecodeError as exc:
        out = {
            "ok": False,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "reason_code": "input_error",
            "error": {"code": "input_error", "message": f"Invalid JSON input: {exc}", "stage": "input"},
        }
        _print(out, args.json_pretty)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
