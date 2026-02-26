#!/usr/bin/env python3
"""Dispatch a separate Codex exec run from the current thread."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start a separate codex exec run with prompt text."
    )
    parser.add_argument(
        "--cwd",
        required=True,
        help="Workspace directory where the new codex run should execute.",
    )
    parser.add_argument("--prompt", help="Prompt text to send to codex exec.")
    parser.add_argument(
        "--prompt-file",
        help="Path to a UTF-8 text file containing the prompt.",
    )
    parser.add_argument(
        "--background",
        action="store_true",
        default=True,
        help="Run detached in background (default behavior).",
    )
    parser.add_argument(
        "--foreground",
        action="store_true",
        help="Run in foreground and stream output to current terminal.",
    )
    parser.add_argument(
        "--full-auto",
        action="store_true",
        default=True,
        help="Pass --full-auto to codex exec (default behavior).",
    )
    parser.add_argument(
        "--no-full-auto",
        action="store_true",
        help="Do not pass --full-auto to codex exec.",
    )
    parser.add_argument(
        "--extra-arg",
        action="append",
        default=[],
        help="Additional argument to pass to codex exec (repeatable).",
    )
    parser.add_argument(
        "--log-dir",
        help="Directory for detached run logs. Default: <cwd>/.codex-dispatch",
    )
    parser.add_argument(
        "--codex-home",
        help=(
            "Override CODEX_HOME for the spawned codex process "
            "(same effect as prefixing the command with CODEX_HOME=...)"
        ),
    )
    mcp_group = parser.add_mutually_exclusive_group()
    mcp_group.add_argument(
        "--disable-all-mcp",
        action="store_true",
        help=(
            "Read <CODEX_HOME>/config.toml and disable all configured MCP "
            "servers via generated -c overrides."
        ),
    )
    mcp_group.add_argument(
        "--enable-only-mcp",
        action="append",
        default=[],
        metavar="MCP_NAME",
        help=(
            "Read <CODEX_HOME>/config.toml and disable all configured MCP "
            "servers except the named MCP(s). Repeatable."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the command and metadata without starting it.",
    )
    return parser.parse_args()


def load_prompt(args: argparse.Namespace) -> str:
    if bool(args.prompt) == bool(args.prompt_file):
        raise ValueError("provide exactly one of --prompt or --prompt-file")
    if args.prompt:
        return args.prompt.strip()
    prompt_path = Path(args.prompt_file).expanduser().resolve()
    if not prompt_path.is_file():
        raise ValueError(f"prompt_file_not_found:{prompt_path}")
    text = prompt_path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("prompt_file_empty")
    return text


def effective_codex_home(args: argparse.Namespace) -> Path:
    if args.codex_home:
        return Path(args.codex_home).expanduser().resolve()
    env_home = os.environ.get("CODEX_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()
    return (Path.home() / ".codex").resolve()


def read_codex_config(config_path: Path) -> dict[str, Any]:
    if tomllib is None:
        raise ValueError("python_tomllib_unavailable")
    if not config_path.is_file():
        raise ValueError(f"config_toml_not_found:{config_path}")
    try:
        with config_path.open("rb") as fh:
            data = tomllib.load(fh)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"config_toml_parse_error:{config_path}:{exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"config_toml_invalid_root:{config_path}")
    return data


def configured_mcp_server_names(config_data: dict[str, Any]) -> list[str]:
    servers = config_data.get("mcp_servers")
    if not isinstance(servers, dict):
        return []
    names = [name for name, value in servers.items() if isinstance(name, str) and isinstance(value, dict)]
    return sorted(names)


def resolve_mcp_disable_overrides(args: argparse.Namespace) -> tuple[list[str], dict[str, Any]]:
    requested_enabled = [value.strip() for value in args.enable_only_mcp if value and value.strip()]

    if not args.disable_all_mcp and not requested_enabled:
        return [], {"mcp_mode": "inherit"}

    mode = "disable_all" if args.disable_all_mcp else "enable_only"
    codex_home = effective_codex_home(args)
    config_path = codex_home / "config.toml"
    config_data = read_codex_config(config_path)
    defined_servers = configured_mcp_server_names(config_data)
    if not defined_servers:
        raise ValueError(f"mcp_servers_not_defined_in_config:{config_path}")

    requested_enabled_set = set(requested_enabled)
    unknown_enabled = sorted(requested_enabled_set - set(defined_servers))
    if unknown_enabled:
        raise ValueError(
            "unknown_mcp_server:"
            + ",".join(unknown_enabled)
            + f":defined={','.join(defined_servers)}"
        )

    if mode == "disable_all":
        disabled_servers = defined_servers
        enabled_servers: list[str] = []
    else:
        disabled_servers = [name for name in defined_servers if name not in requested_enabled_set]
        enabled_servers = [name for name in defined_servers if name in requested_enabled_set]

    overrides = [f"mcp_servers.{name}.enabled=false" for name in disabled_servers]
    metadata = {
        "mcp_mode": mode,
        "mcp_config_path": str(config_path),
        "mcp_servers_defined": defined_servers,
        "mcp_servers_enabled": enabled_servers,
        "mcp_servers_disabled": disabled_servers,
        "mcp_disable_overrides": overrides,
    }
    return overrides, metadata


def build_command(
    args: argparse.Namespace,
    prompt_text: str,
    mcp_disable_overrides: list[str] | None = None,
) -> list[str]:
    cmd = ["codex", "exec"]
    use_full_auto = args.full_auto and not args.no_full_auto
    if use_full_auto:
        cmd.append("--full-auto")
    cmd.extend(["--cd", str(Path(args.cwd).expanduser().resolve())])
    if mcp_disable_overrides:
        for override in mcp_disable_overrides:
            cmd.extend(["-c", override])
    if args.extra_arg:
        cmd.extend(args.extra_arg)
    cmd.append(prompt_text)
    return cmd


def build_env(args: argparse.Namespace) -> dict[str, str]:
    env = os.environ.copy()
    if args.codex_home:
        env["CODEX_HOME"] = str(Path(args.codex_home).expanduser())
    return env


def main() -> int:
    args = parse_args()
    cwd = Path(args.cwd).expanduser().resolve()
    if not cwd.is_dir():
        print(f"error: cwd_not_found:{cwd}", file=sys.stderr)
        return 2

    try:
        prompt_text = load_prompt(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        mcp_disable_overrides, mcp_meta = resolve_mcp_disable_overrides(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    cmd = build_command(args, prompt_text, mcp_disable_overrides=mcp_disable_overrides)
    env = build_env(args)
    mode = "foreground" if args.foreground else "background"
    if args.foreground:
        args.background = False

    if args.log_dir:
        log_dir = Path(args.log_dir).expanduser().resolve()
    else:
        log_dir = cwd / ".codex-dispatch"
    log_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_file = log_dir / f"dispatch-{ts}.log"

    payload = {
        "mode": mode,
        "cwd": str(cwd),
        "command": cmd,
        "command_shell": shlex.join(cmd),
        "log_file": str(log_file),
        "codex_home": env.get("CODEX_HOME"),
    }
    payload.update(mcp_meta)
    if payload["codex_home"]:
        payload["command_shell_with_env"] = (
            f"CODEX_HOME={shlex.quote(payload['codex_home'])} " + shlex.join(cmd)
        )

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 0

    if args.background:
        with log_file.open("w", encoding="utf-8") as out:
            proc = subprocess.Popen(  # noqa: S603
                cmd,
                cwd=str(cwd),
                stdout=out,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env=env,
            )
        payload["pid"] = proc.pid
        payload["status"] = "started"
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 0

    completed = subprocess.run(  # noqa: S603
        cmd,
        cwd=str(cwd),
        env=env,
        check=False,
    )
    payload["status"] = "finished"
    payload["exit_code"] = completed.returncode
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
