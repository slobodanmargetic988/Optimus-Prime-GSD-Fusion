#!/usr/bin/env python3
"""Export OpenAPI, regenerate client types, and report drift deterministically."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOOL = "dev-openapi-client-sync"
TOOL_VERSION = "0.1.0"
SCHEMA_VERSION = "1.0"


class ToolError(Exception):
    def __init__(self, code: str, message: str, stage: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.stage = stage


@dataclass
class SyncInput:
    repo_root: Path
    openapi_output: Path
    client_root: Path
    generate_command: str
    export_command: str | None
    base_url_override: str | None
    fail_on_drift: bool
    dry_run: bool


@dataclass
class CmdResult:
    returncode: int
    stdout: str
    stderr: str


class CommandRunner:
    def run(self, cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> CmdResult:
        proc = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True, check=False)
        return CmdResult(proc.returncode, proc.stdout, proc.stderr)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: str) -> dict[str, Any]:
    if path == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ToolError("input_error", "Input payload must be a JSON object", stage="input")
    return data


def parse_input(args: argparse.Namespace) -> SyncInput:
    payload: dict[str, Any] = {}
    if args.input_json:
        payload = load_json(args.input_json)

    def required_str(key: str, fallback: Any = None) -> str:
        v = payload.get(key, fallback)
        if not isinstance(v, str) or not v.strip():
            raise ToolError("input_error", f"{key} is required and must be a non-empty string", stage="input")
        return v.strip()

    repo_root_raw = payload.get("repo_root", args.repo_root or ".")
    if not isinstance(repo_root_raw, str) or not repo_root_raw.strip():
        raise ToolError("input_error", "repo_root must be a non-empty string", stage="input")
    repo_root = Path(repo_root_raw).expanduser().resolve()

    openapi_output = Path(required_str("openapi_output", fallback=args.openapi_output)).expanduser()
    if not openapi_output.is_absolute():
        openapi_output = (repo_root / openapi_output).resolve()

    client_root = Path(required_str("client_root", fallback=args.client_root)).expanduser()
    if not client_root.is_absolute():
        client_root = (repo_root / client_root).resolve()

    generate_command = required_str("generate_command", fallback=args.generate_command)
    export_command = payload.get("export_command", args.export_command)
    if export_command is not None and (not isinstance(export_command, str) or not export_command.strip()):
        export_command = None

    base_url_override = payload.get("base_url_override", args.base_url_override)
    if base_url_override is not None and (not isinstance(base_url_override, str) or not base_url_override.strip()):
        base_url_override = None

    fail_on_drift = bool(payload.get("fail_on_drift", args.fail_on_drift or False))
    dry_run = bool(payload.get("dry_run", args.dry_run or False))

    if not client_root.exists():
        raise ToolError("env", f"client_root not found: {client_root}", stage="preflight")

    return SyncInput(
        repo_root=repo_root,
        openapi_output=openapi_output,
        client_root=client_root,
        generate_command=generate_command,
        export_command=export_command.strip() if isinstance(export_command, str) else None,
        base_url_override=base_url_override.strip() if isinstance(base_url_override, str) else None,
        fail_on_drift=fail_on_drift,
        dry_run=dry_run,
    )


PLACEHOLDER_VALUES = ("openapi_output", "client_root", "base_url_override")


def render_command(template: str, cfg: SyncInput) -> list[str]:
    rendered = template
    values = {
        "openapi_output": str(cfg.openapi_output),
        "client_root": str(cfg.client_root),
        "base_url_override": cfg.base_url_override or "",
    }
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", value)

    unresolved = sorted(
        {
            m.group(1)
            for m in re.finditer(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", rendered)
            if m.group(1) not in PLACEHOLDER_VALUES
        }
    )
    if unresolved:
        raise ToolError(
            "input_error",
            f"Unknown command placeholder(s): {', '.join(unresolved)}",
            stage="input",
        )

    rendered = rendered.strip()
    if not rendered:
        raise ToolError("input_error", "Rendered command is empty", stage="input")
    return shlex.split(rendered)


def default_export_command(cfg: SyncInput) -> list[str]:
    # fallback deterministic command; users can override via input.export_command
    return ["openapi", "export", "--output", str(cfg.openapi_output)]


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot_files(root: Path) -> dict[str, str]:
    snap: dict[str, str] = {}
    if not root.exists():
        return snap
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(root))
            snap[rel] = hash_file(p)
    return snap


def changed_files(before: dict[str, str], after: dict[str, str]) -> list[str]:
    keys = set(before.keys()) | set(after.keys())
    changed: list[str] = []
    for key in sorted(keys):
        if before.get(key) != after.get(key):
            changed.append(key)
    return changed


def classify_command_failure(result: CmdResult) -> tuple[str, str]:
    text = f"{result.stdout}\n{result.stderr}".lower()
    if "npm err" in text or "cannot find module" in text or "command not found" in text or "enoent" in text:
        return "env", "Missing dependency or command during sync command execution"
    if "openapi" in text and "not found" in text:
        return "env", "OpenAPI export tool is unavailable"
    if "schema" in text or "spec" in text:
        return "data", "OpenAPI schema/data error during export or generation"
    return "script", "Sync command failed"


def run_command_or_error(runner: CommandRunner, cmd: list[str], cwd: Path, env: dict[str, str] | None, stage: str) -> CmdResult:
    result = runner.run(cmd, cwd=cwd, env=env)
    if result.returncode == 0:
        return result
    code, summary = classify_command_failure(result)
    detail = result.stderr.strip() or result.stdout.strip() or summary
    raise ToolError(code, f"{summary}: {detail}", stage=stage)


def execute(cfg: SyncInput, runner: CommandRunner | None = None) -> dict[str, Any]:
    if runner is None:
        runner = CommandRunner()

    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    export_cmd = render_command(cfg.export_command, cfg) if cfg.export_command else default_export_command(cfg)
    gen_cmd = render_command(cfg.generate_command, cfg)

    if cfg.dry_run:
        return {
            "ok": True,
            "schema_version": SCHEMA_VERSION,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "openapi_generated": False,
            "client_generated": False,
            "changed_files": [],
            "drift_detected": False,
            "warnings": [
                {
                    "code": "dry_run",
                    "message": "Dry-run mode enabled; no export/generation commands were executed",
                    "planned_commands": {
                        "export": export_cmd,
                        "generate": gen_cmd,
                    },
                }
            ],
            "errors": [],
        }

    before = snapshot_files(cfg.client_root)

    env = os.environ.copy()
    if cfg.base_url_override:
        env["OPENAPI_BASE_URL"] = cfg.base_url_override
        warnings.append({"code": "base_url_override", "message": f"Using OPENAPI_BASE_URL={cfg.base_url_override}"})

    openapi_generated = False
    client_generated = False

    try:
        cfg.openapi_output.parent.mkdir(parents=True, exist_ok=True)
        run_command_or_error(runner, export_cmd, cwd=cfg.repo_root, env=env, stage="export")
        openapi_generated = cfg.openapi_output.exists()
        if not openapi_generated:
            warnings.append({"code": "openapi_missing_after_export", "message": f"Export command succeeded but output missing at {cfg.openapi_output}"})
    except ToolError as exc:
        errors.append({"code": exc.code, "message": exc.message, "stage": exc.stage})

    if not errors:
        try:
            run_command_or_error(runner, gen_cmd, cwd=cfg.client_root, env=env, stage="generate")
            client_generated = True
        except ToolError as exc:
            errors.append({"code": exc.code, "message": exc.message, "stage": exc.stage})

    after = snapshot_files(cfg.client_root)
    drift = changed_files(before, after)
    drift_detected = len(drift) > 0

    if cfg.fail_on_drift and drift_detected:
        errors.append(
            {
                "code": "drift_detected",
                "message": "Drift detected and fail_on_drift=true",
                "stage": "drift",
            }
        )

    out = {
        "ok": len(errors) == 0,
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "openapi_generated": openapi_generated,
        "client_generated": client_generated,
        "changed_files": drift,
        "drift_detected": drift_detected,
        "warnings": warnings,
        "errors": errors,
    }
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenAPI export + client sync + drift report")
    parser.add_argument("--input-json", help="Path to JSON payload or '-' for stdin")
    parser.add_argument("--repo-root")
    parser.add_argument("--openapi-output")
    parser.add_argument("--client-root")
    parser.add_argument("--generate-command")
    parser.add_argument("--export-command")
    parser.add_argument("--base-url-override")
    parser.add_argument("--fail-on-drift", action="store_true")
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
