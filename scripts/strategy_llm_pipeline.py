#!/usr/bin/env python3
"""REQ-025/REQ-028/REQ-032/REQ-033/REQ-037 contract/data-model surfaces for strategy pipeline artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
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
REQ_032_REQUIREMENT_ID = "REQ-032"
REQ_032_SCHEMA_VERSION = "req-032.call-7-blocker-and-risk-policy-reasoning.v1"
REQ_033_REQUIREMENT_ID = "REQ-033"
REQ_033_SCHEMA_VERSION = "req-033.call-8-constraint-classification-reasoning.v1"
REQ_028_REQUIREMENT_ID = "REQ-028"
REQ_028_SCHEMA_VERSION = "req-028.call-3-gap-and-opportunity-reasoning.v1"
REQ_037_REQUIREMENT_ID = "REQ-037"
REQ_037_SCHEMA_VERSION = "req-037.recommendation-deduplication-and-merge.v1"
RUNTIME_MODE = "llm-first"
EXECUTION_MODE = "long-thinking"
PIPELINE_STRATEGY = "multi-call-strategy-pipeline-planner"
REQ_032_STRATEGY = "call-7-blocker-and-risk-policy-reasoning"
REQ_033_STRATEGY = "call-8-constraint-classification-reasoning"
REQ_028_STRATEGY = "call-3-gap-and-opportunity-reasoning"
REQ_037_STRATEGY = "recommendation-deduplication-and-merge"
REQ_032_REASONING_FOCUS = "blocker-escalation-and-risk-policy-resolution"
REQ_032_CALL_SEQUENCE = 7
REQ_032_TRACE_CALL_OBJECTIVE = (
    "Reason about blocker escalation triggers and fallback sequencing paths before policy promotion."
)
REQ_032_TRACE_EXPECTED_OUTPUT = "call_7_blocker_and_risk_policy_reasoning"
REQ_033_REASONING_FOCUS = "planner-consumable-constraint-classification"
REQ_033_CALL_SEQUENCE = 8
REQ_033_TRACE_CALL_OBJECTIVE = (
    "Classify Call-8 strategy outputs into hard constraints, soft preferences, and speculative ideas "
    "without conflating planner obligations and suggestions."
)
REQ_033_TRACE_EXPECTED_OUTPUT = "call_8_constraint_classification_reasoning"
REQ_028_REASONING_FOCUS = "strategic-gaps-and-opportunities-beyond-local-mission"
REQ_028_CALL_SEQUENCE = 3
REQ_028_TRACE_CALL_OBJECTIVE = "Reason about strategic gaps and opportunities not visible from the local mission alone."
REQ_028_TRACE_EXPECTED_OUTPUT = "call_3_gap_and_opportunity_reasoning"
MIN_CALL_DEPTH = 1
MAX_CALL_DEPTH = 8
DEFAULT_CALL_DEPTH = 4
LLM_CALL_TRACE_RELATIVE_PATH = "strategy/current/llm_call_trace.jsonl"
DEFAULT_TARGET_PROJECT_ROOT = "/workspace/projects/optimus-prime"
DEFAULT_EARTH_ROOT = "/workspace/projects/Earth"
DEFAULT_OUTPUT_ROOT = "/workspace/projects/optimus-prime/strategy/out"
DEFAULT_REQ_032_REVISION_ID = "rev-req032-fixture-r1"
DEFAULT_REQ_033_REVISION_ID = "rev-req033-fixture-r1"
DEFAULT_REQ_037_REVISION_ID = "rev-req037-fixture-r1"

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


def _normalize_semantic_signature(value: Any, *, summary: str) -> str:
    text = _as_text(value)
    if text:
        return text.lower()
    normalized_summary = "".join(ch.lower() if ch.isalnum() else "-" for ch in summary)
    while "--" in normalized_summary:
        normalized_summary = normalized_summary.replace("--", "-")
    return normalized_summary.strip("-")


def _normalize_req_037_recommendation_drafts(raw_value: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError("recommendation_drafts must be an array")

    normalized: list[dict[str, Any]] = []
    recommendation_to_signature: dict[str, str] = {}
    signature_to_recommendation: dict[str, str] = {}
    seen_draft_ids: set[str] = set()

    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"recommendation_drafts[{index}] must be an object")
        draft_id = _require_text(item.get("draft_id"), field_name=f"recommendation_drafts[{index}].draft_id")
        if draft_id in seen_draft_ids:
            raise ValueError(f"recommendation_drafts[{index}].draft_id duplicates {draft_id}")
        seen_draft_ids.add(draft_id)
        recommendation_id = _require_text(
            item.get("recommendation_id"),
            field_name=f"recommendation_drafts[{index}].recommendation_id",
        )
        summary = _require_text(item.get("summary"), field_name=f"recommendation_drafts[{index}].summary")
        rationale = _require_text(item.get("rationale"), field_name=f"recommendation_drafts[{index}].rationale")
        semantic_signature = _normalize_semantic_signature(item.get("semantic_signature"), summary=summary)
        action_scope = _normalize_action_scope(
            item.get("action_scope"),
            field_name=f"recommendation_drafts[{index}].action_scope",
        )
        requires_earth_evidence = bool(item.get("requires_earth_evidence", action_scope == "cross-project"))
        project_id = _as_text(item.get("project_id"))
        next_step = _require_text(
            item.get("next_step")
            if item.get("next_step") is not None
            else f"Merge duplicate drafts for '{recommendation_id}' with deterministic evidence coverage.",
            field_name=f"recommendation_drafts[{index}].next_step",
        )
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            field_name=f"recommendation_drafts[{index}].evidence_refs",
            min_items=1,
        )

        existing_signature = recommendation_to_signature.get(recommendation_id)
        if existing_signature and existing_signature != semantic_signature:
            raise ValueError(
                "stable recommendation_id cannot map to multiple semantic signatures: "
                f"{recommendation_id}"
            )
        recommendation_to_signature[recommendation_id] = semantic_signature

        existing_recommendation = signature_to_recommendation.get(semantic_signature)
        if existing_recommendation and existing_recommendation != recommendation_id:
            raise ValueError(
                "semantic duplicate cannot map to multiple stable recommendation_ids: "
                f"{semantic_signature}"
            )
        signature_to_recommendation[semantic_signature] = recommendation_id

        normalized.append(
            {
                "draft_id": draft_id,
                "recommendation_id": recommendation_id,
                "semantic_signature": semantic_signature,
                "summary": summary,
                "rationale": rationale,
                "action_scope": action_scope,
                "requires_earth_evidence": requires_earth_evidence,
                "project_id": project_id,
                "evidence_refs": evidence_refs,
                "next_step": next_step,
            }
        )

    if not normalized:
        raise ValueError("recommendation_drafts must contain at least 1 item(s)")
    normalized.sort(key=lambda row: (row["recommendation_id"], row["semantic_signature"], row["draft_id"]))
    return normalized


def _build_req_037_merged_recommendations(
    recommendation_drafts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in recommendation_drafts:
        recommendation_id = _require_text(row.get("recommendation_id"), field_name="recommendation_drafts[].recommendation_id")
        semantic_signature = _require_text(
            row.get("semantic_signature"),
            field_name="recommendation_drafts[].semantic_signature",
        )
        grouped.setdefault((recommendation_id, semantic_signature), []).append(row)

    merged_rows: list[dict[str, Any]] = []
    for recommendation_id, semantic_signature in sorted(grouped.keys()):
        drafts = sorted(
            grouped[(recommendation_id, semantic_signature)],
            key=lambda row: _require_text(row.get("draft_id"), field_name="recommendation_drafts[].draft_id"),
        )
        canonical_summary = _require_text(drafts[0].get("summary"), field_name="recommendation_drafts[].summary")
        summary_variants = sorted(
            {
                _require_text(row.get("summary"), field_name="recommendation_drafts[].summary")
                for row in drafts
            }
        )
        source_rationales = [
            {
                "draft_id": _require_text(row.get("draft_id"), field_name="recommendation_drafts[].draft_id"),
                "rationale": _require_text(row.get("rationale"), field_name="recommendation_drafts[].rationale"),
                "evidence_refs": list(
                    _normalize_string_list(
                        row.get("evidence_refs"),
                        field_name="recommendation_drafts[].evidence_refs",
                        min_items=1,
                    )
                ),
            }
            for row in drafts
        ]
        merged_rows.append(
            {
                "recommendation_id": recommendation_id,
                "semantic_signature": semantic_signature,
                "summary": canonical_summary,
                "summary_variants": summary_variants,
                "merged_from_draft_ids": [row["draft_id"] for row in source_rationales],
                "source_rationales": source_rationales,
                "evidence_refs": _collect_unique_refs(*[row["evidence_refs"] for row in source_rationales]),
                "duplicate_count": len(drafts),
            }
        )
    return merged_rows


def _group_req_037_recommendation_drafts(
    recommendation_drafts: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], list[Mapping[str, Any]]]:
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in recommendation_drafts:
        recommendation_id = _require_text(row.get("recommendation_id"), field_name="recommendation_drafts[].recommendation_id")
        semantic_signature = _require_text(
            row.get("semantic_signature"),
            field_name="recommendation_drafts[].semantic_signature",
        )
        grouped.setdefault((recommendation_id, semantic_signature), []).append(row)
    return grouped


def _canonical_req_037_input(
    *,
    target_project_root: str,
    earth_root: str,
    output_root: str,
    revision_identity: str,
    merged_at: str,
) -> dict[str, Any]:
    return {
        "runtime_mode": RUNTIME_MODE,
        "execution_mode": EXECUTION_MODE,
        "target_project_root": target_project_root,
        "earth_root": earth_root,
        "output_root": output_root,
        "revision_identity": revision_identity,
        "merged_at": merged_at,
    }


def _canonical_req_037_processing_input(
    *,
    target_project_evidence_refs: list[str],
    earth_sweep_evidence_refs: list[str],
    cross_project_context: list[dict[str, Any]],
    recommendation_drafts: list[dict[str, Any]],
    strategic_claims: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    processing_input = {
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
        "recommendation_drafts": [
            {
                "draft_id": row["draft_id"],
                "recommendation_id": row["recommendation_id"],
                "semantic_signature": row["semantic_signature"],
                "summary": row["summary"],
                "rationale": row["rationale"],
                "action_scope": row["action_scope"],
                "requires_earth_evidence": row["requires_earth_evidence"],
                "project_id": row["project_id"],
                "evidence_refs": list(row["evidence_refs"]),
                "next_step": row["next_step"],
            }
            for row in recommendation_drafts
        ],
    }
    if strategic_claims:
        processing_input["strategic_claims"] = [
            {
                "claim_id": row["claim_id"],
                "phase": row["phase"],
                "summary": row["summary"],
                "position": row["position"],
                "source_output_ref": row["source_output_ref"],
                "evidence_refs": list(row["evidence_refs"]),
            }
            for row in strategic_claims
        ]
    return processing_input


def _req_037_recommendation_decision(
    *,
    merged_recommendations: Sequence[Mapping[str, Any]],
    open_risks: Sequence[Mapping[str, Any]],
) -> str:
    reason_codes = {_as_text(row.get("reason_code")) for row in open_risks}
    if {"cross_call_contradiction", "uncited_strategic_claim"}.intersection(reason_codes):
        return "resolve-strategy-gaps"
    return _recommendation_decision(
        recommended_actions=list(merged_recommendations),
        open_risks=list(open_risks),
    )


def _build_req_037_processing_behavior(
    *,
    target_project_root: str,
    earth_root: str,
    target_project_evidence_refs: list[str],
    earth_sweep_evidence_refs: list[str],
    cross_project_context: list[dict[str, Any]],
    recommendation_drafts: list[dict[str, Any]],
    merged_recommendations: list[dict[str, Any]],
    strategic_claims: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    grouped_drafts = _group_req_037_recommendation_drafts(recommendation_drafts)
    cross_project_refs = _collect_unique_refs(*[row["evidence_refs"] for row in cross_project_context])
    cross_project_obligations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    normalized_strategic_claims = list(strategic_claims or [])
    available_citation_refs = set(
        _collect_unique_refs(
            target_project_evidence_refs,
            earth_sweep_evidence_refs,
            cross_project_refs,
            *[row["evidence_refs"] for row in recommendation_drafts],
            *[row["evidence_refs"] for row in merged_recommendations],
        )
    )

    claim_rows_by_id: dict[str, list[dict[str, Any]]] = {}
    for claim in normalized_strategic_claims:
        claim_rows_by_id.setdefault(claim["claim_id"], []).append(claim)
        citation_refs = list(claim["evidence_refs"])
        if not citation_refs or not set(citation_refs).issubset(available_citation_refs):
            open_risks.append(
                {
                    "risk_id": f"risk-claim-{claim['claim_id']}-citation",
                    "summary": claim["summary"],
                    "reason_code": "uncited_strategic_claim",
                    "required_evidence_refs": _collect_unique_refs([claim["source_output_ref"]], citation_refs),
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
                        [analysis_row["source_output_ref"]],
                        [synthesis_row["source_output_ref"]],
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

    for merged_row in merged_recommendations:
        recommendation_id = _require_text(
            merged_row.get("recommendation_id"),
            field_name="merged_recommendations[].recommendation_id",
        )
        semantic_signature = _require_text(
            merged_row.get("semantic_signature"),
            field_name="merged_recommendations[].semantic_signature",
        )
        drafts = grouped_drafts[(recommendation_id, semantic_signature)]
        requires_earth_evidence = any(bool(row.get("requires_earth_evidence")) for row in drafts)
        if not requires_earth_evidence:
            continue

        merged_refs = list(merged_row["evidence_refs"])
        earth_refs = _collect_unique_refs(
            [ref for ref in merged_refs if _is_earth_evidence_ref(ref)],
            earth_sweep_evidence_refs,
        )
        if earth_refs:
            project_ids = sorted({_as_text(row.get("project_id")) for row in drafts if _as_text(row.get("project_id"))})
            obligation_project_id = project_ids[0] if project_ids else (
                cross_project_context[0]["project_id"] if cross_project_context else "earth"
            )
            cross_project_obligations.append(
                {
                    "obligation_id": f"obligation-{_slug_id_fragment(recommendation_id)}",
                    "project_id": obligation_project_id,
                    "summary": _require_text(merged_row.get("summary"), field_name="merged_recommendations[].summary"),
                    "evidence_refs": _collect_unique_refs(merged_refs, earth_refs),
                }
            )
            continue

        open_risks.append(
            {
                "risk_id": f"risk-{_slug_id_fragment(recommendation_id)}",
                "summary": _require_text(merged_row.get("summary"), field_name="merged_recommendations[].summary"),
                "reason_code": "missing_earth_sweep_evidence_refs",
                "required_evidence_refs": merged_refs,
            }
        )

    cross_project_obligations.sort(key=lambda row: row["obligation_id"])
    open_risks.sort(key=lambda row: row["risk_id"])
    recommendation_refs = _collect_unique_refs(
        target_project_evidence_refs,
        earth_sweep_evidence_refs,
        cross_project_refs,
        *[row["evidence_refs"] for row in merged_recommendations],
        *[row["evidence_refs"] for row in cross_project_obligations],
        *[row["required_evidence_refs"] for row in open_risks],
    )
    decision = _req_037_recommendation_decision(
        merged_recommendations=merged_recommendations,
        open_risks=open_risks,
    )

    context_inputs = {
        "target_project": {
            "project_root": target_project_root,
            "evidence_refs": list(target_project_evidence_refs),
        },
        "earth_sweep": {
            "earth_root": earth_root,
            "evidence_refs": list(earth_sweep_evidence_refs),
        },
        "cross_project_context": list(cross_project_context),
        "recommendation_drafts": list(recommendation_drafts),
    }
    if normalized_strategic_claims:
        context_inputs["strategic_claims"] = normalized_strategic_claims

    return {
        "strategy": REQ_037_STRATEGY,
        "reasoning_mode": EXECUTION_MODE,
        "strict_evidence_discipline": True,
        "heuristic_summarization_only": False,
        "context_inputs": context_inputs,
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
        "recommendation": {
            "decision": decision,
            "rationale": _recommendation_rationale(decision=decision),
            "confidence": _recommendation_confidence(evidence_refs=recommendation_refs, open_risks=open_risks),
            "evidence_refs": recommendation_refs,
            "merged_recommendations": list(merged_recommendations),
            "cross_project_obligations": cross_project_obligations,
            "open_risks": open_risks,
        },
        "summary": (
            "Merged duplicate recommendation drafts with broad-sweep context inputs, deterministic evidence refs, "
            "and explicit cross-project obligation gating."
        ),
    }


def _build_req_037_call_id(
    *,
    revision_identity: str,
    processing_input_sha: str,
    sequence: int,
    draft_id: str,
    recommendation_id: str,
    semantic_signature: str,
) -> str:
    material = "|".join(
        [
            revision_identity,
            processing_input_sha,
            str(sequence),
            draft_id,
            recommendation_id,
            semantic_signature,
        ]
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:10]
    return f"req037-call-{sequence:02d}-{digest}"


def _build_req_037_trace_expected_output(*, sequence: int, draft_id: str, recommendation_id: str) -> str:
    return (
        f"recommendation_merge_state_{sequence:02d}_"
        f"{_slug_id_fragment(recommendation_id)}_{_slug_id_fragment(draft_id)}"
    )


def _build_req_037_trace_handoff_summary(
    *,
    sequence: int,
    draft_id: str,
    recommendation_id: str,
    output_ref: str,
    input_ref_count: int,
    next_call_id: str,
    recommendation_decision: str,
    merged_recommendation_count: int,
) -> str:
    if next_call_id:
        return (
            f"Call {sequence} hands off draft {draft_id} for {recommendation_id} via {output_ref} "
            f"to {next_call_id} after consuming {input_ref_count} input refs."
        )
    return (
        f"Call {sequence} hands off draft {draft_id} for {recommendation_id} via {output_ref} "
        f"as the terminal merge output with recommendation decision {recommendation_decision} "
        f"across {merged_recommendation_count} merged recommendation(s)."
    )


def _build_req_037_llm_call_trace_rows(
    *,
    revision_identity: str,
    processing_input_sha: str,
    processing_call_id: str,
    target_project_evidence_refs: Sequence[str],
    earth_sweep_evidence_refs: Sequence[str],
    cross_project_context: Sequence[Mapping[str, Any]],
    recommendation_drafts: Sequence[Mapping[str, Any]],
    strategic_claims: Sequence[Mapping[str, Any]] | None,
    merged_recommendation_count: int,
    recommendation_decision: str,
) -> list[dict[str, Any]]:
    plan_id = f"req037-plan-{processing_input_sha[:16]}"
    shared_input_refs = _collect_unique_refs(
        target_project_evidence_refs,
        earth_sweep_evidence_refs,
        *[row["evidence_refs"] for row in cross_project_context],
        *[
            _collect_unique_refs([row.get("source_output_ref", "")], row.get("evidence_refs", []))
            for row in strategic_claims or []
            if isinstance(row, Mapping)
        ],
    )
    trace_call_specs: list[dict[str, Any]] = []
    output_ref_by_call_id: dict[str, str] = {}

    for sequence, row in enumerate(recommendation_drafts, start=1):
        draft_id = _require_text(row.get("draft_id"), field_name="recommendation_drafts[].draft_id")
        recommendation_id = _require_text(
            row.get("recommendation_id"),
            field_name="recommendation_drafts[].recommendation_id",
        )
        semantic_signature = _require_text(
            row.get("semantic_signature"),
            field_name="recommendation_drafts[].semantic_signature",
        )
        call_id = _build_req_037_call_id(
            revision_identity=revision_identity,
            processing_input_sha=processing_input_sha,
            sequence=sequence,
            draft_id=draft_id,
            recommendation_id=recommendation_id,
            semantic_signature=semantic_signature,
        )
        expected_output = _build_req_037_trace_expected_output(
            sequence=sequence,
            draft_id=draft_id,
            recommendation_id=recommendation_id,
        )
        output_ref_by_call_id[call_id] = _build_call_output_ref(
            plan_id=plan_id,
            call_id=call_id,
            expected_output=expected_output,
        )
        trace_call_specs.append(
            {
                "call_id": call_id,
                "sequence": sequence,
                "draft_id": draft_id,
                "recommendation_id": recommendation_id,
                "semantic_signature": semantic_signature,
                "expected_output": expected_output,
                "draft_evidence_refs": list(
                    _normalize_string_list(
                        row.get("evidence_refs"),
                        field_name="recommendation_drafts[].evidence_refs",
                        min_items=1,
                    )
                ),
            }
        )

    trace_rows: list[dict[str, Any]] = []
    for index, spec in enumerate(trace_call_specs):
        depends_on = [] if index == 0 else [trace_call_specs[index - 1]["call_id"]]
        dependency_output_refs = [output_ref_by_call_id[call_id] for call_id in depends_on]
        input_refs = _collect_unique_refs(
            shared_input_refs,
            spec["draft_evidence_refs"],
            dependency_output_refs,
        )
        output_ref = output_ref_by_call_id[spec["call_id"]]
        next_call_id = ""
        if index + 1 < len(trace_call_specs):
            next_call_id = trace_call_specs[index + 1]["call_id"]
        trace_rows.append(
            {
                "schema_version": REQ_025_LLM_CALL_TRACE_SCHEMA_VERSION,
                "requirement_id": REQ_037_REQUIREMENT_ID,
                "plan_id": plan_id,
                "processing_call_id": processing_call_id,
                "call_id": spec["call_id"],
                "sequence": spec["sequence"],
                "call_objective": (
                    f"Merge recommendation draft {spec['draft_id']} into stable recommendation "
                    f"{spec['recommendation_id']} while preserving rationale, evidence refs, and "
                    f"semantic signature {spec['semantic_signature']}."
                ),
                "depends_on": depends_on,
                "expected_output": spec["expected_output"],
                "input_refs": input_refs,
                "output_refs": [output_ref],
                "handoff_summary": _build_req_037_trace_handoff_summary(
                    sequence=spec["sequence"],
                    draft_id=spec["draft_id"],
                    recommendation_id=spec["recommendation_id"],
                    output_ref=output_ref,
                    input_ref_count=len(input_refs),
                    next_call_id=next_call_id,
                    recommendation_decision=recommendation_decision,
                    merged_recommendation_count=merged_recommendation_count,
                ),
            }
        )
    return trace_rows


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


def build_req_037_recommendation_deduplication_and_merge(
    *,
    recommendation_drafts: Sequence[Mapping[str, Any]] | None,
    strategic_claims: Sequence[Mapping[str, Any]] | None = None,
    target_project_root: str = DEFAULT_TARGET_PROJECT_ROOT,
    earth_root: str = DEFAULT_EARTH_ROOT,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    revision_identity: str = DEFAULT_REQ_037_REVISION_ID,
    target_project_evidence_refs: Sequence[Any] | None = None,
    earth_sweep_evidence_refs: Sequence[Any] | None = None,
    cross_project_context: Sequence[Mapping[str, Any]] | None = None,
    merged_at: str | None = None,
) -> dict[str, Any]:
    """Build the REQ-037 recommendation deduplication and merge surface."""
    normalized_target_root = _normalize_root(target_project_root, field_name="target_project_root")
    normalized_earth_root = _normalize_root(earth_root, field_name="earth_root")
    normalized_output_root = _normalize_root(output_root, field_name="output_root")
    normalized_revision_identity = _require_text(revision_identity, field_name="revision_identity")
    normalized_target_refs = _normalize_string_list(
        target_project_evidence_refs,
        field_name="target_project_evidence_refs",
    )
    normalized_earth_refs = _normalize_string_list(
        earth_sweep_evidence_refs,
        field_name="earth_sweep_evidence_refs",
    )
    normalized_cross_project_context = _normalize_cross_project_context(cross_project_context)
    normalized_drafts = _normalize_req_037_recommendation_drafts(recommendation_drafts)
    normalized_strategic_claims = _normalize_req_028_strategic_claims(strategic_claims)
    normalized_merged_at = _require_text(merged_at if merged_at is not None else utc_now_iso(), field_name="merged_at")
    merged_recommendations = _build_req_037_merged_recommendations(normalized_drafts)
    evidence_refs = _collect_unique_refs(*[row["evidence_refs"] for row in merged_recommendations])
    duplicate_group_count = sum(1 for row in merged_recommendations if int(row["duplicate_count"]) > 1)
    canonical_input = _canonical_req_037_input(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        output_root=normalized_output_root,
        revision_identity=normalized_revision_identity,
        merged_at=normalized_merged_at,
    )
    canonical_input_sha = _canonical_digest(canonical_input)
    canonical_processing_input = _canonical_req_037_processing_input(
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        cross_project_context=normalized_cross_project_context,
        recommendation_drafts=normalized_drafts,
        strategic_claims=normalized_strategic_claims,
    )
    processing_sha = _canonical_digest(canonical_processing_input)
    processing_behavior = _build_req_037_processing_behavior(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        cross_project_context=normalized_cross_project_context,
        recommendation_drafts=normalized_drafts,
        merged_recommendations=merged_recommendations,
        strategic_claims=normalized_strategic_claims,
    )
    llm_call_trace_rows = _build_req_037_llm_call_trace_rows(
        revision_identity=normalized_revision_identity,
        processing_input_sha=processing_sha,
        processing_call_id=f"req037-processing-{processing_sha[:16]}",
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        cross_project_context=normalized_cross_project_context,
        recommendation_drafts=normalized_drafts,
        strategic_claims=normalized_strategic_claims,
        merged_recommendation_count=len(merged_recommendations),
        recommendation_decision=_as_text(processing_behavior["recommendation"]["decision"]),
    )
    llm_call_trace_sha = _canonical_digest(llm_call_trace_rows)

    return {
        "requirement_id": REQ_037_REQUIREMENT_ID,
        "surface": "recommendation_deduplication_and_merge",
        "schema_version": REQ_037_SCHEMA_VERSION,
        "recommendation_deduplication_and_merge_entrypoint": {
            "runtime_mode": RUNTIME_MODE,
            "execution_mode": EXECUTION_MODE,
            "target_project_root": normalized_target_root,
            "earth_root": normalized_earth_root,
            "output_root": normalized_output_root,
            "revision_identity": normalized_revision_identity,
            "merged_at": normalized_merged_at,
        },
        "processing_behavior": processing_behavior,
        "call_metadata": {
            "reproducibility": "deterministic-input-fingerprint",
            "canonical_input_sha256": canonical_input_sha,
            "reproducible_call_id": f"req037-{canonical_input_sha[:16]}",
            "canonical_input": canonical_input,
            "processing_input_sha256": processing_sha,
            "processing_call_id": f"req037-processing-{processing_sha[:16]}",
            "canonical_processing_input": canonical_processing_input,
            "llm_call_trace_schema_version": REQ_025_LLM_CALL_TRACE_SCHEMA_VERSION,
            "llm_call_trace_path": LLM_CALL_TRACE_RELATIVE_PATH,
            "llm_call_trace_sha256": llm_call_trace_sha,
            "llm_call_trace_rows": llm_call_trace_rows,
        },
        "merged_at": normalized_merged_at,
        "deduplication_index": {
            "input_draft_count": len(normalized_drafts),
            "merged_recommendation_count": len(merged_recommendations),
            "duplicate_group_count": duplicate_group_count,
            "recommendation_ids": [row["recommendation_id"] for row in merged_recommendations],
            "semantic_signatures": [row["semantic_signature"] for row in merged_recommendations],
        },
        "merged_recommendations": merged_recommendations,
        "evidence_refs": evidence_refs,
        "summary": (
            f"{len(normalized_drafts)} draft(s) collapsed into {len(merged_recommendations)} "
            f"merged recommendation(s) across {duplicate_group_count} duplicate group(s)."
        ),
    }


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


def _collect_req_028_trace_input_refs(canonical_processing_input: Mapping[str, Any]) -> list[str]:
    cross_project_context = canonical_processing_input.get("cross_project_context")
    unresolved_ideas = canonical_processing_input.get("unresolved_ideas")
    gap_candidates = canonical_processing_input.get("gap_candidates")
    opportunity_candidates = canonical_processing_input.get("opportunity_candidates")
    strategic_claims = canonical_processing_input.get("strategic_claims")

    def _rows_to_refs(rows: Any) -> list[list[str]]:
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
            return []
        refs: list[list[str]] = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            row_refs = row.get("evidence_refs")
            if isinstance(row_refs, Sequence) and not isinstance(row_refs, (str, bytes, bytearray)):
                refs.append([_as_text(ref) for ref in row_refs if _as_text(ref)])
        return refs

    required_evidence_refs = canonical_processing_input.get("required_evidence_refs")
    if not isinstance(required_evidence_refs, Sequence) or isinstance(required_evidence_refs, (str, bytes, bytearray)):
        required_evidence_refs = []

    claim_refs: list[list[str]] = []
    claim_output_refs: list[str] = []
    if isinstance(strategic_claims, Sequence) and not isinstance(strategic_claims, (str, bytes, bytearray)):
        for row in strategic_claims:
            if not isinstance(row, Mapping):
                continue
            row_refs = row.get("evidence_refs")
            if isinstance(row_refs, Sequence) and not isinstance(row_refs, (str, bytes, bytearray)):
                claim_refs.append([_as_text(ref) for ref in row_refs if _as_text(ref)])
            source_output_ref = _as_text(row.get("source_output_ref"))
            if source_output_ref:
                claim_output_refs.append(source_output_ref)

    return _collect_unique_refs(
        [_as_text(ref) for ref in required_evidence_refs if _as_text(ref)],
        claim_output_refs,
        *claim_refs,
        *(_rows_to_refs(cross_project_context)),
        *(_rows_to_refs(unresolved_ideas)),
        *(_rows_to_refs(gap_candidates)),
        *(_rows_to_refs(opportunity_candidates)),
    )


def _build_req_028_llm_call_trace_rows(
    *,
    canonical_input_sha: str,
    processing_input_sha: str,
    processing_call_id: str,
    canonical_processing_input: Mapping[str, Any],
    gap_count: int,
    opportunity_count: int,
) -> list[dict[str, Any]]:
    plan_id = f"req028-plan-{processing_input_sha[:16]}"
    call_id = f"req028-call-{REQ_028_CALL_SEQUENCE:02d}-{canonical_input_sha[:10]}"
    output_ref = _build_call_output_ref(
        plan_id=plan_id,
        call_id=call_id,
        expected_output=REQ_028_TRACE_EXPECTED_OUTPUT,
    )
    return [
        {
            "schema_version": REQ_025_LLM_CALL_TRACE_SCHEMA_VERSION,
            "requirement_id": REQ_028_REQUIREMENT_ID,
            "plan_id": plan_id,
            "processing_call_id": processing_call_id,
            "call_id": call_id,
            "sequence": REQ_028_CALL_SEQUENCE,
            "call_objective": REQ_028_TRACE_CALL_OBJECTIVE,
            "depends_on": [],
            "expected_output": REQ_028_TRACE_EXPECTED_OUTPUT,
            "input_refs": _collect_req_028_trace_input_refs(canonical_processing_input),
            "output_refs": [output_ref],
            "handoff_summary": (
                f"Call {REQ_028_CALL_SEQUENCE} hands off {REQ_028_TRACE_EXPECTED_OUTPUT} via {output_ref} "
                f"after reasoning over {gap_count} ecosystem-visible gaps and "
                f"{opportunity_count} linked opportunities beyond the local mission."
            ),
        }
    ]


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


def validate_req_037_recommendation_deduplication_and_merge(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-037 payload shape and merge invariants."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    required_top = {
        "requirement_id",
        "surface",
        "schema_version",
        "recommendation_deduplication_and_merge_entrypoint",
        "processing_behavior",
        "call_metadata",
        "merged_at",
        "deduplication_index",
        "merged_recommendations",
        "evidence_refs",
        "summary",
    }
    top_keys = set(payload.keys())
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - required_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("requirement_id") != REQ_037_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_037_REQUIREMENT_ID}")
    if payload.get("surface") != "recommendation_deduplication_and_merge":
        errors.append("surface must be recommendation_deduplication_and_merge")
    if payload.get("schema_version") != REQ_037_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_037_SCHEMA_VERSION}")
    if not _as_text(payload.get("merged_at")):
        errors.append("merged_at must be a non-empty string")
    if not _as_text(payload.get("summary")):
        errors.append("summary must be a non-empty string")

    entrypoint = payload.get("recommendation_deduplication_and_merge_entrypoint")
    if not isinstance(entrypoint, Mapping):
        errors.append("recommendation_deduplication_and_merge_entrypoint must be an object")
        entrypoint = {}
    else:
        required_entrypoint = {
            "runtime_mode",
            "execution_mode",
            "target_project_root",
            "earth_root",
            "output_root",
            "revision_identity",
            "merged_at",
        }
        entrypoint_keys = set(entrypoint.keys())
        missing_entrypoint = sorted(required_entrypoint - entrypoint_keys)
        if missing_entrypoint:
            errors.append(f"recommendation_deduplication_and_merge_entrypoint missing keys: {missing_entrypoint}")
        unexpected_entrypoint = sorted(entrypoint_keys - required_entrypoint)
        if unexpected_entrypoint:
            errors.append(
                f"recommendation_deduplication_and_merge_entrypoint unexpected keys: {unexpected_entrypoint}"
            )
        if entrypoint.get("runtime_mode") != RUNTIME_MODE:
            errors.append(f"recommendation_deduplication_and_merge_entrypoint.runtime_mode must be {RUNTIME_MODE}")
        if entrypoint.get("execution_mode") != EXECUTION_MODE:
            errors.append(
                f"recommendation_deduplication_and_merge_entrypoint.execution_mode must be {EXECUTION_MODE}"
            )
        for root_field in ("target_project_root", "earth_root", "output_root"):
            root_value = entrypoint.get(root_field)
            if not isinstance(root_value, str) or not root_value.strip():
                errors.append(f"recommendation_deduplication_and_merge_entrypoint.{root_field} must be a non-empty string")
            elif not root_value.startswith("/"):
                errors.append(f"recommendation_deduplication_and_merge_entrypoint.{root_field} must be an absolute path")
        if not _as_text(entrypoint.get("revision_identity")):
            errors.append("recommendation_deduplication_and_merge_entrypoint.revision_identity must be non-empty")
        if _as_text(entrypoint.get("merged_at")) != _as_text(payload.get("merged_at")):
            errors.append("recommendation_deduplication_and_merge_entrypoint.merged_at must match merged_at")

    deduplication_index = payload.get("deduplication_index")
    merged_recommendations = payload.get("merged_recommendations")
    top_level_evidence_refs = payload.get("evidence_refs")
    if not isinstance(deduplication_index, Mapping):
        errors.append("deduplication_index must be an object")
        deduplication_index = {}
    if not isinstance(merged_recommendations, list):
        errors.append("merged_recommendations must be a list")
        merged_recommendations = []
    if not isinstance(top_level_evidence_refs, list):
        errors.append("evidence_refs must be a list")
        top_level_evidence_refs = []

    observed_pairs: list[tuple[str, str]] = []
    merged_evidence_groups: list[list[str]] = []
    recommendation_id_to_signature: dict[str, str] = {}
    signature_to_recommendation_id: dict[str, str] = {}
    duplicate_group_count = 0
    merged_draft_ids_seen: set[str] = set()

    for index, row in enumerate(merged_recommendations):
        if not isinstance(row, Mapping):
            errors.append(f"merged_recommendations[{index}] must be an object")
            continue
        recommendation_id = _as_text(row.get("recommendation_id"))
        semantic_signature = _as_text(row.get("semantic_signature")).lower()
        summary = _as_text(row.get("summary"))
        summary_variants = row.get("summary_variants")
        merged_from_draft_ids = row.get("merged_from_draft_ids")
        source_rationales = row.get("source_rationales")
        evidence_refs = row.get("evidence_refs")
        duplicate_count = row.get("duplicate_count")

        if not recommendation_id:
            errors.append(f"merged_recommendations[{index}].recommendation_id must be non-empty")
        if not semantic_signature:
            errors.append(f"merged_recommendations[{index}].semantic_signature must be non-empty")
        if not summary:
            errors.append(f"merged_recommendations[{index}].summary must be non-empty")

        normalized_summary_variants: list[str] = []
        if not isinstance(summary_variants, list) or not summary_variants:
            errors.append(f"merged_recommendations[{index}].summary_variants must be a non-empty list")
        else:
            normalized_summary_variants = sorted({_as_text(value) for value in summary_variants if _as_text(value)})
            if list(summary_variants) != normalized_summary_variants:
                errors.append(f"merged_recommendations[{index}].summary_variants must be sorted and unique")
            if summary and summary not in normalized_summary_variants:
                errors.append(f"merged_recommendations[{index}].summary must be present in summary_variants")

        normalized_merged_from_draft_ids: list[str] = []
        if not isinstance(merged_from_draft_ids, list) or not merged_from_draft_ids:
            errors.append(f"merged_recommendations[{index}].merged_from_draft_ids must be a non-empty list")
        else:
            normalized_merged_from_draft_ids = [_as_text(value) for value in merged_from_draft_ids if _as_text(value)]
            if list(merged_from_draft_ids) != sorted(normalized_merged_from_draft_ids):
                errors.append(f"merged_recommendations[{index}].merged_from_draft_ids must be sorted")
            for draft_id in normalized_merged_from_draft_ids:
                if draft_id in merged_draft_ids_seen:
                    errors.append(f"merged_recommendations[{index}].merged_from_draft_ids reuses {draft_id}")
                merged_draft_ids_seen.add(draft_id)

        normalized_source_draft_ids: list[str] = []
        source_evidence_groups: list[list[str]] = []
        if not isinstance(source_rationales, list) or not source_rationales:
            errors.append(f"merged_recommendations[{index}].source_rationales must be a non-empty list")
            source_rationales = []
        for source_index, source in enumerate(source_rationales):
            if not isinstance(source, Mapping):
                errors.append(f"merged_recommendations[{index}].source_rationales[{source_index}] must be an object")
                continue
            draft_id = _as_text(source.get("draft_id"))
            rationale = _as_text(source.get("rationale"))
            source_evidence_refs = source.get("evidence_refs")
            if not draft_id:
                errors.append(
                    f"merged_recommendations[{index}].source_rationales[{source_index}].draft_id must be non-empty"
                )
            else:
                normalized_source_draft_ids.append(draft_id)
            if not rationale:
                errors.append(
                    f"merged_recommendations[{index}].source_rationales[{source_index}].rationale must be non-empty"
                )
            if not isinstance(source_evidence_refs, list) or not source_evidence_refs:
                errors.append(
                    f"merged_recommendations[{index}].source_rationales[{source_index}].evidence_refs must be a non-empty list"
                )
                continue
            normalized_source_evidence_refs = sorted({_as_text(ref) for ref in source_evidence_refs if _as_text(ref)})
            if list(source_evidence_refs) != normalized_source_evidence_refs:
                errors.append(
                    f"merged_recommendations[{index}].source_rationales[{source_index}].evidence_refs must be sorted and unique"
                )
            source_evidence_groups.append(normalized_source_evidence_refs)

        normalized_evidence_refs: list[str] = []
        if not isinstance(evidence_refs, list) or not evidence_refs:
            errors.append(f"merged_recommendations[{index}].evidence_refs must be a non-empty list")
        else:
            normalized_evidence_refs = sorted({_as_text(ref) for ref in evidence_refs if _as_text(ref)})
            if list(evidence_refs) != normalized_evidence_refs:
                errors.append(f"merged_recommendations[{index}].evidence_refs must be sorted and unique")
            merged_evidence_groups.append(normalized_evidence_refs)

        if isinstance(duplicate_count, bool) or not isinstance(duplicate_count, int) or duplicate_count < 1:
            errors.append(f"merged_recommendations[{index}].duplicate_count must be an integer >= 1")
            duplicate_count = 1
        if int(duplicate_count) > 1:
            duplicate_group_count += 1

        if normalized_merged_from_draft_ids and normalized_source_draft_ids:
            if normalized_merged_from_draft_ids != normalized_source_draft_ids:
                errors.append(
                    f"merged_recommendations[{index}].merged_from_draft_ids must mirror source_rationales[].draft_id ordering"
                )
        if normalized_evidence_refs and source_evidence_groups:
            expected_evidence_refs = _collect_unique_refs(*source_evidence_groups)
            if normalized_evidence_refs != expected_evidence_refs:
                errors.append(
                    f"merged_recommendations[{index}].evidence_refs must equal the union of source_rationales[].evidence_refs"
                )
        if int(duplicate_count) != len(source_rationales):
            errors.append(f"merged_recommendations[{index}].duplicate_count must equal len(source_rationales)")

        existing_signature = recommendation_id_to_signature.get(recommendation_id)
        if recommendation_id and semantic_signature:
            if existing_signature and existing_signature != semantic_signature:
                errors.append(f"recommendation_id {recommendation_id} maps to multiple semantic signatures")
            recommendation_id_to_signature[recommendation_id] = semantic_signature
            existing_recommendation_id = signature_to_recommendation_id.get(semantic_signature)
            if existing_recommendation_id and existing_recommendation_id != recommendation_id:
                errors.append(f"semantic_signature {semantic_signature} maps to multiple recommendation_ids")
            signature_to_recommendation_id[semantic_signature] = recommendation_id
            observed_pairs.append((recommendation_id, semantic_signature))

    sorted_pairs = sorted(observed_pairs)
    sorted_recommendation_ids = [recommendation_id for recommendation_id, _ in sorted_pairs]
    sorted_semantic_signatures = [semantic_signature for _, semantic_signature in sorted_pairs]
    if observed_pairs != sorted_pairs:
        errors.append("merged_recommendations must be sorted by recommendation_id and semantic_signature")

    normalized_top_level_evidence_refs = sorted({_as_text(ref) for ref in top_level_evidence_refs if _as_text(ref)})
    if list(top_level_evidence_refs) != normalized_top_level_evidence_refs:
        errors.append("evidence_refs must be sorted and unique")
    expected_top_level_evidence_refs = _collect_unique_refs(*merged_evidence_groups)
    if normalized_top_level_evidence_refs != expected_top_level_evidence_refs:
        errors.append("evidence_refs must equal the union of merged_recommendations[].evidence_refs")

    if deduplication_index.get("input_draft_count") != len(merged_draft_ids_seen):
        errors.append("deduplication_index.input_draft_count must equal the merged draft count")
    if deduplication_index.get("merged_recommendation_count") != len(merged_recommendations):
        errors.append("deduplication_index.merged_recommendation_count must equal len(merged_recommendations)")
    if deduplication_index.get("duplicate_group_count") != duplicate_group_count:
        errors.append("deduplication_index.duplicate_group_count must match duplicate_count > 1 groups")
    if deduplication_index.get("recommendation_ids") != sorted_recommendation_ids:
        errors.append("deduplication_index.recommendation_ids must mirror merged recommendation IDs")
    if deduplication_index.get("semantic_signatures") != sorted_semantic_signatures:
        errors.append("deduplication_index.semantic_signatures must mirror merged semantic signatures")

    processing_behavior = payload.get("processing_behavior")
    normalized_cross_project_context: list[dict[str, Any]] = []
    normalized_recommendation_drafts: list[dict[str, Any]] = []
    normalized_strategic_claims: list[dict[str, Any]] = []
    target_project_refs_from_context: list[str] = []
    earth_sweep_refs_from_context: list[str] = []
    recommendation_refs: list[str] = []
    if not isinstance(processing_behavior, Mapping):
        errors.append("processing_behavior must be an object")
        processing_behavior = {}
    else:
        required_processing = {
            "strategy",
            "reasoning_mode",
            "strict_evidence_discipline",
            "heuristic_summarization_only",
            "context_inputs",
            "context_usage",
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
        if processing_behavior.get("strategy") != REQ_037_STRATEGY:
            errors.append(f"processing_behavior.strategy must be {REQ_037_STRATEGY}")
        if processing_behavior.get("reasoning_mode") != EXECUTION_MODE:
            errors.append(f"processing_behavior.reasoning_mode must be {EXECUTION_MODE}")
        if processing_behavior.get("strict_evidence_discipline") is not True:
            errors.append("processing_behavior.strict_evidence_discipline must be true")
        if processing_behavior.get("heuristic_summarization_only") is not False:
            errors.append("processing_behavior.heuristic_summarization_only must be false")
        if not _as_text(processing_behavior.get("summary")):
            errors.append("processing_behavior.summary must be a non-empty string")

        context_inputs = processing_behavior.get("context_inputs")
        if not isinstance(context_inputs, Mapping):
            errors.append("processing_behavior.context_inputs must be an object")
            context_inputs = {}
        target_project = context_inputs.get("target_project")
        if not isinstance(target_project, Mapping):
            errors.append("processing_behavior.context_inputs.target_project must be an object")
        else:
            if target_project.get("project_root") != entrypoint.get("target_project_root"):
                errors.append(
                    "processing_behavior.context_inputs.target_project.project_root must match entrypoint.target_project_root"
                )
            try:
                target_project_refs_from_context = _normalize_string_list(
                    target_project.get("evidence_refs"),
                    field_name="processing_behavior.context_inputs.target_project.evidence_refs",
                )
            except ValueError:
                errors.append("processing_behavior.context_inputs.target_project.evidence_refs must be a list")

        earth_sweep = context_inputs.get("earth_sweep")
        if not isinstance(earth_sweep, Mapping):
            errors.append("processing_behavior.context_inputs.earth_sweep must be an object")
        else:
            if earth_sweep.get("earth_root") != entrypoint.get("earth_root"):
                errors.append("processing_behavior.context_inputs.earth_sweep.earth_root must match entrypoint.earth_root")
            try:
                earth_sweep_refs_from_context = _normalize_string_list(
                    earth_sweep.get("evidence_refs"),
                    field_name="processing_behavior.context_inputs.earth_sweep.evidence_refs",
                )
            except ValueError:
                errors.append("processing_behavior.context_inputs.earth_sweep.evidence_refs must be a list")

        try:
            normalized_cross_project_context = _normalize_cross_project_context(context_inputs.get("cross_project_context"))
        except ValueError as exc:
            errors.append(str(exc).replace("cross_project_context", "processing_behavior.context_inputs.cross_project_context"))
        try:
            normalized_recommendation_drafts = _normalize_req_037_recommendation_drafts(
                context_inputs.get("recommendation_drafts")
            )
        except ValueError as exc:
            errors.append(str(exc).replace("recommendation_drafts", "processing_behavior.context_inputs.recommendation_drafts"))
        try:
            normalized_strategic_claims = _normalize_req_028_strategic_claims(context_inputs.get("strategic_claims"))
        except ValueError as exc:
            errors.append(str(exc).replace("strategic_claims", "processing_behavior.context_inputs.strategic_claims"))

        context_usage = processing_behavior.get("context_usage")
        if not isinstance(context_usage, Mapping):
            errors.append("processing_behavior.context_usage must be an object")
        else:
            required_usage = {
                "target_project_context_used",
                "earth_sweep_context_used",
                "cross_project_context_used",
                "target_project_refs_used",
                "earth_sweep_refs_used",
                "cross_project_refs_used",
                "cross_project_projects_considered",
                "evidence_refs_used",
            }
            usage_keys = set(context_usage.keys())
            missing_usage = sorted(required_usage - usage_keys)
            if missing_usage:
                errors.append(f"processing_behavior.context_usage missing keys: {missing_usage}")
            unexpected_usage = sorted(usage_keys - required_usage)
            if unexpected_usage:
                errors.append(f"processing_behavior.context_usage unexpected keys: {unexpected_usage}")
            if context_usage.get("target_project_context_used") != bool(target_project_refs_from_context):
                errors.append("processing_behavior.context_usage.target_project_context_used is inconsistent")
            if context_usage.get("earth_sweep_context_used") != bool(earth_sweep_refs_from_context):
                errors.append("processing_behavior.context_usage.earth_sweep_context_used is inconsistent")
            if context_usage.get("cross_project_context_used") != bool(normalized_cross_project_context):
                errors.append("processing_behavior.context_usage.cross_project_context_used is inconsistent")
            if context_usage.get("target_project_refs_used") != target_project_refs_from_context:
                errors.append("processing_behavior.context_usage.target_project_refs_used must mirror context inputs")
            if context_usage.get("earth_sweep_refs_used") != earth_sweep_refs_from_context:
                errors.append("processing_behavior.context_usage.earth_sweep_refs_used must mirror context inputs")
            expected_cross_project_refs = _collect_unique_refs(
                *[row["evidence_refs"] for row in normalized_cross_project_context]
            )
            if context_usage.get("cross_project_refs_used") != expected_cross_project_refs:
                errors.append("processing_behavior.context_usage.cross_project_refs_used must mirror context inputs")
            if context_usage.get("cross_project_projects_considered") != [
                row["project_id"] for row in normalized_cross_project_context
            ]:
                errors.append(
                    "processing_behavior.context_usage.cross_project_projects_considered must mirror normalized context"
                )

        recommendation = processing_behavior.get("recommendation")
        if not isinstance(recommendation, Mapping):
            errors.append("processing_behavior.recommendation must be an object")
        else:
            required_recommendation = {
                "decision",
                "rationale",
                "confidence",
                "evidence_refs",
                "merged_recommendations",
                "cross_project_obligations",
                "open_risks",
            }
            recommendation_keys = set(recommendation.keys())
            missing_recommendation = sorted(required_recommendation - recommendation_keys)
            if missing_recommendation:
                errors.append(f"processing_behavior.recommendation missing keys: {missing_recommendation}")
            unexpected_recommendation = sorted(recommendation_keys - required_recommendation)
            if unexpected_recommendation:
                errors.append(f"processing_behavior.recommendation unexpected keys: {unexpected_recommendation}")
            if not _as_text(recommendation.get("decision")):
                errors.append("processing_behavior.recommendation.decision must be non-empty")
            if not _as_text(recommendation.get("rationale")):
                errors.append("processing_behavior.recommendation.rationale must be non-empty")
            if _as_text(recommendation.get("confidence")) not in {"low", "medium", "high"}:
                errors.append("processing_behavior.recommendation.confidence must be low|medium|high")
            recommendation_refs_value = recommendation.get("evidence_refs")
            if not isinstance(recommendation_refs_value, list) or not recommendation_refs_value:
                errors.append("processing_behavior.recommendation.evidence_refs must be a non-empty list")
            else:
                recommendation_refs = sorted({_as_text(ref) for ref in recommendation_refs_value if _as_text(ref)})
                if recommendation_refs_value != recommendation_refs:
                    errors.append("processing_behavior.recommendation.evidence_refs must be sorted and unique")
            if recommendation.get("merged_recommendations") != merged_recommendations:
                errors.append("processing_behavior.recommendation.merged_recommendations must mirror top-level merged_recommendations")

            obligations = recommendation.get("cross_project_obligations")
            if not isinstance(obligations, list):
                errors.append("processing_behavior.recommendation.cross_project_obligations must be a list")
                obligations = []
            for index, row in enumerate(obligations):
                if not isinstance(row, Mapping):
                    errors.append(f"processing_behavior.recommendation.cross_project_obligations[{index}] must be an object")
                    continue
                evidence_refs = row.get("evidence_refs")
                if not isinstance(evidence_refs, list) or not evidence_refs:
                    errors.append(
                        f"processing_behavior.recommendation.cross_project_obligations[{index}].evidence_refs must be non-empty list"
                    )
                    continue
                if not any(_is_earth_evidence_ref(_as_text(ref)) for ref in evidence_refs):
                    errors.append(
                        f"processing_behavior.recommendation.cross_project_obligations[{index}] must include earth_sweep evidence refs"
                    )

            open_risks = recommendation.get("open_risks")
            if not isinstance(open_risks, list):
                errors.append("processing_behavior.recommendation.open_risks must be a list")
                open_risks = []
            for index, row in enumerate(open_risks):
                if not isinstance(row, Mapping):
                    errors.append(f"processing_behavior.recommendation.open_risks[{index}] must be an object")
                    continue
                if not _as_text(row.get("risk_id")):
                    errors.append(f"processing_behavior.recommendation.open_risks[{index}].risk_id must be non-empty")
                if not _as_text(row.get("summary")):
                    errors.append(f"processing_behavior.recommendation.open_risks[{index}].summary must be non-empty")
                if not _as_text(row.get("reason_code")):
                    errors.append(f"processing_behavior.recommendation.open_risks[{index}].reason_code must be non-empty")
                required_evidence_refs = row.get("required_evidence_refs")
                if not isinstance(required_evidence_refs, list) or not required_evidence_refs:
                    errors.append(
                        f"processing_behavior.recommendation.open_risks[{index}].required_evidence_refs must be non-empty list"
                    )

            expected_recommendation_refs = _collect_unique_refs(
                target_project_refs_from_context,
                earth_sweep_refs_from_context,
                *[row["evidence_refs"] for row in normalized_cross_project_context],
                *[
                    row["evidence_refs"]
                    for row in merged_recommendations
                    if isinstance(row, Mapping) and isinstance(row.get("evidence_refs"), list)
                ],
                *[
                    row["evidence_refs"]
                    for row in obligations
                    if isinstance(row, Mapping) and isinstance(row.get("evidence_refs"), list)
                ],
                *[
                    row["required_evidence_refs"]
                    for row in open_risks
                    if isinstance(row, Mapping) and isinstance(row.get("required_evidence_refs"), list)
                ],
            )
            if recommendation_refs and recommendation_refs != expected_recommendation_refs:
                errors.append("processing_behavior.recommendation.evidence_refs must equal the deterministic evidence union")
            if isinstance(context_usage, Mapping) and context_usage.get("evidence_refs_used") != recommendation_refs:
                errors.append("processing_behavior.context_usage.evidence_refs_used must mirror recommendation.evidence_refs")

    metadata = payload.get("call_metadata")
    if not isinstance(metadata, Mapping):
        errors.append("call_metadata must be an object")
        metadata = {}
    else:
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
        else:
            expected_canonical_input = _canonical_req_037_input(
                target_project_root=_as_text(entrypoint.get("target_project_root")),
                earth_root=_as_text(entrypoint.get("earth_root")),
                output_root=_as_text(entrypoint.get("output_root")),
                revision_identity=_as_text(entrypoint.get("revision_identity")),
                merged_at=_as_text(payload.get("merged_at")),
            )
            if dict(canonical_input) != expected_canonical_input:
                errors.append("call_metadata.canonical_input must mirror normalized invocation anchors")
            expected_input_sha = _canonical_digest(expected_canonical_input)
            if metadata.get("canonical_input_sha256") != expected_input_sha:
                errors.append("call_metadata.canonical_input_sha256 does not match canonical input")
            if metadata.get("reproducible_call_id") != f"req037-{expected_input_sha[:16]}":
                errors.append("call_metadata.reproducible_call_id does not match canonical digest")

        canonical_processing_input = metadata.get("canonical_processing_input")
        if not isinstance(canonical_processing_input, Mapping):
            errors.append("call_metadata.canonical_processing_input must be an object")
        else:
            expected_processing_input = _canonical_req_037_processing_input(
                target_project_evidence_refs=target_project_refs_from_context,
                earth_sweep_evidence_refs=earth_sweep_refs_from_context,
                cross_project_context=normalized_cross_project_context,
                recommendation_drafts=normalized_recommendation_drafts,
                strategic_claims=normalized_strategic_claims,
            )
            if dict(canonical_processing_input) != expected_processing_input:
                errors.append("call_metadata.canonical_processing_input must mirror processing inputs")
            expected_processing_sha = _canonical_digest(expected_processing_input)
            if metadata.get("processing_input_sha256") != expected_processing_sha:
                errors.append("call_metadata.processing_input_sha256 does not match processing input")
            if metadata.get("processing_call_id") != f"req037-processing-{expected_processing_sha[:16]}":
                errors.append("call_metadata.processing_call_id does not match processing digest")
            if metadata.get("llm_call_trace_schema_version") != REQ_025_LLM_CALL_TRACE_SCHEMA_VERSION:
                errors.append(
                    f"call_metadata.llm_call_trace_schema_version must be {REQ_025_LLM_CALL_TRACE_SCHEMA_VERSION}"
                )
            if metadata.get("llm_call_trace_path") != LLM_CALL_TRACE_RELATIVE_PATH:
                errors.append(f"call_metadata.llm_call_trace_path must be {LLM_CALL_TRACE_RELATIVE_PATH}")
            expected_trace_rows = _build_req_037_llm_call_trace_rows(
                revision_identity=_as_text(entrypoint.get("revision_identity")),
                processing_input_sha=expected_processing_sha,
                processing_call_id=f"req037-processing-{expected_processing_sha[:16]}",
                target_project_evidence_refs=target_project_refs_from_context,
                earth_sweep_evidence_refs=earth_sweep_refs_from_context,
                cross_project_context=normalized_cross_project_context,
                recommendation_drafts=normalized_recommendation_drafts,
                strategic_claims=normalized_strategic_claims,
                merged_recommendation_count=len(merged_recommendations),
                recommendation_decision=_as_text(
                    processing_behavior.get("recommendation", {}).get("decision")
                    if isinstance(processing_behavior.get("recommendation"), Mapping)
                    else ""
                ),
            )
            if metadata.get("llm_call_trace_rows") != expected_trace_rows:
                errors.append("call_metadata.llm_call_trace_rows must mirror deterministic REQ-037 trace rows")
            if metadata.get("llm_call_trace_sha256") != _canonical_digest(expected_trace_rows):
                errors.append("call_metadata.llm_call_trace_sha256 does not match llm_call_trace_rows")

    return errors


def _normalize_req_032_call_sequence(raw_value: Any) -> int:
    if isinstance(raw_value, bool) or not isinstance(raw_value, int):
        raise ValueError("call_sequence must be an integer")
    if raw_value != REQ_032_CALL_SEQUENCE:
        raise ValueError(f"call_sequence must be {REQ_032_CALL_SEQUENCE}")
    return raw_value


def _normalize_req_032_blocker_severity(value: Any, *, field_name: str) -> str:
    severity = _require_text(value, field_name=field_name).lower()
    if severity not in {"low", "medium", "high", "critical"}:
        raise ValueError(f"{field_name} must be low|medium|high|critical")
    return severity


def _normalize_req_032_escalation_triggers(raw_value: Any, *, field_name: str) -> list[dict[str, Any]]:
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be an array")

    normalized: list[dict[str, Any]] = []
    seen_trigger_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"{field_name}[{index}] must be an object")
        trigger_id = _require_text(item.get("trigger_id"), field_name=f"{field_name}[{index}].trigger_id")
        if trigger_id in seen_trigger_ids:
            raise ValueError(f"{field_name}[{index}].trigger_id must be unique")
        seen_trigger_ids.add(trigger_id)
        project_id = _require_text(item.get("project_id"), field_name=f"{field_name}[{index}].project_id")
        summary = _require_text(item.get("summary"), field_name=f"{field_name}[{index}].summary")
        fire_when = _require_text(item.get("fire_when"), field_name=f"{field_name}[{index}].fire_when")
        urgency = _normalize_req_032_blocker_severity(item.get("urgency"), field_name=f"{field_name}[{index}].urgency")
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            field_name=f"{field_name}[{index}].evidence_refs",
            min_items=1,
        )
        normalized.append(
            {
                "trigger_id": trigger_id,
                "project_id": project_id,
                "summary": summary,
                "fire_when": fire_when,
                "urgency": urgency,
                "evidence_refs": evidence_refs,
            }
        )
    if not normalized:
        raise ValueError(f"{field_name} must contain at least 1 item(s)")
    normalized.sort(key=lambda row: row["trigger_id"])
    return normalized


def _normalize_req_032_fallback_paths(raw_value: Any, *, field_name: str) -> list[dict[str, Any]]:
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be an array")

    normalized: list[dict[str, Any]] = []
    seen_fallback_ids: set[str] = set()
    seen_sequence: set[int] = set()
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"{field_name}[{index}] must be an object")
        fallback_id = _require_text(item.get("fallback_id"), field_name=f"{field_name}[{index}].fallback_id")
        if fallback_id in seen_fallback_ids:
            raise ValueError(f"{field_name}[{index}].fallback_id must be unique")
        seen_fallback_ids.add(fallback_id)
        sequence = item.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
            raise ValueError(f"{field_name}[{index}].sequence must be an integer >= 1")
        if sequence in seen_sequence:
            raise ValueError(f"{field_name}[{index}].sequence must be unique")
        seen_sequence.add(sequence)
        summary = _require_text(item.get("summary"), field_name=f"{field_name}[{index}].summary")
        activates_when = _require_text(
            item.get("activates_when"),
            field_name=f"{field_name}[{index}].activates_when",
        )
        next_step = _require_text(item.get("next_step"), field_name=f"{field_name}[{index}].next_step")
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            field_name=f"{field_name}[{index}].evidence_refs",
            min_items=1,
        )
        normalized.append(
            {
                "fallback_id": fallback_id,
                "sequence": sequence,
                "summary": summary,
                "activates_when": activates_when,
                "next_step": next_step,
                "evidence_refs": evidence_refs,
            }
        )
    if not normalized:
        raise ValueError(f"{field_name} must contain at least 1 item(s)")
    normalized.sort(key=lambda row: (row["sequence"], row["fallback_id"]))
    return normalized


def _normalize_req_032_blocker_candidates(raw_value: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError("blocker_candidates must be an array")

    normalized: list[dict[str, Any]] = []
    seen_blocker_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"blocker_candidates[{index}] must be an object")
        blocker_id = _require_text(item.get("blocker_id"), field_name=f"blocker_candidates[{index}].blocker_id")
        if blocker_id in seen_blocker_ids:
            raise ValueError(f"blocker_candidates[{index}].blocker_id must be unique")
        seen_blocker_ids.add(blocker_id)
        summary = _require_text(item.get("summary"), field_name=f"blocker_candidates[{index}].summary")
        severity = _normalize_req_032_blocker_severity(
            item.get("severity"),
            field_name=f"blocker_candidates[{index}].severity",
        )
        affected_project_ids = _normalize_string_list(
            item.get("affected_project_ids"),
            field_name=f"blocker_candidates[{index}].affected_project_ids",
            min_items=1,
        )
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            field_name=f"blocker_candidates[{index}].evidence_refs",
            min_items=1,
        )
        escalation_triggers = _normalize_req_032_escalation_triggers(
            item.get("escalation_triggers"),
            field_name=f"blocker_candidates[{index}].escalation_triggers",
        )
        fallback_paths = _normalize_req_032_fallback_paths(
            item.get("fallback_paths"),
            field_name=f"blocker_candidates[{index}].fallback_paths",
        )
        normalized.append(
            {
                "blocker_id": blocker_id,
                "summary": summary,
                "severity": severity,
                "affected_project_ids": affected_project_ids,
                "evidence_refs": evidence_refs,
                "escalation_triggers": escalation_triggers,
                "fallback_paths": fallback_paths,
            }
        )
    if not normalized:
        raise ValueError("blocker_candidates must contain at least 1 item(s)")
    normalized.sort(key=lambda row: row["blocker_id"])
    return normalized


def _normalize_req_032_policy_decision(value: Any, *, field_name: str) -> str:
    decision = _require_text(value, field_name=field_name).lower()
    if decision not in {"monitor", "mitigate-locally", "fallback-then-escalate", "escalate-immediately"}:
        raise ValueError(
            f"{field_name} must be monitor|mitigate-locally|fallback-then-escalate|escalate-immediately"
        )
    return decision


def _normalize_req_032_risk_policy_candidates(
    raw_value: Any,
    *,
    blocker_candidates: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError("risk_policy_candidates must be an array")

    blocker_index = {
        _require_text(row.get("blocker_id"), field_name="blocker_candidates[].blocker_id"): row for row in blocker_candidates
    }
    normalized: list[dict[str, Any]] = []
    seen_policy_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"risk_policy_candidates[{index}] must be an object")
        policy_id = _require_text(item.get("policy_id"), field_name=f"risk_policy_candidates[{index}].policy_id")
        if policy_id in seen_policy_ids:
            raise ValueError(f"risk_policy_candidates[{index}].policy_id must be unique")
        seen_policy_ids.add(policy_id)
        blocker_id = _require_text(item.get("blocker_id"), field_name=f"risk_policy_candidates[{index}].blocker_id")
        blocker = blocker_index.get(blocker_id)
        if blocker is None:
            raise ValueError(f"risk_policy_candidates[{index}].blocker_id must reference a known blocker_id")
        policy_decision = _normalize_req_032_policy_decision(
            item.get("policy_decision"),
            field_name=f"risk_policy_candidates[{index}].policy_decision",
        )
        rationale = _require_text(item.get("rationale"), field_name=f"risk_policy_candidates[{index}].rationale")
        preferred_fallback_ids = _normalize_string_list(
            item.get("preferred_fallback_ids"),
            field_name=f"risk_policy_candidates[{index}].preferred_fallback_ids",
        )
        escalation_trigger_ids = _normalize_string_list(
            item.get("escalation_trigger_ids"),
            field_name=f"risk_policy_candidates[{index}].escalation_trigger_ids",
        )
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            field_name=f"risk_policy_candidates[{index}].evidence_refs",
            min_items=1,
        )

        blocker_fallback_ids = {row["fallback_id"] for row in blocker.get("fallback_paths", []) if isinstance(row, Mapping)}
        blocker_trigger_ids = {row["trigger_id"] for row in blocker.get("escalation_triggers", []) if isinstance(row, Mapping)}
        if not set(preferred_fallback_ids).issubset(blocker_fallback_ids):
            raise ValueError(
                f"risk_policy_candidates[{index}].preferred_fallback_ids must reference blocker fallback_paths"
            )
        if not set(escalation_trigger_ids).issubset(blocker_trigger_ids):
            raise ValueError(
                f"risk_policy_candidates[{index}].escalation_trigger_ids must reference blocker escalation_triggers"
            )
        if policy_decision == "mitigate-locally" and not preferred_fallback_ids:
            raise ValueError(
                f"risk_policy_candidates[{index}].preferred_fallback_ids must not be empty for mitigate-locally"
            )
        if policy_decision == "fallback-then-escalate":
            if not preferred_fallback_ids:
                raise ValueError(
                    f"risk_policy_candidates[{index}].preferred_fallback_ids must not be empty for fallback-then-escalate"
                )
            if not escalation_trigger_ids:
                raise ValueError(
                    f"risk_policy_candidates[{index}].escalation_trigger_ids must not be empty for fallback-then-escalate"
                )
        if policy_decision == "escalate-immediately" and not escalation_trigger_ids:
            raise ValueError(
                f"risk_policy_candidates[{index}].escalation_trigger_ids must not be empty for escalate-immediately"
            )

        normalized.append(
            {
                "policy_id": policy_id,
                "blocker_id": blocker_id,
                "policy_decision": policy_decision,
                "rationale": rationale,
                "preferred_fallback_ids": preferred_fallback_ids,
                "escalation_trigger_ids": escalation_trigger_ids,
                "evidence_refs": evidence_refs,
            }
        )
    if not normalized:
        raise ValueError("risk_policy_candidates must contain at least 1 item(s)")
    normalized.sort(key=lambda row: row["policy_id"])
    return normalized


def _canonical_req_032_input(
    *,
    target_project_root: str,
    earth_root: str,
    output_root: str,
    revision_identity: str,
    strategy_goal: str,
    call_sequence: int,
) -> dict[str, Any]:
    return {
        "runtime_mode": RUNTIME_MODE,
        "execution_mode": EXECUTION_MODE,
        "target_project_root": target_project_root,
        "earth_root": earth_root,
        "output_root": output_root,
        "revision_identity": revision_identity,
        "strategy_goal": strategy_goal,
        "call_sequence": call_sequence,
    }


def _canonical_req_032_processing_input(
    *,
    evidence_refs: list[str],
    target_project_evidence_refs: list[str],
    earth_sweep_evidence_refs: list[str],
    cross_project_context: list[dict[str, Any]],
    blocker_candidates: list[dict[str, Any]],
    risk_policy_candidates: list[dict[str, Any]],
    strategic_claims: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    processing_input = {
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
        "blocker_candidates": [
            {
                "blocker_id": row["blocker_id"],
                "summary": row["summary"],
                "severity": row["severity"],
                "affected_project_ids": list(row["affected_project_ids"]),
                "evidence_refs": list(row["evidence_refs"]),
                "escalation_triggers": [
                    {
                        "trigger_id": trigger["trigger_id"],
                        "project_id": trigger["project_id"],
                        "summary": trigger["summary"],
                        "fire_when": trigger["fire_when"],
                        "urgency": trigger["urgency"],
                        "evidence_refs": list(trigger["evidence_refs"]),
                    }
                    for trigger in row["escalation_triggers"]
                ],
                "fallback_paths": [
                    {
                        "fallback_id": fallback["fallback_id"],
                        "sequence": fallback["sequence"],
                        "summary": fallback["summary"],
                        "activates_when": fallback["activates_when"],
                        "next_step": fallback["next_step"],
                        "evidence_refs": list(fallback["evidence_refs"]),
                    }
                    for fallback in row["fallback_paths"]
                ],
            }
            for row in blocker_candidates
        ],
        "risk_policy_candidates": [
            {
                "policy_id": row["policy_id"],
                "blocker_id": row["blocker_id"],
                "policy_decision": row["policy_decision"],
                "rationale": row["rationale"],
                "preferred_fallback_ids": list(row["preferred_fallback_ids"]),
                "escalation_trigger_ids": list(row["escalation_trigger_ids"]),
                "evidence_refs": list(row["evidence_refs"]),
            }
            for row in risk_policy_candidates
        ],
    }
    if strategic_claims:
        processing_input["strategic_claims"] = [
            {
                "claim_id": row["claim_id"],
                "phase": row["phase"],
                "summary": row["summary"],
                "position": row["position"],
                "source_output_ref": row["source_output_ref"],
                "evidence_refs": list(row["evidence_refs"]),
            }
            for row in strategic_claims
        ]
    return processing_input


def _collect_req_032_trace_input_refs(canonical_processing_input: Mapping[str, Any]) -> list[str]:
    blocker_candidates = canonical_processing_input.get("blocker_candidates")
    risk_policy_candidates = canonical_processing_input.get("risk_policy_candidates")
    cross_project_context = canonical_processing_input.get("cross_project_context")
    strategic_claims = canonical_processing_input.get("strategic_claims")

    def _rows_to_refs(rows: Any) -> list[list[str]]:
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
            return []
        refs: list[list[str]] = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            row_refs = row.get("evidence_refs")
            if isinstance(row_refs, Sequence) and not isinstance(row_refs, (str, bytes, bytearray)):
                refs.append([_as_text(ref) for ref in row_refs if _as_text(ref)])
        return refs

    blocker_refs: list[list[str]] = []
    if isinstance(blocker_candidates, Sequence) and not isinstance(blocker_candidates, (str, bytes, bytearray)):
        for blocker in blocker_candidates:
            if not isinstance(blocker, Mapping):
                continue
            blocker_refs.extend(_rows_to_refs([blocker]))
            blocker_refs.extend(_rows_to_refs(blocker.get("escalation_triggers")))
            blocker_refs.extend(_rows_to_refs(blocker.get("fallback_paths")))

    claim_refs: list[list[str]] = []
    claim_output_refs: list[str] = []
    if isinstance(strategic_claims, Sequence) and not isinstance(strategic_claims, (str, bytes, bytearray)):
        for row in strategic_claims:
            if not isinstance(row, Mapping):
                continue
            row_refs = row.get("evidence_refs")
            if isinstance(row_refs, Sequence) and not isinstance(row_refs, (str, bytes, bytearray)):
                claim_refs.append([_as_text(ref) for ref in row_refs if _as_text(ref)])
            source_output_ref = _as_text(row.get("source_output_ref"))
            if source_output_ref:
                claim_output_refs.append(source_output_ref)

    required_evidence_refs = canonical_processing_input.get("required_evidence_refs")
    if not isinstance(required_evidence_refs, Sequence) or isinstance(required_evidence_refs, (str, bytes, bytearray)):
        required_evidence_refs = []

    return _collect_unique_refs(
        [_as_text(ref) for ref in required_evidence_refs if _as_text(ref)],
        claim_output_refs,
        *(_rows_to_refs(cross_project_context)),
        *blocker_refs,
        *(_rows_to_refs(risk_policy_candidates)),
        *claim_refs,
    )


def _build_req_032_llm_call_trace_rows(
    *,
    canonical_input_sha: str,
    processing_input_sha: str,
    processing_call_id: str,
    canonical_processing_input: Mapping[str, Any],
    blocker_count: int,
    escalation_trigger_count: int,
    fallback_path_count: int,
) -> list[dict[str, Any]]:
    plan_id = f"req032-plan-{processing_input_sha[:16]}"
    call_id = f"req032-call-{REQ_032_CALL_SEQUENCE:02d}-{canonical_input_sha[:10]}"
    output_ref = _build_call_output_ref(
        plan_id=plan_id,
        call_id=call_id,
        expected_output=REQ_032_TRACE_EXPECTED_OUTPUT,
    )
    return [
        {
            "schema_version": REQ_025_LLM_CALL_TRACE_SCHEMA_VERSION,
            "requirement_id": REQ_032_REQUIREMENT_ID,
            "plan_id": plan_id,
            "processing_call_id": processing_call_id,
            "call_id": call_id,
            "sequence": REQ_032_CALL_SEQUENCE,
            "call_objective": REQ_032_TRACE_CALL_OBJECTIVE,
            "depends_on": [],
            "expected_output": REQ_032_TRACE_EXPECTED_OUTPUT,
            "input_refs": _collect_req_032_trace_input_refs(canonical_processing_input),
            "output_refs": [output_ref],
            "handoff_summary": (
                f"Call {REQ_032_CALL_SEQUENCE} hands off {REQ_032_TRACE_EXPECTED_OUTPUT} via {output_ref} "
                f"after reasoning over {blocker_count} blockers, {escalation_trigger_count} escalation triggers, "
                f"and {fallback_path_count} fallback paths."
            ),
        }
    ]


def _req_032_recommendation_decision(
    *,
    escalation_triggers: Sequence[Mapping[str, Any]],
    fallback_sequence: Sequence[Mapping[str, Any]],
    open_risks: Sequence[Mapping[str, Any]],
    risk_policy_candidates: Sequence[Mapping[str, Any]],
) -> str:
    reason_codes = {_as_text(row.get("reason_code")) for row in open_risks}
    if {"cross_call_contradiction", "uncited_strategic_claim"}.intersection(reason_codes):
        return "resolve-strategy-gaps"
    if open_risks:
        return "resolve-context-gaps"
    if fallback_sequence and escalation_triggers:
        return "fallback-then-escalate"
    if escalation_triggers:
        return "escalate-blockers"
    if fallback_sequence:
        return "proceed-with-fallbacks"
    if risk_policy_candidates and {
        _as_text(row.get("policy_decision")) for row in risk_policy_candidates
    } == {"monitor"} and not open_risks:
        return "monitor"
    if open_risks:
        return "resolve-context-gaps"
    return "insufficient-context"


def _req_032_recommendation_rationale(*, decision: str) -> str:
    if decision == "resolve-strategy-gaps":
        return "Call-7 detected contradictory or uncited strategy claims that block reliable risk-policy promotion."
    if decision == "fallback-then-escalate":
        return "Risk policies require a bounded fallback sequence before escalation triggers are promoted."
    if decision == "escalate-blockers":
        return "Blocker severity and policy decisions require immediate escalation."
    if decision == "proceed-with-fallbacks":
        return "Fallback sequencing paths are evidence-backed and can proceed without immediate escalation."
    if decision == "monitor":
        return "Current blocker state is evidence-backed but only warrants monitoring."
    if decision == "resolve-context-gaps":
        return "Cross-project context or policy coverage is incomplete for reliable blocker promotion."
    return "No evidence-backed blocker policy actions were supplied for Call-7."


def _req_032_recommendation_confidence(
    *,
    evidence_refs: Sequence[str],
    escalation_triggers: Sequence[Mapping[str, Any]],
    fallback_sequence: Sequence[Mapping[str, Any]],
    open_risks: Sequence[Mapping[str, Any]],
) -> str:
    if not evidence_refs:
        return "low"
    if (escalation_triggers or fallback_sequence) and not open_risks:
        return "high"
    if escalation_triggers or fallback_sequence:
        return "medium"
    if open_risks:
        return "low"
    return "medium"


def _build_req_032_processing_behavior(
    *,
    target_project_root: str,
    earth_root: str,
    strategy_goal: str,
    target_project_evidence_refs: list[str],
    earth_sweep_evidence_refs: list[str],
    cross_project_context: list[dict[str, Any]],
    blocker_candidates: list[dict[str, Any]],
    risk_policy_candidates: list[dict[str, Any]],
    strategic_claims: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not earth_sweep_evidence_refs:
        raise ValueError("earth_sweep_evidence_refs must contain at least 1 item(s)")

    earth_ref_set = set(earth_sweep_evidence_refs)
    context_by_project = {row["project_id"]: row for row in cross_project_context}
    cross_project_refs = _collect_unique_refs(*[row["evidence_refs"] for row in cross_project_context])
    normalized_strategic_claims = list(strategic_claims or [])
    policies_by_blocker: dict[str, list[dict[str, Any]]] = {}
    for policy in risk_policy_candidates:
        policies_by_blocker.setdefault(policy["blocker_id"], []).append(policy)

    available_citation_refs = set(
        _collect_unique_refs(
            target_project_evidence_refs,
            earth_sweep_evidence_refs,
            cross_project_refs,
            *[row["evidence_refs"] for row in blocker_candidates],
            *[
                trigger["evidence_refs"]
                for row in blocker_candidates
                for trigger in row["escalation_triggers"]
            ],
            *[
                fallback["evidence_refs"]
                for row in blocker_candidates
                for fallback in row["fallback_paths"]
            ],
            *[row["evidence_refs"] for row in risk_policy_candidates],
        )
    )

    blocker_reasoning: list[dict[str, Any]] = []
    promoted_escalation_triggers: list[dict[str, Any]] = []
    promoted_fallback_sequence: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []

    claim_rows_by_id: dict[str, list[dict[str, Any]]] = {}
    for claim in normalized_strategic_claims:
        claim_rows_by_id.setdefault(claim["claim_id"], []).append(claim)
        citation_refs = list(claim["evidence_refs"])
        if not citation_refs or not set(citation_refs).issubset(available_citation_refs):
            open_risks.append(
                {
                    "risk_id": f"risk-claim-{claim['claim_id']}-citation",
                    "summary": claim["summary"],
                    "reason_code": "uncited_strategic_claim",
                    "required_evidence_refs": _collect_unique_refs([claim["source_output_ref"]], citation_refs),
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
                        [analysis_row["source_output_ref"]],
                        [synthesis_row["source_output_ref"]],
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

    escalation_rows_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    fallback_rows_by_key: dict[tuple[int, str, str], dict[str, Any]] = {}

    for blocker in blocker_candidates:
        if not set(blocker["evidence_refs"]).intersection(earth_ref_set):
            raise ValueError(f"blocker_candidates[{blocker['blocker_id']}] must include earth_sweep evidence refs")

        missing_context_projects: list[str] = []
        missing_context_evidence_projects: list[str] = []
        linked_context_projects: list[str] = []
        linked_context_refs: list[str] = []
        for project_id in blocker["affected_project_ids"]:
            project_context = context_by_project.get(project_id)
            if project_context is None:
                missing_context_projects.append(project_id)
                continue
            linked_context_projects.append(project_id)
            if project_context["evidence_refs"]:
                linked_context_refs.extend(project_context["evidence_refs"])
            else:
                missing_context_evidence_projects.append(project_id)

        if missing_context_projects:
            open_risks.append(
                {
                    "risk_id": f"risk-{blocker['blocker_id']}-context",
                    "summary": blocker["summary"],
                    "reason_code": "missing_cross_project_context",
                    "affected_project_ids": missing_context_projects,
                    "required_evidence_refs": list(blocker["evidence_refs"]),
                }
            )
        if missing_context_evidence_projects:
            open_risks.append(
                {
                    "risk_id": f"risk-{blocker['blocker_id']}-context-evidence",
                    "summary": blocker["summary"],
                    "reason_code": "missing_cross_project_context_evidence_refs",
                    "affected_project_ids": missing_context_evidence_projects,
                    "required_evidence_refs": list(blocker["evidence_refs"]),
                }
            )

        applicable_policies = policies_by_blocker.get(blocker["blocker_id"], [])
        if not applicable_policies:
            open_risks.append(
                {
                    "risk_id": f"risk-{blocker['blocker_id']}-policy",
                    "summary": blocker["summary"],
                    "reason_code": "missing_risk_policy",
                    "affected_project_ids": list(blocker["affected_project_ids"]),
                    "required_evidence_refs": list(blocker["evidence_refs"]),
                }
            )

        escalation_triggers = [
            {
                "trigger_id": trigger["trigger_id"],
                "project_id": trigger["project_id"],
                "summary": trigger["summary"],
                "fire_when": trigger["fire_when"],
                "urgency": trigger["urgency"],
                "evidence_refs": _collect_unique_refs(
                    blocker["evidence_refs"],
                    trigger["evidence_refs"],
                    context_by_project.get(trigger["project_id"], {}).get("evidence_refs", []),
                ),
            }
            for trigger in blocker["escalation_triggers"]
        ]
        fallback_paths = [
            {
                "fallback_id": fallback["fallback_id"],
                "sequence": fallback["sequence"],
                "summary": fallback["summary"],
                "activates_when": fallback["activates_when"],
                "next_step": fallback["next_step"],
                "evidence_refs": _collect_unique_refs(
                    blocker["evidence_refs"],
                    fallback["evidence_refs"],
                    linked_context_refs,
                ),
            }
            for fallback in blocker["fallback_paths"]
        ]
        invalid_escalation_trigger_ids: set[str] = set()
        for trigger in escalation_triggers:
            project_context = context_by_project.get(trigger["project_id"])
            if project_context is None:
                invalid_escalation_trigger_ids.add(trigger["trigger_id"])
                open_risks.append(
                    {
                        "risk_id": f"risk-{blocker['blocker_id']}-{trigger['trigger_id']}-context",
                        "summary": trigger["summary"],
                        "reason_code": "missing_escalation_project_context",
                        "affected_project_ids": [trigger["project_id"]],
                        "required_evidence_refs": _collect_unique_refs(
                            blocker["evidence_refs"],
                            trigger["evidence_refs"],
                        ),
                    }
                )
                continue
            if not project_context["evidence_refs"]:
                invalid_escalation_trigger_ids.add(trigger["trigger_id"])
                open_risks.append(
                    {
                        "risk_id": f"risk-{blocker['blocker_id']}-{trigger['trigger_id']}-context-evidence",
                        "summary": trigger["summary"],
                        "reason_code": "missing_escalation_project_context_evidence_refs",
                        "affected_project_ids": [trigger["project_id"]],
                        "required_evidence_refs": _collect_unique_refs(
                            blocker["evidence_refs"],
                            trigger["evidence_refs"],
                        ),
                    }
                )

        promoted_trigger_count = 0
        for policy in applicable_policies:
            should_promote_fallbacks = policy["policy_decision"] in {"mitigate-locally", "fallback-then-escalate"}
            should_promote_triggers = policy["policy_decision"] in {"fallback-then-escalate", "escalate-immediately"}
            if should_promote_fallbacks:
                for fallback in fallback_paths:
                    if fallback["fallback_id"] not in set(policy["preferred_fallback_ids"]):
                        continue
                    key = (fallback["sequence"], blocker["blocker_id"], fallback["fallback_id"])
                    fallback_rows_by_key[key] = {
                        "sequence": fallback["sequence"],
                        "fallback_id": fallback["fallback_id"],
                        "blocker_id": blocker["blocker_id"],
                        "policy_id": policy["policy_id"],
                        "summary": fallback["summary"],
                        "activates_when": fallback["activates_when"],
                        "next_step": fallback["next_step"],
                        "evidence_refs": _collect_unique_refs(
                            fallback["evidence_refs"],
                            policy["evidence_refs"],
                        ),
                    }
            if should_promote_triggers:
                for trigger in escalation_triggers:
                    if trigger["trigger_id"] in invalid_escalation_trigger_ids:
                        continue
                    if trigger["trigger_id"] not in set(policy["escalation_trigger_ids"]):
                        continue
                    key = (blocker["blocker_id"], policy["policy_id"], trigger["trigger_id"])
                    escalation_rows_by_key[key] = {
                        "trigger_id": trigger["trigger_id"],
                        "blocker_id": blocker["blocker_id"],
                        "policy_id": policy["policy_id"],
                        "project_id": trigger["project_id"],
                        "summary": trigger["summary"],
                        "fire_when": trigger["fire_when"],
                        "urgency": trigger["urgency"],
                        "evidence_refs": _collect_unique_refs(
                            trigger["evidence_refs"],
                            policy["evidence_refs"],
                        ),
                    }
                    promoted_trigger_count += 1

        if blocker["severity"] == "critical" and promoted_trigger_count == 0:
            open_risks.append(
                {
                    "risk_id": f"risk-{blocker['blocker_id']}-critical",
                    "summary": blocker["summary"],
                    "reason_code": "critical_blocker_without_escalation",
                    "affected_project_ids": list(blocker["affected_project_ids"]),
                    "required_evidence_refs": _collect_unique_refs(
                        blocker["evidence_refs"],
                        *[row["evidence_refs"] for row in escalation_triggers],
                    ),
                }
            )

        blocker_reasoning.append(
            {
                "blocker_id": blocker["blocker_id"],
                "summary": blocker["summary"],
                "severity": blocker["severity"],
                "affected_project_ids": list(blocker["affected_project_ids"]),
                "linked_context_projects": linked_context_projects,
                "evidence_refs": _collect_unique_refs(
                    blocker["evidence_refs"],
                    linked_context_refs,
                    *[row["evidence_refs"] for row in applicable_policies],
                ),
                "escalation_triggers": escalation_triggers,
                "fallback_paths": fallback_paths,
                "applicable_policies": [
                    {
                        "policy_id": policy["policy_id"],
                        "policy_decision": policy["policy_decision"],
                        "rationale": policy["rationale"],
                        "preferred_fallback_ids": list(policy["preferred_fallback_ids"]),
                        "escalation_trigger_ids": list(policy["escalation_trigger_ids"]),
                        "evidence_refs": list(policy["evidence_refs"]),
                    }
                    for policy in applicable_policies
                ],
            }
        )

    promoted_escalation_triggers = [row for _, row in sorted(escalation_rows_by_key.items())]
    promoted_fallback_sequence = [row for _, row in sorted(fallback_rows_by_key.items())]
    blocker_reasoning.sort(key=lambda row: row["blocker_id"])
    open_risks.sort(key=lambda row: row["risk_id"])

    evidence_refs_used = _collect_unique_refs(
        target_project_evidence_refs,
        earth_sweep_evidence_refs,
        cross_project_refs,
        *[row["evidence_refs"] for row in blocker_candidates],
        *[
            trigger["evidence_refs"]
            for row in blocker_candidates
            for trigger in row["escalation_triggers"]
        ],
        *[
            fallback["evidence_refs"]
            for row in blocker_candidates
            for fallback in row["fallback_paths"]
        ],
        *[row["evidence_refs"] for row in risk_policy_candidates],
        *[row["required_evidence_refs"] for row in open_risks],
    )
    recommendation_refs = _collect_unique_refs(
        target_project_evidence_refs,
        earth_sweep_evidence_refs,
        cross_project_refs,
        *[row["evidence_refs"] for row in promoted_escalation_triggers],
        *[row["evidence_refs"] for row in promoted_fallback_sequence],
        *[row["required_evidence_refs"] for row in open_risks],
    )
    recommendation_decision = _req_032_recommendation_decision(
        escalation_triggers=promoted_escalation_triggers,
        fallback_sequence=promoted_fallback_sequence,
        open_risks=open_risks,
        risk_policy_candidates=risk_policy_candidates,
    )

    return {
        "strategy": REQ_032_STRATEGY,
        "reasoning_mode": EXECUTION_MODE,
        "strict_evidence_discipline": True,
        "heuristic_summarization_only": False,
        "context_inputs": {
            "target_project": {
                "project_root": target_project_root,
                "strategy_goal": strategy_goal,
                "evidence_refs": list(target_project_evidence_refs),
            },
            "earth_sweep": {
                "earth_root": earth_root,
                "evidence_refs": list(earth_sweep_evidence_refs),
            },
            "cross_project_context": [
                {
                    "project_id": row["project_id"],
                    "project_root": row["project_root"],
                    "evidence_refs": list(row["evidence_refs"]),
                    "context_note": row["context_note"],
                }
                for row in cross_project_context
            ],
            "blocker_candidates": [
                {
                    "blocker_id": row["blocker_id"],
                    "summary": row["summary"],
                    "severity": row["severity"],
                    "affected_project_ids": list(row["affected_project_ids"]),
                    "evidence_refs": list(row["evidence_refs"]),
                    "escalation_triggers": [
                        {
                            "trigger_id": trigger["trigger_id"],
                            "project_id": trigger["project_id"],
                            "summary": trigger["summary"],
                            "fire_when": trigger["fire_when"],
                            "urgency": trigger["urgency"],
                            "evidence_refs": list(trigger["evidence_refs"]),
                        }
                        for trigger in row["escalation_triggers"]
                    ],
                    "fallback_paths": [
                        {
                            "fallback_id": fallback["fallback_id"],
                            "sequence": fallback["sequence"],
                            "summary": fallback["summary"],
                            "activates_when": fallback["activates_when"],
                            "next_step": fallback["next_step"],
                            "evidence_refs": list(fallback["evidence_refs"]),
                        }
                        for fallback in row["fallback_paths"]
                    ],
                }
                for row in blocker_candidates
            ],
            "risk_policy_candidates": [
                {
                    "policy_id": row["policy_id"],
                    "blocker_id": row["blocker_id"],
                    "policy_decision": row["policy_decision"],
                    "rationale": row["rationale"],
                    "preferred_fallback_ids": list(row["preferred_fallback_ids"]),
                    "escalation_trigger_ids": list(row["escalation_trigger_ids"]),
                    "evidence_refs": list(row["evidence_refs"]),
                }
                for row in risk_policy_candidates
            ],
            "strategic_claims": [
                {
                    "claim_id": row["claim_id"],
                    "phase": row["phase"],
                    "summary": row["summary"],
                    "position": row["position"],
                    "source_output_ref": row["source_output_ref"],
                    "evidence_refs": list(row["evidence_refs"]),
                }
                for row in normalized_strategic_claims
            ],
        },
        "context_usage": {
            "target_project_context_used": bool(strategy_goal or target_project_evidence_refs),
            "earth_sweep_context_used": bool(earth_sweep_evidence_refs),
            "cross_project_context_used": bool(cross_project_context),
            "blocker_ids_considered": [row["blocker_id"] for row in blocker_candidates],
            "policy_ids_considered": [row["policy_id"] for row in risk_policy_candidates],
            "fallback_ids_considered": [
                fallback["fallback_id"] for row in blocker_candidates for fallback in row["fallback_paths"]
            ],
            "cross_project_projects_considered": [row["project_id"] for row in cross_project_context],
            "escalation_project_ids": sorted(
                {row["project_id"] for row in promoted_escalation_triggers}
            ),
            "cross_project_refs_used": cross_project_refs,
            "evidence_refs_used": evidence_refs_used,
        },
        "call_7_reasoning": {
            "call_sequence": REQ_032_CALL_SEQUENCE,
            "reasoning_focus": REQ_032_REASONING_FOCUS,
            "blocker_reasoning": blocker_reasoning,
            "blocker_count": len(blocker_reasoning),
            "policy_count": len(risk_policy_candidates),
            "escalation_trigger_count": sum(len(row["escalation_triggers"]) for row in blocker_reasoning),
            "fallback_path_count": sum(len(row["fallback_paths"]) for row in blocker_reasoning),
        },
        "recommendation": {
            "decision": recommendation_decision,
            "rationale": _req_032_recommendation_rationale(decision=recommendation_decision),
            "confidence": _req_032_recommendation_confidence(
                evidence_refs=recommendation_refs,
                escalation_triggers=promoted_escalation_triggers,
                fallback_sequence=promoted_fallback_sequence,
                open_risks=open_risks,
            ),
            "evidence_refs": recommendation_refs,
            "escalation_triggers": promoted_escalation_triggers,
            "fallback_sequence": promoted_fallback_sequence,
            "open_risks": open_risks,
        },
        "summary": (
            f"Call 7 reasoned over {len(blocker_reasoning)} blocker(s), "
            f"{len(promoted_escalation_triggers)} promoted escalation trigger(s), and "
            f"{len(promoted_fallback_sequence)} fallback sequence step(s)."
        ),
    }


def build_req_032_call_7_blocker_and_risk_policy_reasoning(
    *,
    target_project_root: str = DEFAULT_TARGET_PROJECT_ROOT,
    earth_root: str = DEFAULT_EARTH_ROOT,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    revision_identity: str = DEFAULT_REQ_032_REVISION_ID,
    strategy_goal: str,
    call_sequence: int = REQ_032_CALL_SEQUENCE,
    evidence_refs: Sequence[Any] | None = None,
    target_project_evidence_refs: Sequence[Any] | None = None,
    earth_sweep_evidence_refs: Sequence[Any] | None = None,
    cross_project_context: Sequence[Mapping[str, Any]] | None = None,
    blocker_candidates: Sequence[Mapping[str, Any]] | None = None,
    risk_policy_candidates: Sequence[Mapping[str, Any]] | None = None,
    strategic_claims: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the REQ-032 Call-7 blocker and risk policy reasoning payload."""
    normalized_target_root = _normalize_root(target_project_root, field_name="target_project_root")
    normalized_earth_root = _normalize_root(earth_root, field_name="earth_root")
    normalized_output_root = _normalize_root(output_root, field_name="output_root")
    normalized_revision_identity = _require_text(revision_identity, field_name="revision_identity")
    normalized_strategy_goal = _require_text(strategy_goal, field_name="strategy_goal")
    normalized_call_sequence = _normalize_req_032_call_sequence(call_sequence)
    normalized_evidence_refs = _normalize_string_list(evidence_refs, field_name="evidence_refs", min_items=1)
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
    normalized_blocker_candidates = _normalize_req_032_blocker_candidates(blocker_candidates)
    normalized_risk_policy_candidates = _normalize_req_032_risk_policy_candidates(
        risk_policy_candidates,
        blocker_candidates=normalized_blocker_candidates,
    )
    normalized_strategic_claims = _normalize_req_028_strategic_claims(strategic_claims)

    canonical_input = _canonical_req_032_input(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        output_root=normalized_output_root,
        revision_identity=normalized_revision_identity,
        strategy_goal=normalized_strategy_goal,
        call_sequence=normalized_call_sequence,
    )
    canonical_input_sha = _canonical_digest(canonical_input)

    canonical_processing_input = _canonical_req_032_processing_input(
        evidence_refs=normalized_evidence_refs,
        target_project_evidence_refs=normalized_target_project_evidence_refs,
        earth_sweep_evidence_refs=normalized_earth_sweep_evidence_refs,
        cross_project_context=normalized_cross_project_context,
        blocker_candidates=normalized_blocker_candidates,
        risk_policy_candidates=normalized_risk_policy_candidates,
        strategic_claims=normalized_strategic_claims,
    )
    processing_sha = _canonical_digest(canonical_processing_input)

    processing_behavior = _build_req_032_processing_behavior(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        strategy_goal=normalized_strategy_goal,
        target_project_evidence_refs=normalized_target_project_evidence_refs,
        earth_sweep_evidence_refs=normalized_earth_sweep_evidence_refs,
        cross_project_context=normalized_cross_project_context,
        blocker_candidates=normalized_blocker_candidates,
        risk_policy_candidates=normalized_risk_policy_candidates,
        strategic_claims=normalized_strategic_claims,
    )
    processing_call_id = f"req032-processing-{processing_sha[:16]}"
    llm_call_trace_rows = _build_req_032_llm_call_trace_rows(
        canonical_input_sha=canonical_input_sha,
        processing_input_sha=processing_sha,
        processing_call_id=processing_call_id,
        canonical_processing_input=canonical_processing_input,
        blocker_count=len(normalized_blocker_candidates),
        escalation_trigger_count=sum(
            len(row["escalation_triggers"]) for row in normalized_blocker_candidates
        ),
        fallback_path_count=sum(len(row["fallback_paths"]) for row in normalized_blocker_candidates),
    )
    llm_call_trace_sha = _canonical_digest(llm_call_trace_rows)

    return {
        "schema_version": REQ_032_SCHEMA_VERSION,
        "requirement_id": REQ_032_REQUIREMENT_ID,
        "call_7_blocker_and_risk_policy_reasoning_entrypoint": {
            "runtime_mode": RUNTIME_MODE,
            "execution_mode": EXECUTION_MODE,
            "target_project_root": normalized_target_root,
            "earth_root": normalized_earth_root,
            "output_root": normalized_output_root,
            "revision_identity": normalized_revision_identity,
            "strategy_goal": normalized_strategy_goal,
            "call_sequence": normalized_call_sequence,
        },
        "processing_behavior": processing_behavior,
        "call_metadata": {
            "reproducibility": "deterministic-input-fingerprint",
            "canonical_input_sha256": canonical_input_sha,
            "reproducible_call_id": f"req032-{canonical_input_sha[:16]}",
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


def validate_req_032_call_7_blocker_and_risk_policy_reasoning(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-032 payload shape and deterministic Call-7 blocker reasoning content."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    required_top = {
        "schema_version",
        "requirement_id",
        "call_7_blocker_and_risk_policy_reasoning_entrypoint",
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

    if payload.get("schema_version") != REQ_032_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_032_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_032_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_032_REQUIREMENT_ID}")

    entrypoint = payload.get("call_7_blocker_and_risk_policy_reasoning_entrypoint")
    if not isinstance(entrypoint, Mapping):
        errors.append("call_7_blocker_and_risk_policy_reasoning_entrypoint must be an object")
        return errors

    required_entrypoint = {
        "runtime_mode",
        "execution_mode",
        "target_project_root",
        "earth_root",
        "output_root",
        "revision_identity",
        "strategy_goal",
        "call_sequence",
    }
    entrypoint_keys = set(entrypoint.keys())
    missing_entrypoint = sorted(required_entrypoint - entrypoint_keys)
    if missing_entrypoint:
        errors.append(f"call_7_blocker_and_risk_policy_reasoning_entrypoint missing keys: {missing_entrypoint}")
    unexpected_entrypoint = sorted(entrypoint_keys - required_entrypoint)
    if unexpected_entrypoint:
        errors.append(f"call_7_blocker_and_risk_policy_reasoning_entrypoint unexpected keys: {unexpected_entrypoint}")

    if entrypoint.get("runtime_mode") != RUNTIME_MODE:
        errors.append(f"call_7_blocker_and_risk_policy_reasoning_entrypoint.runtime_mode must be {RUNTIME_MODE}")
    if entrypoint.get("execution_mode") != EXECUTION_MODE:
        errors.append(f"call_7_blocker_and_risk_policy_reasoning_entrypoint.execution_mode must be {EXECUTION_MODE}")
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

    call_sequence = entrypoint.get("call_sequence")
    if call_sequence != REQ_032_CALL_SEQUENCE:
        errors.append(f"call_sequence must be {REQ_032_CALL_SEQUENCE}")
        call_sequence = REQ_032_CALL_SEQUENCE

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
        "call_7_reasoning",
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

    if processing_behavior.get("strategy") != REQ_032_STRATEGY:
        errors.append(f"processing_behavior.strategy must be {REQ_032_STRATEGY}")
    if processing_behavior.get("reasoning_mode") != EXECUTION_MODE:
        errors.append(f"processing_behavior.reasoning_mode must be {EXECUTION_MODE}")
    if processing_behavior.get("strict_evidence_discipline") is not True:
        errors.append("processing_behavior.strict_evidence_discipline must be true")
    if processing_behavior.get("heuristic_summarization_only") is not False:
        errors.append("processing_behavior.heuristic_summarization_only must be false")

    normalized_target_project_refs: list[str] = []
    normalized_earth_sweep_refs: list[str] = []
    normalized_cross_project_context: list[dict[str, Any]] = []
    normalized_blocker_candidates: list[dict[str, Any]] = []
    normalized_risk_policy_candidates: list[dict[str, Any]] = []
    normalized_strategic_claims: list[dict[str, Any]] = []

    metadata = payload.get("call_metadata")
    if isinstance(metadata, Mapping):
        canonical_processing_input_preview = metadata.get("canonical_processing_input")
        if isinstance(canonical_processing_input_preview, Mapping) and "strategic_claims" in canonical_processing_input_preview:
            try:
                normalized_strategic_claims = _normalize_req_028_strategic_claims(
                    canonical_processing_input_preview.get("strategic_claims")
                )
            except ValueError as exc:
                errors.append(str(exc))

    context_inputs = processing_behavior.get("context_inputs")
    if not isinstance(context_inputs, Mapping):
        errors.append("processing_behavior.context_inputs must be an object")
    else:
        target_project = context_inputs.get("target_project")
        if not isinstance(target_project, Mapping):
            errors.append("processing_behavior.context_inputs.target_project must be an object")
        else:
            if target_project.get("project_root") != entrypoint.get("target_project_root"):
                errors.append(
                    "processing_behavior.context_inputs.target_project.project_root must match entrypoint.target_project_root"
                )
            if target_project.get("strategy_goal") != entrypoint.get("strategy_goal"):
                errors.append(
                    "processing_behavior.context_inputs.target_project.strategy_goal must match entrypoint.strategy_goal"
                )
            try:
                normalized_target_project_refs = _normalize_string_list(
                    target_project.get("evidence_refs"),
                    field_name="processing_behavior.context_inputs.target_project.evidence_refs",
                )
            except ValueError as exc:
                errors.append(str(exc))

        earth_sweep = context_inputs.get("earth_sweep")
        if not isinstance(earth_sweep, Mapping):
            errors.append("processing_behavior.context_inputs.earth_sweep must be an object")
        else:
            if earth_sweep.get("earth_root") != entrypoint.get("earth_root"):
                errors.append("processing_behavior.context_inputs.earth_sweep.earth_root must match entrypoint.earth_root")
            try:
                normalized_earth_sweep_refs = _normalize_string_list(
                    earth_sweep.get("evidence_refs"),
                    field_name="processing_behavior.context_inputs.earth_sweep.evidence_refs",
                    min_items=1,
                )
            except ValueError as exc:
                errors.append(str(exc))

        try:
            normalized_cross_project_context = _normalize_cross_project_context(
                context_inputs.get("cross_project_context")
            )
        except ValueError as exc:
            errors.append(str(exc))
        try:
            normalized_blocker_candidates = _normalize_req_032_blocker_candidates(
                context_inputs.get("blocker_candidates")
            )
        except ValueError as exc:
            errors.append(str(exc))
        if normalized_blocker_candidates:
            try:
                normalized_risk_policy_candidates = _normalize_req_032_risk_policy_candidates(
                    context_inputs.get("risk_policy_candidates"),
                    blocker_candidates=normalized_blocker_candidates,
                )
            except ValueError as exc:
                errors.append(str(exc))

    context_usage = processing_behavior.get("context_usage")
    if not isinstance(context_usage, Mapping):
        errors.append("processing_behavior.context_usage must be an object")
    else:
        for key in (
            "target_project_context_used",
            "earth_sweep_context_used",
            "cross_project_context_used",
            "blocker_ids_considered",
            "policy_ids_considered",
            "fallback_ids_considered",
            "cross_project_projects_considered",
            "escalation_project_ids",
            "cross_project_refs_used",
            "evidence_refs_used",
        ):
            if key not in context_usage:
                errors.append(f"processing_behavior.context_usage missing keys: ['{key}']")

    call_7_reasoning = processing_behavior.get("call_7_reasoning")
    if not isinstance(call_7_reasoning, Mapping):
        errors.append("processing_behavior.call_7_reasoning must be an object")
    else:
        required_reasoning = {
            "call_sequence",
            "reasoning_focus",
            "blocker_reasoning",
            "blocker_count",
            "policy_count",
            "escalation_trigger_count",
            "fallback_path_count",
        }
        reasoning_keys = set(call_7_reasoning.keys())
        missing_reasoning = sorted(required_reasoning - reasoning_keys)
        if missing_reasoning:
            errors.append(f"processing_behavior.call_7_reasoning missing keys: {missing_reasoning}")
        unexpected_reasoning = sorted(reasoning_keys - required_reasoning)
        if unexpected_reasoning:
            errors.append(f"processing_behavior.call_7_reasoning unexpected keys: {unexpected_reasoning}")
        if call_7_reasoning.get("call_sequence") != REQ_032_CALL_SEQUENCE:
            errors.append(f"processing_behavior.call_7_reasoning.call_sequence must be {REQ_032_CALL_SEQUENCE}")
        if call_7_reasoning.get("reasoning_focus") != REQ_032_REASONING_FOCUS:
            errors.append(f"processing_behavior.call_7_reasoning.reasoning_focus must be {REQ_032_REASONING_FOCUS}")

    recommendation = processing_behavior.get("recommendation")
    if not isinstance(recommendation, Mapping):
        errors.append("processing_behavior.recommendation must be an object")
    else:
        required_recommendation = {
            "decision",
            "rationale",
            "confidence",
            "evidence_refs",
            "escalation_triggers",
            "fallback_sequence",
            "open_risks",
        }
        recommendation_keys = set(recommendation.keys())
        missing_recommendation = sorted(required_recommendation - recommendation_keys)
        if missing_recommendation:
            errors.append(f"processing_behavior.recommendation missing keys: {missing_recommendation}")
        if not isinstance(recommendation.get("evidence_refs"), list):
            errors.append("processing_behavior.recommendation.evidence_refs must be a list")
        if not isinstance(recommendation.get("escalation_triggers"), list):
            errors.append("processing_behavior.recommendation.escalation_triggers must be a list")
        if not isinstance(recommendation.get("fallback_sequence"), list):
            errors.append("processing_behavior.recommendation.fallback_sequence must be a list")
        if not isinstance(recommendation.get("open_risks"), list):
            errors.append("processing_behavior.recommendation.open_risks must be a list")

    if normalized_blocker_candidates and normalized_risk_policy_candidates and normalized_earth_sweep_refs:
        try:
            expected_processing_behavior = _build_req_032_processing_behavior(
                target_project_root=_as_text(entrypoint.get("target_project_root")),
                earth_root=_as_text(entrypoint.get("earth_root")),
                strategy_goal=_as_text(entrypoint.get("strategy_goal")),
                target_project_evidence_refs=normalized_target_project_refs,
                earth_sweep_evidence_refs=normalized_earth_sweep_refs,
                cross_project_context=normalized_cross_project_context,
                blocker_candidates=normalized_blocker_candidates,
                risk_policy_candidates=normalized_risk_policy_candidates,
                strategic_claims=normalized_strategic_claims,
            )
        except ValueError as exc:
            errors.append(f"processing_behavior could not be reconstructed: {exc}")
        else:
            if dict(processing_behavior) != expected_processing_behavior:
                errors.append("processing_behavior must match deterministic Call-7 reasoning output")

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
    expected_canonical_input = _canonical_req_032_input(
        target_project_root=_as_text(entrypoint.get("target_project_root")),
        earth_root=_as_text(entrypoint.get("earth_root")),
        output_root=_as_text(entrypoint.get("output_root")),
        revision_identity=_as_text(entrypoint.get("revision_identity")),
        strategy_goal=_as_text(entrypoint.get("strategy_goal")),
        call_sequence=int(call_sequence),
    )
    if dict(canonical_input) != expected_canonical_input:
        errors.append("call_metadata.canonical_input must mirror normalized invocation anchors")
    expected_input_sha = _canonical_digest(expected_canonical_input)
    if metadata.get("canonical_input_sha256") != expected_input_sha:
        errors.append("call_metadata.canonical_input_sha256 does not match canonical input")
    if metadata.get("reproducible_call_id") != f"req032-{expected_input_sha[:16]}":
        errors.append("call_metadata.reproducible_call_id does not match canonical digest")

    canonical_processing_input = metadata.get("canonical_processing_input")
    if not isinstance(canonical_processing_input, Mapping):
        errors.append("call_metadata.canonical_processing_input must be an object")
        return errors

    if metadata.get("llm_call_trace_schema_version") != REQ_025_LLM_CALL_TRACE_SCHEMA_VERSION:
        errors.append(
            f"call_metadata.llm_call_trace_schema_version must be {REQ_025_LLM_CALL_TRACE_SCHEMA_VERSION}"
        )
    if metadata.get("llm_call_trace_path") != LLM_CALL_TRACE_RELATIVE_PATH:
        errors.append(f"call_metadata.llm_call_trace_path must be {LLM_CALL_TRACE_RELATIVE_PATH}")

    if normalized_blocker_candidates and normalized_risk_policy_candidates and normalized_earth_sweep_refs:
        expected_processing_input = _canonical_req_032_processing_input(
            evidence_refs=sorted(
                set(
                    _collect_unique_refs(
                        normalized_target_project_refs,
                        normalized_earth_sweep_refs,
                        *[row["evidence_refs"] for row in normalized_cross_project_context],
                        *[row["evidence_refs"] for row in normalized_blocker_candidates],
                        *[
                            trigger["evidence_refs"]
                            for row in normalized_blocker_candidates
                            for trigger in row["escalation_triggers"]
                        ],
                        *[
                            fallback["evidence_refs"]
                            for row in normalized_blocker_candidates
                            for fallback in row["fallback_paths"]
                        ],
                        *[row["evidence_refs"] for row in normalized_risk_policy_candidates],
                    )
                )
            ),
            target_project_evidence_refs=normalized_target_project_refs,
            earth_sweep_evidence_refs=normalized_earth_sweep_refs,
            cross_project_context=normalized_cross_project_context,
            blocker_candidates=normalized_blocker_candidates,
            risk_policy_candidates=normalized_risk_policy_candidates,
            strategic_claims=normalized_strategic_claims,
        )
        if dict(canonical_processing_input) != expected_processing_input:
            errors.append("call_metadata.canonical_processing_input must mirror processing inputs")
        expected_processing_sha = _canonical_digest(expected_processing_input)
        if metadata.get("processing_input_sha256") != expected_processing_sha:
            errors.append("call_metadata.processing_input_sha256 does not match processing input")
        if metadata.get("processing_call_id") != f"req032-processing-{expected_processing_sha[:16]}":
            errors.append("call_metadata.processing_call_id does not match processing digest")

        expected_trace_rows = _build_req_032_llm_call_trace_rows(
            canonical_input_sha=expected_input_sha,
            processing_input_sha=expected_processing_sha,
            processing_call_id=f"req032-processing-{expected_processing_sha[:16]}",
            canonical_processing_input=expected_processing_input,
            blocker_count=len(normalized_blocker_candidates),
            escalation_trigger_count=sum(
                len(row["escalation_triggers"]) for row in normalized_blocker_candidates
            ),
            fallback_path_count=sum(len(row["fallback_paths"]) for row in normalized_blocker_candidates),
        )
        if metadata.get("llm_call_trace_rows") != expected_trace_rows:
            errors.append("call_metadata.llm_call_trace_rows must mirror deterministic Call-7 trace rows")
        if metadata.get("llm_call_trace_sha256") != _canonical_digest(expected_trace_rows):
            errors.append("call_metadata.llm_call_trace_sha256 does not match llm_call_trace_rows")

    return errors


def _normalize_req_033_call_sequence(raw_value: Any) -> int:
    if isinstance(raw_value, bool) or not isinstance(raw_value, int):
        raise ValueError("call_sequence must be an integer")
    if raw_value != REQ_033_CALL_SEQUENCE:
        raise ValueError(f"call_sequence must be {REQ_033_CALL_SEQUENCE}")
    return raw_value


def _normalize_req_033_classification(value: Any, *, field_name: str) -> str:
    classification = _require_text(value, field_name=field_name).lower()
    if classification not in {"hard-constraint", "soft-preference", "speculative-idea"}:
        raise ValueError(
            f"{field_name} must be one of: hard-constraint, soft-preference, speculative-idea"
        )
    return classification


def _normalize_req_033_constraint_candidates(raw_value: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError("constraint_candidates must be an array")

    normalized: list[dict[str, Any]] = []
    seen_candidate_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"constraint_candidates[{index}] must be an object")
        candidate_id = _require_text(item.get("candidate_id"), field_name=f"constraint_candidates[{index}].candidate_id")
        if candidate_id in seen_candidate_ids:
            raise ValueError(f"constraint_candidates[{index}].candidate_id duplicates {candidate_id}")
        seen_candidate_ids.add(candidate_id)
        normalized.append(
            {
                "candidate_id": candidate_id,
                "summary": _require_text(item.get("summary"), field_name=f"constraint_candidates[{index}].summary"),
                "classification": _normalize_req_033_classification(
                    item.get("classification"),
                    field_name=f"constraint_candidates[{index}].classification",
                ),
                "classification_rationale": _require_text(
                    item.get("classification_rationale"),
                    field_name=f"constraint_candidates[{index}].classification_rationale",
                ),
                "planner_implication": _require_text(
                    item.get("planner_implication"),
                    field_name=f"constraint_candidates[{index}].planner_implication",
                ),
                "source_output_refs": _normalize_string_list(
                    item.get("source_output_refs"),
                    field_name=f"constraint_candidates[{index}].source_output_refs",
                    min_items=1,
                ),
                "evidence_refs": _normalize_string_list(
                    item.get("evidence_refs"),
                    field_name=f"constraint_candidates[{index}].evidence_refs",
                    min_items=1,
                ),
            }
        )

    if not normalized:
        raise ValueError("constraint_candidates must contain at least 1 item(s)")
    normalized.sort(key=lambda row: (row["classification"], row["candidate_id"]))
    return normalized


def _canonical_req_033_input(
    *,
    target_project_root: str,
    earth_root: str,
    output_root: str,
    revision_identity: str,
    strategy_goal: str,
    call_sequence: int,
) -> dict[str, Any]:
    return {
        "runtime_mode": RUNTIME_MODE,
        "execution_mode": EXECUTION_MODE,
        "target_project_root": target_project_root,
        "earth_root": earth_root,
        "output_root": output_root,
        "revision_identity": revision_identity,
        "strategy_goal": strategy_goal,
        "call_sequence": call_sequence,
    }


def _canonical_req_033_processing_input(
    *,
    evidence_refs: list[str],
    target_project_evidence_refs: list[str],
    earth_sweep_evidence_refs: list[str],
    cross_project_context: list[dict[str, Any]],
    constraint_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
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
        "constraint_candidates": [
            {
                "candidate_id": row["candidate_id"],
                "summary": row["summary"],
                "classification": row["classification"],
                "classification_rationale": row["classification_rationale"],
                "planner_implication": row["planner_implication"],
                "source_output_refs": list(row["source_output_refs"]),
                "evidence_refs": list(row["evidence_refs"]),
            }
            for row in constraint_candidates
        ],
    }


def _collect_req_033_trace_input_refs(canonical_processing_input: Mapping[str, Any]) -> list[str]:
    cross_project_context = canonical_processing_input.get("cross_project_context")
    constraint_candidates = canonical_processing_input.get("constraint_candidates")

    def _rows_to_evidence_refs(rows: Any) -> list[list[str]]:
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
            return []
        refs: list[list[str]] = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            row_refs = row.get("evidence_refs")
            if isinstance(row_refs, Sequence) and not isinstance(row_refs, (str, bytes, bytearray)):
                refs.append([_as_text(ref) for ref in row_refs if _as_text(ref)])
        return refs

    source_output_refs: list[str] = []
    if isinstance(constraint_candidates, Sequence) and not isinstance(constraint_candidates, (str, bytes, bytearray)):
        for row in constraint_candidates:
            if not isinstance(row, Mapping):
                continue
            row_refs = row.get("source_output_refs")
            if isinstance(row_refs, Sequence) and not isinstance(row_refs, (str, bytes, bytearray)):
                source_output_refs.extend(_as_text(ref) for ref in row_refs if _as_text(ref))

    required_evidence_refs = canonical_processing_input.get("required_evidence_refs")
    if not isinstance(required_evidence_refs, Sequence) or isinstance(required_evidence_refs, (str, bytes, bytearray)):
        required_evidence_refs = []

    return _collect_unique_refs(
        [_as_text(ref) for ref in required_evidence_refs if _as_text(ref)],
        source_output_refs,
        *(_rows_to_evidence_refs(cross_project_context)),
        *(_rows_to_evidence_refs(constraint_candidates)),
    )


def _build_req_033_llm_call_trace_rows(
    *,
    canonical_input_sha: str,
    processing_input_sha: str,
    processing_call_id: str,
    canonical_processing_input: Mapping[str, Any],
    hard_constraint_count: int,
    soft_preference_count: int,
    speculative_idea_count: int,
) -> list[dict[str, Any]]:
    plan_id = f"req033-plan-{processing_input_sha[:16]}"
    call_id = f"req033-call-{REQ_033_CALL_SEQUENCE:02d}-{canonical_input_sha[:10]}"
    output_ref = _build_call_output_ref(
        plan_id=plan_id,
        call_id=call_id,
        expected_output=REQ_033_TRACE_EXPECTED_OUTPUT,
    )
    return [
        {
            "schema_version": REQ_025_LLM_CALL_TRACE_SCHEMA_VERSION,
            "requirement_id": REQ_033_REQUIREMENT_ID,
            "plan_id": plan_id,
            "processing_call_id": processing_call_id,
            "call_id": call_id,
            "sequence": REQ_033_CALL_SEQUENCE,
            "call_objective": REQ_033_TRACE_CALL_OBJECTIVE,
            "depends_on": [],
            "expected_output": REQ_033_TRACE_EXPECTED_OUTPUT,
            "input_refs": _collect_req_033_trace_input_refs(canonical_processing_input),
            "output_refs": [output_ref],
            "handoff_summary": (
                f"Call {REQ_033_CALL_SEQUENCE} hands off {REQ_033_TRACE_EXPECTED_OUTPUT} via {output_ref} "
                f"after classifying {hard_constraint_count} hard constraint(s), "
                f"{soft_preference_count} soft preference(s), and {speculative_idea_count} speculative idea(s)."
            ),
        }
    ]


def _req_033_recommendation_decision(
    *,
    planner_contract: Mapping[str, Any],
    open_risks: Sequence[Mapping[str, Any]],
) -> str:
    if open_risks:
        return "resolve-classification-collision"
    hard_constraints = planner_contract.get("hard_constraints")
    soft_preferences = planner_contract.get("soft_preferences")
    speculative_ideas = planner_contract.get("speculative_ideas")
    if (
        isinstance(hard_constraints, Sequence)
        and not isinstance(hard_constraints, (str, bytes, bytearray))
        and hard_constraints
    ) or (
        isinstance(soft_preferences, Sequence)
        and not isinstance(soft_preferences, (str, bytes, bytearray))
        and soft_preferences
    ):
        return "ready-for-planner"
    if (
        isinstance(speculative_ideas, Sequence)
        and not isinstance(speculative_ideas, (str, bytes, bytearray))
        and speculative_ideas
    ):
        return "ideas-only"
    return "insufficient-context"


def _req_033_recommendation_rationale(*, decision: str) -> str:
    if decision == "resolve-classification-collision":
        return "The same source output was classified into multiple buckets and must be disambiguated before planner use."
    if decision == "ready-for-planner":
        return "Planner-consumable constraints and preferences are explicit, evidence-backed, and separated from speculation."
    if decision == "ideas-only":
        return "Only speculative ideas are available, so planner obligations should not be inferred yet."
    return "No classified strategy outputs were supplied for planner consumption."


def _req_033_recommendation_confidence(
    *,
    evidence_refs: Sequence[str],
    planner_contract: Mapping[str, Any],
    open_risks: Sequence[Mapping[str, Any]],
) -> str:
    if not evidence_refs or open_risks:
        return "low"
    if planner_contract.get("hard_constraints") or planner_contract.get("soft_preferences"):
        return "high"
    if planner_contract.get("speculative_ideas"):
        return "medium"
    return "low"


def _build_req_033_processing_behavior(
    *,
    target_project_root: str,
    earth_root: str,
    strategy_goal: str,
    target_project_evidence_refs: list[str],
    earth_sweep_evidence_refs: list[str],
    cross_project_context: list[dict[str, Any]],
    constraint_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    cross_project_refs = _collect_unique_refs(*[row["evidence_refs"] for row in cross_project_context])
    classification_reasoning = [
        {
            "candidate_id": row["candidate_id"],
            "summary": row["summary"],
            "classification": row["classification"],
            "classification_rationale": row["classification_rationale"],
            "planner_implication": row["planner_implication"],
            "source_output_refs": list(row["source_output_refs"]),
            "evidence_refs": list(row["evidence_refs"]),
        }
        for row in constraint_candidates
    ]

    hard_constraints = [
        {
            "candidate_id": row["candidate_id"],
            "summary": row["summary"],
            "planner_implication": row["planner_implication"],
            "classification_rationale": row["classification_rationale"],
            "source_output_refs": list(row["source_output_refs"]),
            "evidence_refs": list(row["evidence_refs"]),
        }
        for row in classification_reasoning
        if row["classification"] == "hard-constraint"
    ]
    soft_preferences = [
        {
            "candidate_id": row["candidate_id"],
            "summary": row["summary"],
            "planner_implication": row["planner_implication"],
            "classification_rationale": row["classification_rationale"],
            "source_output_refs": list(row["source_output_refs"]),
            "evidence_refs": list(row["evidence_refs"]),
        }
        for row in classification_reasoning
        if row["classification"] == "soft-preference"
    ]
    speculative_ideas = [
        {
            "candidate_id": row["candidate_id"],
            "summary": row["summary"],
            "planner_implication": row["planner_implication"],
            "classification_rationale": row["classification_rationale"],
            "source_output_refs": list(row["source_output_refs"]),
            "evidence_refs": list(row["evidence_refs"]),
        }
        for row in classification_reasoning
        if row["classification"] == "speculative-idea"
    ]

    planner_contract = {
        "classification_is_explicit": True,
        "hard_constraints": hard_constraints,
        "soft_preferences": soft_preferences,
        "speculative_ideas": speculative_ideas,
    }

    source_ref_map: dict[str, dict[str, Any]] = {}
    for row in classification_reasoning:
        for source_output_ref in row["source_output_refs"]:
            state = source_ref_map.setdefault(
                source_output_ref,
                {"candidate_ids": set(), "classifications": set(), "evidence_refs": []},
            )
            state["candidate_ids"].add(row["candidate_id"])
            state["classifications"].add(row["classification"])
            state["evidence_refs"].extend(row["evidence_refs"])

    open_risks: list[dict[str, Any]] = []
    for source_output_ref, state in sorted(source_ref_map.items()):
        classifications = sorted(state["classifications"])
        if len(classifications) < 2:
            continue
        open_risks.append(
            {
                "risk_id": f"risk-{_slug_id_fragment(source_output_ref)}",
                "summary": "A single source output ref was assigned to multiple classification buckets.",
                "reason_code": "mixed_classification_source_ref",
                "source_output_ref": source_output_ref,
                "candidate_ids": sorted(state["candidate_ids"]),
                "classifications": classifications,
                "required_evidence_refs": _collect_unique_refs(state["evidence_refs"]),
            }
        )

    evidence_refs_used = _collect_unique_refs(
        target_project_evidence_refs,
        earth_sweep_evidence_refs,
        cross_project_refs,
        *[row["evidence_refs"] for row in classification_reasoning],
        *[row["required_evidence_refs"] for row in open_risks],
    )
    recommendation_refs = _collect_unique_refs(
        target_project_evidence_refs,
        earth_sweep_evidence_refs,
        cross_project_refs,
        *[row["evidence_refs"] for row in hard_constraints],
        *[row["evidence_refs"] for row in soft_preferences],
        *[row["evidence_refs"] for row in speculative_ideas],
        *[row["required_evidence_refs"] for row in open_risks],
    )
    recommendation_decision = _req_033_recommendation_decision(
        planner_contract=planner_contract,
        open_risks=open_risks,
    )

    return {
        "strategy": REQ_033_STRATEGY,
        "reasoning_mode": EXECUTION_MODE,
        "strict_evidence_discipline": True,
        "heuristic_summarization_only": False,
        "context_inputs": {
            "target_project": {
                "project_root": target_project_root,
                "strategy_goal": strategy_goal,
                "evidence_refs": list(target_project_evidence_refs),
            },
            "earth_sweep": {
                "earth_root": earth_root,
                "evidence_refs": list(earth_sweep_evidence_refs),
            },
            "cross_project_context": [
                {
                    "project_id": row["project_id"],
                    "project_root": row["project_root"],
                    "evidence_refs": list(row["evidence_refs"]),
                    "context_note": row["context_note"],
                }
                for row in cross_project_context
            ],
            "constraint_candidates": [
                {
                    "candidate_id": row["candidate_id"],
                    "summary": row["summary"],
                    "classification": row["classification"],
                    "classification_rationale": row["classification_rationale"],
                    "planner_implication": row["planner_implication"],
                    "source_output_refs": list(row["source_output_refs"]),
                    "evidence_refs": list(row["evidence_refs"]),
                }
                for row in constraint_candidates
            ],
        },
        "context_usage": {
            "target_project_context_used": bool(strategy_goal or target_project_evidence_refs),
            "earth_sweep_context_used": bool(earth_sweep_evidence_refs),
            "cross_project_context_used": bool(cross_project_context),
            "candidate_ids_considered": [row["candidate_id"] for row in classification_reasoning],
            "classifications_present": sorted({row["classification"] for row in classification_reasoning}),
            "cross_project_projects_considered": [row["project_id"] for row in cross_project_context],
            "cross_project_refs_used": cross_project_refs,
            "evidence_refs_used": evidence_refs_used,
        },
        "call_8_reasoning": {
            "call_sequence": REQ_033_CALL_SEQUENCE,
            "reasoning_focus": REQ_033_REASONING_FOCUS,
            "classification_reasoning": classification_reasoning,
            "hard_constraint_count": len(hard_constraints),
            "soft_preference_count": len(soft_preferences),
            "speculative_idea_count": len(speculative_ideas),
        },
        "recommendation": {
            "decision": recommendation_decision,
            "rationale": _req_033_recommendation_rationale(decision=recommendation_decision),
            "confidence": _req_033_recommendation_confidence(
                evidence_refs=recommendation_refs,
                planner_contract=planner_contract,
                open_risks=open_risks,
            ),
            "evidence_refs": recommendation_refs,
            "planner_contract": planner_contract,
            "open_risks": open_risks,
        },
        "summary": (
            f"Call 8 classified {len(hard_constraints)} hard constraint(s), "
            f"{len(soft_preferences)} soft preference(s), and "
            f"{len(speculative_ideas)} speculative idea(s) for planner consumption."
        ),
    }


def build_req_033_call_8_constraint_classification_reasoning(
    *,
    target_project_root: str = DEFAULT_TARGET_PROJECT_ROOT,
    earth_root: str = DEFAULT_EARTH_ROOT,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    revision_identity: str = DEFAULT_REQ_033_REVISION_ID,
    strategy_goal: str,
    call_sequence: int = REQ_033_CALL_SEQUENCE,
    evidence_refs: Sequence[Any] | None = None,
    target_project_evidence_refs: Sequence[Any] | None = None,
    earth_sweep_evidence_refs: Sequence[Any] | None = None,
    cross_project_context: Sequence[Mapping[str, Any]] | None = None,
    constraint_candidates: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the REQ-033 Call-8 constraint classification reasoning payload."""
    normalized_target_root = _normalize_root(target_project_root, field_name="target_project_root")
    normalized_earth_root = _normalize_root(earth_root, field_name="earth_root")
    normalized_output_root = _normalize_root(output_root, field_name="output_root")
    normalized_revision_identity = _require_text(revision_identity, field_name="revision_identity")
    normalized_strategy_goal = _require_text(strategy_goal, field_name="strategy_goal")
    normalized_call_sequence = _normalize_req_033_call_sequence(call_sequence)
    normalized_evidence_refs = _normalize_string_list(evidence_refs, field_name="evidence_refs", min_items=1)
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
    normalized_constraint_candidates = _normalize_req_033_constraint_candidates(constraint_candidates)

    canonical_input = _canonical_req_033_input(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        output_root=normalized_output_root,
        revision_identity=normalized_revision_identity,
        strategy_goal=normalized_strategy_goal,
        call_sequence=normalized_call_sequence,
    )
    canonical_input_sha = _canonical_digest(canonical_input)

    canonical_processing_input = _canonical_req_033_processing_input(
        evidence_refs=normalized_evidence_refs,
        target_project_evidence_refs=normalized_target_project_evidence_refs,
        earth_sweep_evidence_refs=normalized_earth_sweep_evidence_refs,
        cross_project_context=normalized_cross_project_context,
        constraint_candidates=normalized_constraint_candidates,
    )
    processing_sha = _canonical_digest(canonical_processing_input)

    processing_behavior = _build_req_033_processing_behavior(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        strategy_goal=normalized_strategy_goal,
        target_project_evidence_refs=normalized_target_project_evidence_refs,
        earth_sweep_evidence_refs=normalized_earth_sweep_evidence_refs,
        cross_project_context=normalized_cross_project_context,
        constraint_candidates=normalized_constraint_candidates,
    )
    processing_call_id = f"req033-processing-{processing_sha[:16]}"
    llm_call_trace_rows = _build_req_033_llm_call_trace_rows(
        canonical_input_sha=canonical_input_sha,
        processing_input_sha=processing_sha,
        processing_call_id=processing_call_id,
        canonical_processing_input=canonical_processing_input,
        hard_constraint_count=processing_behavior["call_8_reasoning"]["hard_constraint_count"],
        soft_preference_count=processing_behavior["call_8_reasoning"]["soft_preference_count"],
        speculative_idea_count=processing_behavior["call_8_reasoning"]["speculative_idea_count"],
    )
    llm_call_trace_sha = _canonical_digest(llm_call_trace_rows)

    return {
        "schema_version": REQ_033_SCHEMA_VERSION,
        "requirement_id": REQ_033_REQUIREMENT_ID,
        "call_8_constraint_classification_reasoning_entrypoint": {
            "runtime_mode": RUNTIME_MODE,
            "execution_mode": EXECUTION_MODE,
            "target_project_root": normalized_target_root,
            "earth_root": normalized_earth_root,
            "output_root": normalized_output_root,
            "revision_identity": normalized_revision_identity,
            "strategy_goal": normalized_strategy_goal,
            "call_sequence": normalized_call_sequence,
        },
        "processing_behavior": processing_behavior,
        "call_metadata": {
            "reproducibility": "deterministic-input-fingerprint",
            "canonical_input_sha256": canonical_input_sha,
            "reproducible_call_id": f"req033-{canonical_input_sha[:16]}",
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


def validate_req_033_call_8_constraint_classification_reasoning(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-033 payload shape and deterministic Call-8 classification content."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    required_top = {
        "schema_version",
        "requirement_id",
        "call_8_constraint_classification_reasoning_entrypoint",
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

    if payload.get("schema_version") != REQ_033_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_033_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_033_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_033_REQUIREMENT_ID}")

    entrypoint = payload.get("call_8_constraint_classification_reasoning_entrypoint")
    if not isinstance(entrypoint, Mapping):
        errors.append("call_8_constraint_classification_reasoning_entrypoint must be an object")
        return errors

    required_entrypoint = {
        "runtime_mode",
        "execution_mode",
        "target_project_root",
        "earth_root",
        "output_root",
        "revision_identity",
        "strategy_goal",
        "call_sequence",
    }
    entrypoint_keys = set(entrypoint.keys())
    missing_entrypoint = sorted(required_entrypoint - entrypoint_keys)
    if missing_entrypoint:
        errors.append(f"call_8_constraint_classification_reasoning_entrypoint missing keys: {missing_entrypoint}")
    unexpected_entrypoint = sorted(entrypoint_keys - required_entrypoint)
    if unexpected_entrypoint:
        errors.append(
            f"call_8_constraint_classification_reasoning_entrypoint unexpected keys: {unexpected_entrypoint}"
        )

    if entrypoint.get("runtime_mode") != RUNTIME_MODE:
        errors.append(f"call_8_constraint_classification_reasoning_entrypoint.runtime_mode must be {RUNTIME_MODE}")
    if entrypoint.get("execution_mode") != EXECUTION_MODE:
        errors.append(f"call_8_constraint_classification_reasoning_entrypoint.execution_mode must be {EXECUTION_MODE}")
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

    call_sequence = entrypoint.get("call_sequence")
    if call_sequence != REQ_033_CALL_SEQUENCE:
        errors.append(f"call_sequence must be {REQ_033_CALL_SEQUENCE}")
        call_sequence = REQ_033_CALL_SEQUENCE

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
        "call_8_reasoning",
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

    if processing_behavior.get("strategy") != REQ_033_STRATEGY:
        errors.append(f"processing_behavior.strategy must be {REQ_033_STRATEGY}")
    if processing_behavior.get("reasoning_mode") != EXECUTION_MODE:
        errors.append(f"processing_behavior.reasoning_mode must be {EXECUTION_MODE}")
    if processing_behavior.get("strict_evidence_discipline") is not True:
        errors.append("processing_behavior.strict_evidence_discipline must be true")
    if processing_behavior.get("heuristic_summarization_only") is not False:
        errors.append("processing_behavior.heuristic_summarization_only must be false")

    normalized_target_project_refs: list[str] = []
    normalized_earth_sweep_refs: list[str] = []
    normalized_cross_project_context: list[dict[str, Any]] = []
    normalized_constraint_candidates: list[dict[str, Any]] = []
    expected_processing_behavior: dict[str, Any] | None = None

    context_inputs = processing_behavior.get("context_inputs")
    if not isinstance(context_inputs, Mapping):
        errors.append("processing_behavior.context_inputs must be an object")
    else:
        target_project = context_inputs.get("target_project")
        if not isinstance(target_project, Mapping):
            errors.append("processing_behavior.context_inputs.target_project must be an object")
        else:
            if target_project.get("project_root") != entrypoint.get("target_project_root"):
                errors.append(
                    "processing_behavior.context_inputs.target_project.project_root must match entrypoint.target_project_root"
                )
            if target_project.get("strategy_goal") != entrypoint.get("strategy_goal"):
                errors.append(
                    "processing_behavior.context_inputs.target_project.strategy_goal must match entrypoint.strategy_goal"
                )
            try:
                normalized_target_project_refs = _normalize_string_list(
                    target_project.get("evidence_refs"),
                    field_name="processing_behavior.context_inputs.target_project.evidence_refs",
                )
            except ValueError as exc:
                errors.append(str(exc))

        earth_sweep = context_inputs.get("earth_sweep")
        if not isinstance(earth_sweep, Mapping):
            errors.append("processing_behavior.context_inputs.earth_sweep must be an object")
        else:
            if earth_sweep.get("earth_root") != entrypoint.get("earth_root"):
                errors.append("processing_behavior.context_inputs.earth_sweep.earth_root must match entrypoint.earth_root")
            try:
                normalized_earth_sweep_refs = _normalize_string_list(
                    earth_sweep.get("evidence_refs"),
                    field_name="processing_behavior.context_inputs.earth_sweep.evidence_refs",
                )
            except ValueError as exc:
                errors.append(str(exc))

        try:
            normalized_cross_project_context = _normalize_cross_project_context(
                context_inputs.get("cross_project_context")
            )
        except ValueError as exc:
            errors.append(str(exc))
        try:
            normalized_constraint_candidates = _normalize_req_033_constraint_candidates(
                context_inputs.get("constraint_candidates")
            )
        except ValueError as exc:
            errors.append(str(exc))

    context_usage = processing_behavior.get("context_usage")
    if not isinstance(context_usage, Mapping):
        errors.append("processing_behavior.context_usage must be an object")
    else:
        for key in (
            "target_project_context_used",
            "earth_sweep_context_used",
            "cross_project_context_used",
            "candidate_ids_considered",
            "classifications_present",
            "cross_project_projects_considered",
            "cross_project_refs_used",
            "evidence_refs_used",
        ):
            if key not in context_usage:
                errors.append(f"processing_behavior.context_usage missing keys: ['{key}']")

    call_8_reasoning = processing_behavior.get("call_8_reasoning")
    if not isinstance(call_8_reasoning, Mapping):
        errors.append("processing_behavior.call_8_reasoning must be an object")
    else:
        required_reasoning = {
            "call_sequence",
            "reasoning_focus",
            "classification_reasoning",
            "hard_constraint_count",
            "soft_preference_count",
            "speculative_idea_count",
        }
        reasoning_keys = set(call_8_reasoning.keys())
        missing_reasoning = sorted(required_reasoning - reasoning_keys)
        if missing_reasoning:
            errors.append(f"processing_behavior.call_8_reasoning missing keys: {missing_reasoning}")
        unexpected_reasoning = sorted(reasoning_keys - required_reasoning)
        if unexpected_reasoning:
            errors.append(f"processing_behavior.call_8_reasoning unexpected keys: {unexpected_reasoning}")
        if call_8_reasoning.get("call_sequence") != REQ_033_CALL_SEQUENCE:
            errors.append(f"processing_behavior.call_8_reasoning.call_sequence must be {REQ_033_CALL_SEQUENCE}")
        if call_8_reasoning.get("reasoning_focus") != REQ_033_REASONING_FOCUS:
            errors.append(f"processing_behavior.call_8_reasoning.reasoning_focus must be {REQ_033_REASONING_FOCUS}")

    recommendation = processing_behavior.get("recommendation")
    if not isinstance(recommendation, Mapping):
        errors.append("processing_behavior.recommendation must be an object")
    else:
        required_recommendation = {
            "decision",
            "rationale",
            "confidence",
            "evidence_refs",
            "planner_contract",
            "open_risks",
        }
        recommendation_keys = set(recommendation.keys())
        missing_recommendation = sorted(required_recommendation - recommendation_keys)
        if missing_recommendation:
            errors.append(f"processing_behavior.recommendation missing keys: {missing_recommendation}")
        if not isinstance(recommendation.get("evidence_refs"), list):
            errors.append("processing_behavior.recommendation.evidence_refs must be a list")
        planner_contract = recommendation.get("planner_contract")
        if not isinstance(planner_contract, Mapping):
            errors.append("processing_behavior.recommendation.planner_contract must be an object")
        else:
            required_planner_contract = {
                "classification_is_explicit",
                "hard_constraints",
                "soft_preferences",
                "speculative_ideas",
            }
            planner_contract_keys = set(planner_contract.keys())
            missing_planner_contract = sorted(required_planner_contract - planner_contract_keys)
            if missing_planner_contract:
                errors.append(
                    f"processing_behavior.recommendation.planner_contract missing keys: {missing_planner_contract}"
                )
            if planner_contract.get("classification_is_explicit") is not True:
                errors.append(
                    "processing_behavior.recommendation.planner_contract.classification_is_explicit must be true"
                )
            for key in ("hard_constraints", "soft_preferences", "speculative_ideas"):
                if not isinstance(planner_contract.get(key), list):
                    errors.append(f"processing_behavior.recommendation.planner_contract.{key} must be a list")
        if not isinstance(recommendation.get("open_risks"), list):
            errors.append("processing_behavior.recommendation.open_risks must be a list")

    if normalized_constraint_candidates:
        try:
            expected_processing_behavior = _build_req_033_processing_behavior(
                target_project_root=_as_text(entrypoint.get("target_project_root")),
                earth_root=_as_text(entrypoint.get("earth_root")),
                strategy_goal=_as_text(entrypoint.get("strategy_goal")),
                target_project_evidence_refs=normalized_target_project_refs,
                earth_sweep_evidence_refs=normalized_earth_sweep_refs,
                cross_project_context=normalized_cross_project_context,
                constraint_candidates=normalized_constraint_candidates,
            )
        except ValueError as exc:
            errors.append(f"processing_behavior could not be reconstructed: {exc}")
        else:
            if dict(processing_behavior) != expected_processing_behavior:
                errors.append("processing_behavior must match deterministic Call-8 reasoning output")

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
    expected_canonical_input = _canonical_req_033_input(
        target_project_root=_as_text(entrypoint.get("target_project_root")),
        earth_root=_as_text(entrypoint.get("earth_root")),
        output_root=_as_text(entrypoint.get("output_root")),
        revision_identity=_as_text(entrypoint.get("revision_identity")),
        strategy_goal=_as_text(entrypoint.get("strategy_goal")),
        call_sequence=int(call_sequence),
    )
    if dict(canonical_input) != expected_canonical_input:
        errors.append("call_metadata.canonical_input must mirror normalized invocation anchors")
    expected_input_sha = _canonical_digest(expected_canonical_input)
    if metadata.get("canonical_input_sha256") != expected_input_sha:
        errors.append("call_metadata.canonical_input_sha256 does not match canonical input")
    if metadata.get("reproducible_call_id") != f"req033-{expected_input_sha[:16]}":
        errors.append("call_metadata.reproducible_call_id does not match canonical digest")

    canonical_processing_input = metadata.get("canonical_processing_input")
    if not isinstance(canonical_processing_input, Mapping):
        errors.append("call_metadata.canonical_processing_input must be an object")
        return errors

    if metadata.get("llm_call_trace_schema_version") != REQ_025_LLM_CALL_TRACE_SCHEMA_VERSION:
        errors.append(
            f"call_metadata.llm_call_trace_schema_version must be {REQ_025_LLM_CALL_TRACE_SCHEMA_VERSION}"
        )
    if metadata.get("llm_call_trace_path") != LLM_CALL_TRACE_RELATIVE_PATH:
        errors.append(f"call_metadata.llm_call_trace_path must be {LLM_CALL_TRACE_RELATIVE_PATH}")

    if normalized_constraint_candidates:
        expected_processing_input = _canonical_req_033_processing_input(
            evidence_refs=sorted(
                set(
                    _collect_unique_refs(
                        normalized_target_project_refs,
                        normalized_earth_sweep_refs,
                        *[row["evidence_refs"] for row in normalized_cross_project_context],
                        *[row["evidence_refs"] for row in normalized_constraint_candidates],
                    )
                )
            ),
            target_project_evidence_refs=normalized_target_project_refs,
            earth_sweep_evidence_refs=normalized_earth_sweep_refs,
            cross_project_context=normalized_cross_project_context,
            constraint_candidates=normalized_constraint_candidates,
        )
        if dict(canonical_processing_input) != expected_processing_input:
            errors.append("call_metadata.canonical_processing_input must mirror processing inputs")
        expected_processing_sha = _canonical_digest(expected_processing_input)
        if metadata.get("processing_input_sha256") != expected_processing_sha:
            errors.append("call_metadata.processing_input_sha256 does not match processing input")
        if metadata.get("processing_call_id") != f"req033-processing-{expected_processing_sha[:16]}":
            errors.append("call_metadata.processing_call_id does not match processing digest")

        if expected_processing_behavior is not None:
            expected_trace_rows = _build_req_033_llm_call_trace_rows(
                canonical_input_sha=expected_input_sha,
                processing_input_sha=expected_processing_sha,
                processing_call_id=f"req033-processing-{expected_processing_sha[:16]}",
                canonical_processing_input=expected_processing_input,
                hard_constraint_count=expected_processing_behavior["call_8_reasoning"]["hard_constraint_count"],
                soft_preference_count=expected_processing_behavior["call_8_reasoning"]["soft_preference_count"],
                speculative_idea_count=expected_processing_behavior["call_8_reasoning"]["speculative_idea_count"],
            )
            if metadata.get("llm_call_trace_rows") != expected_trace_rows:
                errors.append("call_metadata.llm_call_trace_rows must mirror deterministic Call-8 trace rows")
            if metadata.get("llm_call_trace_sha256") != _canonical_digest(expected_trace_rows):
                errors.append("call_metadata.llm_call_trace_sha256 does not match llm_call_trace_rows")

    return errors


def _normalize_req_028_call_sequence(raw_value: Any) -> int:
    if isinstance(raw_value, bool) or not isinstance(raw_value, int):
        raise ValueError("call_sequence must be an integer")
    if raw_value != REQ_028_CALL_SEQUENCE:
        raise ValueError(f"call_sequence must be {REQ_028_CALL_SEQUENCE}")
    return raw_value


def _normalize_req_028_dependency_effects(raw_value: Any, *, field_name: str) -> list[dict[str, str]]:
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be an array")

    normalized: list[dict[str, str]] = []
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"{field_name}[{index}] must be an object")
        project_id = _require_text(item.get("project_id"), field_name=f"{field_name}[{index}].project_id")
        effect_summary = _require_text(
            item.get("effect_summary"),
            field_name=f"{field_name}[{index}].effect_summary",
        )
        impact = _require_text(item.get("impact"), field_name=f"{field_name}[{index}].impact")
        normalized.append(
            {
                "project_id": project_id,
                "effect_summary": effect_summary,
                "impact": impact,
            }
        )
    if not normalized:
        raise ValueError(f"{field_name} must contain at least 1 item(s)")
    normalized.sort(key=lambda row: (row["project_id"], row["effect_summary"], row["impact"]))
    return normalized


def _slug_id_fragment(value: Any) -> str:
    text = _as_text(value).lower()
    chars = [ch if ch.isalnum() else "-" for ch in text]
    collapsed = "".join(chars).strip("-")
    while "--" in collapsed:
        collapsed = collapsed.replace("--", "-")
    return collapsed or "unknown"


def _normalize_req_028_gap_candidates(raw_value: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError("gap_candidates must be an array")

    normalized: list[dict[str, Any]] = []
    seen_gap_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"gap_candidates[{index}] must be an object")
        gap_id = _require_text(item.get("gap_id"), field_name=f"gap_candidates[{index}].gap_id")
        if gap_id in seen_gap_ids:
            raise ValueError(f"gap_candidates[{index}].gap_id must be unique")
        seen_gap_ids.add(gap_id)
        summary = _require_text(item.get("summary"), field_name=f"gap_candidates[{index}].summary")
        visibility_rationale = _require_text(
            item.get("visibility_rationale"),
            field_name=f"gap_candidates[{index}].visibility_rationale",
        )
        local_mission_blind_spot = _require_text(
            item.get("local_mission_blind_spot"),
            field_name=f"gap_candidates[{index}].local_mission_blind_spot",
        )
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            field_name=f"gap_candidates[{index}].evidence_refs",
            min_items=1,
        )
        normalized.append(
            {
                "gap_id": gap_id,
                "summary": summary,
                "visibility_rationale": visibility_rationale,
                "local_mission_blind_spot": local_mission_blind_spot,
                "evidence_refs": evidence_refs,
            }
        )
    if not normalized:
        raise ValueError("gap_candidates must contain at least 1 item(s)")
    normalized.sort(key=lambda row: row["gap_id"])
    return normalized


def _normalize_req_028_opportunity_candidates(raw_value: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError("opportunity_candidates must be an array")

    normalized: list[dict[str, Any]] = []
    seen_opportunity_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"opportunity_candidates[{index}] must be an object")
        opportunity_id = _require_text(
            item.get("opportunity_id"),
            field_name=f"opportunity_candidates[{index}].opportunity_id",
        )
        if opportunity_id in seen_opportunity_ids:
            raise ValueError(f"opportunity_candidates[{index}].opportunity_id must be unique")
        seen_opportunity_ids.add(opportunity_id)
        gap_id = _require_text(item.get("gap_id"), field_name=f"opportunity_candidates[{index}].gap_id")
        summary = _require_text(item.get("summary"), field_name=f"opportunity_candidates[{index}].summary")
        ecosystem_level_benefit = _require_text(
            item.get("ecosystem_level_benefit"),
            field_name=f"opportunity_candidates[{index}].ecosystem_level_benefit",
        )
        recommendation_rationale = _require_text(
            item.get("recommendation_rationale")
            if item.get("recommendation_rationale") is not None
            else ecosystem_level_benefit,
            field_name=f"opportunity_candidates[{index}].recommendation_rationale",
        )
        dependency_effects = _normalize_req_028_dependency_effects(
            item.get("dependency_effects"),
            field_name=f"opportunity_candidates[{index}].dependency_effects",
        )
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            field_name=f"opportunity_candidates[{index}].evidence_refs",
            min_items=1,
        )
        next_step = _require_text(
            item.get("next_step")
            if item.get("next_step") is not None
            else f"Validate cross-project follow-through for {opportunity_id}.",
            field_name=f"opportunity_candidates[{index}].next_step",
        )
        normalized.append(
            {
                "opportunity_id": opportunity_id,
                "gap_id": gap_id,
                "summary": summary,
                "ecosystem_level_benefit": ecosystem_level_benefit,
                "recommendation_rationale": recommendation_rationale,
                "dependency_effects": dependency_effects,
                "evidence_refs": evidence_refs,
                "next_step": next_step,
            }
        )
    if not normalized:
        raise ValueError("opportunity_candidates must contain at least 1 item(s)")
    normalized.sort(key=lambda row: row["opportunity_id"])
    return normalized


def _normalize_req_028_strategic_claims(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError("strategic_claims must be an array when provided")

    normalized: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"strategic_claims[{index}] must be an object")
        claim_id = _require_text(item.get("claim_id"), field_name=f"strategic_claims[{index}].claim_id")
        phase = _require_text(item.get("phase"), field_name=f"strategic_claims[{index}].phase").lower()
        if phase not in {"analysis", "synthesis"}:
            raise ValueError(f"strategic_claims[{index}].phase must be analysis or synthesis")
        summary = _require_text(item.get("summary"), field_name=f"strategic_claims[{index}].summary")
        position = _require_text(item.get("position"), field_name=f"strategic_claims[{index}].position")
        source_output_ref = _require_text(
            item.get("source_output_ref"),
            field_name=f"strategic_claims[{index}].source_output_ref",
        )
        claim_key = (claim_id, phase, source_output_ref)
        if claim_key in seen_keys:
            raise ValueError(
                f"strategic_claims[{index}] duplicates claim_id/phase/source_output_ref for {claim_id}"
            )
        seen_keys.add(claim_key)
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
                "source_output_ref": source_output_ref,
                "evidence_refs": evidence_refs,
            }
        )
    normalized.sort(key=lambda row: (row["claim_id"], row["phase"], row["source_output_ref"], row["position"]))
    return normalized


def _normalize_req_028_unresolved_ideas(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError("unresolved_ideas must be an array when provided")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"unresolved_ideas[{index}] must be an object")
        project_id = _require_text(item.get("project_id"), field_name=f"unresolved_ideas[{index}].project_id")
        summary = _require_text(item.get("summary"), field_name=f"unresolved_ideas[{index}].summary")
        idea_id = _require_text(
            item.get("idea_id") if item.get("idea_id") is not None else f"idea-{index + 1:03d}-{_slug_id_fragment(project_id)}",
            field_name=f"unresolved_ideas[{index}].idea_id",
        )
        related_gap_ids = _normalize_string_list(
            item.get("related_gap_ids"),
            field_name=f"unresolved_ideas[{index}].related_gap_ids",
        )
        related_opportunity_ids = _normalize_string_list(
            item.get("related_opportunity_ids"),
            field_name=f"unresolved_ideas[{index}].related_opportunity_ids",
        )
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            field_name=f"unresolved_ideas[{index}].evidence_refs",
        )
        normalized.append(
            {
                "idea_id": idea_id,
                "project_id": project_id,
                "summary": summary,
                "related_gap_ids": related_gap_ids,
                "related_opportunity_ids": related_opportunity_ids,
                "evidence_refs": evidence_refs,
            }
        )
    normalized.sort(key=lambda row: row["idea_id"])
    return normalized


def _canonical_req_028_input(
    *,
    target_project_root: str,
    earth_root: str,
    output_root: str,
    revision_identity: str,
    strategy_goal: str,
    call_sequence: int,
) -> dict[str, Any]:
    return {
        "runtime_mode": RUNTIME_MODE,
        "execution_mode": EXECUTION_MODE,
        "target_project_root": target_project_root,
        "earth_root": earth_root,
        "output_root": output_root,
        "revision_identity": revision_identity,
        "strategy_goal": strategy_goal,
        "call_sequence": call_sequence,
    }


def _canonical_req_028_processing_input(
    *,
    evidence_refs: list[str],
    target_project_evidence_refs: list[str],
    earth_sweep_evidence_refs: list[str],
    local_mission_summary: str,
    cross_project_context: list[dict[str, Any]],
    unresolved_ideas: list[dict[str, Any]],
    gap_candidates: list[dict[str, Any]],
    opportunity_candidates: list[dict[str, Any]],
    strategic_claims: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    processing_input = {
        "required_evidence_refs": list(evidence_refs),
        "target_project_evidence_refs": list(target_project_evidence_refs),
        "earth_sweep_evidence_refs": list(earth_sweep_evidence_refs),
        "local_mission_summary": local_mission_summary,
        "cross_project_context": [
            {
                "project_id": row["project_id"],
                "project_root": row["project_root"],
                "evidence_refs": list(row["evidence_refs"]),
                "context_note": row["context_note"],
            }
            for row in cross_project_context
        ],
        "unresolved_ideas": [
            {
                "idea_id": row["idea_id"],
                "project_id": row["project_id"],
                "summary": row["summary"],
                "related_gap_ids": list(row["related_gap_ids"]),
                "related_opportunity_ids": list(row["related_opportunity_ids"]),
                "evidence_refs": list(row["evidence_refs"]),
            }
            for row in unresolved_ideas
        ],
        "gap_candidates": [
            {
                "gap_id": row["gap_id"],
                "summary": row["summary"],
                "visibility_rationale": row["visibility_rationale"],
                "local_mission_blind_spot": row["local_mission_blind_spot"],
                "evidence_refs": list(row["evidence_refs"]),
            }
            for row in gap_candidates
        ],
        "opportunity_candidates": [
            {
                "opportunity_id": row["opportunity_id"],
                "gap_id": row["gap_id"],
                "summary": row["summary"],
                "ecosystem_level_benefit": row["ecosystem_level_benefit"],
                "recommendation_rationale": row["recommendation_rationale"],
                "dependency_effects": [
                    {
                        "project_id": dep["project_id"],
                        "effect_summary": dep["effect_summary"],
                        "impact": dep["impact"],
                    }
                    for dep in row["dependency_effects"]
                ],
                "evidence_refs": list(row["evidence_refs"]),
                "next_step": row["next_step"],
            }
            for row in opportunity_candidates
        ],
    }
    if strategic_claims:
        processing_input["strategic_claims"] = [
            {
                "claim_id": row["claim_id"],
                "phase": row["phase"],
                "summary": row["summary"],
                "position": row["position"],
                "source_output_ref": row["source_output_ref"],
                "evidence_refs": list(row["evidence_refs"]),
            }
            for row in strategic_claims
        ]
    return processing_input


def _req_028_recommendation_decision(
    *,
    recommended_opportunities: Sequence[Mapping[str, Any]],
    open_risks: Sequence[Mapping[str, Any]],
) -> str:
    reason_codes = {_as_text(row.get("reason_code")) for row in open_risks}
    if {"cross_call_contradiction", "uncited_strategic_claim"}.intersection(reason_codes):
        return "resolve-strategy-gaps"
    if recommended_opportunities and not open_risks:
        return "proceed"
    if recommended_opportunities and open_risks:
        return "proceed-with-open-risks"
    if open_risks:
        if reason_codes and reason_codes == {"missing_earth_sweep_evidence_refs"}:
            return "collect-earth-evidence"
        return "resolve-context-gaps"
    return "insufficient-context"


def _req_028_recommendation_rationale(*, decision: str) -> str:
    if decision == "resolve-strategy-gaps":
        return "Call-3 detected contradictory or uncited strategic claims that must be resolved before promotion."
    if decision == "proceed":
        return "Earth-sweep evidence and cross-project context are sufficient to promote Call-3 opportunities."
    if decision == "proceed-with-open-risks":
        return "Some Call-3 opportunities are evidence-backed while unresolved ecosystem ideas remain open risks."
    if decision == "collect-earth-evidence":
        return "Cross-project opportunity promotion is blocked until Earth-sweep evidence refs are attached."
    if decision == "resolve-context-gaps":
        return "Cross-project context gaps must be resolved before unsupported obligations can be promoted."
    return "No evidence-backed ecosystem opportunities were strong enough to promote from Call-3."


def _req_028_recommendation_confidence(
    *,
    evidence_refs: Sequence[str],
    recommended_opportunities: Sequence[Mapping[str, Any]],
    open_risks: Sequence[Mapping[str, Any]],
) -> str:
    if not evidence_refs:
        return "low"
    if recommended_opportunities and not open_risks:
        return "high"
    if recommended_opportunities:
        return "medium"
    return "low"


def _build_req_028_processing_behavior(
    *,
    target_project_root: str,
    earth_root: str,
    target_project_evidence_refs: list[str],
    earth_sweep_evidence_refs: list[str],
    local_mission_summary: str,
    cross_project_context: list[dict[str, Any]],
    unresolved_ideas: list[dict[str, Any]],
    gap_candidates: list[dict[str, Any]],
    opportunity_candidates: list[dict[str, Any]],
    strategic_claims: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not earth_sweep_evidence_refs:
        raise ValueError("earth_sweep_evidence_refs must contain at least 1 item(s)")

    earth_ref_set = set(earth_sweep_evidence_refs)
    context_by_project = {row["project_id"]: row for row in cross_project_context}
    gap_rows_by_id = {row["gap_id"]: row for row in gap_candidates}
    opportunities_by_gap_id: dict[str, list[dict[str, Any]]] = {gap_id: [] for gap_id in gap_rows_by_id}
    cross_project_refs = _collect_unique_refs(*[row["evidence_refs"] for row in cross_project_context])
    recommended_opportunities: list[dict[str, Any]] = []
    cross_project_obligations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    normalized_strategic_claims = list(strategic_claims or [])
    available_citation_refs = set(
        _collect_unique_refs(
            target_project_evidence_refs,
            earth_sweep_evidence_refs,
            cross_project_refs,
            *[row["evidence_refs"] for row in unresolved_ideas],
            *[row["evidence_refs"] for row in gap_candidates],
            *[row["evidence_refs"] for row in opportunity_candidates],
        )
    )

    claim_rows_by_id: dict[str, list[dict[str, Any]]] = {}
    for claim in normalized_strategic_claims:
        claim_rows_by_id.setdefault(claim["claim_id"], []).append(claim)
        citation_refs = list(claim["evidence_refs"])
        if not citation_refs or not set(citation_refs).issubset(available_citation_refs):
            open_risks.append(
                {
                    "risk_id": f"risk-claim-{claim['claim_id']}-citation",
                    "summary": claim["summary"],
                    "reason_code": "uncited_strategic_claim",
                    "required_evidence_refs": _collect_unique_refs([claim["source_output_ref"]], citation_refs),
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
                        [analysis_row["source_output_ref"]],
                        [synthesis_row["source_output_ref"]],
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

    for gap in gap_candidates:
        if not set(gap["evidence_refs"]).intersection(earth_ref_set):
            raise ValueError(f"gap_candidates[{gap['gap_id']}] must include earth_sweep evidence refs")

    for opportunity in opportunity_candidates:
        gap_id = opportunity["gap_id"]
        if gap_id not in gap_rows_by_id:
            raise ValueError(
                f"opportunity_candidates[{opportunity['opportunity_id']}].gap_id must reference a known gap_id"
            )
        if not set(opportunity["evidence_refs"]).intersection(earth_ref_set):
            raise ValueError(
                f"opportunity_candidates[{opportunity['opportunity_id']}] must include earth_sweep evidence refs"
            )
        opportunities_by_gap_id[gap_id].append(
            {
                "opportunity_id": opportunity["opportunity_id"],
                "summary": opportunity["summary"],
                "ecosystem_level_benefit": opportunity["ecosystem_level_benefit"],
                "dependency_effects": [
                    {
                        "project_id": dep["project_id"],
                        "effect_summary": dep["effect_summary"],
                        "impact": dep["impact"],
                    }
                    for dep in opportunity["dependency_effects"]
                ],
                "evidence_refs": list(opportunity["evidence_refs"]),
            }
        )

        dependency_projects = sorted({dep["project_id"] for dep in opportunity["dependency_effects"]})
        missing_reason_codes: list[str] = []
        if not set(opportunity["evidence_refs"]).intersection(earth_ref_set):
            missing_reason_codes.append("missing_earth_sweep_evidence_refs")

        linked_context_projects: list[str] = []
        linked_context_refs: list[str] = []
        missing_context_projects: list[str] = []
        missing_context_evidence_projects: list[str] = []
        for project_id in dependency_projects:
            project_context = context_by_project.get(project_id)
            if project_context is None:
                missing_context_projects.append(project_id)
                continue
            linked_context_projects.append(project_id)
            project_refs = list(project_context["evidence_refs"])
            if project_refs:
                linked_context_refs.extend(project_refs)
            else:
                missing_context_evidence_projects.append(project_id)

        if missing_context_projects:
            missing_reason_codes.append("missing_cross_project_context")
        if missing_context_evidence_projects:
            missing_reason_codes.append("missing_cross_project_context_evidence_refs")

        recommendation_row = {
            "opportunity_id": opportunity["opportunity_id"],
            "gap_id": opportunity["gap_id"],
            "summary": opportunity["summary"],
            "rationale": opportunity["recommendation_rationale"],
            "ecosystem_level_benefit": opportunity["ecosystem_level_benefit"],
            "next_step": opportunity["next_step"],
            "dependency_effects": [
                {
                    "project_id": dep["project_id"],
                    "effect_summary": dep["effect_summary"],
                    "impact": dep["impact"],
                }
                for dep in opportunity["dependency_effects"]
            ],
            "linked_context_projects": linked_context_projects,
            "evidence_refs": _collect_unique_refs(opportunity["evidence_refs"], linked_context_refs),
        }

        if missing_reason_codes:
            open_risks.append(
                {
                    "risk_id": f"risk-{opportunity['opportunity_id']}",
                    "summary": opportunity["summary"],
                    "reason_code": missing_reason_codes[0],
                    "missing_reason_codes": sorted(set(missing_reason_codes)),
                    "affected_project_ids": dependency_projects,
                    "required_evidence_refs": _collect_unique_refs(
                        opportunity["evidence_refs"],
                        linked_context_refs,
                    ),
                }
            )
            continue

        recommended_opportunities.append(recommendation_row)
        for dep in opportunity["dependency_effects"]:
            dep_project_context = context_by_project[dep["project_id"]]
            cross_project_obligations.append(
                {
                    "obligation_id": f"obligation-{opportunity['opportunity_id']}-{_slug_id_fragment(dep['project_id'])}",
                    "project_id": dep["project_id"],
                    "opportunity_id": opportunity["opportunity_id"],
                    "summary": dep["effect_summary"],
                    "impact": dep["impact"],
                    "evidence_refs": _collect_unique_refs(
                        earth_sweep_evidence_refs,
                        opportunity["evidence_refs"],
                        dep_project_context["evidence_refs"],
                    ),
                }
            )

    gap_reasoning: list[dict[str, Any]] = []
    for gap in gap_candidates:
        opportunities = opportunities_by_gap_id[gap["gap_id"]]
        if not opportunities:
            raise ValueError(f"gap_candidates[{gap['gap_id']}] must map to at least 1 opportunity candidate")
        opportunities.sort(key=lambda row: row["opportunity_id"])
        gap_reasoning.append(
            {
                "gap_id": gap["gap_id"],
                "summary": gap["summary"],
                "visibility_rationale": gap["visibility_rationale"],
                "local_mission_blind_spot": gap["local_mission_blind_spot"],
                "evidence_refs": list(gap["evidence_refs"]),
                "opportunities": opportunities,
            }
        )

    for idea in unresolved_ideas:
        open_risks.append(
            {
                "risk_id": f"risk-{idea['idea_id']}",
                "summary": idea["summary"],
                "reason_code": "unresolved_cross_project_idea",
                "project_id": idea["project_id"],
                "related_gap_ids": list(idea["related_gap_ids"]),
                "related_opportunity_ids": list(idea["related_opportunity_ids"]),
                "required_evidence_refs": list(idea["evidence_refs"]),
            }
        )

    evidence_refs_used = _collect_unique_refs(
        target_project_evidence_refs,
        earth_sweep_evidence_refs,
        cross_project_refs,
        *[row["evidence_refs"] for row in unresolved_ideas],
        *[row["evidence_refs"] for row in gap_candidates],
        *[row["evidence_refs"] for row in opportunity_candidates],
        *[row["required_evidence_refs"] for row in open_risks],
    )
    recommendation_refs = _collect_unique_refs(
        target_project_evidence_refs,
        earth_sweep_evidence_refs,
        cross_project_refs,
        *[row["evidence_refs"] for row in recommended_opportunities],
        *[row["evidence_refs"] for row in cross_project_obligations],
        *[row["required_evidence_refs"] for row in open_risks],
    )
    recommendation_decision = _req_028_recommendation_decision(
        recommended_opportunities=recommended_opportunities,
        open_risks=open_risks,
    )

    return {
        "strategy": REQ_028_STRATEGY,
        "reasoning_mode": EXECUTION_MODE,
        "strict_evidence_discipline": True,
        "heuristic_summarization_only": False,
        "context_inputs": {
            "target_project": {
                "project_root": target_project_root,
                "mission_summary": local_mission_summary,
                "evidence_refs": list(target_project_evidence_refs),
            },
            "earth_sweep": {
                "earth_root": earth_root,
                "evidence_refs": list(earth_sweep_evidence_refs),
            },
            "gap_candidates": [
                {
                    "gap_id": row["gap_id"],
                    "summary": row["summary"],
                    "visibility_rationale": row["visibility_rationale"],
                    "local_mission_blind_spot": row["local_mission_blind_spot"],
                    "evidence_refs": list(row["evidence_refs"]),
                }
                for row in gap_candidates
            ],
            "opportunity_candidates": [
                {
                    "opportunity_id": row["opportunity_id"],
                    "gap_id": row["gap_id"],
                    "summary": row["summary"],
                    "ecosystem_level_benefit": row["ecosystem_level_benefit"],
                    "recommendation_rationale": row["recommendation_rationale"],
                    "dependency_effects": [
                        {
                            "project_id": dep["project_id"],
                            "effect_summary": dep["effect_summary"],
                            "impact": dep["impact"],
                        }
                        for dep in row["dependency_effects"]
                    ],
                    "evidence_refs": list(row["evidence_refs"]),
                    "next_step": row["next_step"],
                }
                for row in opportunity_candidates
            ],
            "cross_project_context": [
                {
                    "project_id": row["project_id"],
                    "project_root": row["project_root"],
                    "evidence_refs": list(row["evidence_refs"]),
                    "context_note": row["context_note"],
                }
                for row in cross_project_context
            ],
            "unresolved_ideas": [
                {
                    "idea_id": row["idea_id"],
                    "project_id": row["project_id"],
                    "summary": row["summary"],
                    "related_gap_ids": list(row["related_gap_ids"]),
                    "related_opportunity_ids": list(row["related_opportunity_ids"]),
                    "evidence_refs": list(row["evidence_refs"]),
                }
                for row in unresolved_ideas
            ],
        },
        "context_usage": {
            "target_project_context_used": bool(local_mission_summary or target_project_evidence_refs),
            "earth_sweep_context_used": bool(earth_sweep_evidence_refs),
            "cross_project_context_used": bool(cross_project_context),
            "gap_ids_considered": [row["gap_id"] for row in gap_candidates],
            "opportunity_ids_considered": [row["opportunity_id"] for row in opportunity_candidates],
            "cross_project_projects_considered": [row["project_id"] for row in cross_project_context],
            "dependency_projects_referenced": sorted(
                {dep["project_id"] for row in opportunity_candidates for dep in row["dependency_effects"]}
            ),
            "cross_project_refs_used": cross_project_refs,
            "evidence_refs_used": evidence_refs_used,
        },
        "call_3_reasoning": {
            "call_sequence": REQ_028_CALL_SEQUENCE,
            "reasoning_focus": REQ_028_REASONING_FOCUS,
            "gap_reasoning": gap_reasoning,
            "gap_count": len(gap_reasoning),
            "opportunity_count": len(opportunity_candidates),
        },
        "recommendation": {
            "decision": recommendation_decision,
            "rationale": _req_028_recommendation_rationale(
                decision=recommendation_decision
            ),
            "confidence": _req_028_recommendation_confidence(
                evidence_refs=recommendation_refs,
                recommended_opportunities=recommended_opportunities,
                open_risks=open_risks,
            ),
            "evidence_refs": recommendation_refs,
            "recommended_opportunities": sorted(
                recommended_opportunities,
                key=lambda row: row["opportunity_id"],
            ),
            "cross_project_obligations": sorted(
                cross_project_obligations,
                key=lambda row: row["obligation_id"],
            ),
            "open_risks": sorted(open_risks, key=lambda row: row["risk_id"]),
        },
        "summary": (
            f"Call 3 reasoned over {len(gap_reasoning)} ecosystem-visible strategic gaps and "
            f"{len(opportunity_candidates)} linked opportunities with ecosystem benefits and dependency effects."
        ),
    }


def build_req_028_call_3_gap_and_opportunity_reasoning(
    *,
    target_project_root: str,
    earth_root: str,
    output_root: str,
    revision_identity: str,
    strategy_goal: str,
    call_sequence: int = REQ_028_CALL_SEQUENCE,
    evidence_refs: Sequence[Any] | None = None,
    target_project_evidence_refs: Sequence[Any] | None = None,
    earth_sweep_evidence_refs: Sequence[Any] | None = None,
    local_mission_summary: str,
    cross_project_context: Sequence[Mapping[str, Any]] | None = None,
    unresolved_ideas: Sequence[Mapping[str, Any]] | None = None,
    gap_candidates: Sequence[Mapping[str, Any]] | None = None,
    opportunity_candidates: Sequence[Mapping[str, Any]] | None = None,
    strategic_claims: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the REQ-028 Call-3 gap and opportunity reasoning payload."""
    normalized_target_root = _normalize_root(target_project_root, field_name="target_project_root")
    normalized_earth_root = _normalize_root(earth_root, field_name="earth_root")
    normalized_output_root = _normalize_root(output_root, field_name="output_root")
    normalized_revision_identity = _require_text(revision_identity, field_name="revision_identity")
    normalized_strategy_goal = _require_text(strategy_goal, field_name="strategy_goal")
    normalized_call_sequence = _normalize_req_028_call_sequence(call_sequence)
    normalized_evidence_refs = _normalize_string_list(evidence_refs, field_name="evidence_refs", min_items=1)
    normalized_local_mission_summary = _require_text(local_mission_summary, field_name="local_mission_summary")
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
    normalized_unresolved_ideas = _normalize_req_028_unresolved_ideas(unresolved_ideas)
    normalized_gap_candidates = _normalize_req_028_gap_candidates(gap_candidates)
    normalized_opportunity_candidates = _normalize_req_028_opportunity_candidates(opportunity_candidates)
    normalized_strategic_claims = _normalize_req_028_strategic_claims(strategic_claims)

    canonical_input = _canonical_req_028_input(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        output_root=normalized_output_root,
        revision_identity=normalized_revision_identity,
        strategy_goal=normalized_strategy_goal,
        call_sequence=normalized_call_sequence,
    )
    canonical_input_sha = _canonical_digest(canonical_input)

    canonical_processing_input = _canonical_req_028_processing_input(
        evidence_refs=normalized_evidence_refs,
        target_project_evidence_refs=normalized_target_project_evidence_refs,
        earth_sweep_evidence_refs=normalized_earth_sweep_evidence_refs,
        local_mission_summary=normalized_local_mission_summary,
        cross_project_context=normalized_cross_project_context,
        unresolved_ideas=normalized_unresolved_ideas,
        gap_candidates=normalized_gap_candidates,
        opportunity_candidates=normalized_opportunity_candidates,
        strategic_claims=normalized_strategic_claims,
    )
    processing_sha = _canonical_digest(canonical_processing_input)

    processing_behavior = _build_req_028_processing_behavior(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        target_project_evidence_refs=normalized_target_project_evidence_refs,
        earth_sweep_evidence_refs=normalized_earth_sweep_evidence_refs,
        local_mission_summary=normalized_local_mission_summary,
        cross_project_context=normalized_cross_project_context,
        unresolved_ideas=normalized_unresolved_ideas,
        gap_candidates=normalized_gap_candidates,
        opportunity_candidates=normalized_opportunity_candidates,
        strategic_claims=normalized_strategic_claims,
    )
    processing_call_id = f"req028-processing-{processing_sha[:16]}"
    llm_call_trace_rows = _build_req_028_llm_call_trace_rows(
        canonical_input_sha=canonical_input_sha,
        processing_input_sha=processing_sha,
        processing_call_id=processing_call_id,
        canonical_processing_input=canonical_processing_input,
        gap_count=len(normalized_gap_candidates),
        opportunity_count=len(normalized_opportunity_candidates),
    )
    llm_call_trace_sha = _canonical_digest(llm_call_trace_rows)

    return {
        "schema_version": REQ_028_SCHEMA_VERSION,
        "requirement_id": REQ_028_REQUIREMENT_ID,
        "call_3_gap_and_opportunity_reasoning_entrypoint": {
            "runtime_mode": RUNTIME_MODE,
            "execution_mode": EXECUTION_MODE,
            "target_project_root": normalized_target_root,
            "earth_root": normalized_earth_root,
            "output_root": normalized_output_root,
            "revision_identity": normalized_revision_identity,
            "strategy_goal": normalized_strategy_goal,
            "call_sequence": normalized_call_sequence,
        },
        "processing_behavior": processing_behavior,
        "call_metadata": {
            "reproducibility": "deterministic-input-fingerprint",
            "canonical_input_sha256": canonical_input_sha,
            "reproducible_call_id": f"req028-{canonical_input_sha[:16]}",
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


def validate_req_028_call_3_gap_and_opportunity_reasoning(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-028 payload shape and deterministic Call-3 reasoning content."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    required_top = {
        "schema_version",
        "requirement_id",
        "call_3_gap_and_opportunity_reasoning_entrypoint",
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

    if payload.get("schema_version") != REQ_028_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_028_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_028_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_028_REQUIREMENT_ID}")

    entrypoint = payload.get("call_3_gap_and_opportunity_reasoning_entrypoint")
    if not isinstance(entrypoint, Mapping):
        errors.append("call_3_gap_and_opportunity_reasoning_entrypoint must be an object")
        return errors

    required_entrypoint = {
        "runtime_mode",
        "execution_mode",
        "target_project_root",
        "earth_root",
        "output_root",
        "revision_identity",
        "strategy_goal",
        "call_sequence",
    }
    entrypoint_keys = set(entrypoint.keys())
    missing_entrypoint = sorted(required_entrypoint - entrypoint_keys)
    if missing_entrypoint:
        errors.append(f"call_3_gap_and_opportunity_reasoning_entrypoint missing keys: {missing_entrypoint}")
    unexpected_entrypoint = sorted(entrypoint_keys - required_entrypoint)
    if unexpected_entrypoint:
        errors.append(f"call_3_gap_and_opportunity_reasoning_entrypoint unexpected keys: {unexpected_entrypoint}")

    if entrypoint.get("runtime_mode") != RUNTIME_MODE:
        errors.append(f"call_3_gap_and_opportunity_reasoning_entrypoint.runtime_mode must be {RUNTIME_MODE}")
    if entrypoint.get("execution_mode") != EXECUTION_MODE:
        errors.append(f"call_3_gap_and_opportunity_reasoning_entrypoint.execution_mode must be {EXECUTION_MODE}")
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

    call_sequence = entrypoint.get("call_sequence")
    if call_sequence != REQ_028_CALL_SEQUENCE:
        errors.append(f"call_sequence must be {REQ_028_CALL_SEQUENCE}")
        call_sequence = REQ_028_CALL_SEQUENCE

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
        "call_3_reasoning",
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

    if processing_behavior.get("strategy") != REQ_028_STRATEGY:
        errors.append(f"processing_behavior.strategy must be {REQ_028_STRATEGY}")
    if processing_behavior.get("reasoning_mode") != EXECUTION_MODE:
        errors.append(f"processing_behavior.reasoning_mode must be {EXECUTION_MODE}")
    if processing_behavior.get("strict_evidence_discipline") is not True:
        errors.append("processing_behavior.strict_evidence_discipline must be true")
    if processing_behavior.get("heuristic_summarization_only") is not False:
        errors.append("processing_behavior.heuristic_summarization_only must be false")

    normalized_target_project_refs: list[str] = []
    normalized_earth_sweep_refs: list[str] = []
    normalized_local_mission_summary = ""
    normalized_cross_project_context: list[dict[str, Any]] = []
    normalized_unresolved_ideas: list[dict[str, Any]] = []
    normalized_gap_candidates: list[dict[str, Any]] = []
    normalized_opportunity_candidates: list[dict[str, Any]] = []
    normalized_strategic_claims: list[dict[str, Any]] = []
    metadata = payload.get("call_metadata")
    if isinstance(metadata, Mapping):
        canonical_processing_input_preview = metadata.get("canonical_processing_input")
        if isinstance(canonical_processing_input_preview, Mapping) and "strategic_claims" in canonical_processing_input_preview:
            try:
                normalized_strategic_claims = _normalize_req_028_strategic_claims(
                    canonical_processing_input_preview.get("strategic_claims")
                )
            except ValueError as exc:
                errors.append(str(exc))
    context_inputs = processing_behavior.get("context_inputs")
    if not isinstance(context_inputs, Mapping):
        errors.append("processing_behavior.context_inputs must be an object")
    else:
        target_project = context_inputs.get("target_project")
        if not isinstance(target_project, Mapping):
            errors.append("processing_behavior.context_inputs.target_project must be an object")
        else:
            if target_project.get("project_root") != entrypoint.get("target_project_root"):
                errors.append(
                    "processing_behavior.context_inputs.target_project.project_root must match entrypoint.target_project_root"
                )
            mission_summary = target_project.get("mission_summary")
            if not isinstance(mission_summary, str) or not mission_summary.strip():
                errors.append("processing_behavior.context_inputs.target_project.mission_summary must be non-empty")
            else:
                normalized_local_mission_summary = mission_summary.strip()
            target_refs = target_project.get("evidence_refs")
            try:
                normalized_target_project_refs = _normalize_string_list(
                    target_refs,
                    field_name="processing_behavior.context_inputs.target_project.evidence_refs",
                )
            except ValueError as exc:
                errors.append(str(exc))

        earth_sweep = context_inputs.get("earth_sweep")
        if not isinstance(earth_sweep, Mapping):
            errors.append("processing_behavior.context_inputs.earth_sweep must be an object")
        else:
            if earth_sweep.get("earth_root") != entrypoint.get("earth_root"):
                errors.append("processing_behavior.context_inputs.earth_sweep.earth_root must match entrypoint.earth_root")
            earth_refs = earth_sweep.get("evidence_refs")
            try:
                normalized_earth_sweep_refs = _normalize_string_list(
                    earth_refs,
                    field_name="processing_behavior.context_inputs.earth_sweep.evidence_refs",
                    min_items=1,
                )
            except ValueError as exc:
                errors.append(str(exc))

        try:
            normalized_gap_candidates = _normalize_req_028_gap_candidates(context_inputs.get("gap_candidates"))
        except ValueError as exc:
            errors.append(str(exc))
        try:
            normalized_opportunity_candidates = _normalize_req_028_opportunity_candidates(
                context_inputs.get("opportunity_candidates")
            )
        except ValueError as exc:
            errors.append(str(exc))
        try:
            normalized_cross_project_context = _normalize_cross_project_context(
                context_inputs.get("cross_project_context")
            )
        except ValueError as exc:
            errors.append(str(exc))
        try:
            normalized_unresolved_ideas = _normalize_req_028_unresolved_ideas(context_inputs.get("unresolved_ideas"))
        except ValueError as exc:
            errors.append(str(exc))

    context_usage = processing_behavior.get("context_usage")
    if not isinstance(context_usage, Mapping):
        errors.append("processing_behavior.context_usage must be an object")
    else:
        for key in (
            "target_project_context_used",
            "earth_sweep_context_used",
            "cross_project_context_used",
            "gap_ids_considered",
            "opportunity_ids_considered",
            "cross_project_projects_considered",
            "dependency_projects_referenced",
            "cross_project_refs_used",
            "evidence_refs_used",
        ):
            if key not in context_usage:
                errors.append(f"processing_behavior.context_usage missing keys: ['{key}']")

    call_3_reasoning = processing_behavior.get("call_3_reasoning")
    if not isinstance(call_3_reasoning, Mapping):
        errors.append("processing_behavior.call_3_reasoning must be an object")
    else:
        required_reasoning = {
            "call_sequence",
            "reasoning_focus",
            "gap_reasoning",
            "gap_count",
            "opportunity_count",
        }
        reasoning_keys = set(call_3_reasoning.keys())
        missing_reasoning = sorted(required_reasoning - reasoning_keys)
        if missing_reasoning:
            errors.append(f"processing_behavior.call_3_reasoning missing keys: {missing_reasoning}")
        unexpected_reasoning = sorted(reasoning_keys - required_reasoning)
        if unexpected_reasoning:
            errors.append(f"processing_behavior.call_3_reasoning unexpected keys: {unexpected_reasoning}")
        if call_3_reasoning.get("call_sequence") != REQ_028_CALL_SEQUENCE:
            errors.append(f"processing_behavior.call_3_reasoning.call_sequence must be {REQ_028_CALL_SEQUENCE}")
        if call_3_reasoning.get("reasoning_focus") != REQ_028_REASONING_FOCUS:
            errors.append(f"processing_behavior.call_3_reasoning.reasoning_focus must be {REQ_028_REASONING_FOCUS}")

    recommendation = processing_behavior.get("recommendation")
    if not isinstance(recommendation, Mapping):
        errors.append("processing_behavior.recommendation must be an object")
    else:
        required_recommendation = {
            "decision",
            "rationale",
            "confidence",
            "evidence_refs",
            "recommended_opportunities",
            "cross_project_obligations",
            "open_risks",
        }
        recommendation_keys = set(recommendation.keys())
        missing_recommendation = sorted(required_recommendation - recommendation_keys)
        if missing_recommendation:
            errors.append(f"processing_behavior.recommendation missing keys: {missing_recommendation}")
        if not isinstance(recommendation.get("evidence_refs"), list):
            errors.append("processing_behavior.recommendation.evidence_refs must be a list")
        if not isinstance(recommendation.get("recommended_opportunities"), list):
            errors.append("processing_behavior.recommendation.recommended_opportunities must be a list")
        obligations = recommendation.get("cross_project_obligations")
        if not isinstance(obligations, list):
            errors.append("processing_behavior.recommendation.cross_project_obligations must be a list")
            obligations = []
        earth_ref_set = {ref for ref in normalized_earth_sweep_refs if _is_earth_evidence_ref(ref)}
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
        if not isinstance(recommendation.get("open_risks"), list):
            errors.append("processing_behavior.recommendation.open_risks must be a list")

    if (
        normalized_local_mission_summary
        and normalized_gap_candidates
        and normalized_opportunity_candidates
        and normalized_earth_sweep_refs
    ):
        try:
            expected_processing_behavior = _build_req_028_processing_behavior(
                target_project_root=_as_text(entrypoint.get("target_project_root")),
                earth_root=_as_text(entrypoint.get("earth_root")),
                target_project_evidence_refs=normalized_target_project_refs,
                earth_sweep_evidence_refs=normalized_earth_sweep_refs,
                local_mission_summary=normalized_local_mission_summary,
                cross_project_context=normalized_cross_project_context,
                unresolved_ideas=normalized_unresolved_ideas,
                gap_candidates=normalized_gap_candidates,
                opportunity_candidates=normalized_opportunity_candidates,
                strategic_claims=normalized_strategic_claims,
            )
        except ValueError as exc:
            errors.append(f"processing_behavior could not be reconstructed: {exc}")
        else:
            if dict(processing_behavior) != expected_processing_behavior:
                errors.append("processing_behavior must match deterministic Call-3 reasoning output")

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
    expected_canonical_input = _canonical_req_028_input(
        target_project_root=_as_text(entrypoint.get("target_project_root")),
        earth_root=_as_text(entrypoint.get("earth_root")),
        output_root=_as_text(entrypoint.get("output_root")),
        revision_identity=_as_text(entrypoint.get("revision_identity")),
        strategy_goal=_as_text(entrypoint.get("strategy_goal")),
        call_sequence=int(call_sequence),
    )
    if dict(canonical_input) != expected_canonical_input:
        errors.append("call_metadata.canonical_input must mirror normalized invocation anchors")
    expected_input_sha = _canonical_digest(expected_canonical_input)
    if metadata.get("canonical_input_sha256") != expected_input_sha:
        errors.append("call_metadata.canonical_input_sha256 does not match canonical input")
    if metadata.get("reproducible_call_id") != f"req028-{expected_input_sha[:16]}":
        errors.append("call_metadata.reproducible_call_id does not match canonical digest")

    canonical_processing_input = metadata.get("canonical_processing_input")
    if not isinstance(canonical_processing_input, Mapping):
        errors.append("call_metadata.canonical_processing_input must be an object")
        return errors

    if metadata.get("llm_call_trace_schema_version") != REQ_025_LLM_CALL_TRACE_SCHEMA_VERSION:
        errors.append(
            f"call_metadata.llm_call_trace_schema_version must be {REQ_025_LLM_CALL_TRACE_SCHEMA_VERSION}"
        )
    if metadata.get("llm_call_trace_path") != LLM_CALL_TRACE_RELATIVE_PATH:
        errors.append(f"call_metadata.llm_call_trace_path must be {LLM_CALL_TRACE_RELATIVE_PATH}")

    if (
        normalized_local_mission_summary
        and normalized_gap_candidates
        and normalized_opportunity_candidates
        and normalized_earth_sweep_refs
    ):
        expected_processing_input = _canonical_req_028_processing_input(
            evidence_refs=sorted(
                set(
                    _collect_unique_refs(
                        normalized_target_project_refs,
                        normalized_earth_sweep_refs,
                        *[row["evidence_refs"] for row in normalized_cross_project_context],
                        *[row["evidence_refs"] for row in normalized_unresolved_ideas],
                        *[row["evidence_refs"] for row in normalized_gap_candidates],
                        *[row["evidence_refs"] for row in normalized_opportunity_candidates],
                    )
                )
            ),
            target_project_evidence_refs=normalized_target_project_refs,
            earth_sweep_evidence_refs=normalized_earth_sweep_refs,
            local_mission_summary=normalized_local_mission_summary,
            cross_project_context=normalized_cross_project_context,
            unresolved_ideas=normalized_unresolved_ideas,
            gap_candidates=normalized_gap_candidates,
            opportunity_candidates=normalized_opportunity_candidates,
            strategic_claims=normalized_strategic_claims,
        )
        if dict(canonical_processing_input) != expected_processing_input:
            errors.append("call_metadata.canonical_processing_input must mirror processing inputs")
        expected_processing_sha = _canonical_digest(expected_processing_input)
        if metadata.get("processing_input_sha256") != expected_processing_sha:
            errors.append("call_metadata.processing_input_sha256 does not match processing input")
        if metadata.get("processing_call_id") != f"req028-processing-{expected_processing_sha[:16]}":
            errors.append("call_metadata.processing_call_id does not match processing digest")

        expected_trace_rows = _build_req_028_llm_call_trace_rows(
            canonical_input_sha=expected_input_sha,
            processing_input_sha=expected_processing_sha,
            processing_call_id=f"req028-processing-{expected_processing_sha[:16]}",
            canonical_processing_input=expected_processing_input,
            gap_count=len(normalized_gap_candidates),
            opportunity_count=len(normalized_opportunity_candidates),
        )
        if metadata.get("llm_call_trace_rows") != expected_trace_rows:
            errors.append("call_metadata.llm_call_trace_rows must mirror deterministic Call-3 trace rows")
        if metadata.get("llm_call_trace_sha256") != _canonical_digest(expected_trace_rows):
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


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Emit REQ-025 multi-call strategy pipeline planner payload.")
    parser.add_argument("--input-json", required=True, help="Input JSON path or '-' for stdin.")
    parser.add_argument("--output-json", default="", help="Optional output JSON path.")
    parser.add_argument("--json-pretty", action="store_true", help="Pretty-print JSON output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    _enforce_log_budget(LOG_ROOT)
    _timestamped_print(f"Starting REQ-025 pipeline planning build from input source: {args.input_json}")

    try:
        input_payload = _parse_cli_input(args.input_json)
        output_payload = build_req_025_multi_call_strategy_pipeline_planner(
            target_project_root=input_payload.get("target_project_root"),
            earth_root=input_payload.get("earth_root"),
            output_root=input_payload.get("output_root"),
            revision_identity=input_payload.get("revision_identity"),
            strategy_goal=input_payload.get("strategy_goal"),
            call_depth=input_payload.get("call_depth", DEFAULT_CALL_DEPTH),
            evidence_refs=input_payload.get("evidence_refs"),
            stage_blueprints=input_payload.get("stage_blueprints"),
            target_project_evidence_refs=input_payload.get("target_project_evidence_refs"),
            earth_sweep_evidence_refs=input_payload.get("earth_sweep_evidence_refs"),
            cross_project_context=input_payload.get("cross_project_context"),
            candidate_recommendations=input_payload.get("candidate_recommendations"),
            strategic_claims=input_payload.get("strategic_claims"),
        )
    except (ValueError, json.JSONDecodeError) as exc:
        _timestamped_print(f"REQ-025 pipeline planning failed during input processing: {exc}")
        error_payload = {
            "ok": False,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "requirement_id": REQ_025_REQUIREMENT_ID,
            "reason_code": "input_error",
            "message": str(exc),
            "timestamp_utc": utc_now_iso(),
        }
        serialized_error = _json_dumps(error_payload, pretty=True)
        if args.output_json:
            Path(args.output_json).write_text(serialized_error, encoding="utf-8")
        print(serialized_error, end="")
        return 2

    validation_errors = validate_req_025_multi_call_strategy_pipeline_planner(output_payload)
    if validation_errors:
        _timestamped_print("REQ-025 pipeline planning produced invalid deterministic payload.")
        error_payload = {
            "ok": False,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "requirement_id": REQ_025_REQUIREMENT_ID,
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
    _timestamped_print(f"Wrote REQ-025 call trace to {trace_output_path}")
    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialized_output, encoding="utf-8")
        _timestamped_print(f"Wrote REQ-025 pipeline payload to {output_path}")
    else:
        _timestamped_print("REQ-025 pipeline payload generated successfully and emitted to stdout.")
    print(serialized_output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
