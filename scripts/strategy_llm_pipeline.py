#!/usr/bin/env python3
"""REQ-025, REQ-026, REQ-029, and REQ-031 contract/data-model surface for strategy LLM pipeline flows."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

TOOL = "strategy-llm-pipeline"
TOOL_VERSION = "1.0.0"
REPO_ROOT = Path(__file__).resolve().parents[1]
REQ_025_REQUIREMENT_ID = "REQ-025"
REQ_025_SCHEMA_VERSION = "req-025.multi-call-strategy-pipeline-planner.v1"
REQ_025_LLM_CALL_TRACE_SCHEMA_VERSION = "req-025.llm-call-trace-row.v1"
REQ_026_REQUIREMENT_ID = "REQ-026"
REQ_026_SCHEMA_VERSION = "req-026.call-1-situational-analysis-reasoning.v1"
REQ_026_LLM_CALL_TRACE_SCHEMA_VERSION = "req-026.llm-call-trace-row.v1"
REQ_026_ANALYSIS_TYPE = "call_1_situational_analysis_reasoning"
REQ_026_PROCESSING_STRATEGY = "call-1-situational-analysis"
REQ_026_REASONING_MODE = "deterministic-broad-sweep"
REQ_029_REQUIREMENT_ID = "REQ-029"
REQ_029_SCHEMA_VERSION = "req-029.call-4-recommendation-synthesis.v1"
REQ_029_LLM_CALL_TRACE_SCHEMA_VERSION = "req-029.llm-call-trace-row.v1"
REQ_029_ANALYSIS_TYPE = "call_4_recommendation_synthesis"
REQ_029_PROCESSING_STRATEGY = "call-4-recommendation-synthesis"
REQ_029_REASONING_MODE = "deterministic-recommendation-synthesis"
REQ_029_CALL_ID = "call-4"
REQ_029_ALLOWED_SOURCE_CALL_IDS = ("call-1", "call-2", "call-3")
REQ_029_ALLOWED_RECOMMENDATION_SCOPES = {"local", "cross-project"}
REQ_029_RECOMMENDATION_ID_RE = re.compile(r"^rec\.[a-z0-9]+(?:-[a-z0-9]+)*$")
REQ_029_RECOMMENDATION_ID_SCHEMA = "rec-call-4-{source_call_id}-{candidate_id}"
REQ_029_REQUIRED_DRAFT_FIELDS = [
    "recommendation_id",
    "source_call_id",
    "source_output_ref",
    "source_candidate_id",
    "summary",
    "rationale",
    "impact",
    "risk",
    "evidence_refs",
]
REQ_029_CALL_OBJECTIVES = {
    "call-1": "Assess target state and surface deterministic unknown-resolution candidates.",
    "call-2": "Refine situational constraints into bounded implementation follow-up candidates.",
    "call-3": "Align execution dependencies and cross-project coordination candidates.",
    "call-4": "Synthesize candidate recommendations from earlier call outputs into deterministic structured recommendation drafts.",
}
REQ_031_REQUIREMENT_ID = "REQ-031"
REQ_031_SCHEMA_VERSION = "req-031.call-6-kpi-impact-estimation-reasoning.v1"
REQ_031_LLM_CALL_TRACE_SCHEMA_VERSION = "req-031.llm-call-trace-row.v1"
REQ_031_ANALYSIS_TYPE = "call_6_kpi_impact_estimation_reasoning"
REQ_031_PROCESSING_STRATEGY = "call-6-kpi-impact-estimation"
REQ_031_REASONING_MODE = "deterministic-evidence-bounded-estimation"
REQ_031_CALL_ID = "call-6"
REQ_031_REQUIRED_CALL_IDS = ("call-1", "call-2", "call-3", "call-4", "call-5", "call-6")
REQ_031_ALLOWED_ADOPTION_STATUSES = {"planned", "conditional", "pilot"}
REQ_031_ALLOWED_DIRECTIONS = {"increase", "decrease"}
REQ_031_ALLOWED_CONFIDENCE_VALUES = {"high", "medium", "low"}
REQ_031_REQUIRED_ESTIMATE_FIELDS = [
    "estimate_id",
    "recommendation_id",
    "recommendation_summary",
    "kpi_id",
    "kpi_name",
    "baseline_value",
    "unit",
    "desired_direction",
    "adoption_status",
    "adoption_window",
    "expected_movement",
    "estimated_post_adoption_range",
    "reasoning_summary",
    "confidence",
    "caveats",
    "evidence_backed_assumptions",
    "evidence_refs",
]
REQ_031_CALL_OBJECTIVES = {
    "call-1": "Anchor the target project state and known evidence limits.",
    "call-2": "Refine implementation constraints that shape later adoption options.",
    "call-3": "Align execution dependencies and evidence refresh obligations.",
    "call-4": "Synthesize deterministic recommendation drafts for bounded adoption choices.",
    "call-5": "Select which recommendation adoptions are in scope for KPI estimation.",
    "call-6": "Estimate KPI movement from recommendation adoption using evidence-backed assumptions with explicit confidence and caveats.",
}
RUNTIME_MODE = "llm-first"
EXECUTION_MODE = "long-thinking"
PIPELINE_STRATEGY = "multi-call-strategy-pipeline-planner"
MIN_CALL_DEPTH = 1
MAX_CALL_DEPTH = 8
DEFAULT_CALL_DEPTH = 4
LLM_CALL_TRACE_RELATIVE_PATH = "strategy/current/llm_call_trace.jsonl"
REQ_026_ALLOWED_PLANNING_STATUSES = {"ready", "partial", "blocked"}
REQ_026_ALLOWED_RUNTIME_STATUSES = {"healthy", "degraded", "blocked"}
REQ_026_ALLOWED_RECOMMENDATION_SCOPES = {"local", "cross-project"}
REQ_026_ALLOWED_CLAIM_PHASES = {"analysis", "synthesis"}

DEFAULT_STAGE_BLUEPRINTS = (
    {
        "purpose": "Frame REQ-025 strategy objective and evidence boundaries.",
        "expected_output": "strategy_scope_frame",
    },
    {
        "purpose": "Expand multi-call options for heavy-thinking execution.",
        "expected_output": "candidate_reasoning_paths",
    },
    {
        "purpose": "Resolve call dependencies and strict evidence coverage.",
        "expected_output": "dependency_checked_pipeline",
    },
    {
        "purpose": "Finalize executable pipeline with explicit per-call outputs.",
        "expected_output": "final_pipeline_plan",
    },
)

LOG_ROOT = Path("/Users/slobodan/projects/LOGS")
LOG_PATH = LOG_ROOT / "strategy_llm_pipeline.log"
LOG_BUDGET_CHECK_STAMP = LOG_ROOT / ".log_budget_check.strategy_llm_pipeline"
LOG_BUDGET_CHECK_INTERVAL_SECONDS = 15 * 60
LOG_BUDGET_MAX_BYTES = 3 * 1024 * 1024 * 1024


class Req026Error(ValueError):
    """Raised when REQ-026 input is malformed."""


class Req029Error(ValueError):
    """Raised when REQ-029 input is malformed."""


class Req031Error(ValueError):
    """Raised when REQ-031 input is malformed."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


def _require_text(value: Any, *, field_name: str) -> str:
    text = _as_text(value)
    if not text:
        raise ValueError(f"{field_name} must be a non-empty string")
    return text


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _require_number(value: Any, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number")
    return float(value)


def _normalize_root(value: Any, *, field_name: str) -> str:
    normalized = str(Path(_require_text(value, field_name=field_name)).expanduser().resolve())
    if not normalized.startswith("/"):
        raise ValueError(f"{field_name} must normalize to an absolute path")
    return normalized


def _normalize_call_depth(raw_value: Any) -> int:
    if isinstance(raw_value, bool):
        raise ValueError("call_depth must be an integer")
    if not isinstance(raw_value, int):
        raise ValueError("call_depth must be an integer")
    if raw_value < MIN_CALL_DEPTH or raw_value > MAX_CALL_DEPTH:
        raise ValueError(f"call_depth must be between {MIN_CALL_DEPTH} and {MAX_CALL_DEPTH}")
    return raw_value


def _normalize_string_list(raw_value: Any, *, field_name: str, min_items: int = 0) -> list[str]:
    if raw_value is None:
        raw_seq: Sequence[Any] = []
    else:
        if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
            raise ValueError(f"{field_name} must be an array of non-empty strings")
        raw_seq = raw_value

    normalized: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_seq):
        text = _require_text(item, field_name=f"{field_name}[{index}]")
        if text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    if len(normalized) < min_items:
        raise ValueError(f"{field_name} must contain at least {min_items} item(s)")
    return sorted(normalized)


def _collect_unique_refs(*ref_groups: Sequence[Any]) -> list[str]:
    seen: set[str] = set()
    for refs in ref_groups:
        for raw_ref in refs:
            ref = _as_text(raw_ref)
            if ref:
                seen.add(ref)
    return sorted(seen)


def _is_earth_evidence_ref(ref: str) -> bool:
    return _as_text(ref).startswith("reports/earth/")


def _normalize_action_scope(raw_value: Any, *, field_name: str) -> str:
    if raw_value is None:
        return "local"
    scope = _as_text(raw_value).lower()
    if scope not in {"local", "cross-project"}:
        raise ValueError(f"{field_name} must be either 'local' or 'cross-project'")
    return scope


def _normalize_cross_project_context(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError("cross_project_context must be an array when provided")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"cross_project_context[{index}] must be an object")
        project_id = _require_text(item.get("project_id"), field_name=f"cross_project_context[{index}].project_id")
        project_root = _normalize_root(item.get("project_root"), field_name=f"cross_project_context[{index}].project_root")
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            field_name=f"cross_project_context[{index}].evidence_refs",
        )
        context_note = _require_text(
            item.get("context_note") if item.get("context_note") is not None else "No context note supplied.",
            field_name=f"cross_project_context[{index}].context_note",
        )
        normalized.append(
            {
                "project_id": project_id,
                "project_root": project_root,
                "evidence_refs": evidence_refs,
                "context_note": context_note,
            }
        )
    normalized.sort(key=lambda row: (row["project_id"], row["project_root"], row["context_note"]))
    return normalized


def _normalize_candidate_recommendations(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError("candidate_recommendations must be an array when provided")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"candidate_recommendations[{index}] must be an object")
        action_id = (
            _require_text(item.get("action_id"), field_name=f"candidate_recommendations[{index}].action_id")
            if item.get("action_id") is not None
            else f"action-{index + 1:02d}"
        )
        summary = _require_text(item.get("summary"), field_name=f"candidate_recommendations[{index}].summary")
        rationale = _require_text(
            item.get("rationale") if item.get("rationale") is not None else "No rationale supplied.",
            field_name=f"candidate_recommendations[{index}].rationale",
        )
        action_scope = _normalize_action_scope(
            item.get("action_scope"),
            field_name=f"candidate_recommendations[{index}].action_scope",
        )
        requires_earth_evidence = bool(item.get("requires_earth_evidence", action_scope == "cross-project"))
        project_id = _as_text(item.get("project_id"))
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            field_name=f"candidate_recommendations[{index}].evidence_refs",
            min_items=1,
        )
        next_step = _require_text(
            item.get("next_step")
            if item.get("next_step") is not None
            else f"Validate '{action_id}' under deterministic long-thinking execution.",
            field_name=f"candidate_recommendations[{index}].next_step",
        )
        normalized.append(
            {
                "action_id": action_id,
                "summary": summary,
                "rationale": rationale,
                "action_scope": action_scope,
                "requires_earth_evidence": requires_earth_evidence,
                "project_id": project_id,
                "evidence_refs": evidence_refs,
                "next_step": next_step,
            }
        )
    normalized.sort(key=lambda row: row["action_id"])
    return normalized


def _normalize_strategic_claims(raw_value: Any, *, call_depth: int) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError("strategic_claims must be an array when provided")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"strategic_claims[{index}] must be an object")
        claim_id = _require_text(item.get("claim_id"), field_name=f"strategic_claims[{index}].claim_id")
        phase = _require_text(item.get("phase"), field_name=f"strategic_claims[{index}].phase").lower()
        summary = _require_text(item.get("summary"), field_name=f"strategic_claims[{index}].summary")
        position = _require_text(item.get("position"), field_name=f"strategic_claims[{index}].position")
        source_call_sequence = item.get("source_call_sequence")
        if isinstance(source_call_sequence, bool) or not isinstance(source_call_sequence, int):
            raise ValueError(f"strategic_claims[{index}].source_call_sequence must be an integer")
        if source_call_sequence < 1 or source_call_sequence > call_depth:
            raise ValueError(f"strategic_claims[{index}].source_call_sequence must be between 1 and {call_depth}")
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            field_name=f"strategic_claims[{index}].evidence_refs",
        )
        normalized.append(
            {
                "claim_id": claim_id,
                "phase": phase,
                "summary": summary,
                "position": position,
                "source_call_sequence": source_call_sequence,
                "evidence_refs": evidence_refs,
            }
        )
    normalized.sort(
        key=lambda row: (
            row["claim_id"],
            row["phase"],
            row["source_call_sequence"],
            row["position"],
            row["summary"],
        )
    )
    return normalized


def _default_stage_blueprint(index: int) -> dict[str, str]:
    if index < len(DEFAULT_STAGE_BLUEPRINTS):
        row = DEFAULT_STAGE_BLUEPRINTS[index]
        return {"purpose": row["purpose"], "expected_output": row["expected_output"]}
    stage_num = index + 1
    return {
        "purpose": f"Execute reasoning pass {stage_num} with strict evidence traceability.",
        "expected_output": f"intermediate_output_{stage_num:02d}",
    }


def _normalize_stage_blueprints(raw_value: Any, *, call_depth: int) -> list[dict[str, str]]:
    if raw_value is None:
        return [_default_stage_blueprint(index) for index in range(call_depth)]
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError("stage_blueprints must be an array when provided")
    if len(raw_value) < call_depth:
        raise ValueError("stage_blueprints must include at least call_depth entries")

    normalized: list[dict[str, str]] = []
    for index in range(call_depth):
        row = raw_value[index]
        if not isinstance(row, Mapping):
            raise ValueError(f"stage_blueprints[{index}] must be an object")
        normalized.append(
            {
                "purpose": _require_text(row.get("purpose"), field_name=f"stage_blueprints[{index}].purpose"),
                "expected_output": _require_text(
                    row.get("expected_output"),
                    field_name=f"stage_blueprints[{index}].expected_output",
                ),
            }
        )
    return normalized


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _canonical_digest(payload: Any) -> str:
    raw = _canonical_json(payload)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _matches_slug_schema(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value))


def _build_call_id(
    *,
    revision_identity: str,
    strategy_goal: str,
    sequence: int,
    purpose: str,
    expected_output: str,
) -> str:
    material = "|".join(
        [
            revision_identity,
            strategy_goal,
            str(sequence),
            purpose,
            expected_output,
        ]
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:10]
    return f"req025-call-{sequence:02d}-{digest}"


def _canonical_call_input(
    *,
    target_project_root: str,
    earth_root: str,
    output_root: str,
    revision_identity: str,
    strategy_goal: str,
    call_depth: int,
) -> dict[str, Any]:
    return {
        "runtime_mode": RUNTIME_MODE,
        "execution_mode": EXECUTION_MODE,
        "target_project_root": target_project_root,
        "earth_root": earth_root,
        "output_root": output_root,
        "revision_identity": revision_identity,
        "strategy_goal": strategy_goal,
        "call_depth": call_depth,
    }


def _recommendation_decision(*, recommended_actions: list[dict[str, Any]], open_risks: list[dict[str, Any]]) -> str:
    if recommended_actions and not open_risks:
        return "proceed"
    if recommended_actions and open_risks:
        return "proceed-with-open-risks"
    if open_risks:
        if all(row.get("reason_code") == "missing_earth_sweep_evidence_refs" for row in open_risks):
            return "collect-earth-evidence"
        return "resolve-strategy-gaps"
    return "insufficient-context"


def _recommendation_rationale(*, decision: str) -> str:
    if decision == "proceed":
        return "Broad-sweep context evidence is sufficient for immediate multi-call execution."
    if decision == "proceed-with-open-risks":
        return "Some recommendation paths are evidence-backed while unresolved ideas remain open risks."
    if decision == "collect-earth-evidence":
        return "Cross-project ideas require Earth-sweep evidence before obligations can be committed."
    if decision == "resolve-strategy-gaps":
        return "Contradictory or uncited strategy claims must be resolved before planner outputs can be promoted."
    return "No evidence-backed recommendation actions were supplied for this strategy run."


def _recommendation_confidence(*, evidence_refs: list[str], open_risks: list[dict[str, Any]]) -> str:
    if not evidence_refs:
        return "low"
    if open_risks:
        return "medium"
    return "high"


def _canonical_processing_input(
    *,
    evidence_refs: list[str],
    stage_blueprints: list[dict[str, str]],
    call_depth: int,
    target_project_evidence_refs: list[str],
    earth_sweep_evidence_refs: list[str],
    cross_project_context: list[dict[str, Any]],
    candidate_recommendations: list[dict[str, Any]],
    strategic_claims: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "call_depth": call_depth,
        "required_evidence_refs": list(evidence_refs),
        "target_project_evidence_refs": list(target_project_evidence_refs),
        "earth_sweep_evidence_refs": list(earth_sweep_evidence_refs),
        "cross_project_context": [
            {
                "project_id": row["project_id"],
                "project_root": row["project_root"],
                "evidence_refs": list(row["evidence_refs"]),
                "context_note": row["context_note"],
            }
            for row in cross_project_context
        ],
        "candidate_recommendations": [
            {
                "action_id": row["action_id"],
                "summary": row["summary"],
                "rationale": row["rationale"],
                "action_scope": row["action_scope"],
                "requires_earth_evidence": row["requires_earth_evidence"],
                "project_id": row["project_id"],
                "evidence_refs": list(row["evidence_refs"]),
                "next_step": row["next_step"],
            }
            for row in candidate_recommendations
        ],
        "strategic_claims": [
            {
                "claim_id": row["claim_id"],
                "phase": row["phase"],
                "summary": row["summary"],
                "position": row["position"],
                "source_call_sequence": row["source_call_sequence"],
                "evidence_refs": list(row["evidence_refs"]),
            }
            for row in strategic_claims
        ],
        "stage_blueprints": [{"purpose": row["purpose"], "expected_output": row["expected_output"]} for row in stage_blueprints],
    }


def _build_call_output_ref(*, plan_id: str, call_id: str, expected_output: str) -> str:
    return f"{plan_id}::call::{call_id}::output::{expected_output}"


def _build_trace_handoff_summary(
    *,
    sequence: int,
    expected_output: str,
    output_ref: str,
    input_ref_count: int,
    next_call_id: str,
    recommendation_decision: str,
) -> str:
    if next_call_id:
        return (
            f"Call {sequence} hands off {expected_output} via {output_ref} to {next_call_id} "
            f"after consuming {input_ref_count} input refs."
        )
    return (
        f"Call {sequence} hands off {expected_output} via {output_ref} as the terminal planner output "
        f"with recommendation decision {recommendation_decision}."
    )


def _build_llm_call_trace_rows(
    *,
    plan_id: str,
    processing_call_id: str,
    required_evidence_refs: Sequence[str],
    calls: Sequence[Mapping[str, Any]],
    recommendation_decision: str,
) -> list[dict[str, Any]]:
    output_ref_by_call_id: dict[str, str] = {}
    for call in calls:
        call_id = _require_text(call.get("call_id"), field_name="pipeline_plan.calls[].call_id")
        expected_output = _require_text(call.get("expected_output"), field_name="pipeline_plan.calls[].expected_output")
        output_ref_by_call_id[call_id] = _build_call_output_ref(
            plan_id=plan_id,
            call_id=call_id,
            expected_output=expected_output,
        )

    trace_rows: list[dict[str, Any]] = []
    for index, call in enumerate(calls):
        call_id = _require_text(call.get("call_id"), field_name=f"pipeline_plan.calls[{index}].call_id")
        sequence = call.get("sequence")
        if not isinstance(sequence, int):
            raise ValueError(f"pipeline_plan.calls[{index}].sequence must be an integer")
        call_objective = _require_text(call.get("purpose"), field_name=f"pipeline_plan.calls[{index}].purpose")
        expected_output = _require_text(
            call.get("expected_output"),
            field_name=f"pipeline_plan.calls[{index}].expected_output",
        )
        depends_on = [
            _require_text(dep_call_id, field_name=f"pipeline_plan.calls[{index}].depends_on[{dep_index}]")
            for dep_index, dep_call_id in enumerate(call.get("depends_on", []))
        ]
        dependency_output_refs = [output_ref_by_call_id[dep_call_id] for dep_call_id in depends_on]
        input_refs = list(required_evidence_refs) + dependency_output_refs
        output_ref = output_ref_by_call_id[call_id]
        next_call_id = ""
        if index + 1 < len(calls):
            next_call_id = _as_text(calls[index + 1].get("call_id"))
        trace_rows.append(
            {
                "schema_version": REQ_025_LLM_CALL_TRACE_SCHEMA_VERSION,
                "requirement_id": REQ_025_REQUIREMENT_ID,
                "plan_id": plan_id,
                "processing_call_id": processing_call_id,
                "call_id": call_id,
                "sequence": sequence,
                "call_objective": call_objective,
                "depends_on": depends_on,
                "expected_output": expected_output,
                "input_refs": input_refs,
                "output_refs": [output_ref],
                "handoff_summary": _build_trace_handoff_summary(
                    sequence=sequence,
                    expected_output=expected_output,
                    output_ref=output_ref,
                    input_ref_count=len(input_refs),
                    next_call_id=next_call_id,
                    recommendation_decision=recommendation_decision,
                ),
            }
        )
    return trace_rows


def _build_req_025_processing_behavior(
    *,
    target_project_root: str,
    earth_root: str,
    call_depth: int,
    pipeline_plan: Mapping[str, Any],
    target_project_evidence_refs: list[str],
    earth_sweep_evidence_refs: list[str],
    cross_project_context: list[dict[str, Any]],
    candidate_recommendations: list[dict[str, Any]],
    strategic_claims: list[dict[str, Any]],
) -> dict[str, Any]:
    cross_project_refs = _collect_unique_refs(*[row["evidence_refs"] for row in cross_project_context])
    recommended_actions: list[dict[str, Any]] = []
    cross_project_obligations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    plan_id = _require_text(pipeline_plan.get("plan_id"), field_name="pipeline_plan.plan_id")
    available_citation_refs = set(
        _collect_unique_refs(
            target_project_evidence_refs,
            earth_sweep_evidence_refs,
            cross_project_refs,
            list(pipeline_plan.get("required_evidence_refs", [])),
        )
    )
    output_ref_by_sequence: dict[int, str] = {}
    for call in pipeline_plan.get("calls", []):
        if not isinstance(call, Mapping):
            continue
        sequence = call.get("sequence")
        if not isinstance(sequence, int):
            continue
        output_ref_by_sequence[sequence] = _build_call_output_ref(
            plan_id=plan_id,
            call_id=_require_text(call.get("call_id"), field_name=f"pipeline_plan.calls[{sequence}].call_id"),
            expected_output=_require_text(
                call.get("expected_output"),
                field_name=f"pipeline_plan.calls[{sequence}].expected_output",
            ),
        )

    claim_rows_by_id: dict[str, list[dict[str, Any]]] = {}
    for claim in strategic_claims:
        claim_rows_by_id.setdefault(claim["claim_id"], []).append(claim)
        citation_refs = list(claim["evidence_refs"])
        source_output_ref = output_ref_by_sequence.get(claim["source_call_sequence"], "")
        if not citation_refs or not set(citation_refs).issubset(available_citation_refs):
            open_risks.append(
                {
                    "risk_id": f"risk-claim-{claim['claim_id']}-citation",
                    "summary": claim["summary"],
                    "reason_code": "uncited_strategic_claim",
                    "required_evidence_refs": _collect_unique_refs([source_output_ref], citation_refs),
                }
            )

    for claim_id, claim_rows in claim_rows_by_id.items():
        analysis_rows = [row for row in claim_rows if row["phase"] == "analysis"]
        synthesis_rows = [row for row in claim_rows if row["phase"] == "synthesis"]
        contradiction_row: dict[str, Any] | None = None
        for analysis_row in analysis_rows:
            for synthesis_row in synthesis_rows:
                if analysis_row["position"] == synthesis_row["position"]:
                    continue
                contradiction_row = {
                    "summary": synthesis_row["summary"],
                    "required_evidence_refs": _collect_unique_refs(
                        [output_ref_by_sequence.get(analysis_row["source_call_sequence"], "")],
                        [output_ref_by_sequence.get(synthesis_row["source_call_sequence"], "")],
                        analysis_row["evidence_refs"],
                        synthesis_row["evidence_refs"],
                    ),
                }
                break
            if contradiction_row is not None:
                break
        if contradiction_row is not None:
            open_risks.append(
                {
                    "risk_id": f"risk-claim-{claim_id}-contradiction",
                    "summary": contradiction_row["summary"],
                    "reason_code": "cross_call_contradiction",
                    "required_evidence_refs": contradiction_row["required_evidence_refs"],
                }
            )

    for candidate in candidate_recommendations:
        action = {
            "action_id": candidate["action_id"],
            "summary": candidate["summary"],
            "rationale": candidate["rationale"],
            "action_scope": candidate["action_scope"],
            "next_step": candidate["next_step"],
            "evidence_refs": list(candidate["evidence_refs"]),
        }
        candidate_earth_refs = _collect_unique_refs(
            [ref for ref in candidate["evidence_refs"] if _is_earth_evidence_ref(ref)],
            earth_sweep_evidence_refs,
        )
        uncited_candidate_refs = sorted(set(candidate["evidence_refs"]) - available_citation_refs)
        if uncited_candidate_refs:
            open_risks.append(
                {
                    "risk_id": f"risk-{candidate['action_id']}-citation",
                    "summary": candidate["summary"],
                    "reason_code": "uncited_strategic_claim",
                    "required_evidence_refs": list(uncited_candidate_refs),
                }
            )
            continue
        if candidate["requires_earth_evidence"]:
            if candidate_earth_refs:
                obligation_project_id = candidate["project_id"] or (
                    cross_project_context[0]["project_id"] if cross_project_context else "earth"
                )
                cross_project_obligations.append(
                    {
                        "obligation_id": f"obligation-{candidate['action_id']}",
                        "project_id": obligation_project_id,
                        "summary": candidate["summary"],
                        "evidence_refs": _collect_unique_refs(candidate["evidence_refs"], candidate_earth_refs),
                    }
                )
                recommended_actions.append(action)
            else:
                open_risks.append(
                    {
                        "risk_id": f"risk-{candidate['action_id']}",
                        "summary": candidate["summary"],
                        "reason_code": "missing_earth_sweep_evidence_refs",
                        "required_evidence_refs": list(candidate["evidence_refs"]),
                    }
                )
            continue
        recommended_actions.append(action)

    recommended_actions.sort(key=lambda row: row["action_id"])
    cross_project_obligations.sort(key=lambda row: row["obligation_id"])
    open_risks.sort(key=lambda row: row["risk_id"])

    recommendation_refs = _collect_unique_refs(
        target_project_evidence_refs,
        earth_sweep_evidence_refs,
        cross_project_refs,
        list(pipeline_plan.get("required_evidence_refs", [])),
        *[row["evidence_refs"] for row in recommended_actions],
        *[row["evidence_refs"] for row in cross_project_obligations],
        *[row["required_evidence_refs"] for row in open_risks],
    )
    decision = _recommendation_decision(recommended_actions=recommended_actions, open_risks=open_risks)

    return {
        "strategy": PIPELINE_STRATEGY,
        "reasoning_mode": EXECUTION_MODE,
        "strict_evidence_discipline": True,
        "heuristic_summarization_only": False,
        "context_inputs": {
            "target_project": {
                "project_root": target_project_root,
                "evidence_refs": list(target_project_evidence_refs),
            },
            "earth_sweep": {
                "earth_root": earth_root,
                "evidence_refs": list(earth_sweep_evidence_refs),
            },
            "cross_project_context": list(cross_project_context),
            "candidate_recommendations": list(candidate_recommendations),
            "strategic_claims": list(strategic_claims),
        },
        "context_usage": {
            "target_project_context_used": bool(target_project_evidence_refs),
            "earth_sweep_context_used": bool(earth_sweep_evidence_refs),
            "cross_project_context_used": bool(cross_project_context),
            "target_project_refs_used": list(target_project_evidence_refs),
            "earth_sweep_refs_used": list(earth_sweep_evidence_refs),
            "cross_project_refs_used": cross_project_refs,
            "cross_project_projects_considered": sorted({row["project_id"] for row in cross_project_context}),
            "evidence_refs_used": recommendation_refs,
        },
        "pipeline_plan": dict(pipeline_plan),
        "recommendation": {
            "decision": decision,
            "rationale": _recommendation_rationale(decision=decision),
            "confidence": _recommendation_confidence(evidence_refs=recommendation_refs, open_risks=open_risks),
            "evidence_refs": recommendation_refs,
            "recommended_actions": recommended_actions,
            "cross_project_obligations": cross_project_obligations,
            "open_risks": open_risks,
        },
        "summary": (
            f"Planned {call_depth} deterministic calls with broad-sweep context inputs, explicit dependencies, "
            "required evidence refs, and recommendation outputs."
        ),
    }


def build_req_025_multi_call_strategy_pipeline_planner(
    *,
    target_project_root: str,
    earth_root: str,
    output_root: str,
    revision_identity: str,
    strategy_goal: str,
    call_depth: int = DEFAULT_CALL_DEPTH,
    evidence_refs: Sequence[Any] | None = None,
    stage_blueprints: Sequence[Mapping[str, Any]] | None = None,
    target_project_evidence_refs: Sequence[Any] | None = None,
    earth_sweep_evidence_refs: Sequence[Any] | None = None,
    cross_project_context: Sequence[Mapping[str, Any]] | None = None,
    candidate_recommendations: Sequence[Mapping[str, Any]] | None = None,
    strategic_claims: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the REQ-025 multi-call strategy pipeline planner payload."""
    normalized_target_root = _normalize_root(target_project_root, field_name="target_project_root")
    normalized_earth_root = _normalize_root(earth_root, field_name="earth_root")
    normalized_output_root = _normalize_root(output_root, field_name="output_root")
    normalized_revision_identity = _require_text(revision_identity, field_name="revision_identity")
    normalized_strategy_goal = _require_text(strategy_goal, field_name="strategy_goal")
    normalized_call_depth = _normalize_call_depth(call_depth)
    normalized_evidence_refs = _normalize_string_list(evidence_refs, field_name="evidence_refs", min_items=1)
    normalized_stage_blueprints = _normalize_stage_blueprints(stage_blueprints, call_depth=normalized_call_depth)
    default_target_refs = [ref for ref in normalized_evidence_refs if not _is_earth_evidence_ref(ref)]
    default_earth_refs = [ref for ref in normalized_evidence_refs if _is_earth_evidence_ref(ref)]
    normalized_target_project_evidence_refs = (
        _normalize_string_list(target_project_evidence_refs, field_name="target_project_evidence_refs")
        if target_project_evidence_refs is not None
        else default_target_refs
    )
    normalized_earth_sweep_evidence_refs = (
        _normalize_string_list(earth_sweep_evidence_refs, field_name="earth_sweep_evidence_refs")
        if earth_sweep_evidence_refs is not None
        else default_earth_refs
    )
    normalized_cross_project_context = _normalize_cross_project_context(cross_project_context)
    normalized_candidate_recommendations = _normalize_candidate_recommendations(candidate_recommendations)
    normalized_strategic_claims = _normalize_strategic_claims(strategic_claims, call_depth=normalized_call_depth)

    calls: list[dict[str, Any]] = []
    for index, stage in enumerate(normalized_stage_blueprints):
        sequence = index + 1
        call_id = _build_call_id(
            revision_identity=normalized_revision_identity,
            strategy_goal=normalized_strategy_goal,
            sequence=sequence,
            purpose=stage["purpose"],
            expected_output=stage["expected_output"],
        )
        depends_on: list[str] = []
        if calls:
            depends_on = [calls[-1]["call_id"]]
        calls.append(
            {
                "call_id": call_id,
                "sequence": sequence,
                "purpose": stage["purpose"],
                "depends_on": depends_on,
                "expected_output": stage["expected_output"],
                "evidence_refs": list(normalized_evidence_refs),
            }
        )

    dependency_edges: list[dict[str, str]] = []
    for call in calls:
        for upstream_id in call["depends_on"]:
            dependency_edges.append({"from_call_id": upstream_id, "to_call_id": call["call_id"]})

    canonical_input = _canonical_call_input(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        output_root=normalized_output_root,
        revision_identity=normalized_revision_identity,
        strategy_goal=normalized_strategy_goal,
        call_depth=normalized_call_depth,
    )
    canonical_input_sha = _canonical_digest(canonical_input)

    canonical_processing_input = _canonical_processing_input(
        evidence_refs=normalized_evidence_refs,
        stage_blueprints=normalized_stage_blueprints,
        call_depth=normalized_call_depth,
        target_project_evidence_refs=normalized_target_project_evidence_refs,
        earth_sweep_evidence_refs=normalized_earth_sweep_evidence_refs,
        cross_project_context=normalized_cross_project_context,
        candidate_recommendations=normalized_candidate_recommendations,
        strategic_claims=normalized_strategic_claims,
    )
    processing_sha = _canonical_digest(canonical_processing_input)

    pipeline_plan = {
        "plan_id": f"req025-plan-{processing_sha[:16]}",
        "planner_mode": "multi-call-reasoning-chain",
        "total_calls": normalized_call_depth,
        "required_evidence_refs": list(normalized_evidence_refs),
        "calls": calls,
        "dependency_edges": dependency_edges,
        "terminal_expected_output": calls[-1]["expected_output"],
    }
    processing_behavior = _build_req_025_processing_behavior(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        call_depth=normalized_call_depth,
        pipeline_plan=pipeline_plan,
        target_project_evidence_refs=normalized_target_project_evidence_refs,
        earth_sweep_evidence_refs=normalized_earth_sweep_evidence_refs,
        cross_project_context=normalized_cross_project_context,
        candidate_recommendations=normalized_candidate_recommendations,
        strategic_claims=normalized_strategic_claims,
    )
    processing_call_id = f"req025-processing-{processing_sha[:16]}"
    llm_call_trace_rows = _build_llm_call_trace_rows(
        plan_id=pipeline_plan["plan_id"],
        processing_call_id=processing_call_id,
        required_evidence_refs=pipeline_plan["required_evidence_refs"],
        calls=pipeline_plan["calls"],
        recommendation_decision=_as_text(processing_behavior["recommendation"]["decision"]),
    )
    llm_call_trace_sha = _canonical_digest(llm_call_trace_rows)

    return {
        "schema_version": REQ_025_SCHEMA_VERSION,
        "requirement_id": REQ_025_REQUIREMENT_ID,
        "multi_call_strategy_pipeline_planner_entrypoint": {
            "runtime_mode": RUNTIME_MODE,
            "execution_mode": EXECUTION_MODE,
            "target_project_root": normalized_target_root,
            "earth_root": normalized_earth_root,
            "output_root": normalized_output_root,
            "revision_identity": normalized_revision_identity,
            "strategy_goal": normalized_strategy_goal,
            "call_depth": normalized_call_depth,
        },
        "processing_behavior": processing_behavior,
        "call_metadata": {
            "reproducibility": "deterministic-input-fingerprint",
            "canonical_input_sha256": canonical_input_sha,
            "reproducible_call_id": f"req025-{canonical_input_sha[:16]}",
            "canonical_input": canonical_input,
            "processing_input_sha256": processing_sha,
            "processing_call_id": processing_call_id,
            "canonical_processing_input": canonical_processing_input,
            "llm_call_trace_schema_version": REQ_025_LLM_CALL_TRACE_SCHEMA_VERSION,
            "llm_call_trace_path": LLM_CALL_TRACE_RELATIVE_PATH,
            "llm_call_trace_sha256": llm_call_trace_sha,
            "llm_call_trace_rows": llm_call_trace_rows,
        },
    }


def validate_req_025_multi_call_strategy_pipeline_planner(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-025 payload shape and deterministic metadata."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    required_top = {
        "schema_version",
        "requirement_id",
        "multi_call_strategy_pipeline_planner_entrypoint",
        "processing_behavior",
        "call_metadata",
    }
    top_keys = set(payload.keys())
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - required_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("schema_version") != REQ_025_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_025_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_025_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_025_REQUIREMENT_ID}")

    entrypoint = payload.get("multi_call_strategy_pipeline_planner_entrypoint")
    if not isinstance(entrypoint, Mapping):
        errors.append("multi_call_strategy_pipeline_planner_entrypoint must be an object")
        return errors
    required_entrypoint = {
        "runtime_mode",
        "execution_mode",
        "target_project_root",
        "earth_root",
        "output_root",
        "revision_identity",
        "strategy_goal",
        "call_depth",
    }
    entrypoint_keys = set(entrypoint.keys())
    missing_entrypoint = sorted(required_entrypoint - entrypoint_keys)
    if missing_entrypoint:
        errors.append(f"multi_call_strategy_pipeline_planner_entrypoint missing keys: {missing_entrypoint}")
    unexpected_entrypoint = sorted(entrypoint_keys - required_entrypoint)
    if unexpected_entrypoint:
        errors.append(f"multi_call_strategy_pipeline_planner_entrypoint unexpected keys: {unexpected_entrypoint}")

    if entrypoint.get("runtime_mode") != RUNTIME_MODE:
        errors.append(f"multi_call_strategy_pipeline_planner_entrypoint.runtime_mode must be {RUNTIME_MODE}")
    if entrypoint.get("execution_mode") != EXECUTION_MODE:
        errors.append(f"multi_call_strategy_pipeline_planner_entrypoint.execution_mode must be {EXECUTION_MODE}")
    for root_field in ("target_project_root", "earth_root", "output_root"):
        root_value = entrypoint.get(root_field)
        if not isinstance(root_value, str) or not root_value.strip():
            errors.append(f"{root_field} must be a non-empty string")
        elif not root_value.startswith("/"):
            errors.append(f"{root_field} must be an absolute path")

    revision_identity = entrypoint.get("revision_identity")
    strategy_goal = entrypoint.get("strategy_goal")
    if not isinstance(revision_identity, str) or not revision_identity.strip():
        errors.append("revision_identity must be a non-empty string")
    if not isinstance(strategy_goal, str) or not strategy_goal.strip():
        errors.append("strategy_goal must be a non-empty string")

    call_depth = entrypoint.get("call_depth")
    if not isinstance(call_depth, int):
        errors.append("call_depth must be an integer")
        call_depth = DEFAULT_CALL_DEPTH
    elif call_depth < MIN_CALL_DEPTH or call_depth > MAX_CALL_DEPTH:
        errors.append(f"call_depth must be between {MIN_CALL_DEPTH} and {MAX_CALL_DEPTH}")

    processing_behavior = payload.get("processing_behavior")
    if not isinstance(processing_behavior, Mapping):
        errors.append("processing_behavior must be an object")
        return errors

    required_processing = {
        "strategy",
        "reasoning_mode",
        "strict_evidence_discipline",
        "heuristic_summarization_only",
        "context_inputs",
        "context_usage",
        "pipeline_plan",
        "recommendation",
        "summary",
    }
    processing_keys = set(processing_behavior.keys())
    missing_processing = sorted(required_processing - processing_keys)
    if missing_processing:
        errors.append(f"processing_behavior missing keys: {missing_processing}")
    unexpected_processing = sorted(processing_keys - required_processing)
    if unexpected_processing:
        errors.append(f"processing_behavior unexpected keys: {unexpected_processing}")

    if processing_behavior.get("strategy") != PIPELINE_STRATEGY:
        errors.append(f"processing_behavior.strategy must be {PIPELINE_STRATEGY}")
    if processing_behavior.get("reasoning_mode") != EXECUTION_MODE:
        errors.append(f"processing_behavior.reasoning_mode must be {EXECUTION_MODE}")
    if processing_behavior.get("strict_evidence_discipline") is not True:
        errors.append("processing_behavior.strict_evidence_discipline must be true")
    if processing_behavior.get("heuristic_summarization_only") is not False:
        errors.append("processing_behavior.heuristic_summarization_only must be false")

    context_inputs = processing_behavior.get("context_inputs")
    target_project_refs_from_context: list[str] = []
    earth_sweep_refs_from_context: list[str] = []
    normalized_cross_project_context_for_digest: list[dict[str, Any]] = []
    normalized_candidate_recommendations_for_digest: list[dict[str, Any]] = []
    normalized_strategic_claims_for_digest: list[dict[str, Any]] = []
    if not isinstance(context_inputs, Mapping):
        errors.append("processing_behavior.context_inputs must be an object")
    else:
        target_project_context = context_inputs.get("target_project")
        if not isinstance(target_project_context, Mapping):
            errors.append("processing_behavior.context_inputs.target_project must be an object")
        else:
            if target_project_context.get("project_root") != entrypoint.get("target_project_root"):
                errors.append(
                    "processing_behavior.context_inputs.target_project.project_root must match entrypoint.target_project_root"
                )
            target_refs = target_project_context.get("evidence_refs")
            if not isinstance(target_refs, list):
                errors.append("processing_behavior.context_inputs.target_project.evidence_refs must be a list")
            else:
                target_project_refs_from_context = sorted({_as_text(ref) for ref in target_refs if _as_text(ref)})

        earth_sweep_context = context_inputs.get("earth_sweep")
        if not isinstance(earth_sweep_context, Mapping):
            errors.append("processing_behavior.context_inputs.earth_sweep must be an object")
        else:
            if earth_sweep_context.get("earth_root") != entrypoint.get("earth_root"):
                errors.append("processing_behavior.context_inputs.earth_sweep.earth_root must match entrypoint.earth_root")
            earth_refs = earth_sweep_context.get("evidence_refs")
            if not isinstance(earth_refs, list):
                errors.append("processing_behavior.context_inputs.earth_sweep.evidence_refs must be a list")
            else:
                earth_sweep_refs_from_context = sorted({_as_text(ref) for ref in earth_refs if _as_text(ref)})

        cross_project_context = context_inputs.get("cross_project_context")
        if not isinstance(cross_project_context, list):
            errors.append("processing_behavior.context_inputs.cross_project_context must be a list")
        else:
            for index, row in enumerate(cross_project_context):
                if not isinstance(row, Mapping):
                    errors.append(f"processing_behavior.context_inputs.cross_project_context[{index}] must be an object")
                    continue
                project_id = _as_text(row.get("project_id"))
                project_root = _as_text(row.get("project_root"))
                context_note = _as_text(row.get("context_note"))
                evidence_refs = row.get("evidence_refs")
                if not project_id:
                    errors.append(
                        f"processing_behavior.context_inputs.cross_project_context[{index}].project_id must be non-empty"
                    )
                if not project_root or not project_root.startswith("/"):
                    errors.append(
                        f"processing_behavior.context_inputs.cross_project_context[{index}].project_root must be absolute"
                    )
                if not context_note:
                    errors.append(
                        f"processing_behavior.context_inputs.cross_project_context[{index}].context_note must be non-empty"
                    )
                if not isinstance(evidence_refs, list):
                    errors.append(
                        f"processing_behavior.context_inputs.cross_project_context[{index}].evidence_refs must be a list"
                    )
                    evidence_refs = []
                normalized_cross_project_context_for_digest.append(
                    {
                        "project_id": project_id,
                        "project_root": project_root,
                        "evidence_refs": sorted({_as_text(ref) for ref in evidence_refs if _as_text(ref)}),
                        "context_note": context_note,
                    }
                )
            normalized_cross_project_context_for_digest.sort(
                key=lambda row: (row["project_id"], row["project_root"], row["context_note"])
            )

        candidate_recommendations = context_inputs.get("candidate_recommendations")
        if not isinstance(candidate_recommendations, list):
            errors.append("processing_behavior.context_inputs.candidate_recommendations must be a list")
        else:
            for index, row in enumerate(candidate_recommendations):
                if not isinstance(row, Mapping):
                    errors.append(
                        f"processing_behavior.context_inputs.candidate_recommendations[{index}] must be an object"
                    )
                    continue
                action_id = _as_text(row.get("action_id"))
                summary = _as_text(row.get("summary"))
                rationale = _as_text(row.get("rationale"))
                action_scope = _as_text(row.get("action_scope")).lower()
                requires_earth_evidence = bool(row.get("requires_earth_evidence"))
                project_id = _as_text(row.get("project_id"))
                next_step = _as_text(row.get("next_step"))
                evidence_refs = row.get("evidence_refs")
                if not action_id:
                    errors.append(
                        f"processing_behavior.context_inputs.candidate_recommendations[{index}].action_id must be non-empty"
                    )
                if not summary:
                    errors.append(
                        f"processing_behavior.context_inputs.candidate_recommendations[{index}].summary must be non-empty"
                    )
                if not rationale:
                    errors.append(
                        f"processing_behavior.context_inputs.candidate_recommendations[{index}].rationale must be non-empty"
                    )
                if action_scope not in {"local", "cross-project"}:
                    errors.append(
                        f"processing_behavior.context_inputs.candidate_recommendations[{index}].action_scope must be local or cross-project"
                    )
                if not next_step:
                    errors.append(
                        f"processing_behavior.context_inputs.candidate_recommendations[{index}].next_step must be non-empty"
                    )
                if not isinstance(evidence_refs, list):
                    errors.append(
                        f"processing_behavior.context_inputs.candidate_recommendations[{index}].evidence_refs must be a list"
                    )
                    evidence_refs = []
                normalized_candidate_recommendations_for_digest.append(
                    {
                        "action_id": action_id,
                        "summary": summary,
                        "rationale": rationale,
                        "action_scope": action_scope if action_scope in {"local", "cross-project"} else "local",
                        "requires_earth_evidence": requires_earth_evidence,
                        "project_id": project_id,
                        "evidence_refs": sorted({_as_text(ref) for ref in evidence_refs if _as_text(ref)}),
                        "next_step": next_step,
                    }
                )
            normalized_candidate_recommendations_for_digest.sort(key=lambda row: row["action_id"])

        strategic_claims = context_inputs.get("strategic_claims")
        if not isinstance(strategic_claims, list):
            errors.append("processing_behavior.context_inputs.strategic_claims must be a list")
        else:
            for index, row in enumerate(strategic_claims):
                if not isinstance(row, Mapping):
                    errors.append(f"processing_behavior.context_inputs.strategic_claims[{index}] must be an object")
                    continue
                claim_id = _as_text(row.get("claim_id"))
                phase = _as_text(row.get("phase")).lower()
                summary = _as_text(row.get("summary"))
                position = _as_text(row.get("position"))
                source_call_sequence = row.get("source_call_sequence")
                evidence_refs = row.get("evidence_refs")
                if not claim_id:
                    errors.append(f"processing_behavior.context_inputs.strategic_claims[{index}].claim_id must be non-empty")
                if not phase:
                    errors.append(f"processing_behavior.context_inputs.strategic_claims[{index}].phase must be non-empty")
                if not summary:
                    errors.append(f"processing_behavior.context_inputs.strategic_claims[{index}].summary must be non-empty")
                if not position:
                    errors.append(f"processing_behavior.context_inputs.strategic_claims[{index}].position must be non-empty")
                if isinstance(source_call_sequence, bool) or not isinstance(source_call_sequence, int):
                    errors.append(
                        f"processing_behavior.context_inputs.strategic_claims[{index}].source_call_sequence must be an integer"
                    )
                    source_call_sequence = 0
                if not isinstance(evidence_refs, list):
                    errors.append(
                        f"processing_behavior.context_inputs.strategic_claims[{index}].evidence_refs must be a list"
                    )
                    evidence_refs = []
                normalized_strategic_claims_for_digest.append(
                    {
                        "claim_id": claim_id,
                        "phase": phase,
                        "summary": summary,
                        "position": position,
                        "source_call_sequence": source_call_sequence,
                        "evidence_refs": sorted({_as_text(ref) for ref in evidence_refs if _as_text(ref)}),
                    }
                )
            normalized_strategic_claims_for_digest.sort(
                key=lambda row: (
                    row["claim_id"],
                    row["phase"],
                    row["source_call_sequence"],
                    row["position"],
                    row["summary"],
                )
            )

    context_usage = processing_behavior.get("context_usage")
    if not isinstance(context_usage, Mapping):
        errors.append("processing_behavior.context_usage must be an object")
    else:
        for key in (
            "target_project_context_used",
            "earth_sweep_context_used",
            "cross_project_context_used",
            "target_project_refs_used",
            "earth_sweep_refs_used",
            "cross_project_refs_used",
            "cross_project_projects_considered",
            "evidence_refs_used",
        ):
            if key not in context_usage:
                errors.append(f"processing_behavior.context_usage missing keys: ['{key}']")

    recommendation = processing_behavior.get("recommendation")
    recommendation_evidence_refs: list[str] = []
    if not isinstance(recommendation, Mapping):
        errors.append("processing_behavior.recommendation must be an object")
    else:
        required_recommendation = {
            "decision",
            "rationale",
            "confidence",
            "evidence_refs",
            "recommended_actions",
            "cross_project_obligations",
            "open_risks",
        }
        recommendation_keys = set(recommendation.keys())
        missing_recommendation = sorted(required_recommendation - recommendation_keys)
        if missing_recommendation:
            errors.append(f"processing_behavior.recommendation missing keys: {missing_recommendation}")
        if not isinstance(recommendation.get("evidence_refs"), list):
            errors.append("processing_behavior.recommendation.evidence_refs must be a list")
        else:
            recommendation_evidence_refs = sorted(
                {_as_text(ref) for ref in recommendation.get("evidence_refs", []) if _as_text(ref)}
            )
        if not isinstance(recommendation.get("recommended_actions"), list):
            errors.append("processing_behavior.recommendation.recommended_actions must be a list")
        obligations = recommendation.get("cross_project_obligations")
        earth_ref_set = {ref for ref in earth_sweep_refs_from_context if _is_earth_evidence_ref(ref)}
        if not isinstance(obligations, list):
            errors.append("processing_behavior.recommendation.cross_project_obligations must be a list")
            obligations = []
        if obligations and not earth_ref_set:
            errors.append(
                "processing_behavior.recommendation.cross_project_obligations must be empty without earth_sweep evidence refs"
            )
        for index, obligation in enumerate(obligations):
            if not isinstance(obligation, Mapping):
                errors.append(f"processing_behavior.recommendation.cross_project_obligations[{index}] must be an object")
                continue
            evidence_refs = obligation.get("evidence_refs")
            if not isinstance(evidence_refs, list) or not evidence_refs:
                errors.append(
                    f"processing_behavior.recommendation.cross_project_obligations[{index}].evidence_refs must be non-empty list"
                )
                continue
            obligation_ref_set = {_as_text(ref) for ref in evidence_refs if _as_text(ref)}
            if earth_ref_set and not obligation_ref_set.intersection(earth_ref_set):
                errors.append(
                    f"processing_behavior.recommendation.cross_project_obligations[{index}] must include earth_sweep evidence refs"
                )
        open_risks = recommendation.get("open_risks")
        if not isinstance(open_risks, list):
            errors.append("processing_behavior.recommendation.open_risks must be a list")

    pipeline_plan = processing_behavior.get("pipeline_plan")
    if not isinstance(pipeline_plan, Mapping):
        errors.append("processing_behavior.pipeline_plan must be an object")
        return errors

    required_plan = {
        "plan_id",
        "planner_mode",
        "total_calls",
        "required_evidence_refs",
        "calls",
        "dependency_edges",
        "terminal_expected_output",
    }
    plan_keys = set(pipeline_plan.keys())
    missing_plan = sorted(required_plan - plan_keys)
    if missing_plan:
        errors.append(f"processing_behavior.pipeline_plan missing keys: {missing_plan}")
    unexpected_plan = sorted(plan_keys - required_plan)
    if unexpected_plan:
        errors.append(f"processing_behavior.pipeline_plan unexpected keys: {unexpected_plan}")

    if pipeline_plan.get("planner_mode") != "multi-call-reasoning-chain":
        errors.append("processing_behavior.pipeline_plan.planner_mode must be multi-call-reasoning-chain")
    total_calls = pipeline_plan.get("total_calls")
    if total_calls != call_depth:
        errors.append("processing_behavior.pipeline_plan.total_calls must mirror entrypoint.call_depth")

    required_evidence_refs = pipeline_plan.get("required_evidence_refs")
    if not isinstance(required_evidence_refs, list) or not required_evidence_refs:
        errors.append("processing_behavior.pipeline_plan.required_evidence_refs must be a non-empty array")
        required_evidence_refs = []

    calls = pipeline_plan.get("calls")
    call_rows: list[Mapping[str, Any]] = []
    if not isinstance(calls, list):
        errors.append("processing_behavior.pipeline_plan.calls must be an array")
    else:
        if len(calls) != call_depth:
            errors.append("processing_behavior.pipeline_plan.calls length must match call_depth")
        prior_call_ids: list[str] = []
        expected_dependency_edges: list[dict[str, str]] = []
        for index, row in enumerate(calls):
            if not isinstance(row, Mapping):
                errors.append(f"processing_behavior.pipeline_plan.calls[{index}] must be an object")
                continue
            call_rows.append(row)
            sequence = row.get("sequence")
            if sequence != index + 1:
                errors.append(f"processing_behavior.pipeline_plan.calls[{index}].sequence must be {index + 1}")
            call_id = row.get("call_id")
            purpose = row.get("purpose")
            expected_output = row.get("expected_output")
            if not isinstance(call_id, str) or not call_id.strip():
                errors.append(f"processing_behavior.pipeline_plan.calls[{index}].call_id must be non-empty")
            if not isinstance(purpose, str) or not purpose.strip():
                errors.append(f"processing_behavior.pipeline_plan.calls[{index}].purpose must be non-empty")
            if not isinstance(expected_output, str) or not expected_output.strip():
                errors.append(f"processing_behavior.pipeline_plan.calls[{index}].expected_output must be non-empty")
            if isinstance(call_id, str) and isinstance(purpose, str) and isinstance(expected_output, str):
                if isinstance(revision_identity, str) and isinstance(strategy_goal, str):
                    expected_call_id = _build_call_id(
                        revision_identity=revision_identity.strip(),
                        strategy_goal=strategy_goal.strip(),
                        sequence=index + 1,
                        purpose=purpose.strip(),
                        expected_output=expected_output.strip(),
                    )
                    if call_id != expected_call_id:
                        errors.append(f"processing_behavior.pipeline_plan.calls[{index}].call_id is not reproducible")

            depends_on = row.get("depends_on")
            if not isinstance(depends_on, list):
                errors.append(f"processing_behavior.pipeline_plan.calls[{index}].depends_on must be an array")
                depends_on = []
            if index == 0 and depends_on:
                errors.append("processing_behavior.pipeline_plan.calls[0].depends_on must be empty")
            if index > 0 and not depends_on:
                errors.append(f"processing_behavior.pipeline_plan.calls[{index}].depends_on must not be empty")
            for dep_index, upstream_call_id in enumerate(depends_on):
                if not isinstance(upstream_call_id, str) or not upstream_call_id.strip():
                    errors.append(
                        f"processing_behavior.pipeline_plan.calls[{index}].depends_on[{dep_index}] must be non-empty string"
                    )
                    continue
                if upstream_call_id not in prior_call_ids:
                    errors.append(
                        f"processing_behavior.pipeline_plan.calls[{index}].depends_on[{dep_index}] must reference an earlier call_id"
                    )
                if isinstance(call_id, str) and call_id.strip():
                    expected_dependency_edges.append({"from_call_id": upstream_call_id, "to_call_id": call_id})

            row_evidence_refs = row.get("evidence_refs")
            if not isinstance(row_evidence_refs, list) or not row_evidence_refs:
                errors.append(f"processing_behavior.pipeline_plan.calls[{index}].evidence_refs must be a non-empty array")
            elif sorted(set(_as_text(ref) for ref in row_evidence_refs if _as_text(ref))) != sorted(required_evidence_refs):
                errors.append(
                    f"processing_behavior.pipeline_plan.calls[{index}].evidence_refs must match required_evidence_refs"
                )

            if isinstance(call_id, str) and call_id.strip():
                prior_call_ids.append(call_id)

        terminal_expected_output = pipeline_plan.get("terminal_expected_output")
        if call_rows and isinstance(terminal_expected_output, str):
            final_output = _as_text(call_rows[-1].get("expected_output"))
            if terminal_expected_output != final_output:
                errors.append("processing_behavior.pipeline_plan.terminal_expected_output must match final call expected_output")

        dependency_edges = pipeline_plan.get("dependency_edges")
        if not isinstance(dependency_edges, list):
            errors.append("processing_behavior.pipeline_plan.dependency_edges must be an array")
        elif dependency_edges != expected_dependency_edges:
            errors.append("processing_behavior.pipeline_plan.dependency_edges must mirror call dependency links")

    missing_required_refs = sorted(set(required_evidence_refs) - set(recommendation_evidence_refs))
    if missing_required_refs:
        errors.append("processing_behavior.recommendation.evidence_refs must include required_evidence_refs")

    metadata = payload.get("call_metadata")
    if not isinstance(metadata, Mapping):
        errors.append("call_metadata must be an object")
        return errors

    required_metadata = {
        "reproducibility",
        "canonical_input_sha256",
        "reproducible_call_id",
        "canonical_input",
        "processing_input_sha256",
        "processing_call_id",
        "canonical_processing_input",
        "llm_call_trace_schema_version",
        "llm_call_trace_path",
        "llm_call_trace_sha256",
        "llm_call_trace_rows",
    }
    metadata_keys = set(metadata.keys())
    missing_metadata = sorted(required_metadata - metadata_keys)
    if missing_metadata:
        errors.append(f"call_metadata missing keys: {missing_metadata}")
    unexpected_metadata = sorted(metadata_keys - required_metadata)
    if unexpected_metadata:
        errors.append(f"call_metadata unexpected keys: {unexpected_metadata}")

    if metadata.get("reproducibility") != "deterministic-input-fingerprint":
        errors.append("call_metadata.reproducibility must be deterministic-input-fingerprint")

    canonical_input = metadata.get("canonical_input")
    if not isinstance(canonical_input, Mapping):
        errors.append("call_metadata.canonical_input must be an object")
        return errors

    expected_canonical_input = _canonical_call_input(
        target_project_root=_as_text(entrypoint.get("target_project_root")),
        earth_root=_as_text(entrypoint.get("earth_root")),
        output_root=_as_text(entrypoint.get("output_root")),
        revision_identity=_as_text(entrypoint.get("revision_identity")),
        strategy_goal=_as_text(entrypoint.get("strategy_goal")),
        call_depth=int(call_depth),
    )
    if dict(canonical_input) != expected_canonical_input:
        errors.append("call_metadata.canonical_input must mirror normalized invocation anchors")

    expected_input_sha = _canonical_digest(expected_canonical_input)
    if metadata.get("canonical_input_sha256") != expected_input_sha:
        errors.append("call_metadata.canonical_input_sha256 does not match canonical input")
    if metadata.get("reproducible_call_id") != f"req025-{expected_input_sha[:16]}":
        errors.append("call_metadata.reproducible_call_id does not match canonical digest")

    canonical_processing_input = metadata.get("canonical_processing_input")
    if not isinstance(canonical_processing_input, Mapping):
        errors.append("call_metadata.canonical_processing_input must be an object")
        return errors

    stage_blueprints: list[dict[str, str]] = []
    for index, row in enumerate(call_rows):
        purpose = _as_text(row.get("purpose"))
        expected_output = _as_text(row.get("expected_output"))
        if not purpose or not expected_output:
            continue
        stage_blueprints.append({"purpose": purpose, "expected_output": expected_output})

    expected_processing_input = _canonical_processing_input(
        evidence_refs=sorted(set(_as_text(ref) for ref in required_evidence_refs if _as_text(ref))),
        stage_blueprints=stage_blueprints,
        call_depth=int(call_depth),
        target_project_evidence_refs=target_project_refs_from_context,
        earth_sweep_evidence_refs=earth_sweep_refs_from_context,
        cross_project_context=normalized_cross_project_context_for_digest,
        candidate_recommendations=normalized_candidate_recommendations_for_digest,
        strategic_claims=normalized_strategic_claims_for_digest,
    )
    if dict(canonical_processing_input) != expected_processing_input:
        errors.append("call_metadata.canonical_processing_input must mirror pipeline plan inputs")

    expected_processing_sha = _canonical_digest(expected_processing_input)
    if metadata.get("processing_input_sha256") != expected_processing_sha:
        errors.append("call_metadata.processing_input_sha256 does not match processing input")
    expected_processing_call_id = f"req025-processing-{expected_processing_sha[:16]}"
    if metadata.get("processing_call_id") != expected_processing_call_id:
        errors.append("call_metadata.processing_call_id does not match processing digest")
    if pipeline_plan.get("plan_id") != f"req025-plan-{expected_processing_sha[:16]}":
        errors.append("processing_behavior.pipeline_plan.plan_id must derive from processing digest")

    if metadata.get("llm_call_trace_schema_version") != REQ_025_LLM_CALL_TRACE_SCHEMA_VERSION:
        errors.append(
            f"call_metadata.llm_call_trace_schema_version must be {REQ_025_LLM_CALL_TRACE_SCHEMA_VERSION}"
        )
    if metadata.get("llm_call_trace_path") != LLM_CALL_TRACE_RELATIVE_PATH:
        errors.append(f"call_metadata.llm_call_trace_path must be {LLM_CALL_TRACE_RELATIVE_PATH}")
    llm_call_trace_rows = metadata.get("llm_call_trace_rows")
    if not isinstance(llm_call_trace_rows, list):
        errors.append("call_metadata.llm_call_trace_rows must be a list")
        llm_call_trace_rows = []
    expected_trace_rows: list[dict[str, Any]] = []
    try:
        expected_trace_rows = _build_llm_call_trace_rows(
            plan_id=_as_text(pipeline_plan.get("plan_id")),
            processing_call_id=expected_processing_call_id,
            required_evidence_refs=sorted(set(_as_text(ref) for ref in required_evidence_refs if _as_text(ref))),
            calls=call_rows,
            recommendation_decision=_as_text(recommendation.get("decision")) if isinstance(recommendation, Mapping) else "",
        )
    except ValueError as exc:
        errors.append(f"call_metadata.llm_call_trace_rows could not be reconstructed: {exc}")
    else:
        if llm_call_trace_rows != expected_trace_rows:
            errors.append("call_metadata.llm_call_trace_rows must mirror the deterministic per-call trace rows")
        expected_trace_sha = _canonical_digest(expected_trace_rows)
        if metadata.get("llm_call_trace_sha256") != expected_trace_sha:
            errors.append("call_metadata.llm_call_trace_sha256 does not match llm_call_trace_rows")

    return errors


def _req_026_normalize_anchor(value: Any, *, field_name: str) -> dict[str, Any]:
    if isinstance(value, str):
        text = _require_text(value, field_name=field_name)
        return {"text": text, "source": "inline", "authoritative": True}

    anchor = _require_mapping(value, field_name=field_name)
    source = _as_text(anchor.get("source")) or "inline"
    return {
        "text": _require_text(anchor.get("text"), field_name=f"{field_name}.text"),
        "source": source,
        "authoritative": True,
    }


def _req_026_normalize_string_list(
    value: Any,
    *,
    field_name: str,
    min_items: int = 0,
) -> list[str]:
    if value is None:
        rows: Sequence[Any] = []
    else:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            raise Req026Error(f"{field_name} must be an array")
        rows = value

    normalized: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(rows):
        text = _require_text(item, field_name=f"{field_name}[{index}]")
        if text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    if len(normalized) < min_items:
        raise Req026Error(f"{field_name} must contain at least {min_items} item(s)")
    return normalized


def _req_026_dedupe_preserving_order(rows: Sequence[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if row in seen:
            continue
        seen.add(row)
        deduped.append(row)
    return deduped


def _req_026_normalize_unknown_item(
    value: Any,
    *,
    field_name: str,
    category: str,
) -> dict[str, str]:
    if isinstance(value, str):
        question = _require_text(value, field_name=field_name)
        why_it_matters = (
            "Call-2 needs a stable planning baseline before turning this assessment into implementation work."
            if category == "planning"
            else "Call-2 needs current runtime certainty before promoting execution assumptions."
        )
        return {"question": question, "why_it_matters": why_it_matters}

    row = _require_mapping(value, field_name=field_name)
    return {
        "question": _require_text(row.get("question"), field_name=f"{field_name}.question"),
        "why_it_matters": _require_text(row.get("why_it_matters"), field_name=f"{field_name}.why_it_matters"),
    }


def _req_026_normalize_evidence_artifacts(
    payload: Any,
    *,
    field_name: str,
    category: str,
    allowed_statuses: set[str],
) -> list[dict[str, Any]]:
    container = _require_mapping(payload, field_name=field_name)
    rows = container.get("artifacts")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        raise Req026Error(f"{field_name}.artifacts must be an array")
    if not rows:
        raise Req026Error(f"{field_name}.artifacts must contain at least one artifact")

    artifacts: list[dict[str, Any]] = []
    seen_artifact_ids: set[str] = set()
    for index, raw_row in enumerate(rows):
        row = _require_mapping(raw_row, field_name=f"{field_name}.artifacts[{index}]")
        artifact_id = _require_text(
            row.get("artifact_id"),
            field_name=f"{field_name}.artifacts[{index}].artifact_id",
        )
        if artifact_id in seen_artifact_ids:
            raise Req026Error(f"{field_name}.artifacts[{index}].artifact_id duplicates {artifact_id}")
        seen_artifact_ids.add(artifact_id)

        status = _require_text(
            row.get("status"),
            field_name=f"{field_name}.artifacts[{index}].status",
        ).lower()
        if status not in allowed_statuses:
            raise Req026Error(
                f"{field_name}.artifacts[{index}].status must be one of {sorted(allowed_statuses)}"
            )

        unknowns_value = row.get("unknowns", [])
        if not isinstance(unknowns_value, Sequence) or isinstance(unknowns_value, (str, bytes, bytearray)):
            raise Req026Error(f"{field_name}.artifacts[{index}].unknowns must be an array")

        artifacts.append(
            {
                "artifact_id": artifact_id,
                "summary": _require_text(
                    row.get("summary"),
                    field_name=f"{field_name}.artifacts[{index}].summary",
                ),
                "status": status,
                "source_ref": _require_text(
                    row.get("source_ref"),
                    field_name=f"{field_name}.artifacts[{index}].source_ref",
                ),
                "signals": _req_026_normalize_string_list(
                    row.get("signals"),
                    field_name=f"{field_name}.artifacts[{index}].signals",
                    min_items=1,
                ),
                "unknowns": [
                    _req_026_normalize_unknown_item(
                        item,
                        field_name=f"{field_name}.artifacts[{index}].unknowns[{unknown_index}]",
                        category=category,
                    )
                    for unknown_index, item in enumerate(unknowns_value)
                ],
            }
        )
    return artifacts


def _req_026_normalize_cross_project_context(
    value: Any,
    *,
    field_name: str,
) -> list[dict[str, Any]]:
    if value is None:
        rows: Sequence[Any] = []
    else:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            raise Req026Error(f"{field_name} must be an array")
        rows = value

    normalized: list[dict[str, Any]] = []
    seen_project_ids: set[str] = set()
    for index, raw_row in enumerate(rows):
        row = _require_mapping(raw_row, field_name=f"{field_name}[{index}]")
        project_id = _require_text(row.get("project_id"), field_name=f"{field_name}[{index}].project_id")
        if project_id in seen_project_ids:
            raise Req026Error(f"{field_name}[{index}].project_id must be unique")
        seen_project_ids.add(project_id)
        normalized.append(
            {
                "project_id": project_id,
                "project_root": _require_text(
                    row.get("project_root"),
                    field_name=f"{field_name}[{index}].project_root",
                ),
                "evidence_refs": _req_026_normalize_string_list(
                    row.get("evidence_refs", []),
                    field_name=f"{field_name}[{index}].evidence_refs",
                ),
                "context_note": _require_text(
                    row.get("context_note"),
                    field_name=f"{field_name}[{index}].context_note",
                ),
            }
        )
    normalized.sort(key=lambda row: row["project_id"])
    return normalized


def _req_026_normalize_candidate_recommendations(
    value: Any,
    *,
    field_name: str,
) -> list[dict[str, Any]]:
    if value is None:
        rows: Sequence[Any] = []
    else:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            raise Req026Error(f"{field_name} must be an array")
        rows = value

    normalized: list[dict[str, Any]] = []
    seen_recommendation_ids: set[str] = set()
    for index, raw_row in enumerate(rows):
        row = _require_mapping(raw_row, field_name=f"{field_name}[{index}]")
        recommendation_id = _require_text(
            row.get("recommendation_id"),
            field_name=f"{field_name}[{index}].recommendation_id",
        )
        if recommendation_id in seen_recommendation_ids:
            raise Req026Error(f"{field_name}[{index}].recommendation_id must be unique")
        seen_recommendation_ids.add(recommendation_id)

        recommendation_scope = _require_text(
            row.get("recommendation_scope"),
            field_name=f"{field_name}[{index}].recommendation_scope",
        ).lower()
        if recommendation_scope not in REQ_026_ALLOWED_RECOMMENDATION_SCOPES:
            raise Req026Error(
                f"{field_name}[{index}].recommendation_scope must be one of "
                f"{sorted(REQ_026_ALLOWED_RECOMMENDATION_SCOPES)}"
            )

        project_id = _as_text(row.get("project_id"))
        if recommendation_scope == "cross-project":
            project_id = _require_text(project_id, field_name=f"{field_name}[{index}].project_id")
        else:
            project_id = ""

        requires_earth_evidence = row.get("requires_earth_evidence")
        if requires_earth_evidence is None:
            requires_earth_evidence = recommendation_scope == "cross-project"
        if not isinstance(requires_earth_evidence, bool):
            raise Req026Error(f"{field_name}[{index}].requires_earth_evidence must be a boolean")

        normalized.append(
            {
                "recommendation_id": recommendation_id,
                "summary": _require_text(
                    row.get("summary"),
                    field_name=f"{field_name}[{index}].summary",
                ),
                "rationale": _require_text(
                    row.get("rationale"),
                    field_name=f"{field_name}[{index}].rationale",
                ),
                "recommendation_scope": recommendation_scope,
                "project_id": project_id,
                "requires_earth_evidence": requires_earth_evidence,
                "evidence_refs": _req_026_normalize_string_list(
                    row.get("evidence_refs"),
                    field_name=f"{field_name}[{index}].evidence_refs",
                    min_items=1,
                ),
                "next_step": _require_text(
                    row.get("next_step"),
                    field_name=f"{field_name}[{index}].next_step",
                ),
            }
        )
    normalized.sort(key=lambda row: row["recommendation_id"])
    return normalized


def _req_026_normalize_strategic_claims(
    value: Any,
    *,
    field_name: str,
) -> list[dict[str, Any]]:
    if value is None:
        rows: Sequence[Any] = []
    else:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            raise Req026Error(f"{field_name} must be an array")
        rows = value

    normalized: list[dict[str, Any]] = []
    for index, raw_row in enumerate(rows):
        row = _require_mapping(raw_row, field_name=f"{field_name}[{index}]")
        phase = _require_text(row.get("phase"), field_name=f"{field_name}[{index}].phase").lower()
        if phase not in REQ_026_ALLOWED_CLAIM_PHASES:
            raise Req026Error(
                f"{field_name}[{index}].phase must be one of {sorted(REQ_026_ALLOWED_CLAIM_PHASES)}"
            )
        source_call_sequence = row.get("source_call_sequence")
        if isinstance(source_call_sequence, bool) or not isinstance(source_call_sequence, int) or source_call_sequence < 1:
            raise Req026Error(f"{field_name}[{index}].source_call_sequence must be an integer >= 1")
        normalized.append(
            {
                "claim_id": _require_text(
                    row.get("claim_id"),
                    field_name=f"{field_name}[{index}].claim_id",
                ),
                "phase": phase,
                "summary": _require_text(
                    row.get("summary"),
                    field_name=f"{field_name}[{index}].summary",
                ),
                "position": _require_text(
                    row.get("position"),
                    field_name=f"{field_name}[{index}].position",
                ),
                "source_call_sequence": source_call_sequence,
                "evidence_refs": _req_026_normalize_string_list(
                    row.get("evidence_refs"),
                    field_name=f"{field_name}[{index}].evidence_refs",
                ),
            }
        )
    normalized.sort(
        key=lambda row: (
            row["claim_id"],
            row["phase"],
            row["source_call_sequence"],
            row["position"],
            row["summary"],
        )
    )
    return normalized


def _req_026_normalize_broad_sweep_context(value: Any, *, field_name: str) -> dict[str, Any]:
    if value is None:
        container: Mapping[str, Any] = {}
    else:
        container = _require_mapping(value, field_name=field_name)
    return {
        "earth_sweep_evidence_refs": _req_026_normalize_string_list(
            container.get("earth_sweep_evidence_refs", []),
            field_name=f"{field_name}.earth_sweep_evidence_refs",
        ),
        "cross_project_context": _req_026_normalize_cross_project_context(
            container.get("cross_project_context", []),
            field_name=f"{field_name}.cross_project_context",
        ),
        "candidate_recommendations": _req_026_normalize_candidate_recommendations(
            container.get("candidate_recommendations", []),
            field_name=f"{field_name}.candidate_recommendations",
        ),
        "strategic_claims": _req_026_normalize_strategic_claims(
            container.get("strategic_claims", []),
            field_name=f"{field_name}.strategic_claims",
        ),
    }


def _req_026_evidence_status(artifacts: Sequence[Mapping[str, Any]], *, category: str) -> str:
    statuses = {str(row["status"]) for row in artifacts}
    if "blocked" in statuses:
        return "blocked"
    if category == "planning":
        if "partial" in statuses:
            return "partial"
        return "ready"
    if "degraded" in statuses:
        return "degraded"
    return "healthy"


def _req_026_collect_state_details(
    artifacts: Sequence[Mapping[str, Any]],
) -> tuple[list[str], list[str], list[str]]:
    artifact_ids: list[str] = []
    source_refs: list[str] = []
    key_signals: list[str] = []
    seen_source_refs: set[str] = set()
    seen_signals: set[str] = set()

    for row in artifacts:
        artifact_ids.append(str(row["artifact_id"]))
        source_ref = str(row["source_ref"])
        if source_ref not in seen_source_refs:
            seen_source_refs.add(source_ref)
            source_refs.append(source_ref)
        for signal in row["signals"]:
            if signal not in seen_signals:
                seen_signals.add(signal)
                key_signals.append(signal)
    return artifact_ids, source_refs, key_signals


def _req_026_assessment_status(*, planning_status: str, runtime_status: str) -> str:
    if planning_status == "blocked" or runtime_status == "blocked":
        return "blocked"
    if planning_status == "partial" or runtime_status == "degraded":
        return "needs-follow-up"
    return "grounded"


def _req_026_build_state_summary(
    *,
    project_id: str,
    planning_status: str,
    runtime_status: str,
    unknown_count: int,
) -> str:
    return (
        f"{project_id} remains anchored to mission and scope, planning evidence is {planning_status}, "
        f"runtime evidence is {runtime_status}, and {unknown_count} explicit unknown(s) must be resolved in later calls."
    )


def _req_026_build_unknowns(
    *,
    planning_artifacts: Sequence[Mapping[str, Any]],
    runtime_artifacts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    unknowns: list[dict[str, Any]] = []
    ordinal = 1
    for category, artifacts in (("planning", planning_artifacts), ("runtime", runtime_artifacts)):
        for artifact in artifacts:
            for unknown in artifact["unknowns"]:
                unknowns.append(
                    {
                        "unknown_id": f"unknown.{ordinal:03d}",
                        "category": category,
                        "question": unknown["question"],
                        "why_it_matters": unknown["why_it_matters"],
                        "must_be_resolved_by": "call-2",
                        "provenance": {
                            "evidence_type": category,
                            "artifact_id": artifact["artifact_id"],
                            "source_ref": artifact["source_ref"],
                        },
                    }
                )
                ordinal += 1
    if not unknowns:
        raise Req026Error("at least one explicit unknown is required for Call-1 situational analysis")
    return unknowns


def _req_026_build_cross_project_context_summary(
    *,
    earth_sweep_evidence_refs: Sequence[str],
    cross_project_context: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    projects_considered = [str(row["project_id"]) for row in cross_project_context]
    projects_with_evidence_refs = [
        str(row["project_id"]) for row in cross_project_context if row.get("evidence_refs")
    ]
    projects_without_evidence_refs = [
        str(row["project_id"]) for row in cross_project_context if not row.get("evidence_refs")
    ]
    evidence_refs_by_project = {
        str(row["project_id"]): list(row.get("evidence_refs", []))
        for row in cross_project_context
    }
    return {
        "cross_project": bool(cross_project_context),
        "projects_considered": projects_considered,
        "projects_with_evidence_refs": projects_with_evidence_refs,
        "projects_without_evidence_refs": projects_without_evidence_refs,
        "earth_sweep_evidence_refs": list(earth_sweep_evidence_refs),
        "evidence_refs_by_project": evidence_refs_by_project,
    }


def _req_026_claim_output_ref(*, source_call_sequence: int, phase: str) -> str:
    return f"{REQ_026_REQUIREMENT_ID}::call-chain::{source_call_sequence:02d}::{phase}"


def _req_026_build_processing_behavior(
    *,
    broad_sweep_context: Mapping[str, Any],
    planning_refs: Sequence[str],
    runtime_refs: Sequence[str],
    assessment_status: str,
    unknowns: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    earth_sweep_evidence_refs = list(broad_sweep_context["earth_sweep_evidence_refs"])
    cross_project_context = list(broad_sweep_context["cross_project_context"])
    candidate_recommendations = list(broad_sweep_context["candidate_recommendations"])
    strategic_claims = list(broad_sweep_context["strategic_claims"])
    context_by_project = {
        str(row["project_id"]): row for row in cross_project_context
    }
    available_citation_refs = set(
        _req_026_dedupe_preserving_order(
            list(planning_refs)
            + list(runtime_refs)
            + list(earth_sweep_evidence_refs)
            + [ref for row in cross_project_context for ref in row.get("evidence_refs", [])]
        )
    )

    recommended_next_actions: list[dict[str, Any]] = []
    cross_project_obligations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []

    claims_by_id: dict[str, list[dict[str, Any]]] = {}
    for row in strategic_claims:
        claim_id = str(row["claim_id"])
        claims_by_id.setdefault(claim_id, []).append(row)
        citation_refs = list(row["evidence_refs"])
        source_output_ref = _req_026_claim_output_ref(
            source_call_sequence=int(row["source_call_sequence"]),
            phase=str(row["phase"]),
        )
        if not citation_refs or not set(citation_refs).issubset(available_citation_refs):
            open_risks.append(
                {
                    "risk_id": f"risk-claim-{claim_id}-citation",
                    "reason_code": "uncited_strategic_claim",
                    "summary": row["summary"],
                    "required_evidence_refs": _req_026_dedupe_preserving_order([source_output_ref] + citation_refs),
                }
            )

    for claim_id, claim_rows in claims_by_id.items():
        analysis_rows = [row for row in claim_rows if row["phase"] == "analysis"]
        synthesis_rows = [row for row in claim_rows if row["phase"] == "synthesis"]
        contradiction_refs: list[str] | None = None
        contradiction_summary = ""
        for analysis_row in analysis_rows:
            for synthesis_row in synthesis_rows:
                if analysis_row["position"] == synthesis_row["position"]:
                    continue
                contradiction_summary = str(synthesis_row["summary"])
                contradiction_refs = _req_026_dedupe_preserving_order(
                    [
                        _req_026_claim_output_ref(
                            source_call_sequence=int(analysis_row["source_call_sequence"]),
                            phase=str(analysis_row["phase"]),
                        ),
                        _req_026_claim_output_ref(
                            source_call_sequence=int(synthesis_row["source_call_sequence"]),
                            phase=str(synthesis_row["phase"]),
                        ),
                    ]
                    + list(analysis_row["evidence_refs"])
                    + list(synthesis_row["evidence_refs"])
                )
                break
            if contradiction_refs is not None:
                break
        if contradiction_refs is not None:
            open_risks.append(
                {
                    "risk_id": f"risk-claim-{claim_id}-contradiction",
                    "reason_code": "cross_call_contradiction",
                    "summary": contradiction_summary,
                    "required_evidence_refs": contradiction_refs,
                }
            )

    for row in candidate_recommendations:
        recommendation_id = str(row["recommendation_id"])
        if row["recommendation_scope"] == "local":
            recommended_next_actions.append(
                {
                    "recommendation_id": recommendation_id,
                    "summary": row["summary"],
                    "rationale": row["rationale"],
                    "next_step": row["next_step"],
                    "evidence_refs": list(row["evidence_refs"]),
                }
            )
            continue

        project_id = str(row["project_id"])
        project_context = context_by_project.get(project_id)
        project_evidence_refs = list(project_context.get("evidence_refs", [])) if project_context else []

        missing_reason_codes: list[str] = []
        if row["requires_earth_evidence"] and not earth_sweep_evidence_refs:
            missing_reason_codes.append("missing_earth_sweep_evidence_refs")
        if project_context is None:
            missing_reason_codes.append("missing_cross_project_context")
        elif not project_evidence_refs:
            missing_reason_codes.append("missing_cross_project_context_evidence_refs")

        if missing_reason_codes:
            open_risks.append(
                {
                    "risk_id": f"risk-{recommendation_id}",
                    "reason_code": ",".join(missing_reason_codes),
                    "summary": row["summary"],
                    "required_evidence_refs": _req_026_dedupe_preserving_order(
                        list(row["evidence_refs"]) + project_evidence_refs
                    ),
                }
            )
            continue

        cross_project_obligations.append(
            {
                "obligation_id": f"obligation-{recommendation_id}",
                "project_id": project_id,
                "summary": row["summary"],
                "rationale": row["rationale"],
                "next_step": row["next_step"],
                "evidence_refs": _req_026_dedupe_preserving_order(
                    list(earth_sweep_evidence_refs) + project_evidence_refs + list(row["evidence_refs"])
                ),
            }
        )

    recommended_next_actions.sort(key=lambda row: row["recommendation_id"])
    cross_project_obligations.sort(key=lambda row: row["obligation_id"])
    open_risks.sort(key=lambda row: row["risk_id"])

    if assessment_status == "blocked":
        decision = "hold"
        confidence = "low"
    elif open_risks:
        decision = "proceed-with-open-risks"
        confidence = "low" if assessment_status == "needs-follow-up" else "medium"
    elif assessment_status == "needs-follow-up":
        decision = "proceed-with-caution"
        confidence = "medium"
    else:
        decision = "proceed"
        confidence = "high"

    evidence_refs = _req_026_dedupe_preserving_order(
        list(planning_refs)
        + list(runtime_refs)
        + list(earth_sweep_evidence_refs)
        + [ref for row in recommended_next_actions for ref in row["evidence_refs"]]
        + [ref for row in cross_project_obligations for ref in row["evidence_refs"]]
        + [ref for row in open_risks for ref in row["required_evidence_refs"]]
    )

    return {
        "strategy": REQ_026_PROCESSING_STRATEGY,
        "reasoning_mode": REQ_026_REASONING_MODE,
        "strict_evidence_discipline": True,
        "context_inputs": {
            "broad_sweep_context": {
                "earth_sweep_evidence_refs": earth_sweep_evidence_refs,
                "cross_project_context": cross_project_context,
                "candidate_recommendations": candidate_recommendations,
                "strategic_claims": strategic_claims,
            }
        },
        "context_usage": {
            "broad_sweep_context_used": bool(
                earth_sweep_evidence_refs or cross_project_context or candidate_recommendations or strategic_claims
            ),
            "earth_sweep_context_used": bool(earth_sweep_evidence_refs),
            "cross_project_context_used": bool(cross_project_context),
            "earth_sweep_evidence_refs_used": earth_sweep_evidence_refs,
            "cross_project_projects_considered": [str(row["project_id"]) for row in cross_project_context],
            "cross_project_projects_with_evidence_refs": [
                str(row["project_id"]) for row in cross_project_context if row.get("evidence_refs")
            ],
            "cross_project_projects_without_evidence_refs": [
                str(row["project_id"]) for row in cross_project_context if not row.get("evidence_refs")
            ],
            "candidate_recommendation_ids_considered": [
                str(row["recommendation_id"]) for row in candidate_recommendations
            ],
            "local_recommendation_ids_emitted": [
                str(row["recommendation_id"]) for row in recommended_next_actions
            ],
            "cross_project_obligation_ids_emitted": [
                str(row["obligation_id"]) for row in cross_project_obligations
            ],
            "open_risk_ids_emitted": [str(row["risk_id"]) for row in open_risks],
            "unknown_ids_for_later_calls": [str(row["unknown_id"]) for row in unknowns],
        },
        "recommendation": {
            "decision": decision,
            "rationale": (
                f"assessment={assessment_status} unknowns={len(unknowns)} "
                f"local={len(recommended_next_actions)} obligations={len(cross_project_obligations)} "
                f"open_risks={len(open_risks)}"
            ),
            "confidence": confidence,
            "evidence_refs": evidence_refs,
            "recommended_next_actions": recommended_next_actions,
            "cross_project_context": _req_026_build_cross_project_context_summary(
                earth_sweep_evidence_refs=earth_sweep_evidence_refs,
                cross_project_context=cross_project_context,
            ),
            "cross_project_obligations": cross_project_obligations,
            "open_risks": open_risks,
        },
    }


def _req_026_canonical_input(
    *,
    project_id: str,
    mission: Mapping[str, Any],
    scope: Mapping[str, Any],
    planning_artifacts: Sequence[Mapping[str, Any]],
    runtime_artifacts: Sequence[Mapping[str, Any]],
    broad_sweep_context: Mapping[str, Any],
    call_id: str,
    checked_at_utc: str,
) -> dict[str, Any]:
    return {
        "requirement_id": REQ_026_REQUIREMENT_ID,
        "analysis_type": REQ_026_ANALYSIS_TYPE,
        "call_id": call_id,
        "checked_at_utc": checked_at_utc,
        "target_project": {
            "project_id": project_id,
            "mission": dict(mission),
            "scope": dict(scope),
        },
        "planning_evidence": {"artifacts": [dict(row) for row in planning_artifacts]},
        "runtime_evidence": {"artifacts": [dict(row) for row in runtime_artifacts]},
        "broad_sweep_context": {
            "earth_sweep_evidence_refs": list(broad_sweep_context["earth_sweep_evidence_refs"]),
            "cross_project_context": [dict(row) for row in broad_sweep_context["cross_project_context"]],
            "candidate_recommendations": [dict(row) for row in broad_sweep_context["candidate_recommendations"]],
            "strategic_claims": [dict(row) for row in broad_sweep_context["strategic_claims"]],
        },
    }


def _req_026_trace_output_ref(*, call_id: str) -> str:
    return f"{REQ_026_REQUIREMENT_ID}::call::{call_id}::output::situational_analysis"


def _build_req_026_llm_call_trace_rows(
    *,
    processing_call_id: str,
    call_id: str,
    mission_source: str,
    scope_source: str,
    planning_refs: Sequence[str],
    runtime_refs: Sequence[str],
    broad_sweep_context: Mapping[str, Any],
    unknowns: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    input_refs = _req_026_dedupe_preserving_order(
        [mission_source, scope_source]
        + list(planning_refs)
        + list(runtime_refs)
        + list(broad_sweep_context["earth_sweep_evidence_refs"])
        + [
            ref
            for row in broad_sweep_context["cross_project_context"]
            for ref in row.get("evidence_refs", [])
        ]
        + [
            ref
            for row in broad_sweep_context["candidate_recommendations"]
            for ref in row.get("evidence_refs", [])
        ]
        + [
            ref
            for row in broad_sweep_context["strategic_claims"]
            for ref in row.get("evidence_refs", [])
        ]
    )
    output_ref = _req_026_trace_output_ref(call_id=call_id)
    return [
        {
            "schema_version": REQ_026_LLM_CALL_TRACE_SCHEMA_VERSION,
            "requirement_id": REQ_026_REQUIREMENT_ID,
            "processing_call_id": processing_call_id,
            "call_id": call_id,
            "sequence": 1,
            "call_objective": (
                "Assess target project state from mission, scope, planning evidence, runtime evidence, "
                "and explicit unknowns for later calls."
            ),
            "input_refs": input_refs,
            "output_refs": [output_ref],
            "handoff_summary": (
                f"Call 1 hands off situational_analysis via {output_ref} with {len(unknowns)} "
                "explicit unknown(s) for later calls."
            ),
        }
    ]


def build_req_026_call_1_situational_analysis_reasoning(
    *,
    target_project: Mapping[str, Any],
    planning_evidence: Mapping[str, Any],
    runtime_evidence: Mapping[str, Any],
    broad_sweep_context: Mapping[str, Any] | None = None,
    analysis_type: str = REQ_026_ANALYSIS_TYPE,
    call_id: str = "call-1",
    checked_at_utc: str | None = None,
) -> dict[str, Any]:
    if analysis_type != REQ_026_ANALYSIS_TYPE:
        raise Req026Error(f"analysis_type must be {REQ_026_ANALYSIS_TYPE}")

    project = _require_mapping(target_project, field_name="target_project")
    project_id = _require_text(project.get("project_id"), field_name="target_project.project_id")
    mission = _req_026_normalize_anchor(project.get("mission"), field_name="target_project.mission")
    scope = _req_026_normalize_anchor(project.get("scope"), field_name="target_project.scope")

    planning_artifacts = _req_026_normalize_evidence_artifacts(
        planning_evidence,
        field_name="planning_evidence",
        category="planning",
        allowed_statuses=REQ_026_ALLOWED_PLANNING_STATUSES,
    )
    runtime_artifacts = _req_026_normalize_evidence_artifacts(
        runtime_evidence,
        field_name="runtime_evidence",
        category="runtime",
        allowed_statuses=REQ_026_ALLOWED_RUNTIME_STATUSES,
    )
    normalized_broad_sweep_context = _req_026_normalize_broad_sweep_context(
        broad_sweep_context,
        field_name="broad_sweep_context",
    )

    normalized_checked_at_utc = _require_text(checked_at_utc or utc_now_iso(), field_name="checked_at_utc")
    planning_status = _req_026_evidence_status(planning_artifacts, category="planning")
    runtime_status = _req_026_evidence_status(runtime_artifacts, category="runtime")
    unknowns = _req_026_build_unknowns(
        planning_artifacts=planning_artifacts,
        runtime_artifacts=runtime_artifacts,
    )
    overall_status = _req_026_assessment_status(
        planning_status=planning_status,
        runtime_status=runtime_status,
    )

    planning_artifact_ids, planning_refs, planning_signals = _req_026_collect_state_details(planning_artifacts)
    runtime_artifact_ids, runtime_refs, runtime_signals = _req_026_collect_state_details(runtime_artifacts)
    evidence_basis = planning_artifact_ids + runtime_artifact_ids
    processing_behavior = _req_026_build_processing_behavior(
        broad_sweep_context=normalized_broad_sweep_context,
        planning_refs=planning_refs,
        runtime_refs=runtime_refs,
        assessment_status=overall_status,
        unknowns=unknowns,
    )

    canonical_input = _req_026_canonical_input(
        project_id=project_id,
        mission=mission,
        scope=scope,
        planning_artifacts=planning_artifacts,
        runtime_artifacts=runtime_artifacts,
        broad_sweep_context=normalized_broad_sweep_context,
        call_id=call_id,
        checked_at_utc=normalized_checked_at_utc,
    )
    canonical_input_sha = _canonical_digest(canonical_input)
    processing_call_id = f"req026-processing-{canonical_input_sha[:16]}"
    llm_call_trace_rows = _build_req_026_llm_call_trace_rows(
        processing_call_id=processing_call_id,
        call_id=call_id,
        mission_source=str(mission["source"]),
        scope_source=str(scope["source"]),
        planning_refs=planning_refs,
        runtime_refs=runtime_refs,
        broad_sweep_context=normalized_broad_sweep_context,
        unknowns=unknowns,
    )
    llm_call_trace_sha = _canonical_digest(llm_call_trace_rows)

    return {
        "ok": True,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "schema_version": REQ_026_SCHEMA_VERSION,
        "requirement_id": REQ_026_REQUIREMENT_ID,
        "analysis_type": REQ_026_ANALYSIS_TYPE,
        "call_id": call_id,
        "checked_at_utc": normalized_checked_at_utc,
        "situational_analysis": {
            "target_project": {
                "project_id": project_id,
                "mission": mission,
                "scope": scope,
                "anchor_summary": f"Mission: {mission['text']} Scope: {scope['text']}",
            },
            "planning_state": {
                "status": planning_status,
                "artifact_ids": planning_artifact_ids,
                "evidence_refs": planning_refs,
                "key_signals": planning_signals,
            },
            "runtime_state": {
                "status": runtime_status,
                "artifact_ids": runtime_artifact_ids,
                "evidence_refs": runtime_refs,
                "key_signals": runtime_signals,
            },
            "reasoning": {
                "assessment_status": overall_status,
                "anchor_set": ["mission", "scope", "planning_evidence", "runtime_evidence"],
                "state_summary": _req_026_build_state_summary(
                    project_id=project_id,
                    planning_status=planning_status,
                    runtime_status=runtime_status,
                    unknown_count=len(unknowns),
                ),
                "evidence_basis": evidence_basis,
                "follow_up_required": True,
            },
        },
        "processing_behavior": processing_behavior,
        "unknowns": unknowns,
        "source": {
            "planning_artifact_count": len(planning_artifacts),
            "runtime_artifact_count": len(runtime_artifacts),
            "mission_source": mission["source"],
            "scope_source": scope["source"],
            "earth_sweep_evidence_count": len(normalized_broad_sweep_context["earth_sweep_evidence_refs"]),
            "cross_project_context_count": len(normalized_broad_sweep_context["cross_project_context"]),
            "candidate_recommendation_count": len(normalized_broad_sweep_context["candidate_recommendations"]),
        },
        "call_metadata": {
            "reproducibility": "deterministic-input-fingerprint",
            "canonical_input_sha256": canonical_input_sha,
            "reproducible_call_id": f"req026-{canonical_input_sha[:16]}",
            "canonical_input": canonical_input,
            "processing_call_id": processing_call_id,
            "llm_call_trace_schema_version": REQ_026_LLM_CALL_TRACE_SCHEMA_VERSION,
            "llm_call_trace_path": LLM_CALL_TRACE_RELATIVE_PATH,
            "llm_call_trace_sha256": llm_call_trace_sha,
            "llm_call_trace_rows": llm_call_trace_rows,
        },
    }


def validate_req_026_call_1_situational_analysis_reasoning(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []

    if payload.get("ok") is not True:
        errors.append("ok must be true")
    if payload.get("tool") != TOOL:
        errors.append(f"tool must be {TOOL}")
    if payload.get("tool_version") != TOOL_VERSION:
        errors.append(f"tool_version must be {TOOL_VERSION}")
    if payload.get("schema_version") != REQ_026_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_026_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_026_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_026_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_026_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_026_ANALYSIS_TYPE}")
    if payload.get("call_id") != "call-1":
        errors.append("call_id must be call-1")
    if not _as_text(payload.get("checked_at_utc")):
        errors.append("checked_at_utc is required")

    situational_analysis = payload.get("situational_analysis")
    if not isinstance(situational_analysis, Mapping):
        errors.append("situational_analysis must be an object")
        situational_analysis = {}

    target_project = situational_analysis.get("target_project")
    if not isinstance(target_project, Mapping):
        errors.append("situational_analysis.target_project must be an object")
        target_project = {}
    if not _as_text(target_project.get("project_id")):
        errors.append("situational_analysis.target_project.project_id is required")
    for anchor_name in ("mission", "scope"):
        anchor = target_project.get(anchor_name)
        if not isinstance(anchor, Mapping):
            errors.append(f"situational_analysis.target_project.{anchor_name} must be an object")
            continue
        if not _as_text(anchor.get("text")):
            errors.append(f"situational_analysis.target_project.{anchor_name}.text is required")
        if not _as_text(anchor.get("source")):
            errors.append(f"situational_analysis.target_project.{anchor_name}.source is required")
        if anchor.get("authoritative") is not True:
            errors.append(f"situational_analysis.target_project.{anchor_name}.authoritative must be true")
    if not _as_text(target_project.get("anchor_summary")):
        errors.append("situational_analysis.target_project.anchor_summary is required")

    for section_name, allowed_statuses in (
        ("planning_state", REQ_026_ALLOWED_PLANNING_STATUSES),
        ("runtime_state", REQ_026_ALLOWED_RUNTIME_STATUSES),
    ):
        section = situational_analysis.get(section_name)
        if not isinstance(section, Mapping):
            errors.append(f"situational_analysis.{section_name} must be an object")
            continue
        status = _as_text(section.get("status"))
        if status not in allowed_statuses:
            errors.append(f"situational_analysis.{section_name}.status must be one of {sorted(allowed_statuses)}")
        for key in ("artifact_ids", "evidence_refs", "key_signals"):
            value = section.get(key)
            if not isinstance(value, list) or not value or any(not _as_text(item) for item in value):
                errors.append(f"situational_analysis.{section_name}.{key} must be a non-empty string array")

    reasoning = situational_analysis.get("reasoning")
    if not isinstance(reasoning, Mapping):
        errors.append("situational_analysis.reasoning must be an object")
        reasoning = {}
    if _as_text(reasoning.get("assessment_status")) not in {"grounded", "needs-follow-up", "blocked"}:
        errors.append("situational_analysis.reasoning.assessment_status must be grounded, needs-follow-up, or blocked")
    if reasoning.get("anchor_set") != ["mission", "scope", "planning_evidence", "runtime_evidence"]:
        errors.append("situational_analysis.reasoning.anchor_set must match the canonical anchor set")
    if not _as_text(reasoning.get("state_summary")):
        errors.append("situational_analysis.reasoning.state_summary is required")
    evidence_basis = reasoning.get("evidence_basis")
    if not isinstance(evidence_basis, list) or not evidence_basis or any(not _as_text(item) for item in evidence_basis):
        errors.append("situational_analysis.reasoning.evidence_basis must be a non-empty string array")
    if reasoning.get("follow_up_required") is not True:
        errors.append("situational_analysis.reasoning.follow_up_required must be true")

    processing_behavior = payload.get("processing_behavior")
    if not isinstance(processing_behavior, Mapping):
        errors.append("processing_behavior must be an object")
        processing_behavior = {}
    if processing_behavior.get("strategy") != REQ_026_PROCESSING_STRATEGY:
        errors.append(f"processing_behavior.strategy must be {REQ_026_PROCESSING_STRATEGY}")
    if processing_behavior.get("reasoning_mode") != REQ_026_REASONING_MODE:
        errors.append(f"processing_behavior.reasoning_mode must be {REQ_026_REASONING_MODE}")
    if processing_behavior.get("strict_evidence_discipline") is not True:
        errors.append("processing_behavior.strict_evidence_discipline must be true")

    context_inputs = processing_behavior.get("context_inputs")
    if not isinstance(context_inputs, Mapping):
        errors.append("processing_behavior.context_inputs must be an object")
        context_inputs = {}
    broad_sweep_context = context_inputs.get("broad_sweep_context")
    if not isinstance(broad_sweep_context, Mapping):
        errors.append("processing_behavior.context_inputs.broad_sweep_context must be an object")
        broad_sweep_context = {}
    for key in ("earth_sweep_evidence_refs", "cross_project_context", "candidate_recommendations", "strategic_claims"):
        if not isinstance(broad_sweep_context.get(key), list):
            errors.append(f"processing_behavior.context_inputs.broad_sweep_context.{key} must be an array")
    strategic_claims = broad_sweep_context.get("strategic_claims", [])
    if isinstance(strategic_claims, list):
        for index, row in enumerate(strategic_claims):
            if not isinstance(row, Mapping):
                errors.append(
                    f"processing_behavior.context_inputs.broad_sweep_context.strategic_claims[{index}] must be an object"
                )
                continue
            if not _as_text(row.get("claim_id")):
                errors.append(
                    f"processing_behavior.context_inputs.broad_sweep_context.strategic_claims[{index}].claim_id is required"
                )
            if _as_text(row.get("phase")) not in REQ_026_ALLOWED_CLAIM_PHASES:
                errors.append(
                    f"processing_behavior.context_inputs.broad_sweep_context.strategic_claims[{index}].phase "
                    f"must be one of {sorted(REQ_026_ALLOWED_CLAIM_PHASES)}"
                )
            if not _as_text(row.get("summary")):
                errors.append(
                    f"processing_behavior.context_inputs.broad_sweep_context.strategic_claims[{index}].summary is required"
                )
            if not _as_text(row.get("position")):
                errors.append(
                    f"processing_behavior.context_inputs.broad_sweep_context.strategic_claims[{index}].position is required"
                )
            source_call_sequence = row.get("source_call_sequence")
            if isinstance(source_call_sequence, bool) or not isinstance(source_call_sequence, int) or source_call_sequence < 1:
                errors.append(
                    "processing_behavior.context_inputs.broad_sweep_context.strategic_claims"
                    f"[{index}].source_call_sequence must be an integer >= 1"
                )
            evidence_refs = row.get("evidence_refs")
            if not isinstance(evidence_refs, list) or any(not _as_text(item) for item in evidence_refs):
                errors.append(
                    "processing_behavior.context_inputs.broad_sweep_context.strategic_claims"
                    f"[{index}].evidence_refs must be a string array"
                )

    context_usage = processing_behavior.get("context_usage")
    if not isinstance(context_usage, Mapping):
        errors.append("processing_behavior.context_usage must be an object")
        context_usage = {}
    for key in ("broad_sweep_context_used", "earth_sweep_context_used", "cross_project_context_used"):
        if not isinstance(context_usage.get(key), bool):
            errors.append(f"processing_behavior.context_usage.{key} must be a boolean")
    for key in (
        "earth_sweep_evidence_refs_used",
        "cross_project_projects_considered",
        "cross_project_projects_with_evidence_refs",
        "cross_project_projects_without_evidence_refs",
        "candidate_recommendation_ids_considered",
        "local_recommendation_ids_emitted",
        "cross_project_obligation_ids_emitted",
        "open_risk_ids_emitted",
        "unknown_ids_for_later_calls",
    ):
        value = context_usage.get(key)
        if not isinstance(value, list) or any(not _as_text(item) for item in value):
            errors.append(f"processing_behavior.context_usage.{key} must be a string array")

    recommendation = processing_behavior.get("recommendation")
    if not isinstance(recommendation, Mapping):
        errors.append("processing_behavior.recommendation must be an object")
        recommendation = {}
    if _as_text(recommendation.get("decision")) not in {
        "proceed",
        "proceed-with-caution",
        "proceed-with-open-risks",
        "hold",
    }:
        errors.append(
            "processing_behavior.recommendation.decision must be proceed, proceed-with-caution, "
            "proceed-with-open-risks, or hold"
        )
    if not _as_text(recommendation.get("rationale")):
        errors.append("processing_behavior.recommendation.rationale is required")
    if _as_text(recommendation.get("confidence")) not in {"high", "medium", "low"}:
        errors.append("processing_behavior.recommendation.confidence must be high, medium, or low")
    recommendation_refs = recommendation.get("evidence_refs")
    if not isinstance(recommendation_refs, list) or not recommendation_refs or any(not _as_text(item) for item in recommendation_refs):
        errors.append("processing_behavior.recommendation.evidence_refs must be a non-empty string array")

    unknowns = payload.get("unknowns")
    if not isinstance(unknowns, list) or not unknowns:
        errors.append("unknowns must be a non-empty array")
        unknowns = []
    seen_unknown_ids: set[str] = set()
    for index, row in enumerate(unknowns):
        if not isinstance(row, Mapping):
            errors.append(f"unknowns[{index}] must be an object")
            continue
        unknown_id = _as_text(row.get("unknown_id"))
        if not unknown_id:
            errors.append(f"unknowns[{index}].unknown_id is required")
        elif unknown_id in seen_unknown_ids:
            errors.append(f"unknowns[{index}].unknown_id duplicates {unknown_id}")
        else:
            seen_unknown_ids.add(unknown_id)
        if _as_text(row.get("category")) not in {"planning", "runtime"}:
            errors.append(f"unknowns[{index}].category must be planning or runtime")
        if not _as_text(row.get("question")):
            errors.append(f"unknowns[{index}].question is required")
        if not _as_text(row.get("why_it_matters")):
            errors.append(f"unknowns[{index}].why_it_matters is required")
        if row.get("must_be_resolved_by") != "call-2":
            errors.append(f"unknowns[{index}].must_be_resolved_by must be call-2")
        provenance = row.get("provenance")
        if not isinstance(provenance, Mapping):
            errors.append(f"unknowns[{index}].provenance must be an object")
            continue
        if _as_text(provenance.get("evidence_type")) not in {"planning", "runtime"}:
            errors.append(f"unknowns[{index}].provenance.evidence_type must be planning or runtime")
        if not _as_text(provenance.get("artifact_id")):
            errors.append(f"unknowns[{index}].provenance.artifact_id is required")
        if not _as_text(provenance.get("source_ref")):
            errors.append(f"unknowns[{index}].provenance.source_ref is required")

    source = payload.get("source")
    if not isinstance(source, Mapping):
        errors.append("source must be an object")
        source = {}
    for key in ("planning_artifact_count", "runtime_artifact_count"):
        value = source.get(key)
        if not isinstance(value, int) or value <= 0:
            errors.append(f"source.{key} must be a positive integer")
    for key in (
        "earth_sweep_evidence_count",
        "cross_project_context_count",
        "candidate_recommendation_count",
    ):
        value = source.get(key)
        if not isinstance(value, int) or value < 0:
            errors.append(f"source.{key} must be a non-negative integer")
    if not _as_text(source.get("mission_source")):
        errors.append("source.mission_source is required")
    if not _as_text(source.get("scope_source")):
        errors.append("source.scope_source is required")

    metadata = payload.get("call_metadata")
    if metadata is not None:
        if not isinstance(metadata, Mapping):
            errors.append("call_metadata must be an object")
        else:
            if metadata.get("reproducibility") != "deterministic-input-fingerprint":
                errors.append("call_metadata.reproducibility must be deterministic-input-fingerprint")
            if metadata.get("llm_call_trace_schema_version") != REQ_026_LLM_CALL_TRACE_SCHEMA_VERSION:
                errors.append(
                    f"call_metadata.llm_call_trace_schema_version must be {REQ_026_LLM_CALL_TRACE_SCHEMA_VERSION}"
                )
            if metadata.get("llm_call_trace_path") != LLM_CALL_TRACE_RELATIVE_PATH:
                errors.append(f"call_metadata.llm_call_trace_path must be {LLM_CALL_TRACE_RELATIVE_PATH}")
            rows = metadata.get("llm_call_trace_rows")
            if not isinstance(rows, list) or len(rows) != 1:
                errors.append("call_metadata.llm_call_trace_rows must contain exactly one row")
            else:
                row = rows[0]
                if not isinstance(row, Mapping):
                    errors.append("call_metadata.llm_call_trace_rows[0] must be an object")
                else:
                    if not _as_text(row.get("call_objective")):
                        errors.append("call_metadata.llm_call_trace_rows[0].call_objective is required")
                    for key in ("input_refs", "output_refs"):
                        value = row.get(key)
                        if not isinstance(value, list) or not value or any(not _as_text(item) for item in value):
                            errors.append(
                                f"call_metadata.llm_call_trace_rows[0].{key} must be a non-empty string array"
                            )
                    if not _as_text(row.get("handoff_summary")):
                        errors.append("call_metadata.llm_call_trace_rows[0].handoff_summary is required")

    return errors


def _req_029_build_recommendation_id(*, source_call_id: str, candidate_id: str) -> str:
    return f"rec-call-4-{source_call_id}-{candidate_id}"


def _req_029_normalize_candidate_recommendations(
    value: Any,
    *,
    field_name: str,
    source_call_id: str,
    source_output_ref: str,
) -> list[dict[str, Any]]:
    if value is None:
        raise Req029Error(f"{field_name} must be a non-empty array")
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise Req029Error(f"{field_name} must be a non-empty array")

    normalized: list[dict[str, Any]] = []
    seen_candidate_ids: set[str] = set()
    for index, raw_row in enumerate(value):
        row = _require_mapping(raw_row, field_name=f"{field_name}[{index}]")
        candidate_id = _require_text(row.get("candidate_id"), field_name=f"{field_name}[{index}].candidate_id").lower()
        if not _matches_slug_schema(candidate_id):
            raise Req029Error(f"{field_name}[{index}].candidate_id must match [a-z0-9-] slug schema")
        if candidate_id in seen_candidate_ids:
            raise Req029Error(f"{field_name}[{index}].candidate_id must be unique within {source_call_id}")
        seen_candidate_ids.add(candidate_id)
        recommendation_scope = _as_text(row.get("recommendation_scope")).lower() or "local"
        if recommendation_scope not in REQ_029_ALLOWED_RECOMMENDATION_SCOPES:
            raise Req029Error(
                f"{field_name}[{index}].recommendation_scope must be one of "
                f"{sorted(REQ_029_ALLOWED_RECOMMENDATION_SCOPES)}"
            )
        project_id = _as_text(row.get("project_id"))
        if recommendation_scope == "cross-project":
            project_id = _require_text(project_id, field_name=f"{field_name}[{index}].project_id")
        else:
            project_id = ""
        requires_earth_evidence = row.get("requires_earth_evidence")
        if requires_earth_evidence is None:
            requires_earth_evidence = recommendation_scope == "cross-project"
        if not isinstance(requires_earth_evidence, bool):
            raise Req029Error(f"{field_name}[{index}].requires_earth_evidence must be a boolean")
        normalized.append(
            {
                "recommendation_id": _req_029_build_recommendation_id(
                    source_call_id=source_call_id,
                    candidate_id=candidate_id,
                ),
                "source_call_id": source_call_id,
                "source_output_ref": source_output_ref,
                "source_candidate_id": candidate_id,
                "summary": _require_text(row.get("summary"), field_name=f"{field_name}[{index}].summary"),
                "rationale": _require_text(row.get("rationale"), field_name=f"{field_name}[{index}].rationale"),
                "impact": _require_text(row.get("impact"), field_name=f"{field_name}[{index}].impact"),
                "risk": _require_text(row.get("risk"), field_name=f"{field_name}[{index}].risk"),
                "recommendation_scope": recommendation_scope,
                "project_id": project_id,
                "requires_earth_evidence": requires_earth_evidence,
                "evidence_refs": _normalize_string_list(
                    row.get("evidence_refs"),
                    field_name=f"{field_name}[{index}].evidence_refs",
                    min_items=1,
                ),
            }
        )
    if not normalized:
        raise Req029Error(f"{field_name} must contain at least 1 item(s)")
    normalized.sort(key=lambda row: row["recommendation_id"])
    return normalized


def _req_029_normalize_earlier_call_outputs(
    value: Any,
    *,
    field_name: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if value is None:
        raise Req029Error(f"{field_name} must be a non-empty array")
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise Req029Error(f"{field_name} must be a non-empty array")

    normalized_outputs: list[dict[str, Any]] = []
    recommendation_drafts: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    seen_call_ids: set[str] = set()
    seen_recommendation_ids: set[str] = set()
    for index, raw_row in enumerate(value):
        row = _require_mapping(raw_row, field_name=f"{field_name}[{index}]")
        source_call_id = _require_text(row.get("call_id"), field_name=f"{field_name}[{index}].call_id").lower()
        if source_call_id not in REQ_029_ALLOWED_SOURCE_CALL_IDS:
            raise Req029Error(
                f"{field_name}[{index}].call_id must be one of {list(REQ_029_ALLOWED_SOURCE_CALL_IDS)}"
            )
        if source_call_id in seen_call_ids:
            raise Req029Error(f"{field_name}[{index}].call_id must be unique")
        seen_call_ids.add(source_call_id)

        source_output_ref = _require_text(
            row.get("output_ref"),
            field_name=f"{field_name}[{index}].output_ref",
        )
        candidate_recommendations = _req_029_normalize_candidate_recommendations(
            row.get("candidate_recommendations"),
            field_name=f"{field_name}[{index}].candidate_recommendations",
            source_call_id=source_call_id,
            source_output_ref=source_output_ref,
        )
        for draft in candidate_recommendations:
            recommendation_id = str(draft["recommendation_id"])
            if draft["recommendation_scope"] == "cross-project" and draft["requires_earth_evidence"]:
                earth_evidence_refs = [ref for ref in draft["evidence_refs"] if _is_earth_evidence_ref(ref)]
                if not earth_evidence_refs:
                    open_risks.append(
                        {
                            "risk_id": f"risk-{recommendation_id}",
                            "source_call_id": draft["source_call_id"],
                            "source_output_ref": draft["source_output_ref"],
                            "source_candidate_id": draft["source_candidate_id"],
                            "project_id": draft["project_id"],
                            "summary": draft["summary"],
                            "reason_code": "missing_earth_sweep_evidence_refs",
                            "required_evidence_refs": list(draft["evidence_refs"]),
                        }
                    )
                    continue
            if recommendation_id in seen_recommendation_ids:
                raise Req029Error(f"{field_name}[{index}] produces duplicate recommendation_id {recommendation_id}")
            seen_recommendation_ids.add(recommendation_id)
            recommendation_drafts.append(
                {
                    "recommendation_id": recommendation_id,
                    "source_call_id": draft["source_call_id"],
                    "source_output_ref": draft["source_output_ref"],
                    "source_candidate_id": draft["source_candidate_id"],
                    "summary": draft["summary"],
                    "rationale": draft["rationale"],
                    "impact": draft["impact"],
                    "risk": draft["risk"],
                    "evidence_refs": list(draft["evidence_refs"]),
                }
            )
        normalized_outputs.append(
            {
                "call_id": source_call_id,
                "output_ref": source_output_ref,
                "summary": _require_text(row.get("summary"), field_name=f"{field_name}[{index}].summary"),
                "candidate_recommendations": candidate_recommendations,
            }
        )

    if not normalized_outputs:
        raise Req029Error(f"{field_name} must contain at least 1 item(s)")
    expected_call_ids = set(REQ_029_ALLOWED_SOURCE_CALL_IDS)
    if seen_call_ids != expected_call_ids:
        raise Req029Error(
            f"{field_name} must include exactly {list(REQ_029_ALLOWED_SOURCE_CALL_IDS)} so the Call-4 trace can emit one row per LLM call"
        )
    normalized_outputs.sort(key=lambda row: row["call_id"])
    recommendation_drafts.sort(key=lambda row: row["recommendation_id"])
    open_risks.sort(key=lambda row: row["risk_id"])
    return normalized_outputs, recommendation_drafts, open_risks


def _req_029_canonical_input(
    *,
    project_id: str,
    earlier_call_outputs: Sequence[Mapping[str, Any]],
    checked_at_utc: str,
) -> dict[str, Any]:
    return {
        "requirement_id": REQ_029_REQUIREMENT_ID,
        "analysis_type": REQ_029_ANALYSIS_TYPE,
        "call_id": REQ_029_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "target_project": {
            "project_id": project_id,
        },
        "earlier_call_outputs": [
            {
                "call_id": row["call_id"],
                "output_ref": row["output_ref"],
                "summary": row["summary"],
                "candidate_recommendations": [
                    {
                        "recommendation_id": draft["recommendation_id"],
                        "source_candidate_id": draft["source_candidate_id"],
                        "summary": draft["summary"],
                        "rationale": draft["rationale"],
                        "impact": draft["impact"],
                        "risk": draft["risk"],
                        "recommendation_scope": draft["recommendation_scope"],
                        "project_id": draft["project_id"],
                        "requires_earth_evidence": draft["requires_earth_evidence"],
                        "evidence_refs": list(draft["evidence_refs"]),
                    }
                    for draft in row["candidate_recommendations"]
                ],
            }
            for row in earlier_call_outputs
        ],
    }


def _req_029_trace_output_ref() -> str:
    return f"{REQ_029_REQUIREMENT_ID}::call::{REQ_029_CALL_ID}::output::recommendation_synthesis"


def _req_029_trace_output_name(output_ref: str) -> str:
    _, _, output_name = output_ref.rpartition("::output::")
    return output_name or output_ref


def _req_029_trace_handoff_summary(
    *,
    sequence: int,
    output_name: str,
    output_ref: str,
    input_ref_count: int,
    next_call_id: str,
    recommendation_draft_count: int = 0,
    open_risk_count: int = 0,
) -> str:
    if next_call_id:
        return (
            f"Call {sequence} hands off {output_name} via {output_ref} to {next_call_id} "
            f"after consuming {input_ref_count} input refs."
        )
    return (
        f"Call {sequence} hands off {output_name} via {output_ref} as the terminal recommendation synthesis output "
        f"with {recommendation_draft_count} draft(s) and {open_risk_count} open risk(s)."
    )


def _build_req_029_llm_call_trace_rows(
    *,
    processing_call_id: str,
    earlier_call_outputs: Sequence[Mapping[str, Any]],
    recommendation_drafts: Sequence[Mapping[str, Any]],
    open_risks: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    outputs_by_call_id = {str(row["call_id"]): row for row in earlier_call_outputs}
    trace_rows: list[dict[str, Any]] = []
    previous_output_ref = ""

    for sequence, call_id in enumerate(REQ_029_ALLOWED_SOURCE_CALL_IDS, start=1):
        row = outputs_by_call_id[call_id]
        evidence_refs = _req_026_dedupe_preserving_order(
            [ref for candidate in row.get("candidate_recommendations", []) for ref in candidate.get("evidence_refs", [])]
        )
        input_refs = _req_026_dedupe_preserving_order(([previous_output_ref] if previous_output_ref else []) + evidence_refs)
        output_ref = _require_text(row.get("output_ref"), field_name=f"earlier_call_outputs[{call_id}].output_ref")
        next_call_id = REQ_029_ALLOWED_SOURCE_CALL_IDS[sequence] if sequence < len(REQ_029_ALLOWED_SOURCE_CALL_IDS) else REQ_029_CALL_ID
        trace_rows.append(
            {
                "schema_version": REQ_029_LLM_CALL_TRACE_SCHEMA_VERSION,
                "requirement_id": REQ_029_REQUIREMENT_ID,
                "processing_call_id": processing_call_id,
                "call_id": call_id,
                "sequence": sequence,
                "call_objective": REQ_029_CALL_OBJECTIVES[call_id],
                "input_refs": input_refs,
                "output_refs": [output_ref],
                "handoff_summary": _req_029_trace_handoff_summary(
                    sequence=sequence,
                    output_name=_req_029_trace_output_name(output_ref),
                    output_ref=output_ref,
                    input_ref_count=len(input_refs),
                    next_call_id=next_call_id,
                ),
            }
        )
        previous_output_ref = output_ref

    terminal_output_ref = _req_029_trace_output_ref()
    terminal_input_refs = _req_026_dedupe_preserving_order(
        [str(row["output_ref"]) for row in earlier_call_outputs]
        + [ref for row in recommendation_drafts for ref in row.get("evidence_refs", [])]
        + [ref for row in open_risks for ref in row.get("required_evidence_refs", [])]
    )
    trace_rows.append(
        {
            "schema_version": REQ_029_LLM_CALL_TRACE_SCHEMA_VERSION,
            "requirement_id": REQ_029_REQUIREMENT_ID,
            "processing_call_id": processing_call_id,
            "call_id": REQ_029_CALL_ID,
            "sequence": 4,
            "call_objective": REQ_029_CALL_OBJECTIVES[REQ_029_CALL_ID],
            "input_refs": terminal_input_refs,
            "output_refs": [terminal_output_ref],
            "handoff_summary": _req_029_trace_handoff_summary(
                sequence=4,
                output_name=_req_029_trace_output_name(terminal_output_ref),
                output_ref=terminal_output_ref,
                input_ref_count=len(terminal_input_refs),
                next_call_id="",
                recommendation_draft_count=len(recommendation_drafts),
                open_risk_count=len(open_risks),
            ),
        }
    )
    return trace_rows


def build_req_029_call_4_recommendation_synthesis(
    *,
    target_project: Mapping[str, Any],
    earlier_call_outputs: Sequence[Mapping[str, Any]],
    analysis_type: str = REQ_029_ANALYSIS_TYPE,
    call_id: str = REQ_029_CALL_ID,
    checked_at_utc: str | None = None,
) -> dict[str, Any]:
    if analysis_type != REQ_029_ANALYSIS_TYPE:
        raise Req029Error(f"analysis_type must be {REQ_029_ANALYSIS_TYPE}")
    if call_id != REQ_029_CALL_ID:
        raise Req029Error(f"call_id must be {REQ_029_CALL_ID}")

    project = _require_mapping(target_project, field_name="target_project")
    project_id = _require_text(project.get("project_id"), field_name="target_project.project_id")
    normalized_checked_at_utc = _require_text(checked_at_utc or utc_now_iso(), field_name="checked_at_utc")
    normalized_outputs, recommendation_drafts, open_risks = _req_029_normalize_earlier_call_outputs(
        earlier_call_outputs,
        field_name="earlier_call_outputs",
    )
    canonical_input = _req_029_canonical_input(
        project_id=project_id,
        earlier_call_outputs=normalized_outputs,
        checked_at_utc=normalized_checked_at_utc,
    )
    canonical_input_sha = _canonical_digest(canonical_input)
    processing_call_id = f"req029-processing-{canonical_input_sha[:16]}"
    llm_call_trace_rows = _build_req_029_llm_call_trace_rows(
        processing_call_id=processing_call_id,
        earlier_call_outputs=normalized_outputs,
        recommendation_drafts=recommendation_drafts,
        open_risks=open_risks,
    )
    llm_call_trace_sha = _canonical_digest(llm_call_trace_rows)
    unique_evidence_refs = _collect_unique_refs(
        [ref for draft in recommendation_drafts for ref in draft["evidence_refs"]],
        [ref for row in open_risks for ref in row["required_evidence_refs"]],
    )
    earth_sweep_evidence_refs_used = [ref for ref in unique_evidence_refs if _is_earth_evidence_ref(ref)]
    target_project_evidence_refs_used = [ref for ref in unique_evidence_refs if not _is_earth_evidence_ref(ref)]
    cross_project_project_ids_used = sorted(
        {
            str(candidate["project_id"])
            for output in normalized_outputs
            for candidate in output["candidate_recommendations"]
            if candidate["recommendation_scope"] == "cross-project" and _as_text(candidate["project_id"])
        }
    )

    return {
        "ok": True,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "schema_version": REQ_029_SCHEMA_VERSION,
        "requirement_id": REQ_029_REQUIREMENT_ID,
        "analysis_type": REQ_029_ANALYSIS_TYPE,
        "call_id": REQ_029_CALL_ID,
        "checked_at_utc": normalized_checked_at_utc,
        "recommendation_synthesis": {
            "target_project": {
                "project_id": project_id,
            },
            "source_calls": [row["call_id"] for row in normalized_outputs],
            "recommendation_drafts": recommendation_drafts,
            "open_risks": open_risks,
            "summary": {
                "source_call_count": len(normalized_outputs),
                "candidate_recommendation_count": len(recommendation_drafts) + len(open_risks),
                "draft_count": len(recommendation_drafts),
                "open_risk_count": len(open_risks),
            },
        },
        "processing_behavior": {
            "strategy": REQ_029_PROCESSING_STRATEGY,
            "reasoning_mode": REQ_029_REASONING_MODE,
            "strict_evidence_discipline": True,
            "context_inputs": {
                "earlier_call_outputs": normalized_outputs,
            },
            "context_usage": {
                "earlier_call_outputs_used": bool(normalized_outputs),
                "source_call_ids_used": [row["call_id"] for row in normalized_outputs],
                "source_output_refs_used": [row["output_ref"] for row in normalized_outputs],
                "cross_project_context_used": bool(cross_project_project_ids_used),
                "cross_project_project_ids_used": cross_project_project_ids_used,
                "earth_sweep_evidence_refs_used": earth_sweep_evidence_refs_used,
                "target_project_evidence_refs_used": target_project_evidence_refs_used,
                "evidence_refs_used": unique_evidence_refs,
                "recommendation_ids_emitted": [
                    row["recommendation_id"] for row in recommendation_drafts
                ],
                "open_risk_ids_emitted": [row["risk_id"] for row in open_risks],
            },
            "synthesis_rules": {
                "recommendation_id_schema": REQ_029_RECOMMENDATION_ID_SCHEMA,
                "required_draft_fields": list(REQ_029_REQUIRED_DRAFT_FIELDS),
                "allowed_source_call_ids": list(REQ_029_ALLOWED_SOURCE_CALL_IDS),
            },
        },
        "source": {
            "earlier_call_output_count": len(normalized_outputs),
            "candidate_recommendation_count": len(recommendation_drafts) + len(open_risks),
            "draft_count": len(recommendation_drafts),
            "open_risk_count": len(open_risks),
            "evidence_ref_count": len(unique_evidence_refs),
        },
        "call_metadata": {
            "reproducibility": "deterministic-input-fingerprint",
            "canonical_input_sha256": canonical_input_sha,
            "reproducible_call_id": f"req029-{canonical_input_sha[:16]}",
            "canonical_input": canonical_input,
            "processing_call_id": processing_call_id,
            "llm_call_trace_schema_version": REQ_029_LLM_CALL_TRACE_SCHEMA_VERSION,
            "llm_call_trace_path": LLM_CALL_TRACE_RELATIVE_PATH,
            "llm_call_trace_sha256": llm_call_trace_sha,
            "llm_call_trace_rows": llm_call_trace_rows,
        },
    }


def validate_req_029_call_4_recommendation_synthesis(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []

    if payload.get("ok") is not True:
        errors.append("ok must be true")
    if payload.get("tool") != TOOL:
        errors.append(f"tool must be {TOOL}")
    if payload.get("tool_version") != TOOL_VERSION:
        errors.append(f"tool_version must be {TOOL_VERSION}")
    if payload.get("schema_version") != REQ_029_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_029_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_029_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_029_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_029_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_029_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_029_CALL_ID:
        errors.append(f"call_id must be {REQ_029_CALL_ID}")
    if not _as_text(payload.get("checked_at_utc")):
        errors.append("checked_at_utc is required")

    recommendation_synthesis = payload.get("recommendation_synthesis")
    if not isinstance(recommendation_synthesis, Mapping):
        errors.append("recommendation_synthesis must be an object")
        recommendation_synthesis = {}

    target_project = recommendation_synthesis.get("target_project")
    if not isinstance(target_project, Mapping):
        errors.append("recommendation_synthesis.target_project must be an object")
    elif not _as_text(target_project.get("project_id")):
        errors.append("recommendation_synthesis.target_project.project_id is required")

    source_calls = recommendation_synthesis.get("source_calls")
    if not isinstance(source_calls, list) or not source_calls or any(not _as_text(item) for item in source_calls):
        errors.append("recommendation_synthesis.source_calls must be a non-empty string array")
        source_calls = []

    recommendation_drafts = recommendation_synthesis.get("recommendation_drafts")
    if not isinstance(recommendation_drafts, list) or not recommendation_drafts:
        errors.append("recommendation_synthesis.recommendation_drafts must be a non-empty array")
        recommendation_drafts = []
    seen_recommendation_ids: set[str] = set()
    for index, raw_row in enumerate(recommendation_drafts):
        if not isinstance(raw_row, Mapping):
            errors.append(f"recommendation_synthesis.recommendation_drafts[{index}] must be an object")
            continue
        recommendation_id = _as_text(raw_row.get("recommendation_id"))
        if not recommendation_id:
            errors.append(f"recommendation_synthesis.recommendation_drafts[{index}].recommendation_id is required")
        elif recommendation_id in seen_recommendation_ids:
            errors.append(
                f"recommendation_synthesis.recommendation_drafts[{index}].recommendation_id duplicates {recommendation_id}"
            )
        else:
            seen_recommendation_ids.add(recommendation_id)
        source_call_id = _as_text(raw_row.get("source_call_id"))
        if source_call_id not in REQ_029_ALLOWED_SOURCE_CALL_IDS:
            errors.append(
                f"recommendation_synthesis.recommendation_drafts[{index}].source_call_id must be one of "
                f"{list(REQ_029_ALLOWED_SOURCE_CALL_IDS)}"
            )
        source_candidate_id = _as_text(raw_row.get("source_candidate_id"))
        if not source_candidate_id:
            errors.append(
                f"recommendation_synthesis.recommendation_drafts[{index}].source_candidate_id is required"
            )
        elif not _matches_slug_schema(source_candidate_id):
            errors.append(
                "recommendation_synthesis.recommendation_drafts"
                f"[{index}].source_candidate_id must match [a-z0-9-] slug schema"
            )
        expected_recommendation_id = (
            _req_029_build_recommendation_id(
                source_call_id=source_call_id,
                candidate_id=source_candidate_id,
            )
            if source_call_id in REQ_029_ALLOWED_SOURCE_CALL_IDS and source_candidate_id
            else ""
        )
        if expected_recommendation_id and recommendation_id != expected_recommendation_id:
            errors.append(
                f"recommendation_synthesis.recommendation_drafts[{index}].recommendation_id must equal "
                f"{expected_recommendation_id}"
            )
        if not _as_text(raw_row.get("source_output_ref")):
            errors.append(f"recommendation_synthesis.recommendation_drafts[{index}].source_output_ref is required")
        for key in ("summary", "rationale", "impact", "risk"):
            if not _as_text(raw_row.get(key)):
                errors.append(f"recommendation_synthesis.recommendation_drafts[{index}].{key} is required")
        evidence_refs = raw_row.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not evidence_refs or any(not _as_text(item) for item in evidence_refs):
            errors.append(
                f"recommendation_synthesis.recommendation_drafts[{index}].evidence_refs must be a non-empty string array"
            )

    open_risks = recommendation_synthesis.get("open_risks")
    if not isinstance(open_risks, list):
        errors.append("recommendation_synthesis.open_risks must be an array")
        open_risks = []
    seen_risk_ids: set[str] = set()
    for index, raw_row in enumerate(open_risks):
        if not isinstance(raw_row, Mapping):
            errors.append(f"recommendation_synthesis.open_risks[{index}] must be an object")
            continue
        risk_id = _as_text(raw_row.get("risk_id"))
        if not risk_id:
            errors.append(f"recommendation_synthesis.open_risks[{index}].risk_id is required")
        elif risk_id in seen_risk_ids:
            errors.append(f"recommendation_synthesis.open_risks[{index}].risk_id duplicates {risk_id}")
        else:
            seen_risk_ids.add(risk_id)
        if _as_text(raw_row.get("reason_code")) != "missing_earth_sweep_evidence_refs":
            errors.append(
                "recommendation_synthesis.open_risks"
                f"[{index}].reason_code must be missing_earth_sweep_evidence_refs"
            )
        for key in ("source_call_id", "source_output_ref", "source_candidate_id", "project_id", "summary"):
            if not _as_text(raw_row.get(key)):
                errors.append(f"recommendation_synthesis.open_risks[{index}].{key} is required")
        required_evidence_refs = raw_row.get("required_evidence_refs")
        if (
            not isinstance(required_evidence_refs, list)
            or not required_evidence_refs
            or any(not _as_text(item) for item in required_evidence_refs)
        ):
            errors.append(
                "recommendation_synthesis.open_risks"
                f"[{index}].required_evidence_refs must be a non-empty string array"
            )

    summary = recommendation_synthesis.get("summary")
    if not isinstance(summary, Mapping):
        errors.append("recommendation_synthesis.summary must be an object")
    else:
        expected_counts = {
            "source_call_count": len(source_calls),
            "candidate_recommendation_count": len(recommendation_drafts) + len(open_risks),
            "draft_count": len(recommendation_drafts),
            "open_risk_count": len(open_risks),
        }
        for key, expected_value in expected_counts.items():
            actual_value = summary.get(key)
            if actual_value != expected_value:
                errors.append(f"recommendation_synthesis.summary.{key} must equal {expected_value}")

    processing_behavior = payload.get("processing_behavior")
    if not isinstance(processing_behavior, Mapping):
        errors.append("processing_behavior must be an object")
        processing_behavior = {}
    if processing_behavior.get("strategy") != REQ_029_PROCESSING_STRATEGY:
        errors.append(f"processing_behavior.strategy must be {REQ_029_PROCESSING_STRATEGY}")
    if processing_behavior.get("reasoning_mode") != REQ_029_REASONING_MODE:
        errors.append(f"processing_behavior.reasoning_mode must be {REQ_029_REASONING_MODE}")
    if processing_behavior.get("strict_evidence_discipline") is not True:
        errors.append("processing_behavior.strict_evidence_discipline must be true")

    context_inputs = processing_behavior.get("context_inputs")
    if not isinstance(context_inputs, Mapping):
        errors.append("processing_behavior.context_inputs must be an object")
        context_inputs = {}
    earlier_call_outputs = context_inputs.get("earlier_call_outputs")
    if not isinstance(earlier_call_outputs, list) or not earlier_call_outputs:
        errors.append("processing_behavior.context_inputs.earlier_call_outputs must be a non-empty array")
        earlier_call_outputs = []
    seen_context_call_ids: set[str] = set()
    for index, raw_row in enumerate(earlier_call_outputs):
        if not isinstance(raw_row, Mapping):
            errors.append(f"processing_behavior.context_inputs.earlier_call_outputs[{index}] must be an object")
            continue
        call_id = _as_text(raw_row.get("call_id"))
        if call_id not in REQ_029_ALLOWED_SOURCE_CALL_IDS:
            errors.append(
                f"processing_behavior.context_inputs.earlier_call_outputs[{index}].call_id must be one of "
                f"{list(REQ_029_ALLOWED_SOURCE_CALL_IDS)}"
            )
        elif call_id in seen_context_call_ids:
            errors.append(f"processing_behavior.context_inputs.earlier_call_outputs[{index}].call_id must be unique")
        else:
            seen_context_call_ids.add(call_id)
        for key in ("output_ref", "summary"):
            if not _as_text(raw_row.get(key)):
                errors.append(f"processing_behavior.context_inputs.earlier_call_outputs[{index}].{key} is required")
        candidates = raw_row.get("candidate_recommendations")
        if not isinstance(candidates, list) or not candidates:
            errors.append(
                f"processing_behavior.context_inputs.earlier_call_outputs[{index}].candidate_recommendations "
                "must be a non-empty array"
            )

    context_usage = processing_behavior.get("context_usage")
    if not isinstance(context_usage, Mapping):
        errors.append("processing_behavior.context_usage must be an object")
        context_usage = {}
    else:
        if not isinstance(context_usage.get("earlier_call_outputs_used"), bool):
            errors.append("processing_behavior.context_usage.earlier_call_outputs_used must be a boolean")
        if not isinstance(context_usage.get("cross_project_context_used"), bool):
            errors.append("processing_behavior.context_usage.cross_project_context_used must be a boolean")
        for key in (
            "source_call_ids_used",
            "source_output_refs_used",
            "cross_project_project_ids_used",
            "earth_sweep_evidence_refs_used",
            "target_project_evidence_refs_used",
            "evidence_refs_used",
            "recommendation_ids_emitted",
            "open_risk_ids_emitted",
        ):
            value = context_usage.get(key)
            if not isinstance(value, list) or any(not _as_text(item) for item in value):
                errors.append(f"processing_behavior.context_usage.{key} must be a string array")
        if context_usage.get("source_call_ids_used") != source_calls:
            errors.append("processing_behavior.context_usage.source_call_ids_used must match source_calls")
        if context_usage.get("recommendation_ids_emitted") != [
            row.get("recommendation_id") for row in recommendation_drafts if isinstance(row, Mapping)
        ]:
            errors.append("processing_behavior.context_usage.recommendation_ids_emitted must match recommendation_drafts")
        if context_usage.get("open_risk_ids_emitted") != [
            row.get("risk_id") for row in open_risks if isinstance(row, Mapping)
        ]:
            errors.append("processing_behavior.context_usage.open_risk_ids_emitted must match open_risks")

    synthesis_rules = processing_behavior.get("synthesis_rules")
    if not isinstance(synthesis_rules, Mapping):
        errors.append("processing_behavior.synthesis_rules must be an object")
    else:
        if synthesis_rules.get("recommendation_id_schema") != REQ_029_RECOMMENDATION_ID_SCHEMA:
            errors.append(
                f"processing_behavior.synthesis_rules.recommendation_id_schema must be "
                f"{REQ_029_RECOMMENDATION_ID_SCHEMA}"
            )
        if synthesis_rules.get("required_draft_fields") != REQ_029_REQUIRED_DRAFT_FIELDS:
            errors.append("processing_behavior.synthesis_rules.required_draft_fields must match the canonical list")
        if synthesis_rules.get("allowed_source_call_ids") != list(REQ_029_ALLOWED_SOURCE_CALL_IDS):
            errors.append("processing_behavior.synthesis_rules.allowed_source_call_ids must match the canonical list")

    source = payload.get("source")
    if not isinstance(source, Mapping):
        errors.append("source must be an object")
    else:
        if source.get("earlier_call_output_count") != len(earlier_call_outputs):
            errors.append("source.earlier_call_output_count must match earlier_call_outputs length")
        if source.get("candidate_recommendation_count") != len(recommendation_drafts) + len(open_risks):
            errors.append("source.candidate_recommendation_count must match drafts plus open_risks length")
        if source.get("draft_count") != len(recommendation_drafts):
            errors.append("source.draft_count must match recommendation_drafts length")
        if source.get("open_risk_count") != len(open_risks):
            errors.append("source.open_risk_count must match open_risks length")
        evidence_ref_count = source.get("evidence_ref_count")
        if not isinstance(evidence_ref_count, int) or evidence_ref_count <= 0:
            errors.append("source.evidence_ref_count must be a positive integer")

    metadata = payload.get("call_metadata")
    if metadata is not None:
        if not isinstance(metadata, Mapping):
            errors.append("call_metadata must be an object")
        else:
            if metadata.get("reproducibility") != "deterministic-input-fingerprint":
                errors.append("call_metadata.reproducibility must be deterministic-input-fingerprint")
            if metadata.get("llm_call_trace_schema_version") != REQ_029_LLM_CALL_TRACE_SCHEMA_VERSION:
                errors.append(
                    f"call_metadata.llm_call_trace_schema_version must be {REQ_029_LLM_CALL_TRACE_SCHEMA_VERSION}"
                )
            if metadata.get("llm_call_trace_path") != LLM_CALL_TRACE_RELATIVE_PATH:
                errors.append(f"call_metadata.llm_call_trace_path must be {LLM_CALL_TRACE_RELATIVE_PATH}")
            rows = metadata.get("llm_call_trace_rows")
            if not isinstance(rows, list) or len(rows) != 4:
                errors.append("call_metadata.llm_call_trace_rows must contain exactly four rows")
                rows = []
            for index, row in enumerate(rows):
                if not isinstance(row, Mapping):
                    errors.append(f"call_metadata.llm_call_trace_rows[{index}] must be an object")
                    continue
                for key in ("call_id", "call_objective", "handoff_summary"):
                    if not _as_text(row.get(key)):
                        errors.append(f"call_metadata.llm_call_trace_rows[{index}].{key} is required")
                for key in ("input_refs", "output_refs"):
                    value = row.get(key)
                    if not isinstance(value, list) or not value or any(not _as_text(item) for item in value):
                        errors.append(
                            f"call_metadata.llm_call_trace_rows[{index}].{key} must be a non-empty string array"
                        )
                if row.get("sequence") != index + 1:
                    errors.append(f"call_metadata.llm_call_trace_rows[{index}].sequence must be {index + 1}")
            expected_trace_rows: list[dict[str, Any]] = []
            if isinstance(context_inputs, Mapping):
                expected_earlier_call_outputs = context_inputs.get("earlier_call_outputs")
                if isinstance(expected_earlier_call_outputs, list):
                    try:
                        expected_trace_rows = _build_req_029_llm_call_trace_rows(
                            processing_call_id=_require_text(
                                metadata.get("processing_call_id"),
                                field_name="call_metadata.processing_call_id",
                            ),
                            earlier_call_outputs=[
                                _require_mapping(row, field_name=f"processing_behavior.context_inputs.earlier_call_outputs[{index}]")
                                for index, row in enumerate(expected_earlier_call_outputs)
                            ],
                            recommendation_drafts=[
                                _require_mapping(row, field_name=f"recommendation_synthesis.recommendation_drafts[{index}]")
                                for index, row in enumerate(recommendation_drafts)
                                if isinstance(row, Mapping)
                            ],
                            open_risks=[
                                _require_mapping(row, field_name=f"recommendation_synthesis.open_risks[{index}]")
                                for index, row in enumerate(open_risks)
                                if isinstance(row, Mapping)
                            ],
                        )
                    except ValueError as exc:
                        errors.append(f"call_metadata.llm_call_trace_rows could not be reconstructed: {exc}")
            if expected_trace_rows:
                if rows != expected_trace_rows:
                    errors.append("call_metadata.llm_call_trace_rows must mirror the deterministic per-call trace rows")
                expected_trace_sha = _canonical_digest(expected_trace_rows)
                if metadata.get("llm_call_trace_sha256") != expected_trace_sha:
                    errors.append("call_metadata.llm_call_trace_sha256 does not match llm_call_trace_rows")

    return errors


def _req_031_normalize_call_chain(
    value: Any,
    *,
    field_name: str = "call_chain",
) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise Req031Error(f"{field_name} must be an array")

    normalized: list[dict[str, Any]] = []
    seen_call_ids: set[str] = set()
    for index, raw_row in enumerate(value):
        row = _require_mapping(raw_row, field_name=f"{field_name}[{index}]")
        sequence = row.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int):
            raise Req031Error(f"{field_name}[{index}].sequence must be an integer")
        if sequence != index + 1:
            raise Req031Error(f"{field_name}[{index}].sequence must be {index + 1}")
        expected_call_id = REQ_031_REQUIRED_CALL_IDS[index] if index < len(REQ_031_REQUIRED_CALL_IDS) else ""
        call_id = _require_text(row.get("call_id"), field_name=f"{field_name}[{index}].call_id").lower()
        if call_id != expected_call_id:
            raise Req031Error(f"{field_name}[{index}].call_id must be {expected_call_id}")
        if call_id in seen_call_ids:
            raise Req031Error(f"{field_name}[{index}].call_id must be unique")
        seen_call_ids.add(call_id)
        normalized.append(
            {
                "sequence": sequence,
                "call_id": call_id,
                "phase": _require_text(row.get("phase"), field_name=f"{field_name}[{index}].phase"),
                "output_ref": _require_text(row.get("output_ref"), field_name=f"{field_name}[{index}].output_ref"),
            }
        )

    if len(normalized) != len(REQ_031_REQUIRED_CALL_IDS):
        raise Req031Error(
            f"{field_name} must include exactly {len(REQ_031_REQUIRED_CALL_IDS)} rows for Call-6 estimation"
        )
    return normalized


def _req_031_claim_output_ref(*, source_call_sequence: int, phase: str) -> str:
    return f"{REQ_031_REQUIREMENT_ID}::call-chain::{source_call_sequence:02d}::{phase}"


def _req_031_normalize_strategic_claims(
    value: Any,
    *,
    call_depth: int,
    field_name: str = "strategic_claims",
) -> list[dict[str, Any]]:
    if value is None:
        rows: Sequence[Any] = []
    else:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            raise Req031Error(f"{field_name} must be an array")
        rows = value

    normalized: list[dict[str, Any]] = []
    for index, raw_row in enumerate(rows):
        row = _require_mapping(raw_row, field_name=f"{field_name}[{index}]")
        phase = _require_text(row.get("phase"), field_name=f"{field_name}[{index}].phase").lower()
        if phase not in REQ_026_ALLOWED_CLAIM_PHASES:
            raise Req031Error(
                f"{field_name}[{index}].phase must be one of {sorted(REQ_026_ALLOWED_CLAIM_PHASES)}"
            )
        source_call_sequence = row.get("source_call_sequence")
        if (
            isinstance(source_call_sequence, bool)
            or not isinstance(source_call_sequence, int)
            or source_call_sequence < 1
            or source_call_sequence > call_depth
        ):
            raise Req031Error(
                f"{field_name}[{index}].source_call_sequence must be an integer between 1 and {call_depth}"
            )
        normalized.append(
            {
                "claim_id": _require_text(
                    row.get("claim_id"),
                    field_name=f"{field_name}[{index}].claim_id",
                ),
                "phase": phase,
                "summary": _require_text(
                    row.get("summary"),
                    field_name=f"{field_name}[{index}].summary",
                ),
                "position": _require_text(
                    row.get("position"),
                    field_name=f"{field_name}[{index}].position",
                ),
                "source_call_sequence": source_call_sequence,
                "evidence_refs": _normalize_string_list(
                    row.get("evidence_refs"),
                    field_name=f"{field_name}[{index}].evidence_refs",
                    min_items=1,
                ),
            }
        )

    normalized.sort(
        key=lambda row: (
            row["claim_id"],
            row["phase"],
            row["source_call_sequence"],
            row["position"],
            row["summary"],
        )
    )
    return normalized


def _req_031_normalize_recommendation_adoptions(
    value: Any,
    *,
    field_name: str = "recommendation_adoptions",
) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise Req031Error(f"{field_name} must be a non-empty array")

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_row in enumerate(value):
        row = _require_mapping(raw_row, field_name=f"{field_name}[{index}]")
        recommendation_id = _require_text(
            row.get("recommendation_id"),
            field_name=f"{field_name}[{index}].recommendation_id",
        )
        if not REQ_029_RECOMMENDATION_ID_RE.match(recommendation_id):
            raise Req031Error(
                f"{field_name}[{index}].recommendation_id must match {REQ_029_RECOMMENDATION_ID_RE.pattern}"
            )
        if recommendation_id in seen_ids:
            raise Req031Error(f"{field_name}[{index}].recommendation_id must be unique")
        seen_ids.add(recommendation_id)

        adoption_status = _require_text(
            row.get("adoption_status"),
            field_name=f"{field_name}[{index}].adoption_status",
        ).lower()
        if adoption_status not in REQ_031_ALLOWED_ADOPTION_STATUSES:
            raise Req031Error(
                f"{field_name}[{index}].adoption_status must be one of {sorted(REQ_031_ALLOWED_ADOPTION_STATUSES)}"
            )

        project_id = _as_text(row.get("project_id"))
        requires_earth_evidence = row.get("requires_earth_evidence")
        if requires_earth_evidence is None:
            requires_earth_evidence = bool(project_id)
        if not isinstance(requires_earth_evidence, bool):
            raise Req031Error(f"{field_name}[{index}].requires_earth_evidence must be a boolean")

        normalized.append(
            {
                "recommendation_id": recommendation_id,
                "summary": _require_text(row.get("summary"), field_name=f"{field_name}[{index}].summary"),
                "adoption_status": adoption_status,
                "adoption_window": _require_text(
                    row.get("adoption_window"),
                    field_name=f"{field_name}[{index}].adoption_window",
                ),
                "project_id": project_id,
                "requires_earth_evidence": requires_earth_evidence,
                "evidence_refs": _normalize_string_list(
                    row.get("evidence_refs"),
                    field_name=f"{field_name}[{index}].evidence_refs",
                    min_items=1,
                ),
            }
        )

    if not normalized:
        raise Req031Error(f"{field_name} must contain at least 1 item(s)")
    normalized.sort(key=lambda row: row["recommendation_id"])
    return normalized


def _req_031_normalize_kpi_definitions(
    value: Any,
    *,
    field_name: str = "kpi_definitions",
) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise Req031Error(f"{field_name} must be a non-empty array")

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_row in enumerate(value):
        row = _require_mapping(raw_row, field_name=f"{field_name}[{index}]")
        kpi_id = _require_text(row.get("kpi_id"), field_name=f"{field_name}[{index}].kpi_id")
        if not re.fullmatch(r"kpi\.[a-z0-9]+(?:-[a-z0-9]+)*", kpi_id):
            raise Req031Error(f"{field_name}[{index}].kpi_id must match kpi.[a-z0-9-] schema")
        if kpi_id in seen_ids:
            raise Req031Error(f"{field_name}[{index}].kpi_id must be unique")
        seen_ids.add(kpi_id)

        desired_direction = _require_text(
            row.get("desired_direction"),
            field_name=f"{field_name}[{index}].desired_direction",
        ).lower()
        if desired_direction not in REQ_031_ALLOWED_DIRECTIONS:
            raise Req031Error(
                f"{field_name}[{index}].desired_direction must be one of {sorted(REQ_031_ALLOWED_DIRECTIONS)}"
            )

        normalized.append(
            {
                "kpi_id": kpi_id,
                "name": _require_text(row.get("name"), field_name=f"{field_name}[{index}].name"),
                "unit": _require_text(row.get("unit"), field_name=f"{field_name}[{index}].unit"),
                "baseline_value": _require_number(
                    row.get("baseline_value"),
                    field_name=f"{field_name}[{index}].baseline_value",
                ),
                "desired_direction": desired_direction,
                "source_ref": _require_text(
                    row.get("source_ref"),
                    field_name=f"{field_name}[{index}].source_ref",
                ),
            }
        )

    if not normalized:
        raise Req031Error(f"{field_name} must contain at least 1 item(s)")
    normalized.sort(key=lambda row: row["kpi_id"])
    return normalized


def _req_031_normalize_impact_assumptions(
    value: Any,
    *,
    recommendation_ids: set[str],
    kpi_ids: set[str],
    available_evidence_refs: set[str],
    field_name: str = "impact_assumptions",
) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise Req031Error(f"{field_name} must be a non-empty array")

    normalized: list[dict[str, Any]] = []
    seen_assumption_ids: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    for index, raw_row in enumerate(value):
        row = _require_mapping(raw_row, field_name=f"{field_name}[{index}]")
        assumption_id = _require_text(
            row.get("assumption_id"),
            field_name=f"{field_name}[{index}].assumption_id",
        )
        if assumption_id in seen_assumption_ids:
            raise Req031Error(f"{field_name}[{index}].assumption_id must be unique")
        seen_assumption_ids.add(assumption_id)

        recommendation_id = _require_text(
            row.get("recommendation_id"),
            field_name=f"{field_name}[{index}].recommendation_id",
        )
        if recommendation_id not in recommendation_ids:
            raise Req031Error(f"{field_name}[{index}].recommendation_id must reference recommendation_adoptions")

        kpi_id = _require_text(row.get("kpi_id"), field_name=f"{field_name}[{index}].kpi_id")
        if kpi_id not in kpi_ids:
            raise Req031Error(f"{field_name}[{index}].kpi_id must reference kpi_definitions")

        pair = (recommendation_id, kpi_id)
        if pair in seen_pairs:
            raise Req031Error(
                f"{field_name}[{index}] duplicates recommendation_id/kpi_id pair {recommendation_id}/{kpi_id}"
            )
        seen_pairs.add(pair)

        expected_movement_lower = _require_number(
            row.get("expected_movement_lower"),
            field_name=f"{field_name}[{index}].expected_movement_lower",
        )
        expected_movement_upper = _require_number(
            row.get("expected_movement_upper"),
            field_name=f"{field_name}[{index}].expected_movement_upper",
        )
        if expected_movement_lower > expected_movement_upper:
            raise Req031Error(
                f"{field_name}[{index}].expected_movement_lower must be <= expected_movement_upper"
            )

        confidence = _require_text(
            row.get("confidence"),
            field_name=f"{field_name}[{index}].confidence",
        ).lower()
        if confidence not in REQ_031_ALLOWED_CONFIDENCE_VALUES:
            raise Req031Error(
                f"{field_name}[{index}].confidence must be one of {sorted(REQ_031_ALLOWED_CONFIDENCE_VALUES)}"
            )

        evidence_refs = _normalize_string_list(
            row.get("evidence_refs"),
            field_name=f"{field_name}[{index}].evidence_refs",
            min_items=1,
        )
        missing_refs = sorted(set(evidence_refs) - available_evidence_refs)
        if missing_refs:
            raise Req031Error(
                f"{field_name}[{index}].evidence_refs must stay within available evidence refs; missing {missing_refs}"
            )

        normalized.append(
            {
                "assumption_id": assumption_id,
                "recommendation_id": recommendation_id,
                "kpi_id": kpi_id,
                "statement": _require_text(row.get("statement"), field_name=f"{field_name}[{index}].statement"),
                "expected_movement_lower": expected_movement_lower,
                "expected_movement_upper": expected_movement_upper,
                "confidence": confidence,
                "caveats": _normalize_string_list(
                    row.get("caveats"),
                    field_name=f"{field_name}[{index}].caveats",
                    min_items=1,
                ),
                "evidence_refs": evidence_refs,
            }
        )

    if not normalized:
        raise Req031Error(f"{field_name} must contain at least 1 item(s)")
    normalized.sort(key=lambda row: (row["recommendation_id"], row["kpi_id"], row["assumption_id"]))
    return normalized


def _req_031_estimate_id(*, recommendation_id: str, kpi_id: str) -> str:
    return f"estimate::{recommendation_id}::{kpi_id}"


def _req_031_build_reasoning_summary(
    *,
    recommendation_summary: str,
    kpi_name: str,
    adoption_window: str,
    expected_movement_lower: float,
    expected_movement_upper: float,
    unit: str,
    assumption_id: str,
) -> str:
    return (
        f"Adopting '{recommendation_summary}' is estimated to shift {kpi_name} by "
        f"{expected_movement_lower:g} to {expected_movement_upper:g} {unit} over {adoption_window} "
        f"under assumption {assumption_id}."
    )


def _req_031_canonical_input(
    *,
    project_id: str,
    call_chain: Sequence[Mapping[str, Any]],
    recommendation_adoptions: Sequence[Mapping[str, Any]],
    kpi_definitions: Sequence[Mapping[str, Any]],
    impact_assumptions: Sequence[Mapping[str, Any]],
    target_project_evidence_refs: Sequence[str],
    earth_sweep_evidence_refs: Sequence[str],
    strategic_claims: Sequence[Mapping[str, Any]],
    checked_at_utc: str,
) -> dict[str, Any]:
    return {
        "requirement_id": REQ_031_REQUIREMENT_ID,
        "analysis_type": REQ_031_ANALYSIS_TYPE,
        "call_id": REQ_031_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "target_project": {"project_id": project_id},
        "call_chain": [dict(row) for row in call_chain],
        "target_project_evidence_refs": list(target_project_evidence_refs),
        "earth_sweep_evidence_refs": list(earth_sweep_evidence_refs),
        "strategic_claims": [dict(row) for row in strategic_claims],
        "recommendation_adoptions": [dict(row) for row in recommendation_adoptions],
        "kpi_definitions": [dict(row) for row in kpi_definitions],
        "impact_assumptions": [dict(row) for row in impact_assumptions],
    }


def _build_req_031_llm_call_trace_rows(
    *,
    processing_call_id: str,
    call_chain: Sequence[Mapping[str, Any]],
    target_project_evidence_refs: Sequence[str],
    earth_sweep_evidence_refs: Sequence[str],
    strategic_claims: Sequence[Mapping[str, Any]],
    impact_assumptions: Sequence[Mapping[str, Any]],
    estimate_count: int,
) -> list[dict[str, Any]]:
    trace_rows: list[dict[str, Any]] = []
    prior_output_refs: list[str] = []
    terminal_evidence_refs = _req_026_dedupe_preserving_order(
        list(target_project_evidence_refs)
        + list(earth_sweep_evidence_refs)
        + [
            _req_031_claim_output_ref(
                source_call_sequence=int(row["source_call_sequence"]),
                phase=str(row["phase"]),
            )
            for row in strategic_claims
        ]
        + [ref for row in strategic_claims for ref in row.get("evidence_refs", [])]
        + [ref for row in impact_assumptions for ref in row.get("evidence_refs", [])]
    )

    for row in call_chain:
        call_id = str(row["call_id"])
        sequence = int(row["sequence"])
        output_ref = str(row["output_ref"])
        if call_id == REQ_031_CALL_ID:
            input_refs = _req_026_dedupe_preserving_order(prior_output_refs + terminal_evidence_refs)
            handoff_summary = (
                f"Call 6 hands off kpi_impact_estimation via {output_ref} as the terminal KPI estimation output "
                f"with {estimate_count} estimate(s)."
            )
        else:
            input_refs = list(prior_output_refs[-1:]) if prior_output_refs else []
            next_call_id = REQ_031_REQUIRED_CALL_IDS[sequence]
            handoff_summary = (
                f"Call {sequence} hands off {_req_029_trace_output_name(output_ref)} via {output_ref} to "
                f"{next_call_id} after consuming {len(input_refs)} input refs."
            )
        trace_rows.append(
            {
                "schema_version": REQ_031_LLM_CALL_TRACE_SCHEMA_VERSION,
                "requirement_id": REQ_031_REQUIREMENT_ID,
                "processing_call_id": processing_call_id,
                "call_id": call_id,
                "sequence": sequence,
                "call_objective": REQ_031_CALL_OBJECTIVES[call_id],
                "input_refs": input_refs,
                "output_refs": [output_ref],
                "handoff_summary": handoff_summary,
            }
        )
        prior_output_refs.append(output_ref)

    return trace_rows


def build_req_031_call_6_kpi_impact_estimation_reasoning(
    *,
    target_project: Mapping[str, Any],
    call_chain: Sequence[Mapping[str, Any]],
    recommendation_adoptions: Sequence[Mapping[str, Any]],
    kpi_definitions: Sequence[Mapping[str, Any]],
    impact_assumptions: Sequence[Mapping[str, Any]],
    target_project_evidence_refs: Sequence[Any] | None = None,
    earth_sweep_evidence_refs: Sequence[Any] | None = None,
    strategic_claims: Sequence[Mapping[str, Any]] | None = None,
    analysis_type: str = REQ_031_ANALYSIS_TYPE,
    call_id: str = REQ_031_CALL_ID,
    checked_at_utc: str | None = None,
) -> dict[str, Any]:
    if analysis_type != REQ_031_ANALYSIS_TYPE:
        raise Req031Error(f"analysis_type must be {REQ_031_ANALYSIS_TYPE}")
    if call_id != REQ_031_CALL_ID:
        raise Req031Error(f"call_id must be {REQ_031_CALL_ID}")

    project = _require_mapping(target_project, field_name="target_project")
    project_id = _require_text(project.get("project_id"), field_name="target_project.project_id")
    normalized_checked_at_utc = _require_text(checked_at_utc or utc_now_iso(), field_name="checked_at_utc")
    normalized_call_chain = _req_031_normalize_call_chain(call_chain)
    normalized_target_refs = _normalize_string_list(
        target_project_evidence_refs,
        field_name="target_project_evidence_refs",
        min_items=1,
    )
    normalized_earth_refs = _normalize_string_list(
        earth_sweep_evidence_refs,
        field_name="earth_sweep_evidence_refs",
    )
    normalized_strategic_claims = _req_031_normalize_strategic_claims(
        strategic_claims,
        call_depth=len(normalized_call_chain),
    )
    normalized_recommendation_adoptions = _req_031_normalize_recommendation_adoptions(recommendation_adoptions)
    normalized_kpi_definitions = _req_031_normalize_kpi_definitions(kpi_definitions)

    for index, row in enumerate(normalized_recommendation_adoptions):
        if row["requires_earth_evidence"] and not any(
            _is_earth_evidence_ref(ref) for ref in list(row["evidence_refs"]) + normalized_earth_refs
        ):
            raise Req031Error(
                f"recommendation_adoptions[{index}] requires Earth evidence but no Earth-scoped refs were supplied"
            )

    available_citation_refs = set(
        _collect_unique_refs(
            normalized_target_refs,
            normalized_earth_refs,
            [row["output_ref"] for row in normalized_call_chain],
            [row["source_ref"] for row in normalized_kpi_definitions],
            [ref for row in normalized_recommendation_adoptions for ref in row["evidence_refs"]],
        )
    )
    available_evidence_refs = set(
        _collect_unique_refs(
            normalized_target_refs,
            normalized_earth_refs,
            [row["output_ref"] for row in normalized_call_chain],
            [row["source_ref"] for row in normalized_kpi_definitions],
            [ref for row in normalized_recommendation_adoptions for ref in row["evidence_refs"]],
        )
    )
    normalized_impact_assumptions = _req_031_normalize_impact_assumptions(
        impact_assumptions,
        recommendation_ids={str(row["recommendation_id"]) for row in normalized_recommendation_adoptions},
        kpi_ids={str(row["kpi_id"]) for row in normalized_kpi_definitions},
        available_evidence_refs=available_evidence_refs,
    )

    open_risks: list[dict[str, Any]] = []
    claims_by_id: dict[str, list[dict[str, Any]]] = {}
    for claim in normalized_strategic_claims:
        claim_id = str(claim["claim_id"])
        claims_by_id.setdefault(claim_id, []).append(claim)
        citation_refs = list(claim["evidence_refs"])
        source_output_ref = _req_031_claim_output_ref(
            source_call_sequence=int(claim["source_call_sequence"]),
            phase=str(claim["phase"]),
        )
        if not set(citation_refs).issubset(available_citation_refs):
            open_risks.append(
                {
                    "risk_id": f"risk-claim-{claim_id}-citation",
                    "reason_code": "uncited_strategic_claim",
                    "summary": str(claim["summary"]),
                    "required_evidence_refs": _req_026_dedupe_preserving_order([source_output_ref] + citation_refs),
                }
            )

    for claim_id, claim_rows in claims_by_id.items():
        analysis_rows = [row for row in claim_rows if row["phase"] == "analysis"]
        synthesis_rows = [row for row in claim_rows if row["phase"] == "synthesis"]
        contradiction_refs: list[str] | None = None
        contradiction_summary = ""
        for analysis_row in analysis_rows:
            for synthesis_row in synthesis_rows:
                if analysis_row["position"] == synthesis_row["position"]:
                    continue
                contradiction_summary = str(synthesis_row["summary"])
                contradiction_refs = _req_026_dedupe_preserving_order(
                    [
                        _req_031_claim_output_ref(
                            source_call_sequence=int(analysis_row["source_call_sequence"]),
                            phase=str(analysis_row["phase"]),
                        ),
                        _req_031_claim_output_ref(
                            source_call_sequence=int(synthesis_row["source_call_sequence"]),
                            phase=str(synthesis_row["phase"]),
                        ),
                    ]
                    + list(analysis_row["evidence_refs"])
                    + list(synthesis_row["evidence_refs"])
                )
                break
            if contradiction_refs is not None:
                break
        if contradiction_refs is not None:
            open_risks.append(
                {
                    "risk_id": f"risk-claim-{claim_id}-contradiction",
                    "reason_code": "cross_call_contradiction",
                    "summary": contradiction_summary,
                    "required_evidence_refs": contradiction_refs,
                }
            )

    open_risks.sort(key=lambda row: str(row["risk_id"]))

    recommendation_by_id = {
        str(row["recommendation_id"]): row for row in normalized_recommendation_adoptions
    }
    kpi_by_id = {str(row["kpi_id"]): row for row in normalized_kpi_definitions}

    kpi_estimates: list[dict[str, Any]] = []
    for assumption in normalized_impact_assumptions:
        recommendation = recommendation_by_id[str(assumption["recommendation_id"])]
        kpi = kpi_by_id[str(assumption["kpi_id"])]
        baseline_value = float(kpi["baseline_value"])
        expected_movement_lower = float(assumption["expected_movement_lower"])
        expected_movement_upper = float(assumption["expected_movement_upper"])
        kpi_estimates.append(
            {
                "estimate_id": _req_031_estimate_id(
                    recommendation_id=str(recommendation["recommendation_id"]),
                    kpi_id=str(kpi["kpi_id"]),
                ),
                "recommendation_id": str(recommendation["recommendation_id"]),
                "recommendation_summary": str(recommendation["summary"]),
                "kpi_id": str(kpi["kpi_id"]),
                "kpi_name": str(kpi["name"]),
                "baseline_value": baseline_value,
                "unit": str(kpi["unit"]),
                "desired_direction": str(kpi["desired_direction"]),
                "adoption_status": str(recommendation["adoption_status"]),
                "adoption_window": str(recommendation["adoption_window"]),
                "expected_movement": {
                    "lower_bound": expected_movement_lower,
                    "upper_bound": expected_movement_upper,
                    "unit": str(kpi["unit"]),
                    "direction": str(kpi["desired_direction"]),
                },
                "estimated_post_adoption_range": {
                    "lower_bound": baseline_value + expected_movement_lower,
                    "upper_bound": baseline_value + expected_movement_upper,
                    "unit": str(kpi["unit"]),
                },
                "reasoning_summary": _req_031_build_reasoning_summary(
                    recommendation_summary=str(recommendation["summary"]),
                    kpi_name=str(kpi["name"]),
                    adoption_window=str(recommendation["adoption_window"]),
                    expected_movement_lower=expected_movement_lower,
                    expected_movement_upper=expected_movement_upper,
                    unit=str(kpi["unit"]),
                    assumption_id=str(assumption["assumption_id"]),
                ),
                "confidence": str(assumption["confidence"]),
                "caveats": list(assumption["caveats"]),
                "evidence_backed_assumptions": [
                    {
                        "assumption_id": str(assumption["assumption_id"]),
                        "statement": str(assumption["statement"]),
                        "evidence_refs": list(assumption["evidence_refs"]),
                    }
                ],
                "evidence_refs": _req_026_dedupe_preserving_order(
                    list(recommendation["evidence_refs"])
                    + [str(kpi["source_ref"])]
                    + list(assumption["evidence_refs"])
                ),
            }
        )

    kpi_estimates.sort(key=lambda row: str(row["estimate_id"]))
    low_confidence_estimate_ids = [
        str(row["estimate_id"]) for row in kpi_estimates if row["confidence"] == "low"
    ]
    cross_project_project_ids = sorted(
        {
            str(row["project_id"])
            for row in normalized_recommendation_adoptions
            if _as_text(row.get("project_id"))
        }
    )
    unique_evidence_refs = _req_026_dedupe_preserving_order(
        list(normalized_target_refs)
        + list(normalized_earth_refs)
        + [ref for row in kpi_estimates for ref in row["evidence_refs"]]
        + [ref for row in open_risks for ref in row["required_evidence_refs"]]
    )

    canonical_input = _req_031_canonical_input(
        project_id=project_id,
        call_chain=normalized_call_chain,
        recommendation_adoptions=normalized_recommendation_adoptions,
        kpi_definitions=normalized_kpi_definitions,
        impact_assumptions=normalized_impact_assumptions,
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        strategic_claims=normalized_strategic_claims,
        checked_at_utc=normalized_checked_at_utc,
    )
    canonical_input_sha = _canonical_digest(canonical_input)
    processing_call_id = f"req031-processing-{canonical_input_sha[:16]}"
    llm_call_trace_rows = _build_req_031_llm_call_trace_rows(
        processing_call_id=processing_call_id,
        call_chain=normalized_call_chain,
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        strategic_claims=normalized_strategic_claims,
        impact_assumptions=normalized_impact_assumptions,
        estimate_count=len(kpi_estimates),
    )
    llm_call_trace_sha = _canonical_digest(llm_call_trace_rows)

    return {
        "ok": True,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "schema_version": REQ_031_SCHEMA_VERSION,
        "requirement_id": REQ_031_REQUIREMENT_ID,
        "analysis_type": REQ_031_ANALYSIS_TYPE,
        "call_id": REQ_031_CALL_ID,
        "checked_at_utc": normalized_checked_at_utc,
        "kpi_impact_estimation": {
            "target_project": {
                "project_id": project_id,
            },
            "recommendation_adoptions": normalized_recommendation_adoptions,
            "kpi_estimates": kpi_estimates,
            "summary": {
                "recommendation_count": len(normalized_recommendation_adoptions),
                "kpi_count": len(normalized_kpi_definitions),
                "estimate_count": len(kpi_estimates),
                "low_confidence_estimate_count": len(low_confidence_estimate_ids),
                "caveat_count": sum(len(row["caveats"]) for row in kpi_estimates),
            },
        },
        "processing_behavior": {
            "strategy": REQ_031_PROCESSING_STRATEGY,
            "reasoning_mode": REQ_031_REASONING_MODE,
            "strict_evidence_discipline": True,
            "context_inputs": {
                "call_chain": normalized_call_chain,
                "target_project_evidence_refs": normalized_target_refs,
                "earth_sweep_evidence_refs": normalized_earth_refs,
                "strategic_claims": normalized_strategic_claims,
                "recommendation_adoptions": normalized_recommendation_adoptions,
                "kpi_definitions": normalized_kpi_definitions,
                "impact_assumptions": normalized_impact_assumptions,
            },
            "context_usage": {
                "source_call_ids_used": [str(row["call_id"]) for row in normalized_call_chain],
                "earth_sweep_context_used": bool(normalized_earth_refs),
                "cross_project_context_used": bool(cross_project_project_ids),
                "cross_project_project_ids_used": cross_project_project_ids,
                "earth_sweep_evidence_refs_used": list(normalized_earth_refs),
                "recommendation_ids_considered": [
                    str(row["recommendation_id"]) for row in normalized_recommendation_adoptions
                ],
                "kpi_ids_considered": [str(row["kpi_id"]) for row in normalized_kpi_definitions],
                "estimate_ids_emitted": [str(row["estimate_id"]) for row in kpi_estimates],
                "low_confidence_estimate_ids": low_confidence_estimate_ids,
                "open_risk_ids_emitted": [str(row["risk_id"]) for row in open_risks],
                "reason_codes_emitted": [str(row["reason_code"]) for row in open_risks],
                "caveat_count": sum(len(row["caveats"]) for row in kpi_estimates),
                "evidence_refs_used": unique_evidence_refs,
            },
            "estimation_rules": {
                "confidence_scale": ["high", "medium", "low"],
                "required_estimate_fields": list(REQ_031_REQUIRED_ESTIMATE_FIELDS),
                "caveats_required": True,
                "bounded_range_required": True,
                "assumption_evidence_required": True,
            },
            "diagnostics": {
                "open_risks": open_risks,
            },
        },
        "source": {
            "recommendation_adoption_count": len(normalized_recommendation_adoptions),
            "kpi_definition_count": len(normalized_kpi_definitions),
            "impact_assumption_count": len(normalized_impact_assumptions),
            "estimate_count": len(kpi_estimates),
            "evidence_ref_count": len(unique_evidence_refs),
            "earth_sweep_evidence_count": len(normalized_earth_refs),
        },
        "call_metadata": {
            "reproducibility": "deterministic-input-fingerprint",
            "canonical_input_sha256": canonical_input_sha,
            "reproducible_call_id": f"req031-{canonical_input_sha[:16]}",
            "canonical_input": canonical_input,
            "processing_call_id": processing_call_id,
            "llm_call_trace_schema_version": REQ_031_LLM_CALL_TRACE_SCHEMA_VERSION,
            "llm_call_trace_path": LLM_CALL_TRACE_RELATIVE_PATH,
            "llm_call_trace_sha256": llm_call_trace_sha,
            "llm_call_trace_rows": llm_call_trace_rows,
        },
    }


def validate_req_031_call_6_kpi_impact_estimation_reasoning(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []

    if payload.get("ok") is not True:
        errors.append("ok must be true")
    if payload.get("tool") != TOOL:
        errors.append(f"tool must be {TOOL}")
    if payload.get("tool_version") != TOOL_VERSION:
        errors.append(f"tool_version must be {TOOL_VERSION}")
    if payload.get("schema_version") != REQ_031_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_031_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_031_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_031_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_031_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_031_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_031_CALL_ID:
        errors.append(f"call_id must be {REQ_031_CALL_ID}")
    if not _as_text(payload.get("checked_at_utc")):
        errors.append("checked_at_utc is required")

    kpi_impact_estimation = payload.get("kpi_impact_estimation")
    if not isinstance(kpi_impact_estimation, Mapping):
        errors.append("kpi_impact_estimation must be an object")
        kpi_impact_estimation = {}

    target_project = kpi_impact_estimation.get("target_project")
    if not isinstance(target_project, Mapping):
        errors.append("kpi_impact_estimation.target_project must be an object")
    elif not _as_text(target_project.get("project_id")):
        errors.append("kpi_impact_estimation.target_project.project_id is required")

    recommendation_adoptions = kpi_impact_estimation.get("recommendation_adoptions")
    if not isinstance(recommendation_adoptions, list) or not recommendation_adoptions:
        errors.append("kpi_impact_estimation.recommendation_adoptions must be a non-empty array")
        recommendation_adoptions = []
    recommendation_ids: list[str] = []
    for index, row in enumerate(recommendation_adoptions):
        if not isinstance(row, Mapping):
            errors.append(f"kpi_impact_estimation.recommendation_adoptions[{index}] must be an object")
            continue
        recommendation_id = _as_text(row.get("recommendation_id"))
        if not recommendation_id:
            errors.append(f"kpi_impact_estimation.recommendation_adoptions[{index}].recommendation_id is required")
        else:
            recommendation_ids.append(recommendation_id)
        if not _as_text(row.get("summary")):
            errors.append(f"kpi_impact_estimation.recommendation_adoptions[{index}].summary is required")
        if _as_text(row.get("adoption_status")) not in REQ_031_ALLOWED_ADOPTION_STATUSES:
            errors.append(
                "kpi_impact_estimation.recommendation_adoptions"
                f"[{index}].adoption_status must be one of {sorted(REQ_031_ALLOWED_ADOPTION_STATUSES)}"
            )
        if not _as_text(row.get("adoption_window")):
            errors.append(f"kpi_impact_estimation.recommendation_adoptions[{index}].adoption_window is required")
        if not isinstance(row.get("requires_earth_evidence"), bool):
            errors.append(
                f"kpi_impact_estimation.recommendation_adoptions[{index}].requires_earth_evidence must be a boolean"
            )
        evidence_refs = row.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not evidence_refs or any(not _as_text(item) for item in evidence_refs):
            errors.append(
                f"kpi_impact_estimation.recommendation_adoptions[{index}].evidence_refs must be a non-empty string array"
            )

    kpi_estimates = kpi_impact_estimation.get("kpi_estimates")
    if not isinstance(kpi_estimates, list) or not kpi_estimates:
        errors.append("kpi_impact_estimation.kpi_estimates must be a non-empty array")
        kpi_estimates = []
    estimate_ids: list[str] = []
    low_confidence_estimate_ids: list[str] = []
    for index, row in enumerate(kpi_estimates):
        if not isinstance(row, Mapping):
            errors.append(f"kpi_impact_estimation.kpi_estimates[{index}] must be an object")
            continue
        for key in REQ_031_REQUIRED_ESTIMATE_FIELDS:
            if key not in row:
                errors.append(f"kpi_impact_estimation.kpi_estimates[{index}].{key} is required")
        estimate_id = _as_text(row.get("estimate_id"))
        if estimate_id:
            estimate_ids.append(estimate_id)
        if not _as_text(row.get("recommendation_id")):
            errors.append(f"kpi_impact_estimation.kpi_estimates[{index}].recommendation_id is required")
        if not _as_text(row.get("recommendation_summary")):
            errors.append(f"kpi_impact_estimation.kpi_estimates[{index}].recommendation_summary is required")
        if not _as_text(row.get("kpi_id")):
            errors.append(f"kpi_impact_estimation.kpi_estimates[{index}].kpi_id is required")
        if not _as_text(row.get("kpi_name")):
            errors.append(f"kpi_impact_estimation.kpi_estimates[{index}].kpi_name is required")
        if isinstance(row.get("baseline_value"), bool) or not isinstance(row.get("baseline_value"), (int, float)):
            errors.append(f"kpi_impact_estimation.kpi_estimates[{index}].baseline_value must be numeric")
        if _as_text(row.get("desired_direction")) not in REQ_031_ALLOWED_DIRECTIONS:
            errors.append(
                f"kpi_impact_estimation.kpi_estimates[{index}].desired_direction must be one of "
                f"{sorted(REQ_031_ALLOWED_DIRECTIONS)}"
            )
        if _as_text(row.get("adoption_status")) not in REQ_031_ALLOWED_ADOPTION_STATUSES:
            errors.append(
                f"kpi_impact_estimation.kpi_estimates[{index}].adoption_status must be one of "
                f"{sorted(REQ_031_ALLOWED_ADOPTION_STATUSES)}"
            )
        if not _as_text(row.get("adoption_window")):
            errors.append(f"kpi_impact_estimation.kpi_estimates[{index}].adoption_window is required")

        expected_movement = row.get("expected_movement")
        if not isinstance(expected_movement, Mapping):
            errors.append(f"kpi_impact_estimation.kpi_estimates[{index}].expected_movement must be an object")
        else:
            for key in ("lower_bound", "upper_bound"):
                value = expected_movement.get(key)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    errors.append(
                        f"kpi_impact_estimation.kpi_estimates[{index}].expected_movement.{key} must be numeric"
                    )
            if not _as_text(expected_movement.get("unit")):
                errors.append(f"kpi_impact_estimation.kpi_estimates[{index}].expected_movement.unit is required")
            if _as_text(expected_movement.get("direction")) not in REQ_031_ALLOWED_DIRECTIONS:
                errors.append(
                    "kpi_impact_estimation.kpi_estimates"
                    f"[{index}].expected_movement.direction must be increase or decrease"
                )

        post_range = row.get("estimated_post_adoption_range")
        if not isinstance(post_range, Mapping):
            errors.append(
                f"kpi_impact_estimation.kpi_estimates[{index}].estimated_post_adoption_range must be an object"
            )
        else:
            for key in ("lower_bound", "upper_bound"):
                value = post_range.get(key)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    errors.append(
                        "kpi_impact_estimation.kpi_estimates"
                        f"[{index}].estimated_post_adoption_range.{key} must be numeric"
                    )
            if not _as_text(post_range.get("unit")):
                errors.append(
                    f"kpi_impact_estimation.kpi_estimates[{index}].estimated_post_adoption_range.unit is required"
                )

        if not _as_text(row.get("reasoning_summary")):
            errors.append(f"kpi_impact_estimation.kpi_estimates[{index}].reasoning_summary is required")
        confidence = _as_text(row.get("confidence"))
        if confidence not in REQ_031_ALLOWED_CONFIDENCE_VALUES:
            errors.append(
                f"kpi_impact_estimation.kpi_estimates[{index}].confidence must be one of "
                f"{sorted(REQ_031_ALLOWED_CONFIDENCE_VALUES)}"
            )
        elif confidence == "low":
            low_confidence_estimate_ids.append(estimate_id)

        caveats = row.get("caveats")
        if not isinstance(caveats, list) or not caveats or any(not _as_text(item) for item in caveats):
            errors.append(f"kpi_impact_estimation.kpi_estimates[{index}].caveats must be a non-empty string array")

        assumptions = row.get("evidence_backed_assumptions")
        if not isinstance(assumptions, list) or not assumptions:
            errors.append(
                f"kpi_impact_estimation.kpi_estimates[{index}].evidence_backed_assumptions must be a non-empty array"
            )
        else:
            for assumption_index, assumption_row in enumerate(assumptions):
                if not isinstance(assumption_row, Mapping):
                    errors.append(
                        "kpi_impact_estimation.kpi_estimates"
                        f"[{index}].evidence_backed_assumptions[{assumption_index}] must be an object"
                    )
                    continue
                if not _as_text(assumption_row.get("assumption_id")):
                    errors.append(
                        "kpi_impact_estimation.kpi_estimates"
                        f"[{index}].evidence_backed_assumptions[{assumption_index}].assumption_id is required"
                    )
                if not _as_text(assumption_row.get("statement")):
                    errors.append(
                        "kpi_impact_estimation.kpi_estimates"
                        f"[{index}].evidence_backed_assumptions[{assumption_index}].statement is required"
                    )
                evidence_refs = assumption_row.get("evidence_refs")
                if not isinstance(evidence_refs, list) or not evidence_refs or any(not _as_text(item) for item in evidence_refs):
                    errors.append(
                        "kpi_impact_estimation.kpi_estimates"
                        f"[{index}].evidence_backed_assumptions[{assumption_index}].evidence_refs "
                        "must be a non-empty string array"
                    )

        evidence_refs = row.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not evidence_refs or any(not _as_text(item) for item in evidence_refs):
            errors.append(f"kpi_impact_estimation.kpi_estimates[{index}].evidence_refs must be a non-empty string array")

    summary = kpi_impact_estimation.get("summary")
    if not isinstance(summary, Mapping):
        errors.append("kpi_impact_estimation.summary must be an object")
    else:
        if summary.get("recommendation_count") != len(recommendation_adoptions):
            errors.append("kpi_impact_estimation.summary.recommendation_count must match recommendation_adoptions length")
        unique_kpi_ids = {
            row.get("kpi_id") for row in kpi_estimates if isinstance(row, Mapping) and _as_text(row.get("kpi_id"))
        }
        if summary.get("kpi_count") != len(unique_kpi_ids):
            errors.append("kpi_impact_estimation.summary.kpi_count must match unique kpi_id count")
        if summary.get("estimate_count") != len(kpi_estimates):
            errors.append("kpi_impact_estimation.summary.estimate_count must match kpi_estimates length")
        if summary.get("low_confidence_estimate_count") != len(low_confidence_estimate_ids):
            errors.append(
                "kpi_impact_estimation.summary.low_confidence_estimate_count must match low-confidence estimates"
            )
        if summary.get("caveat_count") != sum(
            len(row.get("caveats", [])) for row in kpi_estimates if isinstance(row, Mapping)
        ):
            errors.append("kpi_impact_estimation.summary.caveat_count must match total caveat count")

    processing_behavior = payload.get("processing_behavior")
    if not isinstance(processing_behavior, Mapping):
        errors.append("processing_behavior must be an object")
        processing_behavior = {}
    if processing_behavior.get("strategy") != REQ_031_PROCESSING_STRATEGY:
        errors.append(f"processing_behavior.strategy must be {REQ_031_PROCESSING_STRATEGY}")
    if processing_behavior.get("reasoning_mode") != REQ_031_REASONING_MODE:
        errors.append(f"processing_behavior.reasoning_mode must be {REQ_031_REASONING_MODE}")
    if processing_behavior.get("strict_evidence_discipline") is not True:
        errors.append("processing_behavior.strict_evidence_discipline must be true")

    context_inputs = processing_behavior.get("context_inputs")
    if not isinstance(context_inputs, Mapping):
        errors.append("processing_behavior.context_inputs must be an object")
        context_inputs = {}
    for key in (
        "call_chain",
        "target_project_evidence_refs",
        "earth_sweep_evidence_refs",
        "recommendation_adoptions",
        "kpi_definitions",
        "impact_assumptions",
    ):
        if not isinstance(context_inputs.get(key), list):
            errors.append(f"processing_behavior.context_inputs.{key} must be an array")
    strategic_claims = context_inputs.get("strategic_claims")
    if strategic_claims is not None:
        if not isinstance(strategic_claims, list):
            errors.append("processing_behavior.context_inputs.strategic_claims must be an array")
            strategic_claims = []
        for index, row in enumerate(strategic_claims):
            if not isinstance(row, Mapping):
                errors.append(f"processing_behavior.context_inputs.strategic_claims[{index}] must be an object")
                continue
            if not _as_text(row.get("claim_id")):
                errors.append(f"processing_behavior.context_inputs.strategic_claims[{index}].claim_id is required")
            if _as_text(row.get("phase")) not in REQ_026_ALLOWED_CLAIM_PHASES:
                errors.append(
                    "processing_behavior.context_inputs.strategic_claims"
                    f"[{index}].phase must be one of {sorted(REQ_026_ALLOWED_CLAIM_PHASES)}"
                )
            if not _as_text(row.get("summary")):
                errors.append(f"processing_behavior.context_inputs.strategic_claims[{index}].summary is required")
            if not _as_text(row.get("position")):
                errors.append(f"processing_behavior.context_inputs.strategic_claims[{index}].position is required")
            sequence = row.get("source_call_sequence")
            if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1 or sequence > 6:
                errors.append(
                    "processing_behavior.context_inputs.strategic_claims"
                    f"[{index}].source_call_sequence must be an integer between 1 and 6"
                )
            evidence_refs = row.get("evidence_refs")
            if not isinstance(evidence_refs, list) or not evidence_refs or any(not _as_text(item) for item in evidence_refs):
                errors.append(
                    "processing_behavior.context_inputs.strategic_claims"
                    f"[{index}].evidence_refs must be a non-empty string array"
                )

    context_usage = processing_behavior.get("context_usage")
    if not isinstance(context_usage, Mapping):
        errors.append("processing_behavior.context_usage must be an object")
        context_usage = {}
    if not isinstance(context_usage.get("earth_sweep_context_used"), bool):
        errors.append("processing_behavior.context_usage.earth_sweep_context_used must be a boolean")
    if not isinstance(context_usage.get("cross_project_context_used"), bool):
        errors.append("processing_behavior.context_usage.cross_project_context_used must be a boolean")
    for key in (
        "source_call_ids_used",
        "cross_project_project_ids_used",
        "earth_sweep_evidence_refs_used",
        "recommendation_ids_considered",
        "kpi_ids_considered",
        "estimate_ids_emitted",
        "low_confidence_estimate_ids",
        "evidence_refs_used",
    ):
        value = context_usage.get(key)
        if not isinstance(value, list) or any(not _as_text(item) for item in value):
            errors.append(f"processing_behavior.context_usage.{key} must be a string array")
    for key in ("open_risk_ids_emitted", "reason_codes_emitted"):
        value = context_usage.get(key)
        if value is not None and (not isinstance(value, list) or any(not _as_text(item) for item in value)):
            errors.append(f"processing_behavior.context_usage.{key} must be a string array when present")
    caveat_count = context_usage.get("caveat_count")
    if not isinstance(caveat_count, int) or caveat_count < 0:
        errors.append("processing_behavior.context_usage.caveat_count must be a non-negative integer")
    if context_usage.get("recommendation_ids_considered") != recommendation_ids:
        errors.append("processing_behavior.context_usage.recommendation_ids_considered must match recommendation_adoptions")
    expected_cross_project_ids = sorted(
        {
            _as_text(row.get("project_id"))
            for row in recommendation_adoptions
            if isinstance(row, Mapping) and _as_text(row.get("project_id"))
        }
    )
    if context_usage.get("cross_project_project_ids_used") != expected_cross_project_ids:
        errors.append(
            "processing_behavior.context_usage.cross_project_project_ids_used must match cross-project recommendations"
        )
    if context_usage.get("cross_project_context_used") != bool(expected_cross_project_ids):
        errors.append(
            "processing_behavior.context_usage.cross_project_context_used must match cross-project recommendations"
        )
    if context_usage.get("estimate_ids_emitted") != estimate_ids:
        errors.append("processing_behavior.context_usage.estimate_ids_emitted must match kpi_estimates")
    if context_usage.get("low_confidence_estimate_ids") != low_confidence_estimate_ids:
        errors.append("processing_behavior.context_usage.low_confidence_estimate_ids must match low-confidence estimates")

    estimation_rules = processing_behavior.get("estimation_rules")
    if not isinstance(estimation_rules, Mapping):
        errors.append("processing_behavior.estimation_rules must be an object")
    else:
        if estimation_rules.get("confidence_scale") != ["high", "medium", "low"]:
            errors.append("processing_behavior.estimation_rules.confidence_scale must match the canonical list")
        if estimation_rules.get("required_estimate_fields") != REQ_031_REQUIRED_ESTIMATE_FIELDS:
            errors.append("processing_behavior.estimation_rules.required_estimate_fields must match the canonical list")
        for key in ("caveats_required", "bounded_range_required", "assumption_evidence_required"):
            if estimation_rules.get(key) is not True:
                errors.append(f"processing_behavior.estimation_rules.{key} must be true")

    diagnostics = processing_behavior.get("diagnostics")
    open_risks: list[Any] = []
    if diagnostics is not None:
        if not isinstance(diagnostics, Mapping):
            errors.append("processing_behavior.diagnostics must be an object")
        else:
            open_risks = diagnostics.get("open_risks") if isinstance(diagnostics.get("open_risks"), list) else []
            if not isinstance(diagnostics.get("open_risks"), list):
                errors.append("processing_behavior.diagnostics.open_risks must be an array")
            for index, row in enumerate(open_risks):
                if not isinstance(row, Mapping):
                    errors.append(f"processing_behavior.diagnostics.open_risks[{index}] must be an object")
                    continue
                if not _as_text(row.get("risk_id")):
                    errors.append(f"processing_behavior.diagnostics.open_risks[{index}].risk_id is required")
                if not _as_text(row.get("reason_code")):
                    errors.append(f"processing_behavior.diagnostics.open_risks[{index}].reason_code is required")
                if not _as_text(row.get("summary")):
                    errors.append(f"processing_behavior.diagnostics.open_risks[{index}].summary is required")
                required_evidence_refs = row.get("required_evidence_refs")
                if (
                    not isinstance(required_evidence_refs, list)
                    or not required_evidence_refs
                    or any(not _as_text(item) for item in required_evidence_refs)
                ):
                    errors.append(
                        "processing_behavior.diagnostics.open_risks"
                        f"[{index}].required_evidence_refs must be a non-empty string array"
                    )
            expected_open_risk_ids = [
                _as_text(row.get("risk_id")) for row in open_risks if isinstance(row, Mapping) and _as_text(row.get("risk_id"))
            ]
            expected_reason_codes = [
                _as_text(row.get("reason_code"))
                for row in open_risks
                if isinstance(row, Mapping) and _as_text(row.get("reason_code"))
            ]
            if context_usage.get("open_risk_ids_emitted") is not None and context_usage.get("open_risk_ids_emitted") != expected_open_risk_ids:
                errors.append("processing_behavior.context_usage.open_risk_ids_emitted must match diagnostics.open_risks")
            if context_usage.get("reason_codes_emitted") is not None and context_usage.get("reason_codes_emitted") != expected_reason_codes:
                errors.append("processing_behavior.context_usage.reason_codes_emitted must match diagnostics.open_risks")

    source = payload.get("source")
    if not isinstance(source, Mapping):
        errors.append("source must be an object")
    else:
        if source.get("recommendation_adoption_count") != len(recommendation_adoptions):
            errors.append("source.recommendation_adoption_count must match recommendation_adoptions length")
        unique_kpi_ids = {
            row.get("kpi_id") for row in kpi_estimates if isinstance(row, Mapping) and _as_text(row.get("kpi_id"))
        }
        if source.get("kpi_definition_count") != len(unique_kpi_ids):
            errors.append("source.kpi_definition_count must match unique kpi_ids in estimates")
        if source.get("impact_assumption_count") != len(kpi_estimates):
            errors.append("source.impact_assumption_count must match kpi_estimates length")
        if source.get("estimate_count") != len(kpi_estimates):
            errors.append("source.estimate_count must match kpi_estimates length")
        evidence_ref_count = source.get("evidence_ref_count")
        if not isinstance(evidence_ref_count, int) or evidence_ref_count <= 0:
            errors.append("source.evidence_ref_count must be a positive integer")
        earth_sweep_evidence_count = source.get("earth_sweep_evidence_count")
        if not isinstance(earth_sweep_evidence_count, int) or earth_sweep_evidence_count < 0:
            errors.append("source.earth_sweep_evidence_count must be a non-negative integer")

    metadata = payload.get("call_metadata")
    if metadata is not None:
        if not isinstance(metadata, Mapping):
            errors.append("call_metadata must be an object")
        else:
            if metadata.get("reproducibility") != "deterministic-input-fingerprint":
                errors.append("call_metadata.reproducibility must be deterministic-input-fingerprint")
            canonical_input = metadata.get("canonical_input")
            if not isinstance(canonical_input, Mapping):
                errors.append("call_metadata.canonical_input must be an object")
            else:
                expected_canonical_sha = _canonical_digest(canonical_input)
                if metadata.get("canonical_input_sha256") != expected_canonical_sha:
                    errors.append("call_metadata.canonical_input_sha256 does not match canonical_input")
            if metadata.get("llm_call_trace_schema_version") != REQ_031_LLM_CALL_TRACE_SCHEMA_VERSION:
                errors.append(
                    f"call_metadata.llm_call_trace_schema_version must be {REQ_031_LLM_CALL_TRACE_SCHEMA_VERSION}"
                )
            if metadata.get("llm_call_trace_path") != LLM_CALL_TRACE_RELATIVE_PATH:
                errors.append(f"call_metadata.llm_call_trace_path must be {LLM_CALL_TRACE_RELATIVE_PATH}")
            rows = metadata.get("llm_call_trace_rows")
            if not isinstance(rows, list) or len(rows) != 6:
                errors.append("call_metadata.llm_call_trace_rows must contain exactly six rows")
                rows = []
            for index, row in enumerate(rows):
                if not isinstance(row, Mapping):
                    errors.append(f"call_metadata.llm_call_trace_rows[{index}] must be an object")
                    continue
                if row.get("sequence") != index + 1:
                    errors.append(f"call_metadata.llm_call_trace_rows[{index}].sequence must be {index + 1}")
                for key in ("call_id", "call_objective", "handoff_summary"):
                    if not _as_text(row.get(key)):
                        errors.append(f"call_metadata.llm_call_trace_rows[{index}].{key} is required")
                for key in ("input_refs", "output_refs"):
                    value = row.get(key)
                    if not isinstance(value, list) or any(not _as_text(item) for item in value):
                        errors.append(
                            f"call_metadata.llm_call_trace_rows[{index}].{key} must be a string array"
                        )
            expected_trace_rows: list[dict[str, Any]] = []
            if isinstance(context_inputs, Mapping):
                try:
                    expected_trace_rows = _build_req_031_llm_call_trace_rows(
                        processing_call_id=_require_text(
                            metadata.get("processing_call_id"),
                            field_name="call_metadata.processing_call_id",
                        ),
                        call_chain=[
                            _require_mapping(row, field_name=f"processing_behavior.context_inputs.call_chain[{index}]")
                            for index, row in enumerate(context_inputs.get("call_chain", []))
                        ],
                        target_project_evidence_refs=[
                            _require_text(item, field_name=f"processing_behavior.context_inputs.target_project_evidence_refs[{index}]")
                            for index, item in enumerate(context_inputs.get("target_project_evidence_refs", []))
                        ],
                        earth_sweep_evidence_refs=[
                            _require_text(item, field_name=f"processing_behavior.context_inputs.earth_sweep_evidence_refs[{index}]")
                            for index, item in enumerate(context_inputs.get("earth_sweep_evidence_refs", []))
                        ],
                        strategic_claims=[
                            _require_mapping(row, field_name=f"processing_behavior.context_inputs.strategic_claims[{index}]")
                            for index, row in enumerate(context_inputs.get("strategic_claims", []))
                        ],
                        impact_assumptions=[
                            _require_mapping(row, field_name=f"processing_behavior.context_inputs.impact_assumptions[{index}]")
                            for index, row in enumerate(context_inputs.get("impact_assumptions", []))
                        ],
                        estimate_count=len(kpi_estimates),
                    )
                except ValueError as exc:
                    errors.append(f"call_metadata.llm_call_trace_rows could not be reconstructed: {exc}")
            if expected_trace_rows:
                if rows != expected_trace_rows:
                    errors.append("call_metadata.llm_call_trace_rows must mirror the deterministic per-call trace rows")
                expected_trace_sha = _canonical_digest(expected_trace_rows)
                if metadata.get("llm_call_trace_sha256") != expected_trace_sha:
                    errors.append("call_metadata.llm_call_trace_sha256 does not match llm_call_trace_rows")

    return errors


def _json_dumps(payload: Mapping[str, Any], *, pretty: bool) -> str:
    if pretty:
        return json.dumps(payload, indent=2, sort_keys=False) + "\n"
    return json.dumps(payload, separators=(",", ":"), sort_keys=False) + "\n"


def _jsonl_dumps(rows: Sequence[Mapping[str, Any]]) -> str:
    return "".join(f"{_canonical_json(row)}\n" for row in rows)


def _write_llm_call_trace(payload: Mapping[str, Any]) -> Path:
    metadata = _require_mapping(payload.get("call_metadata"), field_name="call_metadata")
    trace_path = REPO_ROOT / _require_text(metadata.get("llm_call_trace_path"), field_name="call_metadata.llm_call_trace_path")
    trace_rows = metadata.get("llm_call_trace_rows")
    if not isinstance(trace_rows, Sequence) or isinstance(trace_rows, (str, bytes, bytearray)):
        raise ValueError("call_metadata.llm_call_trace_rows must be an array before trace serialization")
    serialized_rows = _jsonl_dumps([_require_mapping(row, field_name=f"llm_call_trace_rows[{index}]") for index, row in enumerate(trace_rows)])
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(serialized_rows, encoding="utf-8")
    return trace_path


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


def _timestamped_print(message: str) -> None:
    line = f"[{TOOL} {utc_now_iso()}] {message}"
    print(line, file=sys.stderr, flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _parse_cli_input(input_path: str) -> Mapping[str, Any]:
    raw = sys.stdin.read() if input_path == "-" else Path(input_path).read_text(encoding="utf-8")
    payload = json.loads(raw)
    return _require_mapping(payload, field_name="input payload")


def _detect_requirement(payload: Mapping[str, Any]) -> str:
    if "impact_assumptions" in payload or payload.get("analysis_type") == REQ_031_ANALYSIS_TYPE:
        return REQ_031_REQUIREMENT_ID
    if "target_project_root" in payload:
        return REQ_025_REQUIREMENT_ID
    if "earlier_call_outputs" in payload or payload.get("analysis_type") == REQ_029_ANALYSIS_TYPE:
        return REQ_029_REQUIREMENT_ID
    if "target_project" in payload or payload.get("analysis_type") == REQ_026_ANALYSIS_TYPE:
        return REQ_026_REQUIREMENT_ID
    raise ValueError("input payload does not match REQ-025, REQ-026, REQ-029, or REQ-031 contract anchors")


def run(payload: Mapping[str, Any]) -> dict[str, Any]:
    requirement_id = _detect_requirement(payload)
    if requirement_id == REQ_031_REQUIREMENT_ID:
        return build_req_031_call_6_kpi_impact_estimation_reasoning(
            target_project=_require_mapping(payload.get("target_project"), field_name="input.target_project"),
            call_chain=payload.get("call_chain"),
            recommendation_adoptions=payload.get("recommendation_adoptions"),
            kpi_definitions=payload.get("kpi_definitions"),
            impact_assumptions=payload.get("impact_assumptions"),
            target_project_evidence_refs=payload.get("target_project_evidence_refs"),
            earth_sweep_evidence_refs=payload.get("earth_sweep_evidence_refs"),
            strategic_claims=payload.get("strategic_claims"),
            analysis_type=_as_text(payload.get("analysis_type")) or REQ_031_ANALYSIS_TYPE,
            call_id=_as_text(payload.get("call_id")) or REQ_031_CALL_ID,
            checked_at_utc=_as_text(payload.get("checked_at_utc")) or None,
        )
    if requirement_id == REQ_025_REQUIREMENT_ID:
        return build_req_025_multi_call_strategy_pipeline_planner(
            target_project_root=payload.get("target_project_root"),
            earth_root=payload.get("earth_root"),
            output_root=payload.get("output_root"),
            revision_identity=payload.get("revision_identity"),
            strategy_goal=payload.get("strategy_goal"),
            call_depth=payload.get("call_depth", DEFAULT_CALL_DEPTH),
            evidence_refs=payload.get("evidence_refs"),
            stage_blueprints=payload.get("stage_blueprints"),
            target_project_evidence_refs=payload.get("target_project_evidence_refs"),
            earth_sweep_evidence_refs=payload.get("earth_sweep_evidence_refs"),
            cross_project_context=payload.get("cross_project_context"),
            candidate_recommendations=payload.get("candidate_recommendations"),
            strategic_claims=payload.get("strategic_claims"),
        )
    if requirement_id == REQ_029_REQUIREMENT_ID:
        return build_req_029_call_4_recommendation_synthesis(
            target_project=_require_mapping(payload.get("target_project"), field_name="input.target_project"),
            earlier_call_outputs=payload.get("earlier_call_outputs", []),
            analysis_type=_as_text(payload.get("analysis_type")) or REQ_029_ANALYSIS_TYPE,
            call_id=_as_text(payload.get("call_id")) or REQ_029_CALL_ID,
            checked_at_utc=_as_text(payload.get("checked_at_utc")) or None,
        )
    return build_req_026_call_1_situational_analysis_reasoning(
        target_project=_require_mapping(payload.get("target_project"), field_name="input.target_project"),
        planning_evidence=_require_mapping(payload.get("planning_evidence"), field_name="input.planning_evidence"),
        runtime_evidence=_require_mapping(payload.get("runtime_evidence"), field_name="input.runtime_evidence"),
        broad_sweep_context=payload.get("broad_sweep_context"),
        analysis_type=_as_text(payload.get("analysis_type")) or REQ_026_ANALYSIS_TYPE,
        call_id=_as_text(payload.get("call_id")) or "call-1",
        checked_at_utc=_as_text(payload.get("checked_at_utc")) or None,
    )


def _validate_output(payload: Mapping[str, Any]) -> list[str]:
    requirement_id = _as_text(payload.get("requirement_id"))
    if requirement_id == REQ_031_REQUIREMENT_ID:
        return validate_req_031_call_6_kpi_impact_estimation_reasoning(payload)
    if requirement_id == REQ_025_REQUIREMENT_ID:
        return validate_req_025_multi_call_strategy_pipeline_planner(payload)
    if requirement_id == REQ_026_REQUIREMENT_ID:
        return validate_req_026_call_1_situational_analysis_reasoning(payload)
    if requirement_id == REQ_029_REQUIREMENT_ID:
        return validate_req_029_call_4_recommendation_synthesis(payload)
    return [f"unsupported requirement_id {requirement_id or '<missing>'}"]


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Emit REQ-025, REQ-026, REQ-029, or REQ-031 strategy pipeline payloads."
    )
    parser.add_argument("--input-json", required=True, help="Input JSON path or '-' for stdin.")
    parser.add_argument("--output-json", default="", help="Optional output JSON path.")
    parser.add_argument("--json-pretty", action="store_true", help="Pretty-print JSON output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    _enforce_log_budget(LOG_ROOT)

    try:
        input_payload = _parse_cli_input(args.input_json)
        requirement_id = _detect_requirement(input_payload)
        _timestamped_print(f"Starting {requirement_id} pipeline build from input source: {args.input_json}")
        output_payload = run(input_payload)
    except (Req026Error, Req029Error, Req031Error, ValueError, json.JSONDecodeError) as exc:
        requirement_id = (
            REQ_026_REQUIREMENT_ID
            if isinstance(exc, Req026Error)
            else REQ_029_REQUIREMENT_ID
            if isinstance(exc, Req029Error)
            else REQ_031_REQUIREMENT_ID if isinstance(exc, Req031Error) else ""
        )
        _timestamped_print(f"Pipeline input processing failed: {exc}")
        error_payload = {
            "ok": False,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "requirement_id": requirement_id,
            "reason_code": "input_error",
            "message": str(exc),
            "timestamp_utc": utc_now_iso(),
        }
        serialized_error = _json_dumps(error_payload, pretty=True)
        if args.output_json:
            Path(args.output_json).write_text(serialized_error, encoding="utf-8")
        print(serialized_error, end="")
        return 2

    validation_errors = _validate_output(output_payload)
    if validation_errors:
        requirement_id = _as_text(output_payload.get("requirement_id"))
        _timestamped_print(f"{requirement_id or 'strategy-pipeline'} produced invalid deterministic payload.")
        error_payload = {
            "ok": False,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "requirement_id": requirement_id,
            "reason_code": "validation_error",
            "message": "Payload failed deterministic validation checks.",
            "validation_errors": validation_errors,
            "timestamp_utc": utc_now_iso(),
        }
        serialized_error = _json_dumps(error_payload, pretty=True)
        if args.output_json:
            Path(args.output_json).write_text(serialized_error, encoding="utf-8")
        print(serialized_error, end="")
        return 3

    serialized_output = _json_dumps(output_payload, pretty=args.json_pretty)
    trace_output_path = _write_llm_call_trace(output_payload)
    requirement_id = _as_text(output_payload.get("requirement_id"))
    _timestamped_print(f"Wrote {requirement_id} call trace to {trace_output_path}")
    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialized_output, encoding="utf-8")
        _timestamped_print(f"Wrote {requirement_id} pipeline payload to {output_path}")
    else:
        _timestamped_print(f"{requirement_id} pipeline payload generated successfully and emitted to stdout.")
    print(serialized_output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
