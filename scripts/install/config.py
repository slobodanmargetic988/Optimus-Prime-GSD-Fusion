#!/usr/bin/env python3
"""Lane C config/profile resolution and validation."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

from scripts.install.common import InstallContext, InstallError, as_bool, as_str

PROFILES = {
    "quality": {
        "workflow": {
            "max_build_cycles": 50,
            "strict_validation": True,
            "sleep_minutes": 1.0,
            "enable_artifact_fan_in": False,
        },
        "rate_gate": {"max_wait_hours": 2.0},
    },
    "balanced": {
        "workflow": {
            "max_build_cycles": 20,
            "strict_validation": True,
            "sleep_minutes": 1.0,
            "enable_artifact_fan_in": False,
        },
        "rate_gate": {"max_wait_hours": 2.0},
    },
    "budget": {
        "workflow": {
            "max_build_cycles": 10,
            "strict_validation": False,
            "sleep_minutes": 1.0,
            "enable_artifact_fan_in": False,
        },
        "rate_gate": {"max_wait_hours": 1.0},
    },
}

DEFAULT_CONFIG = {
    "profile": "balanced",
    "workflow": {
        "max_build_cycles": 20,
        "strict_validation": True,
        "sleep_minutes": 1.0,
        "enable_artifact_fan_in": False,
    },
    "rate_gate": {"max_wait_hours": 2.0},
    "paths": {},
}


def _xdg_global_config_path(home: Path) -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg).expanduser().resolve() / "optimus-prime" / "config.json"
    return home / ".optimus-prime" / "config" / "config.json"


def _project_config_path(ctx: InstallContext) -> Path | None:
    if ctx.repo_root is None:
        return None
    return ctx.repo_root / ".optimus-prime" / "config.json"


def _read_config(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InstallError(
            "config_error",
            f"invalid JSON in config file {path}: {exc}. Fix JSON syntax and retry.",
            stage="config",
        ) from exc
    except OSError as exc:
        raise InstallError("config_error", f"unable to read config file {path}: {exc}", stage="config") from exc
    if not isinstance(payload, dict):
        raise InstallError("config_error", f"config file must contain a JSON object: {path}", stage="config")
    return payload


def _deep_merge(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _validate_config(config: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    profile = as_str(config.get("profile"))
    if not profile or profile not in PROFILES:
        errors.append(
            {
                "code": "config_validation_error",
                "field": "profile",
                "message": "profile must be one of quality|balanced|budget",
                "fix": "Set profile to quality, balanced, or budget.",
            }
        )
    workflow = config.get("workflow")
    if not isinstance(workflow, dict):
        errors.append(
            {
                "code": "config_validation_error",
                "field": "workflow",
                "message": "workflow must be an object",
                "fix": "Set workflow to object with max_build_cycles and strict_validation.",
            }
        )
    else:
        cycles = workflow.get("max_build_cycles")
        if not isinstance(cycles, int) or cycles <= 0:
            errors.append(
                {
                    "code": "config_validation_error",
                    "field": "workflow.max_build_cycles",
                    "message": "workflow.max_build_cycles must be positive integer",
                    "fix": "Set workflow.max_build_cycles to a positive integer.",
                }
            )
        strict = workflow.get("strict_validation")
        if not isinstance(strict, bool):
            errors.append(
                {
                    "code": "config_validation_error",
                    "field": "workflow.strict_validation",
                    "message": "workflow.strict_validation must be boolean",
                    "fix": "Set workflow.strict_validation to true or false.",
                }
            )
        sleep_minutes = workflow.get("sleep_minutes")
        if not isinstance(sleep_minutes, (int, float)) or float(sleep_minutes) <= 0:
            errors.append(
                {
                    "code": "config_validation_error",
                    "field": "workflow.sleep_minutes",
                    "message": "workflow.sleep_minutes must be a positive number",
                    "fix": "Set workflow.sleep_minutes to a number greater than 0.",
                }
            )
        enable_artifact_fan_in = workflow.get("enable_artifact_fan_in")
        if not isinstance(enable_artifact_fan_in, bool):
            errors.append(
                {
                    "code": "config_validation_error",
                    "field": "workflow.enable_artifact_fan_in",
                    "message": "workflow.enable_artifact_fan_in must be boolean",
                    "fix": "Set workflow.enable_artifact_fan_in to true or false.",
                }
            )
    rate_gate = config.get("rate_gate")
    if not isinstance(rate_gate, dict):
        errors.append(
            {
                "code": "config_validation_error",
                "field": "rate_gate",
                "message": "rate_gate must be an object",
                "fix": "Set rate_gate.max_wait_hours to a positive number.",
            }
        )
    else:
        max_wait = rate_gate.get("max_wait_hours")
        if not isinstance(max_wait, (int, float)) or float(max_wait) <= 0:
            errors.append(
                {
                    "code": "config_validation_error",
                    "field": "rate_gate.max_wait_hours",
                    "message": "rate_gate.max_wait_hours must be a positive number",
                    "fix": "Set rate_gate.max_wait_hours to a number greater than 0.",
                }
            )
    paths = config.get("paths")
    if paths is not None and not isinstance(paths, dict):
        errors.append(
            {
                "code": "config_validation_error",
                "field": "paths",
                "message": "paths must be an object when provided",
                "fix": "Set paths to an object map of string overrides.",
            }
        )
    return errors


def resolve_effective_config(payload: dict[str, Any], ctx: InstallContext) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    effective = copy.deepcopy(DEFAULT_CONFIG)
    profile = as_str(effective.get("profile")) or "balanced"
    effective = _deep_merge(effective, PROFILES[profile])
    sources.append({"source": "defaults", "path": None})

    global_path = _xdg_global_config_path(ctx.home)
    if global_path.exists():
        parsed = _read_config(global_path)
        effective = _deep_merge(effective, parsed)
        sources.append({"source": "global", "path": str(global_path)})

    project_path = _project_config_path(ctx)
    if project_path is not None and project_path.exists():
        parsed = _read_config(project_path)
        effective = _deep_merge(effective, parsed)
        sources.append({"source": "project", "path": str(project_path)})

    cli_config = payload.get("config")
    if isinstance(cli_config, dict):
        effective = _deep_merge(effective, cli_config)
        sources.append({"source": "cli", "path": None})

    cli_profile = as_str(payload.get("profile"))
    if cli_profile:
        effective["profile"] = cli_profile
        sources.append({"source": "cli_profile", "path": None})
    profile = as_str(effective.get("profile")) or "balanced"
    if profile in PROFILES:
        effective = _deep_merge(effective, PROFILES[profile])

    cli_cycles = payload.get("max_build_cycles")
    if cli_cycles is not None:
        workflow = effective.get("workflow") if isinstance(effective.get("workflow"), dict) else {}
        workflow["max_build_cycles"] = int(cli_cycles)
        effective["workflow"] = workflow
        sources.append({"source": "cli_max_build_cycles", "path": None})

    strict_validation_raw = payload.get("strict_validation")
    if strict_validation_raw is not None:
        workflow = effective.get("workflow") if isinstance(effective.get("workflow"), dict) else {}
        workflow["strict_validation"] = as_bool(strict_validation_raw, default=True)
        effective["workflow"] = workflow
        sources.append({"source": "cli_strict_validation", "path": None})

    cli_sleep = payload.get("sleep_minutes")
    if cli_sleep is not None:
        workflow = effective.get("workflow") if isinstance(effective.get("workflow"), dict) else {}
        workflow["sleep_minutes"] = float(cli_sleep)
        effective["workflow"] = workflow
        sources.append({"source": "cli_sleep_minutes", "path": None})

    cli_fan_in = payload.get("enable_artifact_fan_in")
    if cli_fan_in is not None:
        workflow = effective.get("workflow") if isinstance(effective.get("workflow"), dict) else {}
        workflow["enable_artifact_fan_in"] = as_bool(cli_fan_in, default=False)
        effective["workflow"] = workflow
        sources.append({"source": "cli_enable_artifact_fan_in", "path": None})

    errors = _validate_config(effective)
    return {
        "effective_config": effective,
        "sources": sources,
        "errors": errors,
        "global_config_path": str(global_path),
        "project_config_path": str(project_path) if project_path is not None else None,
    }
