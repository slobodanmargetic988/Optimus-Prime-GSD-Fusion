#!/usr/bin/env python3
"""Create a derived Codex profile with copy/symlink policy."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
COPY_ITEMS = {"auth.json", "sessions"}


class ProfileError(Exception):
    def __init__(self, code: str, message: str, stage: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.stage = stage


def _resolve_default_source() -> Path:
    env_home = os.environ.get("CODEX_HOME")
    if env_home:
        return Path(os.path.expanduser(os.path.expandvars(env_home))).resolve()
    return (Path.home() / ".codex").resolve()


def _normalize_profile_name(value: str) -> str:
    raw = value.strip()
    if not raw:
        raise ProfileError("input_error", "profile must be non-empty", "input")
    if raw.startswith(".codex-"):
        alias = raw[len(".codex-") :]
    elif raw.startswith("codex-"):
        alias = raw[len("codex-") :]
    elif raw.startswith(".codex"):
        alias = raw[len(".codex") :]
        alias = alias.lstrip("-_")
    else:
        alias = raw
    alias = alias.strip()
    if not alias:
        raise ProfileError("input_error", "profile alias resolved to empty value", "input")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", alias):
        raise ProfileError(
            "input_error",
            "profile alias must match [A-Za-z0-9][A-Za-z0-9._-]*",
            "input",
        )
    return f".codex-{alias}"


def _copy_item(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dst)
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _symlink_item(src: Path, dst: Path) -> None:
    if dst.exists() or dst.is_symlink():
        if dst.is_dir() and not dst.is_symlink():
            shutil.rmtree(dst)
        else:
            dst.unlink()
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.symlink_to(src)


def create_profile(
    *,
    source_codex_home: Path,
    profile: str,
    target_codex_home: Path | None,
    replace: bool,
) -> dict[str, Any]:
    source = source_codex_home.expanduser().resolve()
    if not source.exists() or not source.is_dir():
        raise ProfileError("source_missing", f"source CODEX_HOME missing: {source}", "validate")
    source_auth = source / "auth.json"
    if not source_auth.is_file():
        raise ProfileError("source_missing", f"source auth.json missing: {source_auth}", "validate")

    profile_dir_name = _normalize_profile_name(profile)
    if target_codex_home is None:
        target = (source.parent / profile_dir_name).resolve()
    else:
        target = target_codex_home.expanduser().resolve()

    if target == source:
        raise ProfileError("input_error", "target profile path must differ from source CODEX_HOME", "input")

    if target.exists():
        if not replace:
            raise ProfileError(
                "target_exists",
                f"target profile already exists: {target} (use --replace to recreate)",
                "prepare",
            )
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()

    target.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    symlinked: list[str] = []
    warnings: list[dict[str, Any]] = []

    for child in sorted(source.iterdir(), key=lambda p: p.name.lower()):
        name = child.name
        dst = target / name
        if name in COPY_ITEMS:
            if not child.exists():
                if name == "sessions":
                    warnings.append(
                        {
                            "code": "sessions_missing",
                            "message": f"source sessions directory missing; created empty directory at {dst}",
                            "stage": "copy",
                        }
                    )
                    dst.mkdir(parents=True, exist_ok=True)
                    copied.append(str(dst))
                    continue
                raise ProfileError("source_missing", f"required source item missing: {child}", "copy")
            _copy_item(child, dst)
            copied.append(str(dst))
            continue
        _symlink_item(child, dst)
        symlinked.append(str(dst))

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "status": "completed",
        "summary": "Codex profile created.",
        "warnings": warnings,
        "errors": [],
        "data": {
            "source_codex_home": str(source),
            "target_codex_home": str(target),
            "profile_dir_name": target.name,
            "copied_items": copied,
            "symlinked_items": symlinked,
            "copy_policy": sorted(COPY_ITEMS),
        },
        "next_action": "Set CODEX_HOME to the new profile path when you want to run under that profile.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a derived .codex profile with copy/symlink policy.")
    parser.add_argument("--profile", required=True, help="Profile alias/name (e.g. second or .codex-second).")
    parser.add_argument("--source-codex-home", default=None, help="Source CODEX_HOME path (default: $CODEX_HOME or ~/.codex).")
    parser.add_argument(
        "--target-codex-home",
        default=None,
        help="Explicit target CODEX_HOME path (default: sibling .codex-<profile>).",
    )
    parser.add_argument("--replace", action="store_true", help="Replace target profile directory if it already exists.")
    parser.add_argument("--json-pretty", action="store_true")
    return parser.parse_args()


def _print(payload: dict[str, Any], pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=False))
    else:
        print(json.dumps(payload, separators=(",", ":"), sort_keys=False))


def main() -> int:
    args = parse_args()
    source = Path(args.source_codex_home).expanduser().resolve() if args.source_codex_home else _resolve_default_source()
    target = Path(args.target_codex_home).expanduser().resolve() if args.target_codex_home else None
    try:
        out = create_profile(
            source_codex_home=source,
            profile=args.profile,
            target_codex_home=target,
            replace=bool(args.replace),
        )
        _print(out, args.json_pretty)
        return 0
    except ProfileError as exc:
        out = {
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "status": "failed",
            "summary": "Failed to create Codex profile.",
            "warnings": [],
            "errors": [{"code": exc.code, "message": exc.message, "stage": exc.stage}],
            "next_action": "Fix the reported input/path issue and retry.",
        }
        _print(out, args.json_pretty)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
