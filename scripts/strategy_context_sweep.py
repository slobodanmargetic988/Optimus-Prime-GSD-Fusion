#!/usr/bin/env python3
"""REQ-002, REQ-010, and REQ-014 strategy context contract surfaces."""

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
TOOL_VERSION = "1.1.0"
MANIFEST_SCHEMA_VERSION = "req-002.earth-wide-repository-discovery-manifest.v1"
CHANGE_DETECTION_SCHEMA_VERSION = "req-010.change-detection-since-previous-strategy-revision.v1"
REQ014_ANALYSIS_TYPE = "deficit_and_need_signal_extraction"
REQ014_ANALYSIS_ANCHORS = ("unmet_ecosystem_needs", "high_leverage_fit", "impact", "urgency")
REQ014_DEFAULT_THRESHOLDS = {
    "min_impact_score": 6.0,
    "min_urgency_score": 6.0,
    "min_leverage_ratio": 0.5,
}
REQ014_DEFAULT_MAX_SIGNALS = 5
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


class SweepError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        stage: str = "runtime",
        evidence_refs: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.stage = stage
        self.evidence_refs = list(evidence_refs or [])


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


def _safe_nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value if value >= 0 else 0
    if isinstance(value, float) and value.is_integer():
        integer_value = int(value)
        return integer_value if integer_value >= 0 else 0
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            try:
                parsed = int(stripped)
            except ValueError:
                return 0
            return parsed if parsed >= 0 else 0
    return 0


def _first_mapping(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def _first_list(*values: Any) -> list[Any]:
    for value in values:
        if isinstance(value, list):
            return value
    return []


def _normalize_req010_broad_sweep_inputs(raw_value: Any) -> dict[str, Any]:
    payload = raw_value if isinstance(raw_value, dict) else {}
    source_ref_coverage = (
        payload.get("source_ref_coverage") if isinstance(payload.get("source_ref_coverage"), dict) else {}
    )
    excluded_reason_counts = (
        payload.get("excluded_reason_counts") if isinstance(payload.get("excluded_reason_counts"), dict) else {}
    )
    discovered_project_ids = _sorted_unique_strings(
        [
            _as_str(project_id)
            for project_id in (payload.get("discovered_project_ids") if isinstance(payload.get("discovered_project_ids"), list) else [])
            if _as_str(project_id)
        ]
    )
    return {
        "include_rule": _as_str(payload.get("include_rule")) or "direct_child_repository_roots_only",
        "direct_child_count": _safe_nonnegative_int(payload.get("direct_child_count")),
        "discovered_project_ids": discovered_project_ids,
        "source_ref_coverage": {
            "project_count": _safe_nonnegative_int(source_ref_coverage.get("project_count")),
            "complete_project_count": _safe_nonnegative_int(source_ref_coverage.get("complete_project_count")),
            "partial_project_count": _safe_nonnegative_int(source_ref_coverage.get("partial_project_count")),
            "mission_ref_count": _safe_nonnegative_int(source_ref_coverage.get("mission_ref_count")),
            "scope_ref_count": _safe_nonnegative_int(source_ref_coverage.get("scope_ref_count")),
        },
        "excluded_reason_counts": {
            reason_code: _safe_nonnegative_int(excluded_reason_counts.get(reason_code))
            for reason_code in EXCLUDE_REASON_CODES
        },
    }


def _normalize_req010_cross_project_context(raw_rows: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_rows, list):
        return []

    merged_rows: dict[str, dict[str, Any]] = {}
    status_rank = {"complete": 2, "partial": 1, "unknown": 0}
    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        project_id = _as_str(row.get("project_id"))
        if not project_id:
            continue
        context_status = _as_str(row.get("context_status")).lower()
        if context_status not in {"complete", "partial"}:
            context_status = "unknown"
        summary = _as_str(row.get("summary")) or f"{project_id} context status is {context_status}."
        reason_codes = _sorted_unique_strings(
            [
                _as_str(value)
                for value in (row.get("reason_codes") if isinstance(row.get("reason_codes"), list) else [])
                if _as_str(value)
            ]
        )
        row_evidence_refs = _sorted_unique_strings(
            [
                _as_str(ref)
                for ref in (
                    (row.get("evidence_refs") if isinstance(row.get("evidence_refs"), list) else [])
                    + [_as_str(row.get("mission_ref")), _as_str(row.get("scope_ref"))]
                )
                if _as_str(ref)
            ]
        )
        if not row_evidence_refs:
            row_evidence_refs = [f"context:{project_id}#context_status={context_status}"]

        existing = merged_rows.get(project_id)
        if existing is None:
            merged_rows[project_id] = {
                "project_id": project_id,
                "context_status": context_status,
                "summary": summary,
                "reason_codes": reason_codes,
                "evidence_refs": row_evidence_refs,
            }
            continue

        existing_status = _as_str(existing.get("context_status")) or "unknown"
        if status_rank.get(context_status, 0) > status_rank.get(existing_status, 0):
            existing["context_status"] = context_status
        existing["reason_codes"] = _sorted_unique_strings(
            [
                _as_str(code)
                for code in [*existing.get("reason_codes", []), *reason_codes]
                if _as_str(code)
            ]
        )
        existing["evidence_refs"] = _sorted_unique_strings(
            [
                _as_str(ref)
                for ref in [*existing.get("evidence_refs", []), *row_evidence_refs]
                if _as_str(ref)
            ]
        )

    return [merged_rows[project_id] for project_id in sorted(merged_rows.keys())]


def _extract_req010_context_inputs(
    previous_revision: dict[str, Any],
    current_revision: dict[str, Any],
) -> dict[str, Any]:
    current_context_inputs = (
        current_revision.get("context_inputs") if isinstance(current_revision.get("context_inputs"), dict) else {}
    )
    previous_context_inputs = (
        previous_revision.get("context_inputs") if isinstance(previous_revision.get("context_inputs"), dict) else {}
    )
    current_manifest = _first_mapping(
        current_revision.get("earth_repository_discovery_manifest"),
        current_context_inputs.get("earth_repository_discovery_manifest"),
    )
    previous_manifest = _first_mapping(
        previous_revision.get("earth_repository_discovery_manifest"),
        previous_context_inputs.get("earth_repository_discovery_manifest"),
    )

    broad_sweep_inputs = _normalize_req010_broad_sweep_inputs(
        _first_mapping(
            current_context_inputs.get("broad_sweep_inputs"),
            current_revision.get("broad_sweep_inputs"),
            current_context_inputs.get("earth_sweep"),
            current_manifest.get("broad_sweep_inputs"),
            previous_context_inputs.get("broad_sweep_inputs"),
            previous_revision.get("broad_sweep_inputs"),
            previous_context_inputs.get("earth_sweep"),
            previous_manifest.get("broad_sweep_inputs"),
        )
    )

    cross_project_context = _normalize_req010_cross_project_context(
        _first_list(
            current_context_inputs.get("cross_project_context"),
            current_revision.get("cross_project_context"),
            current_context_inputs.get("projects"),
            current_manifest.get("cross_project_context"),
            previous_context_inputs.get("cross_project_context"),
            previous_revision.get("cross_project_context"),
            previous_context_inputs.get("projects"),
            previous_manifest.get("cross_project_context"),
        )
    )

    earth_sweep_evidence_refs = _sorted_unique_strings(
        [
            _as_str(ref)
            for ref in [
                *(
                    current_context_inputs.get("earth_sweep_evidence_refs")
                    if isinstance(current_context_inputs.get("earth_sweep_evidence_refs"), list)
                    else []
                ),
                *(
                    current_revision.get("earth_sweep_evidence_refs")
                    if isinstance(current_revision.get("earth_sweep_evidence_refs"), list)
                    else []
                ),
                *(
                    current_context_inputs.get("evidence_refs")
                    if isinstance(current_context_inputs.get("evidence_refs"), list)
                    else []
                ),
                *(current_manifest.get("evidence_refs") if isinstance(current_manifest.get("evidence_refs"), list) else []),
                *(
                    previous_context_inputs.get("earth_sweep_evidence_refs")
                    if isinstance(previous_context_inputs.get("earth_sweep_evidence_refs"), list)
                    else []
                ),
                *(
                    previous_revision.get("earth_sweep_evidence_refs")
                    if isinstance(previous_revision.get("earth_sweep_evidence_refs"), list)
                    else []
                ),
                *(
                    previous_context_inputs.get("evidence_refs")
                    if isinstance(previous_context_inputs.get("evidence_refs"), list)
                    else []
                ),
                *(previous_manifest.get("evidence_refs") if isinstance(previous_manifest.get("evidence_refs"), list) else []),
                *[ref for row in cross_project_context for ref in row.get("evidence_refs", [])],
            ]
            if _as_str(ref)
        ]
    )

    context_project_ids = _sorted_unique_strings(
        [
            *broad_sweep_inputs.get("discovered_project_ids", []),
            *[row["project_id"] for row in cross_project_context],
        ]
    )

    context_evidence_refs = _sorted_unique_strings(
        [
            *earth_sweep_evidence_refs,
            *[ref for row in cross_project_context for ref in row.get("evidence_refs", [])],
        ]
    )

    return {
        "broad_sweep_inputs": broad_sweep_inputs,
        "cross_project_context": cross_project_context,
        "earth_sweep_evidence_refs": earth_sweep_evidence_refs,
        "context_project_ids": context_project_ids,
        "evidence_refs": context_evidence_refs,
    }


def _normalize_req010_candidate_cross_project_obligations(
    current_revision: dict[str, Any],
    context_project_ids: list[str],
) -> list[dict[str, Any]]:
    recommendation_payload = (
        current_revision.get("recommendation") if isinstance(current_revision.get("recommendation"), dict) else {}
    )
    context_inputs = current_revision.get("context_inputs") if isinstance(current_revision.get("context_inputs"), dict) else {}
    raw_rows = _first_list(
        current_revision.get("proposed_cross_project_obligations"),
        recommendation_payload.get("proposed_cross_project_obligations"),
        context_inputs.get("cross_project_obligations"),
        context_inputs.get("proposed_cross_project_obligations"),
        current_revision.get("cross_project_obligations"),
    )
    obligations: list[dict[str, Any]] = []
    for idx, row in enumerate(raw_rows):
        if not isinstance(row, dict):
            continue
        obligation_id = _as_str(row.get("obligation_id")) or f"obl.cross-project.{idx + 1:03d}"
        title = _as_str(row.get("title") or row.get("summary")) or f"Cross-project obligation {idx + 1}."
        project_ids = _sorted_unique_strings(
            [
                _as_str(project_id)
                for project_id in (row.get("project_ids") if isinstance(row.get("project_ids"), list) else [])
                if _as_str(project_id)
            ]
        )
        if not project_ids:
            project_ids = list(context_project_ids)
        evidence_refs = _sorted_unique_strings(
            [
                _as_str(ref)
                for ref in (row.get("evidence_refs") if isinstance(row.get("evidence_refs"), list) else [])
                if _as_str(ref)
            ]
        )
        obligations.append(
            {
                "obligation_id": obligation_id,
                "title": title,
                "project_ids": project_ids,
                "evidence_refs": evidence_refs,
            }
        )
    obligations.sort(key=lambda row: row["obligation_id"])
    return obligations


def _build_req010_cross_project_context_usage(
    *,
    context_inputs: dict[str, Any],
    candidate_obligations: list[dict[str, Any]],
) -> dict[str, Any]:
    context_project_ids = context_inputs.get("context_project_ids") if isinstance(context_inputs.get("context_project_ids"), list) else []
    cross_project_context = (
        context_inputs.get("cross_project_context") if isinstance(context_inputs.get("cross_project_context"), list) else []
    )
    earth_sweep_evidence_refs = (
        context_inputs.get("earth_sweep_evidence_refs")
        if isinstance(context_inputs.get("earth_sweep_evidence_refs"), list)
        else []
    )
    earth_sweep_ref_set = set(earth_sweep_evidence_refs)

    obligations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    for row in candidate_obligations:
        evidence_refs = row.get("evidence_refs") if isinstance(row.get("evidence_refs"), list) else []
        has_earth_sweep_evidence = bool(evidence_refs) and all(ref in earth_sweep_ref_set for ref in evidence_refs)
        if has_earth_sweep_evidence:
            obligations.append(
                {
                    "obligation_id": _as_str(row.get("obligation_id")),
                    "title": _as_str(row.get("title")),
                    "project_ids": _sorted_unique_strings(
                        [_as_str(project_id) for project_id in row.get("project_ids", []) if _as_str(project_id)]
                    ),
                    "evidence_refs": _sorted_unique_strings([_as_str(ref) for ref in evidence_refs if _as_str(ref)]),
                }
            )
            continue

        obligation_id = _as_str(row.get("obligation_id")) or "obligation.unknown"
        obligation_projects = _sorted_unique_strings(
            [_as_str(project_id) for project_id in row.get("project_ids", []) if _as_str(project_id)]
        )
        risk_evidence_refs = _sorted_unique_strings(
            [_as_str(ref) for ref in evidence_refs if _as_str(ref)]
            + [ref for row in cross_project_context for ref in row.get("evidence_refs", [])]
            + list(earth_sweep_evidence_refs)
        )
        if not risk_evidence_refs:
            risk_evidence_refs = [f"missing:earth-sweep-evidence#{obligation_id}"]
        open_risks.append(
            {
                "risk_id": f"risk.req010.cross-project-obligation.{obligation_id}",
                "reason_code": "missing_peer_project_doc",
                "summary": (
                    f"{obligation_id} cannot be promoted to a cross-project obligation because Earth-sweep evidence refs are incomplete."
                ),
                "project_ids": obligation_projects or list(context_project_ids),
                "evidence_refs": risk_evidence_refs,
            }
        )

    partial_project_ids = _sorted_unique_strings(
        [_as_str(row.get("project_id")) for row in cross_project_context if _as_str(row.get("context_status")) == "partial"]
    )
    if partial_project_ids:
        open_risks.append(
            {
                "risk_id": "risk.req010.cross-project-context-partial",
                "reason_code": "missing_peer_project_doc",
                "summary": "Cross-project context remains partial for one or more projects; unresolved ideas remain open risks.",
                "project_ids": partial_project_ids,
                "evidence_refs": _sorted_unique_strings(
                    [
                        ref
                        for row in cross_project_context
                        if _as_str(row.get("project_id")) in partial_project_ids
                        for ref in row.get("evidence_refs", [])
                    ]
                )
                or [f"context:partial#{','.join(partial_project_ids)}"],
            }
        )

    obligations.sort(key=lambda row: row["obligation_id"])
    open_risks.sort(key=lambda row: row["risk_id"])
    usage_evidence_refs = _sorted_unique_strings(
        [
            *[ref for row in cross_project_context for ref in row.get("evidence_refs", [])],
            *earth_sweep_evidence_refs,
            *[ref for row in obligations for ref in row.get("evidence_refs", [])],
            *[ref for row in open_risks for ref in row.get("evidence_refs", [])],
        ]
    )
    usage_project_ids = _sorted_unique_strings(
        [*context_project_ids, *[project_id for row in obligations for project_id in row.get("project_ids", [])]]
    )
    return {
        "context_project_ids": usage_project_ids,
        "obligations": obligations,
        "open_risks": open_risks,
        "evidence_refs": usage_evidence_refs,
    }


def _build_req010_recommendation_deltas(
    *,
    previous_revision: dict[str, Any],
    current_revision: dict[str, Any],
    section_change_ids: dict[str, list[str]],
    all_change_ids: list[str],
    shared_evidence_refs: list[str],
    context_project_ids: list[str],
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
                "evidence_refs": list(shared_evidence_refs),
                "linked_context_project_ids": list(context_project_ids),
            }
        )

    referenced_change_ids = {
        change_id
        for row in deltas
        for change_id in row.get("change_ids", [])
        if _as_str(change_id)
    }
    missing_change_ids = [change_id for change_id in all_change_ids if change_id not in referenced_change_ids]
    if missing_change_ids:
        missing_change_id_set = set(missing_change_ids)
        changed_anchors = [
            section_key
            for section_key in REQ010_SECTION_KEYS
            if any(change_id in missing_change_id_set for change_id in section_change_ids.get(section_key, []))
        ]
        if not changed_anchors:
            changed_anchors = [section_key for section_key in REQ010_SECTION_KEYS if section_change_ids.get(section_key)]
        reserved_ids = {_as_str(row.get("recommendation_id")) for row in deltas}
        recommendation_id = "rec.strategy-revision-delta"
        if recommendation_id in reserved_ids:
            recommendation_id = "rec.strategy-revision-delta-coverage"
            sequence = 2
            while recommendation_id in reserved_ids:
                recommendation_id = f"rec.strategy-revision-delta-coverage-{sequence}"
                sequence += 1
        deltas.append(
            {
                "recommendation_id": recommendation_id,
                "summary": "Backfill recommendation coverage for detected revision changes.",
                "anchors": changed_anchors,
                "change_ids": missing_change_ids,
                "delta_type": "derived",
                "evidence_refs": list(shared_evidence_refs),
                "linked_context_project_ids": list(context_project_ids),
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
    context_inputs = _extract_req010_context_inputs(previous_revision, current_revision)
    cross_project_context_usage = _build_req010_cross_project_context_usage(
        context_inputs=context_inputs,
        candidate_obligations=_normalize_req010_candidate_cross_project_obligations(
            current_revision,
            context_inputs.get("context_project_ids", []),
        ),
    )

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
    shared_evidence_refs = _sorted_unique_strings(
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
                *(context_inputs.get("evidence_refs") if isinstance(context_inputs.get("evidence_refs"), list) else []),
                *(
                    cross_project_context_usage.get("evidence_refs")
                    if isinstance(cross_project_context_usage.get("evidence_refs"), list)
                    else []
                ),
            ]
            if _as_str(ref)
        ]
    )
    recommendation_deltas = _build_req010_recommendation_deltas(
        previous_revision=previous_revision,
        current_revision=current_revision,
        section_change_ids=section_change_ids,
        all_change_ids=all_change_ids,
        shared_evidence_refs=shared_evidence_refs,
        context_project_ids=(
            cross_project_context_usage.get("context_project_ids")
            if isinstance(cross_project_context_usage.get("context_project_ids"), list)
            else []
        ),
    )
    evidence_refs = _sorted_unique_strings(
        [
            *shared_evidence_refs,
            *[
                _as_str(ref)
                for row in recommendation_deltas
                for ref in (row.get("evidence_refs") if isinstance(row.get("evidence_refs"), list) else [])
                if _as_str(ref)
            ],
        ]
    )

    return {
        "schema_version": CHANGE_DETECTION_SCHEMA_VERSION,
        "revision_pair": {
            "previous_revision_id": previous_revision_id,
            "current_revision_id": current_revision_id,
        },
        "context_inputs": {
            "broad_sweep_inputs": context_inputs.get("broad_sweep_inputs", {}),
            "cross_project_context": context_inputs.get("cross_project_context", []),
            "earth_sweep_evidence_refs": context_inputs.get("earth_sweep_evidence_refs", []),
            "evidence_refs": context_inputs.get("evidence_refs", []),
        },
        "change_detection": detection_sections,
        "change_summary": {
            "total_change_count": len(all_changes),
            "changed_sections": [section_key for section_key in REQ010_SECTION_KEYS if section_change_ids.get(section_key)],
            "change_ids": all_change_ids,
        },
        "recommendation_deltas": recommendation_deltas,
        "cross_project_context_usage": cross_project_context_usage,
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

    context_inputs = payload.get("context_inputs")
    context_project_ids: list[str] = []
    earth_sweep_evidence_refs: list[str] = []
    context_evidence_refs: list[str] = []
    if not isinstance(context_inputs, dict):
        errors.append("context_inputs must be an object")
        context_inputs = {}
    else:
        broad_sweep_inputs = context_inputs.get("broad_sweep_inputs")
        if not isinstance(broad_sweep_inputs, dict):
            errors.append("context_inputs.broad_sweep_inputs must be an object")
            broad_sweep_inputs = {}
        discovered_project_ids = broad_sweep_inputs.get("discovered_project_ids")
        if discovered_project_ids is not None:
            if not isinstance(discovered_project_ids, list):
                errors.append("context_inputs.broad_sweep_inputs.discovered_project_ids must be a list")
            else:
                normalized_discovered_project_ids = [_as_str(project_id) for project_id in discovered_project_ids]
                if normalized_discovered_project_ids != sorted(normalized_discovered_project_ids):
                    errors.append("context_inputs.broad_sweep_inputs.discovered_project_ids must be sorted")
                if len(set(normalized_discovered_project_ids)) != len(normalized_discovered_project_ids):
                    errors.append("context_inputs.broad_sweep_inputs.discovered_project_ids must be unique")
                context_project_ids.extend(
                    [project_id for project_id in normalized_discovered_project_ids if project_id]
                )

        cross_project_context = context_inputs.get("cross_project_context")
        if not isinstance(cross_project_context, list):
            errors.append("context_inputs.cross_project_context must be a list")
            cross_project_context = []
        else:
            row_project_ids: list[str] = []
            for idx, row in enumerate(cross_project_context):
                if not isinstance(row, dict):
                    errors.append(f"context_inputs.cross_project_context[{idx}] must be an object")
                    continue
                project_id = _as_str(row.get("project_id"))
                if not project_id:
                    errors.append(f"context_inputs.cross_project_context[{idx}].project_id is required")
                row_project_ids.append(project_id)
                context_project_ids.append(project_id)
                context_status = _as_str(row.get("context_status"))
                if context_status not in {"complete", "partial", "unknown"}:
                    errors.append(
                        f"context_inputs.cross_project_context[{idx}].context_status must be complete|partial|unknown"
                    )
                if not _as_str(row.get("summary")):
                    errors.append(f"context_inputs.cross_project_context[{idx}].summary is required")
                row_evidence_refs = row.get("evidence_refs")
                if not isinstance(row_evidence_refs, list) or not row_evidence_refs:
                    errors.append(f"context_inputs.cross_project_context[{idx}].evidence_refs must be a non-empty list")
                else:
                    normalized_row_refs = [_as_str(ref) for ref in row_evidence_refs]
                    if normalized_row_refs != sorted(normalized_row_refs):
                        errors.append(
                            f"context_inputs.cross_project_context[{idx}].evidence_refs must be sorted"
                        )
                    if len(set(normalized_row_refs)) != len(normalized_row_refs):
                        errors.append(
                            f"context_inputs.cross_project_context[{idx}].evidence_refs must be unique"
                        )
                    context_evidence_refs.extend([ref for ref in normalized_row_refs if ref])
                row_reason_codes = row.get("reason_codes")
                if row_reason_codes is not None:
                    if not isinstance(row_reason_codes, list):
                        errors.append(f"context_inputs.cross_project_context[{idx}].reason_codes must be a list")
                    else:
                        for code_idx, code in enumerate(row_reason_codes):
                            if not _as_str(code):
                                errors.append(
                                    f"context_inputs.cross_project_context[{idx}].reason_codes[{code_idx}] "
                                    "must be non-empty string"
                                )
            if row_project_ids != sorted(row_project_ids):
                errors.append("context_inputs.cross_project_context must be sorted by project_id")
            if len(set(row_project_ids)) != len(row_project_ids):
                errors.append("context_inputs.cross_project_context.project_id values must be unique")

        earth_sweep_evidence_refs_value = context_inputs.get("earth_sweep_evidence_refs")
        if not isinstance(earth_sweep_evidence_refs_value, list):
            errors.append("context_inputs.earth_sweep_evidence_refs must be a list")
        else:
            normalized_earth_refs = [_as_str(ref) for ref in earth_sweep_evidence_refs_value]
            if normalized_earth_refs != sorted(normalized_earth_refs):
                errors.append("context_inputs.earth_sweep_evidence_refs must be sorted")
            if len(set(normalized_earth_refs)) != len(normalized_earth_refs):
                errors.append("context_inputs.earth_sweep_evidence_refs must be unique")
            earth_sweep_evidence_refs = [ref for ref in normalized_earth_refs if ref]
            context_evidence_refs.extend(earth_sweep_evidence_refs)

        context_evidence_refs_value = context_inputs.get("evidence_refs")
        if not isinstance(context_evidence_refs_value, list):
            errors.append("context_inputs.evidence_refs must be a list")
        else:
            normalized_context_refs = [_as_str(ref) for ref in context_evidence_refs_value]
            if normalized_context_refs != sorted(normalized_context_refs):
                errors.append("context_inputs.evidence_refs must be sorted")
            if len(set(normalized_context_refs)) != len(normalized_context_refs):
                errors.append("context_inputs.evidence_refs must be unique")
            for idx, ref in enumerate(normalized_context_refs):
                if not ref:
                    errors.append(f"context_inputs.evidence_refs[{idx}] must be non-empty string")
            context_evidence_refs.extend([ref for ref in normalized_context_refs if ref])

    context_project_ids = _sorted_unique_strings([_as_str(project_id) for project_id in context_project_ids if _as_str(project_id)])
    context_evidence_refs = _sorted_unique_strings([_as_str(ref) for ref in context_evidence_refs if _as_str(ref)])

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

    evidence_refs = payload.get("evidence_refs")
    normalized_evidence_refs: list[str] = []
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

    cross_project_context_usage = payload.get("cross_project_context_usage")
    usage_context_project_ids: list[str] = []
    if not isinstance(cross_project_context_usage, dict):
        errors.append("cross_project_context_usage must be an object")
        cross_project_context_usage = {}
    else:
        usage_project_ids = cross_project_context_usage.get("context_project_ids")
        if not isinstance(usage_project_ids, list):
            errors.append("cross_project_context_usage.context_project_ids must be a list")
        else:
            usage_context_project_ids = [_as_str(project_id) for project_id in usage_project_ids if _as_str(project_id)]
            if usage_context_project_ids != sorted(usage_context_project_ids):
                errors.append("cross_project_context_usage.context_project_ids must be sorted")
            if len(set(usage_context_project_ids)) != len(usage_context_project_ids):
                errors.append("cross_project_context_usage.context_project_ids must be unique")
            if context_project_ids and usage_context_project_ids != context_project_ids:
                errors.append("cross_project_context_usage.context_project_ids must match context_inputs project ids")

        obligations = cross_project_context_usage.get("obligations")
        if not isinstance(obligations, list):
            errors.append("cross_project_context_usage.obligations must be a list")
            obligations = []
        else:
            for idx, row in enumerate(obligations):
                if not isinstance(row, dict):
                    errors.append(f"cross_project_context_usage.obligations[{idx}] must be an object")
                    continue
                if not _as_str(row.get("obligation_id")):
                    errors.append(f"cross_project_context_usage.obligations[{idx}].obligation_id is required")
                if not _as_str(row.get("title")):
                    errors.append(f"cross_project_context_usage.obligations[{idx}].title is required")
                row_project_ids = row.get("project_ids")
                if not isinstance(row_project_ids, list) or not row_project_ids:
                    errors.append(
                        f"cross_project_context_usage.obligations[{idx}].project_ids must be a non-empty list"
                    )
                else:
                    for project_idx, project_id in enumerate(row_project_ids):
                        value = _as_str(project_id)
                        if not value:
                            errors.append(
                                f"cross_project_context_usage.obligations[{idx}].project_ids[{project_idx}] must be non-empty string"
                            )
                        if usage_context_project_ids and value not in usage_context_project_ids:
                            errors.append(
                                f"cross_project_context_usage.obligations[{idx}].project_ids[{project_idx}] "
                                "must reference context_project_ids"
                            )
                row_evidence_refs = row.get("evidence_refs")
                if not isinstance(row_evidence_refs, list) or not row_evidence_refs:
                    errors.append(
                        f"cross_project_context_usage.obligations[{idx}].evidence_refs must be a non-empty list"
                    )
                else:
                    normalized_row_refs = [_as_str(ref) for ref in row_evidence_refs]
                    if normalized_row_refs != sorted(normalized_row_refs):
                        errors.append(
                            f"cross_project_context_usage.obligations[{idx}].evidence_refs must be sorted"
                        )
                    if len(set(normalized_row_refs)) != len(normalized_row_refs):
                        errors.append(
                            f"cross_project_context_usage.obligations[{idx}].evidence_refs must be unique"
                        )
                    for ref_idx, ref in enumerate(normalized_row_refs):
                        if not ref:
                            errors.append(
                                f"cross_project_context_usage.obligations[{idx}].evidence_refs[{ref_idx}] "
                                "must be non-empty string"
                            )
                        if ref and earth_sweep_evidence_refs and ref not in earth_sweep_evidence_refs:
                            errors.append(
                                f"cross_project_context_usage.obligations[{idx}].evidence_refs[{ref_idx}] "
                                "must be Earth-sweep backed"
                            )

        open_risks = cross_project_context_usage.get("open_risks")
        if not isinstance(open_risks, list):
            errors.append("cross_project_context_usage.open_risks must be a list")
            open_risks = []
        else:
            for idx, row in enumerate(open_risks):
                if not isinstance(row, dict):
                    errors.append(f"cross_project_context_usage.open_risks[{idx}] must be an object")
                    continue
                if not _as_str(row.get("risk_id")):
                    errors.append(f"cross_project_context_usage.open_risks[{idx}].risk_id is required")
                if not _as_str(row.get("summary")):
                    errors.append(f"cross_project_context_usage.open_risks[{idx}].summary is required")
                if _as_str(row.get("reason_code")) not in OPEN_RISK_REASON_CODES:
                    errors.append(
                        f"cross_project_context_usage.open_risks[{idx}].reason_code must be one of {', '.join(OPEN_RISK_REASON_CODES)}"
                    )
                row_evidence_refs = row.get("evidence_refs")
                if not isinstance(row_evidence_refs, list) or not row_evidence_refs:
                    errors.append(
                        f"cross_project_context_usage.open_risks[{idx}].evidence_refs must be a non-empty list"
                    )
                else:
                    normalized_row_refs = [_as_str(ref) for ref in row_evidence_refs]
                    if normalized_row_refs != sorted(normalized_row_refs):
                        errors.append(
                            f"cross_project_context_usage.open_risks[{idx}].evidence_refs must be sorted"
                        )
                    if len(set(normalized_row_refs)) != len(normalized_row_refs):
                        errors.append(
                            f"cross_project_context_usage.open_risks[{idx}].evidence_refs must be unique"
                        )
                row_project_ids = row.get("project_ids")
                if row_project_ids is not None:
                    if not isinstance(row_project_ids, list):
                        errors.append(f"cross_project_context_usage.open_risks[{idx}].project_ids must be a list")
                    else:
                        for project_idx, project_id in enumerate(row_project_ids):
                            value = _as_str(project_id)
                            if not value:
                                errors.append(
                                    f"cross_project_context_usage.open_risks[{idx}].project_ids[{project_idx}] must be non-empty string"
                                )
                            elif usage_context_project_ids and value not in usage_context_project_ids:
                                errors.append(
                                    f"cross_project_context_usage.open_risks[{idx}].project_ids[{project_idx}] "
                                    "must reference context_project_ids"
                                )

        usage_evidence_refs = cross_project_context_usage.get("evidence_refs")
        if not isinstance(usage_evidence_refs, list):
            errors.append("cross_project_context_usage.evidence_refs must be a list")
        else:
            normalized_usage_refs = [_as_str(ref) for ref in usage_evidence_refs]
            if normalized_usage_refs != sorted(normalized_usage_refs):
                errors.append("cross_project_context_usage.evidence_refs must be sorted")
            if len(set(normalized_usage_refs)) != len(normalized_usage_refs):
                errors.append("cross_project_context_usage.evidence_refs must be unique")
            for idx, ref in enumerate(normalized_usage_refs):
                if not ref:
                    errors.append(f"cross_project_context_usage.evidence_refs[{idx}] must be non-empty string")

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
            delta_evidence_refs = row.get("evidence_refs")
            if not isinstance(delta_evidence_refs, list) or not delta_evidence_refs:
                errors.append(f"recommendation_deltas[{idx}].evidence_refs must be a non-empty list")
            else:
                normalized_delta_refs = [_as_str(ref) for ref in delta_evidence_refs]
                if normalized_delta_refs != sorted(normalized_delta_refs):
                    errors.append(f"recommendation_deltas[{idx}].evidence_refs must be sorted")
                if len(set(normalized_delta_refs)) != len(normalized_delta_refs):
                    errors.append(f"recommendation_deltas[{idx}].evidence_refs must be unique")
                for ref_idx, ref in enumerate(normalized_delta_refs):
                    if not ref:
                        errors.append(
                            f"recommendation_deltas[{idx}].evidence_refs[{ref_idx}] must be non-empty string"
                        )
                    elif normalized_evidence_refs and ref not in normalized_evidence_refs:
                        errors.append(
                            f"recommendation_deltas[{idx}].evidence_refs[{ref_idx}] must exist in top-level evidence_refs"
                        )
            linked_context_project_ids = row.get("linked_context_project_ids")
            if not isinstance(linked_context_project_ids, list):
                errors.append(f"recommendation_deltas[{idx}].linked_context_project_ids must be a list")
            else:
                normalized_linked_project_ids = [_as_str(project_id) for project_id in linked_context_project_ids if _as_str(project_id)]
                if normalized_linked_project_ids != sorted(normalized_linked_project_ids):
                    errors.append(
                        f"recommendation_deltas[{idx}].linked_context_project_ids must be sorted"
                    )
                if len(set(normalized_linked_project_ids)) != len(normalized_linked_project_ids):
                    errors.append(
                        f"recommendation_deltas[{idx}].linked_context_project_ids must be unique"
                    )
                expected_project_ids = usage_context_project_ids or context_project_ids
                if expected_project_ids and normalized_linked_project_ids != expected_project_ids:
                    errors.append(
                        f"recommendation_deltas[{idx}].linked_context_project_ids must match context project ids"
                    )

    if all_change_ids:
        if not referenced_change_ids:
            errors.append("recommendation_deltas must reference detected changes")
        missing_references = sorted(set(all_change_ids) - set(referenced_change_ids))
        if missing_references:
            errors.append("recommendation_deltas must reference every detected change_id")

    return errors


def _required_object(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise SweepError("input_error", f"{key} must be an object", stage="input")
    return value


def _required_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise SweepError("input_error", f"{key} must be a list", stage="input")
    return value


def _required_str(payload: dict[str, Any], key: str) -> str:
    text = _as_str(payload.get(key))
    if not text:
        raise SweepError("input_error", f"{key} is required", stage="input")
    return text


def _required_number(payload: dict[str, Any], key: str) -> float:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SweepError("input_error", f"{key} must be a number", stage="input")
    return float(value)


def _parse_req014_now(payload: dict[str, Any]) -> datetime:
    raw = payload.get("now_utc")
    if raw is None:
        return datetime.now(timezone.utc)
    text = _as_str(raw)
    if not text:
        raise SweepError("input_error", "now_utc must be non-empty when provided", stage="input")
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SweepError("input_error", f"invalid now_utc timestamp: {exc}", stage="input") from exc
    if dt.tzinfo is None:
        raise SweepError("input_error", "now_utc must include timezone offset", stage="input")
    return dt.astimezone(timezone.utc)


def _to_iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _normalize_string_list(values: Any, *, path: str, allow_empty: bool = False) -> list[str]:
    if not isinstance(values, list):
        raise SweepError("input_error", f"{path} must be a list", stage="input")
    out: list[str] = []
    for idx, raw in enumerate(values):
        text = _as_str(raw)
        if not text:
            raise SweepError("input_error", f"{path}[{idx}] must be a non-empty string", stage="input")
        out.append(text)
    if not allow_empty and not out:
        raise SweepError("input_error", f"{path} must be non-empty", stage="input")
    return out


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _normalize_capability_tags(values: Any, *, path: str) -> list[str]:
    tags = _normalize_string_list(values, path=path, allow_empty=False)
    out: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        normalized = tag.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _resolve_context_doc_path(raw_path: str, *, base_dir: Path) -> Path:
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = base_dir / candidate
    return candidate.resolve()


def _doc_evidence_ref(kind: str, path: Path, *, project_id: str | None = None) -> str:
    if project_id:
        return f"DOCREF:{kind}:{project_id}:{path}"
    return f"DOCREF:{kind}:{path}"


def _coerce_req014_thresholds(payload: dict[str, Any]) -> dict[str, float]:
    raw = payload.get("thresholds")
    if raw is None:
        return dict(REQ014_DEFAULT_THRESHOLDS)
    if not isinstance(raw, dict):
        raise SweepError("input_error", "thresholds must be an object", stage="input")

    out = dict(REQ014_DEFAULT_THRESHOLDS)
    for key in REQ014_DEFAULT_THRESHOLDS:
        if key not in raw:
            continue
        value = raw.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SweepError("input_error", f"thresholds.{key} must be numeric", stage="input")
        out[key] = float(value)

    if out["min_impact_score"] < 0 or out["min_impact_score"] > 10:
        raise SweepError("input_error", "thresholds.min_impact_score must be between 0 and 10", stage="input")
    if out["min_urgency_score"] < 0 or out["min_urgency_score"] > 10:
        raise SweepError("input_error", "thresholds.min_urgency_score must be between 0 and 10", stage="input")
    if out["min_leverage_ratio"] < 0 or out["min_leverage_ratio"] > 1:
        raise SweepError("input_error", "thresholds.min_leverage_ratio must be between 0 and 1", stage="input")
    return out


def _coerce_req014_max_signals(payload: dict[str, Any]) -> int:
    raw = payload.get("max_signals")
    if raw is None:
        return REQ014_DEFAULT_MAX_SIGNALS
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise SweepError("input_error", "max_signals must be an integer", stage="input")
    if raw <= 0:
        raise SweepError("input_error", "max_signals must be > 0", stage="input")
    return raw


def _validate_req014_target_project(payload: dict[str, Any]) -> dict[str, Any]:
    target = _required_object(payload, "target_project")
    project_id = _required_str(target, "project_id")
    capability_tags = _normalize_capability_tags(target.get("capability_tags"), path="target_project.capability_tags")
    return {
        "project_id": project_id,
        "capability_tags": capability_tags,
    }


def _validate_req014_unhappy_paths(values: Any, *, path: str) -> list[dict[str, Any]]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise SweepError("input_error", f"{path} must be a list", stage="input")

    out: list[dict[str, Any]] = []
    for idx, row in enumerate(values):
        row_path = f"{path}[{idx}]"
        if not isinstance(row, dict):
            raise SweepError("input_error", f"{row_path} must be an object", stage="input")

        reason_code = _required_str(row, "reason_code")
        evidence_refs = _normalize_string_list(
            row.get("evidence_refs") or [],
            path=f"{row_path}.evidence_refs",
            allow_empty=True,
        )
        normalized_row = {
            "reason_code": reason_code,
            "project_id": _as_str(row.get("project_id")),
            "artifact_type": _as_str(row.get("artifact_type")),
            "source_id": _as_str(row.get("source_id")),
            "evidence_refs": _dedupe_preserve_order(evidence_refs),
        }
        if reason_code == "stale_source_artifact_detected" and not normalized_row["evidence_refs"]:
            raise SweepError(
                "input_error",
                f"{row_path}.evidence_refs must be non-empty for stale_source_artifact_detected",
                stage="input",
            )
        out.append(normalized_row)
    return out


def _validate_req014_broad_sweep_context(
    payload: dict[str, Any],
    *,
    target_project_id: str,
) -> dict[str, Any]:
    raw = payload.get("broad_sweep_context")
    if raw is None:
        projects_considered = [target_project_id]
        evidence_refs_by_project = {target_project_id: []}
        cross_project = False
        unhappy_paths: list[dict[str, Any]] = []
    else:
        if not isinstance(raw, dict):
            raise SweepError("input_error", "broad_sweep_context must be an object", stage="input")

        raw_evidence_refs = raw.get("evidence_refs_by_project")
        if raw_evidence_refs is None:
            raw_evidence_refs = {}
        if not isinstance(raw_evidence_refs, dict):
            raise SweepError("input_error", "broad_sweep_context.evidence_refs_by_project must be an object", stage="input")

        evidence_refs_by_project: dict[str, list[str]] = {}
        for raw_project_id, raw_refs in raw_evidence_refs.items():
            project_id = _as_str(raw_project_id)
            if not project_id:
                raise SweepError(
                    "input_error",
                    "broad_sweep_context.evidence_refs_by_project keys must be non-empty strings",
                    stage="input",
                )
            refs = _normalize_string_list(
                raw_refs,
                path=f"broad_sweep_context.evidence_refs_by_project.{project_id}",
                allow_empty=True,
            )
            evidence_refs_by_project[project_id] = _dedupe_preserve_order(refs)

        raw_projects_considered = raw.get("projects_considered")
        if raw_projects_considered is None:
            projects_considered = list(evidence_refs_by_project.keys())
        else:
            projects_considered = _normalize_string_list(
                raw_projects_considered,
                path="broad_sweep_context.projects_considered",
                allow_empty=True,
            )
            projects_considered = _dedupe_preserve_order(projects_considered)

        for project_id in evidence_refs_by_project:
            if project_id not in projects_considered:
                projects_considered.append(project_id)

        if not projects_considered:
            projects_considered = [target_project_id]
        for project_id in projects_considered:
            evidence_refs_by_project.setdefault(project_id, [])

        raw_cross_project = raw.get("cross_project")
        if raw_cross_project is None:
            cross_project = len(projects_considered) > 1
        elif isinstance(raw_cross_project, bool):
            cross_project = raw_cross_project
        else:
            raise SweepError("input_error", "broad_sweep_context.cross_project must be boolean", stage="input")
        unhappy_paths = _validate_req014_unhappy_paths(
            raw.get("unhappy_paths"),
            path="broad_sweep_context.unhappy_paths",
        )

    projects_with_evidence_refs = [
        project_id for project_id in projects_considered if evidence_refs_by_project.get(project_id)
    ]
    projects_without_evidence_refs = [
        project_id for project_id in projects_considered if not evidence_refs_by_project.get(project_id)
    ]
    earth_sweep_evidence_refs = _dedupe_preserve_order(
        [
            evidence_ref
            for project_id in projects_considered
            for evidence_ref in evidence_refs_by_project.get(project_id, [])
        ]
    )

    return {
        "cross_project": cross_project,
        "projects_considered": projects_considered,
        "projects_with_evidence_refs": projects_with_evidence_refs,
        "projects_without_evidence_refs": projects_without_evidence_refs,
        "evidence_refs_by_project": evidence_refs_by_project,
        "earth_sweep_evidence_refs": earth_sweep_evidence_refs,
        "unhappy_paths": unhappy_paths,
    }


def _validate_req014_deficits(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = _required_list(payload, "deficits")
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            raise SweepError("input_error", f"deficits[{idx}] must be an object", stage="input")
        deficit_id = _required_str(row, "deficit_id")
        summary = _required_str(row, "summary")
        impact_score = _required_number(row, "impact_score")
        urgency_score = _required_number(row, "urgency_score")
        if impact_score < 0 or impact_score > 10:
            raise SweepError("input_error", f"deficits[{idx}].impact_score must be between 0 and 10", stage="input")
        if urgency_score < 0 or urgency_score > 10:
            raise SweepError("input_error", f"deficits[{idx}].urgency_score must be between 0 and 10", stage="input")
        required_tags = _normalize_capability_tags(
            row.get("required_capability_tags"),
            path=f"deficits[{idx}].required_capability_tags",
        )
        upstream_refs = _normalize_string_list(
            row.get("evidence_refs"),
            path=f"deficits[{idx}].evidence_refs",
            allow_empty=False,
        )
        out.append(
            {
                "deficit_id": deficit_id,
                "summary": summary,
                "impact_score": impact_score,
                "urgency_score": urgency_score,
                "required_capability_tags": required_tags,
                "upstream_evidence_refs": upstream_refs,
            }
        )
    return out


def _classify_req014_failed_criteria(
    *,
    impact_score: float,
    urgency_score: float,
    leverage_ratio: float,
    thresholds: dict[str, float],
) -> list[str]:
    failed: list[str] = []
    if impact_score < thresholds["min_impact_score"]:
        failed.append("impact_below_threshold")
    if urgency_score < thresholds["min_urgency_score"]:
        failed.append("urgency_below_threshold")
    if leverage_ratio < thresholds["min_leverage_ratio"]:
        failed.append("leverage_below_threshold")
    return failed


def _validate_context_bundle_docs(payload: dict[str, Any]) -> dict[str, Any] | None:
    raw = payload.get("context_bundle_docs")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise SweepError("input_error", "context_bundle_docs must be an object", stage="input")

    base_dir_raw = _as_str(raw.get("base_dir"))
    base_dir = Path(base_dir_raw).expanduser() if base_dir_raw else Path.cwd()
    if not base_dir.is_absolute():
        base_dir = (Path.cwd() / base_dir).resolve()
    else:
        base_dir = base_dir.resolve()

    mission_raw = _as_str(raw.get("mission_path"))
    scope_raw = _as_str(raw.get("scope_path"))
    if not mission_raw or not scope_raw:
        raise SweepError(
            "input_error",
            "context_bundle_docs.mission_path and context_bundle_docs.scope_path are required",
            stage="input",
        )

    mission_path = _resolve_context_doc_path(mission_raw, base_dir=base_dir)
    scope_path = _resolve_context_doc_path(scope_raw, base_dir=base_dir)
    missing_mission_scope_refs: list[str] = []
    if not mission_path.is_file():
        missing_mission_scope_refs.append(_doc_evidence_ref("mission", mission_path))
    if not scope_path.is_file():
        missing_mission_scope_refs.append(_doc_evidence_ref("scope", scope_path))
    if missing_mission_scope_refs:
        raise SweepError(
            "mission_scope_doc_missing",
            "mission/scope context docs must exist for context bundle serialization",
            stage="input",
            evidence_refs=missing_mission_scope_refs,
        )

    peer_docs_raw = raw.get("peer_project_docs")
    if peer_docs_raw is None:
        peer_docs_raw = []
    if not isinstance(peer_docs_raw, list):
        raise SweepError("input_error", "context_bundle_docs.peer_project_docs must be a list", stage="input")
    peer_docs: list[dict[str, str]] = []
    for idx, peer_row in enumerate(peer_docs_raw):
        if not isinstance(peer_row, dict):
            raise SweepError(
                "input_error",
                f"context_bundle_docs.peer_project_docs[{idx}] must be an object",
                stage="input",
            )
        project_id = _as_str(peer_row.get("project_id"))
        peer_path_raw = _as_str(peer_row.get("path"))
        if not project_id or not peer_path_raw:
            raise SweepError(
                "input_error",
                f"context_bundle_docs.peer_project_docs[{idx}] requires project_id and path",
                stage="input",
            )
        peer_path = _resolve_context_doc_path(peer_path_raw, base_dir=base_dir)
        peer_evidence_ref = _doc_evidence_ref("peer", peer_path, project_id=project_id)
        if not peer_path.is_file():
            raise SweepError(
                "peer_project_doc_missing",
                f"peer-project context doc missing for {project_id}: {peer_path}",
                stage="input",
                evidence_refs=[peer_evidence_ref],
            )
        peer_docs.append(
            {
                "project_id": project_id,
                "path": str(peer_path),
                "evidence_ref": peer_evidence_ref,
            }
        )

    return {
        "mission": {
            "path": str(mission_path),
            "evidence_ref": _doc_evidence_ref("mission", mission_path),
        },
        "scope": {
            "path": str(scope_path),
            "evidence_ref": _doc_evidence_ref("scope", scope_path),
        },
        "peer_project_docs": peer_docs,
    }


def _sorted_citation_refs(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row["citation_id"]) for row in rows if isinstance(row.get("citation_id"), str)]


def _append_obligation_or_open_risk(
    *,
    obligations: list[dict[str, Any]],
    open_risks: list[dict[str, Any]],
    obligation_id: str,
    summary: str,
    evidence_refs: list[str],
    risk_id: str,
    risk_summary: str,
) -> None:
    if evidence_refs:
        obligations.append(
            {
                "obligation_id": obligation_id,
                "summary": summary,
                "evidence_refs": evidence_refs,
            }
        )
        return
    open_risks.append(
        {
            "risk_id": risk_id,
            "summary": risk_summary,
            "evidence_refs": [],
        }
    )


def _build_context_bundle(
    *,
    checked_at_utc: str,
    analysis_anchors: tuple[str, ...] | list[str],
    broad_sweep_context: dict[str, Any],
    recommendation: dict[str, Any],
    source_references: list[dict[str, Any]],
    unhappy_paths: list[dict[str, Any]],
    context_docs: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "checked_at_utc": checked_at_utc,
        "analysis_anchors": [str(anchor) for anchor in analysis_anchors],
        "broad_sweep_context": broad_sweep_context,
        "recommendation_evidence_refs": list(recommendation.get("evidence_refs") or []),
        "source_reference_ids": _sorted_citation_refs(source_references),
        "unhappy_paths": unhappy_paths,
        "context_docs": context_docs,
    }


def _serialize_context_bundle(bundle: dict[str, Any]) -> str:
    return json.dumps(bundle, sort_keys=True, separators=(",", ":"))


def extract_deficit_and_need_signals(payload: dict[str, Any]) -> dict[str, Any]:
    now_utc = _parse_req014_now(payload)
    checked_at_utc = _to_iso_utc(now_utc)
    context_docs = _validate_context_bundle_docs(payload)
    thresholds = _coerce_req014_thresholds(payload)
    max_signals = _coerce_req014_max_signals(payload)
    target_project = _validate_req014_target_project(payload)
    broad_sweep_context = _validate_req014_broad_sweep_context(
        payload,
        target_project_id=target_project["project_id"],
    )
    deficits = _validate_req014_deficits(payload)

    target_tags = set(target_project["capability_tags"])
    scored_rows: list[dict[str, Any]] = []
    for row in deficits:
        matched_tags = [tag for tag in row["required_capability_tags"] if tag in target_tags]
        leverage_ratio = round(len(matched_tags) / len(row["required_capability_tags"]), 4)
        priority_score = round(row["impact_score"] * row["urgency_score"], 4)
        failed_criteria = _classify_req014_failed_criteria(
            impact_score=row["impact_score"],
            urgency_score=row["urgency_score"],
            leverage_ratio=leverage_ratio,
            thresholds=thresholds,
        )
        scored_rows.append(
            {
                **row,
                "matched_capability_tags": matched_tags,
                "leverage_ratio": leverage_ratio,
                "priority_score": priority_score,
                "failed_criteria": failed_criteria,
                "eligible": not failed_criteria,
            }
        )

    eligible_rows = sorted(
        [row for row in scored_rows if row["eligible"]],
        key=lambda row: (
            -float(row["priority_score"]),
            -float(row["impact_score"]),
            -float(row["urgency_score"]),
            str(row["deficit_id"]),
        ),
    )

    selected_rows = eligible_rows[:max_signals]
    selected_ids = {str(row["deficit_id"]) for row in selected_rows}

    need_signals: list[dict[str, Any]] = []
    evidence_references: list[dict[str, Any]] = []
    citation_counter = 0
    for idx, row in enumerate(selected_rows, start=1):
        signal_id = f"NEED-{idx:04d}"
        signal_evidence_refs: list[str] = []
        for upstream_ref in row["upstream_evidence_refs"]:
            citation_counter += 1
            citation_id = f"EVD-{citation_counter:04d}"
            signal_evidence_refs.append(citation_id)
            evidence_references.append(
                {
                    "citation_id": citation_id,
                    "signal_id": signal_id,
                    "deficit_id": row["deficit_id"],
                    "upstream_evidence_ref": upstream_ref,
                    "reason_code": "need_signal_supporting_evidence",
                }
            )
        need_signals.append(
            {
                "signal_id": signal_id,
                "deficit_id": row["deficit_id"],
                "summary": row["summary"],
                "impact_score": row["impact_score"],
                "urgency_score": row["urgency_score"],
                "priority_score": row["priority_score"],
                "required_capability_tags": row["required_capability_tags"],
                "matched_capability_tags": row["matched_capability_tags"],
                "leverage_ratio": row["leverage_ratio"],
                "evidence_refs": signal_evidence_refs,
                "reason_code": "eligible_need_signal",
            }
        )

    excluded_deficits: list[dict[str, Any]] = []
    for row in scored_rows:
        deficit_id = str(row["deficit_id"])
        if deficit_id in selected_ids:
            continue
        if row["eligible"]:
            failed_criteria = ["max_signals_cap_reached"]
            reason_code = "max_signals_cap_reached"
        else:
            failed_criteria = list(row["failed_criteria"])
            reason_code = failed_criteria[0] if len(failed_criteria) == 1 else "multiple_threshold_failures"
        excluded_deficits.append(
            {
                "deficit_id": deficit_id,
                "summary": row["summary"],
                "impact_score": row["impact_score"],
                "urgency_score": row["urgency_score"],
                "leverage_ratio": row["leverage_ratio"],
                "failed_criteria": failed_criteria,
                "reason_code": reason_code,
            }
        )

    all_evidence_refs = [str(row["citation_id"]) for row in evidence_references]
    cross_project_evidence_refs = list(broad_sweep_context["earth_sweep_evidence_refs"])
    earth_sweep_unhappy_paths = list(broad_sweep_context["unhappy_paths"])
    unhappy_path_evidence_refs = _dedupe_preserve_order(
        [
            evidence_ref
            for row in earth_sweep_unhappy_paths
            for evidence_ref in (row.get("evidence_refs") or [])
            if isinstance(evidence_ref, str)
        ]
    )
    recommendation_evidence_refs = _dedupe_preserve_order(
        all_evidence_refs + cross_project_evidence_refs + unhappy_path_evidence_refs
    )
    recommendation_decision = "prioritize_need_signals" if need_signals else "hold"

    obligations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    if broad_sweep_context["cross_project"]:
        _append_obligation_or_open_risk(
            obligations=obligations,
            open_risks=open_risks,
            obligation_id="OBL-NEED-0001",
            summary="Validate prioritized need signals against Earth-sweep cross-project evidence before execution.",
            evidence_refs=cross_project_evidence_refs,
            risk_id="RISK-NEED-0001",
            risk_summary="Cross-project need validation is unresolved because Earth-sweep evidence refs are missing.",
        )
        missing_projects = list(broad_sweep_context["projects_without_evidence_refs"])
        if missing_projects:
            open_risks.append(
                {
                    "risk_id": "RISK-NEED-0002",
                    "summary": (
                        "Earth-sweep evidence refs are missing for cross-project context rows: "
                        + ", ".join(missing_projects)
                    ),
                    "evidence_refs": [],
                }
            )
    else:
        open_risks.append(
            {
                "risk_id": "RISK-NEED-0003",
                "summary": "Cross-project inference is unresolved because fewer than two projects were provided.",
                "evidence_refs": [],
            }
        )

    recommendation = {
        "decision": recommendation_decision,
        "rationale": (
            f"Need-signal extraction evaluated {len(scored_rows)} deficit(s), "
            f"selected {len(need_signals)} high-leverage signal(s), and excluded "
            f"{len(excluded_deficits)} deficit(s)."
        ),
        "top_signal_id": need_signals[0]["signal_id"] if need_signals else None,
        "evidence_refs": recommendation_evidence_refs,
        "cross_project_context": broad_sweep_context,
        "obligations": obligations,
        "open_risks": open_risks,
    }

    totals = {
        "deficits": len(scored_rows),
        "eligible": len(eligible_rows),
        "signals": len(need_signals),
        "excluded": len(excluded_deficits),
        "evidence_references": len(evidence_references),
    }
    context_bundle = _build_context_bundle(
        checked_at_utc=checked_at_utc,
        analysis_anchors=REQ014_ANALYSIS_ANCHORS,
        broad_sweep_context=broad_sweep_context,
        recommendation=recommendation,
        source_references=evidence_references,
        unhappy_paths=earth_sweep_unhappy_paths,
        context_docs=context_docs,
    )
    context_bundle_serialized = _serialize_context_bundle(context_bundle)

    return {
        "ok": True,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "analysis_type": REQ014_ANALYSIS_TYPE,
        "checked_at_utc": checked_at_utc,
        "analysis_anchors": list(REQ014_ANALYSIS_ANCHORS),
        "target_project": target_project,
        "thresholds": thresholds,
        "max_signals": max_signals,
        "need_signals": need_signals,
        "excluded_deficits": excluded_deficits,
        "evidence_references": evidence_references,
        "unhappy_paths": earth_sweep_unhappy_paths,
        "context_bundle": context_bundle,
        "context_bundle_serialized": context_bundle_serialized,
        "recommendation": recommendation,
        "totals": totals,
    }


def run(payload: dict[str, Any]) -> dict[str, Any]:
    analysis_type = _as_str(payload.get("analysis_type"))
    if (
        analysis_type == REQ014_ANALYSIS_TYPE
        or isinstance(payload.get("deficits"), list)
        or isinstance(payload.get("target_project"), dict)
    ):
        return extract_deficit_and_need_signals(payload)
    raise SweepError(
        "input_error",
        "input-json mode currently supports only REQ-014 deficit and need signal extraction payloads",
        stage="input",
    )


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
    parser = argparse.ArgumentParser(
        description="Generate REQ-002/REQ-010 artifacts or run REQ-014 deficit-and-need signal extraction."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--earth-root", help="Earth ecosystem root path for REQ-002 manifest mode.")
    mode.add_argument("--input-json", help="REQ-014 JSON payload path or '-' for stdin.")
    parser.add_argument("--owner-username", default="", help="Owner username for non-owner path policy.")
    parser.add_argument("--output-json", default="", help="Optional output file path for manifest.")
    parser.add_argument("--json-pretty", action="store_true")
    return parser.parse_args(argv)


def _parse_input_json_payload(path: str) -> dict[str, Any]:
    raw = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise SweepError("input_error", "input must be a JSON object", stage="input")
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if _as_str(args.input_json):
        try:
            payload = _parse_input_json_payload(_as_str(args.input_json))
            out = run(payload)
            sys.stdout.write(_json_dumps(out, args.json_pretty))
            return 0 if out.get("ok") else 1
        except SweepError as exc:
            out = {
                "ok": False,
                "tool": TOOL,
                "tool_version": TOOL_VERSION,
                "reason_code": exc.code,
                "evidence_refs": exc.evidence_refs,
                "error": {"code": exc.code, "message": exc.message, "stage": exc.stage},
            }
            sys.stdout.write(_json_dumps(out, args.json_pretty))
            return 1
        except json.JSONDecodeError as exc:
            out = {
                "ok": False,
                "tool": TOOL,
                "tool_version": TOOL_VERSION,
                "reason_code": "input_error",
                "evidence_refs": [],
                "error": {"code": "input_error", "message": f"invalid JSON input: {exc}", "stage": "input"},
            }
            sys.stdout.write(_json_dumps(out, args.json_pretty))
            return 1

    _enforce_log_budget(LOG_ROOT)
    emit = _make_cli_emit(LOG_PATH)

    manifest = build_earth_repository_discovery_manifest(
        Path(_as_str(args.earth_root)),
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
