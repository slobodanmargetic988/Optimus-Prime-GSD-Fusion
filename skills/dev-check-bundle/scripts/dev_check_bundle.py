#!/usr/bin/env python3
"""Run task-scoped checks and produce a single structured verdict."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TOOL = "dev-check-bundle"
TOOL_VERSION = "0.1.0"
SCHEMA_VERSION = "1.0"

SNIPPET_LIMIT = 400


class ToolError(Exception):
    def __init__(self, code: str, message: str, stage: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.stage = stage


@dataclass
class CheckSpec:
    name: str
    cmd: str
    timeout_sec: float | None = None


@dataclass
class BundleInput:
    task_identifier: str
    checks: list[CheckSpec]
    stop_on_fail: bool
    max_parallel: int
    dry_run: bool
    repo_root: Path
    timeout_sec: float | None


@dataclass
class CheckResult:
    name: str
    result: str
    exit_code: int | None
    duration_ms: int
    snippet: str


class CommandRunner:
    def run(self, cmd: list[str], cwd: Path, timeout: float | None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False, timeout=timeout)


def load_json(path: str) -> dict[str, Any]:
    if path == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ToolError("input_error", "Input payload must be a JSON object", stage="input")
    return data


def as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def parse_input(args: argparse.Namespace) -> BundleInput:
    payload: dict[str, Any] = {}
    if args.input_json:
        payload = load_json(args.input_json)

    task_identifier = payload.get("task_identifier", args.task_identifier)
    if not isinstance(task_identifier, str) or not task_identifier.strip():
        raise ToolError("input_error", "task_identifier is required", stage="input")

    checks_raw = payload.get("checks")
    if not isinstance(checks_raw, list) or not checks_raw:
        raise ToolError("input_error", "checks must be a non-empty list", stage="input")

    checks: list[CheckSpec] = []
    for idx, item in enumerate(checks_raw):
        if not isinstance(item, dict):
            raise ToolError("input_error", f"checks[{idx}] must be an object", stage="input")
        name = item.get("name")
        cmd = item.get("cmd")
        if not isinstance(name, str) or not name.strip():
            raise ToolError("input_error", f"checks[{idx}].name must be a non-empty string", stage="input")
        if not isinstance(cmd, str) or not cmd.strip():
            raise ToolError("input_error", f"checks[{idx}].cmd must be a non-empty string", stage="input")
        timeout_sec = item.get("timeout_sec")
        parsed_timeout: float | None = None
        if timeout_sec is not None:
            try:
                parsed_timeout = float(timeout_sec)
            except (TypeError, ValueError) as exc:
                raise ToolError("input_error", f"checks[{idx}].timeout_sec must be numeric", stage="input") from exc
            if parsed_timeout <= 0:
                raise ToolError("input_error", f"checks[{idx}].timeout_sec must be > 0", stage="input")
        checks.append(CheckSpec(name=name.strip(), cmd=cmd.strip(), timeout_sec=parsed_timeout))

    stop_on_fail = as_bool(payload.get("stop_on_fail", args.stop_on_fail), default=False)

    max_parallel_raw = payload.get("max_parallel", args.max_parallel if args.max_parallel is not None else 1)
    try:
        max_parallel = int(max_parallel_raw)
    except (TypeError, ValueError) as exc:
        raise ToolError("input_error", "max_parallel must be an integer", stage="input") from exc
    if max_parallel < 1:
        raise ToolError("input_error", "max_parallel must be >= 1", stage="input")

    timeout_raw = payload.get("timeout_sec", args.timeout_sec)
    timeout_sec: float | None = None
    if timeout_raw is not None:
        try:
            timeout_sec = float(timeout_raw)
        except (TypeError, ValueError) as exc:
            raise ToolError("input_error", "timeout_sec must be numeric", stage="input") from exc
        if timeout_sec <= 0:
            raise ToolError("input_error", "timeout_sec must be > 0", stage="input")

    repo_root_raw = payload.get("repo_root", args.repo_root or ".")
    if not isinstance(repo_root_raw, str) or not repo_root_raw.strip():
        raise ToolError("input_error", "repo_root must be a non-empty string", stage="input")
    repo_root = Path(repo_root_raw).expanduser().resolve()

    if not repo_root.exists() or not repo_root.is_dir():
        raise ToolError("input_error", f"repo_root does not exist or is not a directory: {repo_root}", stage="input")

    return BundleInput(
        task_identifier=task_identifier.strip(),
        checks=checks,
        stop_on_fail=stop_on_fail,
        max_parallel=max_parallel,
        dry_run=as_bool(payload.get("dry_run", args.dry_run), default=False),
        repo_root=repo_root,
        timeout_sec=timeout_sec,
    )


def classify_failed_check(snippet: str) -> str:
    text = snippet.lower()
    if any(token in text for token in ["command not found", "no such file", "permission denied", "modulenotfounderror", "cannot find module"]):
        return "blocked"
    return "fail"


def derive_overall(results: list[CheckResult]) -> str:
    if any(item.result == "blocked" for item in results):
        return "blocked"
    if any(item.result == "fail" for item in results):
        return "fail"
    return "pass"


def truncate_snippet(stdout: str, stderr: str) -> str:
    text = (stdout or "").strip()
    if stderr.strip():
        if text:
            text = text + "\n" + stderr.strip()
        else:
            text = stderr.strip()
    text = text.strip()
    if len(text) > SNIPPET_LIMIT:
        return text[: SNIPPET_LIMIT - 3] + "..."
    return text


def run_checks(cfg: BundleInput, runner: CommandRunner | None = None) -> dict[str, Any]:
    if runner is None:
        runner = CommandRunner()

    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    if cfg.max_parallel != 1:
        warnings.append(
            {
                "code": "max_parallel_ignored",
                "message": "Current implementation runs checks sequentially for deterministic output; max_parallel is ignored",
            }
        )

    if cfg.dry_run:
        return {
            "ok": True,
            "schema_version": SCHEMA_VERSION,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "task_identifier": cfg.task_identifier,
            "overall": "pass",
            "checks": [
                {
                    "name": chk.name,
                    "result": "pass",
                    "exit_code": 0,
                    "duration_ms": 0,
                    "snippet": f"DRY-RUN: {chk.cmd}",
                }
                for chk in cfg.checks
            ],
            "blockers": [],
            "warnings": warnings + [{"code": "dry_run", "message": "Dry-run mode enabled; checks were not executed"}],
            "errors": [],
        }

    results: list[CheckResult] = []
    blockers: list[str] = []

    for check in cfg.checks:
        start = time.monotonic()
        timeout = check.timeout_sec if check.timeout_sec is not None else cfg.timeout_sec

        try:
            cmd = shlex.split(check.cmd)
        except ValueError as exc:
            raise ToolError("input_error", f"Invalid command for check '{check.name}': {exc}", stage="input") from exc
        if not cmd:
            raise ToolError("input_error", f"Invalid command for check '{check.name}': empty command", stage="input")

        try:
            proc = runner.run(cmd, cwd=cfg.repo_root, timeout=timeout)
            duration_ms = int((time.monotonic() - start) * 1000)
            snippet = truncate_snippet(proc.stdout, proc.stderr)

            if proc.returncode == 0:
                result = CheckResult(check.name, "pass", 0, duration_ms, snippet)
            else:
                verdict = classify_failed_check(snippet)
                result = CheckResult(check.name, verdict, int(proc.returncode), duration_ms, snippet)
                if verdict == "blocked":
                    blockers.append(f"{check.name}: {snippet or 'blocked by environment/dependency issue'}")

            results.append(result)

            if cfg.stop_on_fail and result.result in {"fail", "blocked"}:
                warnings.append(
                    {
                        "code": "stop_on_fail_triggered",
                        "message": f"Stopped after failing check '{check.name}' due to stop_on_fail=true",
                    }
                )
                break

        except OSError as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            missing = getattr(exc, "filename", None)
            if missing:
                snippet = f"Command not found: {missing}"
            else:
                snippet = f"Execution error: {exc}"
            result = CheckResult(check.name, "blocked", None, duration_ms, snippet)
            results.append(result)
            blockers.append(f"{check.name}: {snippet}")
            if cfg.stop_on_fail:
                warnings.append(
                    {
                        "code": "stop_on_fail_triggered",
                        "message": f"Stopped after blocked check '{check.name}' due to stop_on_fail=true",
                    }
                )
                break

        except subprocess.TimeoutExpired:
            duration_ms = int((time.monotonic() - start) * 1000)
            result = CheckResult(check.name, "blocked", None, duration_ms, f"Timeout after {timeout} seconds")
            results.append(result)
            blockers.append(f"{check.name}: timeout after {timeout} seconds")
            if cfg.stop_on_fail:
                warnings.append(
                    {
                        "code": "stop_on_fail_triggered",
                        "message": f"Stopped after timeout in check '{check.name}' due to stop_on_fail=true",
                    }
                )
                break

    overall = derive_overall(results)

    return {
        "ok": overall == "pass",
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "task_identifier": cfg.task_identifier,
        "overall": overall,
        "checks": [
            {
                "name": item.name,
                "result": item.result,
                "exit_code": item.exit_code,
                "duration_ms": item.duration_ms,
                "snippet": item.snippet,
            }
            for item in results
        ],
        "blockers": blockers,
        "warnings": warnings,
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Task-scoped deterministic check bundle runner")
    parser.add_argument("--input-json", help="JSON payload path or '-' for stdin")
    parser.add_argument("--task-identifier")
    parser.add_argument("--repo-root")
    parser.add_argument("--stop-on-fail", action="store_true")
    parser.add_argument("--max-parallel", type=int)
    parser.add_argument("--timeout-sec", type=float)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json-pretty", action="store_true")
    return parser.parse_args()


def print_json(obj: dict[str, Any], pretty: bool) -> None:
    if pretty:
        print(json.dumps(obj, indent=2, sort_keys=False))
    else:
        print(json.dumps(obj, separators=(",", ":"), sort_keys=False))


def main() -> int:
    args = parse_args()
    try:
        cfg = parse_input(args)
        out = run_checks(cfg)
        print_json(out, args.json_pretty)
        return 0 if out.get("ok") else 1
    except ToolError as exc:
        out = {
            "ok": False,
            "schema_version": SCHEMA_VERSION,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "warnings": [],
            "errors": [{"code": exc.code, "message": exc.message, "stage": exc.stage}],
        }
        print_json(out, args.json_pretty)
        return 1
    except json.JSONDecodeError as exc:
        out = {
            "ok": False,
            "schema_version": SCHEMA_VERSION,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "warnings": [],
            "errors": [{"code": "input_error", "message": f"Invalid JSON input: {exc}", "stage": "input"}],
        }
        print_json(out, args.json_pretty)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
