#!/usr/bin/env python3
"""Lane C environment diagnostics and optional repair command."""

from __future__ import annotations

import argparse
import json
import os
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
    atomic_write_json,
    load_install_state,
    normalize_managed_paths,
    read_json,
    resolve_context,
    standard_response,
    utc_now_iso,
)
from scripts.install.config import resolve_effective_config


def _check_python() -> dict[str, Any]:
    passed = sys.version_info >= (3, 11)
    return {
        "id": "python_version",
        "passed": passed,
        "severity": "high",
        "fixable": False,
        "message": f"python version is {sys.version.split()[0]} (>=3.11 required)",
        "details": {"version": sys.version.split()[0]},
    }


def _check_tools() -> dict[str, Any]:
    missing = [tool for tool in ["git", "bash", "python3"] if shutil.which(tool) is None]
    return {
        "id": "required_tools",
        "passed": len(missing) == 0,
        "severity": "high",
        "fixable": False,
        "message": "required shell tools check",
        "details": {"missing": missing},
    }


def _check_write(path: Path, check_id: str, severity: str = "medium") -> dict[str, Any]:
    passed = True
    detail = "ok"
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_probe"
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        passed = False
        detail = str(exc)
    return {
        "id": check_id,
        "passed": passed,
        "severity": severity,
        "fixable": True,
        "message": f"write access check for {path}",
        "details": {"path": str(path), "detail": detail},
    }


def _check_codex_home(path: Path) -> dict[str, Any]:
    passed = True
    detail = "ok"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        passed = False
        detail = str(exc)
    return {
        "id": "codex_home_access",
        "passed": passed,
        "severity": "high",
        "fixable": True,
        "message": "CODEX_HOME accessibility",
        "details": {"path": str(path), "detail": detail},
    }


def _check_state_and_managed_paths(state_path: Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if not state_path.exists():
        return (
            {
                "id": "install_state",
                "passed": False,
                "severity": "medium",
                "fixable": False,
                "message": "install state not found",
                "details": {"path": str(state_path)},
            },
            None,
        )
    try:
        state = read_json(state_path)
    except InstallError as exc:
        return (
            {
                "id": "install_state",
                "passed": False,
                "severity": "high",
                "fixable": True,
                "message": exc.message,
                "details": {"path": str(state_path)},
            },
            None,
        )
    if not isinstance(state, dict):
        return (
            {
                "id": "install_state",
                "passed": False,
                "severity": "high",
                "fixable": True,
                "message": "install state must be a JSON object",
                "details": {"path": str(state_path)},
            },
            None,
        )
    managed = normalize_managed_paths(state)
    missing = [item for item in managed if not Path(item).expanduser().exists()]
    return (
        {
            "id": "managed_assets_integrity",
            "passed": len(missing) == 0,
            "severity": "high",
            "fixable": True,
            "message": "managed install paths integrity",
            "details": {"missing_paths": missing, "total_managed_paths": len(managed)},
        },
        state,
    )


def _repair(ctx, state: dict[str, Any] | None) -> list[dict[str, Any]]:
    repairs: list[dict[str, Any]] = []
    for path in [ctx.config_dir, ctx.state_path.parent, ctx.install_root.parent, ctx.bin_dir, ctx.codex_home]:
        path.mkdir(parents=True, exist_ok=True)
        repairs.append({"action": "ensure_dir", "path": str(path)})
    if state is not None:
        managed = normalize_managed_paths(state)
        state["managed_paths"] = managed
        state["last_doctor_at"] = utc_now_iso()
        atomic_write_json(ctx.state_path, state)
        repairs.append({"action": "normalize_state", "path": str(ctx.state_path)})
        install_root = Path(as_str(state.get("managed_paths")[0]) or str(ctx.install_root)).expanduser()
        product_entry = install_root / "scripts" / "op" / "opctl_product.py"
        if product_entry.exists():
            opctl = ctx.bin_dir / "opctl"
            op = ctx.bin_dir / "op"
            launcher = (
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                f"exec python3 \"{product_entry}\" \"$@\"\n"
            )
            opctl.write_text(launcher, encoding="utf-8")
            opctl.chmod(0o755)
            op.write_text(launcher, encoding="utf-8")
            op.chmod(0o755)
            repairs.append({"action": "repair_launchers", "paths": [str(opctl), str(op)]})
    return repairs


def run_doctor(payload: dict[str, Any]) -> dict[str, Any]:
    ctx = resolve_context(payload)
    repair = bool(payload.get("repair"))
    config_resolution = resolve_effective_config(payload, ctx)
    checks = [
        _check_python(),
        _check_tools(),
        _check_write(ctx.config_dir, "config_dir_writable"),
        _check_write(ctx.state_path.parent, "state_dir_writable"),
        _check_write(ctx.bin_dir, "bin_dir_writable"),
        _check_codex_home(ctx.codex_home),
        {
            "id": "config_resolution",
            "passed": len(config_resolution["errors"]) == 0,
            "severity": "high",
            "fixable": False,
            "message": "effective config resolution and validation",
            "details": {
                "sources": config_resolution["sources"],
                "errors": config_resolution["errors"],
                "global_config_path": config_resolution["global_config_path"],
                "project_config_path": config_resolution["project_config_path"],
            },
        },
    ]
    state_check, state_payload = _check_state_and_managed_paths(ctx.state_path)
    checks.append(state_check)

    repairs: list[dict[str, Any]] = []
    if repair:
        repairs = _repair(ctx, state_payload)
        # Recompute post-repair checks for deterministic final report.
        checks = [
            _check_python(),
            _check_tools(),
            _check_write(ctx.config_dir, "config_dir_writable"),
            _check_write(ctx.state_path.parent, "state_dir_writable"),
            _check_write(ctx.bin_dir, "bin_dir_writable"),
            _check_codex_home(ctx.codex_home),
            {
                "id": "config_resolution",
                "passed": len(config_resolution["errors"]) == 0,
                "severity": "high",
                "fixable": False,
                "message": "effective config resolution and validation",
                "details": {
                    "sources": config_resolution["sources"],
                    "errors": config_resolution["errors"],
                    "global_config_path": config_resolution["global_config_path"],
                    "project_config_path": config_resolution["project_config_path"],
                },
            },
        ]
        state_check, _ = _check_state_and_managed_paths(ctx.state_path)
        checks.append(state_check)

    passed = all(bool(item.get("passed")) for item in checks)
    status = "passed" if passed else "blocked"
    errors = []
    if not passed:
        errors = [
            {
                "code": "doctor_blocked",
                "message": "one or more readiness checks failed",
                "stage": "doctor",
            }
        ]
    return standard_response(
        ok=passed,
        status=status,
        summary="Doctor checks passed." if passed else "Doctor checks found blocking issues.",
        data={"checks": checks, "repairs": repairs},
        errors=errors,
        next_action=(
            "Environment is healthy."
            if passed
            else "Run `opctl doctor --repair` for auto-fixable issues or complete manual fixes."
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Lane C diagnostics and optional repair.")
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
    parser.add_argument("--repair", action="store_true")
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
        "codex_home": args.codex_home,
        "bin_dir": args.bin_dir,
        "home_override": args.home_override,
        "profile": args.profile,
        "max_build_cycles": args.max_build_cycles,
        "strict_validation": args.strict_validation,
        "repair": args.repair,
    }
    try:
        out = run_doctor(payload)
        _print(out, args.json_pretty)
        return 0 if out.get("ok") else 1
    except InstallError as exc:
        out = {
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "status": "failed",
            "summary": "Doctor command failed.",
            "errors": [{"code": exc.code, "message": exc.message, "stage": exc.stage}],
            "warnings": [],
            "next_action": "Fix doctor invocation inputs and retry.",
        }
        _print(out, args.json_pretty)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
