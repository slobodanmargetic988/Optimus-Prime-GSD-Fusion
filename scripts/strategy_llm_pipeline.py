#!/usr/bin/env python3
"""Contract/data-model surfaces for strategy LLM pipeline calls.

Implemented requirement surfaces:
- REQ-027 Call-2 ecosystem linkage reasoning.
- REQ-030 Call-5 sequencing and lane design reasoning.
- REQ-035 Evidence citation discipline in reasoning calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping


REQ_027_SCHEMA_VERSION = "req-027.call-2-ecosystem-linkage-reasoning.v1"
REQ_027_PROCESSING_SCHEMA_VERSION = "req-027.call-2-ecosystem-linkage-processing.v1"
REQ_027_REQUIREMENT_ID = "REQ-027"
REQ_027_ANALYSIS_TYPE = "call_2_ecosystem_linkage_reasoning"
REQ_027_CALL_ID = "call-2"

REQ_030_SCHEMA_VERSION = "req-030.call-5-sequencing-and-lane-design-reasoning.v1"
REQ_030_PROCESSING_SCHEMA_VERSION = "req-030.call-5-sequencing-and-lane-design-processing.v1"
REQ_030_REQUIREMENT_ID = "REQ-030"
REQ_030_ANALYSIS_TYPE = "call_5_sequencing_and_lane_design_reasoning"
REQ_030_CALL_ID = "call-5"

REQ_035_SCHEMA_VERSION = "req-035.evidence-citation-discipline-in-reasoning-calls.v1"
REQ_035_PROCESSING_SCHEMA_VERSION = "req-035.evidence-citation-discipline-in-reasoning-calls-processing.v1"
REQ_035_REQUIREMENT_ID = "REQ-035"
REQ_035_ANALYSIS_TYPE = "evidence_citation_discipline_in_reasoning_calls"
REQ_035_CALL_ID = "reasoning-calls"

_CONFIDENCE_TAGS = ("high", "medium", "low")
_DIRECTIONS = ("target_to_peer", "peer_to_target", "bidirectional")
_OBLIGATED_PARTIES = ("target", "peer", "both")
_RISK_LEVELS = ("high", "medium", "low")
_DEPENDS_ON_TYPES = ("recommendation", "external")
_LOG_CHECK_SENTINEL = ".log_size_check.json"
_MAX_LOG_BYTES = 3_000_000_000
_LLM_CALL_TRACE_SCHEMA_VERSION = "optimus-prime.llm-call-trace.v1"
_LLM_CALL_TRACE_RELATIVE_PATH = "strategy/current/llm_call_trace.jsonl"
_LLM_CALL_TRACE_ARTIFACTS_RELATIVE_DIR = "strategy/current/llm_call_trace_artifacts"
_REQ_027_CALL_2_OBJECTIVE = (
    "Reason about ecosystem links and interaction obligations between the target project and peer projects; "
    "distinguish existing links, missing links, and proposed links with confidence tags; "
    "surface evidence-backed cross-project obligations plus context gaps that block promotion."
)
_REQ_030_CALL_5_OBJECTIVE = (
    "Design execution lanes and sequencing order for recommendations under current constraints; "
    "include why-now rationale and expected coordination dependencies; "
    "gate cross-project obligations on Earth-sweep evidence refs and record unresolved ideas as open risks."
)
_REQ_035_CALL_OBJECTIVE = (
    "Enforce evidence citation discipline across reasoning calls; "
    "flag uncited or unknown-evidence strategic claims; "
    "exclude flagged claims from promoted recommendations and gate cross-project obligations on Earth-sweep evidence refs."
)


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _require_nonempty_text(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must be a non-empty string")
    return text


def _normalize_root(raw_path: Any, *, field_name: str) -> str:
    normalized = str(Path(_require_nonempty_text(raw_path, field_name=field_name)).expanduser().resolve())
    if not normalized.startswith("/"):
        raise ValueError(f"{field_name} must normalize to an absolute path")
    return normalized


def _normalize_string_list(raw_value: Any, *, field_name: str) -> list[str]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError(f"{field_name} must be a list of strings")
    normalized: set[str] = set()
    for index, item in enumerate(raw_value):
        normalized.add(_require_nonempty_text(item, field_name=f"{field_name}[{index}]"))
    return sorted(normalized)


def _normalize_direction(raw_value: Any, *, field_name: str) -> str:
    if raw_value is None:
        return "bidirectional"
    direction = _require_nonempty_text(raw_value, field_name=field_name).lower()
    if direction not in _DIRECTIONS:
        raise ValueError(f"{field_name} must be one of: {list(_DIRECTIONS)}")
    return direction


def _normalize_confidence_tag(raw_value: Any, *, field_name: str) -> str:
    if raw_value is None:
        raise ValueError(f"{field_name} must be set to one of: {list(_CONFIDENCE_TAGS)}")
    tag = _require_nonempty_text(raw_value, field_name=field_name).lower()
    if tag not in _CONFIDENCE_TAGS:
        raise ValueError(f"{field_name} must be one of: {list(_CONFIDENCE_TAGS)}")
    return tag


def _normalize_risk_level(raw_value: Any, *, field_name: str) -> str:
    if raw_value is None:
        raise ValueError(f"{field_name} must be set to one of: {list(_RISK_LEVELS)}")
    level = _require_nonempty_text(raw_value, field_name=field_name).lower()
    if level not in _RISK_LEVELS:
        raise ValueError(f"{field_name} must be one of: {list(_RISK_LEVELS)}")
    return level


def _stable_id_fragment(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _format_ts_line(message: str, *, now_utc: str | None = None) -> str:
    stamp = now_utc.strip() if isinstance(now_utc, str) and now_utc.strip() else _utc_timestamp()
    return f"[{stamp}] {message}"


def _default_log_dir() -> Path:
    return Path.home() / "projects" / "LOGS"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_llm_call_trace_path() -> Path:
    return _repo_root() / _LLM_CALL_TRACE_RELATIVE_PATH


def _default_llm_call_trace_artifacts_dir() -> Path:
    return _repo_root() / _LLM_CALL_TRACE_ARTIFACTS_RELATIVE_DIR


def _repo_relative_path(path: Path) -> str:
    return path.resolve().relative_to(_repo_root()).as_posix()


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_hex(payload: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _canonicalize(payload: Any) -> Any:
    return json.loads(_canonical_json_bytes(payload).decode("utf-8"))


def _write_json_artifact(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _append_jsonl_row(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")


def _best_effort_extract_string_refs(raw_value: Any) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, str):
        ref = raw_value.strip()
        return [ref] if ref else []
    if isinstance(raw_value, list):
        out: list[str] = []
        for item in raw_value:
            if item is None:
                continue
            ref = str(item).strip()
            if ref:
                out.append(ref)
        return out
    return []


def _trace_input_refs(
    *,
    earth_sweep_evidence_refs: list[str],
    cross_project_context: list[dict[str, Any]],
    earth_sweep_projects: list[dict[str, Any]],
) -> list[str]:
    refs: set[str] = set()
    refs.update(earth_sweep_evidence_refs)
    for row in cross_project_context:
        refs.update(_best_effort_extract_string_refs(row.get("evidence_refs")))
    for project in earth_sweep_projects:
        for obligation in project.get("obligations") or []:
            if not isinstance(obligation, Mapping):
                continue
            refs.update(_best_effort_extract_string_refs(obligation.get("earth_sweep_evidence_refs")))
            refs.update(_best_effort_extract_string_refs(obligation.get("evidence_refs")))
        for idea in project.get("unresolved_ideas") or []:
            if not isinstance(idea, Mapping):
                continue
            refs.update(_best_effort_extract_string_refs(idea.get("evidence_refs")))
    return sorted(refs)


def _handoff_summary_for_req_027_call_2(result: Mapping[str, Any]) -> str:
    totals = result.get("totals") if isinstance(result.get("totals"), Mapping) else {}
    behavior = result.get("processing_behavior") if isinstance(result.get("processing_behavior"), Mapping) else {}
    recommendation = behavior.get("recommendation") if isinstance(behavior.get("recommendation"), Mapping) else {}
    decision = str(recommendation.get("decision") or "").strip() or "unknown"
    confidence = str(recommendation.get("confidence") or "").strip() or "unknown"
    obligations = recommendation.get("cross_project_obligations") if isinstance(recommendation.get("cross_project_obligations"), list) else []
    risks = recommendation.get("open_risks") if isinstance(recommendation.get("open_risks"), list) else []
    return (
        f"{REQ_027_REQUIREMENT_ID} {REQ_027_CALL_ID} handoff: "
        f"decision={decision} confidence={confidence} "
        f"peers={int(totals.get('peer_projects') or 0)} "
        f"existing={int(totals.get('existing_links') or 0)} "
        f"missing={int(totals.get('missing_links') or 0)} "
        f"proposed={int(totals.get('proposed_links') or 0)} "
        f"obligations={len(obligations)} open_risks={len(risks)}"
    )


def _record_req_027_call_2_llm_call_trace(
    *,
    checked_at_utc: str,
    target_project: Mapping[str, Any],
    peer_projects: list[dict[str, Any]],
    earth_sweep_evidence_refs: list[str],
    earth_sweep_projects: list[dict[str, Any]],
    cross_project_context: list[dict[str, Any]],
    result: Mapping[str, Any],
    trace_path: Path | None = None,
    artifacts_dir: Path | None = None,
) -> dict[str, Any]:
    trace_file = trace_path or _default_llm_call_trace_path()
    artifacts_root = artifacts_dir or _default_llm_call_trace_artifacts_dir()
    peer_project_ids = sorted({str(row.get("project_id") or "").strip() for row in peer_projects if row.get("project_id")})

    input_snapshot = {
        "schema_version": "optimus-prime.req-027.call-2-input-snapshot.v1",
        "checked_at_utc": checked_at_utc,
        "requirement_id": REQ_027_REQUIREMENT_ID,
        "analysis_type": REQ_027_ANALYSIS_TYPE,
        "call_id": REQ_027_CALL_ID,
        "target_project": dict(target_project),
        "peer_projects": peer_projects,
        "broad_sweep_context": {
            "earth_sweep_evidence_refs": earth_sweep_evidence_refs,
            "earth_sweep_projects": earth_sweep_projects,
            "cross_project_context": cross_project_context,
        },
    }
    output_snapshot = {
        "schema_version": "optimus-prime.req-027.call-2-output-snapshot.v1",
        "checked_at_utc": checked_at_utc,
        "requirement_id": REQ_027_REQUIREMENT_ID,
        "analysis_type": REQ_027_ANALYSIS_TYPE,
        "call_id": REQ_027_CALL_ID,
        "result": dict(result),
    }

    input_digest = _sha256_hex(input_snapshot)
    output_digest = _sha256_hex(output_snapshot)
    bundle_dir = artifacts_root / "req-027" / "call-2" / input_digest[:16]
    input_path = bundle_dir / "input.normalized.json"
    output_path = bundle_dir / "output.normalized.json"
    _write_json_artifact(input_path, input_snapshot)
    _write_json_artifact(output_path, output_snapshot)

    input_refs = _trace_input_refs(
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        cross_project_context=cross_project_context,
        earth_sweep_projects=earth_sweep_projects,
    )
    behavior = result.get("processing_behavior") if isinstance(result.get("processing_behavior"), Mapping) else {}
    usage = behavior.get("context_usage") if isinstance(behavior.get("context_usage"), Mapping) else {}
    output_refs = sorted({str(ref) for ref in (usage.get("evidence_refs_used") or []) if str(ref).strip()})

    row = {
        "schema_version": _LLM_CALL_TRACE_SCHEMA_VERSION,
        "checked_at_utc": checked_at_utc,
        "requirement_id": REQ_027_REQUIREMENT_ID,
        "analysis_type": REQ_027_ANALYSIS_TYPE,
        "call_id": REQ_027_CALL_ID,
        "call_objective": _REQ_027_CALL_2_OBJECTIVE,
        "target_project_id": str(target_project.get("project_id") or "").strip(),
        "peer_project_ids": peer_project_ids,
        "input_refs": input_refs,
        "output_refs": output_refs,
        "artifacts": [
            {"kind": "input_snapshot", "path": str(input_path), "sha256": input_digest},
            {"kind": "output_snapshot", "path": str(output_path), "sha256": output_digest},
        ],
        "handoff_summary": _handoff_summary_for_req_027_call_2(result),
        "totals": dict(result.get("totals") or {}) if isinstance(result.get("totals"), Mapping) else {},
    }
    _append_jsonl_row(trace_file, row)
    return row


def _handoff_summary_for_req_030_call_5(result: Mapping[str, Any]) -> str:
    behavior = result.get("processing_behavior") if isinstance(result.get("processing_behavior"), Mapping) else {}
    recommendation = behavior.get("recommendation") if isinstance(behavior.get("recommendation"), Mapping) else {}
    decision = str(recommendation.get("decision") or "").strip() or "unknown"
    confidence = str(recommendation.get("confidence") or "").strip() or "unknown"
    obligations = recommendation.get("cross_project_obligations") if isinstance(recommendation.get("cross_project_obligations"), list) else []
    risks = recommendation.get("open_risks") if isinstance(recommendation.get("open_risks"), list) else []
    totals = result.get("totals") if isinstance(result.get("totals"), Mapping) else {}
    lanes = int(totals.get("lanes") or 0)
    sequence_items = int(totals.get("sequence_items") or 0)
    dependencies = int(totals.get("total_dependencies") or 0)
    return (
        f"{REQ_030_REQUIREMENT_ID} {REQ_030_CALL_ID} handoff: "
        f"decision={decision} confidence={confidence} "
        f"lanes={lanes} sequence_items={sequence_items} dependencies={dependencies} "
        "why_now=explicit coordination_dependencies=explicit "
        f"obligations={len(obligations)} open_risks={len(risks)}"
    )


def _req_030_canonical_input(
    *,
    checked_at_utc: str,
    target_project: Mapping[str, Any],
    constraints: Mapping[str, Any],
    recommendations: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "analysis_type": REQ_030_ANALYSIS_TYPE,
        "call_id": REQ_030_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "target_project": _canonicalize(target_project),
        "constraints": _canonicalize(constraints),
        "recommendations": _canonicalize(recommendations),
    }


def _req_030_canonical_processing_input(
    *,
    earth_sweep_evidence_refs: list[str],
    earth_sweep_projects: list[dict[str, Any]],
    cross_project_context: list[dict[str, Any]],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "earth_sweep_evidence_refs": _canonicalize(earth_sweep_evidence_refs),
        "earth_sweep_projects": _canonicalize(earth_sweep_projects),
        "cross_project_context": _canonicalize(cross_project_context),
        "sequencing_and_lane_design_reasoning": _canonicalize(
            result.get("sequencing_and_lane_design_reasoning") or {}
        ),
        "totals": _canonicalize(result.get("totals") or {}),
        "processing_behavior": _canonicalize(result.get("processing_behavior") or {}),
    }


def _record_req_030_call_5_llm_call_trace(
    *,
    checked_at_utc: str,
    target_project: Mapping[str, Any],
    constraints: Mapping[str, Any],
    recommendations: list[dict[str, Any]],
    earth_sweep_evidence_refs: list[str],
    earth_sweep_projects: list[dict[str, Any]],
    cross_project_context: list[dict[str, Any]],
    result: Mapping[str, Any],
    trace_path: Path | None = None,
    artifacts_dir: Path | None = None,
) -> dict[str, Any]:
    trace_file = trace_path or _default_llm_call_trace_path()
    artifacts_root = artifacts_dir or _default_llm_call_trace_artifacts_dir()

    input_snapshot = {
        "schema_version": "optimus-prime.req-030.call-5-input-snapshot.v1",
        "checked_at_utc": checked_at_utc,
        "requirement_id": REQ_030_REQUIREMENT_ID,
        "analysis_type": REQ_030_ANALYSIS_TYPE,
        "call_id": REQ_030_CALL_ID,
        "target_project": dict(target_project),
        "constraints": dict(constraints),
        "recommendations": [dict(row) for row in recommendations],
        "broad_sweep_context": {
            "earth_sweep_evidence_refs": list(earth_sweep_evidence_refs),
            "earth_sweep_projects": earth_sweep_projects,
            "cross_project_context": cross_project_context,
        },
    }
    output_snapshot = {
        "schema_version": "optimus-prime.req-030.call-5-output-snapshot.v1",
        "checked_at_utc": checked_at_utc,
        "requirement_id": REQ_030_REQUIREMENT_ID,
        "analysis_type": REQ_030_ANALYSIS_TYPE,
        "call_id": REQ_030_CALL_ID,
        "result": dict(result),
    }

    input_digest = _sha256_hex(input_snapshot)
    output_digest = _sha256_hex(output_snapshot)
    bundle_dir = artifacts_root / "req-030" / "call-5" / input_digest[:16]
    input_path = bundle_dir / "input.normalized.json"
    output_path = bundle_dir / "output.normalized.json"
    _write_json_artifact(input_path, input_snapshot)
    _write_json_artifact(output_path, output_snapshot)

    input_refs = _trace_input_refs(
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        cross_project_context=cross_project_context,
        earth_sweep_projects=earth_sweep_projects,
    )
    recommendation = {}
    if isinstance(result.get("processing_behavior"), Mapping):
        recommendation = result["processing_behavior"].get("recommendation") or {}
    output_refs = [
        f"{REQ_030_REQUIREMENT_ID}::call::{REQ_030_CALL_ID}::output::sequencing_and_lane_design_reasoning",
        f"{REQ_030_REQUIREMENT_ID}::call::{REQ_030_CALL_ID}::output::recommended_actions",
        _repo_relative_path(output_path),
    ]
    if isinstance(recommendation, Mapping) and recommendation.get("cross_project_obligations"):
        output_refs.append(f"{REQ_030_REQUIREMENT_ID}::call::{REQ_030_CALL_ID}::output::cross_project_obligations")
    if isinstance(recommendation, Mapping) and recommendation.get("open_risks"):
        output_refs.append(f"{REQ_030_REQUIREMENT_ID}::call::{REQ_030_CALL_ID}::output::open_risks")

    row = {
        "schema_version": _LLM_CALL_TRACE_SCHEMA_VERSION,
        "checked_at_utc": checked_at_utc,
        "requirement_id": REQ_030_REQUIREMENT_ID,
        "analysis_type": REQ_030_ANALYSIS_TYPE,
        "call_id": REQ_030_CALL_ID,
        "call_objective": _REQ_030_CALL_5_OBJECTIVE,
        "target_project_id": str(target_project.get("project_id") or "").strip(),
        "peer_project_ids": sorted({str(row.get("project_id") or "").strip() for row in cross_project_context if row.get("project_id")}),
        "input_refs": input_refs,
        "output_refs": sorted(set(output_refs)),
        "artifacts": [
            {"kind": "input_snapshot", "path": _repo_relative_path(input_path), "sha256": input_digest},
            {"kind": "output_snapshot", "path": _repo_relative_path(output_path), "sha256": output_digest},
        ],
        "handoff_summary": _handoff_summary_for_req_030_call_5(result),
        "totals": dict(result.get("totals") or {}) if isinstance(result.get("totals"), Mapping) else {},
    }
    _append_jsonl_row(trace_file, row)
    return row


def _handoff_summary_for_req_035_reasoning_call(
    *,
    call_id: str,
    call_totals: Mapping[str, Any],
    call_actions_count: int,
    overall_recommendation: Mapping[str, Any],
) -> str:
    decision = str(overall_recommendation.get("decision") or "").strip() or "unknown"
    confidence = str(overall_recommendation.get("confidence") or "").strip() or "unknown"
    return (
        f"{REQ_035_REQUIREMENT_ID} {call_id} handoff: "
        f"decision={decision} confidence={confidence} "
        f"strategic_claims={int(call_totals.get('strategic_claims') or 0)} "
        f"cited_claims={int(call_totals.get('cited_claims') or 0)} "
        f"flagged_claims={int(call_totals.get('flagged_claims') or 0)} "
        f"final_recommendations={int(call_totals.get('final_recommendations') or 0)} "
        f"promoted_actions={call_actions_count}"
    )


def _req_035_canonical_input(
    *,
    checked_at_utc: str,
    context_provenance_ledger: Mapping[str, Any],
    reasoning_calls: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "analysis_type": REQ_035_ANALYSIS_TYPE,
        "call_id": REQ_035_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "context_provenance_ledger": _canonicalize(context_provenance_ledger),
        "reasoning_calls": _canonicalize(reasoning_calls),
    }


def _req_035_canonical_processing_input(
    *,
    earth_sweep_evidence_refs: list[str],
    earth_sweep_projects: list[dict[str, Any]],
    cross_project_context: list[dict[str, Any]],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "earth_sweep_evidence_refs": _canonicalize(earth_sweep_evidence_refs),
        "earth_sweep_projects": _canonicalize(earth_sweep_projects),
        "cross_project_context": _canonicalize(cross_project_context),
        "evidence_citation_discipline": _canonicalize(result.get("evidence_citation_discipline") or {}),
        "totals": _canonicalize(result.get("totals") or {}),
        "processing_behavior": _canonicalize(result.get("processing_behavior") or {}),
    }


def _record_req_035_reasoning_calls_llm_call_trace(
    *,
    checked_at_utc: str,
    context_provenance_ledger: Mapping[str, Any],
    reasoning_calls: list[dict[str, Any]],
    earth_sweep_evidence_refs: list[str],
    earth_sweep_projects: list[dict[str, Any]],
    cross_project_context: list[dict[str, Any]],
    result: Mapping[str, Any],
    trace_path: Path | None = None,
    artifacts_dir: Path | None = None,
) -> list[dict[str, Any]]:
    trace_file = trace_path or _default_llm_call_trace_path()
    artifacts_root = artifacts_dir or _default_llm_call_trace_artifacts_dir()

    trace_input_refs = _trace_input_refs(
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        cross_project_context=cross_project_context,
        earth_sweep_projects=earth_sweep_projects,
    )
    ledger_refs = {
        str(ref)
        for ref in (context_provenance_ledger.get("evidence_ids") or [])
        if isinstance(ref, str) and ref.strip()
    }

    discipline = result.get("evidence_citation_discipline")
    discipline_map = discipline if isinstance(discipline, Mapping) else {}
    status_rows = discipline_map.get("strategic_claim_citation_status")
    flagged_rows = discipline_map.get("flagged_claims")
    final_rows = discipline_map.get("final_recommendations")
    status_rows = status_rows if isinstance(status_rows, list) else []
    flagged_rows = flagged_rows if isinstance(flagged_rows, list) else []
    final_rows = final_rows if isinstance(final_rows, list) else []

    behavior = result.get("processing_behavior")
    behavior_map = behavior if isinstance(behavior, Mapping) else {}
    recommendation = behavior_map.get("recommendation")
    recommendation_map = recommendation if isinstance(recommendation, Mapping) else {}
    recommended_actions = recommendation_map.get("recommended_actions")
    recommended_actions = recommended_actions if isinstance(recommended_actions, list) else []

    call_rows: list[dict[str, Any]] = []
    for call in sorted(reasoning_calls, key=lambda row: str(row.get("call_id") or "")):
        call_id = str(call.get("call_id") or "").strip()
        if not call_id:
            continue
        call_claims = call.get("strategic_claims")
        call_claims = call_claims if isinstance(call_claims, list) else []
        claim_evidence_refs = {
            str(ref).strip()
            for claim in call_claims
            if isinstance(claim, Mapping)
            for ref in (claim.get("evidence_ids") or [])
            if isinstance(ref, str) and ref.strip()
        }
        call_input_refs = sorted(set(trace_input_refs) | ledger_refs | claim_evidence_refs)

        call_status_rows = [
            row for row in status_rows if isinstance(row, Mapping) and str(row.get("call_id") or "").strip() == call_id
        ]
        call_flagged_rows = [
            row for row in flagged_rows if isinstance(row, Mapping) and str(row.get("call_id") or "").strip() == call_id
        ]
        call_final_rows = [
            row for row in final_rows if isinstance(row, Mapping) and str(row.get("call_id") or "").strip() == call_id
        ]
        call_actions = [
            row
            for row in recommended_actions
            if isinstance(row, Mapping) and str(row.get("call_id") or "").strip() == call_id
        ]
        call_actions = sorted(call_actions, key=lambda row: (str(row.get("recommendation_id") or ""), str(row.get("action_id") or "")))

        call_totals = {
            "reasoning_calls": 1,
            "strategic_claims": len(call_status_rows),
            "cited_claims": sum(1 for row in call_status_rows if str(row.get("citation_status") or "") == "cited"),
            "flagged_claims": len(call_flagged_rows),
            "final_recommendations": len(call_final_rows),
        }

        input_snapshot = {
            "schema_version": "optimus-prime.req-035.reasoning-call-input-snapshot.v1",
            "checked_at_utc": checked_at_utc,
            "requirement_id": REQ_035_REQUIREMENT_ID,
            "analysis_type": REQ_035_ANALYSIS_TYPE,
            "call_id": call_id,
            "context_provenance_ledger": dict(context_provenance_ledger),
            "reasoning_call": dict(call),
            "broad_sweep_context": {
                "earth_sweep_evidence_refs": list(earth_sweep_evidence_refs),
                "earth_sweep_projects": earth_sweep_projects,
                "cross_project_context": cross_project_context,
            },
        }
        output_snapshot = {
            "schema_version": "optimus-prime.req-035.reasoning-call-output-snapshot.v1",
            "checked_at_utc": checked_at_utc,
            "requirement_id": REQ_035_REQUIREMENT_ID,
            "analysis_type": REQ_035_ANALYSIS_TYPE,
            "call_id": call_id,
            "result": {
                "evidence_citation_discipline": {
                    "strategic_claim_citation_status": call_status_rows,
                    "flagged_claims": call_flagged_rows,
                    "final_recommendations": call_final_rows,
                },
                "recommended_actions": call_actions,
                "totals": call_totals,
            },
        }

        input_digest = _sha256_hex(input_snapshot)
        output_digest = _sha256_hex(output_snapshot)
        bundle_dir = artifacts_root / "req-035" / call_id / input_digest[:16]
        input_path = bundle_dir / "input.normalized.json"
        output_path = bundle_dir / "output.normalized.json"
        _write_json_artifact(input_path, input_snapshot)
        _write_json_artifact(output_path, output_snapshot)

        output_refs = [
            f"{REQ_035_REQUIREMENT_ID}::call::{call_id}::output::strategic_claim_citation_status",
            _repo_relative_path(output_path),
        ]
        if call_flagged_rows:
            output_refs.append(f"{REQ_035_REQUIREMENT_ID}::call::{call_id}::output::flagged_claims")
        if call_final_rows:
            output_refs.append(f"{REQ_035_REQUIREMENT_ID}::call::{call_id}::output::final_recommendations")
        if call_actions:
            output_refs.append(f"{REQ_035_REQUIREMENT_ID}::call::{call_id}::output::recommended_actions")

        row = {
            "schema_version": _LLM_CALL_TRACE_SCHEMA_VERSION,
            "checked_at_utc": checked_at_utc,
            "requirement_id": REQ_035_REQUIREMENT_ID,
            "analysis_type": REQ_035_ANALYSIS_TYPE,
            "call_id": call_id,
            "call_objective": _REQ_035_CALL_OBJECTIVE,
            "target_project_id": "",
            "peer_project_ids": sorted(
                {str(item.get("project_id") or "").strip() for item in cross_project_context if item.get("project_id")}
            ),
            "input_refs": call_input_refs,
            "output_refs": sorted(set(output_refs)),
            "artifacts": [
                {"kind": "input_snapshot", "path": _repo_relative_path(input_path), "sha256": input_digest},
                {"kind": "output_snapshot", "path": _repo_relative_path(output_path), "sha256": output_digest},
            ],
            "handoff_summary": _handoff_summary_for_req_035_reasoning_call(
                call_id=call_id,
                call_totals=call_totals,
                call_actions_count=len(call_actions),
                overall_recommendation=recommendation_map,
            ),
            "totals": call_totals,
        }
        _append_jsonl_row(trace_file, row)
        call_rows.append(row)

    return call_rows


def _tail_file(path: Path, *, keep_bytes: int) -> bytes:
    if keep_bytes <= 0:
        return b""
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        handle.seek(max(0, size - keep_bytes), os.SEEK_SET)
        return handle.read()


def _maybe_truncate_large_logs(log_dir: Path, *, now_utc: str | None = None) -> None:
    """Best-effort log truncation guardrail.

    Only checks periodically (sentinel file) and truncates any single log file
    exceeding ~3GB by keeping the tail so debugging remains possible.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    sentinel = log_dir / _LOG_CHECK_SENTINEL
    now_epoch = int(time.time())
    check_interval_seconds = 6 * 60 * 60  # 6 hours
    last_checked = 0
    if sentinel.exists():
        try:
            payload = json.loads(sentinel.read_text(encoding="utf-8"))
            last_checked = int(payload.get("last_checked_epoch") or 0)
        except (OSError, ValueError, TypeError):
            last_checked = 0

    if last_checked and now_epoch - last_checked < check_interval_seconds:
        return

    checked_files: list[dict[str, Any]] = []
    for path in sorted(log_dir.glob("*.log")):
        try:
            size = path.stat().st_size
        except OSError:
            continue
        truncated = False
        if size > _MAX_LOG_BYTES:
            keep_bytes = 25_000_000  # keep last ~25MB
            try:
                tail = _tail_file(path, keep_bytes=keep_bytes)
                path.write_bytes(tail)
                truncated = True
                size = len(tail)
            except OSError:
                continue
        checked_files.append({"path": str(path), "size_bytes": size, "truncated": truncated})

    sentinel.write_text(
        json.dumps(
            {
                "checked_at_utc": (now_utc or _utc_timestamp()),
                "last_checked_epoch": now_epoch,
                "max_log_bytes": _MAX_LOG_BYTES,
                "files_checked": checked_files,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def make_log_emitter(
    *,
    log_name: str,
    log_dir: Path | None = None,
    now_utc: str | None = None,
) -> Callable[[str], None]:
    """Return an emitter that appends timestamped lines under `~/projects/LOGS/`."""
    directory = log_dir or _default_log_dir()
    _maybe_truncate_large_logs(directory, now_utc=now_utc)
    target = directory / f"{log_name}.log"
    target.parent.mkdir(parents=True, exist_ok=True)

    def emit(message: str) -> None:
        line = _format_ts_line(str(message), now_utc=now_utc)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    return emit


def _normalize_target_project(raw_value: Any) -> dict[str, str]:
    target = _require_mapping(raw_value, field_name="target_project")
    project_id = _require_nonempty_text(target.get("project_id"), field_name="target_project.project_id")
    project_root = _normalize_root(target.get("project_root"), field_name="target_project.project_root")
    normalized = {"project_id": project_id, "project_root": project_root}
    extra = sorted(set(target.keys()) - set(normalized.keys()))
    if extra:
        raise ValueError(f"target_project has unexpected keys: {extra}")
    return normalized


def _normalize_peer_projects(raw_value: Any) -> list[dict[str, str]]:
    if not isinstance(raw_value, list) or not raw_value:
        raise ValueError("peer_projects must be a non-empty list")
    peers: list[dict[str, str]] = []
    for index, item in enumerate(raw_value):
        peer = _require_mapping(item, field_name=f"peer_projects[{index}]")
        project_id = _require_nonempty_text(peer.get("project_id"), field_name=f"peer_projects[{index}].project_id")
        project_root = _normalize_root(peer.get("project_root"), field_name=f"peer_projects[{index}].project_root")
        row = {"project_id": project_id, "project_root": project_root}
        extra = sorted(set(peer.keys()) - set(row.keys()))
        if extra:
            raise ValueError(f"peer_projects[{index}] has unexpected keys: {extra}")
        peers.append(row)
    peers.sort(key=lambda row: row["project_id"])
    return peers


def _normalize_req_030_constraints(raw_value: Any) -> dict[str, Any]:
    if raw_value is None:
        raise ValueError("constraints must be an object")
    constraints = _require_mapping(raw_value, field_name="constraints")
    max_parallel_lanes = constraints.get("max_parallel_lanes")
    if not isinstance(max_parallel_lanes, int) or max_parallel_lanes <= 0:
        raise ValueError("constraints.max_parallel_lanes must be a positive integer")
    max_active_work_items = constraints.get("max_active_work_items")
    if not isinstance(max_active_work_items, int) or max_active_work_items <= 0:
        raise ValueError("constraints.max_active_work_items must be a positive integer")
    notes = _normalize_string_list(constraints.get("notes"), field_name="constraints.notes")
    normalized = {
        "max_parallel_lanes": max_parallel_lanes,
        "max_active_work_items": max_active_work_items,
        "notes": notes,
    }
    extra = sorted(set(constraints.keys()) - set(normalized.keys()))
    if extra:
        raise ValueError(f"constraints has unexpected keys: {extra}")
    return normalized


def _normalize_req_030_recommendations(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        raise ValueError("recommendations must be a list")
    if not isinstance(raw_value, list):
        raise ValueError("recommendations must be a list")
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_value):
        rec = _require_mapping(item, field_name=f"recommendations[{idx}]")
        recommendation_id = _require_nonempty_text(
            rec.get("recommendation_id"),
            field_name=f"recommendations[{idx}].recommendation_id",
        )
        if recommendation_id in seen:
            raise ValueError(
                f"recommendations[{idx}].recommendation_id must be unique (duplicate: {recommendation_id})"
            )
        seen.add(recommendation_id)
        summary = _require_nonempty_text(rec.get("summary"), field_name=f"recommendations[{idx}].summary")
        rationale = _require_nonempty_text(rec.get("rationale"), field_name=f"recommendations[{idx}].rationale")
        expected_impact = _require_nonempty_text(
            rec.get("expected_impact"),
            field_name=f"recommendations[{idx}].expected_impact",
        )
        risk_level = _normalize_risk_level(rec.get("risk_level"), field_name=f"recommendations[{idx}].risk_level")
        row = {
            "recommendation_id": recommendation_id,
            "summary": summary,
            "rationale": rationale,
            "expected_impact": expected_impact,
            "risk_level": risk_level,
        }
        extra = sorted(set(rec.keys()) - set(row.keys()))
        if extra:
            raise ValueError(f"recommendations[{idx}] has unexpected keys: {extra}")
        normalized.append(row)
    normalized.sort(key=lambda r: r["recommendation_id"])
    return normalized


def _normalize_req_030_coordination_dependencies(
    raw_value: Any,
    *,
    field_name: str,
    target_project_id: str,
    parent_kind: str,
    parent_id: str,
    recommendation_ids: set[str],
) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError(f"{field_name} must be a list")
    deps: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_value):
        dep = _require_mapping(item, field_name=f"{field_name}[{idx}]")
        dependency_kind = _require_nonempty_text(
            dep.get("dependency_kind"),
            field_name=f"{field_name}[{idx}].dependency_kind",
        )
        depends_on = _require_nonempty_text(dep.get("depends_on"), field_name=f"{field_name}[{idx}].depends_on")
        summary = _require_nonempty_text(dep.get("summary"), field_name=f"{field_name}[{idx}].summary")
        depends_on_type = "recommendation" if depends_on in recommendation_ids else "external"
        dependency_id = (
            f"dep.{_stable_id_fragment(target_project_id, parent_kind, parent_id, depends_on_type, depends_on, dependency_kind, summary)}"
        )
        row = {
            "dependency_id": dependency_id,
            "dependency_kind": dependency_kind,
            "depends_on_type": depends_on_type,
            "depends_on": depends_on,
            "summary": summary,
        }
        extra = sorted(set(dep.keys()) - {"dependency_kind", "depends_on", "summary"})
        if extra:
            raise ValueError(f"{field_name}[{idx}] has unexpected keys: {extra}")
        deps.append(row)
    deps.sort(key=lambda d: (d["depends_on_type"], d["depends_on"], d["dependency_kind"], d["dependency_id"]))
    return deps


def _normalize_req_030_lanes(
    raw_value: Any,
    *,
    target_project_id: str,
    recommendation_ids: set[str],
) -> list[dict[str, Any]]:
    if raw_value is None:
        raise ValueError("lanes must be a list")
    if not isinstance(raw_value, list):
        raise ValueError("lanes must be a list")
    lanes: list[dict[str, Any]] = []
    lane_names_seen: set[str] = set()
    for idx, item in enumerate(raw_value):
        lane = _require_mapping(item, field_name=f"lanes[{idx}]")
        lane_name = _require_nonempty_text(lane.get("lane_name"), field_name=f"lanes[{idx}].lane_name")
        if lane_name in lane_names_seen:
            raise ValueError(f"lanes[{idx}].lane_name must be unique (duplicate: {lane_name})")
        lane_names_seen.add(lane_name)
        lane_kind = _require_nonempty_text(lane.get("lane_kind"), field_name=f"lanes[{idx}].lane_kind")
        lane_goal = _require_nonempty_text(lane.get("lane_goal"), field_name=f"lanes[{idx}].lane_goal")
        why_now = _require_nonempty_text(lane.get("why_now"), field_name=f"lanes[{idx}].why_now")
        raw_recommendation_ids = lane.get("recommendation_ids")
        if not isinstance(raw_recommendation_ids, list) or not raw_recommendation_ids:
            raise ValueError(f"lanes[{idx}].recommendation_ids must be a non-empty list of recommendation ids")
        normalized_rec_ids: list[str] = []
        for ridx, rec_id in enumerate(raw_recommendation_ids):
            rec_text = _require_nonempty_text(rec_id, field_name=f"lanes[{idx}].recommendation_ids[{ridx}]")
            if rec_text not in recommendation_ids:
                raise ValueError(f"lanes[{idx}].recommendation_ids[{ridx}] must be declared in recommendations")
            normalized_rec_ids.append(rec_text)
        normalized_rec_ids = sorted(set(normalized_rec_ids))
        lane_id = f"lane.{_stable_id_fragment(target_project_id, lane_name)}"
        coordination_dependencies = _normalize_req_030_coordination_dependencies(
            lane.get("coordination_dependencies"),
            field_name=f"lanes[{idx}].coordination_dependencies",
            target_project_id=target_project_id,
            parent_kind="lane",
            parent_id=lane_id,
            recommendation_ids=recommendation_ids,
        )
        row = {
            "lane_id": lane_id,
            "lane_name": lane_name,
            "lane_kind": lane_kind,
            "lane_goal": lane_goal,
            "why_now": why_now,
            "recommendation_ids": normalized_rec_ids,
            "coordination_dependencies": coordination_dependencies,
        }
        extra = sorted(
            set(lane.keys())
            - {
                "lane_name",
                "lane_kind",
                "lane_goal",
                "why_now",
                "recommendation_ids",
                "coordination_dependencies",
            }
        )
        if extra:
            raise ValueError(f"lanes[{idx}] has unexpected keys: {extra}")
        lanes.append(row)
    lanes.sort(key=lambda l: (l["lane_name"], l["lane_id"]))
    return lanes


def _normalize_req_030_sequence(
    raw_value: Any,
    *,
    target_project_id: str,
    lanes_by_name: Mapping[str, Mapping[str, Any]],
    recommendation_ids: set[str],
) -> list[dict[str, Any]]:
    if raw_value is None:
        raise ValueError("sequence must be a list")
    if not isinstance(raw_value, list):
        raise ValueError("sequence must be a list")
    sequence_rows: list[dict[str, Any]] = []
    orders_seen: set[int] = set()
    recommendation_seen: set[str] = set()
    for idx, item in enumerate(raw_value):
        row = _require_mapping(item, field_name=f"sequence[{idx}]")
        order = row.get("order")
        if not isinstance(order, int) or order <= 0:
            raise ValueError(f"sequence[{idx}].order must be a positive integer")
        if order in orders_seen:
            raise ValueError(f"sequence[{idx}].order must be unique (duplicate: {order})")
        orders_seen.add(order)
        recommendation_id = _require_nonempty_text(
            row.get("recommendation_id"),
            field_name=f"sequence[{idx}].recommendation_id",
        )
        if recommendation_id not in recommendation_ids:
            raise ValueError(f"sequence[{idx}].recommendation_id must be declared in recommendations")
        if recommendation_id in recommendation_seen:
            raise ValueError(f"sequence[{idx}].recommendation_id must be unique (duplicate: {recommendation_id})")
        recommendation_seen.add(recommendation_id)
        lane_name = _require_nonempty_text(row.get("lane_name"), field_name=f"sequence[{idx}].lane_name")
        if lane_name not in lanes_by_name:
            raise ValueError(f"sequence[{idx}].lane_name must match a declared lane")
        why_now = _require_nonempty_text(row.get("why_now"), field_name=f"sequence[{idx}].why_now")
        lane_id = str(lanes_by_name[lane_name].get("lane_id") or "").strip()
        if not lane_id:
            raise ValueError("internal error: lane_id missing while normalizing sequence")
        sequence_id = f"seq.{_stable_id_fragment(target_project_id, recommendation_id, lane_id, str(order))}"
        coordination_dependencies = _normalize_req_030_coordination_dependencies(
            row.get("coordination_dependencies"),
            field_name=f"sequence[{idx}].coordination_dependencies",
            target_project_id=target_project_id,
            parent_kind="sequence_item",
            parent_id=sequence_id,
            recommendation_ids=recommendation_ids,
        )
        normalized = {
            "sequence_id": sequence_id,
            "order": order,
            "recommendation_id": recommendation_id,
            "lane_id": lane_id,
            "lane_name": lane_name,
            "why_now": why_now,
            "coordination_dependencies": coordination_dependencies,
        }
        extra = sorted(
            set(row.keys()) - {"order", "recommendation_id", "lane_name", "why_now", "coordination_dependencies"}
        )
        if extra:
            raise ValueError(f"sequence[{idx}] has unexpected keys: {extra}")
        sequence_rows.append(normalized)
    sequence_rows.sort(key=lambda r: r["order"])
    return sequence_rows


def _normalize_req_035_context_provenance_ledger(raw_value: Any) -> dict[str, Any]:
    ledger = _require_mapping(raw_value, field_name="context_provenance_ledger")
    ledger_requirement_id = _require_nonempty_text(
        ledger.get("ledger_requirement_id"),
        field_name="context_provenance_ledger.ledger_requirement_id",
    )
    ledger_scope = _require_nonempty_text(
        ledger.get("ledger_scope"),
        field_name="context_provenance_ledger.ledger_scope",
    )
    raw_evidence_ids = ledger.get("evidence_ids")
    if not isinstance(raw_evidence_ids, list) or not raw_evidence_ids:
        raise ValueError("context_provenance_ledger.evidence_ids must be a non-empty list of evidence ids")
    evidence_ids: list[str] = []
    for idx, raw_id in enumerate(raw_evidence_ids):
        evidence_id = _require_nonempty_text(
            raw_id,
            field_name=f"context_provenance_ledger.evidence_ids[{idx}]",
        )
        if not evidence_id.startswith("claim-"):
            raise ValueError(
                f"context_provenance_ledger.evidence_ids[{idx}] must use REQ-021 claim id format (claim-<id>)"
            )
        evidence_ids.append(evidence_id)
    normalized = {
        "ledger_requirement_id": ledger_requirement_id,
        "ledger_scope": ledger_scope,
        "evidence_ids": sorted(set(evidence_ids)),
    }
    extra = sorted(set(ledger.keys()) - set(normalized.keys()))
    if extra:
        raise ValueError(f"context_provenance_ledger has unexpected keys: {extra}")
    return normalized


def _normalize_req_035_recommendation(raw_value: Any, *, field_name: str) -> dict[str, str]:
    recommendation = _require_mapping(raw_value, field_name=field_name)
    recommendation_id = _require_nonempty_text(
        recommendation.get("recommendation_id"),
        field_name=f"{field_name}.recommendation_id",
    )
    summary = _require_nonempty_text(
        recommendation.get("summary"),
        field_name=f"{field_name}.summary",
    )
    rationale = _require_nonempty_text(
        recommendation.get("rationale"),
        field_name=f"{field_name}.rationale",
    )
    confidence_tag = _normalize_confidence_tag(
        recommendation.get("confidence_tag"),
        field_name=f"{field_name}.confidence_tag",
    )
    normalized = {
        "recommendation_id": recommendation_id,
        "summary": summary,
        "rationale": rationale,
        "confidence_tag": confidence_tag,
    }
    extra = sorted(set(recommendation.keys()) - set(normalized.keys()))
    if extra:
        raise ValueError(f"{field_name} has unexpected keys: {extra}")
    return normalized


def _normalize_req_035_reasoning_calls(raw_value: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_value, list) or not raw_value:
        raise ValueError("reasoning_calls must be a non-empty list")

    calls: list[dict[str, Any]] = []
    seen_call_ids: set[str] = set()
    seen_recommendation_ids: set[str] = set()
    for cidx, item in enumerate(raw_value):
        call = _require_mapping(item, field_name=f"reasoning_calls[{cidx}]")
        call_id = _require_nonempty_text(call.get("call_id"), field_name=f"reasoning_calls[{cidx}].call_id")
        if call_id in seen_call_ids:
            raise ValueError(f"reasoning_calls[{cidx}].call_id must be unique (duplicate: {call_id})")
        seen_call_ids.add(call_id)

        raw_claims = call.get("strategic_claims")
        if not isinstance(raw_claims, list) or not raw_claims:
            raise ValueError(f"reasoning_calls[{cidx}].strategic_claims must be a non-empty list")

        claims: list[dict[str, Any]] = []
        seen_claim_ids: set[str] = set()
        for sidx, raw_claim in enumerate(raw_claims):
            claim = _require_mapping(raw_claim, field_name=f"reasoning_calls[{cidx}].strategic_claims[{sidx}]")
            strategic_claim_id = _require_nonempty_text(
                claim.get("strategic_claim_id"),
                field_name=f"reasoning_calls[{cidx}].strategic_claims[{sidx}].strategic_claim_id",
            )
            if strategic_claim_id in seen_claim_ids:
                raise ValueError(
                    f"reasoning_calls[{cidx}].strategic_claims[{sidx}].strategic_claim_id must be unique within call "
                    f"(duplicate: {strategic_claim_id})"
                )
            seen_claim_ids.add(strategic_claim_id)
            summary = _require_nonempty_text(
                claim.get("summary"),
                field_name=f"reasoning_calls[{cidx}].strategic_claims[{sidx}].summary",
            )

            evidence_ids: list[str] = []
            if claim.get("evidence_ids") is None:
                evidence_ids = []
            else:
                raw_evidence_ids = claim.get("evidence_ids")
                if not isinstance(raw_evidence_ids, list):
                    raise ValueError(
                        f"reasoning_calls[{cidx}].strategic_claims[{sidx}].evidence_ids must be a list of evidence ids"
                    )
                for evidx, raw_id in enumerate(raw_evidence_ids):
                    evidence_ids.append(
                        _require_nonempty_text(
                            raw_id,
                            field_name=f"reasoning_calls[{cidx}].strategic_claims[{sidx}].evidence_ids[{evidx}]",
                        )
                    )
            recommendation = _normalize_req_035_recommendation(
                claim.get("recommendation"),
                field_name=f"reasoning_calls[{cidx}].strategic_claims[{sidx}].recommendation",
            )
            recommendation_id = recommendation["recommendation_id"]
            if recommendation_id in seen_recommendation_ids:
                raise ValueError(
                    "reasoning_calls[*].strategic_claims[*].recommendation.recommendation_id must be globally unique "
                    f"(duplicate: {recommendation_id})"
                )
            seen_recommendation_ids.add(recommendation_id)
            normalized_claim = {
                "strategic_claim_id": strategic_claim_id,
                "summary": summary,
                "evidence_ids": sorted(set(evidence_ids)),
                "recommendation": recommendation,
            }
            extra_claim = sorted(set(claim.keys()) - set(normalized_claim.keys()))
            if extra_claim:
                raise ValueError(f"reasoning_calls[{cidx}].strategic_claims[{sidx}] has unexpected keys: {extra_claim}")
            claims.append(normalized_claim)
        claims.sort(key=lambda row: row["strategic_claim_id"])
        normalized_call = {"call_id": call_id, "strategic_claims": claims}
        extra_call = sorted(set(call.keys()) - set(normalized_call.keys()))
        if extra_call:
            raise ValueError(f"reasoning_calls[{cidx}] has unexpected keys: {extra_call}")
        calls.append(normalized_call)
    calls.sort(key=lambda row: row["call_id"])
    return calls


def _normalize_interaction_obligations(
    raw_value: Any,
    *,
    field_name: str,
    target_project_id: str,
    peer_project_id: str,
    link_kind: str,
    direction: str,
) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError(f"{field_name} must be a list")
    obligations: list[dict[str, Any]] = []
    for index, item in enumerate(raw_value):
        obligation = _require_mapping(item, field_name=f"{field_name}[{index}]")
        obligated_party = _require_nonempty_text(
            obligation.get("obligated_party"),
            field_name=f"{field_name}[{index}].obligated_party",
        ).lower()
        if obligated_party not in _OBLIGATED_PARTIES:
            raise ValueError(f"{field_name}[{index}].obligated_party must be one of: {list(_OBLIGATED_PARTIES)}")
        summary = _require_nonempty_text(obligation.get("summary"), field_name=f"{field_name}[{index}].summary")
        obligation_kind = _require_nonempty_text(
            obligation.get("obligation_kind"),
            field_name=f"{field_name}[{index}].obligation_kind",
        )
        evidence_refs = _normalize_string_list(
            obligation.get("evidence_refs"),
            field_name=f"{field_name}[{index}].evidence_refs",
        )
        obligation_id = f"obl.{_stable_id_fragment(target_project_id, peer_project_id, link_kind, direction, obligation_kind, summary)}"
        row = {
            "obligation_id": obligation_id,
            "obligated_party": obligated_party,
            "obligation_kind": obligation_kind,
            "summary": summary,
            "evidence_refs": evidence_refs,
        }
        extra = sorted(set(obligation.keys()) - {"obligated_party", "obligation_kind", "summary", "evidence_refs"})
        if extra:
            raise ValueError(f"{field_name}[{index}] has unexpected keys: {extra}")
        obligations.append(row)
    obligations.sort(key=lambda row: (row["obligated_party"], row["obligation_kind"], row["obligation_id"]))
    return obligations


def _normalize_link_rows(
    raw_value: Any,
    *,
    field_name: str,
    target_project_id: str,
    peer_project_ids: set[str],
    bucket: str,
) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError(f"{field_name} must be a list")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_value):
        link = _require_mapping(item, field_name=f"{field_name}[{index}]")
        peer_project_id = _require_nonempty_text(
            link.get("peer_project_id"),
            field_name=f"{field_name}[{index}].peer_project_id",
        )
        if peer_project_id not in peer_project_ids:
            raise ValueError(f"{field_name}[{index}].peer_project_id must be declared in peer_projects")
        link_kind = _require_nonempty_text(link.get("link_kind"), field_name=f"{field_name}[{index}].link_kind")
        direction = _normalize_direction(link.get("direction"), field_name=f"{field_name}[{index}].direction")
        summary = _require_nonempty_text(link.get("summary"), field_name=f"{field_name}[{index}].summary")
        evidence_refs = _normalize_string_list(
            link.get("evidence_refs"),
            field_name=f"{field_name}[{index}].evidence_refs",
        )
        confidence_tag = _normalize_confidence_tag(
            link.get("confidence_tag"),
            field_name=f"{field_name}[{index}].confidence_tag",
        )
        interaction_obligations = _normalize_interaction_obligations(
            link.get("interaction_obligations"),
            field_name=f"{field_name}[{index}].interaction_obligations",
            target_project_id=target_project_id,
            peer_project_id=peer_project_id,
            link_kind=link_kind,
            direction=direction,
        )
        link_id = f"lnk.{_stable_id_fragment(target_project_id, peer_project_id, link_kind, direction, bucket)}"
        row = {
            "link_id": link_id,
            "peer_project_id": peer_project_id,
            "link_kind": link_kind,
            "direction": direction,
            "summary": summary,
            "evidence_refs": evidence_refs,
            "confidence_tag": confidence_tag,
            "interaction_obligations": interaction_obligations,
        }
        extra = sorted(
            set(link.keys())
            - {
                "peer_project_id",
                "link_kind",
                "direction",
                "summary",
                "evidence_refs",
                "confidence_tag",
                "interaction_obligations",
            }
        )
        if extra:
            raise ValueError(f"{field_name}[{index}] has unexpected keys: {extra}")
        normalized.append(row)
    normalized.sort(key=lambda row: (row["peer_project_id"], row["link_kind"], row["direction"], row["link_id"]))
    return normalized


def _normalize_cross_project_context(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError("cross_project_context must be a list")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_value):
        row = _require_mapping(item, field_name=f"cross_project_context[{index}]")
        project_id = _require_nonempty_text(
            row.get("project_id"),
            field_name=f"cross_project_context[{index}].project_id",
        )
        evidence_refs = _normalize_string_list(
            row.get("evidence_refs"),
            field_name=f"cross_project_context[{index}].evidence_refs",
        )
        context_note = ""
        if row.get("context_note") is not None:
            context_note = str(row.get("context_note") or "").strip()
        project_root = ""
        if row.get("project_root") is not None:
            project_root = _normalize_root(
                row.get("project_root"),
                field_name=f"cross_project_context[{index}].project_root",
            )
        normalized.append(
            {
                "project_id": project_id,
                "project_root": project_root,
                "evidence_refs": evidence_refs,
                "context_note": context_note,
            }
        )
    normalized.sort(key=lambda r: (r["project_id"], r["project_root"]))
    return normalized


def _extract_earth_sweep_inputs(raw_value: Any) -> tuple[list[str], list[dict[str, Any]]]:
    """Return (earth_sweep_evidence_refs, earth_sweep_projects)."""
    if raw_value is None:
        return ([], [])
    broad = _require_mapping(raw_value, field_name="broad_sweep_context")

    evidence_refs: list[str] = []
    earth_sweep_projects: list[dict[str, Any]] = []

    if broad.get("earth_sweep_evidence_refs") is not None:
        evidence_refs = _normalize_string_list(
            broad.get("earth_sweep_evidence_refs"),
            field_name="broad_sweep_context.earth_sweep_evidence_refs",
        )

    earth_sweep = broad.get("earth_sweep")
    if earth_sweep is None:
        return (evidence_refs, earth_sweep_projects)

    sweep = _require_mapping(earth_sweep, field_name="broad_sweep_context.earth_sweep")
    if sweep.get("evidence_refs") is not None and not evidence_refs:
        evidence_refs = _normalize_string_list(
            sweep.get("evidence_refs"),
            field_name="broad_sweep_context.earth_sweep.evidence_refs",
        )

    raw_projects = sweep.get("projects")
    if raw_projects is None:
        return (evidence_refs, earth_sweep_projects)
    if not isinstance(raw_projects, list):
        raise ValueError("broad_sweep_context.earth_sweep.projects must be a list")

    for index, item in enumerate(raw_projects):
        project = _require_mapping(item, field_name=f"broad_sweep_context.earth_sweep.projects[{index}]")
        project_id = _require_nonempty_text(
            project.get("project_id"),
            field_name=f"broad_sweep_context.earth_sweep.projects[{index}].project_id",
        )
        obligations = project.get("obligations") or []
        unresolved = project.get("unresolved_ideas") or []
        if not isinstance(obligations, list):
            raise ValueError(f"broad_sweep_context.earth_sweep.projects[{index}].obligations must be a list")
        if not isinstance(unresolved, list):
            raise ValueError(f"broad_sweep_context.earth_sweep.projects[{index}].unresolved_ideas must be a list")
        earth_sweep_projects.append(
            {
                "project_id": project_id,
                "obligations": obligations,
                "unresolved_ideas": unresolved,
            }
        )

    earth_sweep_projects.sort(key=lambda r: r["project_id"])
    return (evidence_refs, earth_sweep_projects)


def _collect_unique_refs(*lists: list[str]) -> list[str]:
    out: set[str] = set()
    for items in lists:
        out.update([str(item) for item in items if str(item).strip()])
    return sorted(out)


def _recommendation_decision(*, recommended_actions: list[dict[str, Any]], open_risks: list[dict[str, Any]]) -> str:
    if open_risks:
        if any(str(row.get("reason_code")) != "missing_earth_sweep_evidence_refs" for row in open_risks):
            return "resolve-context-gaps"
        return "collect-earth-evidence"
    if recommended_actions:
        return "resolve-context-gaps"
    return "insufficient-context"


def _recommendation_rationale(*, decision: str, totals: Mapping[str, Any], open_risks: list[dict[str, Any]]) -> str:
    peer_count = int(totals.get("peer_projects") or 0)
    existing = int(totals.get("existing_links") or 0)
    missing = int(totals.get("missing_links") or 0)
    proposed = int(totals.get("proposed_links") or 0)
    risks = len(open_risks)
    if decision == "proceed":
        return f"links validated (peers={peer_count} existing={existing} proposed={proposed}) with evidence-backed obligations."
    if decision == "proceed-with-open-risks":
        return f"some ecosystem links are evidence-backed, but open risks remain (risks={risks})."
    if decision == "collect-earth-evidence":
        return "ecosystem obligations require Earth-sweep evidence refs before promotion."
    if decision == "resolve-context-gaps":
        return f"context gaps detected while reasoning about ecosystem links (risks={risks})."
    return f"insufficient evidence-backed linkage data (peers={peer_count} existing={existing} missing={missing} proposed={proposed})."


def _recommendation_confidence(*, evidence_refs: list[str], open_risks: list[dict[str, Any]]) -> str:
    if not evidence_refs:
        return "low"
    if open_risks:
        return "medium"
    return "high"


def process_req_027_call_2_ecosystem_linkage_reasoning(
    payload: Mapping[str, Any],
    *,
    emit: Callable[[str], None] | None = None,
    trace_path: str | Path | None = None,
    trace_artifacts_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Implement REQ-027 reasoning/processing behavior using broad-sweep context inputs.

    The strict REQ-027 contract builder remains the source of truth for deterministic
    link/obligation ids. This processor derives input link buckets from Earth-sweep
    context and records unresolved ideas/insufficient evidence as open risks.
    """
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_027_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_027_ANALYSIS_TYPE}")

    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")
    target_project = _normalize_target_project(raw.get("target_project"))
    peer_projects = _normalize_peer_projects(raw.get("peer_projects"))
    peer_project_ids = {row["project_id"] for row in peer_projects}

    broad_sweep_context = raw.get("broad_sweep_context")
    earth_sweep_evidence_refs, earth_sweep_projects = _extract_earth_sweep_inputs(broad_sweep_context)
    broad_mapping: Mapping[str, Any] = _require_mapping(broad_sweep_context, field_name="broad_sweep_context") if broad_sweep_context is not None else {}
    cross_project_context = _normalize_cross_project_context(broad_mapping.get("cross_project_context"))
    cross_context_by_project: dict[str, list[dict[str, Any]]] = {}
    for row in cross_project_context:
        cross_context_by_project.setdefault(row["project_id"], []).append(row)
    earth_projects_by_id: dict[str, dict[str, Any]] = {row["project_id"]: row for row in earth_sweep_projects}

    if emit is not None:
        emit(_format_ts_line(f"REQ-027 processing start peers={len(peer_projects)}", now_utc=checked_at_utc))

    existing_links_raw: list[dict[str, Any]] = []
    missing_links_raw: list[dict[str, Any]] = []
    proposed_links_raw: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []

    for peer in peer_projects:
        peer_id = peer["project_id"]
        cross_rows = cross_context_by_project.get(peer_id, [])
        earth_row = earth_projects_by_id.get(peer_id)

        if cross_rows:
            context_refs = _collect_unique_refs(*[row["evidence_refs"] for row in cross_rows])
            note = next((row["context_note"] for row in cross_rows if row.get("context_note")), "")
            summary = note or f"Broad-sweep cross-project context references peer project '{peer_id}'."
            combined_refs = _collect_unique_refs(context_refs, earth_sweep_evidence_refs)
            if not combined_refs:
                open_risks.append(
                    {
                        "risk_id": f"risk.{_stable_id_fragment(peer_id, 'uncited-cross-project-context', summary)}",
                        "summary": summary,
                        "reason_code": "uncited_strategic_claim",
                        "required_evidence_refs": [],
                    }
                )
                missing_links_raw.append(
                    {
                        "peer_project_id": peer_id,
                        "link_kind": "cross-project-context",
                        "direction": "bidirectional",
                        "summary": f"Cross-project context for '{peer_id}' is present but has no evidence refs; attach citations before promotion.",
                        "evidence_refs": [],
                        "confidence_tag": "low",
                        "interaction_obligations": [],
                    }
                )
            else:
                existing_links_raw.append(
                    {
                        "peer_project_id": peer_id,
                        "link_kind": "cross-project-context",
                        "direction": "bidirectional",
                        "summary": summary,
                        "evidence_refs": combined_refs,
                        "confidence_tag": "high" if context_refs else "medium",
                        "interaction_obligations": [],
                    }
                )

        if earth_row is not None:
            invalid_obligation_count = 0
            for obligation_index, obligation in enumerate(earth_row.get("obligations") or []):
                if not isinstance(obligation, Mapping):
                    invalid_obligation_count += 1
                    continue

                obligation_summary = str(obligation.get("summary") or "").strip() or (
                    f"Earth-sweep obligation entry #{obligation_index} for '{peer_id}'."
                )
                obligation_refs = _normalize_string_list(
                    obligation.get("earth_sweep_evidence_refs") or obligation.get("evidence_refs"),
                    field_name=f"broad_sweep_context.earth_sweep.projects[project_id={peer_id}].obligations[{obligation_index}].evidence_refs",
                )
                if not obligation_refs:
                    open_risks.append(
                        {
                            "risk_id": f"risk.{_stable_id_fragment(peer_id, 'obligation-missing-evidence', obligation_summary)}",
                            "summary": obligation_summary,
                            "reason_code": "missing_obligation_evidence_refs",
                            "required_evidence_refs": [],
                        }
                    )
                    continue

                if not earth_sweep_evidence_refs:
                    open_risks.append(
                        {
                            "risk_id": f"risk.{_stable_id_fragment(peer_id, 'missing-earth-sweep-evidence', obligation_summary)}",
                            "summary": obligation_summary,
                            "reason_code": "missing_earth_sweep_evidence_refs",
                            "required_evidence_refs": obligation_refs,
                        }
                    )
                    continue

                combined_refs = _collect_unique_refs(obligation_refs, earth_sweep_evidence_refs)
                proposed_links_raw.append(
                    {
                        "peer_project_id": peer_id,
                        "link_kind": "earth-sweep-obligation",
                        "direction": "bidirectional",
                        "summary": obligation_summary,
                        "evidence_refs": combined_refs,
                        "confidence_tag": "medium",
                        "interaction_obligations": [
                            {
                                "obligated_party": "both",
                                "obligation_kind": "coordination",
                                "summary": obligation_summary,
                                "evidence_refs": combined_refs,
                            }
                        ],
                    }
                )

            if invalid_obligation_count:
                open_risks.append(
                    {
                        "risk_id": f"risk.{_stable_id_fragment(peer_id, 'invalid-earth-sweep-obligations', str(invalid_obligation_count))}",
                        "summary": f"Malformed Earth-sweep obligation entries for '{peer_id}' (count={invalid_obligation_count}).",
                        "reason_code": "invalid_earth_sweep_obligation_shape",
                        "required_evidence_refs": earth_sweep_evidence_refs,
                    }
                )

            for idea_index, idea_row in enumerate(earth_row.get("unresolved_ideas") or []):
                if not isinstance(idea_row, Mapping):
                    continue
                idea = str(idea_row.get("idea") or idea_row.get("summary") or "").strip()
                if not idea:
                    continue
                idea_refs = _normalize_string_list(
                    idea_row.get("earth_sweep_evidence_refs") or idea_row.get("evidence_refs"),
                    field_name=f"broad_sweep_context.earth_sweep.projects[project_id={peer_id}].unresolved_ideas[{idea_index}].evidence_refs",
                )
                open_risks.append(
                    {
                        "risk_id": f"risk.{_stable_id_fragment(peer_id, 'unresolved-idea', idea)}",
                        "summary": idea,
                        "reason_code": "unresolved_cross_project_idea",
                        "required_evidence_refs": idea_refs,
                    }
                )

        if not cross_rows and earth_row is None:
            missing_links_raw.append(
                {
                    "peer_project_id": peer_id,
                    "link_kind": "context-missing",
                    "direction": "bidirectional",
                    "summary": f"No Earth-sweep context was supplied for peer project '{peer_id}'.",
                    "evidence_refs": earth_sweep_evidence_refs,
                    "confidence_tag": "low",
                    "interaction_obligations": [],
                }
            )

    contract_payload = build_req_027_call_2_ecosystem_linkage_reasoning(
        {
            "analysis_type": REQ_027_ANALYSIS_TYPE,
            "now_utc": checked_at_utc,
            "target_project": target_project,
            "peer_projects": peer_projects,
            "existing_links": existing_links_raw,
            "missing_links": missing_links_raw,
            "proposed_links": proposed_links_raw,
        }
    )

    cross_project_refs = _collect_unique_refs(*[row["evidence_refs"] for row in cross_project_context])
    obligations: list[dict[str, Any]] = []
    link_refs: list[str] = []
    for bucket in ("existing_links", "missing_links", "proposed_links"):
        for link in contract_payload["linkage_reasoning"][bucket]:
            link_refs.extend(link.get("evidence_refs") or [])
            for obligation in link.get("interaction_obligations") or []:
                obligations.append(
                    {
                        "obligation_id": obligation["obligation_id"],
                        "project_id": link["peer_project_id"],
                        "summary": obligation["summary"],
                        "evidence_refs": obligation["evidence_refs"],
                    }
                )
    link_refs = _collect_unique_refs(link_refs)

    recommended_actions: list[dict[str, Any]] = []
    for link in contract_payload["linkage_reasoning"]["missing_links"]:
        action_id = f"action.{_stable_id_fragment('collect-context', link['peer_project_id'], link['link_kind'])}"
        recommended_actions.append(
            {
                "action_id": action_id,
                "summary": f"Collect missing ecosystem linkage context for peer '{link['peer_project_id']}'.",
                "rationale": link["summary"],
                "action_scope": "cross-project",
                "next_step": "Attach Earth-sweep evidence refs and re-run linkage reasoning.",
                "evidence_refs": link.get("evidence_refs") or [],
            }
        )

    missing_links_total = int(contract_payload["totals"].get("missing_links") or 0)
    if missing_links_total:
        missing_link_ids = sorted(
            {str(link.get("link_id") or "") for link in contract_payload["linkage_reasoning"]["missing_links"]}
        )
        open_risks.append(
            {
                "risk_id": f"risk.{_stable_id_fragment('missing-links', json.dumps(missing_link_ids, sort_keys=True))}",
                "summary": f"Missing ecosystem linkage context detected (missing_links={missing_links_total}); resolve gaps before promotion.",
                "reason_code": "analysis_synthesis_contradiction_missing_links",
                "required_evidence_refs": _collect_unique_refs(
                    earth_sweep_evidence_refs,
                    *[
                        _best_effort_extract_string_refs(link.get('evidence_refs'))
                        for link in contract_payload['linkage_reasoning']['missing_links']
                    ],
                ),
            }
        )

    evidence_refs_used = _collect_unique_refs(
        earth_sweep_evidence_refs,
        cross_project_refs,
        link_refs,
        *[row.get("required_evidence_refs") or [] for row in open_risks],
        *[row.get("evidence_refs") or [] for row in recommended_actions],
        *[row.get("evidence_refs") or [] for row in obligations],
    )
    decision = _recommendation_decision(recommended_actions=recommended_actions, open_risks=open_risks)

    processing_behavior = {
        "strategy": "llm-first-broad-sweep",
        "reasoning_mode": "long-thinking",
        "heuristic_summarization_only": False,
        "context_inputs": {
            "target_project": {
                "project_id": target_project["project_id"],
                "project_root": target_project["project_root"],
            },
            "earth_sweep": {
                "evidence_refs": earth_sweep_evidence_refs,
                "projects_considered": sorted(
                    {row["project_id"] for row in earth_sweep_projects if row["project_id"] in peer_project_ids}
                ),
            },
            "cross_project_context": cross_project_context,
        },
        "context_usage": {
            "earth_sweep_context_used": bool(earth_sweep_evidence_refs or earth_sweep_projects),
            "cross_project_context_used": bool(cross_project_context),
            "cross_project_projects_considered": sorted({row["project_id"] for row in cross_project_context}),
            "earth_sweep_refs_used": earth_sweep_evidence_refs,
            "cross_project_refs_used": cross_project_refs,
            "evidence_refs_used": evidence_refs_used,
        },
        "recommendation": {
            "decision": decision,
            "rationale": _recommendation_rationale(
                decision=decision,
                totals=contract_payload["totals"],
                open_risks=open_risks,
            ),
            "confidence": _recommendation_confidence(evidence_refs=evidence_refs_used, open_risks=open_risks),
            "evidence_refs": evidence_refs_used,
            "recommended_actions": recommended_actions,
            "cross_project_obligations": obligations,
            "open_risks": sorted(open_risks, key=lambda r: (r.get("reason_code", ""), r.get("risk_id", ""))),
        },
    }

    if emit is not None:
        emit(_format_ts_line(f"REQ-027 processing decision={decision}", now_utc=checked_at_utc))

    result = {
        "ok": True,
        "schema_version": REQ_027_PROCESSING_SCHEMA_VERSION,
        "requirement_id": REQ_027_REQUIREMENT_ID,
        "analysis_type": REQ_027_ANALYSIS_TYPE,
        "call_id": REQ_027_CALL_ID,
        "checked_at_utc": contract_payload["checked_at_utc"],
        "target_project": contract_payload["target_project"],
        "peer_projects": contract_payload["peer_projects"],
        "linkage_reasoning": contract_payload["linkage_reasoning"],
        "totals": contract_payload["totals"],
        "processing_behavior": processing_behavior,
    }
    _record_req_027_call_2_llm_call_trace(
        checked_at_utc=checked_at_utc,
        target_project=target_project,
        peer_projects=peer_projects,
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        earth_sweep_projects=[row for row in earth_sweep_projects if row.get("project_id") in peer_project_ids],
        cross_project_context=cross_project_context,
        result=result,
        trace_path=Path(trace_path) if trace_path is not None else None,
        artifacts_dir=Path(trace_artifacts_dir) if trace_artifacts_dir is not None else None,
    )
    return result


def _req_035_infer_cross_project_targets(
    *,
    text_fields: list[str],
    peer_project_ids: set[str],
) -> list[str]:
    text = "\n".join([field.strip() for field in text_fields if str(field).strip()]).lower()
    if not text:
        return []

    matched = [pid for pid in sorted(peer_project_ids) if pid.lower() in text]
    if matched:
        return matched
    cross_tokens = ("cross-project", "cross project", "peer project", "coordination", "coordinate", "sync", "align")
    if any(token in text for token in cross_tokens):
        return ["<unspecified>"]
    return []


def _req_035_recommendation_decision(*, promoted_actions: list[dict[str, Any]], open_risks: list[dict[str, Any]]) -> str:
    if promoted_actions and open_risks:
        return "proceed-with-open-risks"
    if promoted_actions:
        return "proceed"
    if open_risks:
        if all(str(row.get("reason_code")) == "missing_earth_sweep_evidence_refs" for row in open_risks):
            return "collect-earth-evidence"
        if any("uncited" in str(row.get("reason_code")) for row in open_risks):
            return "resolve-citation-gaps"
        return "resolve-context-gaps"
    return "insufficient-context"


def _req_030_infer_cross_project_targets(
    *,
    recommendation: Mapping[str, Any],
    peer_project_ids: set[str],
) -> list[str]:
    summary = str(recommendation.get("summary") or "")
    rationale = str(recommendation.get("rationale") or "")
    expected_impact = str(recommendation.get("expected_impact") or "")
    text = f"{summary}\n{rationale}\n{expected_impact}".lower()

    matched = [pid for pid in sorted(peer_project_ids) if pid.lower() in text]
    if matched:
        return matched
    cross_tokens = ("cross-project", "cross project", "coordinate", "coordination", "sync", "align")
    if any(token in text for token in cross_tokens):
        return ["<unspecified>"]
    return []


def _req_030_recommendation_decision(*, sequenced_recommendations: list[str], open_risks: list[dict[str, Any]]) -> str:
    if sequenced_recommendations and open_risks:
        return "proceed-with-open-risks"
    if sequenced_recommendations:
        return "proceed"
    if open_risks:
        if all(str(row.get("reason_code")) == "missing_earth_sweep_evidence_refs" for row in open_risks):
            return "collect-earth-evidence"
        return "resolve-context-gaps"
    return "insufficient-context"


def process_req_030_call_5_sequencing_and_lane_design_reasoning(
    payload: Mapping[str, Any],
    *,
    emit: Callable[[str], None] | None = None,
    trace_path: str | Path | None = None,
    trace_artifacts_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Implement REQ-030 reasoning/processing behavior using broad-sweep context inputs.

    Call-5 is responsible for designing execution lanes and a sequencing order for
    recommendations under the current constraints. Cross-project coordination is
    gated on Earth-sweep evidence refs; unresolved cross-project ideas become open risks.
    """
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_030_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_030_ANALYSIS_TYPE}")

    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")
    target_project = _normalize_target_project(raw.get("target_project"))
    constraints = _normalize_req_030_constraints(raw.get("constraints"))
    recommendations = _normalize_req_030_recommendations(raw.get("recommendations"))
    recommendation_ids = {row["recommendation_id"] for row in recommendations}

    earth_sweep_evidence_refs, earth_sweep_projects = _extract_earth_sweep_inputs(raw.get("broad_sweep_context"))
    broad = raw.get("broad_sweep_context")
    cross_project_context = []
    if broad is not None:
        broad_map = _require_mapping(broad, field_name="broad_sweep_context")
        cross_project_context = _normalize_cross_project_context(broad_map.get("cross_project_context"))
    context_by_project = {row["project_id"]: row for row in cross_project_context if row.get("project_id")}
    peer_project_ids = set(context_by_project.keys())

    recommendation_by_id = {row["recommendation_id"]: row for row in recommendations}

    lane_impl: list[str] = []
    lane_verify: list[str] = []
    lane_cross_exec: list[str] = []
    lane_blocked: list[str] = []
    open_risks: list[dict[str, Any]] = []
    cross_project_obligations: list[dict[str, Any]] = []
    cross_project_deps_by_rec: dict[str, list[dict[str, Any]]] = {}

    for rec in recommendations:
        rec_id = rec["recommendation_id"]
        targets = _req_030_infer_cross_project_targets(recommendation=rec, peer_project_ids=peer_project_ids)
        is_cross_project = bool(targets)

        if not is_cross_project:
            if rec.get("risk_level") == "high":
                lane_verify.append(rec_id)
            else:
                lane_impl.append(rec_id)
            continue

        if not earth_sweep_evidence_refs:
            lane_blocked.append(rec_id)
            open_risks.append(
                {
                    "risk_id": f"risk.{_stable_id_fragment(target_project['project_id'], 'req-030', rec_id, 'missing-earth')}",
                    "summary": rec["summary"],
                    "reason_code": "missing_earth_sweep_evidence_refs",
                    "required_evidence_refs": [],
                }
            )
            continue

        missing_reason_codes: list[str] = []
        required_refs: list[str] = list(earth_sweep_evidence_refs)
        dependency_projects: list[str] = []

        if targets == ["<unspecified>"]:
            missing_reason_codes.append("missing_cross_project_context")
        else:
            for project_id in targets:
                context = context_by_project.get(project_id)
                if context is None:
                    missing_reason_codes.append("missing_cross_project_context")
                    continue
                context_refs = list(context.get("evidence_refs") or [])
                if not context_refs:
                    missing_reason_codes.append("missing_cross_project_context_evidence_refs")
                else:
                    required_refs.extend(context_refs)
                dependency_projects.append(project_id)

        if missing_reason_codes:
            lane_blocked.append(rec_id)
            open_risks.append(
                {
                    "risk_id": f"risk.{_stable_id_fragment(target_project['project_id'], 'req-030', rec_id, ','.join(sorted(set(missing_reason_codes))))}",
                    "summary": rec["summary"],
                    "reason_code": ",".join(sorted(set(missing_reason_codes))),
                    "required_evidence_refs": _collect_unique_refs(required_refs),
                }
            )
            continue

        lane_cross_exec.append(rec_id)
        deps = [
            {
                "dependency_kind": "cross-project-coordination",
                "depends_on": project_id,
                "summary": f"Coordinate sequencing assumptions with peer project '{project_id}' before execution.",
            }
            for project_id in sorted(set(dependency_projects))
        ]
        cross_project_deps_by_rec[rec_id] = deps
        for project_id in sorted(set(dependency_projects)):
            obligation_id = f"obl.{_stable_id_fragment(target_project['project_id'], 'req-030', rec_id, project_id)}"
            cross_project_obligations.append(
                {
                    "obligation_id": obligation_id,
                    "project_id": project_id,
                    "summary": rec["summary"],
                    "evidence_refs": _collect_unique_refs(
                        earth_sweep_evidence_refs,
                        list(context_by_project.get(project_id, {}).get("evidence_refs") or []),
                    ),
                }
            )

    lane_impl.sort()
    lane_verify.sort()
    lane_cross_exec.sort()
    lane_blocked.sort()
    cross_project_obligations.sort(key=lambda row: (row["project_id"], row["obligation_id"]))
    open_risks.sort(key=lambda row: (row.get("reason_code", ""), row.get("risk_id", "")))

    lane_specs: list[dict[str, Any]] = []
    if lane_impl:
        lane_specs.append(
            {
                "lane_name": "Local implementation",
                "lane_kind": "local-implementation",
                "lane_goal": "Execute low/medium-risk local recommendations within current work-in-progress limits.",
                "why_now": (
                    f"Constraints allow execution now (max_parallel_lanes={constraints['max_parallel_lanes']} "
                    f"max_active_work_items={constraints['max_active_work_items']})."
                ),
                "recommendation_ids": lane_impl,
                "coordination_dependencies": [],
            }
        )
    if lane_verify:
        lane_specs.append(
            {
                "lane_name": "Local verification",
                "lane_kind": "local-verification",
                "lane_goal": "Validate higher-risk recommendations with explicit sequencing to avoid churn.",
                "why_now": "High-risk items benefit from an explicit verification lane to preserve deterministic recovery.",
                "recommendation_ids": lane_verify,
                "coordination_dependencies": [],
            }
        )
    if lane_cross_exec:
        lane_specs.append(
            {
                "lane_name": "Cross-project coordination",
                "lane_kind": "cross-project-coordination",
                "lane_goal": "Coordinate externally required recommendations before execution proceeds.",
                "why_now": "Earth-sweep evidence refs and cross-project context support starting coordination immediately.",
                "recommendation_ids": lane_cross_exec,
                "coordination_dependencies": [
                    dep
                    for rec_id in lane_cross_exec
                    for dep in (cross_project_deps_by_rec.get(rec_id) or [])
                ],
            }
        )
    if lane_blocked:
        lane_specs.append(
            {
                "lane_name": "Evidence collection",
                "lane_kind": "evidence-collection",
                "lane_goal": "Collect Earth-sweep and cross-project evidence to unblock coordination recommendations.",
                "why_now": "Blocked cross-project ideas must be captured as open risks and routed to evidence collection.",
                "recommendation_ids": lane_blocked,
                "coordination_dependencies": [],
            }
        )

    lanes_needed = len(lane_specs)
    if lanes_needed > constraints["max_parallel_lanes"]:
        if emit is not None:
            emit(
                _format_ts_line(
                    f"REQ-030 lane design exceeds max_parallel_lanes={constraints['max_parallel_lanes']} (lanes={lanes_needed}); lanes are still emitted deterministically.",
                    now_utc=checked_at_utc,
                )
            )

    sequence_specs: list[dict[str, Any]] = []
    order = 1
    for group, lane_name in (
        (lane_cross_exec, "Cross-project coordination"),
        (lane_impl, "Local implementation"),
        (lane_verify, "Local verification"),
    ):
        for rec_id in group:
            seq_row: dict[str, Any] = {
                "order": order,
                "recommendation_id": rec_id,
                "lane_name": lane_name,
                "why_now": "",
                "coordination_dependencies": [],
            }
            rec = recommendation_by_id[rec_id]
            if lane_name == "Cross-project coordination":
                seq_row["why_now"] = (
                    "Start coordination early to avoid downstream blocking; Earth-sweep evidence refs are present."
                )
                seq_row["coordination_dependencies"] = list(cross_project_deps_by_rec.get(rec_id) or [])
            elif lane_name == "Local verification":
                seq_row["why_now"] = "Sequence explicitly to validate high-risk work without expanding active work items."
            else:
                seq_row["why_now"] = "Local scope work is unblocked and can proceed under current constraints."
            sequence_specs.append(seq_row)
            order += 1

    contract_payload = build_req_030_call_5_sequencing_and_lane_design_reasoning(
        {
            "analysis_type": REQ_030_ANALYSIS_TYPE,
            "now_utc": checked_at_utc,
            "target_project": target_project,
            "constraints": constraints,
            "recommendations": recommendations,
            "sequencing_and_lane_design_reasoning": {"lanes": lane_specs, "sequence": sequence_specs},
        }
    )

    cross_project_refs = _collect_unique_refs(*[row["evidence_refs"] for row in cross_project_context])
    evidence_refs_used = _collect_unique_refs(
        earth_sweep_evidence_refs,
        cross_project_refs,
        *[row.get("required_evidence_refs") or [] for row in open_risks],
        *[row.get("evidence_refs") or [] for row in cross_project_obligations],
    )

    sequenced_recommendations = [row["recommendation_id"] for row in contract_payload["sequencing_and_lane_design_reasoning"]["sequence"]]
    decision = _req_030_recommendation_decision(
        sequenced_recommendations=sequenced_recommendations,
        open_risks=open_risks,
    )
    confidence = _recommendation_confidence(evidence_refs=evidence_refs_used, open_risks=open_risks)

    recommended_actions: list[dict[str, Any]] = []
    for row in contract_payload["sequencing_and_lane_design_reasoning"]["sequence"]:
        rec_id = row["recommendation_id"]
        rec = recommendation_by_id.get(rec_id, {})
        action_id = f"action.{_stable_id_fragment(target_project['project_id'], 'req-030', rec_id, str(row['lane_id']))}"
        recommended_actions.append(
            {
                "action_id": action_id,
                "recommendation_id": rec_id,
                "summary": str(rec.get("summary") or ""),
                "rationale": str(rec.get("rationale") or ""),
                "lane_id": row["lane_id"],
                "lane_name": row["lane_name"],
                "why_now": row["why_now"],
                "coordination_dependencies": list(row.get("coordination_dependencies") or []),
            }
        )
    recommended_actions.sort(key=lambda r: (r["lane_name"], r["recommendation_id"], r["action_id"]))

    processing_behavior = {
        "strategy": "llm-first-broad-sweep",
        "reasoning_mode": "long-thinking",
        "heuristic_summarization_only": False,
        "strict_evidence_discipline": True,
        "context_inputs": {
            "target_project": {
                "project_id": target_project["project_id"],
                "project_root": target_project["project_root"],
            },
            "constraints": dict(constraints),
            "broad_sweep_context": {
                "earth_sweep_evidence_refs": list(earth_sweep_evidence_refs),
                "cross_project_context": cross_project_context,
            },
        },
        "context_usage": {
            "earth_sweep_context_used": bool(earth_sweep_evidence_refs or earth_sweep_projects),
            "cross_project_context_used": bool(cross_project_context),
            "cross_project_projects_considered": sorted({row["project_id"] for row in cross_project_context}),
            "earth_sweep_refs_used": earth_sweep_evidence_refs,
            "cross_project_refs_used": cross_project_refs,
            "evidence_refs_used": evidence_refs_used,
        },
        "recommendation": {
            "decision": decision,
            "rationale": (
                f"lanes={contract_payload['totals']['lanes']} "
                f"sequence_items={contract_payload['totals']['sequence_items']} "
                f"blocked={len(lane_blocked)} open_risks={len(open_risks)}"
            ),
            "confidence": confidence,
            "evidence_refs": evidence_refs_used,
            "recommended_actions": recommended_actions,
            "cross_project_obligations": cross_project_obligations,
            "open_risks": open_risks,
        },
    }

    if emit is not None:
        emit(_format_ts_line(f"REQ-030 processing decision={decision}", now_utc=checked_at_utc))

    result = {
        "ok": True,
        "schema_version": REQ_030_PROCESSING_SCHEMA_VERSION,
        "requirement_id": REQ_030_REQUIREMENT_ID,
        "analysis_type": REQ_030_ANALYSIS_TYPE,
        "call_id": REQ_030_CALL_ID,
        "checked_at_utc": contract_payload["checked_at_utc"],
        "target_project": contract_payload["target_project"],
        "constraints": contract_payload["constraints"],
        "recommendations": contract_payload["recommendations"],
        "sequencing_and_lane_design_reasoning": contract_payload["sequencing_and_lane_design_reasoning"],
        "totals": contract_payload["totals"],
        "processing_behavior": processing_behavior,
    }

    trace_row = _record_req_030_call_5_llm_call_trace(
        checked_at_utc=checked_at_utc,
        target_project=target_project,
        constraints=constraints,
        recommendations=recommendations,
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        earth_sweep_projects=earth_sweep_projects,
        cross_project_context=cross_project_context,
        result=result,
        trace_path=Path(trace_path) if trace_path is not None else None,
        artifacts_dir=Path(trace_artifacts_dir) if trace_artifacts_dir is not None else None,
    )

    canonical_input = _req_030_canonical_input(
        checked_at_utc=checked_at_utc,
        target_project=target_project,
        constraints=constraints,
        recommendations=recommendations,
    )
    canonical_processing_input = _req_030_canonical_processing_input(
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        earth_sweep_projects=earth_sweep_projects,
        cross_project_context=cross_project_context,
        result=result,
    )
    canonical_input_sha = _sha256_hex(canonical_input)
    processing_input_sha = _sha256_hex(canonical_processing_input)
    result["call_metadata"] = {
        "reproducibility": "deterministic-input-fingerprint",
        "canonical_input": canonical_input,
        "canonical_input_sha256": canonical_input_sha,
        "reproducible_call_id": f"req030-{canonical_input_sha[:16]}",
        "canonical_processing_input": canonical_processing_input,
        "processing_input_sha256": processing_input_sha,
        "processing_call_id": f"req030-processing-{processing_input_sha[:16]}",
        "llm_call_trace_schema_version": _LLM_CALL_TRACE_SCHEMA_VERSION,
        "llm_call_trace_path": _LLM_CALL_TRACE_RELATIVE_PATH,
        "llm_call_trace_sha256": _sha256_hex([trace_row]),
        "llm_call_trace_rows": [trace_row],
    }
    return result


def process_req_035_evidence_citation_discipline_in_reasoning_calls(
    payload: Mapping[str, Any],
    *,
    emit: Callable[[str], None] | None = None,
    trace_path: str | Path | None = None,
    trace_artifacts_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Implement REQ-035 reasoning/processing behavior using broad-sweep context inputs."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_035_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_035_ANALYSIS_TYPE}")

    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")
    context_provenance_ledger = _normalize_req_035_context_provenance_ledger(raw.get("context_provenance_ledger"))
    if context_provenance_ledger["ledger_requirement_id"] != "REQ-021":
        raise ValueError("context_provenance_ledger.ledger_requirement_id must be REQ-021")
    reasoning_calls = _normalize_req_035_reasoning_calls(raw.get("reasoning_calls"))

    earth_sweep_evidence_refs, earth_sweep_projects = _extract_earth_sweep_inputs(raw.get("broad_sweep_context"))
    broad = raw.get("broad_sweep_context")
    cross_project_context: list[dict[str, Any]] = []
    if broad is not None:
        broad_map = _require_mapping(broad, field_name="broad_sweep_context")
        cross_project_context = _normalize_cross_project_context(broad_map.get("cross_project_context"))
    context_by_project = {row["project_id"]: row for row in cross_project_context if row.get("project_id")}
    peer_project_ids = set(context_by_project.keys())

    if emit is not None:
        emit(_format_ts_line(f"REQ-035 processing start reasoning_calls={len(reasoning_calls)}", now_utc=checked_at_utc))

    contract_payload = build_req_035_evidence_citation_discipline_in_reasoning_calls(
        {
            "analysis_type": REQ_035_ANALYSIS_TYPE,
            "now_utc": checked_at_utc,
            "context_provenance_ledger": context_provenance_ledger,
            "reasoning_calls": reasoning_calls,
        }
    )
    discipline = contract_payload["evidence_citation_discipline"]
    final_rows = list(discipline["final_recommendations"])
    flagged_rows = list(discipline["flagged_claims"])

    claim_lookup: dict[tuple[str, str], Mapping[str, Any]] = {}
    for call in reasoning_calls:
        call_id = call["call_id"]
        for claim in call["strategic_claims"]:
            claim_lookup[(call_id, claim["strategic_claim_id"])] = claim

    promoted_actions: list[dict[str, Any]] = []
    cross_project_obligations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []

    for row in flagged_rows:
        recommendation_id = str(row.get("recommendation_id") or "").strip()
        reason_codes = sorted({str(reason).strip() for reason in row.get("flag_reason_codes") or [] if str(reason).strip()})
        reason_code = ",".join(reason_codes) if reason_codes else "uncited_strategic_claim"
        required_refs = _collect_unique_refs(
            list(row.get("evidence_ids") or []),
            list(row.get("unknown_evidence_ids") or []),
        )
        risk_id = f"risk.{_stable_id_fragment('req-035', recommendation_id, reason_code)}"
        open_risks.append(
            {
                "risk_id": risk_id,
                "summary": str(row.get("summary") or ""),
                "reason_code": reason_code,
                "required_evidence_refs": required_refs,
            }
        )

    for recommendation in final_rows:
        recommendation_id = recommendation["recommendation_id"]
        call_id = recommendation["call_id"]
        strategic_claim_id = recommendation["strategic_claim_id"]
        claim_row = claim_lookup.get((call_id, strategic_claim_id), {})
        targets = _req_035_infer_cross_project_targets(
            text_fields=[
                str(claim_row.get("summary") or ""),
                str(recommendation.get("summary") or ""),
                str(recommendation.get("rationale") or ""),
            ],
            peer_project_ids=peer_project_ids,
        )
        evidence_ids = list(recommendation.get("evidence_ids") or [])
        action = {
            "action_id": f"action.{_stable_id_fragment('req-035', call_id, strategic_claim_id, recommendation_id)}",
            "recommendation_id": recommendation_id,
            "call_id": call_id,
            "strategic_claim_id": strategic_claim_id,
            "summary": recommendation["summary"],
            "rationale": recommendation["rationale"],
            "confidence_tag": recommendation["confidence_tag"],
            "evidence_ids": evidence_ids,
            "coordination_required": bool(targets),
            "coordination_projects": sorted(set([project_id for project_id in targets if project_id != "<unspecified>"])),
        }

        if not targets:
            promoted_actions.append(action)
            continue

        if not earth_sweep_evidence_refs:
            open_risks.append(
                {
                    "risk_id": f"risk.{_stable_id_fragment('req-035', recommendation_id, 'missing-earth-sweep-evidence-refs')}",
                    "summary": recommendation["summary"],
                    "reason_code": "missing_earth_sweep_evidence_refs",
                    "required_evidence_refs": _collect_unique_refs(evidence_ids),
                }
            )
            continue

        if targets == ["<unspecified>"]:
            open_risks.append(
                {
                    "risk_id": f"risk.{_stable_id_fragment('req-035', recommendation_id, 'missing-cross-project-context')}",
                    "summary": recommendation["summary"],
                    "reason_code": "missing_cross_project_context",
                    "required_evidence_refs": _collect_unique_refs(earth_sweep_evidence_refs, evidence_ids),
                }
            )
            continue

        missing_reason_codes: list[str] = []
        required_refs: list[str] = list(earth_sweep_evidence_refs)
        candidate_obligations: list[dict[str, Any]] = []
        for project_id in sorted(set(targets)):
            context_row = context_by_project.get(project_id)
            if context_row is None:
                missing_reason_codes.append("missing_cross_project_context")
                continue
            context_refs = list(context_row.get("evidence_refs") or [])
            if not context_refs:
                missing_reason_codes.append("missing_cross_project_context_evidence_refs")
                continue
            required_refs.extend(context_refs)
            candidate_obligations.append(
                {
                    "obligation_id": f"obl.{_stable_id_fragment('req-035', recommendation_id, project_id)}",
                    "project_id": project_id,
                    "recommendation_id": recommendation_id,
                    "summary": recommendation["summary"],
                    "evidence_refs": _collect_unique_refs(earth_sweep_evidence_refs, context_refs, evidence_ids),
                }
            )

        if missing_reason_codes:
            open_risks.append(
                {
                    "risk_id": f"risk.{_stable_id_fragment('req-035', recommendation_id, ','.join(sorted(set(missing_reason_codes))))}",
                    "summary": recommendation["summary"],
                    "reason_code": ",".join(sorted(set(missing_reason_codes))),
                    "required_evidence_refs": _collect_unique_refs(required_refs, evidence_ids),
                }
            )
            continue

        cross_project_obligations.extend(candidate_obligations)
        promoted_actions.append(action)

    for project in earth_sweep_projects:
        project_id = str(project.get("project_id") or "").strip()
        if not project_id:
            continue
        for idx, idea_row in enumerate(project.get("unresolved_ideas") or []):
            if not isinstance(idea_row, Mapping):
                continue
            idea_summary = str(idea_row.get("idea") or idea_row.get("summary") or "").strip()
            if not idea_summary:
                continue
            idea_refs = _normalize_string_list(
                idea_row.get("earth_sweep_evidence_refs") or idea_row.get("evidence_refs"),
                field_name=f"broad_sweep_context.earth_sweep.projects[project_id={project_id}].unresolved_ideas[{idx}].evidence_refs",
            )
            open_risks.append(
                {
                    "risk_id": f"risk.{_stable_id_fragment('req-035', project_id, 'unresolved-idea', idea_summary)}",
                    "summary": idea_summary,
                    "reason_code": "unresolved_cross_project_idea",
                    "required_evidence_refs": _collect_unique_refs(idea_refs),
                }
            )

    cross_project_obligations.sort(key=lambda row: (row["project_id"], row["obligation_id"]))
    promoted_actions.sort(key=lambda row: (row["recommendation_id"], row["action_id"]))

    deduped_open_risks: dict[str, dict[str, Any]] = {}
    for row in open_risks:
        deduped_open_risks[row["risk_id"]] = row
    open_risks = sorted(
        deduped_open_risks.values(),
        key=lambda row: (str(row.get("reason_code") or ""), str(row.get("risk_id") or "")),
    )

    cross_project_refs = _collect_unique_refs(*[row["evidence_refs"] for row in cross_project_context])
    evidence_refs_used = _collect_unique_refs(
        context_provenance_ledger["evidence_ids"],
        earth_sweep_evidence_refs,
        cross_project_refs,
        *[list(row.get("evidence_ids") or []) for row in final_rows],
        *[list(row.get("evidence_ids") or []) for row in flagged_rows],
        *[list(row.get("required_evidence_refs") or []) for row in open_risks],
        *[list(row.get("evidence_refs") or []) for row in cross_project_obligations],
    )

    decision = _req_035_recommendation_decision(promoted_actions=promoted_actions, open_risks=open_risks)
    confidence = _recommendation_confidence(evidence_refs=evidence_refs_used, open_risks=open_risks)
    totals = contract_payload["totals"]

    processing_behavior = {
        "strategy": "llm-first-broad-sweep",
        "reasoning_mode": "long-thinking",
        "heuristic_summarization_only": False,
        "strict_evidence_discipline": True,
        "context_inputs": {
            "context_provenance_ledger": context_provenance_ledger,
            "reasoning_calls": reasoning_calls,
            "broad_sweep_context": {
                "earth_sweep_evidence_refs": earth_sweep_evidence_refs,
                "earth_sweep_projects": earth_sweep_projects,
                "cross_project_context": cross_project_context,
            },
        },
        "context_usage": {
            "earth_sweep_context_used": bool(earth_sweep_evidence_refs or earth_sweep_projects),
            "cross_project_context_used": bool(cross_project_context),
            "cross_project_projects_considered": sorted({row["project_id"] for row in cross_project_context}),
            "earth_sweep_refs_used": earth_sweep_evidence_refs,
            "cross_project_refs_used": cross_project_refs,
            "ledger_evidence_ids_used": list(context_provenance_ledger["evidence_ids"]),
            "evidence_refs_used": evidence_refs_used,
        },
        "recommendation": {
            "decision": decision,
            "rationale": (
                f"strategic_claims={totals['strategic_claims']} "
                f"cited={totals['cited_claims']} "
                f"flagged={totals['flagged_claims']} "
                f"promoted_actions={len(promoted_actions)} "
                f"open_risks={len(open_risks)}"
            ),
            "confidence": confidence,
            "evidence_refs": evidence_refs_used,
            "recommended_actions": promoted_actions,
            "cross_project_obligations": cross_project_obligations,
            "open_risks": open_risks,
        },
    }

    if emit is not None:
        emit(_format_ts_line(f"REQ-035 processing decision={decision}", now_utc=checked_at_utc))

    result = {
        "ok": True,
        "schema_version": REQ_035_PROCESSING_SCHEMA_VERSION,
        "requirement_id": REQ_035_REQUIREMENT_ID,
        "analysis_type": REQ_035_ANALYSIS_TYPE,
        "call_id": REQ_035_CALL_ID,
        "checked_at_utc": contract_payload["checked_at_utc"],
        "context_provenance_ledger": contract_payload["context_provenance_ledger"],
        "reasoning_calls": contract_payload["reasoning_calls"],
        "evidence_citation_discipline": contract_payload["evidence_citation_discipline"],
        "totals": contract_payload["totals"],
        "processing_behavior": processing_behavior,
    }

    trace_rows = _record_req_035_reasoning_calls_llm_call_trace(
        checked_at_utc=checked_at_utc,
        context_provenance_ledger=context_provenance_ledger,
        reasoning_calls=reasoning_calls,
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        earth_sweep_projects=earth_sweep_projects,
        cross_project_context=cross_project_context,
        result=result,
        trace_path=Path(trace_path) if trace_path is not None else None,
        artifacts_dir=Path(trace_artifacts_dir) if trace_artifacts_dir is not None else None,
    )

    canonical_input = _req_035_canonical_input(
        checked_at_utc=checked_at_utc,
        context_provenance_ledger=context_provenance_ledger,
        reasoning_calls=reasoning_calls,
    )
    canonical_processing_input = _req_035_canonical_processing_input(
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        earth_sweep_projects=earth_sweep_projects,
        cross_project_context=cross_project_context,
        result=result,
    )
    canonical_input_sha = _sha256_hex(canonical_input)
    processing_input_sha = _sha256_hex(canonical_processing_input)
    result["call_metadata"] = {
        "reproducibility": "deterministic-input-fingerprint",
        "canonical_input": canonical_input,
        "canonical_input_sha256": canonical_input_sha,
        "reproducible_call_id": f"req035-{canonical_input_sha[:16]}",
        "canonical_processing_input": canonical_processing_input,
        "processing_input_sha256": processing_input_sha,
        "processing_call_id": f"req035-processing-{processing_input_sha[:16]}",
        "llm_call_trace_schema_version": _LLM_CALL_TRACE_SCHEMA_VERSION,
        "llm_call_trace_path": _LLM_CALL_TRACE_RELATIVE_PATH,
        "llm_call_trace_sha256": _sha256_hex(trace_rows),
        "llm_call_trace_rows": trace_rows,
    }
    return result


def build_req_027_call_2_ecosystem_linkage_reasoning(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build normalized REQ-027 payload for ecosystem linkage reasoning."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_027_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_027_ANALYSIS_TYPE}")
    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")

    target_project = _normalize_target_project(raw.get("target_project"))
    peer_projects = _normalize_peer_projects(raw.get("peer_projects"))
    peer_project_ids = {row["project_id"] for row in peer_projects}

    existing_links = _normalize_link_rows(
        raw.get("existing_links"),
        field_name="existing_links",
        target_project_id=target_project["project_id"],
        peer_project_ids=peer_project_ids,
        bucket="existing",
    )
    missing_links = _normalize_link_rows(
        raw.get("missing_links"),
        field_name="missing_links",
        target_project_id=target_project["project_id"],
        peer_project_ids=peer_project_ids,
        bucket="missing",
    )
    proposed_links = _normalize_link_rows(
        raw.get("proposed_links"),
        field_name="proposed_links",
        target_project_id=target_project["project_id"],
        peer_project_ids=peer_project_ids,
        bucket="proposed",
    )

    totals = {
        "peer_projects": len(peer_projects),
        "existing_links": len(existing_links),
        "missing_links": len(missing_links),
        "proposed_links": len(proposed_links),
        "interaction_obligations": sum(
            len(row["interaction_obligations"]) for row in (existing_links + missing_links + proposed_links)
        ),
    }

    output_payload = {
        "ok": True,
        "schema_version": REQ_027_SCHEMA_VERSION,
        "requirement_id": REQ_027_REQUIREMENT_ID,
        "analysis_type": REQ_027_ANALYSIS_TYPE,
        "call_id": REQ_027_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "target_project": target_project,
        "peer_projects": peer_projects,
        "linkage_reasoning": {
            "existing_links": existing_links,
            "missing_links": missing_links,
            "proposed_links": proposed_links,
        },
        "totals": totals,
    }

    errors = validate_req_027_call_2_ecosystem_linkage_reasoning(output_payload)
    if errors:
        raise ValueError(f"built REQ-027 payload failed validation: {errors}")
    return output_payload


def validate_req_027_call_2_ecosystem_linkage_reasoning(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-027 Call-2 ecosystem linkage reasoning payload shape."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    required_top = {
        "ok",
        "schema_version",
        "requirement_id",
        "analysis_type",
        "call_id",
        "checked_at_utc",
        "target_project",
        "peer_projects",
        "linkage_reasoning",
        "totals",
    }
    top_keys = set(payload.keys())
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - required_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("ok") is not True:
        errors.append("ok must be true")
    if payload.get("schema_version") != REQ_027_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_027_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_027_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_027_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_027_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_027_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_027_CALL_ID:
        errors.append(f"call_id must be {REQ_027_CALL_ID}")
    if not isinstance(payload.get("checked_at_utc"), str) or not str(payload.get("checked_at_utc")).strip():
        errors.append("checked_at_utc must be a non-empty string")

    target_project = payload.get("target_project")
    if not isinstance(target_project, Mapping):
        errors.append("target_project must be an object")
        target_project = {}
    else:
        expected_target_keys = {"project_id", "project_root"}
        target_keys = set(target_project.keys())
        missing_target = sorted(expected_target_keys - target_keys)
        if missing_target:
            errors.append(f"target_project missing keys: {missing_target}")
        unexpected_target = sorted(target_keys - expected_target_keys)
        if unexpected_target:
            errors.append(f"target_project has unexpected keys: {unexpected_target}")
        if not isinstance(target_project.get("project_id"), str) or not str(target_project.get("project_id")).strip():
            errors.append("target_project.project_id must be a non-empty string")
        root = target_project.get("project_root")
        if not isinstance(root, str) or not root.strip():
            errors.append("target_project.project_root must be a non-empty string")
        elif not root.startswith("/"):
            errors.append("target_project.project_root must be an absolute path")

    peer_projects = payload.get("peer_projects")
    peer_project_ids: set[str] = set()
    if not isinstance(peer_projects, list) or not peer_projects:
        errors.append("peer_projects must be a non-empty list")
        peer_projects = []
    else:
        for index, item in enumerate(peer_projects):
            if not isinstance(item, Mapping):
                errors.append(f"peer_projects[{index}] must be an object")
                continue
            expected_peer_keys = {"project_id", "project_root"}
            peer_keys = set(item.keys())
            missing_peer = sorted(expected_peer_keys - peer_keys)
            if missing_peer:
                errors.append(f"peer_projects[{index}] missing keys: {missing_peer}")
            unexpected_peer = sorted(peer_keys - expected_peer_keys)
            if unexpected_peer:
                errors.append(f"peer_projects[{index}] has unexpected keys: {unexpected_peer}")
            project_id = item.get("project_id")
            if not isinstance(project_id, str) or not project_id.strip():
                errors.append(f"peer_projects[{index}].project_id must be a non-empty string")
            else:
                peer_project_ids.add(project_id)
            root = item.get("project_root")
            if not isinstance(root, str) or not root.strip():
                errors.append(f"peer_projects[{index}].project_root must be a non-empty string")
            elif not root.startswith("/"):
                errors.append(f"peer_projects[{index}].project_root must be an absolute path")

    linkage_reasoning = payload.get("linkage_reasoning")
    if not isinstance(linkage_reasoning, Mapping):
        errors.append("linkage_reasoning must be an object")
        return errors

    expected_reasoning_keys = {"existing_links", "missing_links", "proposed_links"}
    reasoning_keys = set(linkage_reasoning.keys())
    missing_reasoning = sorted(expected_reasoning_keys - reasoning_keys)
    if missing_reasoning:
        errors.append(f"linkage_reasoning missing keys: {missing_reasoning}")
    unexpected_reasoning = sorted(reasoning_keys - expected_reasoning_keys)
    if unexpected_reasoning:
        errors.append(f"linkage_reasoning has unexpected keys: {unexpected_reasoning}")

    for bucket in ("existing_links", "missing_links", "proposed_links"):
        rows = linkage_reasoning.get(bucket)
        if not isinstance(rows, list):
            errors.append(f"linkage_reasoning.{bucket} must be a list")
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                errors.append(f"linkage_reasoning.{bucket}[{index}] must be an object")
                continue
            expected_link_keys = {
                "link_id",
                "peer_project_id",
                "link_kind",
                "direction",
                "summary",
                "evidence_refs",
                "confidence_tag",
                "interaction_obligations",
            }
            row_keys = set(row.keys())
            missing_link = sorted(expected_link_keys - row_keys)
            if missing_link:
                errors.append(f"linkage_reasoning.{bucket}[{index}] missing keys: {missing_link}")
            unexpected_link = sorted(row_keys - expected_link_keys)
            if unexpected_link:
                errors.append(f"linkage_reasoning.{bucket}[{index}] has unexpected keys: {unexpected_link}")
            link_id = row.get("link_id")
            if not isinstance(link_id, str) or not link_id.startswith("lnk.") or len(link_id) < 6:
                errors.append(f"linkage_reasoning.{bucket}[{index}].link_id must be a string like lnk.<id>")
            peer_project_id = row.get("peer_project_id")
            if not isinstance(peer_project_id, str) or not peer_project_id.strip():
                errors.append(f"linkage_reasoning.{bucket}[{index}].peer_project_id must be a non-empty string")
            elif peer_project_ids and peer_project_id not in peer_project_ids:
                errors.append(
                    f"linkage_reasoning.{bucket}[{index}].peer_project_id must be declared in peer_projects"
                )
            link_kind = row.get("link_kind")
            if not isinstance(link_kind, str) or not link_kind.strip():
                errors.append(f"linkage_reasoning.{bucket}[{index}].link_kind must be a non-empty string")
            direction = row.get("direction")
            if direction not in _DIRECTIONS:
                errors.append(f"linkage_reasoning.{bucket}[{index}].direction must be one of: {list(_DIRECTIONS)}")
            summary = row.get("summary")
            if not isinstance(summary, str) or not summary.strip():
                errors.append(f"linkage_reasoning.{bucket}[{index}].summary must be a non-empty string")
            evidence_refs = row.get("evidence_refs")
            if not isinstance(evidence_refs, list):
                errors.append(f"linkage_reasoning.{bucket}[{index}].evidence_refs must be a list of strings")
            else:
                for ev_index, ev in enumerate(evidence_refs):
                    if not isinstance(ev, str) or not ev.strip():
                        errors.append(
                            f"linkage_reasoning.{bucket}[{index}].evidence_refs[{ev_index}] must be non-empty string"
                        )
            confidence_tag = row.get("confidence_tag")
            if confidence_tag not in _CONFIDENCE_TAGS:
                errors.append(
                    f"linkage_reasoning.{bucket}[{index}].confidence_tag must be one of: {list(_CONFIDENCE_TAGS)}"
                )
            obligations = row.get("interaction_obligations")
            if not isinstance(obligations, list):
                errors.append(f"linkage_reasoning.{bucket}[{index}].interaction_obligations must be a list")
                continue
            for ob_index, obligation in enumerate(obligations):
                if not isinstance(obligation, Mapping):
                    errors.append(
                        f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}] must be an object"
                    )
                    continue
                expected_ob_keys = {"obligation_id", "obligated_party", "obligation_kind", "summary", "evidence_refs"}
                ob_keys = set(obligation.keys())
                missing_ob = sorted(expected_ob_keys - ob_keys)
                if missing_ob:
                    errors.append(
                        f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}] missing keys: {missing_ob}"
                    )
                unexpected_ob = sorted(ob_keys - expected_ob_keys)
                if unexpected_ob:
                    errors.append(
                        f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}] has unexpected keys: {unexpected_ob}"
                    )
                ob_id = obligation.get("obligation_id")
                if not isinstance(ob_id, str) or not ob_id.startswith("obl.") or len(ob_id) < 6:
                    errors.append(
                        f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}].obligation_id must be like obl.<id>"
                    )
                obligated_party = obligation.get("obligated_party")
                if obligated_party not in _OBLIGATED_PARTIES:
                    errors.append(
                        f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}].obligated_party must be one of: {list(_OBLIGATED_PARTIES)}"
                    )
                obligation_kind = obligation.get("obligation_kind")
                if not isinstance(obligation_kind, str) or not obligation_kind.strip():
                    errors.append(
                        f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}].obligation_kind must be a non-empty string"
                    )
                ob_summary = obligation.get("summary")
                if not isinstance(ob_summary, str) or not ob_summary.strip():
                    errors.append(
                        f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}].summary must be a non-empty string"
                    )
                ob_evidence = obligation.get("evidence_refs")
                if not isinstance(ob_evidence, list):
                    errors.append(
                        f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}].evidence_refs must be a list of strings"
                    )
                else:
                    for ev_index, ev in enumerate(ob_evidence):
                        if not isinstance(ev, str) or not ev.strip():
                            errors.append(
                                f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}].evidence_refs[{ev_index}] must be non-empty string"
                            )

    totals = payload.get("totals")
    if not isinstance(totals, Mapping):
        errors.append("totals must be an object")
    else:
        expected_total_keys = {
            "peer_projects",
            "existing_links",
            "missing_links",
            "proposed_links",
            "interaction_obligations",
        }
        total_keys = set(totals.keys())
        missing_totals = sorted(expected_total_keys - total_keys)
        if missing_totals:
            errors.append(f"totals missing keys: {missing_totals}")
        unexpected_totals = sorted(total_keys - expected_total_keys)
        if unexpected_totals:
            errors.append(f"totals has unexpected keys: {unexpected_totals}")
        for key in expected_total_keys:
            value = totals.get(key)
            if not isinstance(value, int) or value < 0:
                errors.append(f"totals.{key} must be a non-negative integer")

    return errors


def build_req_030_call_5_sequencing_and_lane_design_reasoning(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build normalized REQ-030 payload for Call-5 sequencing and lane design reasoning."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_030_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_030_ANALYSIS_TYPE}")
    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")

    target_project = _normalize_target_project(raw.get("target_project"))
    constraints = _normalize_req_030_constraints(raw.get("constraints"))
    recommendations = _normalize_req_030_recommendations(raw.get("recommendations"))
    recommendation_ids = {row["recommendation_id"] for row in recommendations}

    reasoning = _require_mapping(
        raw.get("sequencing_and_lane_design_reasoning"),
        field_name="sequencing_and_lane_design_reasoning",
    )
    lanes = _normalize_req_030_lanes(
        reasoning.get("lanes"),
        target_project_id=target_project["project_id"],
        recommendation_ids=recommendation_ids,
    )
    lanes_by_name = {lane["lane_name"]: lane for lane in lanes}
    sequence = _normalize_req_030_sequence(
        reasoning.get("sequence"),
        target_project_id=target_project["project_id"],
        lanes_by_name=lanes_by_name,
        recommendation_ids=recommendation_ids,
    )
    extra_reasoning = sorted(set(reasoning.keys()) - {"lanes", "sequence"})
    if extra_reasoning:
        raise ValueError(f"sequencing_and_lane_design_reasoning has unexpected keys: {extra_reasoning}")

    lane_deps = sum(len(lane["coordination_dependencies"]) for lane in lanes)
    seq_deps = sum(len(item["coordination_dependencies"]) for item in sequence)
    totals = {
        "recommendations": len(recommendations),
        "lanes": len(lanes),
        "sequence_items": len(sequence),
        "lane_dependencies": lane_deps,
        "sequence_dependencies": seq_deps,
        "total_dependencies": lane_deps + seq_deps,
    }

    output_payload = {
        "ok": True,
        "schema_version": REQ_030_SCHEMA_VERSION,
        "requirement_id": REQ_030_REQUIREMENT_ID,
        "analysis_type": REQ_030_ANALYSIS_TYPE,
        "call_id": REQ_030_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "target_project": target_project,
        "constraints": constraints,
        "recommendations": recommendations,
        "sequencing_and_lane_design_reasoning": {
            "lanes": lanes,
            "sequence": sequence,
        },
        "totals": totals,
    }

    errors = validate_req_030_call_5_sequencing_and_lane_design_reasoning(output_payload)
    if errors:
        raise ValueError(f"built REQ-030 payload failed validation: {errors}")
    return output_payload


def validate_req_030_call_5_sequencing_and_lane_design_reasoning(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-030 Call-5 sequencing and lane design reasoning payload shape."""
    errors: list[str] = []

    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    required_top = {
        "ok",
        "schema_version",
        "requirement_id",
        "analysis_type",
        "call_id",
        "checked_at_utc",
        "target_project",
        "constraints",
        "recommendations",
        "sequencing_and_lane_design_reasoning",
        "totals",
    }
    top_keys = set(payload.keys())
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - required_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("ok") is not True:
        errors.append("ok must be true")
    if payload.get("schema_version") != REQ_030_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_030_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_030_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_030_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_030_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_030_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_030_CALL_ID:
        errors.append(f"call_id must be {REQ_030_CALL_ID}")
    if not isinstance(payload.get("checked_at_utc"), str) or not str(payload.get("checked_at_utc")).strip():
        errors.append("checked_at_utc must be a non-empty string")

    target_project = payload.get("target_project")
    target_project_id = ""
    if not isinstance(target_project, Mapping):
        errors.append("target_project must be an object")
    else:
        expected_target_keys = {"project_id", "project_root"}
        target_keys = set(target_project.keys())
        missing_target = sorted(expected_target_keys - target_keys)
        if missing_target:
            errors.append(f"target_project missing keys: {missing_target}")
        unexpected_target = sorted(target_keys - expected_target_keys)
        if unexpected_target:
            errors.append(f"target_project has unexpected keys: {unexpected_target}")
        project_id = target_project.get("project_id")
        if not isinstance(project_id, str) or not project_id.strip():
            errors.append("target_project.project_id must be a non-empty string")
        else:
            target_project_id = project_id
        root = target_project.get("project_root")
        if not isinstance(root, str) or not root.strip():
            errors.append("target_project.project_root must be a non-empty string")
        elif not root.startswith("/"):
            errors.append("target_project.project_root must be an absolute path")

    constraints = payload.get("constraints")
    if not isinstance(constraints, Mapping):
        errors.append("constraints must be an object")
    else:
        expected_constraint_keys = {"max_parallel_lanes", "max_active_work_items", "notes"}
        constraint_keys = set(constraints.keys())
        missing_constraints = sorted(expected_constraint_keys - constraint_keys)
        if missing_constraints:
            errors.append(f"constraints missing keys: {missing_constraints}")
        unexpected_constraints = sorted(constraint_keys - expected_constraint_keys)
        if unexpected_constraints:
            errors.append(f"constraints has unexpected keys: {unexpected_constraints}")
        for key in ("max_parallel_lanes", "max_active_work_items"):
            value = constraints.get(key)
            if not isinstance(value, int) or value <= 0:
                errors.append(f"constraints.{key} must be a positive integer")
        notes = constraints.get("notes")
        if not isinstance(notes, list):
            errors.append("constraints.notes must be a list of strings")
        else:
            for idx, note in enumerate(notes):
                if not isinstance(note, str) or not note.strip():
                    errors.append(f"constraints.notes[{idx}] must be a non-empty string")

    recommendations = payload.get("recommendations")
    recommendation_ids: set[str] = set()
    if not isinstance(recommendations, list) or not recommendations:
        errors.append("recommendations must be a non-empty list")
    else:
        for idx, rec in enumerate(recommendations):
            if not isinstance(rec, Mapping):
                errors.append(f"recommendations[{idx}] must be an object")
                continue
            expected_rec_keys = {"recommendation_id", "summary", "rationale", "expected_impact", "risk_level"}
            rec_keys = set(rec.keys())
            missing_rec = sorted(expected_rec_keys - rec_keys)
            if missing_rec:
                errors.append(f"recommendations[{idx}] missing keys: {missing_rec}")
            unexpected_rec = sorted(rec_keys - expected_rec_keys)
            if unexpected_rec:
                errors.append(f"recommendations[{idx}] has unexpected keys: {unexpected_rec}")
            rec_id = rec.get("recommendation_id")
            if not isinstance(rec_id, str) or not rec_id.strip():
                errors.append(f"recommendations[{idx}].recommendation_id must be a non-empty string")
            elif rec_id in recommendation_ids:
                errors.append(f"recommendations[{idx}].recommendation_id must be unique (duplicate: {rec_id})")
            else:
                recommendation_ids.add(rec_id)
            for key in ("summary", "rationale", "expected_impact"):
                value = rec.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"recommendations[{idx}].{key} must be a non-empty string")
            risk_level = rec.get("risk_level")
            if risk_level not in _RISK_LEVELS:
                errors.append(f"recommendations[{idx}].risk_level must be one of: {list(_RISK_LEVELS)}")

    reasoning = payload.get("sequencing_and_lane_design_reasoning")
    if not isinstance(reasoning, Mapping):
        errors.append("sequencing_and_lane_design_reasoning must be an object")
        return errors

    expected_reasoning_keys = {"lanes", "sequence"}
    reasoning_keys = set(reasoning.keys())
    missing_reasoning = sorted(expected_reasoning_keys - reasoning_keys)
    if missing_reasoning:
        errors.append(f"sequencing_and_lane_design_reasoning missing keys: {missing_reasoning}")
    unexpected_reasoning = sorted(reasoning_keys - expected_reasoning_keys)
    if unexpected_reasoning:
        errors.append(f"sequencing_and_lane_design_reasoning has unexpected keys: {unexpected_reasoning}")

    lanes = reasoning.get("lanes")
    lanes_by_name: dict[str, Mapping[str, Any]] = {}
    if not isinstance(lanes, list) or not lanes:
        errors.append("sequencing_and_lane_design_reasoning.lanes must be a non-empty list")
        lanes = []
    else:
        for idx, lane in enumerate(lanes):
            if not isinstance(lane, Mapping):
                errors.append(f"sequencing_and_lane_design_reasoning.lanes[{idx}] must be an object")
                continue
            expected_lane_keys = {
                "lane_id",
                "lane_name",
                "lane_kind",
                "lane_goal",
                "why_now",
                "recommendation_ids",
                "coordination_dependencies",
            }
            lane_keys = set(lane.keys())
            missing_lane = sorted(expected_lane_keys - lane_keys)
            if missing_lane:
                errors.append(f"sequencing_and_lane_design_reasoning.lanes[{idx}] missing keys: {missing_lane}")
            unexpected_lane = sorted(lane_keys - expected_lane_keys)
            if unexpected_lane:
                errors.append(f"sequencing_and_lane_design_reasoning.lanes[{idx}] has unexpected keys: {unexpected_lane}")
            lane_id = lane.get("lane_id")
            if not isinstance(lane_id, str) or not lane_id.startswith("lane.") or len(lane_id) < 7:
                errors.append(f"sequencing_and_lane_design_reasoning.lanes[{idx}].lane_id must be like lane.<id>")
            lane_name = lane.get("lane_name")
            if not isinstance(lane_name, str) or not lane_name.strip():
                errors.append(f"sequencing_and_lane_design_reasoning.lanes[{idx}].lane_name must be a non-empty string")
            else:
                if lane_name in lanes_by_name:
                    errors.append(
                        f"sequencing_and_lane_design_reasoning.lanes[{idx}].lane_name must be unique (duplicate: {lane_name})"
                    )
                else:
                    lanes_by_name[lane_name] = lane
            for key in ("lane_kind", "lane_goal", "why_now"):
                value = lane.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"sequencing_and_lane_design_reasoning.lanes[{idx}].{key} must be a non-empty string")
            rec_ids = lane.get("recommendation_ids")
            if not isinstance(rec_ids, list) or not rec_ids:
                errors.append(f"sequencing_and_lane_design_reasoning.lanes[{idx}].recommendation_ids must be a non-empty list")
            else:
                for ridx, rec_id in enumerate(rec_ids):
                    if not isinstance(rec_id, str) or not rec_id.strip():
                        errors.append(
                            f"sequencing_and_lane_design_reasoning.lanes[{idx}].recommendation_ids[{ridx}] must be a non-empty string"
                        )
                    elif recommendation_ids and rec_id not in recommendation_ids:
                        errors.append(
                            f"sequencing_and_lane_design_reasoning.lanes[{idx}].recommendation_ids[{ridx}] must be declared in recommendations"
                        )
            deps = lane.get("coordination_dependencies")
            if not isinstance(deps, list):
                errors.append(f"sequencing_and_lane_design_reasoning.lanes[{idx}].coordination_dependencies must be a list")
            else:
                for didx, dep in enumerate(deps):
                    _validate_req_030_dependency(
                        dep,
                        errors=errors,
                        field_prefix=f"sequencing_and_lane_design_reasoning.lanes[{idx}].coordination_dependencies[{didx}]",
                    )

    sequence = reasoning.get("sequence")
    orders_seen: set[int] = set()
    recommendation_seen: set[str] = set()
    if not isinstance(sequence, list) or not sequence:
        errors.append("sequencing_and_lane_design_reasoning.sequence must be a non-empty list")
    else:
        for idx, item in enumerate(sequence):
            if not isinstance(item, Mapping):
                errors.append(f"sequencing_and_lane_design_reasoning.sequence[{idx}] must be an object")
                continue
            expected_seq_keys = {
                "sequence_id",
                "order",
                "recommendation_id",
                "lane_id",
                "lane_name",
                "why_now",
                "coordination_dependencies",
            }
            seq_keys = set(item.keys())
            missing_seq = sorted(expected_seq_keys - seq_keys)
            if missing_seq:
                errors.append(f"sequencing_and_lane_design_reasoning.sequence[{idx}] missing keys: {missing_seq}")
            unexpected_seq = sorted(seq_keys - expected_seq_keys)
            if unexpected_seq:
                errors.append(f"sequencing_and_lane_design_reasoning.sequence[{idx}] has unexpected keys: {unexpected_seq}")
            seq_id = item.get("sequence_id")
            if not isinstance(seq_id, str) or not seq_id.startswith("seq.") or len(seq_id) < 6:
                errors.append(f"sequencing_and_lane_design_reasoning.sequence[{idx}].sequence_id must be like seq.<id>")
            order = item.get("order")
            if not isinstance(order, int) or order <= 0:
                errors.append(f"sequencing_and_lane_design_reasoning.sequence[{idx}].order must be a positive integer")
            elif order in orders_seen:
                errors.append(
                    f"sequencing_and_lane_design_reasoning.sequence[{idx}].order must be unique (duplicate: {order})"
                )
            else:
                orders_seen.add(order)
            rec_id = item.get("recommendation_id")
            if not isinstance(rec_id, str) or not rec_id.strip():
                errors.append(
                    f"sequencing_and_lane_design_reasoning.sequence[{idx}].recommendation_id must be a non-empty string"
                )
            else:
                if recommendation_ids and rec_id not in recommendation_ids:
                    errors.append(
                        f"sequencing_and_lane_design_reasoning.sequence[{idx}].recommendation_id must be declared in recommendations"
                    )
                if rec_id in recommendation_seen:
                    errors.append(
                        f"sequencing_and_lane_design_reasoning.sequence[{idx}].recommendation_id must be unique (duplicate: {rec_id})"
                    )
                else:
                    recommendation_seen.add(rec_id)
            lane_id = item.get("lane_id")
            if not isinstance(lane_id, str) or not lane_id.startswith("lane.") or len(lane_id) < 7:
                errors.append(f"sequencing_and_lane_design_reasoning.sequence[{idx}].lane_id must be like lane.<id>")
            lane_name = item.get("lane_name")
            if not isinstance(lane_name, str) or not lane_name.strip():
                errors.append(f"sequencing_and_lane_design_reasoning.sequence[{idx}].lane_name must be a non-empty string")
            elif lanes_by_name and lane_name not in lanes_by_name:
                errors.append(f"sequencing_and_lane_design_reasoning.sequence[{idx}].lane_name must match a declared lane")
            why_now = item.get("why_now")
            if not isinstance(why_now, str) or not why_now.strip():
                errors.append(f"sequencing_and_lane_design_reasoning.sequence[{idx}].why_now must be a non-empty string")
            deps = item.get("coordination_dependencies")
            if not isinstance(deps, list):
                errors.append(f"sequencing_and_lane_design_reasoning.sequence[{idx}].coordination_dependencies must be a list")
            else:
                for didx, dep in enumerate(deps):
                    _validate_req_030_dependency(
                        dep,
                        errors=errors,
                        field_prefix=f"sequencing_and_lane_design_reasoning.sequence[{idx}].coordination_dependencies[{didx}]",
                    )

    totals = payload.get("totals")
    if not isinstance(totals, Mapping):
        errors.append("totals must be an object")
    else:
        expected_total_keys = {
            "recommendations",
            "lanes",
            "sequence_items",
            "lane_dependencies",
            "sequence_dependencies",
            "total_dependencies",
        }
        total_keys = set(totals.keys())
        missing_totals = sorted(expected_total_keys - total_keys)
        if missing_totals:
            errors.append(f"totals missing keys: {missing_totals}")
        unexpected_totals = sorted(total_keys - expected_total_keys)
        if unexpected_totals:
            errors.append(f"totals has unexpected keys: {unexpected_totals}")
        for key in expected_total_keys:
            value = totals.get(key)
            if not isinstance(value, int) or value < 0:
                errors.append(f"totals.{key} must be a non-negative integer")

    if target_project_id and not recommendation_ids:
        errors.append("recommendations must be a non-empty list")

    return errors


def build_req_035_evidence_citation_discipline_in_reasoning_calls(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build normalized REQ-035 payload for evidence citation discipline in reasoning calls."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_035_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_035_ANALYSIS_TYPE}")
    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")

    context_provenance_ledger = _normalize_req_035_context_provenance_ledger(raw.get("context_provenance_ledger"))
    if context_provenance_ledger["ledger_requirement_id"] != "REQ-021":
        raise ValueError("context_provenance_ledger.ledger_requirement_id must be REQ-021")
    reasoning_calls = _normalize_req_035_reasoning_calls(raw.get("reasoning_calls"))

    extra = sorted(set(raw.keys()) - {"analysis_type", "now_utc", "context_provenance_ledger", "reasoning_calls"})
    if extra:
        raise ValueError(f"payload has unexpected keys: {extra}")

    ledger_evidence_ids = set(context_provenance_ledger["evidence_ids"])
    strategic_claim_citation_status: list[dict[str, Any]] = []
    flagged_claims: list[dict[str, Any]] = []
    final_recommendations: list[dict[str, Any]] = []

    for call in reasoning_calls:
        call_id = call["call_id"]
        for claim in call["strategic_claims"]:
            strategic_claim_id = claim["strategic_claim_id"]
            summary = claim["summary"]
            evidence_ids = list(claim["evidence_ids"])
            recommendation = claim["recommendation"]
            recommendation_id = recommendation["recommendation_id"]
            unknown_evidence_ids = sorted({ev for ev in evidence_ids if ev not in ledger_evidence_ids})
            flag_reason_codes: list[str] = []
            if not evidence_ids:
                flag_reason_codes.append("uncited_strategic_claim")
            if unknown_evidence_ids:
                flag_reason_codes.append("evidence_id_not_in_context_provenance_ledger")

            citation_status = "flagged" if flag_reason_codes else "cited"
            status_row = {
                "strategic_claim_id": strategic_claim_id,
                "call_id": call_id,
                "recommendation_id": recommendation_id,
                "summary": summary,
                "evidence_ids": evidence_ids,
                "citation_status": citation_status,
                "flag_reason_codes": flag_reason_codes,
            }
            strategic_claim_citation_status.append(status_row)

            if citation_status == "flagged":
                flagged_claims.append(
                    {
                        "strategic_claim_id": strategic_claim_id,
                        "call_id": call_id,
                        "recommendation_id": recommendation_id,
                        "summary": summary,
                        "evidence_ids": evidence_ids,
                        "flag_reason_codes": flag_reason_codes,
                        "unknown_evidence_ids": unknown_evidence_ids,
                        "excluded_from_final_recommendations": True,
                    }
                )
                continue

            final_recommendations.append(
                {
                    "recommendation_id": recommendation_id,
                    "call_id": call_id,
                    "strategic_claim_id": strategic_claim_id,
                    "summary": recommendation["summary"],
                    "rationale": recommendation["rationale"],
                    "confidence_tag": recommendation["confidence_tag"],
                    "evidence_ids": evidence_ids,
                }
            )

    strategic_claim_citation_status.sort(
        key=lambda row: (row["call_id"], row["strategic_claim_id"], row["recommendation_id"])
    )
    flagged_claims.sort(key=lambda row: (row["call_id"], row["strategic_claim_id"], row["recommendation_id"]))
    final_recommendations.sort(key=lambda row: row["recommendation_id"])

    totals = {
        "reasoning_calls": len(reasoning_calls),
        "strategic_claims": len(strategic_claim_citation_status),
        "cited_claims": sum(1 for row in strategic_claim_citation_status if row["citation_status"] == "cited"),
        "flagged_claims": len(flagged_claims),
        "final_recommendations": len(final_recommendations),
    }

    output_payload = {
        "ok": True,
        "schema_version": REQ_035_SCHEMA_VERSION,
        "requirement_id": REQ_035_REQUIREMENT_ID,
        "analysis_type": REQ_035_ANALYSIS_TYPE,
        "call_id": REQ_035_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "context_provenance_ledger": context_provenance_ledger,
        "reasoning_calls": reasoning_calls,
        "evidence_citation_discipline": {
            "strategic_claim_citation_status": strategic_claim_citation_status,
            "flagged_claims": flagged_claims,
            "final_recommendations": final_recommendations,
        },
        "totals": totals,
    }

    errors = validate_req_035_evidence_citation_discipline_in_reasoning_calls(output_payload)
    if errors:
        raise ValueError(f"built REQ-035 payload failed validation: {errors}")
    return output_payload


def validate_req_035_evidence_citation_discipline_in_reasoning_calls(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-035 evidence citation discipline payload shape."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    required_top = {
        "ok",
        "schema_version",
        "requirement_id",
        "analysis_type",
        "call_id",
        "checked_at_utc",
        "context_provenance_ledger",
        "reasoning_calls",
        "evidence_citation_discipline",
        "totals",
    }
    top_keys = set(payload.keys())
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - required_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("ok") is not True:
        errors.append("ok must be true")
    if payload.get("schema_version") != REQ_035_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_035_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_035_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_035_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_035_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_035_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_035_CALL_ID:
        errors.append(f"call_id must be {REQ_035_CALL_ID}")
    if not isinstance(payload.get("checked_at_utc"), str) or not str(payload.get("checked_at_utc")).strip():
        errors.append("checked_at_utc must be a non-empty string")

    ledger = payload.get("context_provenance_ledger")
    ledger_evidence_ids: set[str] = set()
    if not isinstance(ledger, Mapping):
        errors.append("context_provenance_ledger must be an object")
    else:
        expected_ledger_keys = {"ledger_requirement_id", "ledger_scope", "evidence_ids"}
        ledger_keys = set(ledger.keys())
        missing_ledger = sorted(expected_ledger_keys - ledger_keys)
        if missing_ledger:
            errors.append(f"context_provenance_ledger missing keys: {missing_ledger}")
        unexpected_ledger = sorted(ledger_keys - expected_ledger_keys)
        if unexpected_ledger:
            errors.append(f"context_provenance_ledger has unexpected keys: {unexpected_ledger}")
        if ledger.get("ledger_requirement_id") != "REQ-021":
            errors.append("context_provenance_ledger.ledger_requirement_id must be REQ-021")
        ledger_scope = ledger.get("ledger_scope")
        if not isinstance(ledger_scope, str) or not ledger_scope.strip():
            errors.append("context_provenance_ledger.ledger_scope must be a non-empty string")
        evidence_ids = ledger.get("evidence_ids")
        if not isinstance(evidence_ids, list) or not evidence_ids:
            errors.append("context_provenance_ledger.evidence_ids must be a non-empty list")
        else:
            for idx, evidence_id in enumerate(evidence_ids):
                if not isinstance(evidence_id, str) or not evidence_id.strip():
                    errors.append(f"context_provenance_ledger.evidence_ids[{idx}] must be a non-empty string")
                elif not evidence_id.startswith("claim-"):
                    errors.append(
                        f"context_provenance_ledger.evidence_ids[{idx}] must use REQ-021 claim id format (claim-<id>)"
                    )
                else:
                    ledger_evidence_ids.add(evidence_id)

    reasoning_calls = payload.get("reasoning_calls")
    reasoning_claim_refs: set[tuple[str, str, str]] = set()
    if not isinstance(reasoning_calls, list) or not reasoning_calls:
        errors.append("reasoning_calls must be a non-empty list")
        reasoning_calls = []
    else:
        seen_call_ids: set[str] = set()
        seen_recommendation_ids: set[str] = set()
        for cidx, call in enumerate(reasoning_calls):
            if not isinstance(call, Mapping):
                errors.append(f"reasoning_calls[{cidx}] must be an object")
                continue
            expected_call_keys = {"call_id", "strategic_claims"}
            call_keys = set(call.keys())
            missing_call = sorted(expected_call_keys - call_keys)
            if missing_call:
                errors.append(f"reasoning_calls[{cidx}] missing keys: {missing_call}")
            unexpected_call = sorted(call_keys - expected_call_keys)
            if unexpected_call:
                errors.append(f"reasoning_calls[{cidx}] has unexpected keys: {unexpected_call}")
            call_id = call.get("call_id")
            if not isinstance(call_id, str) or not call_id.strip():
                errors.append(f"reasoning_calls[{cidx}].call_id must be a non-empty string")
                call_id = ""
            elif call_id in seen_call_ids:
                errors.append(f"reasoning_calls[{cidx}].call_id must be unique (duplicate: {call_id})")
            else:
                seen_call_ids.add(call_id)

            strategic_claims = call.get("strategic_claims")
            if not isinstance(strategic_claims, list) or not strategic_claims:
                errors.append(f"reasoning_calls[{cidx}].strategic_claims must be a non-empty list")
                continue
            seen_claim_ids: set[str] = set()
            for sidx, claim in enumerate(strategic_claims):
                if not isinstance(claim, Mapping):
                    errors.append(f"reasoning_calls[{cidx}].strategic_claims[{sidx}] must be an object")
                    continue
                expected_claim_keys = {"strategic_claim_id", "summary", "evidence_ids", "recommendation"}
                claim_keys = set(claim.keys())
                missing_claim = sorted(expected_claim_keys - claim_keys)
                if missing_claim:
                    errors.append(f"reasoning_calls[{cidx}].strategic_claims[{sidx}] missing keys: {missing_claim}")
                unexpected_claim = sorted(claim_keys - expected_claim_keys)
                if unexpected_claim:
                    errors.append(
                        f"reasoning_calls[{cidx}].strategic_claims[{sidx}] has unexpected keys: {unexpected_claim}"
                    )
                strategic_claim_id = claim.get("strategic_claim_id")
                if not isinstance(strategic_claim_id, str) or not strategic_claim_id.strip():
                    errors.append(
                        f"reasoning_calls[{cidx}].strategic_claims[{sidx}].strategic_claim_id must be a non-empty string"
                    )
                    strategic_claim_id = ""
                elif strategic_claim_id in seen_claim_ids:
                    errors.append(
                        f"reasoning_calls[{cidx}].strategic_claims[{sidx}].strategic_claim_id must be unique within call "
                        f"(duplicate: {strategic_claim_id})"
                    )
                else:
                    seen_claim_ids.add(strategic_claim_id)
                summary = claim.get("summary")
                if not isinstance(summary, str) or not summary.strip():
                    errors.append(f"reasoning_calls[{cidx}].strategic_claims[{sidx}].summary must be a non-empty string")
                evidence_ids = claim.get("evidence_ids")
                if not isinstance(evidence_ids, list):
                    errors.append(
                        f"reasoning_calls[{cidx}].strategic_claims[{sidx}].evidence_ids must be a list of strings"
                    )
                    evidence_ids = []
                else:
                    for evidx, evidence_id in enumerate(evidence_ids):
                        if not isinstance(evidence_id, str) or not evidence_id.strip():
                            errors.append(
                                f"reasoning_calls[{cidx}].strategic_claims[{sidx}].evidence_ids[{evidx}] must be a non-empty string"
                            )
                recommendation = claim.get("recommendation")
                recommendation_id = ""
                if not isinstance(recommendation, Mapping):
                    errors.append(f"reasoning_calls[{cidx}].strategic_claims[{sidx}].recommendation must be an object")
                else:
                    expected_recommendation_keys = {"recommendation_id", "summary", "rationale", "confidence_tag"}
                    recommendation_keys = set(recommendation.keys())
                    missing_recommendation = sorted(expected_recommendation_keys - recommendation_keys)
                    if missing_recommendation:
                        errors.append(
                            f"reasoning_calls[{cidx}].strategic_claims[{sidx}].recommendation missing keys: {missing_recommendation}"
                        )
                    unexpected_recommendation = sorted(recommendation_keys - expected_recommendation_keys)
                    if unexpected_recommendation:
                        errors.append(
                            f"reasoning_calls[{cidx}].strategic_claims[{sidx}].recommendation has unexpected keys: {unexpected_recommendation}"
                        )
                    recommendation_id = recommendation.get("recommendation_id")  # type: ignore[assignment]
                    if not isinstance(recommendation_id, str) or not recommendation_id.strip():
                        errors.append(
                            f"reasoning_calls[{cidx}].strategic_claims[{sidx}].recommendation.recommendation_id must be a non-empty string"
                        )
                        recommendation_id = ""
                    elif recommendation_id in seen_recommendation_ids:
                        errors.append(
                            "reasoning_calls[*].strategic_claims[*].recommendation.recommendation_id must be globally unique "
                            f"(duplicate: {recommendation_id})"
                        )
                    else:
                        seen_recommendation_ids.add(recommendation_id)
                    for key in ("summary", "rationale"):
                        value = recommendation.get(key)
                        if not isinstance(value, str) or not value.strip():
                            errors.append(
                                f"reasoning_calls[{cidx}].strategic_claims[{sidx}].recommendation.{key} must be a non-empty string"
                            )
                    if recommendation.get("confidence_tag") not in _CONFIDENCE_TAGS:
                        errors.append(
                            f"reasoning_calls[{cidx}].strategic_claims[{sidx}].recommendation.confidence_tag must be one of: {list(_CONFIDENCE_TAGS)}"
                        )
                if call_id and strategic_claim_id and recommendation_id:
                    reasoning_claim_refs.add((call_id, strategic_claim_id, recommendation_id))

    discipline = payload.get("evidence_citation_discipline")
    status_refs: set[tuple[str, str, str]] = set()
    flagged_refs: set[tuple[str, str, str]] = set()
    final_recommendation_ids: set[str] = set()
    flagged_recommendation_ids: set[str] = set()
    if not isinstance(discipline, Mapping):
        errors.append("evidence_citation_discipline must be an object")
    else:
        expected_discipline_keys = {
            "strategic_claim_citation_status",
            "flagged_claims",
            "final_recommendations",
        }
        discipline_keys = set(discipline.keys())
        missing_discipline = sorted(expected_discipline_keys - discipline_keys)
        if missing_discipline:
            errors.append(f"evidence_citation_discipline missing keys: {missing_discipline}")
        unexpected_discipline = sorted(discipline_keys - expected_discipline_keys)
        if unexpected_discipline:
            errors.append(f"evidence_citation_discipline has unexpected keys: {unexpected_discipline}")

        status_rows = discipline.get("strategic_claim_citation_status")
        if not isinstance(status_rows, list):
            errors.append("evidence_citation_discipline.strategic_claim_citation_status must be a list")
            status_rows = []
        for idx, row in enumerate(status_rows):
            if not isinstance(row, Mapping):
                errors.append(f"evidence_citation_discipline.strategic_claim_citation_status[{idx}] must be an object")
                continue
            expected_status_keys = {
                "strategic_claim_id",
                "call_id",
                "recommendation_id",
                "summary",
                "evidence_ids",
                "citation_status",
                "flag_reason_codes",
            }
            status_keys = set(row.keys())
            missing_status = sorted(expected_status_keys - status_keys)
            if missing_status:
                errors.append(
                    f"evidence_citation_discipline.strategic_claim_citation_status[{idx}] missing keys: {missing_status}"
                )
            unexpected_status = sorted(status_keys - expected_status_keys)
            if unexpected_status:
                errors.append(
                    f"evidence_citation_discipline.strategic_claim_citation_status[{idx}] has unexpected keys: {unexpected_status}"
                )

            call_id = row.get("call_id")
            claim_id = row.get("strategic_claim_id")
            recommendation_id = row.get("recommendation_id")
            if not isinstance(call_id, str) or not call_id.strip():
                errors.append(
                    f"evidence_citation_discipline.strategic_claim_citation_status[{idx}].call_id must be a non-empty string"
                )
                call_id = ""
            if not isinstance(claim_id, str) or not claim_id.strip():
                errors.append(
                    f"evidence_citation_discipline.strategic_claim_citation_status[{idx}].strategic_claim_id must be a non-empty string"
                )
                claim_id = ""
            if not isinstance(recommendation_id, str) or not recommendation_id.strip():
                errors.append(
                    f"evidence_citation_discipline.strategic_claim_citation_status[{idx}].recommendation_id must be a non-empty string"
                )
                recommendation_id = ""
            if call_id and claim_id and recommendation_id:
                status_refs.add((call_id, claim_id, recommendation_id))

            summary = row.get("summary")
            if not isinstance(summary, str) or not summary.strip():
                errors.append(
                    f"evidence_citation_discipline.strategic_claim_citation_status[{idx}].summary must be a non-empty string"
                )
            evidence_ids = row.get("evidence_ids")
            if not isinstance(evidence_ids, list):
                errors.append(
                    f"evidence_citation_discipline.strategic_claim_citation_status[{idx}].evidence_ids must be a list of strings"
                )
                evidence_ids = []
            else:
                for evidx, evidence_id in enumerate(evidence_ids):
                    if not isinstance(evidence_id, str) or not evidence_id.strip():
                        errors.append(
                            "evidence_citation_discipline.strategic_claim_citation_status"
                            f"[{idx}].evidence_ids[{evidx}] must be a non-empty string"
                        )

            citation_status = row.get("citation_status")
            if citation_status not in {"cited", "flagged"}:
                errors.append(
                    "evidence_citation_discipline.strategic_claim_citation_status"
                    f"[{idx}].citation_status must be one of: ['cited', 'flagged']"
                )
            flag_reason_codes = row.get("flag_reason_codes")
            if not isinstance(flag_reason_codes, list):
                errors.append(
                    f"evidence_citation_discipline.strategic_claim_citation_status[{idx}].flag_reason_codes must be a list of strings"
                )
                flag_reason_codes = []
            else:
                for rcidx, reason in enumerate(flag_reason_codes):
                    if not isinstance(reason, str) or not reason.strip():
                        errors.append(
                            "evidence_citation_discipline.strategic_claim_citation_status"
                            f"[{idx}].flag_reason_codes[{rcidx}] must be a non-empty string"
                        )

            if citation_status == "cited":
                if flag_reason_codes:
                    errors.append(
                        f"evidence_citation_discipline.strategic_claim_citation_status[{idx}] cited claims must have empty flag_reason_codes"
                    )
                if not evidence_ids:
                    errors.append(
                        f"evidence_citation_discipline.strategic_claim_citation_status[{idx}] cited claims must include evidence_ids"
                    )
                for evidence_id in evidence_ids:
                    if isinstance(evidence_id, str) and evidence_id and ledger_evidence_ids and evidence_id not in ledger_evidence_ids:
                        errors.append(
                            f"evidence_citation_discipline.strategic_claim_citation_status[{idx}] evidence_ids must exist in context_provenance_ledger.evidence_ids"
                        )
            elif citation_status == "flagged":
                if not flag_reason_codes:
                    errors.append(
                        f"evidence_citation_discipline.strategic_claim_citation_status[{idx}] flagged claims must include flag_reason_codes"
                    )
                if call_id and claim_id and recommendation_id:
                    flagged_refs.add((call_id, claim_id, recommendation_id))

        flagged_rows = discipline.get("flagged_claims")
        if not isinstance(flagged_rows, list):
            errors.append("evidence_citation_discipline.flagged_claims must be a list")
            flagged_rows = []
        for idx, row in enumerate(flagged_rows):
            if not isinstance(row, Mapping):
                errors.append(f"evidence_citation_discipline.flagged_claims[{idx}] must be an object")
                continue
            expected_flagged_keys = {
                "strategic_claim_id",
                "call_id",
                "recommendation_id",
                "summary",
                "evidence_ids",
                "flag_reason_codes",
                "unknown_evidence_ids",
                "excluded_from_final_recommendations",
            }
            flagged_keys = set(row.keys())
            missing_flagged = sorted(expected_flagged_keys - flagged_keys)
            if missing_flagged:
                errors.append(f"evidence_citation_discipline.flagged_claims[{idx}] missing keys: {missing_flagged}")
            unexpected_flagged = sorted(flagged_keys - expected_flagged_keys)
            if unexpected_flagged:
                errors.append(
                    f"evidence_citation_discipline.flagged_claims[{idx}] has unexpected keys: {unexpected_flagged}"
                )

            call_id = row.get("call_id")
            claim_id = row.get("strategic_claim_id")
            recommendation_id = row.get("recommendation_id")
            if isinstance(call_id, str) and call_id.strip() and isinstance(claim_id, str) and claim_id.strip() and isinstance(recommendation_id, str) and recommendation_id.strip():
                flagged_refs.add((call_id, claim_id, recommendation_id))
            else:
                if not isinstance(call_id, str) or not call_id.strip():
                    errors.append(f"evidence_citation_discipline.flagged_claims[{idx}].call_id must be a non-empty string")
                if not isinstance(claim_id, str) or not claim_id.strip():
                    errors.append(
                        f"evidence_citation_discipline.flagged_claims[{idx}].strategic_claim_id must be a non-empty string"
                    )
                if not isinstance(recommendation_id, str) or not recommendation_id.strip():
                    errors.append(
                        f"evidence_citation_discipline.flagged_claims[{idx}].recommendation_id must be a non-empty string"
                    )

            summary = row.get("summary")
            if not isinstance(summary, str) or not summary.strip():
                errors.append(f"evidence_citation_discipline.flagged_claims[{idx}].summary must be a non-empty string")
            evidence_ids = row.get("evidence_ids")
            if not isinstance(evidence_ids, list):
                errors.append(f"evidence_citation_discipline.flagged_claims[{idx}].evidence_ids must be a list of strings")
                evidence_ids = []
            else:
                for evidx, evidence_id in enumerate(evidence_ids):
                    if not isinstance(evidence_id, str) or not evidence_id.strip():
                        errors.append(
                            f"evidence_citation_discipline.flagged_claims[{idx}].evidence_ids[{evidx}] must be a non-empty string"
                        )
            reason_codes = row.get("flag_reason_codes")
            if not isinstance(reason_codes, list) or not reason_codes:
                errors.append(
                    f"evidence_citation_discipline.flagged_claims[{idx}].flag_reason_codes must be a non-empty list"
                )
            else:
                for rcidx, reason in enumerate(reason_codes):
                    if not isinstance(reason, str) or not reason.strip():
                        errors.append(
                            f"evidence_citation_discipline.flagged_claims[{idx}].flag_reason_codes[{rcidx}] must be a non-empty string"
                        )
            unknown_evidence_ids = row.get("unknown_evidence_ids")
            if not isinstance(unknown_evidence_ids, list):
                errors.append(
                    f"evidence_citation_discipline.flagged_claims[{idx}].unknown_evidence_ids must be a list of strings"
                )
            else:
                for evidx, evidence_id in enumerate(unknown_evidence_ids):
                    if not isinstance(evidence_id, str) or not evidence_id.strip():
                        errors.append(
                            f"evidence_citation_discipline.flagged_claims[{idx}].unknown_evidence_ids[{evidx}] must be a non-empty string"
                        )
                    elif ledger_evidence_ids and evidence_id in ledger_evidence_ids:
                        errors.append(
                            f"evidence_citation_discipline.flagged_claims[{idx}].unknown_evidence_ids[{evidx}] must not exist in context_provenance_ledger.evidence_ids"
                        )
            if row.get("excluded_from_final_recommendations") is not True:
                errors.append(
                    f"evidence_citation_discipline.flagged_claims[{idx}].excluded_from_final_recommendations must be true"
                )
            if isinstance(recommendation_id, str) and recommendation_id.strip():
                flagged_recommendation_ids.add(recommendation_id)

        final_rows = discipline.get("final_recommendations")
        if not isinstance(final_rows, list):
            errors.append("evidence_citation_discipline.final_recommendations must be a list")
            final_rows = []
        for idx, row in enumerate(final_rows):
            if not isinstance(row, Mapping):
                errors.append(f"evidence_citation_discipline.final_recommendations[{idx}] must be an object")
                continue
            expected_final_keys = {
                "recommendation_id",
                "call_id",
                "strategic_claim_id",
                "summary",
                "rationale",
                "confidence_tag",
                "evidence_ids",
            }
            final_keys = set(row.keys())
            missing_final = sorted(expected_final_keys - final_keys)
            if missing_final:
                errors.append(f"evidence_citation_discipline.final_recommendations[{idx}] missing keys: {missing_final}")
            unexpected_final = sorted(final_keys - expected_final_keys)
            if unexpected_final:
                errors.append(
                    f"evidence_citation_discipline.final_recommendations[{idx}] has unexpected keys: {unexpected_final}"
                )
            recommendation_id = row.get("recommendation_id")
            if not isinstance(recommendation_id, str) or not recommendation_id.strip():
                errors.append(
                    f"evidence_citation_discipline.final_recommendations[{idx}].recommendation_id must be a non-empty string"
                )
                recommendation_id = ""
            elif recommendation_id in final_recommendation_ids:
                errors.append(
                    f"evidence_citation_discipline.final_recommendations[{idx}].recommendation_id must be unique (duplicate: {recommendation_id})"
                )
            else:
                final_recommendation_ids.add(recommendation_id)
            call_id = row.get("call_id")
            if not isinstance(call_id, str) or not call_id.strip():
                errors.append(
                    f"evidence_citation_discipline.final_recommendations[{idx}].call_id must be a non-empty string"
                )
                call_id = ""
            claim_id = row.get("strategic_claim_id")
            if not isinstance(claim_id, str) or not claim_id.strip():
                errors.append(
                    f"evidence_citation_discipline.final_recommendations[{idx}].strategic_claim_id must be a non-empty string"
                )
                claim_id = ""
            for key in ("summary", "rationale"):
                value = row.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(
                        f"evidence_citation_discipline.final_recommendations[{idx}].{key} must be a non-empty string"
                    )
            confidence_tag = row.get("confidence_tag")
            if confidence_tag not in _CONFIDENCE_TAGS:
                errors.append(
                    f"evidence_citation_discipline.final_recommendations[{idx}].confidence_tag must be one of: {list(_CONFIDENCE_TAGS)}"
                )
            evidence_ids = row.get("evidence_ids")
            if not isinstance(evidence_ids, list) or not evidence_ids:
                errors.append(
                    f"evidence_citation_discipline.final_recommendations[{idx}].evidence_ids must be a non-empty list of strings"
                )
            else:
                for evidx, evidence_id in enumerate(evidence_ids):
                    if not isinstance(evidence_id, str) or not evidence_id.strip():
                        errors.append(
                            f"evidence_citation_discipline.final_recommendations[{idx}].evidence_ids[{evidx}] must be a non-empty string"
                        )
                    elif ledger_evidence_ids and evidence_id not in ledger_evidence_ids:
                        errors.append(
                            f"evidence_citation_discipline.final_recommendations[{idx}].evidence_ids[{evidx}] must exist in context_provenance_ledger.evidence_ids"
                        )

    if reasoning_claim_refs and status_refs != reasoning_claim_refs:
        errors.append("evidence_citation_discipline.strategic_claim_citation_status must cover all reasoning_calls strategic claims")
    if flagged_refs and status_refs and not flagged_refs.issubset(status_refs):
        errors.append("evidence_citation_discipline.flagged_claims entries must exist in strategic_claim_citation_status")
    if flagged_recommendation_ids and final_recommendation_ids and (flagged_recommendation_ids & final_recommendation_ids):
        errors.append("flagged claims must be excluded from evidence_citation_discipline.final_recommendations")

    totals = payload.get("totals")
    if not isinstance(totals, Mapping):
        errors.append("totals must be an object")
    else:
        expected_totals = {
            "reasoning_calls",
            "strategic_claims",
            "cited_claims",
            "flagged_claims",
            "final_recommendations",
        }
        totals_keys = set(totals.keys())
        missing_totals = sorted(expected_totals - totals_keys)
        if missing_totals:
            errors.append(f"totals missing keys: {missing_totals}")
        unexpected_totals = sorted(totals_keys - expected_totals)
        if unexpected_totals:
            errors.append(f"totals has unexpected keys: {unexpected_totals}")
        for key in expected_totals:
            value = totals.get(key)
            if not isinstance(value, int) or value < 0:
                errors.append(f"totals.{key} must be a non-negative integer")

        expected_reasoning_calls = len(reasoning_calls) if isinstance(reasoning_calls, list) else None
        if expected_reasoning_calls is not None and isinstance(totals.get("reasoning_calls"), int):
            if totals["reasoning_calls"] != expected_reasoning_calls:
                errors.append("totals.reasoning_calls must equal len(reasoning_calls)")
        if isinstance(totals.get("strategic_claims"), int) and status_refs:
            if totals["strategic_claims"] != len(status_refs):
                errors.append("totals.strategic_claims must equal len(strategic_claim_citation_status)")
        if isinstance(totals.get("flagged_claims"), int) and flagged_refs:
            if totals["flagged_claims"] != len(flagged_refs):
                errors.append("totals.flagged_claims must equal len(flagged_claims)")
        if isinstance(totals.get("final_recommendations"), int) and final_recommendation_ids:
            if totals["final_recommendations"] != len(final_recommendation_ids):
                errors.append("totals.final_recommendations must equal len(final_recommendations)")
        if isinstance(totals.get("cited_claims"), int) and status_refs:
            expected_cited = len(status_refs) - len(flagged_refs)
            if totals["cited_claims"] != expected_cited:
                errors.append("totals.cited_claims must equal strategic_claims - flagged_claims")

    return errors


def _validate_req_030_dependency(raw_value: Any, *, errors: list[str], field_prefix: str) -> None:
    if not isinstance(raw_value, Mapping):
        errors.append(f"{field_prefix} must be an object")
        return
    expected_keys = {"dependency_id", "dependency_kind", "depends_on_type", "depends_on", "summary"}
    keys = set(raw_value.keys())
    missing = sorted(expected_keys - keys)
    if missing:
        errors.append(f"{field_prefix} missing keys: {missing}")
    extra = sorted(keys - expected_keys)
    if extra:
        errors.append(f"{field_prefix} has unexpected keys: {extra}")
    dep_id = raw_value.get("dependency_id")
    if not isinstance(dep_id, str) or not dep_id.startswith("dep.") or len(dep_id) < 6:
        errors.append(f"{field_prefix}.dependency_id must be like dep.<id>")
    dep_kind = raw_value.get("dependency_kind")
    if not isinstance(dep_kind, str) or not dep_kind.strip():
        errors.append(f"{field_prefix}.dependency_kind must be a non-empty string")
    dep_on = raw_value.get("depends_on")
    if not isinstance(dep_on, str) or not dep_on.strip():
        errors.append(f"{field_prefix}.depends_on must be a non-empty string")
    dep_type = raw_value.get("depends_on_type")
    if dep_type not in _DEPENDS_ON_TYPES:
        errors.append(f"{field_prefix}.depends_on_type must be one of: {list(_DEPENDS_ON_TYPES)}")
    summary = raw_value.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        errors.append(f"{field_prefix}.summary must be a non-empty string")


def run(payload: dict[str, Any]) -> dict[str, Any]:
    analysis_type = str(payload.get("analysis_type") or "").strip()
    if analysis_type == REQ_035_ANALYSIS_TYPE:
        return build_req_035_evidence_citation_discipline_in_reasoning_calls(payload)
    if analysis_type == REQ_030_ANALYSIS_TYPE:
        return build_req_030_call_5_sequencing_and_lane_design_reasoning(payload)
    if analysis_type and analysis_type != REQ_027_ANALYSIS_TYPE:
        raise ValueError(
            f"analysis_type must be {REQ_027_ANALYSIS_TYPE} or {REQ_030_ANALYSIS_TYPE} or {REQ_035_ANALYSIS_TYPE}"
        )
    return build_req_027_call_2_ecosystem_linkage_reasoning(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Strategy LLM pipeline contract surface (REQ-027 Call-2, REQ-030 Call-5, REQ-035)."
    )
    parser.add_argument("--input-json", required=True, help='Input payload path or "-" for stdin.')
    parser.add_argument("--output-json", default="-", help='Output path or "-" for stdout.')
    parser.add_argument("--json-pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args(sys.argv[1:] if argv is None else list(argv))

    if args.input_json == "-":
        raw_payload = json.loads(sys.stdin.read())
    else:
        raw_payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    if not isinstance(raw_payload, dict):
        raise SystemExit("input payload must be a JSON object")

    output_payload = run(raw_payload)
    rendered = json.dumps(output_payload, indent=2 if args.json_pretty else None, sort_keys=False)
    if args.output_json == "-":
        print(rendered)
    else:
        target = Path(args.output_json)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
