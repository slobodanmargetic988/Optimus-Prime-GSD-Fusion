#!/usr/bin/env python3
"""Deterministic local PostgreSQL lifecycle runner for developer packets."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

TOOL = "dev-ephemeral-db-runner"
TOOL_VERSION = "0.1.0"
SCHEMA_VERSION = "1.0"

CLEANUP_MODES = {"preserve", "destroy_on_exit"}
ACTIONS = {"start", "stop"}
SHM_COMPAT_PRIMARY = "none"
SHM_COMPAT_FALLBACK_ORDER = ("mmap", "posix", "sysv")


class ToolError(Exception):
    def __init__(self, code: str, message: str, stage: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.stage = stage


@dataclass
class RunnerInput:
    action: str
    profile_name: str
    port: int
    db_name: str
    host: str
    cleanup_mode: str
    shared_memory_compat: bool
    dry_run: bool
    base_dir: Path


@dataclass
class CmdResult:
    returncode: int
    stdout: str
    stderr: str


class CommandRunner:
    def run(self, cmd: list[str]) -> CmdResult:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return CmdResult(returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(value: str) -> str:
    out = []
    for ch in value.strip():
        if ch.isalnum() or ch in {"-", "_", "."}:
            out.append(ch)
        else:
            out.append("-")
    text = "".join(out).strip("-")
    return text or "profile"


def load_input(path: str) -> dict[str, Any]:
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
        v = value.strip().lower()
        if v in {"1", "true", "yes", "on"}:
            return True
        if v in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def parse_config(args: argparse.Namespace) -> RunnerInput:
    payload: dict[str, Any] = {}
    if args.input_json:
        payload = load_input(args.input_json)

    def required_str(key: str, fallback: Any = None) -> str:
        v = payload.get(key, fallback)
        if not isinstance(v, str) or not v.strip():
            raise ToolError("input_error", f"{key} is required and must be a non-empty string", stage="input")
        return v.strip()

    action = required_str("action", fallback=args.action or "start").lower()
    if action not in ACTIONS:
        raise ToolError("input_error", f"action must be one of: {', '.join(sorted(ACTIONS))}", stage="input")

    profile_name = required_str("profile_name", fallback=args.profile_name)

    port_value = payload.get("port", args.port)
    if port_value is None:
        port_value = 55432
    try:
        port = int(port_value)
    except (TypeError, ValueError) as exc:
        raise ToolError("input_error", "port must be an integer", stage="input") from exc

    db_name = required_str("db_name", fallback=args.db_name or "myboard_test_v2")
    host = required_str("host", fallback=args.host or "127.0.0.1")
    cleanup_mode = required_str("cleanup_mode", fallback=args.cleanup_mode or "preserve")
    if cleanup_mode not in CLEANUP_MODES:
        raise ToolError("input_error", f"cleanup_mode must be one of: {', '.join(sorted(CLEANUP_MODES))}", stage="input")

    if port < 1 or port > 65535:
        raise ToolError("input_error", "port must be in range 1..65535", stage="input")

    shared_memory_compat = as_bool(payload.get("shared_memory_compat", args.shared_memory_compat), default=True)
    dry_run = as_bool(payload.get("dry_run", args.dry_run), default=False)

    base_dir_raw = payload.get("base_dir", args.base_dir)
    if isinstance(base_dir_raw, str) and base_dir_raw.strip():
        base_dir = Path(base_dir_raw).expanduser().resolve()
    else:
        base_dir = (Path("/tmp") / "dev-ephemeral-db-runner" / slugify(profile_name)).resolve()

    return RunnerInput(
        action=action,
        profile_name=profile_name,
        port=port,
        db_name=db_name,
        host=host,
        cleanup_mode=cleanup_mode,
        shared_memory_compat=shared_memory_compat,
        dry_run=dry_run,
        base_dir=base_dir,
    )


def paths_for(cfg: RunnerInput) -> dict[str, Path]:
    pgdata = cfg.base_dir / "pgdata"
    logfile = cfg.base_dir / "postgres.log"
    state = cfg.base_dir / "state.json"
    return {"base": cfg.base_dir, "pgdata": pgdata, "log": logfile, "state": state}


def ensure_binaries(action: str, which_fn: Callable[[str], str | None] = shutil.which) -> dict[str, str]:
    needed = ["pg_ctl"]
    if action == "start":
        needed.extend(["initdb", "createdb"])

    found: dict[str, str] = {}
    missing: list[str] = []
    for binary in needed:
        path = which_fn(binary)
        if path:
            found[binary] = path
        else:
            missing.append(binary)

    pg_isready = which_fn("pg_isready")
    if pg_isready:
        found["pg_isready"] = pg_isready

    if missing:
        raise ToolError(
            "missing_binaries",
            f"Required PostgreSQL binaries not found: {', '.join(missing)}",
            stage="preflight",
        )
    return found


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ToolError("state_error", f"Malformed state file {path}: {exc}", stage="state") from exc
    except OSError as exc:
        raise ToolError("state_error", f"Failed to read state file {path}: {exc}", stage="state") from exc
    if isinstance(data, dict):
        return data
    raise ToolError("state_error", f"Invalid state format in {path}", stage="state")


def pg_ctl_status(runner: CommandRunner, pg_ctl: str, pgdata: Path) -> bool:
    res = runner.run([pg_ctl, "-D", str(pgdata), "status"])
    return res.returncode == 0


def init_cluster(runner: CommandRunner, initdb: str, pgdata: Path) -> None:
    pgdata.parent.mkdir(parents=True, exist_ok=True)
    if (pgdata / "PG_VERSION").exists():
        return
    res = runner.run([initdb, "-D", str(pgdata), "-U", "postgres", "-A", "trust", "-E", "UTF8"])
    if res.returncode != 0:
        raise ToolError(
            "cluster_init_failed",
            f"initdb failed: {res.stderr.strip() or res.stdout.strip()}",
            stage="init",
        )


def start_postgres(
    runner: CommandRunner,
    pg_ctl: str,
    pgdata: Path,
    logfile: Path,
    host: str,
    port: int,
    shared_memory_compat: bool,
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []

    def start_with_dynamic_shm(value: str | None) -> CmdResult:
        opts = [f"-p {port}", f"-h {host}"]
        if value:
            opts.append(f"-c dynamic_shared_memory_type={value}")
        opts_str = " ".join(opts)
        return runner.run([pg_ctl, "-D", str(pgdata), "-l", str(logfile), "-o", opts_str, "start"])

    def parse_available_dynamic_shm_values(text: str) -> list[str]:
        match = re.search(r"Available values:\s*([a-z,\s]+)\.", text, flags=re.IGNORECASE)
        if not match:
            return []
        values = [part.strip().lower() for part in match.group(1).split(",")]
        return [value for value in values if value]

    logfile.parent.mkdir(parents=True, exist_ok=True)
    dynamic_shm_value = SHM_COMPAT_PRIMARY if shared_memory_compat else None
    res = start_with_dynamic_shm(dynamic_shm_value)
    if res.returncode == 0:
        return warnings

    combined = f"{res.stdout}\n{res.stderr}".lower()
    if "address already in use" in combined or "could not bind" in combined:
        raise ToolError("port_occupied", f"Port {port} appears occupied", stage="start")

    log_text = ""
    try:
        log_text = logfile.read_text(encoding="utf-8")
    except OSError:
        log_text = ""

    invalid_dynamic_shm = (
        shared_memory_compat
        and "invalid value for parameter \"dynamic_shared_memory_type\"" in (combined + "\n" + log_text.lower())
    )
    if invalid_dynamic_shm:
        available = parse_available_dynamic_shm_values(log_text or f"{res.stdout}\n{res.stderr}")
        fallback = next((v for v in SHM_COMPAT_FALLBACK_ORDER if v in available), None)
        if fallback is None and available:
            fallback = available[0]
        if fallback and fallback != SHM_COMPAT_PRIMARY:
            retry = start_with_dynamic_shm(fallback)
            if retry.returncode == 0:
                warnings.append(
                    {
                        "code": "shared_memory_compat_fallback",
                        "message": f"Retried PostgreSQL startup with dynamic_shared_memory_type={fallback}",
                    }
                )
                return warnings
            retry_text = f"{retry.stdout}\n{retry.stderr}".lower()
            if "address already in use" in retry_text or "could not bind" in retry_text:
                raise ToolError("port_occupied", f"Port {port} appears occupied", stage="start")
            raise ToolError(
                "startup_failed",
                f"pg_ctl start failed after shared-memory fallback ({fallback}): {retry.stderr.strip() or retry.stdout.strip()}",
                stage="start",
            )

    raise ToolError("startup_failed", f"pg_ctl start failed: {res.stderr.strip() or res.stdout.strip()}", stage="start")


def wait_ready(runner: CommandRunner, binaries: dict[str, str], host: str, port: int) -> None:
    for _ in range(20):
        if "pg_isready" in binaries:
            res = runner.run([binaries["pg_isready"], "-h", host, "-p", str(port), "-d", "postgres", "-U", "postgres"])
            if res.returncode == 0:
                return
        else:
            return
        time.sleep(0.25)
    raise ToolError("startup_failed", "PostgreSQL readiness check timed out", stage="start")


def create_database_if_missing(runner: CommandRunner, createdb: str, host: str, port: int, db_name: str) -> None:
    res = runner.run([createdb, "--if-not-exists", "-h", host, "-p", str(port), "-U", "postgres", db_name])
    if res.returncode == 0:
        return
    combined = f"{res.stdout}\n{res.stderr}".lower()
    if "already exists" in combined:
        return
    res2 = runner.run([createdb, "-h", host, "-p", str(port), "-U", "postgres", db_name])
    if res2.returncode == 0:
        return
    combined2 = f"{res2.stdout}\n{res2.stderr}".lower()
    if "already exists" in combined2:
        return
    raise ToolError("db_create_failed", f"createdb failed: {res2.stderr.strip() or res2.stdout.strip()}", stage="db_create")


def stop_postgres(runner: CommandRunner, pg_ctl: str, pgdata: Path) -> bool:
    if not pgdata.exists():
        return False
    res = runner.run([pg_ctl, "-D", str(pgdata), "stop", "-m", "fast"])
    if res.returncode != 0:
        text = (res.stderr or res.stdout or "").lower()
        if "no server running" in text:
            return False
        raise ToolError("stop_failed", f"pg_ctl stop failed: {res.stderr.strip() or res.stdout.strip()}", stage="stop")
    return True


def cleanup_base_dir(base_dir: Path) -> None:
    if base_dir.exists():
        shutil.rmtree(base_dir)


def dsn_sqlalchemy(host: str, port: int, db_name: str) -> str:
    return f"postgresql+psycopg2://postgres@{host}:{port}/{db_name}"


def dsn_standard(host: str, port: int, db_name: str) -> str:
    return f"postgresql://postgres@{host}:{port}/{db_name}"


def build_stop_cmd(cfg: RunnerInput) -> str:
    script = Path(__file__).resolve()
    return (
        f"python3 {script} --action stop --profile-name {cfg.profile_name} "
        f"--port {cfg.port} --db-name {cfg.db_name} --host {cfg.host} "
        f"--cleanup-mode {cfg.cleanup_mode}"
    )


def run_start(cfg: RunnerInput, runner: CommandRunner, which_fn: Callable[[str], str | None] = shutil.which) -> dict[str, Any]:
    paths = paths_for(cfg)
    binaries = ensure_binaries("start", which_fn=which_fn)

    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    state = read_json(paths["state"])
    already_running = False
    if state and paths["pgdata"].exists() and pg_ctl_status(runner, binaries["pg_ctl"], paths["pgdata"]):
        already_running = True

    if not already_running:
        init_cluster(runner, binaries["initdb"], paths["pgdata"])
        warnings.extend(
            start_postgres(
                runner,
                binaries["pg_ctl"],
                paths["pgdata"],
                paths["log"],
                cfg.host,
                cfg.port,
                cfg.shared_memory_compat,
            )
        )
        wait_ready(runner, binaries, cfg.host, cfg.port)
    else:
        warnings.append({"code": "already_running", "message": "Profile already running; reusing existing instance"})

    create_database_if_missing(runner, binaries["createdb"], cfg.host, cfg.port, cfg.db_name)

    state_payload = {
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "profile_name": cfg.profile_name,
        "host": cfg.host,
        "port": cfg.port,
        "db_name": cfg.db_name,
        "pgdata": str(paths["pgdata"]),
        "log_file": str(paths["log"]),
        "cleanup_mode": cfg.cleanup_mode,
        "shared_memory_compat": cfg.shared_memory_compat,
        "updated_at": utc_now_iso(),
    }
    write_json(paths["state"], state_payload)

    dsn = dsn_sqlalchemy(cfg.host, cfg.port, cfg.db_name)
    out = {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "profile_name": cfg.profile_name,
        "host": cfg.host,
        "port": cfg.port,
        "db_name": cfg.db_name,
        "dsn": dsn,
        "dsn_standard": dsn_standard(cfg.host, cfg.port, cfg.db_name),
        "env": {
            "TEST_DATABASE_URL": dsn,
            "DATABASE_URL": dsn,
        },
        "pgdata": str(paths["pgdata"]),
        "log_file": str(paths["log"]),
        "started": True,
        "stop_cmd": build_stop_cmd(cfg),
        "warnings": warnings,
        "errors": errors,
    }
    return out


def run_stop(cfg: RunnerInput, runner: CommandRunner, which_fn: Callable[[str], str | None] = shutil.which) -> dict[str, Any]:
    paths = paths_for(cfg)
    binaries = ensure_binaries("stop", which_fn=which_fn)

    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    stopped = False
    if paths["pgdata"].exists():
        try:
            stopped = stop_postgres(runner, binaries["pg_ctl"], paths["pgdata"])
        except ToolError as exc:
            errors.append({"code": exc.code, "message": exc.message, "stage": exc.stage})
    else:
        warnings.append({"code": "missing_pgdata", "message": "PGDATA path does not exist; nothing to stop"})

    if cfg.cleanup_mode == "destroy_on_exit":
        try:
            cleanup_base_dir(paths["base"])
        except OSError as exc:
            errors.append({"code": "cleanup_failed", "message": str(exc), "stage": "cleanup"})
    else:
        if paths["state"].exists():
            try:
                state = read_json(paths["state"]) or {}
                state["updated_at"] = utc_now_iso()
                state["last_stop"] = utc_now_iso()
                write_json(paths["state"], state)
            except ToolError as exc:
                warnings.append({"code": exc.code, "message": exc.message, "stage": exc.stage})

    return {
        "ok": len(errors) == 0,
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "profile_name": cfg.profile_name,
        "host": cfg.host,
        "port": cfg.port,
        "db_name": cfg.db_name,
        "dsn": dsn_sqlalchemy(cfg.host, cfg.port, cfg.db_name),
        "pgdata": str(paths["pgdata"]),
        "log_file": str(paths["log"]),
        "started": False,
        "stopped": stopped,
        "stop_cmd": build_stop_cmd(cfg),
        "warnings": warnings,
        "errors": errors,
    }


def run(cfg: RunnerInput, runner: CommandRunner | None = None, which_fn: Callable[[str], str | None] = shutil.which) -> dict[str, Any]:
    if runner is None:
        runner = CommandRunner()

    if cfg.dry_run:
        paths = paths_for(cfg)
        return {
            "ok": True,
            "schema_version": SCHEMA_VERSION,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "profile_name": cfg.profile_name,
            "host": cfg.host,
            "port": cfg.port,
            "db_name": cfg.db_name,
            "dsn": dsn_sqlalchemy(cfg.host, cfg.port, cfg.db_name),
            "pgdata": str(paths["pgdata"]),
            "log_file": str(paths["log"]),
            "started": cfg.action == "start",
            "stop_cmd": build_stop_cmd(cfg),
            "warnings": [
                {
                    "code": "dry_run",
                    "message": f"Dry-run mode enabled; no process or filesystem mutations performed for action={cfg.action}",
                }
            ],
            "errors": [],
        }

    if cfg.action == "start":
        return run_start(cfg, runner, which_fn=which_fn)
    if cfg.action == "stop":
        return run_stop(cfg, runner, which_fn=which_fn)
    raise ToolError("input_error", f"Unsupported action '{cfg.action}'", stage="input")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deterministic local PostgreSQL lifecycle runner")
    parser.add_argument("--input-json", help="Path to JSON input, or '-' for stdin")
    parser.add_argument("--action", choices=sorted(ACTIONS), default="start")
    parser.add_argument("--profile-name")
    parser.add_argument("--port", type=int)
    parser.add_argument("--db-name")
    parser.add_argument("--host")
    parser.add_argument("--cleanup-mode")
    parser.add_argument("--shared-memory-compat", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--base-dir")
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
        cfg = parse_config(args)
        out = run(cfg)
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
