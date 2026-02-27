#!/usr/bin/env python3
"""Lane C uninstaller command."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SCRIPTS_ROOT.parent
for candidate in (REPO_ROOT, SCRIPTS_ROOT, SCRIPT_DIR):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from scripts.install.common import (
    InstallError,
    SCHEMA_VERSION,
    as_str,
    load_install_state,
    normalize_managed_paths,
    resolve_context,
    standard_response,
)


def _remove_path(path: Path) -> bool:
    if not path.exists() and not path.is_symlink():
        return False
    if path.is_symlink() or path.is_file():
        path.unlink()
        return True
    shutil.rmtree(path)
    return True


def run_uninstall(payload: dict[str, Any]) -> dict[str, Any]:
    ctx = resolve_context(payload)
    state = load_install_state(ctx.state_path)
    managed_paths = normalize_managed_paths(state)
    removed_paths: list[str] = []
    preserve = [str(ctx.config_dir)]
    warnings: list[dict[str, Any]] = []
    for raw in managed_paths:
        path = Path(raw).expanduser().resolve()
        try:
            removed = _remove_path(path)
            if removed:
                removed_paths.append(str(path))
        except OSError as exc:
            warnings.append(
                {
                    "code": "remove_failed",
                    "message": f"failed to remove managed path {path}: {exc}",
                    "stage": "uninstall",
                    "path": str(path),
                }
            )
    if ctx.state_path.exists():
        ctx.state_path.unlink()
    return standard_response(
        ok=True,
        status="completed",
        summary="Lane C uninstall completed.",
        data={
            "install_mode": ctx.mode,
            "removed_paths": sorted(set(removed_paths)),
            "preserved_paths": preserve,
            "previous_version": as_str(state.get("installed_version")) or "unknown",
        },
        warnings=warnings,
        next_action="Installation removed. Reinstall with `op_install.py` when ready.",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Uninstall Lane C managed install.")
    parser.add_argument("--mode", choices=["global", "local"], default="global")
    parser.add_argument("--repo-root")
    parser.add_argument("--home-override")
    parser.add_argument("--json-pretty", action="store_true")
    return parser.parse_args()


def _print(payload: dict[str, Any], pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=False))
    else:
        print(json.dumps(payload, separators=(",", ":"), sort_keys=False))


def main() -> int:
    args = parse_args()
    payload = {
        "mode": args.mode,
        "repo_root": args.repo_root,
        "home_override": args.home_override,
    }
    try:
        out = run_uninstall(payload)
        _print(out, args.json_pretty)
        return 0 if out.get("ok") else 1
    except InstallError as exc:
        out = {
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "status": "failed",
            "summary": "Lane C uninstall failed.",
            "errors": [{"code": exc.code, "message": exc.message, "stage": exc.stage}],
            "warnings": [],
            "next_action": "Fix uninstall blockers and rerun uninstall.",
        }
        _print(out, args.json_pretty)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
