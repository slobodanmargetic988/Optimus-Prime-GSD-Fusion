#!/usr/bin/env python3
"""REQ-002 and REQ-010 strategy context contract surfaces."""

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
CHANGE_DETECTION_SCHEMA_VERSION = "req-010.change-detection-since-previous-strategy-revision.v1"
REQ010_SECTION_KEYS = ("mission_scope", "runtime_data", "ecosystem_signals")
REQ010_CHANGE_TYPES = ("added", "removed", "updated")
ARCHIVED_NAME_TOKENS = ("archive", "archives", "archived")
EXCLUDE_REASON_CODES = (
    "exclude_non_directory",
    "exclude_hidden_path",
    "exclude_archived_path",
    "exclude_non_owner_path",
    "exclude_non_repository_path",
)
SOURCE_REASON_CODES = (
    "source_present",
    "missing_mission_doc",
    "missing_scope_doc",
    "stale_source_artifact_detected",
)
OPEN_RISK_REASON_CODES = (
    "missing_mission_doc",
    "missing_scope_doc",
    "stale_source_artifact_detected",
    "missing_peer_project_doc",
)
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


def _source_artifact_status(path: Path, rel_name: str) -> tuple[str | None, str]:
    candidate = path / rel_name
    if candidate.exists() and candidate.is_file():
        return rel_name, "source_present"
    if candidate.is_symlink():
        return None, "stale_source_artifact_detected"
    if rel_name == "mission.md":
        return None, "missing_mission_doc"
    if rel_name == "scope.md":
        return None, "missing_scope_doc"
    return None, "source_present"


def _source_evidence_ref(repo_relpath: str, rel_name: str, reason_code: str) -> str:
    if reason_code == "source_present":
        return f"{repo_relpath}/{rel_name}"
    if reason_code == "stale_source_artifact_detected":
        return f"stale:{repo_relpath}/{rel_name}#stale_source_artifact_detected"
    return f"missing:{repo_relpath}/{rel_name}#{reason_code}"


def _discovery_fingerprint(projects: list[dict[str, Any]]) -> str:
    encoded = json.dumps(projects, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sorted_unique_strings(values: list[str]) -> list[str]:
    return sorted({value for value in values if _as_str(value)})


def _build_evidence_refs(
    projects: list[dict[str, Any]],
    excluded_paths: list[dict[str, str]],
    cross_project_context: list[dict[str, Any]],
) -> list[str]:
    refs: list[str] = []
    for project in projects:
        repo_relpath = _as_str(project.get("repo_relpath"))
        if repo_relpath:
            refs.append(f"{repo_relpath}/.git")
        source_refs = project.get("source_refs") if isinstance(project.get("source_refs"), dict) else {}
        for key in ("mission", "scope"):
            source_ref = _as_str(source_refs.get(key))
            if repo_relpath and source_ref:
                refs.append(f"{repo_relpath}/{source_ref}")

    for row in excluded_paths:
        path = _as_str(row.get("path"))
        reason_code = _as_str(row.get("reason_code"))
        if path and reason_code:
            refs.append(f"excluded:{path}#{reason_code}")

    for row in cross_project_context:
        row_refs = row.get("evidence_refs")
        if isinstance(row_refs, list):
            refs.extend(_as_str(ref) for ref in row_refs)

    return _sorted_unique_strings(refs)


def _build_cross_project_context(projects: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    context_rows: list[dict[str, Any]] = []
    partial_project_ids: list[str] = []
    for project in projects:
        project_id = _as_str(project.get("project_id"))
        project_name = _as_str(project.get("project_name"))
        repo_relpath = _as_str(project.get("repo_relpath"))
        source_refs = project.get("source_refs") if isinstance(project.get("source_refs"), dict) else {}
        mission_source = _as_str(source_refs.get("mission"))
        scope_source = _as_str(source_refs.get("scope"))
        mission_ref = f"{repo_relpath}/{mission_source}" if repo_relpath and mission_source else None
        scope_ref = f"{repo_relpath}/{scope_source}" if repo_relpath and scope_source else None
        status = "complete" if mission_ref and scope_ref else "partial"
        reason_codes = [
            _as_str((project.get("source_artifact_reason_codes") or {}).get("mission")),
            _as_str((project.get("source_artifact_reason_codes") or {}).get("scope")),
        ]
        reason_codes = _sorted_unique_strings([code for code in reason_codes if code and code != "source_present"])
        if status == "partial":
            partial_project_ids.append(project_id)
        row_evidence_refs = _sorted_unique_strings(
            [f"{repo_relpath}/.git" if repo_relpath else "", mission_ref or "", scope_ref or ""]
            + [
                _source_evidence_ref(repo_relpath, "mission.md", _as_str((project.get("source_artifact_reason_codes") or {}).get("mission")))
                if repo_relpath
                else "",
                _source_evidence_ref(repo_relpath, "scope.md", _as_str((project.get("source_artifact_reason_codes") or {}).get("scope")))
                if repo_relpath
                else "",
            ]
        )
        context_rows.append(
            {
                "project_id": project_id,
                "project_name": project_name,
                "mission_ref": mission_ref,
                "scope_ref": scope_ref,
                "context_status": status,
                "reason_codes": reason_codes,
                "evidence_refs": row_evidence_refs,
            }
        )
    context_rows.sort(key=lambda row: row["project_id"])
    partial_project_ids.sort()
    return context_rows, partial_project_ids


def _build_broad_sweep_inputs(
    *,
    earth_root: Path,
    owner_username: str,
    owner_prefix: Path,
    direct_child_count: int,
    projects: list[dict[str, Any]],
    excluded_paths: list[dict[str, str]],
    partial_project_ids: list[str],
) -> dict[str, Any]:
    reason_counts: dict[str, int] = {code: 0 for code in EXCLUDE_REASON_CODES}
    for row in excluded_paths:
        reason_code = _as_str(row.get("reason_code"))
        if reason_code in reason_counts:
            reason_counts[reason_code] += 1
    return {
        "earth_root": earth_root.as_posix(),
        "owner_username": owner_username,
        "owner_prefix": owner_prefix.as_posix(),
        "include_rule": "direct_child_repository_roots_only",
        "direct_child_count": direct_child_count,
        "discovered_project_ids": [project["project_id"] for project in projects],
        "source_ref_coverage": {
            "project_count": len(projects),
            "complete_project_count": len(projects) - len(partial_project_ids),
            "partial_project_count": len(partial_project_ids),
            "mission_ref_count": sum(
                1 for project in projects if _as_str((project.get("source_refs") or {}).get("mission"))
            ),
            "scope_ref_count": sum(
                1 for project in projects if _as_str((project.get("source_refs") or {}).get("scope"))
            ),
        },
        "excluded_reason_counts": {code: reason_counts[code] for code in EXCLUDE_REASON_CODES},
    }


def _build_recommendation_and_open_risks(
    *,
    projects: list[dict[str, Any]],
    cross_project_context: list[dict[str, Any]],
    partial_project_ids: list[str],
    evidence_refs: list[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    project_ids = [project["project_id"] for project in projects]
    context_by_project_id = {row["project_id"]: row for row in cross_project_context}
    open_risks: list[dict[str, Any]] = []
    obligations: list[dict[str, Any]] = []

    for project_id in partial_project_ids:
        row = context_by_project_id[project_id]
        row_reason_codes = _sorted_unique_strings([_as_str(code) for code in row.get("reason_codes", [])])
        missing_refs: list[str] = []
        if row.get("mission_ref") is None:
            missing_refs.append("mission.md")
        if row.get("scope_ref") is None:
            missing_refs.append("scope.md")
        missing_reason_codes = [code for code in row_reason_codes if code in {"missing_mission_doc", "missing_scope_doc"}]
        if not missing_reason_codes and missing_refs:
            missing_reason_codes = _sorted_unique_strings(
                [
                    "missing_mission_doc" if ref == "mission.md" else "missing_scope_doc"
                    for ref in missing_refs
                ]
            )
        stale_detected = "stale_source_artifact_detected" in row_reason_codes
        summary_bits: list[str] = []
        if missing_refs:
            summary_bits.append(f"missing required source refs: {', '.join(missing_refs)}")
        if stale_detected:
            summary_bits.append("contains stale source artifacts")
        summary_text = "; ".join(summary_bits) if summary_bits else "has unresolved source-document issues"
        reason_code = "stale_source_artifact_detected" if stale_detected else ",".join(missing_reason_codes)
        open_risks.append(
            {
                "risk_id": f"risk.missing-source-refs.{project_id}",
                "project_id": project_id,
                "summary": f"{project_id} {summary_text}.",
                "reason_code": reason_code,
                "evidence_refs": row["evidence_refs"],
                "missing_source_refs": missing_refs if missing_refs else [],
            }
        )

    if len(project_ids) >= 2:
        mission_scope_evidence = _sorted_unique_strings(
            [ref for row in cross_project_context for ref in [row.get("mission_ref"), row.get("scope_ref")] if ref]
        )
        if partial_project_ids:
            open_risks.append(
                {
                    "risk_id": "risk.cross-project-obligation-evidence-gap",
                    "project_ids": partial_project_ids,
                    "reason_code": "missing_peer_project_doc",
                    "summary": (
                        "Cross-project obligations are deferred because one or more projects lack mission/scope evidence."
                    ),
                    "evidence_refs": _sorted_unique_strings(
                        [ref for project_id in partial_project_ids for ref in context_by_project_id[project_id]["evidence_refs"]]
                    ),
                }
            )
        elif mission_scope_evidence:
            obligations.append(
                {
                    "obligation_id": "obl.cross-project.mission-scope-coverage",
                    "title": "Maintain complete mission/scope evidence coverage across discovered Earth repositories.",
                    "project_ids": project_ids,
                    "evidence_refs": mission_scope_evidence,
                }
            )
        else:
            open_risks.append(
                {
                    "risk_id": "risk.cross-project-obligation-evidence-gap",
                    "project_ids": project_ids,
                    "reason_code": "missing_peer_project_doc",
                    "summary": "Cross-project obligation inference skipped because mission/scope evidence refs are unavailable.",
                    "evidence_refs": _sorted_unique_strings(
                        [ref for row in cross_project_context for ref in row["evidence_refs"]]
                    ),
                }
            )

    if not projects:
        decision = "blocked_no_projects_discovered"
        rationale = "No repository roots were discovered under Earth root, so cross-project planning cannot begin."
        action_items = ["Verify Earth root and owner policy inputs, then rerun discovery."]
    elif partial_project_ids:
        decision = "needs_evidence_backfill"
        rationale = (
            "At least one discovered project has partial mission/scope evidence, so cross-project obligations stay open risks."
        )
        action_items = ["Backfill missing mission/scope files for partial projects and rerun strategy context sweep."]
    else:
        decision = "ready_for_cross_project_planning"
        rationale = (
            "All discovered projects provide mission/scope evidence; recommendation can include evidence-backed obligations."
        )
        action_items = ["Proceed with cross-project planning using the manifest evidence refs and obligations."]

    recommendation_evidence_refs = _sorted_unique_strings(
        evidence_refs
        + [ref for row in cross_project_context for ref in row.get("evidence_refs", [])]
        + [ref for row in obligations for ref in row.get("evidence_refs", [])]
        + [ref for row in open_risks for ref in row.get("evidence_refs", [])]
    )

    recommendation = {
        "decision": decision,
        "rationale": rationale,
        "context_project_ids": project_ids,
        "evidence_refs": recommendation_evidence_refs,
        "action_items": action_items,
        "proposed_cross_project_obligations": obligations,
    }

    open_risks.sort(key=lambda row: row["risk_id"])
    return recommendation, open_risks


def build_earth_repository_discovery_context_bundle(manifest: dict[str, Any]) -> dict[str, Any]:
    projects = manifest.get("projects") if isinstance(manifest.get("projects"), list) else []
    cross_project_context = (
        manifest.get("cross_project_context") if isinstance(manifest.get("cross_project_context"), list) else []
    )
    open_risks = manifest.get("open_risks") if isinstance(manifest.get("open_risks"), list) else []
    return {
        "schema_version": "req-002.earth-wide-repository-discovery-context-bundle.v1",
        "manifest_schema_version": _as_str(manifest.get("schema_version")),
        "earth_root": _as_str(manifest.get("earth_root")),
        "discovery_fingerprint": _as_str(manifest.get("discovery_fingerprint")),
        "project_ids": _sorted_unique_strings([_as_str(row.get("project_id")) for row in projects if isinstance(row, dict)]),
        "context_project_ids": _sorted_unique_strings(
            [_as_str(row.get("project_id")) for row in cross_project_context if isinstance(row, dict)]
        ),
        "open_risk_reason_codes": _sorted_unique_strings(
            [_as_str(row.get("reason_code")) for row in open_risks if isinstance(row, dict)]
        ),
        "evidence_refs": _sorted_unique_strings(
            [_as_str(ref) for ref in manifest.get("evidence_refs", []) if isinstance(ref, str)]
        ),
    }


def serialize_earth_repository_discovery_context_bundle(bundle: dict[str, Any]) -> str:
    return json.dumps(bundle, sort_keys=True, separators=(",", ":"))


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

    children = sorted(resolved_earth_root.iterdir(), key=lambda item: item.name.lower())
    for child in children:
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
            "source_artifact_reason_codes": {
                "mission": _source_artifact_status(child, "mission.md")[1],
                "scope": _source_artifact_status(child, "scope.md")[1],
            },
        }
        projects.append(entry)

    projects.sort(key=lambda item: item["project_id"])
    excluded_paths.sort(key=lambda item: (item["path"], item["reason_code"]))
    cross_project_context, partial_project_ids = _build_cross_project_context(projects)
    evidence_refs = _build_evidence_refs(projects, excluded_paths, cross_project_context)
    recommendation, open_risks = _build_recommendation_and_open_risks(
        projects=projects,
        cross_project_context=cross_project_context,
        partial_project_ids=partial_project_ids,
        evidence_refs=evidence_refs,
    )
    broad_sweep_inputs = _build_broad_sweep_inputs(
        earth_root=resolved_earth_root,
        owner_username=owner,
        owner_prefix=owner_prefix,
        direct_child_count=len(children),
        projects=projects,
        excluded_paths=excluded_paths,
        partial_project_ids=partial_project_ids,
    )

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
        "broad_sweep_inputs": broad_sweep_inputs,
        "earth_root": resolved_earth_root.as_posix(),
        "projects": projects,
        "excluded_paths": excluded_paths,
        "evidence_refs": evidence_refs,
        "cross_project_context": cross_project_context,
        "recommendation": recommendation,
        "open_risks": open_risks,
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

    broad_sweep_inputs = payload.get("broad_sweep_inputs")
    if not isinstance(broad_sweep_inputs, dict):
        errors.append("broad_sweep_inputs must be an object")
    else:
        if not isinstance(broad_sweep_inputs.get("direct_child_count"), int):
            errors.append("broad_sweep_inputs.direct_child_count must be an integer")
        discovered_project_ids = broad_sweep_inputs.get("discovered_project_ids")
        if not isinstance(discovered_project_ids, list):
            errors.append("broad_sweep_inputs.discovered_project_ids must be a list")
        else:
            for idx, value in enumerate(discovered_project_ids):
                if not re.fullmatch(r"prj\.[a-z0-9][a-z0-9-]*", _as_str(value)):
                    errors.append(f"broad_sweep_inputs.discovered_project_ids[{idx}] must match prj.<slug>")
        source_ref_coverage = broad_sweep_inputs.get("source_ref_coverage")
        if not isinstance(source_ref_coverage, dict):
            errors.append("broad_sweep_inputs.source_ref_coverage must be an object")
        else:
            for key in (
                "project_count",
                "complete_project_count",
                "partial_project_count",
                "mission_ref_count",
                "scope_ref_count",
            ):
                if not isinstance(source_ref_coverage.get(key), int):
                    errors.append(f"broad_sweep_inputs.source_ref_coverage.{key} must be an integer")
        excluded_reason_counts = broad_sweep_inputs.get("excluded_reason_counts")
        if not isinstance(excluded_reason_counts, dict):
            errors.append("broad_sweep_inputs.excluded_reason_counts must be an object")
        else:
            for reason_code in EXCLUDE_REASON_CODES:
                if not isinstance(excluded_reason_counts.get(reason_code), int):
                    errors.append(f"broad_sweep_inputs.excluded_reason_counts.{reason_code} must be an integer")

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
        for idx, row in enumerate(excluded):
            if not isinstance(row, dict):
                errors.append(f"excluded_paths[{idx}] must be an object")
                continue
            path = _as_str(row.get("path"))
            reason_code = _as_str(row.get("reason_code"))
            if not path:
                errors.append(f"excluded_paths[{idx}].path is required")
            if reason_code not in EXCLUDE_REASON_CODES:
                errors.append(f"excluded_paths[{idx}].reason_code is invalid")

    evidence_refs = payload.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        errors.append("evidence_refs must be a non-empty list")
        evidence_refs = []
    else:
        for idx, ref in enumerate(evidence_refs):
            if not _as_str(ref):
                errors.append(f"evidence_refs[{idx}] must be a non-empty string")
        if evidence_refs != sorted(evidence_refs):
            errors.append("evidence_refs must be sorted for rerun stability")
        if len(set(evidence_refs)) != len(evidence_refs):
            errors.append("evidence_refs must be unique")

    cross_project_context = payload.get("cross_project_context")
    partial_project_ids: set[str] = set()
    if not isinstance(cross_project_context, list):
        errors.append("cross_project_context must be a list")
        cross_project_context = []
    else:
        context_project_ids: list[str] = []
        for idx, row in enumerate(cross_project_context):
            if not isinstance(row, dict):
                errors.append(f"cross_project_context[{idx}] must be an object")
                continue
            project_id = _as_str(row.get("project_id"))
            if project_id not in project_ids:
                errors.append(f"cross_project_context[{idx}].project_id must reference discovered projects")
            context_project_ids.append(project_id)
            context_status = _as_str(row.get("context_status"))
            if context_status not in {"complete", "partial"}:
                errors.append(f"cross_project_context[{idx}].context_status must be complete|partial")
            if context_status == "partial":
                partial_project_ids.add(project_id)
            for key in ("mission_ref", "scope_ref"):
                value = row.get(key)
                if value is not None and not isinstance(value, str):
                    errors.append(f"cross_project_context[{idx}].{key} must be string|null")
            row_evidence_refs = row.get("evidence_refs")
            if not isinstance(row_evidence_refs, list) or not row_evidence_refs:
                errors.append(f"cross_project_context[{idx}].evidence_refs must be a non-empty list")
            else:
                for ref_idx, ref in enumerate(row_evidence_refs):
                    if not _as_str(ref):
                        errors.append(f"cross_project_context[{idx}].evidence_refs[{ref_idx}] must be non-empty string")
                    if isinstance(evidence_refs, list) and ref not in evidence_refs:
                        errors.append(
                            f"cross_project_context[{idx}].evidence_refs[{ref_idx}] must exist in top-level evidence_refs"
                        )
            row_reason_codes = row.get("reason_codes")
            if row_reason_codes is not None:
                if not isinstance(row_reason_codes, list):
                    errors.append(f"cross_project_context[{idx}].reason_codes must be a list when set")
                else:
                    for code_idx, code in enumerate(row_reason_codes):
                        if _as_str(code) not in SOURCE_REASON_CODES:
                            errors.append(
                                f"cross_project_context[{idx}].reason_codes[{code_idx}] "
                                f"must be one of {', '.join(SOURCE_REASON_CODES)}"
                            )
        if len(context_project_ids) != len(set(context_project_ids)):
            errors.append("cross_project_context.project_id values must be unique")
        if context_project_ids != sorted(context_project_ids):
            errors.append("cross_project_context must be sorted by project_id")
        if sorted(context_project_ids) != sorted(project_ids):
            errors.append("cross_project_context must provide one row per discovered project")

    recommendation = payload.get("recommendation")
    obligations: list[dict[str, Any]] = []
    if not isinstance(recommendation, dict):
        errors.append("recommendation must be an object")
    else:
        if not _as_str(recommendation.get("decision")):
            errors.append("recommendation.decision is required")
        if not _as_str(recommendation.get("rationale")):
            errors.append("recommendation.rationale is required")
        context_project_ids = recommendation.get("context_project_ids")
        if not isinstance(context_project_ids, list):
            errors.append("recommendation.context_project_ids must be a list")
        else:
            if context_project_ids != project_ids:
                errors.append("recommendation.context_project_ids must equal discovered project_ids")
        rec_evidence_refs = recommendation.get("evidence_refs")
        if not isinstance(rec_evidence_refs, list) or not rec_evidence_refs:
            errors.append("recommendation.evidence_refs must be a non-empty list")
        else:
            for idx, ref in enumerate(rec_evidence_refs):
                if not _as_str(ref):
                    errors.append(f"recommendation.evidence_refs[{idx}] must be a non-empty string")
                if isinstance(evidence_refs, list) and ref not in evidence_refs:
                    errors.append(f"recommendation.evidence_refs[{idx}] must exist in top-level evidence_refs")
        action_items = recommendation.get("action_items")
        if not isinstance(action_items, list) or not action_items:
            errors.append("recommendation.action_items must be a non-empty list")
        else:
            for idx, item in enumerate(action_items):
                if not _as_str(item):
                    errors.append(f"recommendation.action_items[{idx}] must be a non-empty string")

        obligations_raw = recommendation.get("proposed_cross_project_obligations")
        if not isinstance(obligations_raw, list):
            errors.append("recommendation.proposed_cross_project_obligations must be a list")
        else:
            for idx, row in enumerate(obligations_raw):
                if not isinstance(row, dict):
                    errors.append(f"recommendation.proposed_cross_project_obligations[{idx}] must be an object")
                    continue
                obligation_id = _as_str(row.get("obligation_id"))
                if not obligation_id:
                    errors.append(f"recommendation.proposed_cross_project_obligations[{idx}].obligation_id is required")
                if not _as_str(row.get("title")):
                    errors.append(f"recommendation.proposed_cross_project_obligations[{idx}].title is required")
                related_project_ids = row.get("project_ids")
                if not isinstance(related_project_ids, list) or not related_project_ids:
                    errors.append(
                        f"recommendation.proposed_cross_project_obligations[{idx}].project_ids must be non-empty list"
                    )
                else:
                    for pid_idx, project_id in enumerate(related_project_ids):
                        if _as_str(project_id) not in project_ids:
                            errors.append(
                                f"recommendation.proposed_cross_project_obligations[{idx}].project_ids[{pid_idx}] "
                                "must reference discovered projects"
                            )
                obligation_evidence_refs = row.get("evidence_refs")
                if not isinstance(obligation_evidence_refs, list) or not obligation_evidence_refs:
                    errors.append(
                        f"recommendation.proposed_cross_project_obligations[{idx}].evidence_refs must be non-empty list"
                    )
                else:
                    for ref_idx, ref in enumerate(obligation_evidence_refs):
                        if not _as_str(ref):
                            errors.append(
                                f"recommendation.proposed_cross_project_obligations[{idx}].evidence_refs[{ref_idx}] "
                                "must be a non-empty string"
                            )
                        if isinstance(evidence_refs, list) and ref not in evidence_refs:
                            errors.append(
                                f"recommendation.proposed_cross_project_obligations[{idx}].evidence_refs[{ref_idx}] "
                                "must exist in top-level evidence_refs"
                            )
                obligations.append(row)

    open_risks = payload.get("open_risks")
    if not isinstance(open_risks, list):
        errors.append("open_risks must be a list")
        open_risks = []
    else:
        for idx, row in enumerate(open_risks):
            if not isinstance(row, dict):
                errors.append(f"open_risks[{idx}] must be an object")
                continue
            if not _as_str(row.get("risk_id")):
                errors.append(f"open_risks[{idx}].risk_id is required")
            if not _as_str(row.get("summary")):
                errors.append(f"open_risks[{idx}].summary is required")
            project_id = row.get("project_id")
            if project_id is not None and _as_str(project_id) not in project_ids:
                errors.append(f"open_risks[{idx}].project_id must reference discovered projects when set")
            risk_project_ids = row.get("project_ids")
            if risk_project_ids is not None:
                if not isinstance(risk_project_ids, list):
                    errors.append(f"open_risks[{idx}].project_ids must be a list when set")
                else:
                    for pid_idx, risk_project_id in enumerate(risk_project_ids):
                        if _as_str(risk_project_id) not in project_ids:
                            errors.append(
                                f"open_risks[{idx}].project_ids[{pid_idx}] must reference discovered projects"
                            )
            row_evidence_refs = row.get("evidence_refs")
            if not isinstance(row_evidence_refs, list) or not row_evidence_refs:
                errors.append(f"open_risks[{idx}].evidence_refs must be a non-empty list")
            else:
                for ref_idx, ref in enumerate(row_evidence_refs):
                    if not _as_str(ref):
                        errors.append(f"open_risks[{idx}].evidence_refs[{ref_idx}] must be a non-empty string")
                    if isinstance(evidence_refs, list) and ref not in evidence_refs:
                        errors.append(
                            f"open_risks[{idx}].evidence_refs[{ref_idx}] must exist in top-level evidence_refs"
                        )
            reason_code = _as_str(row.get("reason_code"))
            if not reason_code:
                errors.append(f"open_risks[{idx}].reason_code is required")
            elif reason_code not in OPEN_RISK_REASON_CODES and "," not in reason_code:
                errors.append(
                    f"open_risks[{idx}].reason_code must be one of {', '.join(OPEN_RISK_REASON_CODES)} "
                    "or a comma-delimited subset for missing source docs"
                )

    if partial_project_ids and obligations:
        errors.append(
            "recommendation.proposed_cross_project_obligations must be empty when partial cross_project_context exists"
        )
    if partial_project_ids and not open_risks:
        errors.append("open_risks must capture unresolved cross-project ideas when evidence is partial")

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


_MISSING = object()


def _canonical_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonical_json_value(val) for key, val in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, list):
        return [_canonical_json_value(item) for item in value]
    return value


def _join_pointer(base: str, segment: str) -> str:
    escaped = segment.replace("~", "~0").replace("/", "~1")
    if base == "/":
        return f"/{escaped}"
    return f"{base}/{escaped}"


def _req010_change_id(
    section_key: str,
    path: str,
    change_type: str,
    previous_value: Any,
    current_value: Any,
) -> str:
    payload = {
        "section_key": section_key,
        "path": path,
        "change_type": change_type,
        "previous_value": _canonical_json_value(previous_value),
        "current_value": _canonical_json_value(current_value),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()[:16]
    return f"chg.{section_key}.{digest}"


def _collect_req010_section_changes(section_key: str, previous_value: Any, current_value: Any) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []

    def _add_change(path: str, change_type: str, before: Any, after: Any) -> None:
        changes.append(
            {
                "change_id": _req010_change_id(section_key, path, change_type, before, after),
                "section_key": section_key,
                "path": path,
                "change_type": change_type,
                "previous_value": _canonical_json_value(before),
                "current_value": _canonical_json_value(after),
            }
        )

    def _walk(before: Any, after: Any, path: str) -> None:
        if before is _MISSING:
            _add_change(path, "added", None, after)
            return
        if after is _MISSING:
            _add_change(path, "removed", before, None)
            return
        if isinstance(before, dict) and isinstance(after, dict):
            keyset = sorted(set(before.keys()) | set(after.keys()))
            for key in keyset:
                _walk(before.get(key, _MISSING), after.get(key, _MISSING), _join_pointer(path, str(key)))
            return
        if isinstance(before, list) and isinstance(after, list):
            for idx in range(max(len(before), len(after))):
                before_item = before[idx] if idx < len(before) else _MISSING
                after_item = after[idx] if idx < len(after) else _MISSING
                _walk(before_item, after_item, _join_pointer(path, str(idx)))
            return
        if before != after:
            _add_change(path, "updated", before, after)

    _walk(_canonical_json_value(previous_value), _canonical_json_value(current_value), "/")
    changes.sort(key=lambda row: row["change_id"])
    return changes


def _normalize_req010_anchors(raw_anchors: Any) -> list[str]:
    if not isinstance(raw_anchors, list):
        return []
    anchor_set = {_as_str(anchor) for anchor in raw_anchors if _as_str(anchor) in REQ010_SECTION_KEYS}
    return [section_key for section_key in REQ010_SECTION_KEYS if section_key in anchor_set]


def _recommendation_delta_type(previous_row: dict[str, Any] | None, summary: str, anchors: list[str]) -> str:
    if previous_row is None:
        return "new"
    previous_summary = _as_str(previous_row.get("summary") or previous_row.get("title"))
    previous_anchors = _normalize_req010_anchors(previous_row.get("anchors"))
    if previous_summary != summary or previous_anchors != anchors:
        return "updated"
    return "retained"


def _build_req010_recommendation_deltas(
    *,
    previous_revision: dict[str, Any],
    current_revision: dict[str, Any],
    section_change_ids: dict[str, list[str]],
    all_change_ids: list[str],
) -> list[dict[str, Any]]:
    current_recommendations = (
        current_revision.get("recommendations") if isinstance(current_revision.get("recommendations"), list) else []
    )
    previous_recommendations = (
        previous_revision.get("recommendations") if isinstance(previous_revision.get("recommendations"), list) else []
    )
    previous_by_id: dict[str, dict[str, Any]] = {}
    for row in previous_recommendations:
        if not isinstance(row, dict):
            continue
        recommendation_id = _as_str(row.get("recommendation_id") or row.get("id"))
        if recommendation_id and recommendation_id not in previous_by_id:
            previous_by_id[recommendation_id] = row

    deltas: list[dict[str, Any]] = []
    for row in current_recommendations:
        if not isinstance(row, dict):
            continue
        recommendation_id = _as_str(row.get("recommendation_id") or row.get("id"))
        if not recommendation_id:
            continue
        anchors = _normalize_req010_anchors(row.get("anchors"))
        if not anchors:
            continue
        change_ids = _sorted_unique_strings(
            [
                change_id
                for anchor in anchors
                for change_id in section_change_ids.get(anchor, [])
            ]
        )
        if not change_ids:
            continue
        summary = _as_str(row.get("summary") or row.get("title")) or f"Adjust {recommendation_id} to current revision."
        deltas.append(
            {
                "recommendation_id": recommendation_id,
                "summary": summary,
                "anchors": anchors,
                "change_ids": change_ids,
                "delta_type": _recommendation_delta_type(previous_by_id.get(recommendation_id), summary, anchors),
            }
        )

    if not deltas and all_change_ids:
        changed_anchors = [section_key for section_key in REQ010_SECTION_KEYS if section_change_ids.get(section_key)]
        deltas.append(
            {
                "recommendation_id": "rec.strategy-revision-delta",
                "summary": "Align strategy recommendations with detected revision changes.",
                "anchors": changed_anchors,
                "change_ids": all_change_ids,
                "delta_type": "derived",
            }
        )

    deltas.sort(key=lambda row: row["recommendation_id"])
    return deltas


def build_change_detection_since_previous_strategy_revision(
    previous_revision: dict[str, Any],
    current_revision: dict[str, Any],
) -> dict[str, Any]:
    previous_revision_id = _as_str(previous_revision.get("revision_id")) or "revision.previous.unknown"
    current_revision_id = _as_str(current_revision.get("revision_id")) or "revision.current.unknown"

    detection_sections: dict[str, dict[str, Any]] = {}
    section_change_ids: dict[str, list[str]] = {}
    all_changes: list[dict[str, Any]] = []
    for section_key in REQ010_SECTION_KEYS:
        section_changes = _collect_req010_section_changes(
            section_key,
            previous_revision.get(section_key),
            current_revision.get(section_key),
        )
        detection_sections[section_key] = {
            "changed": bool(section_changes),
            "change_count": len(section_changes),
            "changes": section_changes,
        }
        section_change_ids[section_key] = [row["change_id"] for row in section_changes]
        all_changes.extend(section_changes)

    all_changes.sort(key=lambda row: row["change_id"])
    all_change_ids = [row["change_id"] for row in all_changes]
    recommendation_deltas = _build_req010_recommendation_deltas(
        previous_revision=previous_revision,
        current_revision=current_revision,
        section_change_ids=section_change_ids,
        all_change_ids=all_change_ids,
    )
    evidence_refs = _sorted_unique_strings(
        [
            _as_str(ref)
            for ref in [
                *(
                    previous_revision.get("evidence_refs")
                    if isinstance(previous_revision.get("evidence_refs"), list)
                    else []
                ),
                *(
                    current_revision.get("evidence_refs")
                    if isinstance(current_revision.get("evidence_refs"), list)
                    else []
                ),
            ]
            if _as_str(ref)
        ]
    )

    return {
        "schema_version": CHANGE_DETECTION_SCHEMA_VERSION,
        "revision_pair": {
            "previous_revision_id": previous_revision_id,
            "current_revision_id": current_revision_id,
        },
        "change_detection": detection_sections,
        "change_summary": {
            "total_change_count": len(all_changes),
            "changed_sections": [section_key for section_key in REQ010_SECTION_KEYS if section_change_ids.get(section_key)],
            "change_ids": all_change_ids,
        },
        "recommendation_deltas": recommendation_deltas,
        "evidence_refs": evidence_refs,
    }


def validate_change_detection_since_previous_strategy_revision(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["payload must be an object"]

    if _as_str(payload.get("schema_version")) != CHANGE_DETECTION_SCHEMA_VERSION:
        errors.append(f"schema_version must equal {CHANGE_DETECTION_SCHEMA_VERSION}")

    revision_pair = payload.get("revision_pair")
    if not isinstance(revision_pair, dict):
        errors.append("revision_pair must be an object")
    else:
        previous_revision_id = _as_str(revision_pair.get("previous_revision_id"))
        current_revision_id = _as_str(revision_pair.get("current_revision_id"))
        if not previous_revision_id:
            errors.append("revision_pair.previous_revision_id is required")
        if not current_revision_id:
            errors.append("revision_pair.current_revision_id is required")
        if previous_revision_id and current_revision_id and previous_revision_id == current_revision_id:
            errors.append("revision_pair.previous_revision_id and current_revision_id must differ")

    detection = payload.get("change_detection")
    all_change_ids: list[str] = []
    section_change_ids: dict[str, list[str]] = {}
    if not isinstance(detection, dict):
        errors.append("change_detection must be an object")
        detection = {}
    for section_key in REQ010_SECTION_KEYS:
        section_payload = detection.get(section_key)
        if not isinstance(section_payload, dict):
            errors.append(f"change_detection.{section_key} must be an object")
            section_change_ids[section_key] = []
            continue
        changed = section_payload.get("changed")
        if not isinstance(changed, bool):
            errors.append(f"change_detection.{section_key}.changed must be a boolean")
        change_count = section_payload.get("change_count")
        if not isinstance(change_count, int):
            errors.append(f"change_detection.{section_key}.change_count must be an integer")
        changes = section_payload.get("changes")
        if not isinstance(changes, list):
            errors.append(f"change_detection.{section_key}.changes must be a list")
            section_change_ids[section_key] = []
            continue
        section_ids: list[str] = []
        for idx, row in enumerate(changes):
            if not isinstance(row, dict):
                errors.append(f"change_detection.{section_key}.changes[{idx}] must be an object")
                continue
            change_id = _as_str(row.get("change_id"))
            if not re.fullmatch(rf"chg\.{section_key}\.[a-f0-9]{{16}}", change_id):
                errors.append(f"change_detection.{section_key}.changes[{idx}].change_id is invalid")
            section_value = _as_str(row.get("section_key"))
            if section_value != section_key:
                errors.append(f"change_detection.{section_key}.changes[{idx}].section_key must equal {section_key}")
            path_value = _as_str(row.get("path"))
            if not path_value.startswith("/"):
                errors.append(f"change_detection.{section_key}.changes[{idx}].path must be a JSON pointer")
            change_type = _as_str(row.get("change_type"))
            if change_type not in REQ010_CHANGE_TYPES:
                errors.append(f"change_detection.{section_key}.changes[{idx}].change_type is invalid")
            section_ids.append(change_id)
        if isinstance(change_count, int) and change_count != len(changes):
            errors.append(f"change_detection.{section_key}.change_count must equal len(changes)")
        if isinstance(changed, bool) and changed != bool(changes):
            errors.append(f"change_detection.{section_key}.changed must match whether changes are present")
        raw_change_ids = [_as_str(row.get("change_id")) if isinstance(row, dict) else "" for row in changes]
        if raw_change_ids != sorted(raw_change_ids):
            errors.append(f"change_detection.{section_key}.changes must be sorted by change_id")
        section_ids = [change_id for change_id in section_ids if change_id]
        if len(set(section_ids)) != len(section_ids):
            errors.append(f"change_detection.{section_key}.changes change_id values must be unique")
        section_change_ids[section_key] = section_ids
        all_change_ids.extend(section_ids)

    if set(detection.keys()) != set(REQ010_SECTION_KEYS):
        errors.append(
            "change_detection must contain exactly mission_scope, runtime_data, and ecosystem_signals sections"
        )
    if len(set(all_change_ids)) != len(all_change_ids):
        errors.append("change_detection change_id values must be globally unique")

    change_summary = payload.get("change_summary")
    if not isinstance(change_summary, dict):
        errors.append("change_summary must be an object")
    else:
        total_change_count = change_summary.get("total_change_count")
        if not isinstance(total_change_count, int):
            errors.append("change_summary.total_change_count must be an integer")
        elif total_change_count != len(all_change_ids):
            errors.append("change_summary.total_change_count must equal total detected changes")

        changed_sections = change_summary.get("changed_sections")
        expected_changed_sections = [section_key for section_key in REQ010_SECTION_KEYS if section_change_ids.get(section_key)]
        if not isinstance(changed_sections, list):
            errors.append("change_summary.changed_sections must be a list")
        else:
            if changed_sections != expected_changed_sections:
                errors.append("change_summary.changed_sections must match sections with detected changes")

        summary_change_ids = change_summary.get("change_ids")
        if not isinstance(summary_change_ids, list):
            errors.append("change_summary.change_ids must be a list")
        else:
            if summary_change_ids != sorted(all_change_ids):
                errors.append("change_summary.change_ids must equal sorted detected change_ids")

    recommendation_deltas = payload.get("recommendation_deltas")
    referenced_change_ids: list[str] = []
    if not isinstance(recommendation_deltas, list):
        errors.append("recommendation_deltas must be a list")
    else:
        for idx, row in enumerate(recommendation_deltas):
            if not isinstance(row, dict):
                errors.append(f"recommendation_deltas[{idx}] must be an object")
                continue
            recommendation_id = _as_str(row.get("recommendation_id"))
            if not recommendation_id:
                errors.append(f"recommendation_deltas[{idx}].recommendation_id is required")
            summary = _as_str(row.get("summary"))
            if not summary:
                errors.append(f"recommendation_deltas[{idx}].summary is required")
            anchors = row.get("anchors")
            if not isinstance(anchors, list) or not anchors:
                errors.append(f"recommendation_deltas[{idx}].anchors must be a non-empty list")
            else:
                normalized_anchors = _normalize_req010_anchors(anchors)
                if anchors != normalized_anchors:
                    errors.append(
                        f"recommendation_deltas[{idx}].anchors must be ordered subset of {', '.join(REQ010_SECTION_KEYS)}"
                    )
            change_ids = row.get("change_ids")
            if not isinstance(change_ids, list) or not change_ids:
                errors.append(f"recommendation_deltas[{idx}].change_ids must be a non-empty list")
                continue
            normalized_change_ids = [_as_str(change_id) for change_id in change_ids]
            if normalized_change_ids != sorted(normalized_change_ids):
                errors.append(f"recommendation_deltas[{idx}].change_ids must be sorted")
            if len(set(normalized_change_ids)) != len(normalized_change_ids):
                errors.append(f"recommendation_deltas[{idx}].change_ids must be unique")
            for change_idx, change_id in enumerate(change_ids):
                value = _as_str(change_id)
                if not value:
                    errors.append(f"recommendation_deltas[{idx}].change_ids[{change_idx}] must be non-empty string")
                    continue
                if value not in all_change_ids:
                    errors.append(
                        f"recommendation_deltas[{idx}].change_ids[{change_idx}] must reference change_detection change_id values"
                    )
                referenced_change_ids.append(value)
            delta_type = _as_str(row.get("delta_type"))
            if delta_type not in {"new", "updated", "retained", "derived"}:
                errors.append(
                    f"recommendation_deltas[{idx}].delta_type must be one of new, updated, retained, derived"
                )

    if all_change_ids:
        if not referenced_change_ids:
            errors.append("recommendation_deltas must reference detected changes")
        missing_references = sorted(set(all_change_ids) - set(referenced_change_ids))
        if missing_references:
            errors.append("recommendation_deltas must reference every detected change_id")

    evidence_refs = payload.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        errors.append("evidence_refs must be a non-empty list")
    else:
        normalized_evidence_refs = [_as_str(ref) for ref in evidence_refs]
        for idx, ref in enumerate(evidence_refs):
            if not _as_str(ref):
                errors.append(f"evidence_refs[{idx}] must be non-empty string")
        if normalized_evidence_refs != sorted(normalized_evidence_refs):
            errors.append("evidence_refs must be sorted")
        if len(set(normalized_evidence_refs)) != len(normalized_evidence_refs):
            errors.append("evidence_refs must be unique")

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
