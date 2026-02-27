#!/usr/bin/env python3
"""Lane C manual updater command."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SCRIPTS_ROOT.parent
for candidate in (REPO_ROOT, SCRIPTS_ROOT, SCRIPT_DIR):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from scripts.install.common import InstallError, SCHEMA_VERSION, load_install_state, resolve_context, standard_response
from scripts.install.op_install import run_install


def run_update(payload: dict[str, Any]) -> dict[str, Any]:
    ctx = resolve_context(payload)
    current_state = load_install_state(ctx.state_path)
    from_version = str(current_state.get("installed_version") or "unknown")
    updated = run_install(payload)
    if not updated.get("ok"):
        return standard_response(
            ok=False,
            status="failed",
            summary="Lane C update failed during install step.",
            errors=[{"code": "update_failed", "message": "install phase failed", "stage": "update"}],
            next_action="Inspect install errors and retry update.",
        )
    data = updated.get("data") if isinstance(updated.get("data"), dict) else {}
    to_version = str(data.get("installed_version") or "unknown")
    return standard_response(
        ok=True,
        status="completed",
        summary="Lane C update completed.",
        data={
            "from_version": from_version,
            "to_version": to_version,
            "updated_paths": data.get("managed_paths", []),
            "install_state_path": data.get("install_state_path"),
        },
        warnings=updated.get("warnings") if isinstance(updated.get("warnings"), list) else [],
        next_action="Run `opctl doctor` to confirm post-update integrity.",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update Lane C managed install from a bundle.")
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--mode", choices=["global", "local"], default="global")
    parser.add_argument("--repo-root")
    parser.add_argument("--codex-home")
    parser.add_argument("--bin-dir")
    parser.add_argument("--home-override")
    parser.add_argument("--profile", choices=["quality", "balanced", "budget"])
    parser.add_argument("--max-build-cycles", type=int)
    parser.add_argument("--strict-validation", dest="strict_validation", action="store_true")
    parser.add_argument("--no-strict-validation", dest="strict_validation", action="store_false")
    parser.set_defaults(strict_validation=None)
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
        "bundle_dir": args.bundle_dir,
        "mode": args.mode,
        "repo_root": args.repo_root,
        "codex_home": args.codex_home,
        "bin_dir": args.bin_dir,
        "home_override": args.home_override,
        "profile": args.profile,
        "max_build_cycles": args.max_build_cycles,
        "strict_validation": args.strict_validation,
    }
    try:
        out = run_update(payload)
        _print(out, args.json_pretty)
        return 0 if out.get("ok") else 1
    except InstallError as exc:
        out = {
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "status": "failed",
            "summary": "Lane C update failed.",
            "errors": [{"code": exc.code, "message": exc.message, "stage": exc.stage}],
            "warnings": [],
            "next_action": "Fix update blockers and retry.",
        }
        _print(out, args.json_pretty)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
