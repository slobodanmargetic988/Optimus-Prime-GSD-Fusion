#!/usr/bin/env python3
"""Lane C installer command."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
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
    atomic_write_json,
    build_state_payload,
    copy_codex_assets,
    copy_tree_replace,
    ensure_launcher,
    load_bundle,
    read_json,
    resolve_context,
    standard_response,
    utc_now_iso,
    verify_bundle_integrity,
)
from scripts.install.config import resolve_effective_config


def _bundle_dir(payload: dict[str, Any]) -> Path:
    raw = payload.get("bundle_dir")
    if not isinstance(raw, str) or not raw.strip():
        raise InstallError("input_error", "bundle_dir is required", stage="input")
    return Path(raw).expanduser().resolve()


def _backup_existing_install(ctx_install_root: Path, backup_root: Path) -> str | None:
    if not ctx_install_root.exists():
        return None
    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_root / f"install-backup-{stamp}"
    if backup_path.exists():
        shutil.rmtree(backup_path)
    shutil.move(str(ctx_install_root), str(backup_path))
    return str(backup_path)


def run_install(payload: dict[str, Any]) -> dict[str, Any]:
    ctx = resolve_context(payload)
    config_resolution = resolve_effective_config(payload, ctx)
    if config_resolution["errors"]:
        rendered = "; ".join(
            f"{item.get('field')}: {item.get('message')} ({item.get('fix')})"
            for item in config_resolution["errors"]
        )
        raise InstallError("config_error", f"invalid effective config: {rendered}", stage="config")
    bundle_dir = _bundle_dir(payload)
    manifest, checksums = load_bundle(bundle_dir)
    verify_bundle_integrity(bundle_dir, manifest, checksums)
    version = str(manifest.get("product_version") or "0.0.0")

    previous_state = None
    if ctx.state_path.exists():
        parsed = read_json(ctx.state_path)
        if isinstance(parsed, dict):
            previous_state = parsed

    ctx.config_dir.mkdir(parents=True, exist_ok=True)
    ctx.install_root.parent.mkdir(parents=True, exist_ok=True)
    ctx.bin_dir.mkdir(parents=True, exist_ok=True)
    ctx.codex_home.mkdir(parents=True, exist_ok=True)
    backup_path = _backup_existing_install(ctx.install_root, ctx.backup_root)

    payload_root = bundle_dir / "payload"
    if not payload_root.exists():
        raise InstallError("validation_error", f"bundle payload missing: {payload_root}", stage="validate")
    copy_tree_replace(payload_root, ctx.install_root)

    product_entry = ctx.install_root / "scripts" / "op" / "opctl_product.py"
    if not product_entry.exists():
        raise InstallError(
            "validation_error",
            f"installed product entrypoint missing from payload: {product_entry}",
            stage="install",
        )
    opctl_path = ctx.bin_dir / "opctl"
    op_alias_path = ctx.bin_dir / "op"
    ensure_launcher(opctl_path, product_entry)
    ensure_launcher(op_alias_path, product_entry)

    codex_managed = copy_codex_assets(bundle_dir, ctx.codex_home)
    managed_paths = [str(ctx.install_root), str(opctl_path), str(op_alias_path), *codex_managed]
    recovery = {
        "last_backup_path": backup_path,
        "last_recovery_reason": "in_place_replace" if backup_path else None,
    }
    install_state = build_state_payload(
        ctx=ctx,
        installed_version=version,
        managed_paths=managed_paths,
        recovery=recovery,
        previous=previous_state,
    )
    atomic_write_json(ctx.state_path, install_state)
    return standard_response(
        ok=True,
        status="completed",
        summary="Lane C install completed.",
        data={
            "install_mode": ctx.mode,
            "installed_version": version,
            "install_state_path": str(ctx.state_path),
            "install_root": str(ctx.install_root),
            "bin_dir": str(ctx.bin_dir),
            "codex_home": str(ctx.codex_home),
            "managed_paths": install_state.get("managed_paths", []),
            "effective_config": config_resolution["effective_config"],
            "config_sources": config_resolution["sources"],
            "updated_at": utc_now_iso(),
        },
        next_action="Run `opctl doctor` to validate environment and install integrity.",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install Lane C bundle.")
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
        out = run_install(payload)
        _print(out, args.json_pretty)
        return 0 if out.get("ok") else 1
    except InstallError as exc:
        out = {
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "status": "failed",
            "summary": "Lane C install failed.",
            "errors": [{"code": exc.code, "message": exc.message, "stage": exc.stage}],
            "warnings": [],
            "next_action": "Fix the error and rerun install.",
        }
        _print(out, args.json_pretty)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
