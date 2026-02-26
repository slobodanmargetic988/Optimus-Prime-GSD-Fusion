#!/usr/bin/env python3
"""Deterministic benchmark wrapper with retry policy and structured artifact output."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

TOOL = "dev-benchmark-runner"
TOOL_VERSION = "0.1.0"
SCHEMA_VERSION = "1.0"


class ToolError(Exception):
    def __init__(self, code: str, message: str, stage: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.stage = stage


@dataclass
class RunnerInput:
    script: Path
    dataset_size: int
    iterations: int
    warmup: int
    max_retries: int
    artifact_path: Path
    dry_run: bool
    repo_root: Path


@dataclass
class CmdResult:
    returncode: int
    stdout: str
    stderr: str


class CommandRunner:
    def run(self, cmd: list[str], cwd: Path) -> CmdResult:
        proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
        return CmdResult(returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_input(path: str) -> dict[str, Any]:
    if path == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ToolError("input_error", "Input payload must be a JSON object", stage="input")
    return data


def parse_input(args: argparse.Namespace) -> RunnerInput:
    payload: dict[str, Any] = {}
    if args.input_json:
        payload = load_input(args.input_json)

    def required_str(key: str, fallback: Any = None) -> str:
        v = payload.get(key, fallback)
        if not isinstance(v, str) or not v.strip():
            raise ToolError("input_error", f"{key} is required and must be a non-empty string", stage="input")
        return v.strip()

    def int_field(key: str, fallback: Any = None, minimum: int = 0) -> int:
        v = payload.get(key, fallback)
        if v is None:
            raise ToolError("input_error", f"{key} is required", stage="input")
        try:
            iv = int(v)
        except (TypeError, ValueError) as exc:
            raise ToolError("input_error", f"{key} must be an integer", stage="input") from exc
        if iv < minimum:
            raise ToolError("input_error", f"{key} must be >= {minimum}", stage="input")
        return iv

    repo_root_raw = payload.get("repo_root", args.repo_root or ".")
    if not isinstance(repo_root_raw, str) or not repo_root_raw.strip():
        raise ToolError("input_error", "repo_root must be a non-empty string", stage="input")
    repo_root = Path(repo_root_raw).expanduser().resolve()

    script_raw = required_str("script", fallback=args.script)
    script = Path(script_raw).expanduser()
    if not script.is_absolute():
        script = (repo_root / script).resolve()

    artifact_raw = required_str("artifact_path", fallback=args.artifact_path)
    artifact = Path(artifact_raw).expanduser()
    if not artifact.is_absolute():
        artifact = (repo_root / artifact).resolve()

    cfg = RunnerInput(
        script=script,
        dataset_size=int_field("dataset_size", fallback=args.dataset_size, minimum=1),
        iterations=int_field("iterations", fallback=args.iterations, minimum=1),
        warmup=int_field("warmup", fallback=args.warmup, minimum=0),
        max_retries=int_field("max_retries", fallback=args.max_retries if args.max_retries is not None else 0, minimum=0),
        artifact_path=artifact,
        dry_run=bool(payload.get("dry_run", False) or args.dry_run),
        repo_root=repo_root,
    )

    if not cfg.script.exists():
        raise ToolError("env", f"Benchmark script not found: {cfg.script}", stage="preflight")

    return cfg


def build_command(cfg: RunnerInput) -> list[str]:
    return [
        sys.executable,
        str(cfg.script),
        "--dataset-size",
        str(cfg.dataset_size),
        "--iterations",
        str(cfg.iterations),
        "--warmup",
        str(cfg.warmup),
        "--json",
    ]


def classify_failure(result: CmdResult) -> str:
    text = f"{result.stdout}\n{result.stderr}".lower()
    if any(token in text for token in ["modulenotfounderror", "no module named", "command not found", "permission denied", "env", "venv"]):
        return "env"
    if any(token in text for token in ["connection refused", "could not connect", "database", "postgres", "timeout while connecting", "deadlock"]):
        return "db"
    if any(token in text for token in ["dataset", "file not found", "enoent", "missing input", "no such file"]):
        return "data"
    return "script"


def is_transient_failure(result: CmdResult, classification: str) -> bool:
    text = f"{result.stdout}\n{result.stderr}".lower()
    if "transient" in text or "temporar" in text:
        return True
    transient_tokens = ["timeout", "timed out", "connection reset", "try again", "deadlock", "resource temporarily unavailable"]
    if any(token in text for token in transient_tokens):
        return classification in {"db", "env", "script"}
    return False


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (pct / 100.0) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = rank - low
    return ordered[low] * (1 - frac) + ordered[high] * frac


def parse_metrics(stdout: str) -> tuple[dict[str, float], dict[str, float]]:
    stdout = stdout.strip()
    if not stdout:
        raise ToolError("script", "Benchmark script produced empty output", stage="parse")

    parsed: dict[str, Any] | None = None
    try:
        candidate = json.loads(stdout)
        if isinstance(candidate, dict):
            parsed = candidate
    except json.JSONDecodeError:
        parsed = None

    values: list[float] = []
    comparison = {"minimal_vs_tasks_percent_improvement": 0.0}

    if parsed is not None:
        metrics = parsed.get("metrics") if isinstance(parsed.get("metrics"), dict) else parsed
        p50 = metrics.get("p50_ms") if isinstance(metrics, dict) else None
        p95 = metrics.get("p95_ms") if isinstance(metrics, dict) else None
        mean_ms = metrics.get("mean_ms") if isinstance(metrics, dict) else None

        if p50 is not None and p95 is not None and mean_ms is not None:
            return (
                {
                    "p50_ms": float(p50),
                    "p95_ms": float(p95),
                    "mean_ms": float(mean_ms),
                },
                {
                    "minimal_vs_tasks_percent_improvement": float(
                        parsed.get("comparison", {}).get("minimal_vs_tasks_percent_improvement", 0.0)
                        if isinstance(parsed.get("comparison"), dict)
                        else parsed.get("minimal_vs_tasks_percent_improvement", 0.0)
                    )
                },
            )

        maybe_values = metrics.get("samples_ms") if isinstance(metrics, dict) else None
        if isinstance(maybe_values, list):
            for item in maybe_values:
                try:
                    values.append(float(item))
                except (TypeError, ValueError):
                    pass

        if isinstance(parsed.get("comparison"), dict):
            try:
                comparison["minimal_vs_tasks_percent_improvement"] = float(
                    parsed["comparison"].get("minimal_vs_tasks_percent_improvement", 0.0)
                )
            except (TypeError, ValueError):
                pass

    if not values:
        # fallback text parser for lines like "runtime_ms=12.4"
        for match in re.finditer(r"(?:runtime|latency|ms)\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", stdout, re.IGNORECASE):
            values.append(float(match.group(1)))

    if not values:
        raise ToolError("script", "Unable to parse benchmark metrics from output", stage="parse")

    return (
        {
            "p50_ms": float(round(percentile(values, 50), 4)),
            "p95_ms": float(round(percentile(values, 95), 4)),
            "mean_ms": float(round(mean(values), 4)),
        },
        comparison,
    )


def write_artifact(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def execute(cfg: RunnerInput, runner: CommandRunner | None = None) -> dict[str, Any]:
    if runner is None:
        runner = CommandRunner()

    cmd = build_command(cfg)
    cmd_text = " ".join(cmd)

    if cfg.dry_run:
        return {
            "ok": True,
            "schema_version": SCHEMA_VERSION,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "attempts": 0,
            "command": cmd_text,
            "artifact_path": str(cfg.artifact_path),
            "metrics": {"p50_ms": 0.0, "p95_ms": 0.0, "mean_ms": 0.0},
            "comparison": {"minimal_vs_tasks_percent_improvement": 0.0},
            "warnings": [{"code": "dry_run", "message": "Dry-run mode enabled; benchmark not executed"}],
            "errors": [],
        }

    last_error: dict[str, Any] | None = None
    warnings: list[dict[str, Any]] = []

    for attempt in range(1, cfg.max_retries + 2):
        result = runner.run(cmd, cwd=cfg.repo_root)
        if result.returncode == 0:
            metrics, comparison = parse_metrics(result.stdout)
            artifact = {
                "schema_version": SCHEMA_VERSION,
                "tool": TOOL,
                "tool_version": TOOL_VERSION,
                "generated_at": utc_now_iso(),
                "attempts": attempt,
                "command": cmd,
                "script": str(cfg.script),
                "input": {
                    "dataset_size": cfg.dataset_size,
                    "iterations": cfg.iterations,
                    "warmup": cfg.warmup,
                    "max_retries": cfg.max_retries,
                },
                "metrics": metrics,
                "comparison": comparison,
                "stdout": result.stdout,
            }
            write_artifact(cfg.artifact_path, artifact)
            return {
                "ok": True,
                "schema_version": SCHEMA_VERSION,
                "tool": TOOL,
                "tool_version": TOOL_VERSION,
                "attempts": attempt,
                "command": cmd_text,
                "artifact_path": str(cfg.artifact_path),
                "metrics": metrics,
                "comparison": comparison,
                "warnings": warnings,
                "errors": [],
            }

        classification = classify_failure(result)
        transient = is_transient_failure(result, classification)

        last_error = {
            "code": classification,
            "message": (result.stderr.strip() or result.stdout.strip() or "benchmark failed"),
            "stage": "execute",
            "attempt": attempt,
            "transient": transient,
        }

        if transient and attempt <= cfg.max_retries:
            warnings.append(
                {
                    "code": "retry_transient_failure",
                    "message": f"Transient {classification} failure on attempt {attempt}; retrying",
                }
            )
            time.sleep(0.2)
            continue
        break

    return {
        "ok": False,
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "attempts": (last_error or {}).get("attempt", 0),
        "command": cmd_text,
        "artifact_path": str(cfg.artifact_path),
        "metrics": {"p50_ms": 0.0, "p95_ms": 0.0, "mean_ms": 0.0},
        "comparison": {"minimal_vs_tasks_percent_improvement": 0.0},
        "warnings": warnings,
        "errors": [last_error] if last_error else [{"code": "script", "message": "Unknown benchmark failure", "stage": "execute"}],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deterministic benchmark runner wrapper")
    parser.add_argument("--input-json", help="Path to JSON payload or '-' for stdin")
    parser.add_argument("--script")
    parser.add_argument("--dataset-size", type=int)
    parser.add_argument("--iterations", type=int)
    parser.add_argument("--warmup", type=int)
    parser.add_argument("--max-retries", type=int)
    parser.add_argument("--artifact-path")
    parser.add_argument("--repo-root")
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
        out = execute(cfg)
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
