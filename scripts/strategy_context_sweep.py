#!/usr/bin/env python3
"""REQ-002 Earth-wide repository discovery manifest surface."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

EmitFn = Callable[[str], None]

TOOL = "strategy-context-sweep"
TOOL_VERSION = "1.0.0"
MANIFEST_SCHEMA_VERSION = "req-002.earth-wide-repository-discovery-manifest.v1"
ARCHIVED_NAME_TOKENS = ("archive", "archives", "archived")
LOG_ROOT = Path("/Users/slobodan/projects/LOGS")
LOG_PATH = LOG_ROOT / "strategy_context_sweep.log"
LOG_BUDGET_CHECK_STAMP = LOG_ROOT / ".log_budget_check.strategy_context_sweep"
LOG_BUDGET_CHECK_INTERVAL_SECONDS = 15 * 60
LOG_BUDGET_MAX_BYTES = 3 * 1024 * 1024 * 1024


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_str(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


def _safe_relpath(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except Exception:
        return path.name


def _canonical_project_id(project_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", project_name.strip().lower()).strip("-")
    if not slug:
        slug = "unknown"
    return f"prj.{slug}"


def _is_archived_name(name: str) -> bool:
    lowered = name.strip().lower()
    if lowered in ARCHIVED_NAME_TOKENS:
        return True
    return any(token in lowered for token in ARCHIVED_NAME_TOKENS)


def _default_owner_username(earth_root: Path) -> str:
    parts = earth_root.resolve().parts
    for idx, value in enumerate(parts):
        if value == "Users" and idx + 1 < len(parts):
            return parts[idx + 1]
    env_user = _as_str(os.environ.get("USER"))
    return env_user or "unknown"


def _owner_root_prefix(owner_username: str) -> Path:
    return (Path("/Users") / owner_username / "projects" / "Earth").resolve()


def _is_owner_path(path: Path, owner_prefix: Path) -> bool:
    try:
        path.resolve().relative_to(owner_prefix)
        return True
    except Exception:
        return False


def _resolve_effective_owner_prefix(earth_root: Path, owner_username: str) -> Path:
    configured = _owner_root_prefix(owner_username)
    try:
        earth_root.resolve().relative_to(configured)
        return configured
    except Exception:
        return earth_root.resolve()


def _is_repo_root(path: Path) -> bool:
    return (path / ".git").exists()


def _source_ref(path: Path, rel_name: str) -> str | None:
    candidate = path / rel_name
    if candidate.exists() and candidate.is_file():
        return rel_name
    return None


def _discovery_fingerprint(projects: list[dict[str, Any]]) -> str:
    encoded = json.dumps(projects, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_earth_repository_discovery_manifest(
    earth_root: Path,
    *,
    owner_username: str | None = None,
    emit: EmitFn | None = None,
) -> dict[str, Any]:
    resolved_earth_root = earth_root.expanduser().resolve()
    owner = _as_str(owner_username) or _default_owner_username(resolved_earth_root)
    owner_prefix = _resolve_effective_owner_prefix(resolved_earth_root, owner)

    if emit:
        emit(
            f"Starting Earth-wide discovery in {resolved_earth_root.as_posix()} with owner "
            f"policy prefix={owner_prefix.as_posix()}."
        )

    projects: list[dict[str, Any]] = []
    excluded_paths: list[dict[str, str]] = []

    for child in sorted(resolved_earth_root.iterdir(), key=lambda item: item.name.lower()):
        relpath = _safe_relpath(child, resolved_earth_root)
        if not child.is_dir():
            excluded_paths.append({"path": relpath, "reason_code": "exclude_non_directory"})
            continue
        if child.name.startswith("."):
            excluded_paths.append({"path": relpath, "reason_code": "exclude_hidden_path"})
            continue
        if _is_archived_name(child.name):
            excluded_paths.append({"path": relpath, "reason_code": "exclude_archived_path"})
            continue
        if not _is_owner_path(child, owner_prefix):
            excluded_paths.append({"path": relpath, "reason_code": "exclude_non_owner_path"})
            continue
        if not _is_repo_root(child):
            excluded_paths.append({"path": relpath, "reason_code": "exclude_non_repository_path"})
            continue

        entry = {
            "project_id": _canonical_project_id(child.name),
            "project_name": child.name,
            "repo_relpath": relpath,
            "repo_root": child.resolve().as_posix(),
            "source_refs": {
                "mission": _source_ref(child, "mission.md"),
                "scope": _source_ref(child, "scope.md"),
            },
        }
        projects.append(entry)

    projects.sort(key=lambda item: item["project_id"])
    excluded_paths.sort(key=lambda item: (item["path"], item["reason_code"]))

    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "policy": {
            "include_rule": "direct_child_repository_roots_only",
            "owner_rule": {
                "owner_username": owner,
                "required_path_prefix": owner_prefix.as_posix(),
            },
            "exclude_rules": [
                {"rule_id": "exclude_non_directory", "description": "Ignore non-directory entries under Earth root."},
                {"rule_id": "exclude_hidden_path", "description": "Ignore hidden directories under Earth root."},
                {"rule_id": "exclude_archived_path", "description": "Ignore archived/archive/archives named directories."},
                {"rule_id": "exclude_non_owner_path", "description": "Ignore directories resolving outside owner Earth root prefix."},
                {"rule_id": "exclude_non_repository_path", "description": "Ignore directories that do not look like repository roots (.git missing)."},
            ],
        },
        "earth_root": resolved_earth_root.as_posix(),
        "projects": projects,
        "excluded_paths": excluded_paths,
        "stats": {
            "project_count": len(projects),
            "excluded_path_count": len(excluded_paths),
        },
        "discovery_fingerprint": _discovery_fingerprint(projects),
    }

    if emit:
        emit(
            f"Discovery completed with {len(projects)} projects and "
            f"{len(excluded_paths)} excluded paths."
        )
    return manifest


def validate_earth_repository_discovery_manifest(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["manifest must be an object"]

    if payload.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        errors.append(f"schema_version must equal {MANIFEST_SCHEMA_VERSION}")

    policy = payload.get("policy")
    if not isinstance(policy, dict):
        errors.append("policy must be an object")
    else:
        if _as_str(policy.get("include_rule")) != "direct_child_repository_roots_only":
            errors.append("policy.include_rule must equal direct_child_repository_roots_only")
        owner_rule = policy.get("owner_rule")
        if not isinstance(owner_rule, dict):
            errors.append("policy.owner_rule must be an object")
        else:
            if not _as_str(owner_rule.get("owner_username")):
                errors.append("policy.owner_rule.owner_username is required")
            if not _as_str(owner_rule.get("required_path_prefix")):
                errors.append("policy.owner_rule.required_path_prefix is required")
        exclude_rules = policy.get("exclude_rules")
        if not isinstance(exclude_rules, list) or not exclude_rules:
            errors.append("policy.exclude_rules must be a non-empty list")

    earth_root = _as_str(payload.get("earth_root"))
    if not earth_root:
        errors.append("earth_root is required")

    projects = payload.get("projects")
    if not isinstance(projects, list):
        errors.append("projects must be a list")
        projects = []
    project_ids: list[str] = []
    for idx, project in enumerate(projects):
        if not isinstance(project, dict):
            errors.append(f"projects[{idx}] must be an object")
            continue
        project_id = _as_str(project.get("project_id"))
        if not re.fullmatch(r"prj\.[a-z0-9][a-z0-9-]*", project_id):
            errors.append(f"projects[{idx}].project_id must match prj.<slug>")
        project_ids.append(project_id)
        if not _as_str(project.get("project_name")):
            errors.append(f"projects[{idx}].project_name is required")
        if not _as_str(project.get("repo_relpath")):
            errors.append(f"projects[{idx}].repo_relpath is required")
        if not _as_str(project.get("repo_root")):
            errors.append(f"projects[{idx}].repo_root is required")
        source_refs = project.get("source_refs")
        if not isinstance(source_refs, dict):
            errors.append(f"projects[{idx}].source_refs must be an object")
        else:
            for key in ("mission", "scope"):
                value = source_refs.get(key)
                if value is not None and not isinstance(value, str):
                    errors.append(f"projects[{idx}].source_refs.{key} must be string|null")

    if project_ids != sorted(project_ids):
        errors.append("projects must be sorted by project_id for rerun stability")
    if len(set(project_ids)) != len(project_ids):
        errors.append("project_id values must be unique")

    excluded = payload.get("excluded_paths")
    if not isinstance(excluded, list):
        errors.append("excluded_paths must be a list")
    else:
        allowed_reason_codes = {
            "exclude_non_directory",
            "exclude_hidden_path",
            "exclude_archived_path",
            "exclude_non_owner_path",
            "exclude_non_repository_path",
        }
        for idx, row in enumerate(excluded):
            if not isinstance(row, dict):
                errors.append(f"excluded_paths[{idx}] must be an object")
                continue
            path = _as_str(row.get("path"))
            reason_code = _as_str(row.get("reason_code"))
            if not path:
                errors.append(f"excluded_paths[{idx}].path is required")
            if reason_code not in allowed_reason_codes:
                errors.append(f"excluded_paths[{idx}].reason_code is invalid")

    stats = payload.get("stats")
    if not isinstance(stats, dict):
        errors.append("stats must be an object")
    else:
        if not isinstance(stats.get("project_count"), int):
            errors.append("stats.project_count must be an integer")
        if not isinstance(stats.get("excluded_path_count"), int):
            errors.append("stats.excluded_path_count must be an integer")

    fingerprint = _as_str(payload.get("discovery_fingerprint"))
    if not re.fullmatch(r"[a-f0-9]{64}", fingerprint):
        errors.append("discovery_fingerprint must be a sha256 hex digest")
    elif isinstance(projects, list):
        expected_fingerprint = _discovery_fingerprint([row for row in projects if isinstance(row, dict)])
        if fingerprint != expected_fingerprint:
            errors.append("discovery_fingerprint must match canonical projects payload")

    return errors


def _json_dumps(payload: dict[str, Any], pretty: bool) -> str:
    if pretty:
        return json.dumps(payload, indent=2, sort_keys=False) + "\n"
    return json.dumps(payload, separators=(",", ":"), sort_keys=False) + "\n"


def _enforce_log_budget(log_root: Path) -> None:
    log_root.mkdir(parents=True, exist_ok=True)
    now_epoch = time.time()
    if LOG_BUDGET_CHECK_STAMP.exists():
        last_checked = LOG_BUDGET_CHECK_STAMP.stat().st_mtime
        if (now_epoch - last_checked) < LOG_BUDGET_CHECK_INTERVAL_SECONDS:
            return

    log_files = [path for path in log_root.rglob("*") if path.is_file() and path != LOG_BUDGET_CHECK_STAMP]
    total_bytes = sum(path.stat().st_size for path in log_files)
    if total_bytes > LOG_BUDGET_MAX_BYTES:
        for path in sorted(log_files, key=lambda item: item.stat().st_mtime):
            original_size = path.stat().st_size
            if original_size <= 0:
                continue
            path.write_text("", encoding="utf-8")
            total_bytes -= original_size
            if total_bytes <= LOG_BUDGET_MAX_BYTES:
                break
    LOG_BUDGET_CHECK_STAMP.touch()


def _make_cli_emit(log_path: Path) -> EmitFn:
    def _emit(message: str) -> None:
        stamp = utc_now_iso()
        line = f"[{TOOL} {stamp}] {message}"
        print(line, file=sys.stderr, flush=True)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    return _emit


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate REQ-002 Earth-wide repository discovery manifest.")
    parser.add_argument("--earth-root", required=True, help="Earth ecosystem root path.")
    parser.add_argument("--owner-username", default="", help="Owner username for non-owner path policy.")
    parser.add_argument("--output-json", default="", help="Optional output file path for manifest.")
    parser.add_argument("--json-pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _enforce_log_budget(LOG_ROOT)
    emit = _make_cli_emit(LOG_PATH)

    manifest = build_earth_repository_discovery_manifest(
        Path(args.earth_root),
        owner_username=_as_str(args.owner_username) or None,
        emit=emit,
    )
    errors = validate_earth_repository_discovery_manifest(manifest)
    if errors:
        error_payload = {
            "ok": False,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "reason_code": "contract_validation_failed",
            "errors": errors,
        }
        sys.stdout.write(_json_dumps(error_payload, args.json_pretty))
        return 1

    if _as_str(args.output_json):
        output_path = Path(args.output_json).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(_json_dumps(manifest, True), encoding="utf-8")
        emit(f"Manifest written to {output_path.as_posix()}.")

    sys.stdout.write(_json_dumps(manifest, args.json_pretty))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
