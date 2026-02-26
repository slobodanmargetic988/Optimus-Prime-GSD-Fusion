#!/usr/bin/env python3
"""Run deterministic targeted pytest commands and derive tester decision hints."""

from __future__ import annotations

import argparse
import json
import shlex
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TOOL = "tester-targeted-pytest-runner"
BLOCKER_CLASSES = {"none", "db_unreachable", "sandbox_network", "missing_env", "test_failure"}


class ToolError(Exception):
    def __init__(self, code: str, message: str, stage: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.stage = stage


@dataclass
class RunSpec:
    name: str
    cmd: str
    required: bool
    timeout_sec: float | None = None


@dataclass
class DbPrecheck:
    enabled: bool
    host: str
    port: int


@dataclass
class RunnerInput:
    worktree_root: Path
    task_identifier: str
    env_source: Path
    python_bin: Path
    runs: list[RunSpec]
    db_precheck: DbPrecheck
    stop_on_blocked: bool
    dry_run: bool
    timeout_sec: float | None


@dataclass
class RunResult:
    name: str
    required: bool
    result: str
    exit_code: int | None
    duration_ms: int
    summary: str
    snippet: str
    signature: str | None
    blocker_class: str | None
    rerun_cmd: str
    timeout_sec: float | None


class CommandRunner:
    def run(self, cmd: list[str], cwd: Path, env: dict[str, str], timeout: float | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True, check=False, timeout=timeout)


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


def load_json(path: str) -> dict[str, Any]:
    if path == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ToolError("input_error", "Input payload must be a JSON object", stage="input")
    return data


def must_str(data: dict[str, Any], key: str, fallback: Any = None) -> str:
    value = data.get(key, fallback)
    if not isinstance(value, str) or not value.strip():
        raise ToolError("input_error", f"{key} is required and must be a non-empty string", stage="input")
    return value.strip()


def parse_runs(data: dict[str, Any]) -> list[RunSpec]:
    runs_raw = data.get("runs")
    if not isinstance(runs_raw, list) or not runs_raw:
        raise ToolError("input_error", "runs must be a non-empty list", stage="input")

    runs: list[RunSpec] = []
    for idx, item in enumerate(runs_raw):
        if not isinstance(item, dict):
            raise ToolError("input_error", f"runs[{idx}] must be an object", stage="input")
        name = item.get("name")
        cmd = item.get("cmd")
        if not isinstance(name, str) or not name.strip():
            raise ToolError("input_error", f"runs[{idx}].name must be non-empty string", stage="input")
        if not isinstance(cmd, str) or not cmd.strip():
            raise ToolError("input_error", f"runs[{idx}].cmd must be non-empty string", stage="input")
        required = as_bool(item.get("required", True), default=True)
        timeout_raw = item.get("timeout_sec")
        timeout_sec: float | None = None
        if timeout_raw is not None:
            try:
                timeout_sec = float(timeout_raw)
            except (TypeError, ValueError) as exc:
                raise ToolError("input_error", f"runs[{idx}].timeout_sec must be numeric", stage="input") from exc
            if timeout_sec <= 0:
                raise ToolError("input_error", f"runs[{idx}].timeout_sec must be > 0", stage="input")
        runs.append(RunSpec(name=name.strip(), cmd=cmd.strip(), required=required, timeout_sec=timeout_sec))
    return runs


def parse_db_precheck(data: dict[str, Any]) -> DbPrecheck:
    raw = data.get("db_precheck")
    if raw is None:
        return DbPrecheck(enabled=False, host="127.0.0.1", port=5432)
    if not isinstance(raw, dict):
        raise ToolError("input_error", "db_precheck must be an object when provided", stage="input")

    enabled = as_bool(raw.get("enabled", False), default=False)
    host = raw.get("host", "127.0.0.1")
    port = raw.get("port", 5432)

    if not isinstance(host, str) or not host.strip():
        raise ToolError("input_error", "db_precheck.host must be non-empty string", stage="input")
    try:
        port_int = int(port)
    except (TypeError, ValueError) as exc:
        raise ToolError("input_error", "db_precheck.port must be an integer", stage="input") from exc
    if port_int < 1 or port_int > 65535:
        raise ToolError("input_error", "db_precheck.port must be in range 1..65535", stage="input")

    return DbPrecheck(enabled=enabled, host=host.strip(), port=port_int)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic targeted pytest checks")
    parser.add_argument("--input-json", help="JSON payload path or '-' for stdin")
    parser.add_argument("--task-identifier")
    parser.add_argument("--worktree-root")
    parser.add_argument("--env-source")
    parser.add_argument("--python-bin")
    parser.add_argument("--timeout-sec", type=float)
    parser.add_argument("--stop-on-blocked", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json-pretty", action="store_true")
    return parser.parse_args()


def parse_input(args: argparse.Namespace) -> RunnerInput:
    payload: dict[str, Any] = {}
    if args.input_json:
        payload = load_json(args.input_json)

    worktree_root = Path(must_str(payload, "worktree_root", fallback=args.worktree_root or ".")).expanduser().resolve()
    if not worktree_root.exists() or not worktree_root.is_dir():
        raise ToolError("input_error", f"worktree_root does not exist or is not a directory: {worktree_root}", stage="input")

    env_source = Path(must_str(payload, "env_source", fallback=args.env_source)).expanduser()
    if not env_source.is_absolute():
        env_source = (worktree_root / env_source).resolve()

    python_bin = Path(must_str(payload, "python_bin", fallback=args.python_bin)).expanduser()
    if not python_bin.is_absolute():
        python_bin = (worktree_root / python_bin).resolve()

    timeout_raw = payload.get("timeout_sec", args.timeout_sec)
    timeout_sec: float | None = None
    if timeout_raw is not None:
        try:
            timeout_sec = float(timeout_raw)
        except (TypeError, ValueError) as exc:
            raise ToolError("input_error", "timeout_sec must be numeric", stage="input") from exc
        if timeout_sec <= 0:
            raise ToolError("input_error", "timeout_sec must be > 0", stage="input")

    return RunnerInput(
        worktree_root=worktree_root,
        task_identifier=must_str(payload, "task_identifier", fallback=args.task_identifier),
        env_source=env_source,
        python_bin=python_bin,
        runs=parse_runs(payload),
        db_precheck=parse_db_precheck(payload),
        stop_on_blocked=as_bool(payload.get("stop_on_blocked", args.stop_on_blocked), default=False),
        dry_run=as_bool(payload.get("dry_run", args.dry_run), default=False),
        timeout_sec=timeout_sec,
    )


def load_env_file(path: Path) -> dict[str, str]:
    if not path.exists() or not path.is_file():
        raise ToolError("missing_env", f"env_source not found: {path}", stage="preflight")

    env: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip().strip('"').strip("'")
        env[key] = value
    return env


def db_precheck(cfg: DbPrecheck, timeout: float = 1.0) -> tuple[bool, str]:
    if not cfg.enabled:
        return True, "db precheck disabled"
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((cfg.host, cfg.port))
    except OSError as exc:
        return False, str(exc)
    finally:
        sock.close()
    return True, "db reachable"


def build_command(cmd: str, python_bin: Path) -> list[str]:
    tokens = shlex.split(cmd)
    if not tokens:
        raise ToolError("input_error", "run command resolved to empty token list", stage="input")

    first = tokens[0]
    base = Path(first).name

    if first.startswith("-"):
        return [str(python_bin), "-m", "pytest", *tokens]
    if base in {"pytest", "py.test"}:
        return [str(python_bin), "-m", "pytest", *tokens[1:]]
    if base in {"python", "python3"}:
        return [str(python_bin), *tokens[1:]]
    return tokens


def parse_pytest_summary(output: str) -> str:
    lowered = output.lower()
    counts: dict[str, int] = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
    for key in counts.keys():
        marker = f" {key}"
        idx = 0
        while True:
            idx = lowered.find(marker, idx)
            if idx == -1:
                break
            start = idx - 1
            while start >= 0 and lowered[start].isdigit():
                start -= 1
            number = lowered[start + 1 : idx].strip()
            if number.isdigit():
                counts[key] += int(number)
            idx += len(marker)
    return f"passed={counts['passed']} failed={counts['failed']} skipped={counts['skipped']} errors={counts['errors']}"


def truncate_snippet(stdout: str, stderr: str, limit: int = 320) -> str:
    text = (stdout or "").strip()
    err = (stderr or "").strip()
    if err:
        text = f"{text}\n{err}".strip() if text else err
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def classify_failure(snippet: str) -> tuple[str, str, str]:
    text = snippet.lower()
    if any(token in text for token in ["connection refused", "could not connect", "connectionerror", "operationalerror", "database", "postgres"]):
        return "blocked", "db_unreachable", "db_unreachable"
    if any(token in text for token in ["operation not permitted", "temporary failure in name resolution", "network is unreachable", "sandbox"]):
        return "blocked", "sandbox_network", "sandbox_network"
    if any(token in text for token in ["no such file or directory", "modulenotfounderror", "command not found", "not found"]):
        return "blocked", "missing_env", "missing_env"
    if any(token in text for token in ["assert", "failed", "error", "traceback"]):
        return "fail", "test_failure", "test_failure"
    return "fail", "test_failure", "test_failure"


def derive_decision(runs: list[RunResult], precheck_blocker: str | None) -> tuple[str, str]:
    if precheck_blocker is not None:
        return "blocked", precheck_blocker

    run_blockers = [r.blocker_class for r in runs if r.result == "blocked" and r.blocker_class]
    if run_blockers:
        if "db_unreachable" in run_blockers:
            return "blocked", "db_unreachable"
        if "sandbox_network" in run_blockers:
            return "blocked", "sandbox_network"
        return "blocked", "missing_env"

    required_fail = any(r.required and r.result == "fail" for r in runs)
    if required_fail:
        return "needs_dev_fix", "test_failure"

    required_not_pass = any(r.required and r.result != "pass" for r in runs)
    if required_not_pass:
        return "blocked", "test_failure"

    return "ready_for_review", "none"


def execute(cfg: RunnerInput, runner: CommandRunner | None = None) -> dict[str, Any]:
    if runner is None:
        runner = CommandRunner()

    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    host_rerun_commands: list[str] = []

    if cfg.dry_run:
        return {
            "ok": True,
            "tool": TOOL,
            "task_identifier": cfg.task_identifier,
            "decision_hint": "ready_for_review",
            "runs": [
                {
                    "name": run.name,
                    "result": "pass",
                    "exit_code": 0,
                    "duration_ms": 0,
                    "summary": f"DRY-RUN: {run.cmd}",
                    "snippet": f"DRY-RUN: {run.cmd}",
                    "signature": None,
                    "timeout_sec": run.timeout_sec if run.timeout_sec is not None else cfg.timeout_sec,
                }
                for run in cfg.runs
            ],
            "blocker_class": "none",
            "host_rerun_commands": host_rerun_commands,
            "warnings": [{"code": "dry_run", "message": "Dry-run mode enabled; runs were not executed"}],
            "errors": errors,
        }

    try:
        env_values = load_env_file(cfg.env_source)
    except ToolError as exc:
        return {
            "ok": False,
            "tool": TOOL,
            "task_identifier": cfg.task_identifier,
            "decision_hint": "blocked",
            "runs": [],
            "blocker_class": "missing_env",
            "host_rerun_commands": [f"test -f {cfg.env_source}"],
            "warnings": warnings,
            "errors": [{"code": exc.code, "message": exc.message, "stage": exc.stage}],
        }

    if not cfg.python_bin.exists() or not cfg.python_bin.is_file():
        return {
            "ok": False,
            "tool": TOOL,
            "task_identifier": cfg.task_identifier,
            "decision_hint": "blocked",
            "runs": [],
            "blocker_class": "missing_env",
            "host_rerun_commands": [f"ls -l {cfg.python_bin}"],
            "warnings": warnings,
            "errors": [{"code": "missing_env", "message": f"python_bin not found: {cfg.python_bin}", "stage": "preflight"}],
        }

    env = dict(**dict(**__import__("os").environ), **env_values)

    precheck_blocker: str | None = None
    if cfg.db_precheck.enabled:
        db_ok, reason = db_precheck(cfg.db_precheck)
        if not db_ok:
            precheck_blocker = "db_unreachable"
            errors.append(
                {
                    "code": "db_unreachable",
                    "message": f"DB precheck failed for {cfg.db_precheck.host}:{cfg.db_precheck.port} ({reason})",
                    "stage": "precheck",
                }
            )
            host_rerun_commands.append(f"nc -vz {cfg.db_precheck.host} {cfg.db_precheck.port}")
            if cfg.stop_on_blocked:
                return {
                    "ok": False,
                    "tool": TOOL,
                    "task_identifier": cfg.task_identifier,
                    "decision_hint": "blocked",
                    "runs": [],
                    "blocker_class": "db_unreachable",
                    "host_rerun_commands": host_rerun_commands,
                    "warnings": warnings,
                    "errors": errors,
                }

    run_results: list[RunResult] = []

    for spec in cfg.runs:
        try:
            cmd = build_command(spec.cmd, cfg.python_bin)
        except ToolError as exc:
            run_results.append(
                RunResult(
                    name=spec.name,
                    required=spec.required,
                    result="blocked",
                    exit_code=None,
                    duration_ms=0,
                    summary=exc.message,
                    snippet=exc.message,
                    signature="missing_env",
                    blocker_class="missing_env",
                    rerun_cmd=spec.cmd,
                    timeout_sec=spec.timeout_sec if spec.timeout_sec is not None else cfg.timeout_sec,
                )
            )
            if cfg.stop_on_blocked:
                warnings.append({"code": "stop_on_blocked_triggered", "message": f"Stopped at run '{spec.name}'"})
                break
            continue

        start = time.monotonic()
        try:
            effective_timeout = spec.timeout_sec if spec.timeout_sec is not None else cfg.timeout_sec
            proc = runner.run(cmd, cwd=cfg.worktree_root, env=env, timeout=effective_timeout)
        except subprocess.TimeoutExpired:
            duration_ms = int((time.monotonic() - start) * 1000)
            summary = f"timeout after {effective_timeout}s" if effective_timeout else "timeout"
            snippet = summary
            run_results.append(
                RunResult(
                    name=spec.name,
                    required=spec.required,
                    result="blocked",
                    exit_code=None,
                    duration_ms=duration_ms,
                    summary=summary,
                    snippet=snippet,
                    signature="timeout",
                    blocker_class="test_failure",
                    rerun_cmd=shlex.join(cmd),
                    timeout_sec=effective_timeout,
                )
            )
            host_rerun_commands.append(shlex.join(cmd))
            if cfg.stop_on_blocked:
                warnings.append({"code": "stop_on_blocked_triggered", "message": f"Stopped at run '{spec.name}'"})
                break
            continue
        except OSError as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            summary = f"Execution error: {exc}"
            run_results.append(
                RunResult(
                    name=spec.name,
                    required=spec.required,
                    result="blocked",
                    exit_code=None,
                    duration_ms=duration_ms,
                    summary=summary,
                    snippet=summary,
                    signature="missing_env",
                    blocker_class="missing_env",
                    rerun_cmd=shlex.join(cmd),
                    timeout_sec=spec.timeout_sec if spec.timeout_sec is not None else cfg.timeout_sec,
                )
            )
            host_rerun_commands.append(shlex.join(cmd))
            if cfg.stop_on_blocked:
                warnings.append({"code": "stop_on_blocked_triggered", "message": f"Stopped at run '{spec.name}'"})
                break
            continue

        duration_ms = int((time.monotonic() - start) * 1000)
        snippet = truncate_snippet(proc.stdout, proc.stderr)
        summary = parse_pytest_summary(f"{proc.stdout}\n{proc.stderr}")
        rerun_cmd = shlex.join(cmd)

        if proc.returncode == 0:
            result = RunResult(
                name=spec.name,
                required=spec.required,
                result="pass",
                exit_code=0,
                duration_ms=duration_ms,
                summary=summary,
                snippet=snippet,
                signature=None,
                blocker_class=None,
                rerun_cmd=rerun_cmd,
                timeout_sec=spec.timeout_sec if spec.timeout_sec is not None else cfg.timeout_sec,
            )
        else:
            run_result, signature, blocker_class = classify_failure(snippet)
            result = RunResult(
                name=spec.name,
                required=spec.required,
                result=run_result,
                exit_code=int(proc.returncode),
                duration_ms=duration_ms,
                summary=summary,
                snippet=snippet,
                signature=signature,
                blocker_class=blocker_class if run_result == "blocked" else None,
                rerun_cmd=rerun_cmd,
                timeout_sec=spec.timeout_sec if spec.timeout_sec is not None else cfg.timeout_sec,
            )
            if run_result == "blocked":
                host_rerun_commands.append(rerun_cmd)

        run_results.append(result)

        if cfg.stop_on_blocked and result.result == "blocked":
            warnings.append({"code": "stop_on_blocked_triggered", "message": f"Stopped at run '{spec.name}'"})
            break

    decision, blocker_class = derive_decision(run_results, precheck_blocker)
    if blocker_class not in BLOCKER_CLASSES:
        blocker_class = "test_failure"

    return {
        "ok": decision != "blocked",
        "tool": TOOL,
        "task_identifier": cfg.task_identifier,
        "decision_hint": decision,
        "runs": [
            {
                "name": item.name,
                "result": item.result,
                "exit_code": item.exit_code,
                "duration_ms": item.duration_ms,
                "summary": item.summary,
                "snippet": item.snippet,
                "signature": item.signature,
                "timeout_sec": item.timeout_sec,
            }
            for item in run_results
        ],
        "blocker_class": blocker_class,
        "host_rerun_commands": host_rerun_commands,
        "warnings": warnings,
        "errors": errors,
    }


def print_json(payload: dict[str, Any], pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=False))
    else:
        print(json.dumps(payload, separators=(",", ":"), sort_keys=False))


def main() -> int:
    args = parse_args()
    try:
        cfg = parse_input(args)
    except ToolError as exc:
        out = {
            "ok": False,
            "tool": TOOL,
            "task_identifier": args.task_identifier or "",
            "decision_hint": "blocked",
            "runs": [],
            "blocker_class": "missing_env",
            "host_rerun_commands": [],
            "warnings": [],
            "errors": [{"code": exc.code, "message": exc.message, "stage": exc.stage}],
        }
        print_json(out, args.json_pretty)
        return 1
    except json.JSONDecodeError as exc:
        out = {
            "ok": False,
            "tool": TOOL,
            "task_identifier": args.task_identifier or "",
            "decision_hint": "blocked",
            "runs": [],
            "blocker_class": "missing_env",
            "host_rerun_commands": [],
            "warnings": [],
            "errors": [{"code": "input_error", "message": f"Invalid JSON input: {exc}", "stage": "input"}],
        }
        print_json(out, args.json_pretty)
        return 1

    out = execute(cfg)
    print_json(out, args.json_pretty)
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
