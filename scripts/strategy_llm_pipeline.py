#!/usr/bin/env python3
"""Contract/data-model surfaces for strategy LLM pipeline flows."""

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

try:
    from scripts import strategy_llm_pipeline_req027_035 as _req27_35
    from scripts import strategy_llm_pipeline_req036 as _req36
    from scripts import strategy_llm_pipeline_req038_041 as _req38_41
    from scripts import strategy_llm_pipeline_req039_047 as _req39_47
    from scripts import strategy_llm_pipeline_req040 as _req40
    from scripts import strategy_llm_pipeline_req042 as _req42
    from scripts import strategy_llm_pipeline_req043 as _req43
    from scripts import strategy_llm_pipeline_req044 as _req44
    from scripts import strategy_llm_pipeline_req045 as _req45
except ModuleNotFoundError:
    _repo_root = Path(__file__).resolve().parents[1]
    if str(_repo_root) not in sys.path:
        sys.path.insert(0, str(_repo_root))
    from scripts import strategy_llm_pipeline_req027_035 as _req27_35
    from scripts import strategy_llm_pipeline_req036 as _req36
    from scripts import strategy_llm_pipeline_req038_041 as _req38_41
    from scripts import strategy_llm_pipeline_req039_047 as _req39_47
    from scripts import strategy_llm_pipeline_req040 as _req40
    from scripts import strategy_llm_pipeline_req042 as _req42
    from scripts import strategy_llm_pipeline_req043 as _req43
    from scripts import strategy_llm_pipeline_req044 as _req44
    from scripts import strategy_llm_pipeline_req045 as _req45

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
REQ_026_REQUIREMENT_ID = "REQ-026"
REQ_026_SCHEMA_VERSION = "req-026.call-1-situational-analysis-reasoning.v1"
REQ_026_LLM_CALL_TRACE_SCHEMA_VERSION = "req-026.llm-call-trace-row.v1"
REQ_026_ANALYSIS_TYPE = "call_1_situational_analysis_reasoning"
REQ_029_REQUIREMENT_ID = "REQ-029"
REQ_029_SCHEMA_VERSION = "req-029.call-4-recommendation-synthesis.v1"
REQ_029_LLM_CALL_TRACE_SCHEMA_VERSION = "req-029.llm-call-trace-row.v1"
REQ_029_ANALYSIS_TYPE = "call_4_recommendation_synthesis"
REQ_030_REQUIREMENT_ID = "REQ-030"
REQ_030_SCHEMA_VERSION = "req-030.call-5-sequencing-and-lane-design-reasoning.v1"
REQ_030_LLM_CALL_TRACE_SCHEMA_VERSION = "req-030.llm-call-trace-row.v1"
REQ_030_ANALYSIS_TYPE = "call_5_sequencing_and_lane_design_reasoning"
REQ_031_REQUIREMENT_ID = "REQ-031"
REQ_031_SCHEMA_VERSION = "req-031.call-6-kpi-impact-estimation-reasoning.v1"
REQ_031_LLM_CALL_TRACE_SCHEMA_VERSION = "req-031.llm-call-trace-row.v1"
REQ_031_ANALYSIS_TYPE = "call_6_kpi_impact_estimation_reasoning"
REQ_034_REQUIREMENT_ID = "REQ-034"
REQ_034_SCHEMA_VERSION = "req-034.cross-call-memory-handoff-contract.v1"
REQ_034_LLM_CALL_TRACE_SCHEMA_VERSION = "req-034.llm-call-trace-row.v1"
REQ_034_ANALYSIS_TYPE = "cross_call_memory_handoff_contract"
REQ_046_REQUIREMENT_ID = "REQ-046"
REQ_046_SCHEMA_VERSION = "req-046.final-strategy-synthesis-composer.v1"
REQ_046_ANALYSIS_TYPE = "final_strategy_synthesis_composer"
REQ_046_CALL_ID = "final-strategy-synthesis"
REQ_027_SCHEMA_VERSION = _req27_35.REQ_027_SCHEMA_VERSION
REQ_027_PROCESSING_SCHEMA_VERSION = _req27_35.REQ_027_PROCESSING_SCHEMA_VERSION
REQ_027_REQUIREMENT_ID = _req27_35.REQ_027_REQUIREMENT_ID
REQ_027_ANALYSIS_TYPE = _req27_35.REQ_027_ANALYSIS_TYPE
REQ_027_CALL_ID = _req27_35.REQ_027_CALL_ID
REQ_035_SCHEMA_VERSION = _req27_35.REQ_035_SCHEMA_VERSION
REQ_035_PROCESSING_SCHEMA_VERSION = _req27_35.REQ_035_PROCESSING_SCHEMA_VERSION
REQ_035_REQUIREMENT_ID = _req27_35.REQ_035_REQUIREMENT_ID
REQ_035_ANALYSIS_TYPE = _req27_35.REQ_035_ANALYSIS_TYPE
REQ_035_CALL_ID = _req27_35.REQ_035_CALL_ID
REQ_036_REQUIREMENT_ID = _req36.REQ_036_REQUIREMENT_ID
REQ_036_SCHEMA_VERSION = _req36.REQ_036_SCHEMA_VERSION
REQ_036_DETECTION_STRATEGY = _req36.REQ_036_DETECTION_STRATEGY
REQ_036_REASON_CODE = _req36.REQ_036_REASON_CODE
REQ_036_HANDLING_POLICY = _req36.REQ_036_HANDLING_POLICY
REQ_036_LLM_CALL_TRACE_SCHEMA_VERSION = _req36.REQ_036_LLM_CALL_TRACE_SCHEMA_VERSION
REQ_036_LLM_CALL_TRACE_ROW_SCHEMA_VERSION = _req36.REQ_036_LLM_CALL_TRACE_ROW_SCHEMA_VERSION
REQ_036_DEFAULT_LLM_CALL_TRACE_PATH = _req36.REQ_036_DEFAULT_LLM_CALL_TRACE_PATH
REQ_038_REQUIREMENT_ID = _req38_41.REQ_038_REQUIREMENT_ID
REQ_038_SCHEMA_VERSION = _req38_41.REQ_038_SCHEMA_VERSION
REQ_038_SURFACE = _req38_41.REQ_038_SURFACE
REASON_CODE_CROSS_CALL_ANALYSIS_SYNTHESIS_CONTRADICTION = (
    _req38_41.REASON_CODE_CROSS_CALL_ANALYSIS_SYNTHESIS_CONTRADICTION
)
REASON_CODE_CITATION_DISCIPLINE_UNCITED_STRATEGIC_CLAIM = (
    _req38_41.REASON_CODE_CITATION_DISCIPLINE_UNCITED_STRATEGIC_CLAIM
)
REQ_039_REQUIREMENT_ID = _req39_47.REQ_039_REQUIREMENT_ID
REQ_039_SCHEMA_VERSION = _req39_47.REQ_039_SCHEMA_VERSION
REQ_039_PROCESSING_SCHEMA_VERSION = _req39_47.REQ_039_PROCESSING_SCHEMA_VERSION
REQ_039_ANALYSIS_TYPE = _req39_47.REQ_039_ANALYSIS_TYPE
REQ_039_CALL_ID = _req39_47.REQ_039_CALL_ID
REQ_040_REQUIREMENT_ID = _req40.REQ_040_REQUIREMENT_ID
REQ_040_SCHEMA_VERSION = _req40.REQ_040_SCHEMA_VERSION
REQ_041_REQUIREMENT_ID = _req38_41.REQ_041_REQUIREMENT_ID
REQ_041_SCHEMA_VERSION = _req38_41.REQ_041_SCHEMA_VERSION
REQ_041_SURFACE = _req38_41.REQ_041_SURFACE
REQ_042_REQUIREMENT_ID = _req42.REQ_042_REQUIREMENT_ID
REQ_042_SCHEMA_VERSION = _req42.REQ_042_SCHEMA_VERSION
REQ_042_STRATEGY = _req42.REQ_042_STRATEGY
REQ_043_REQUIREMENT_ID = _req43.REQ_043_REQUIREMENT_ID
REQ_043_SCHEMA_VERSION = _req43.REQ_043_SCHEMA_VERSION
REQ_043_ANALYSIS_TYPE = _req43.REQ_043_ANALYSIS_TYPE
REQ_043_PROCESSING_STRATEGY = _req43.REQ_043_PROCESSING_STRATEGY
REQ_043_REASONING_MODE = _req43.REQ_043_REASONING_MODE
REQ_044_REQUIREMENT_ID = _req44.REQ_044_REQUIREMENT_ID
REQ_044_SCHEMA_VERSION = _req44.REQ_044_SCHEMA_VERSION
REQ_044_ANALYSIS_TYPE = _req44.REQ_044_ANALYSIS_TYPE
REQ_044_PROCESSING_STRATEGY = _req44.REQ_044_PROCESSING_STRATEGY
REQ_044_REASONING_MODE = _req44.REQ_044_REASONING_MODE
REQ_045_REQUIREMENT_ID = _req45.REQ_045_REQUIREMENT_ID
REQ_045_SCHEMA_VERSION = _req45.REQ_045_SCHEMA_VERSION
REQ_045_ANALYSIS_TYPE = _req45.REQ_045_ANALYSIS_TYPE
REQ_045_PROCESSING_STRATEGY = _req45.REQ_045_PROCESSING_STRATEGY
REQ_045_REASONING_MODE = _req45.REQ_045_REASONING_MODE
REQ_045_CALL_TRACE_SCHEMA_VERSION = _req45.REQ_045_CALL_TRACE_SCHEMA_VERSION
REQ_045_REASON_CODE_ANALYSIS_SYNTHESIS_CONTRADICTION = (
    _req45.REQ_045_REASON_CODE_ANALYSIS_SYNTHESIS_CONTRADICTION
)
REQ_045_REASON_CODE_UNCITED_STRATEGIC_CLAIM_BLOCKED = (
    _req45.REQ_045_REASON_CODE_UNCITED_STRATEGIC_CLAIM_BLOCKED
)
REQ_047_REQUIREMENT_ID = _req39_47.REQ_047_REQUIREMENT_ID
REQ_047_SCHEMA_VERSION = _req39_47.REQ_047_SCHEMA_VERSION
REQ_047_PROCESSING_SCHEMA_VERSION = _req39_47.REQ_047_PROCESSING_SCHEMA_VERSION
REQ_047_ANALYSIS_TYPE = _req39_47.REQ_047_ANALYSIS_TYPE
REQ_047_CALL_ID = _req39_47.REQ_047_CALL_ID
REQ_026_PROCESSING_STRATEGY = "call-1-situational-analysis"
REQ_026_REASONING_MODE = "deterministic-broad-sweep"
REQ_029_PROCESSING_STRATEGY = "call-4-recommendation-synthesis"
REQ_029_REASONING_MODE = "deterministic-replay-synthesis"
REQ_030_PROCESSING_STRATEGY = "call-5-sequencing-and-lane-design-reasoning"
REQ_030_REASONING_MODE = "deterministic-lane-replay-planning"
REQ_031_PROCESSING_STRATEGY = "call-6-kpi-impact-estimation-reasoning"
REQ_031_REASONING_MODE = "deterministic-kpi-impact-replay-estimation"
REQ_034_PROCESSING_STRATEGY = "cross-call-memory-handoff"
REQ_034_REASONING_MODE = "deterministic-bounded-memory-handoff"
REQ_034_ALLOWED_ENTRY_KINDS = {"constraint", "decision", "fact", "risk"}
REQ_034_REQUIRED_HANDOFF_FIELDS = [
    "memory_id",
    "memory_key",
    "kind",
    "summary",
    "position",
    "source_call_id",
    "source_output_ref",
    "carry_forward",
    "supersedes_memory_ids",
    "citation_refs",
]
REQ_034_DEFAULT_MAX_ENTRIES = 8
REQ_034_DEFAULT_MAX_CITATION_REFS_PER_ENTRY = 3
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
REQ_033_TRACE_BUCKET_OUTPUTS = (
    "call_8_hard_constraints",
    "call_8_soft_preferences",
    "call_8_speculative_ideas",
    "call_8_planner_contract",
)
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
REQ_026_ALLOWED_PLANNING_STATUSES = {"ready", "partial", "blocked"}
REQ_026_ALLOWED_RUNTIME_STATUSES = {"healthy", "degraded", "blocked"}
REQ_026_ALLOWED_RECOMMENDATION_SCOPES = {"local", "cross-project"}
REQ_046_PACKET_KINDS = ("target-project", "cross-project")
REQ_046_PRIORITY_LEVELS = ("high", "medium", "low")
REQ_046_ROUTING_CONFLICT_REASON = "conflicting_packet_routing"
REQ_046_OPEN_RISK_REASON_MISSING_EARTH_SWEEP_EVIDENCE = "missing_earth_sweep_evidence_refs"
REQ_046_OPEN_RISK_REASON_UNRESOLVED_IDEA = "unresolved_idea_open_risk"
REQ_046_OPEN_RISK_REASON_UNCITED_STRATEGIC_CLAIM_BLOCKED = "uncited_strategic_claim_blocked"
REQ_046_EARTH_SWEEP_REF_PREFIXES = ("earth-sweep/", "reports/earth/sweeps/")
REQ_029_ALLOWED_RECOMMENDATION_SCOPES = {"local", "cross-project"}
REQ_029_RECOMMENDATION_ID_RE = re.compile(r"^rec\.[a-z0-9]+(?:-[a-z0-9]+)*$")
REQ_030_ALLOWED_LANE_SCOPES = {"local", "cross-project"}
REQ_030_RECOMMENDATION_ID_RE = re.compile(r"^rec\.[a-z0-9]+(?:-[a-z0-9]+)*$")
REQ_030_LANE_ID_RE = re.compile(r"^lane\.[a-z0-9]+(?:-[a-z0-9]+)*$")
REQ_034_MEMORY_ID_RE = re.compile(r"^memory\.[a-z0-9]+(?:-[a-z0-9]+)*$")
REQ_034_ALLOWED_MEMORY_SCOPES = {"local", "cross-project"}
REQ_034_MAX_MEMORY_ITEMS_PER_CALL = 3
REQ_031_ALLOWED_ADOPTION_STATUSES = {"planned", "conditional", "pilot"}
REQ_031_ALLOWED_CONFIDENCE = {"high", "medium", "low"}
REQ_031_ALLOWED_DIRECTIONS = {"increase", "decrease"}
REQ_031_KPI_ID_RE = re.compile(r"^kpi\.[a-z0-9]+(?:-[a-z0-9]+)*$")
REQ_031_ESTIMATE_ID_RE = re.compile(r"^estimate::rec\.[a-z0-9]+(?:-[a-z0-9]+)*::kpi\.[a-z0-9]+(?:-[a-z0-9]+)*$")
REQ_031_CALL_OBJECTIVES = {
    "call-1": "Assess target-project state and evidence anchors required for later strategy reasoning.",
    "call-2": "Refine implementation constraints into deterministic execution-planning inputs.",
    "call-3": "Validate dependency and evidence readiness before recommendation promotion.",
    "call-4": "Synthesize evidence-backed recommendation drafts from earlier call outputs.",
    "call-5": "Sequence recommendation adoption lanes for replay-stable branch-head execution.",
    "call-6": "Estimate KPI impact from lane adoption using evidence-backed assumptions and explicit caveats.",
}

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

process_req_027_call_2_ecosystem_linkage_reasoning = _req27_35.process_req_027_call_2_ecosystem_linkage_reasoning
build_req_027_call_2_ecosystem_linkage_reasoning = _req27_35.build_req_027_call_2_ecosystem_linkage_reasoning
validate_req_027_call_2_ecosystem_linkage_reasoning = _req27_35.validate_req_027_call_2_ecosystem_linkage_reasoning
process_req_035_evidence_citation_discipline_in_reasoning_calls = (
    _req27_35.process_req_035_evidence_citation_discipline_in_reasoning_calls
)
build_req_035_evidence_citation_discipline_in_reasoning_calls = (
    _req27_35.build_req_035_evidence_citation_discipline_in_reasoning_calls
)
validate_req_035_evidence_citation_discipline_in_reasoning_calls = (
    _req27_35.validate_req_035_evidence_citation_discipline_in_reasoning_calls
)
build_req_036_cross_call_contradiction_detection = _req36.build_req_036_cross_call_contradiction_detection
validate_req_036_cross_call_contradiction_detection = _req36.validate_req_036_cross_call_contradiction_detection
build_req_038_recommendation_priority_calibration = _req38_41.build_req_038_recommendation_priority_calibration
validate_req_038_recommendation_priority_calibration = (
    _req38_41.validate_req_038_recommendation_priority_calibration
)
build_req_039_recommendation_rationale_quality_scoring = (
    _req39_47.build_req_039_recommendation_rationale_quality_scoring
)
process_req_039_recommendation_rationale_quality_scoring = (
    _req39_47.process_req_039_recommendation_rationale_quality_scoring
)
validate_req_039_recommendation_rationale_quality_scoring = (
    _req39_47.validate_req_039_recommendation_rationale_quality_scoring
)
build_req_040_recommendation_feasibility_scoring = _req40.build_req_040_recommendation_feasibility_scoring
validate_req_040_recommendation_feasibility_scoring = (
    _req40.validate_req_040_recommendation_feasibility_scoring
)
build_req_041_recommendation_dependency_effect_modeling = (
    _req38_41.build_req_041_recommendation_dependency_effect_modeling
)
validate_req_041_recommendation_dependency_effect_modeling = (
    _req38_41.validate_req_041_recommendation_dependency_effect_modeling
)
build_req_042_existing_functionality_interaction_reasoning = (
    _req42.build_req_042_existing_functionality_interaction_reasoning
)
validate_req_042_existing_functionality_interaction_reasoning = (
    _req42.validate_req_042_existing_functionality_interaction_reasoning
)
build_req_043_project_obligation_reasoning = _req43.build_req_043_project_obligation_reasoning
validate_req_043_project_obligation_reasoning = _req43.validate_req_043_project_obligation_reasoning
build_req_044_recommendation_omission_detector = _req44.build_req_044_recommendation_omission_detector
validate_req_044_recommendation_omission_detector = _req44.validate_req_044_recommendation_omission_detector
build_req_045_alternative_strategic_scenario_generator = (
    _req45.build_req_045_alternative_strategic_scenario_generator
)
build_req_045_llm_call_trace_rows = _req45.build_req_045_llm_call_trace_rows
validate_req_045_alternative_strategic_scenario_generator = (
    _req45.validate_req_045_alternative_strategic_scenario_generator
)
build_req_047_llm_call_trace_and_decision_ledger = _req39_47.build_req_047_llm_call_trace_and_decision_ledger
process_req_047_llm_call_trace_and_decision_ledger = _req39_47.process_req_047_llm_call_trace_and_decision_ledger
validate_req_047_llm_call_trace_and_decision_ledger = (
    _req39_47.validate_req_047_llm_call_trace_and_decision_ledger
)


def process_req_035_evidence_citation_discipline_in_reasoning_calls(
    payload: Mapping[str, Any],
    *,
    emit: Any | None = None,
    trace_path: str | Path | None = None,
    trace_artifacts_dir: str | Path | None = None,
) -> dict[str, Any]:
    artifacts_root = (
        Path(trace_artifacts_dir)
        if trace_artifacts_dir is not None
        else REPO_ROOT / "strategy/current/llm_call_trace_artifacts"
    )
    artifacts_root.mkdir(parents=True, exist_ok=True)
    return _req27_35.process_req_035_evidence_citation_discipline_in_reasoning_calls(
        payload,
        emit=emit,
        trace_path=trace_path,
        trace_artifacts_dir=artifacts_root,
    )


class Req026Error(ValueError):
    """Raised when REQ-026 input is malformed."""


class Req029Error(ValueError):
    """Raised when REQ-029 input is malformed."""


class Req030Error(ValueError):
    """Raised when REQ-030 input is malformed."""


class Req031Error(ValueError):
    """Raised when REQ-031 input is malformed."""


class Req034Error(ValueError):
    """Raised when REQ-034 input is malformed."""


Req043Error = _req43.Req043Error
Req045Error = _req45.Req045Error
Req044Error = _req44.Req044Error
Req045Error = _req45.Req045Error


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


def _dedupe_preserving_order(values: Sequence[Any]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = _as_text(raw_value)
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


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
    normalized.sort(key=lambda row: (row["project_id"], row["project_root"]))
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


def _req_046_stable_id_fragment(*parts: str) -> str:
    material = "|".join(parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]


_stable_id_fragment = _req_046_stable_id_fragment


def _req_046_priority_rank(priority: str) -> int:
    return {level: index for index, level in enumerate(REQ_046_PRIORITY_LEVELS)}[priority]


def _req_046_is_earth_sweep_ref(value: str) -> bool:
    ref = _as_text(value).lower()
    return any(ref.startswith(prefix) for prefix in REQ_046_EARTH_SWEEP_REF_PREFIXES)


def _req_046_require_positive_int(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _req_046_normalize_target_project(raw_value: Any) -> dict[str, str]:
    target_project = _require_mapping(raw_value, field_name="target_project")
    expected_keys = {"project_id", "project_root"}
    unexpected = sorted(set(target_project.keys()) - expected_keys)
    if unexpected:
        raise ValueError(f"target_project has unexpected keys: {unexpected}")
    return {
        "project_id": _require_text(target_project.get("project_id"), field_name="target_project.project_id"),
        "project_root": _normalize_root(target_project.get("project_root"), field_name="target_project.project_root"),
    }


def _req_046_normalize_call_trace(raw_value: Any, *, field_name: str) -> dict[str, str]:
    call_trace = _require_mapping(raw_value, field_name=field_name)
    expected_keys = {"trace_id", "trace_ref", "artifact_ref", "checked_at_utc"}
    unexpected = sorted(set(call_trace.keys()) - expected_keys)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {unexpected}")
    return {
        "trace_id": _require_text(call_trace.get("trace_id"), field_name=f"{field_name}.trace_id"),
        "trace_ref": _require_text(call_trace.get("trace_ref"), field_name=f"{field_name}.trace_ref"),
        "artifact_ref": _require_text(call_trace.get("artifact_ref"), field_name=f"{field_name}.artifact_ref"),
        "checked_at_utc": _require_text(call_trace.get("checked_at_utc"), field_name=f"{field_name}.checked_at_utc"),
    }


def _req_046_normalize_input_recommendation(raw_value: Any, *, field_name: str) -> dict[str, Any]:
    recommendation = _require_mapping(raw_value, field_name=field_name)
    expected_keys = {
        "recommendation_id",
        "summary",
        "rationale",
        "packet_kind",
        "peer_project_id",
        "lane",
        "sequence_hint",
        "priority",
        "evidence_refs",
    }
    unexpected = sorted(set(recommendation.keys()) - expected_keys)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {unexpected}")

    packet_kind = _require_text(recommendation.get("packet_kind"), field_name=f"{field_name}.packet_kind").lower()
    if packet_kind not in REQ_046_PACKET_KINDS:
        raise ValueError(f"{field_name}.packet_kind must be one of: {list(REQ_046_PACKET_KINDS)}")

    peer_project_id = ""
    if recommendation.get("peer_project_id") is not None:
        peer_project_id = _require_text(
            recommendation.get("peer_project_id"),
            field_name=f"{field_name}.peer_project_id",
        )
    if packet_kind == "cross-project" and not peer_project_id:
        raise ValueError(f"{field_name}.peer_project_id must be set when packet_kind is cross-project")
    if packet_kind == "target-project" and peer_project_id:
        raise ValueError(f"{field_name}.peer_project_id must be empty when packet_kind is target-project")

    priority = _require_text(
        recommendation.get("priority") if recommendation.get("priority") is not None else "medium",
        field_name=f"{field_name}.priority",
    ).lower()
    if priority not in REQ_046_PRIORITY_LEVELS:
        raise ValueError(f"{field_name}.priority must be one of: {list(REQ_046_PRIORITY_LEVELS)}")

    return {
        "recommendation_id": _require_text(
            recommendation.get("recommendation_id"),
            field_name=f"{field_name}.recommendation_id",
        ),
        "summary": _require_text(recommendation.get("summary"), field_name=f"{field_name}.summary"),
        "rationale": _require_text(recommendation.get("rationale"), field_name=f"{field_name}.rationale"),
        "packet_kind": packet_kind,
        "peer_project_id": peer_project_id,
        "lane": _require_text(recommendation.get("lane"), field_name=f"{field_name}.lane"),
        "sequence_hint": _req_046_require_positive_int(
            recommendation.get("sequence_hint"),
            field_name=f"{field_name}.sequence_hint",
        ),
        "priority": priority,
        "evidence_refs": _normalize_string_list(
            recommendation.get("evidence_refs"),
            field_name=f"{field_name}.evidence_refs",
        ),
    }


def _req_046_normalize_validated_call_outputs(raw_value: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_value, list) or not raw_value:
        raise ValueError("validated_call_outputs must be a non-empty list")

    normalized_calls: list[dict[str, Any]] = []
    seen_trace_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        field_name = f"validated_call_outputs[{index}]"
        call_output = _require_mapping(item, field_name=field_name)
        expected_keys = {"requirement_id", "call_id", "call_status", "call_trace", "recommendations"}
        unexpected = sorted(set(call_output.keys()) - expected_keys)
        if unexpected:
            raise ValueError(f"{field_name} has unexpected keys: {unexpected}")

        call_status = _require_text(
            call_output.get("call_status") if call_output.get("call_status") is not None else "validated",
            field_name=f"{field_name}.call_status",
        ).lower()
        if call_status != "validated":
            raise ValueError(f"{field_name}.call_status must be validated")

        call_trace = _req_046_normalize_call_trace(call_output.get("call_trace"), field_name=f"{field_name}.call_trace")
        if call_trace["trace_id"] in seen_trace_ids:
            raise ValueError(f"{field_name}.call_trace.trace_id duplicates {call_trace['trace_id']}")
        seen_trace_ids.add(call_trace["trace_id"])

        raw_recommendations = call_output.get("recommendations")
        if not isinstance(raw_recommendations, list) or not raw_recommendations:
            raise ValueError(f"{field_name}.recommendations must be a non-empty list")
        recommendations: list[dict[str, Any]] = []
        seen_recommendation_ids: set[str] = set()
        for recommendation_index, recommendation in enumerate(raw_recommendations):
            normalized = _req_046_normalize_input_recommendation(
                recommendation,
                field_name=f"{field_name}.recommendations[{recommendation_index}]",
            )
            recommendation_id = normalized["recommendation_id"]
            if recommendation_id in seen_recommendation_ids:
                raise ValueError(
                    f"{field_name}.recommendations[{recommendation_index}].recommendation_id duplicates {recommendation_id}"
                )
            seen_recommendation_ids.add(recommendation_id)
            recommendations.append(normalized)

        recommendations.sort(
            key=lambda row: (
                row["sequence_hint"],
                _req_046_priority_rank(row["priority"]),
                row["recommendation_id"],
            )
        )
        normalized_calls.append(
            {
                "requirement_id": _require_text(
                    call_output.get("requirement_id"),
                    field_name=f"{field_name}.requirement_id",
                ),
                "call_id": _require_text(call_output.get("call_id"), field_name=f"{field_name}.call_id"),
                "call_status": call_status,
                "call_trace": call_trace,
                "recommendations": recommendations,
            }
        )

    normalized_calls.sort(
        key=lambda row: (
            row["call_id"],
            row["requirement_id"],
            row["call_trace"]["trace_id"],
        )
    )
    return normalized_calls


def _req_046_normalize_broad_sweep_context(raw_value: Any) -> dict[str, Any]:
    if raw_value is None:
        return {
            "earth_sweep_evidence_refs": [],
            "projects_considered": [],
            "cross_project_obligations": [],
            "unresolved_ideas": [],
        }

    broad_sweep_context = _require_mapping(raw_value, field_name="broad_sweep_context")
    earth_sweep_evidence_refs = _normalize_string_list(
        broad_sweep_context.get("earth_sweep_evidence_refs"),
        field_name="broad_sweep_context.earth_sweep_evidence_refs",
    )
    projects_considered = set(
        _normalize_string_list(
            broad_sweep_context.get("projects_considered"),
            field_name="broad_sweep_context.projects_considered",
        )
    )

    cross_project_obligations_raw = broad_sweep_context.get("cross_project_obligations")
    if cross_project_obligations_raw is None:
        cross_project_obligations_raw = []
    if not isinstance(cross_project_obligations_raw, list):
        raise ValueError("broad_sweep_context.cross_project_obligations must be a list")
    cross_project_obligations: list[dict[str, Any]] = []
    for index, item in enumerate(cross_project_obligations_raw):
        field_name = f"broad_sweep_context.cross_project_obligations[{index}]"
        row = _require_mapping(item, field_name=field_name)
        target_project_id = ""
        if row.get("target_project_id") is not None:
            target_project_id = _require_text(
                row.get("target_project_id"),
                field_name=f"{field_name}.target_project_id",
            )
            projects_considered.add(target_project_id)
        recommendation_ids = _normalize_string_list(
            row.get("recommendation_ids"),
            field_name=f"{field_name}.recommendation_ids",
        )
        obligation_refs = _normalize_string_list(
            row.get("earth_sweep_evidence_refs"),
            field_name=f"{field_name}.earth_sweep_evidence_refs",
        )
        cross_project_obligations.append(
            {
                "target_project_id": target_project_id,
                "recommendation_ids": recommendation_ids,
                "earth_sweep_evidence_refs": obligation_refs,
            }
        )
    cross_project_obligations.sort(
        key=lambda row: (
            row["target_project_id"],
            ",".join(row["recommendation_ids"]),
            ",".join(row["earth_sweep_evidence_refs"]),
        )
    )

    unresolved_ideas_raw = broad_sweep_context.get("unresolved_ideas")
    if unresolved_ideas_raw is None:
        unresolved_ideas_raw = []
    if not isinstance(unresolved_ideas_raw, list):
        raise ValueError("broad_sweep_context.unresolved_ideas must be a list")
    unresolved_ideas: list[dict[str, Any]] = []
    for index, item in enumerate(unresolved_ideas_raw):
        field_name = f"broad_sweep_context.unresolved_ideas[{index}]"
        row = _require_mapping(item, field_name=field_name)
        summary = _require_text(row.get("summary"), field_name=f"{field_name}.summary")
        target_project_id = ""
        if row.get("target_project_id") is not None:
            target_project_id = _require_text(
                row.get("target_project_id"),
                field_name=f"{field_name}.target_project_id",
            )
            projects_considered.add(target_project_id)
        recommendation_ids = _normalize_string_list(
            row.get("recommendation_ids"),
            field_name=f"{field_name}.recommendation_ids",
        )
        idea_refs = _normalize_string_list(
            row.get("earth_sweep_evidence_refs"),
            field_name=f"{field_name}.earth_sweep_evidence_refs",
        )
        idea_id = _require_text(row.get("idea_id"), field_name=f"{field_name}.idea_id") if row.get("idea_id") else ""
        if not idea_id:
            idea_id = (
                "idea."
                + _req_046_stable_id_fragment(summary, target_project_id, "|".join(recommendation_ids), "|".join(idea_refs))
            )
        unresolved_ideas.append(
            {
                "idea_id": idea_id,
                "summary": summary,
                "target_project_id": target_project_id,
                "recommendation_ids": recommendation_ids,
                "earth_sweep_evidence_refs": idea_refs,
            }
        )
    unresolved_ideas.sort(key=lambda row: row["idea_id"])

    return {
        "earth_sweep_evidence_refs": earth_sweep_evidence_refs,
        "projects_considered": sorted(projects_considered),
        "cross_project_obligations": cross_project_obligations,
        "unresolved_ideas": unresolved_ideas,
    }


def _req_046_lineage_sort_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(row["call_id"]), str(row["requirement_id"]), str(row["trace_id"]))


def _req_046_contribution_sort_key(row: Mapping[str, Any]) -> tuple[int, int, str, str, str]:
    return (
        int(row["sequence_hint"]),
        _req_046_priority_rank(str(row["priority"])),
        str(row["call_id"]),
        str(row["requirement_id"]),
        str(row["call_trace"]["trace_id"]),
    )


def _req_046_build_call_trace_lineage(contributions: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = [
        {
            "call_id": str(row["call_id"]),
            "requirement_id": str(row["requirement_id"]),
            "trace_id": str(row["call_trace"]["trace_id"]),
            "trace_ref": str(row["call_trace"]["trace_ref"]),
            "artifact_ref": str(row["call_trace"]["artifact_ref"]),
            "checked_at_utc": str(row["call_trace"]["checked_at_utc"]),
        }
        for row in contributions
    ]
    rows.sort(key=_req_046_lineage_sort_key)
    return rows


def _req_046_build_final_strategy_synthesis(
    *,
    target_project: Mapping[str, str],
    validated_call_outputs: list[dict[str, Any]],
    broad_sweep_context: Mapping[str, Any],
) -> dict[str, Any]:
    context_earth_refs = list(broad_sweep_context.get("earth_sweep_evidence_refs") or [])
    context_earth_ref_set = set(context_earth_refs)
    obligation_refs_by_recommendation_id: dict[str, set[str]] = {}
    obligation_projects_by_recommendation_id: dict[str, set[str]] = {}
    for row in broad_sweep_context.get("cross_project_obligations") or []:
        if not isinstance(row, Mapping):
            continue
        recommendation_ids = [str(item) for item in row.get("recommendation_ids") or [] if str(item).strip()]
        obligation_refs = [str(item) for item in row.get("earth_sweep_evidence_refs") or [] if str(item).strip()]
        target_project_id = str(row.get("target_project_id") or "").strip()
        for recommendation_id in recommendation_ids:
            obligation_refs_by_recommendation_id.setdefault(recommendation_id, set()).update(obligation_refs)
            if target_project_id:
                obligation_projects_by_recommendation_id.setdefault(recommendation_id, set()).add(target_project_id)

    grouped: dict[str, list[dict[str, Any]]] = {}
    for call_output in validated_call_outputs:
        for recommendation in call_output["recommendations"]:
            grouped.setdefault(recommendation["recommendation_id"], []).append(
                {
                    **recommendation,
                    "call_id": call_output["call_id"],
                    "requirement_id": call_output["requirement_id"],
                    "call_trace": call_output["call_trace"],
                }
            )

    final_recommendations: list[dict[str, Any]] = []
    deferred_recommendations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []

    for recommendation_id in sorted(grouped):
        contributions = sorted(grouped[recommendation_id], key=_req_046_contribution_sort_key)
        canonical = contributions[0]
        packet_kind_candidates = sorted({str(row["packet_kind"]) for row in contributions})
        peer_project_candidates = sorted({str(row["peer_project_id"]) for row in contributions if row["peer_project_id"]})
        contribution_evidence_refs = _collect_unique_refs(*[list(row["evidence_refs"]) for row in contributions])
        evidence_refs = _collect_unique_refs(
            contribution_evidence_refs,
            sorted(obligation_refs_by_recommendation_id.get(recommendation_id, set())),
        )
        call_trace_lineage = _req_046_build_call_trace_lineage(contributions)
        contributing_call_ids = sorted({str(row["call_id"]) for row in contributions})
        contributing_requirement_ids = sorted({str(row["requirement_id"]) for row in contributions})

        packet_kind = packet_kind_candidates[0]
        routing_conflict = len(packet_kind_candidates) != 1
        if not routing_conflict and packet_kind == "cross-project" and len(peer_project_candidates) != 1:
            routing_conflict = True
        if not routing_conflict and packet_kind == "target-project" and peer_project_candidates:
            routing_conflict = True

        if not contribution_evidence_refs:
            open_risks.append(
                {
                    "open_risk_id": (
                        "open-risk."
                        + _req_046_stable_id_fragment(
                            recommendation_id,
                            REQ_046_OPEN_RISK_REASON_UNCITED_STRATEGIC_CLAIM_BLOCKED,
                        )
                    ),
                    "recommendation_id": recommendation_id,
                    "summary": canonical["summary"],
                    "reason_code": REQ_046_OPEN_RISK_REASON_UNCITED_STRATEGIC_CLAIM_BLOCKED,
                    "project_id": peer_project_candidates[0] if peer_project_candidates else "",
                    "required_evidence_refs": ["missing:citation-evidence-ref"],
                    "evidence_refs": contribution_evidence_refs,
                    "linked_recommendation_ids": [recommendation_id],
                    "call_trace_lineage": call_trace_lineage,
                    "contributing_call_ids": contributing_call_ids,
                }
            )
            continue

        if routing_conflict:
            deferred_recommendations.append(
                {
                    "recommendation_id": recommendation_id,
                    "summary": canonical["summary"],
                    "deferred_reason_code": REQ_046_ROUTING_CONFLICT_REASON,
                    "packet_kind_candidates": packet_kind_candidates,
                    "peer_project_candidates": peer_project_candidates,
                    "evidence_refs": evidence_refs,
                    "call_trace_lineage": call_trace_lineage,
                    "contributing_call_ids": contributing_call_ids,
                }
            )
            continue

        if packet_kind == "cross-project":
            has_earth_sweep_evidence = any(
                _req_046_is_earth_sweep_ref(ref) or ref in context_earth_ref_set for ref in evidence_refs
            )
            if not has_earth_sweep_evidence:
                required_evidence_refs = sorted(obligation_refs_by_recommendation_id.get(recommendation_id, set()))
                if not required_evidence_refs:
                    required_evidence_refs = list(context_earth_refs)
                if not required_evidence_refs:
                    required_evidence_refs = ["missing:earth-sweep-evidence-ref"]
                linked_project_candidates = sorted(obligation_projects_by_recommendation_id.get(recommendation_id, set()))
                open_risks.append(
                    {
                        "open_risk_id": (
                            "open-risk."
                            + _req_046_stable_id_fragment(
                                recommendation_id,
                                REQ_046_OPEN_RISK_REASON_MISSING_EARTH_SWEEP_EVIDENCE,
                            )
                        ),
                        "recommendation_id": recommendation_id,
                        "summary": canonical["summary"],
                        "reason_code": REQ_046_OPEN_RISK_REASON_MISSING_EARTH_SWEEP_EVIDENCE,
                        "project_id": (
                            peer_project_candidates[0]
                            if peer_project_candidates
                            else (linked_project_candidates[0] if linked_project_candidates else "")
                        ),
                        "required_evidence_refs": required_evidence_refs,
                        "evidence_refs": evidence_refs,
                        "linked_recommendation_ids": [recommendation_id],
                        "call_trace_lineage": call_trace_lineage,
                        "contributing_call_ids": contributing_call_ids,
                    }
                )
                continue

        final_recommendations.append(
            {
                "recommendation_id": recommendation_id,
                "summary": canonical["summary"],
                "rationale": canonical["rationale"],
                "packet_kind": packet_kind,
                "peer_project_id": peer_project_candidates[0] if peer_project_candidates else "",
                "lane": canonical["lane"],
                "sequence_hint": canonical["sequence_hint"],
                "priority": canonical["priority"],
                "evidence_refs": evidence_refs,
                "call_trace_lineage": call_trace_lineage,
                "contributing_call_ids": contributing_call_ids,
                "contributing_requirement_ids": contributing_requirement_ids,
                "supporting_call_count": len(call_trace_lineage),
                "strategy_packet_input_id": "",
            }
        )

    final_recommendations.sort(
        key=lambda row: (
            row["sequence_hint"],
            _req_046_priority_rank(str(row["priority"])),
            row["packet_kind"],
            row["peer_project_id"],
            row["recommendation_id"],
        )
    )
    deferred_recommendations.sort(key=lambda row: row["recommendation_id"])

    for idea in broad_sweep_context.get("unresolved_ideas") or []:
        if not isinstance(idea, Mapping):
            continue
        idea_id = str(idea.get("idea_id") or "").strip()
        summary = str(idea.get("summary") or "").strip()
        if not idea_id or not summary:
            continue
        required_evidence_refs = _collect_unique_refs(
            list(idea.get("earth_sweep_evidence_refs") or []),
            list(context_earth_refs),
        )
        if not required_evidence_refs:
            required_evidence_refs = ["missing:earth-sweep-evidence-ref"]
        open_risks.append(
            {
                "open_risk_id": (
                    "open-risk."
                    + _req_046_stable_id_fragment(idea_id, REQ_046_OPEN_RISK_REASON_UNRESOLVED_IDEA)
                ),
                "recommendation_id": idea_id,
                "summary": summary,
                "reason_code": REQ_046_OPEN_RISK_REASON_UNRESOLVED_IDEA,
                "project_id": str(idea.get("target_project_id") or ""),
                "required_evidence_refs": required_evidence_refs,
                "evidence_refs": list(idea.get("earth_sweep_evidence_refs") or []),
                "linked_recommendation_ids": list(idea.get("recommendation_ids") or []),
                "call_trace_lineage": [],
                "contributing_call_ids": [],
            }
        )

    open_risks.sort(
        key=lambda row: (
            row["reason_code"],
            row["project_id"],
            row["recommendation_id"],
            row["open_risk_id"],
        )
    )

    packet_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for recommendation in final_recommendations:
        group_key = (
            str(recommendation["packet_kind"]),
            str(recommendation["peer_project_id"]),
            str(recommendation["lane"]),
        )
        packet_groups.setdefault(group_key, []).append(recommendation)

    strategy_packet_inputs: list[dict[str, Any]] = []
    for packet_kind, peer_project_id, lane in sorted(packet_groups):
        recommendations = sorted(
            packet_groups[(packet_kind, peer_project_id, lane)],
            key=lambda row: (
                row["sequence_hint"],
                _req_046_priority_rank(str(row["priority"])),
                row["recommendation_id"],
            ),
        )
        packet_input_id = (
            "pkt."
            + _req_046_stable_id_fragment(packet_kind, peer_project_id or target_project["project_id"], lane)
        )
        evidence_refs = _collect_unique_refs(*[list(row["evidence_refs"]) for row in recommendations])
        strategy_packet_inputs.append(
            {
                "packet_input_id": packet_input_id,
                "packet_kind": packet_kind,
                "target_project_id": str(target_project["project_id"]),
                "peer_project_id": peer_project_id,
                "lane": lane,
                "recommendation_ids": [str(row["recommendation_id"]) for row in recommendations],
                "recommendation_count": len(recommendations),
                "earliest_sequence_hint": min(int(row["sequence_hint"]) for row in recommendations),
                "evidence_refs": evidence_refs,
            }
        )
        for recommendation in recommendations:
            recommendation["strategy_packet_input_id"] = packet_input_id

    usage_projects_considered = _collect_unique_refs(
        list(broad_sweep_context.get("projects_considered") or []),
        [str(row["peer_project_id"]) for row in final_recommendations if str(row["packet_kind"]) == "cross-project"],
        [str(row["project_id"]) for row in open_risks if str(row["project_id"]).strip()],
    )
    recommendation_ids_with_context = sorted(obligation_refs_by_recommendation_id)

    return {
        "final_recommendations": final_recommendations,
        "deferred_recommendations": deferred_recommendations,
        "open_risks": open_risks,
        "strategy_packet_inputs": strategy_packet_inputs,
        "cross_project_context_usage": {
            "cross_project_context_provided": bool(
                context_earth_refs
                or broad_sweep_context.get("projects_considered")
                or broad_sweep_context.get("cross_project_obligations")
                or broad_sweep_context.get("unresolved_ideas")
            ),
            "cross_project_context_used": bool(
                recommendation_ids_with_context
                or any(str(row["packet_kind"]) == "cross-project" for row in final_recommendations)
                or open_risks
            ),
            "projects_considered": usage_projects_considered,
            "earth_sweep_evidence_refs_considered": context_earth_refs,
            "cross_project_obligation_count": len(broad_sweep_context.get("cross_project_obligations") or []),
            "unresolved_idea_count": len(broad_sweep_context.get("unresolved_ideas") or []),
            "recommendation_ids_with_context": recommendation_ids_with_context,
        },
    }


def build_req_046_final_strategy_synthesis_composer(payload: Mapping[str, Any]) -> dict[str, Any]:
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = _as_text(raw.get("analysis_type"))
    if analysis_type and analysis_type != REQ_046_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_046_ANALYSIS_TYPE}")
    checked_at_utc = _require_text(raw.get("now_utc"), field_name="now_utc")

    target_project = _req_046_normalize_target_project(raw.get("target_project"))
    validated_call_outputs = _req_046_normalize_validated_call_outputs(raw.get("validated_call_outputs"))
    broad_sweep_context = _req_046_normalize_broad_sweep_context(raw.get("broad_sweep_context"))
    synthesis = _req_046_build_final_strategy_synthesis(
        target_project=target_project,
        validated_call_outputs=validated_call_outputs,
        broad_sweep_context=broad_sweep_context,
    )

    output_payload = {
        "ok": True,
        "schema_version": REQ_046_SCHEMA_VERSION,
        "requirement_id": REQ_046_REQUIREMENT_ID,
        "analysis_type": REQ_046_ANALYSIS_TYPE,
        "call_id": REQ_046_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "target_project": target_project,
        "final_strategy_synthesis": synthesis,
        "totals": {
            "validated_calls": len(validated_call_outputs),
            "candidate_recommendations": sum(len(row["recommendations"]) for row in validated_call_outputs),
            "final_recommendations": len(synthesis["final_recommendations"]),
            "deferred_recommendations": len(synthesis["deferred_recommendations"]),
            "open_risks": len(synthesis["open_risks"]),
            "strategy_packet_inputs": len(synthesis["strategy_packet_inputs"]),
            "call_trace_lineage_rows": sum(
                len(row["call_trace_lineage"])
                for row in (
                    list(synthesis["final_recommendations"])
                    + list(synthesis["deferred_recommendations"])
                    + list(synthesis["open_risks"])
                )
            ),
        },
    }

    errors = validate_req_046_final_strategy_synthesis_composer(output_payload)
    if errors:
        raise ValueError(f"built REQ-046 payload failed validation: {errors}")
    return output_payload


def validate_req_046_final_strategy_synthesis_composer(payload: Mapping[str, Any]) -> list[str]:
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
        "final_strategy_synthesis",
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
    if payload.get("schema_version") != REQ_046_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_046_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_046_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_046_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_046_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_046_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_046_CALL_ID:
        errors.append(f"call_id must be {REQ_046_CALL_ID}")
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
        target_project_id = str(target_project.get("project_id") or "")
        if not target_project_id:
            errors.append("target_project.project_id must be a non-empty string")
        project_root = target_project.get("project_root")
        if not isinstance(project_root, str) or not project_root.strip():
            errors.append("target_project.project_root must be a non-empty string")
        elif not project_root.startswith("/"):
            errors.append("target_project.project_root must be an absolute path")

    synthesis = payload.get("final_strategy_synthesis")
    packet_input_ids: set[str] = set()
    if not isinstance(synthesis, Mapping):
        errors.append("final_strategy_synthesis must be an object")
        return errors

    expected_synthesis_keys = {
        "final_recommendations",
        "deferred_recommendations",
        "open_risks",
        "strategy_packet_inputs",
        "cross_project_context_usage",
    }
    synthesis_keys = set(synthesis.keys())
    missing_synthesis = sorted(expected_synthesis_keys - synthesis_keys)
    if missing_synthesis:
        errors.append(f"final_strategy_synthesis missing keys: {missing_synthesis}")
    unexpected_synthesis = sorted(synthesis_keys - expected_synthesis_keys)
    if unexpected_synthesis:
        errors.append(f"final_strategy_synthesis has unexpected keys: {unexpected_synthesis}")

    strategy_packet_inputs = synthesis.get("strategy_packet_inputs")
    if not isinstance(strategy_packet_inputs, list):
        errors.append("final_strategy_synthesis.strategy_packet_inputs must be a list")
        strategy_packet_inputs = []
    else:
        for index, row in enumerate(strategy_packet_inputs):
            if not isinstance(row, Mapping):
                errors.append(f"final_strategy_synthesis.strategy_packet_inputs[{index}] must be an object")
                continue
            expected_keys = {
                "packet_input_id",
                "packet_kind",
                "target_project_id",
                "peer_project_id",
                "lane",
                "recommendation_ids",
                "recommendation_count",
                "earliest_sequence_hint",
                "evidence_refs",
            }
            row_keys = set(row.keys())
            missing_keys = sorted(expected_keys - row_keys)
            if missing_keys:
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}] missing keys: {missing_keys}"
                )
            unexpected_keys = sorted(row_keys - expected_keys)
            if unexpected_keys:
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}] has unexpected keys: {unexpected_keys}"
                )
            packet_input_id = row.get("packet_input_id")
            if not isinstance(packet_input_id, str) or not packet_input_id.startswith("pkt."):
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].packet_input_id must be like pkt.<id>"
                )
            elif packet_input_id in packet_input_ids:
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].packet_input_id must be unique"
                )
            else:
                packet_input_ids.add(packet_input_id)
            packet_kind = row.get("packet_kind")
            if packet_kind not in REQ_046_PACKET_KINDS:
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].packet_kind must be one of: {list(REQ_046_PACKET_KINDS)}"
                )
            target_project_id_value = row.get("target_project_id")
            if not isinstance(target_project_id_value, str) or not target_project_id_value.strip():
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].target_project_id must be a non-empty string"
                )
            elif target_project_id and target_project_id_value != target_project_id:
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].target_project_id must match target_project.project_id"
                )
            peer_project_id = row.get("peer_project_id")
            if not isinstance(peer_project_id, str):
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].peer_project_id must be a string"
                )
            elif packet_kind == "cross-project" and not peer_project_id.strip():
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].peer_project_id must be set for cross-project packets"
                )
            elif packet_kind == "target-project" and peer_project_id.strip():
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].peer_project_id must be empty for target-project packets"
                )
            if not isinstance(row.get("lane"), str) or not str(row.get("lane")).strip():
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].lane must be a non-empty string"
                )
            recommendation_ids = row.get("recommendation_ids")
            if not isinstance(recommendation_ids, list) or not recommendation_ids:
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].recommendation_ids must be a non-empty list"
                )
            recommendation_count = row.get("recommendation_count")
            if not isinstance(recommendation_count, int) or recommendation_count < 1:
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].recommendation_count must be a positive integer"
                )
            elif isinstance(recommendation_ids, list) and recommendation_count != len(recommendation_ids):
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].recommendation_count must match recommendation_ids length"
                )
            earliest_sequence_hint = row.get("earliest_sequence_hint")
            if not isinstance(earliest_sequence_hint, int) or earliest_sequence_hint < 1:
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].earliest_sequence_hint must be a positive integer"
                )
            evidence_refs = row.get("evidence_refs")
            if not isinstance(evidence_refs, list) or not evidence_refs:
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].evidence_refs must be a non-empty list"
                )

    def _validate_lineage_rows(rows: Any, *, field_name: str) -> None:
        if not isinstance(rows, list) or not rows:
            errors.append(f"{field_name} must be a non-empty list")
            return
        seen_trace_ids: set[str] = set()
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                errors.append(f"{field_name}[{index}] must be an object")
                continue
            expected_keys = {"call_id", "requirement_id", "trace_id", "trace_ref", "artifact_ref", "checked_at_utc"}
            row_keys = set(row.keys())
            missing_keys = sorted(expected_keys - row_keys)
            if missing_keys:
                errors.append(f"{field_name}[{index}] missing keys: {missing_keys}")
            unexpected_keys = sorted(row_keys - expected_keys)
            if unexpected_keys:
                errors.append(f"{field_name}[{index}] has unexpected keys: {unexpected_keys}")
            trace_id = row.get("trace_id")
            if not isinstance(trace_id, str) or not trace_id.strip():
                errors.append(f"{field_name}[{index}].trace_id must be a non-empty string")
            elif trace_id in seen_trace_ids:
                errors.append(f"{field_name}[{index}].trace_id must be unique within the lineage list")
            else:
                seen_trace_ids.add(trace_id)
            for key in ("call_id", "requirement_id", "trace_ref", "artifact_ref", "checked_at_utc"):
                value = row.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"{field_name}[{index}].{key} must be a non-empty string")

    final_recommendations = synthesis.get("final_recommendations")
    seen_final_ids: set[str] = set()
    referenced_packet_input_ids: set[str] = set()
    if not isinstance(final_recommendations, list):
        errors.append("final_strategy_synthesis.final_recommendations must be a list")
        final_recommendations = []
    else:
        for index, row in enumerate(final_recommendations):
            if not isinstance(row, Mapping):
                errors.append(f"final_strategy_synthesis.final_recommendations[{index}] must be an object")
                continue
            expected_keys = {
                "recommendation_id",
                "summary",
                "rationale",
                "packet_kind",
                "peer_project_id",
                "lane",
                "sequence_hint",
                "priority",
                "evidence_refs",
                "call_trace_lineage",
                "contributing_call_ids",
                "contributing_requirement_ids",
                "supporting_call_count",
                "strategy_packet_input_id",
            }
            row_keys = set(row.keys())
            missing_keys = sorted(expected_keys - row_keys)
            if missing_keys:
                errors.append(f"final_strategy_synthesis.final_recommendations[{index}] missing keys: {missing_keys}")
            unexpected_keys = sorted(row_keys - expected_keys)
            if unexpected_keys:
                errors.append(f"final_strategy_synthesis.final_recommendations[{index}] has unexpected keys: {unexpected_keys}")
            recommendation_id = row.get("recommendation_id")
            if not isinstance(recommendation_id, str) or not recommendation_id.strip():
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].recommendation_id must be a non-empty string"
                )
            elif recommendation_id in seen_final_ids:
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].recommendation_id must be unique"
                )
            else:
                seen_final_ids.add(recommendation_id)
            for key in ("summary", "rationale", "lane"):
                value = row.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(
                        f"final_strategy_synthesis.final_recommendations[{index}].{key} must be a non-empty string"
                    )
            packet_kind = row.get("packet_kind")
            if packet_kind not in REQ_046_PACKET_KINDS:
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].packet_kind must be one of: {list(REQ_046_PACKET_KINDS)}"
                )
            peer_project_id = row.get("peer_project_id")
            if not isinstance(peer_project_id, str):
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].peer_project_id must be a string"
                )
            elif packet_kind == "cross-project" and not peer_project_id.strip():
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].peer_project_id must be set for cross-project recommendations"
                )
            elif packet_kind == "target-project" and peer_project_id.strip():
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].peer_project_id must be empty for target-project recommendations"
                )
            sequence_hint = row.get("sequence_hint")
            if not isinstance(sequence_hint, int) or sequence_hint < 1:
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].sequence_hint must be a positive integer"
                )
            priority = row.get("priority")
            if priority not in REQ_046_PRIORITY_LEVELS:
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].priority must be one of: {list(REQ_046_PRIORITY_LEVELS)}"
                )
            evidence_refs = row.get("evidence_refs")
            if not isinstance(evidence_refs, list) or not evidence_refs:
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].evidence_refs must be a non-empty list"
                )
            _validate_lineage_rows(
                row.get("call_trace_lineage"),
                field_name=f"final_strategy_synthesis.final_recommendations[{index}].call_trace_lineage",
            )
            contributing_call_ids = row.get("contributing_call_ids")
            if not isinstance(contributing_call_ids, list) or not contributing_call_ids:
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].contributing_call_ids must be a non-empty list"
                )
            contributing_requirement_ids = row.get("contributing_requirement_ids")
            if not isinstance(contributing_requirement_ids, list) or not contributing_requirement_ids:
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].contributing_requirement_ids must be a non-empty list"
                )
            supporting_call_count = row.get("supporting_call_count")
            lineage_rows = row.get("call_trace_lineage") if isinstance(row.get("call_trace_lineage"), list) else []
            if not isinstance(supporting_call_count, int) or supporting_call_count < 1:
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].supporting_call_count must be a positive integer"
                )
            elif lineage_rows and supporting_call_count != len(lineage_rows):
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].supporting_call_count must match call_trace_lineage length"
                )
            strategy_packet_input_id = row.get("strategy_packet_input_id")
            if not isinstance(strategy_packet_input_id, str) or not strategy_packet_input_id.startswith("pkt."):
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].strategy_packet_input_id must be like pkt.<id>"
                )
            else:
                referenced_packet_input_ids.add(strategy_packet_input_id)

    deferred_recommendations = synthesis.get("deferred_recommendations")
    seen_deferred_ids: set[str] = set()
    if not isinstance(deferred_recommendations, list):
        errors.append("final_strategy_synthesis.deferred_recommendations must be a list")
        deferred_recommendations = []
    else:
        for index, row in enumerate(deferred_recommendations):
            if not isinstance(row, Mapping):
                errors.append(f"final_strategy_synthesis.deferred_recommendations[{index}] must be an object")
                continue
            expected_keys = {
                "recommendation_id",
                "summary",
                "deferred_reason_code",
                "packet_kind_candidates",
                "peer_project_candidates",
                "evidence_refs",
                "call_trace_lineage",
                "contributing_call_ids",
            }
            row_keys = set(row.keys())
            missing_keys = sorted(expected_keys - row_keys)
            if missing_keys:
                errors.append(
                    f"final_strategy_synthesis.deferred_recommendations[{index}] missing keys: {missing_keys}"
                )
            unexpected_keys = sorted(row_keys - expected_keys)
            if unexpected_keys:
                errors.append(
                    f"final_strategy_synthesis.deferred_recommendations[{index}] has unexpected keys: {unexpected_keys}"
                )
            recommendation_id = row.get("recommendation_id")
            if not isinstance(recommendation_id, str) or not recommendation_id.strip():
                errors.append(
                    f"final_strategy_synthesis.deferred_recommendations[{index}].recommendation_id must be a non-empty string"
                )
            elif recommendation_id in seen_deferred_ids or recommendation_id in seen_final_ids:
                errors.append(
                    f"final_strategy_synthesis.deferred_recommendations[{index}].recommendation_id must be unique across synthesis output"
                )
            else:
                seen_deferred_ids.add(recommendation_id)
            if not isinstance(row.get("summary"), str) or not str(row.get("summary")).strip():
                errors.append(
                    f"final_strategy_synthesis.deferred_recommendations[{index}].summary must be a non-empty string"
                )
            if row.get("deferred_reason_code") != REQ_046_ROUTING_CONFLICT_REASON:
                errors.append(
                    f"final_strategy_synthesis.deferred_recommendations[{index}].deferred_reason_code must be {REQ_046_ROUTING_CONFLICT_REASON}"
                )
            for key in ("packet_kind_candidates", "peer_project_candidates", "evidence_refs", "contributing_call_ids"):
                value = row.get(key)
                if not isinstance(value, list):
                    errors.append(
                        f"final_strategy_synthesis.deferred_recommendations[{index}].{key} must be a list"
                    )
            _validate_lineage_rows(
                row.get("call_trace_lineage"),
                field_name=f"final_strategy_synthesis.deferred_recommendations[{index}].call_trace_lineage",
            )

    open_risks = synthesis.get("open_risks")
    seen_open_risk_ids: set[str] = set()
    if not isinstance(open_risks, list):
        errors.append("final_strategy_synthesis.open_risks must be a list")
        open_risks = []
    else:
        for index, row in enumerate(open_risks):
            if not isinstance(row, Mapping):
                errors.append(f"final_strategy_synthesis.open_risks[{index}] must be an object")
                continue
            expected_keys = {
                "open_risk_id",
                "recommendation_id",
                "summary",
                "reason_code",
                "project_id",
                "required_evidence_refs",
                "evidence_refs",
                "linked_recommendation_ids",
                "call_trace_lineage",
                "contributing_call_ids",
            }
            row_keys = set(row.keys())
            missing_keys = sorted(expected_keys - row_keys)
            if missing_keys:
                errors.append(f"final_strategy_synthesis.open_risks[{index}] missing keys: {missing_keys}")
            unexpected_keys = sorted(row_keys - expected_keys)
            if unexpected_keys:
                errors.append(f"final_strategy_synthesis.open_risks[{index}] has unexpected keys: {unexpected_keys}")

            open_risk_id = row.get("open_risk_id")
            if not isinstance(open_risk_id, str) or not open_risk_id.strip():
                errors.append(f"final_strategy_synthesis.open_risks[{index}].open_risk_id must be a non-empty string")
            elif open_risk_id in seen_open_risk_ids:
                errors.append(f"final_strategy_synthesis.open_risks[{index}].open_risk_id must be unique")
            else:
                seen_open_risk_ids.add(open_risk_id)

            recommendation_id = row.get("recommendation_id")
            if not isinstance(recommendation_id, str) or not recommendation_id.strip():
                errors.append(
                    f"final_strategy_synthesis.open_risks[{index}].recommendation_id must be a non-empty string"
                )
            if not isinstance(row.get("summary"), str) or not str(row.get("summary")).strip():
                errors.append(f"final_strategy_synthesis.open_risks[{index}].summary must be a non-empty string")
            reason_code = row.get("reason_code")
            if reason_code not in (
                REQ_046_OPEN_RISK_REASON_MISSING_EARTH_SWEEP_EVIDENCE,
                REQ_046_OPEN_RISK_REASON_UNRESOLVED_IDEA,
                REQ_046_OPEN_RISK_REASON_UNCITED_STRATEGIC_CLAIM_BLOCKED,
            ):
                errors.append(
                    "final_strategy_synthesis.open_risks"
                    f"[{index}].reason_code must be one of: "
                    f"{[REQ_046_OPEN_RISK_REASON_MISSING_EARTH_SWEEP_EVIDENCE, REQ_046_OPEN_RISK_REASON_UNRESOLVED_IDEA, REQ_046_OPEN_RISK_REASON_UNCITED_STRATEGIC_CLAIM_BLOCKED]}"
                )
            if not isinstance(row.get("project_id"), str):
                errors.append(f"final_strategy_synthesis.open_risks[{index}].project_id must be a string")
            for key in ("required_evidence_refs", "evidence_refs", "linked_recommendation_ids", "contributing_call_ids"):
                if not isinstance(row.get(key), list):
                    errors.append(f"final_strategy_synthesis.open_risks[{index}].{key} must be a list")

            lineage_rows = row.get("call_trace_lineage")
            if not isinstance(lineage_rows, list):
                errors.append(f"final_strategy_synthesis.open_risks[{index}].call_trace_lineage must be a list")
                lineage_rows = []
            elif reason_code == REQ_046_OPEN_RISK_REASON_MISSING_EARTH_SWEEP_EVIDENCE and not lineage_rows:
                errors.append(
                    f"final_strategy_synthesis.open_risks[{index}].call_trace_lineage must be non-empty for missing Earth sweep evidence risks"
                )
            elif reason_code == REQ_046_OPEN_RISK_REASON_UNCITED_STRATEGIC_CLAIM_BLOCKED and not lineage_rows:
                errors.append(
                    f"final_strategy_synthesis.open_risks[{index}].call_trace_lineage must be non-empty for uncited strategic claim risks"
                )
            if lineage_rows:
                _validate_lineage_rows(
                    lineage_rows,
                    field_name=f"final_strategy_synthesis.open_risks[{index}].call_trace_lineage",
                )

    cross_project_context_usage = synthesis.get("cross_project_context_usage")
    if not isinstance(cross_project_context_usage, Mapping):
        errors.append("final_strategy_synthesis.cross_project_context_usage must be an object")
    else:
        expected_usage_keys = {
            "cross_project_context_provided",
            "cross_project_context_used",
            "projects_considered",
            "earth_sweep_evidence_refs_considered",
            "cross_project_obligation_count",
            "unresolved_idea_count",
            "recommendation_ids_with_context",
        }
        usage_keys = set(cross_project_context_usage.keys())
        missing_usage = sorted(expected_usage_keys - usage_keys)
        if missing_usage:
            errors.append(f"final_strategy_synthesis.cross_project_context_usage missing keys: {missing_usage}")
        unexpected_usage = sorted(usage_keys - expected_usage_keys)
        if unexpected_usage:
            errors.append(f"final_strategy_synthesis.cross_project_context_usage has unexpected keys: {unexpected_usage}")
        if not isinstance(cross_project_context_usage.get("cross_project_context_provided"), bool):
            errors.append("final_strategy_synthesis.cross_project_context_usage.cross_project_context_provided must be a boolean")
        if not isinstance(cross_project_context_usage.get("cross_project_context_used"), bool):
            errors.append("final_strategy_synthesis.cross_project_context_usage.cross_project_context_used must be a boolean")
        for key in (
            "projects_considered",
            "earth_sweep_evidence_refs_considered",
            "recommendation_ids_with_context",
        ):
            value = cross_project_context_usage.get(key)
            if not isinstance(value, list):
                errors.append(f"final_strategy_synthesis.cross_project_context_usage.{key} must be a list")
        for key in ("cross_project_obligation_count", "unresolved_idea_count"):
            value = cross_project_context_usage.get(key)
            if not isinstance(value, int) or value < 0:
                errors.append(
                    f"final_strategy_synthesis.cross_project_context_usage.{key} must be a non-negative integer"
                )

    if packet_input_ids and referenced_packet_input_ids != packet_input_ids:
        errors.append(
            "final_strategy_synthesis.final_recommendations.strategy_packet_input_id values must cover all strategy_packet_inputs"
        )

    totals = payload.get("totals")
    if not isinstance(totals, Mapping):
        errors.append("totals must be an object")
    else:
        expected_total_keys = {
            "validated_calls",
            "candidate_recommendations",
            "final_recommendations",
            "deferred_recommendations",
            "open_risks",
            "strategy_packet_inputs",
            "call_trace_lineage_rows",
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

        if totals.get("final_recommendations") != len(final_recommendations):
            errors.append("totals.final_recommendations must match synthesized final recommendations count")
        if totals.get("deferred_recommendations") != len(deferred_recommendations):
            errors.append("totals.deferred_recommendations must match synthesized deferred recommendations count")
        if totals.get("open_risks") != len(open_risks):
            errors.append("totals.open_risks must match synthesized open risk count")
        if totals.get("strategy_packet_inputs") != len(strategy_packet_inputs):
            errors.append("totals.strategy_packet_inputs must match synthesized packet input count")

        expected_lineage_rows = 0
        unique_trace_ids: set[str] = set()
        for collection in (final_recommendations, deferred_recommendations, open_risks):
            for row in collection:
                if isinstance(row, Mapping) and isinstance(row.get("call_trace_lineage"), list):
                    expected_lineage_rows += len(row["call_trace_lineage"])
                    unique_trace_ids.update(
                        str(lineage_row.get("trace_id"))
                        for lineage_row in row["call_trace_lineage"]
                        if isinstance(lineage_row, Mapping) and str(lineage_row.get("trace_id") or "").strip()
                    )
        if totals.get("call_trace_lineage_rows") != expected_lineage_rows:
            errors.append("totals.call_trace_lineage_rows must match all synthesized lineage rows")
        if totals.get("candidate_recommendations") != expected_lineage_rows:
            errors.append("totals.candidate_recommendations must match all synthesized candidate recommendation rows")
        if totals.get("validated_calls") != len(unique_trace_ids):
            errors.append("totals.validated_calls must match unique call trace lineage rows")

    return errors


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


def _req_029_normalize_call_chain(
    value: Any,
    *,
    field_name: str = "call_chain",
) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise Req029Error(f"{field_name} must be an array")

    normalized: list[dict[str, Any]] = []
    seen_sequences: set[int] = set()
    seen_call_ids: set[str] = set()
    for index, raw_row in enumerate(value):
        row = _require_mapping(raw_row, field_name=f"{field_name}[{index}]")
        sequence = row.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int):
            raise Req029Error(f"{field_name}[{index}].sequence must be an integer")
        if sequence < 1:
            raise Req029Error(f"{field_name}[{index}].sequence must be >= 1")
        if sequence in seen_sequences:
            raise Req029Error(f"{field_name}[{index}].sequence must be unique")
        seen_sequences.add(sequence)

        call_id = _require_text(row.get("call_id"), field_name=f"{field_name}[{index}].call_id")
        if call_id in seen_call_ids:
            raise Req029Error(f"{field_name}[{index}].call_id must be unique")
        seen_call_ids.add(call_id)

        normalized.append(
            {
                "sequence": sequence,
                "call_id": call_id,
                "phase": _require_text(row.get("phase"), field_name=f"{field_name}[{index}].phase"),
                "output_ref": _require_text(row.get("output_ref"), field_name=f"{field_name}[{index}].output_ref"),
            }
        )

    normalized.sort(key=lambda row: row["sequence"])
    expected_sequences = list(range(1, len(normalized) + 1))
    actual_sequences = [row["sequence"] for row in normalized]
    if actual_sequences != expected_sequences:
        raise Req029Error(f"{field_name}.sequence must be contiguous starting at 1")
    if len(normalized) < 4:
        raise Req029Error(f"{field_name} must include at least 4 calls for Call-4 synthesis")
    return normalized


def _req_029_slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "recommendation"


def _req_029_recommendation_id_from_candidate(row: Mapping[str, Any], *, index: int) -> str:
    provided = _as_text(row.get("recommendation_id"))
    if provided:
        if not REQ_029_RECOMMENDATION_ID_RE.match(provided):
            raise Req029Error(
                f"candidate_recommendations[{index}].recommendation_id must match {REQ_029_RECOMMENDATION_ID_RE.pattern}"
            )
        return provided

    summary = _require_text(row.get("summary"), field_name=f"candidate_recommendations[{index}].summary")
    return f"rec.{_req_029_slugify(summary)}"


def _req_029_normalize_candidate_recommendations(
    value: Any,
    *,
    field_name: str = "candidate_recommendations",
) -> list[dict[str, Any]]:
    if value is None:
        rows: Sequence[Any] = []
    else:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            raise Req029Error(f"{field_name} must be an array")
        rows = value

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_row in enumerate(rows):
        row = _require_mapping(raw_row, field_name=f"{field_name}[{index}]")
        recommendation_id = _req_029_recommendation_id_from_candidate(row, index=index)
        if recommendation_id in seen_ids:
            raise Req029Error(f"{field_name}[{index}].recommendation_id must be unique")
        seen_ids.add(recommendation_id)

        recommendation_scope = _require_text(
            row.get("recommendation_scope"),
            field_name=f"{field_name}[{index}].recommendation_scope",
        ).lower()
        if recommendation_scope not in REQ_029_ALLOWED_RECOMMENDATION_SCOPES:
            raise Req029Error(
                f"{field_name}[{index}].recommendation_scope must be one of {sorted(REQ_029_ALLOWED_RECOMMENDATION_SCOPES)}"
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

        synthesized_from_call_sequence = row.get("synthesized_from_call_sequence")
        if isinstance(synthesized_from_call_sequence, bool) or not isinstance(synthesized_from_call_sequence, int):
            raise Req029Error(f"{field_name}[{index}].synthesized_from_call_sequence must be an integer")

        normalized.append(
            {
                "recommendation_id": recommendation_id,
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
                "next_step": _require_text(row.get("next_step"), field_name=f"{field_name}[{index}].next_step"),
                "synthesized_from_call_sequence": synthesized_from_call_sequence,
            }
        )

    normalized.sort(key=lambda row: row["recommendation_id"])
    return normalized


def _req_029_normalize_strategic_claims(
    value: Any,
    *,
    field_name: str = "strategic_claims",
    call_depth: int,
) -> list[dict[str, Any]]:
    if value is None:
        rows: Sequence[Any] = []
    else:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            raise Req029Error(f"{field_name} must be an array")
        rows = value

    normalized: list[dict[str, Any]] = []
    for index, raw_row in enumerate(rows):
        row = _require_mapping(raw_row, field_name=f"{field_name}[{index}]")
        source_call_sequence = row.get("source_call_sequence")
        if isinstance(source_call_sequence, bool) or not isinstance(source_call_sequence, int):
            raise Req029Error(f"{field_name}[{index}].source_call_sequence must be an integer")
        if source_call_sequence < 1 or source_call_sequence > call_depth:
            raise Req029Error(f"{field_name}[{index}].source_call_sequence must be between 1 and {call_depth}")
        normalized.append(
            {
                "claim_id": _require_text(row.get("claim_id"), field_name=f"{field_name}[{index}].claim_id"),
                "phase": _require_text(row.get("phase"), field_name=f"{field_name}[{index}].phase").lower(),
                "summary": _require_text(row.get("summary"), field_name=f"{field_name}[{index}].summary"),
                "position": _require_text(row.get("position"), field_name=f"{field_name}[{index}].position"),
                "source_call_sequence": source_call_sequence,
                "evidence_refs": _normalize_string_list(
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


def _req_029_build_trace_rows(
    *,
    synthesis_call_id: str,
    call_chain: Sequence[Mapping[str, Any]],
    recommendation_ids: Sequence[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    output_ref_by_sequence = {int(row["sequence"]): str(row["output_ref"]) for row in call_chain}
    prior_output_refs: list[str] = []
    for row in call_chain:
        sequence = int(row["sequence"])
        call_id = str(row["call_id"])
        output_ref = str(row["output_ref"])
        input_refs = list(prior_output_refs)
        if sequence == 4:
            input_refs = list(prior_output_refs)
        rows.append(
            {
                "schema_version": REQ_029_LLM_CALL_TRACE_SCHEMA_VERSION,
                "requirement_id": REQ_029_REQUIREMENT_ID,
                "processing_call_id": synthesis_call_id,
                "call_id": call_id,
                "sequence": sequence,
                "call_objective": str(row["phase"]),
                "input_refs": input_refs,
                "output_refs": [output_ref],
                "handoff_summary": (
                    f"Call {sequence} supplies {output_ref}."
                    if sequence < 4
                    else f"Call 4 synthesizes recommendation_drafts for {len(recommendation_ids)} recommendation(s)."
                ),
            }
        )
        if output_ref_by_sequence.get(sequence):
            prior_output_refs.append(output_ref)
    return rows


def _req_029_canonical_input(
    *,
    target_project_root: str,
    earth_root: str,
    output_root: str,
    revision_identity: str,
    strategy_goal: str,
    call_id: str,
    checked_at_utc: str,
) -> dict[str, Any]:
    return {
        "runtime_mode": RUNTIME_MODE,
        "execution_mode": EXECUTION_MODE,
        "target_project_root": target_project_root,
        "earth_root": earth_root,
        "output_root": output_root,
        "revision_identity": revision_identity,
        "strategy_goal": strategy_goal,
        "analysis_type": REQ_029_ANALYSIS_TYPE,
        "call_id": call_id,
        "checked_at_utc": checked_at_utc,
    }


def _req_029_canonical_processing_input(
    *,
    call_chain: Sequence[Mapping[str, Any]],
    target_project_evidence_refs: Sequence[str],
    earth_sweep_evidence_refs: Sequence[str],
    cross_project_context: Sequence[Mapping[str, Any]],
    candidate_recommendations: Sequence[Mapping[str, Any]],
    strategic_claims: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "call_chain": [dict(row) for row in call_chain],
        "target_project_evidence_refs": list(target_project_evidence_refs),
        "earth_sweep_evidence_refs": list(earth_sweep_evidence_refs),
        "cross_project_context": [dict(row) for row in cross_project_context],
        "candidate_recommendations": [dict(row) for row in candidate_recommendations],
        "strategic_claims": [dict(row) for row in strategic_claims],
    }


def build_req_029_call_4_recommendation_synthesis(
    *,
    target_project_root: str,
    earth_root: str,
    output_root: str,
    revision_identity: str,
    strategy_goal: str,
    call_chain: Sequence[Mapping[str, Any]],
    candidate_recommendations: Sequence[Mapping[str, Any]],
    strategic_claims: Sequence[Mapping[str, Any]] | None = None,
    cross_project_context: Sequence[Mapping[str, Any]] | None = None,
    target_project_evidence_refs: Sequence[Any] | None = None,
    earth_sweep_evidence_refs: Sequence[Any] | None = None,
    call_id: str = "call-4",
    checked_at_utc: str | None = None,
) -> dict[str, Any]:
    normalized_target_root = _normalize_root(target_project_root, field_name="target_project_root")
    normalized_earth_root = _normalize_root(earth_root, field_name="earth_root")
    normalized_output_root = _normalize_root(output_root, field_name="output_root")
    normalized_revision_identity = _require_text(revision_identity, field_name="revision_identity")
    normalized_strategy_goal = _require_text(strategy_goal, field_name="strategy_goal")
    normalized_call_id = _require_text(call_id, field_name="call_id")
    normalized_checked_at_utc = _require_text(checked_at_utc or utc_now_iso(), field_name="checked_at_utc")
    normalized_call_chain = _req_029_normalize_call_chain(call_chain)
    normalized_target_refs = _normalize_string_list(
        target_project_evidence_refs,
        field_name="target_project_evidence_refs",
    )
    normalized_earth_refs = _normalize_string_list(
        earth_sweep_evidence_refs,
        field_name="earth_sweep_evidence_refs",
    )
    normalized_cross_project_context = _normalize_cross_project_context(cross_project_context)
    normalized_candidate_recommendations = _req_029_normalize_candidate_recommendations(candidate_recommendations)
    normalized_strategic_claims = _req_029_normalize_strategic_claims(
        strategic_claims,
        call_depth=len(normalized_call_chain),
    )

    cross_project_refs = _collect_unique_refs(*[row["evidence_refs"] for row in normalized_cross_project_context])
    available_citation_refs = set(
        _collect_unique_refs(
            normalized_target_refs,
            normalized_earth_refs,
            cross_project_refs,
            [row["output_ref"] for row in normalized_call_chain],
        )
    )
    output_ref_by_sequence = {int(row["sequence"]): str(row["output_ref"]) for row in normalized_call_chain}
    context_by_project = {str(row["project_id"]): row for row in normalized_cross_project_context}

    blocked_ids: set[str] = set()
    open_risks: list[dict[str, Any]] = []
    claim_rows_by_id: dict[str, list[dict[str, Any]]] = {}
    for claim in normalized_strategic_claims:
        claim_rows_by_id.setdefault(str(claim["claim_id"]), []).append(claim)
        source_output_ref = output_ref_by_sequence.get(int(claim["source_call_sequence"]), "")
        citation_refs = list(claim["evidence_refs"])
        if not citation_refs or not set(citation_refs).issubset(available_citation_refs):
            risk_id = f"risk-claim-{claim['claim_id']}-citation"
            open_risks.append(
                {
                    "risk_id": risk_id,
                    "reason_code": "uncited_strategic_claim",
                    "summary": str(claim["summary"]),
                    "required_evidence_refs": _collect_unique_refs([source_output_ref], citation_refs),
                }
            )

    for claim_id, claim_rows in claim_rows_by_id.items():
        analysis_rows = [row for row in claim_rows if row["phase"] == "analysis"]
        synthesis_rows = [row for row in claim_rows if row["phase"] == "synthesis"]
        contradiction_found = False
        for analysis_row in analysis_rows:
            for synthesis_row in synthesis_rows:
                if analysis_row["position"] == synthesis_row["position"]:
                    continue
                open_risks.append(
                    {
                        "risk_id": f"risk-claim-{claim_id}-contradiction",
                        "reason_code": "cross_call_contradiction",
                        "summary": str(synthesis_row["summary"]),
                        "required_evidence_refs": _collect_unique_refs(
                            [output_ref_by_sequence.get(int(analysis_row["source_call_sequence"]), "")],
                            [output_ref_by_sequence.get(int(synthesis_row["source_call_sequence"]), "")],
                            analysis_row["evidence_refs"],
                            synthesis_row["evidence_refs"],
                        ),
                    }
                )
                contradiction_found = True
                break
            if contradiction_found:
                break

    recommendation_drafts: list[dict[str, Any]] = []
    for row in normalized_candidate_recommendations:
        recommendation_id = str(row["recommendation_id"])
        source_output_ref = output_ref_by_sequence.get(int(row["synthesized_from_call_sequence"]), "")
        uncited_refs = sorted(set(row["evidence_refs"]) - available_citation_refs)
        if uncited_refs:
            blocked_ids.add(recommendation_id)
            open_risks.append(
                {
                    "risk_id": f"risk-{recommendation_id}-citation",
                    "reason_code": "uncited_strategic_claim",
                    "summary": str(row["summary"]),
                    "required_evidence_refs": _collect_unique_refs([source_output_ref], uncited_refs),
                }
            )
            continue

        project_context = context_by_project.get(str(row["project_id"]))
        project_evidence_refs = list(project_context["evidence_refs"]) if project_context else []
        if row["recommendation_scope"] == "cross-project":
            if row["requires_earth_evidence"] and not normalized_earth_refs:
                blocked_ids.add(recommendation_id)
                open_risks.append(
                    {
                        "risk_id": f"risk-{recommendation_id}-earth-evidence",
                        "reason_code": "missing_earth_sweep_evidence_refs",
                        "summary": str(row["summary"]),
                        "required_evidence_refs": _collect_unique_refs([source_output_ref], row["evidence_refs"]),
                    }
                )
                continue
            if project_context is None:
                blocked_ids.add(recommendation_id)
                open_risks.append(
                    {
                        "risk_id": f"risk-{recommendation_id}-context",
                        "reason_code": "missing_cross_project_context",
                        "summary": str(row["summary"]),
                        "required_evidence_refs": _collect_unique_refs([source_output_ref], row["evidence_refs"]),
                    }
                )
                continue

        recommendation_drafts.append(
            {
                "recommendation_id": recommendation_id,
                "summary": str(row["summary"]),
                "rationale": str(row["rationale"]),
                "impact": str(row["impact"]),
                "risk": str(row["risk"]),
                "recommendation_scope": str(row["recommendation_scope"]),
                "project_id": str(row["project_id"]),
                "next_step": str(row["next_step"]),
                "synthesized_from_call_sequence": int(row["synthesized_from_call_sequence"]),
                "source_output_ref": source_output_ref,
                "evidence_refs": _collect_unique_refs(
                    [source_output_ref],
                    row["evidence_refs"],
                    project_evidence_refs,
                    normalized_earth_refs if row["recommendation_scope"] == "cross-project" else [],
                ),
            }
        )

    recommendation_drafts.sort(key=lambda row: row["recommendation_id"])
    open_risks.sort(key=lambda row: row["risk_id"])

    evidence_refs = _collect_unique_refs(
        normalized_target_refs,
        normalized_earth_refs,
        cross_project_refs,
        [row["output_ref"] for row in normalized_call_chain],
        *[row["evidence_refs"] for row in recommendation_drafts],
        *[row["required_evidence_refs"] for row in open_risks],
    )
    if recommendation_drafts and not open_risks:
        decision = "proceed"
    elif recommendation_drafts and open_risks:
        decision = "proceed-with-open-risks"
    elif open_risks:
        decision = "blocked"
    else:
        decision = "insufficient-context"
    confidence = "high" if recommendation_drafts and not open_risks else "medium" if recommendation_drafts else "low"

    canonical_input = _req_029_canonical_input(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        output_root=normalized_output_root,
        revision_identity=normalized_revision_identity,
        strategy_goal=normalized_strategy_goal,
        call_id=normalized_call_id,
        checked_at_utc=normalized_checked_at_utc,
    )
    canonical_processing_input = _req_029_canonical_processing_input(
        call_chain=normalized_call_chain,
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        cross_project_context=normalized_cross_project_context,
        candidate_recommendations=normalized_candidate_recommendations,
        strategic_claims=normalized_strategic_claims,
    )
    processing_sha = _canonical_digest(canonical_processing_input)
    processing_call_id = f"req029-processing-{processing_sha[:16]}"
    llm_call_trace_rows = _req_029_build_trace_rows(
        synthesis_call_id=processing_call_id,
        call_chain=normalized_call_chain,
        recommendation_ids=[str(row["recommendation_id"]) for row in recommendation_drafts],
    )

    return {
        "schema_version": REQ_029_SCHEMA_VERSION,
        "requirement_id": REQ_029_REQUIREMENT_ID,
        "analysis_type": REQ_029_ANALYSIS_TYPE,
        "call_id": normalized_call_id,
        "checked_at_utc": normalized_checked_at_utc,
        "processing_behavior": {
            "strategy": REQ_029_PROCESSING_STRATEGY,
            "reasoning_mode": REQ_029_REASONING_MODE,
            "strict_evidence_discipline": True,
            "context_inputs": {
                "call_chain": [dict(row) for row in normalized_call_chain],
                "target_project": {
                    "project_root": normalized_target_root,
                    "evidence_refs": list(normalized_target_refs),
                },
                "earth_sweep": {
                    "earth_root": normalized_earth_root,
                    "evidence_refs": list(normalized_earth_refs),
                },
                "cross_project_context": [dict(row) for row in normalized_cross_project_context],
                "candidate_recommendations": [dict(row) for row in normalized_candidate_recommendations],
                "strategic_claims": [dict(row) for row in normalized_strategic_claims],
            },
            "context_usage": {
                "call_ids_considered": [str(row["call_id"]) for row in normalized_call_chain],
                "candidate_recommendation_ids_considered": [
                    str(row["recommendation_id"]) for row in normalized_candidate_recommendations
                ],
                "emitted_recommendation_ids": [str(row["recommendation_id"]) for row in recommendation_drafts],
                "blocked_recommendation_ids": sorted(blocked_ids),
                "open_risk_ids_emitted": [str(row["risk_id"]) for row in open_risks],
                "evidence_refs_used": list(evidence_refs),
            },
            "recommendation": {
                "decision": decision,
                "rationale": (
                    f"drafts={len(recommendation_drafts)} open_risks={len(open_risks)} "
                    f"blocked={len(blocked_ids)}"
                ),
                "confidence": confidence,
                "evidence_refs": list(evidence_refs),
                "recommendation_drafts": recommendation_drafts,
                "open_risks": open_risks,
            },
        },
        "call_metadata": {
            "reproducibility": "deterministic-input-fingerprint",
            "canonical_input": canonical_input,
            "canonical_input_sha256": _canonical_digest(canonical_input),
            "reproducible_call_id": f"req029-{_canonical_digest(canonical_input)[:16]}",
            "canonical_processing_input": canonical_processing_input,
            "processing_input_sha256": processing_sha,
            "processing_call_id": processing_call_id,
            "llm_call_trace_schema_version": REQ_029_LLM_CALL_TRACE_SCHEMA_VERSION,
            "llm_call_trace_path": LLM_CALL_TRACE_RELATIVE_PATH,
            "llm_call_trace_sha256": _canonical_digest(llm_call_trace_rows),
            "llm_call_trace_rows": llm_call_trace_rows,
        },
    }


def validate_req_029_call_4_recommendation_synthesis(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    if payload.get("schema_version") != REQ_029_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_029_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_029_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_029_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_029_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_029_ANALYSIS_TYPE}")
    if not _as_text(payload.get("call_id")):
        errors.append("call_id is required")
    if not _as_text(payload.get("checked_at_utc")):
        errors.append("checked_at_utc is required")

    processing_behavior = payload.get("processing_behavior")
    if not isinstance(processing_behavior, Mapping):
        errors.append("processing_behavior must be an object")
        return errors
    if processing_behavior.get("strategy") != REQ_029_PROCESSING_STRATEGY:
        errors.append(f"processing_behavior.strategy must be {REQ_029_PROCESSING_STRATEGY}")
    if processing_behavior.get("reasoning_mode") != REQ_029_REASONING_MODE:
        errors.append(f"processing_behavior.reasoning_mode must be {REQ_029_REASONING_MODE}")
    if processing_behavior.get("strict_evidence_discipline") is not True:
        errors.append("processing_behavior.strict_evidence_discipline must be true")

    context_inputs = processing_behavior.get("context_inputs")
    normalized_call_chain: list[dict[str, Any]] = []
    normalized_target_refs: list[str] = []
    normalized_earth_refs: list[str] = []
    normalized_cross_project_context: list[dict[str, Any]] = []
    normalized_candidate_recommendations: list[dict[str, Any]] = []
    normalized_strategic_claims: list[dict[str, Any]] = []
    if not isinstance(context_inputs, Mapping):
        errors.append("processing_behavior.context_inputs must be an object")
        return errors
    try:
        normalized_call_chain = _req_029_normalize_call_chain(context_inputs.get("call_chain"))
    except Req029Error as exc:
        errors.append(str(exc))
    target_project = context_inputs.get("target_project")
    if not isinstance(target_project, Mapping):
        errors.append("processing_behavior.context_inputs.target_project must be an object")
    else:
        normalized_target_refs = sorted(
            {_as_text(ref) for ref in target_project.get("evidence_refs", []) if _as_text(ref)}
        )
    earth_sweep = context_inputs.get("earth_sweep")
    if not isinstance(earth_sweep, Mapping):
        errors.append("processing_behavior.context_inputs.earth_sweep must be an object")
    else:
        normalized_earth_refs = sorted(
            {_as_text(ref) for ref in earth_sweep.get("evidence_refs", []) if _as_text(ref)}
        )
    try:
        normalized_cross_project_context = _normalize_cross_project_context(context_inputs.get("cross_project_context"))
    except ValueError as exc:
        errors.append(str(exc))
    try:
        normalized_candidate_recommendations = _req_029_normalize_candidate_recommendations(
            context_inputs.get("candidate_recommendations")
        )
    except Req029Error as exc:
        errors.append(str(exc))
    try:
        normalized_strategic_claims = _req_029_normalize_strategic_claims(
            context_inputs.get("strategic_claims"),
            call_depth=len(normalized_call_chain) if normalized_call_chain else 4,
        )
    except Req029Error as exc:
        errors.append(str(exc))

    recommendation = processing_behavior.get("recommendation")
    if not isinstance(recommendation, Mapping):
        errors.append("processing_behavior.recommendation must be an object")
        return errors
    if not isinstance(recommendation.get("evidence_refs"), list):
        errors.append("processing_behavior.recommendation.evidence_refs must be a list")
    recommendation_drafts = recommendation.get("recommendation_drafts")
    if not isinstance(recommendation_drafts, list):
        errors.append("processing_behavior.recommendation.recommendation_drafts must be a list")
        recommendation_drafts = []
    previous_id = ""
    for index, row in enumerate(recommendation_drafts):
        if not isinstance(row, Mapping):
            errors.append(f"processing_behavior.recommendation.recommendation_drafts[{index}] must be an object")
            continue
        recommendation_id = _as_text(row.get("recommendation_id"))
        if not REQ_029_RECOMMENDATION_ID_RE.match(recommendation_id):
            errors.append(
                f"processing_behavior.recommendation.recommendation_drafts[{index}].recommendation_id must match {REQ_029_RECOMMENDATION_ID_RE.pattern}"
            )
        if previous_id and recommendation_id < previous_id:
            errors.append("processing_behavior.recommendation.recommendation_drafts must be sorted by recommendation_id")
        previous_id = recommendation_id
        for field_name in ("summary", "rationale", "impact", "risk", "next_step", "source_output_ref"):
            if not _as_text(row.get(field_name)):
                errors.append(
                    f"processing_behavior.recommendation.recommendation_drafts[{index}].{field_name} is required"
                )
        if not isinstance(row.get("evidence_refs"), list) or not row.get("evidence_refs"):
            errors.append(
                f"processing_behavior.recommendation.recommendation_drafts[{index}].evidence_refs must be non-empty list"
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
            errors.append(f"processing_behavior.recommendation.open_risks[{index}].risk_id is required")
        if not _as_text(row.get("reason_code")):
            errors.append(f"processing_behavior.recommendation.open_risks[{index}].reason_code is required")
        if not isinstance(row.get("required_evidence_refs"), list) or not row.get("required_evidence_refs"):
            errors.append(
                f"processing_behavior.recommendation.open_risks[{index}].required_evidence_refs must be non-empty list"
            )

    metadata = payload.get("call_metadata")
    if not isinstance(metadata, Mapping):
        errors.append("call_metadata must be an object")
        return errors
    if metadata.get("reproducibility") != "deterministic-input-fingerprint":
        errors.append("call_metadata.reproducibility must be deterministic-input-fingerprint")
    canonical_input = metadata.get("canonical_input")
    if not isinstance(canonical_input, Mapping):
        errors.append("call_metadata.canonical_input must be an object")
    else:
        expected_canonical_input = _req_029_canonical_input(
            target_project_root=_as_text(context_inputs.get("target_project", {}).get("project_root"))
            if isinstance(context_inputs.get("target_project"), Mapping)
            else "",
            earth_root=_as_text(context_inputs.get("earth_sweep", {}).get("earth_root"))
            if isinstance(context_inputs.get("earth_sweep"), Mapping)
            else "",
            output_root=_as_text(canonical_input.get("output_root")),
            revision_identity=_as_text(canonical_input.get("revision_identity")),
            strategy_goal=_as_text(canonical_input.get("strategy_goal")),
            call_id=_as_text(payload.get("call_id")),
            checked_at_utc=_as_text(payload.get("checked_at_utc")),
        )
        if dict(canonical_input) != expected_canonical_input:
            errors.append("call_metadata.canonical_input must mirror normalized invocation anchors")
        expected_input_sha = _canonical_digest(expected_canonical_input)
        if metadata.get("canonical_input_sha256") != expected_input_sha:
            errors.append("call_metadata.canonical_input_sha256 does not match canonical input")
        if metadata.get("reproducible_call_id") != f"req029-{expected_input_sha[:16]}":
            errors.append("call_metadata.reproducible_call_id does not match canonical digest")

    canonical_processing_input = metadata.get("canonical_processing_input")
    if not isinstance(canonical_processing_input, Mapping):
        errors.append("call_metadata.canonical_processing_input must be an object")
    else:
        expected_processing_input = _req_029_canonical_processing_input(
            call_chain=normalized_call_chain,
            target_project_evidence_refs=normalized_target_refs,
            earth_sweep_evidence_refs=normalized_earth_refs,
            cross_project_context=normalized_cross_project_context,
            candidate_recommendations=normalized_candidate_recommendations,
            strategic_claims=normalized_strategic_claims,
        )
        if dict(canonical_processing_input) != expected_processing_input:
            errors.append("call_metadata.canonical_processing_input must mirror normalized synthesis inputs")
        expected_processing_sha = _canonical_digest(expected_processing_input)
        if metadata.get("processing_input_sha256") != expected_processing_sha:
            errors.append("call_metadata.processing_input_sha256 does not match processing input")
        if metadata.get("processing_call_id") != f"req029-processing-{expected_processing_sha[:16]}":
            errors.append("call_metadata.processing_call_id does not match processing digest")

    if metadata.get("llm_call_trace_schema_version") != REQ_029_LLM_CALL_TRACE_SCHEMA_VERSION:
        errors.append(
            f"call_metadata.llm_call_trace_schema_version must be {REQ_029_LLM_CALL_TRACE_SCHEMA_VERSION}"
        )
    if metadata.get("llm_call_trace_path") != LLM_CALL_TRACE_RELATIVE_PATH:
        errors.append(f"call_metadata.llm_call_trace_path must be {LLM_CALL_TRACE_RELATIVE_PATH}")
    llm_call_trace_rows = metadata.get("llm_call_trace_rows")
    if not isinstance(llm_call_trace_rows, list):
        errors.append("call_metadata.llm_call_trace_rows must be a list")
    else:
        expected_trace_rows = _req_029_build_trace_rows(
            synthesis_call_id=_as_text(metadata.get("processing_call_id")),
            call_chain=normalized_call_chain,
            recommendation_ids=[_as_text(row.get("recommendation_id")) for row in recommendation_drafts if isinstance(row, Mapping)],
        )
        if llm_call_trace_rows != expected_trace_rows:
            errors.append("call_metadata.llm_call_trace_rows must mirror deterministic trace rows")
        if metadata.get("llm_call_trace_sha256") != _canonical_digest(expected_trace_rows):
            errors.append("call_metadata.llm_call_trace_sha256 does not match llm_call_trace_rows")

    return errors


def _req_034_handoff_ref(*, output_ref: str) -> str:
    return f"{output_ref}::memory_handoff"


def _req_034_contract_output_ref(*, call_id: str) -> str:
    return f"{REQ_034_REQUIREMENT_ID}::call::{call_id}::output::memory_handoff_contract"


def _req_034_normalize_memory_items(
    value: Any,
    *,
    field_name: str,
) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise Req034Error(f"{field_name} must be an array")

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_row in enumerate(value):
        row = _require_mapping(raw_row, field_name=f"{field_name}[{index}]")
        memory_id = _require_text(row.get("memory_id"), field_name=f"{field_name}[{index}].memory_id")
        if not REQ_034_MEMORY_ID_RE.match(memory_id):
            raise Req034Error(
                f"{field_name}[{index}].memory_id must match {REQ_034_MEMORY_ID_RE.pattern}"
            )
        if memory_id in seen_ids:
            raise Req034Error(f"{field_name}[{index}].memory_id must be unique within a handoff")
        seen_ids.add(memory_id)
        project_scope = _require_text(
            row.get("project_scope"),
            field_name=f"{field_name}[{index}].project_scope",
        ).lower()
        if project_scope not in REQ_034_ALLOWED_MEMORY_SCOPES:
            raise Req034Error(
                f"{field_name}[{index}].project_scope must be one of {sorted(REQ_034_ALLOWED_MEMORY_SCOPES)}"
            )
        project_id = _as_text(row.get("project_id"))
        if project_scope == "cross-project":
            project_id = _require_text(project_id, field_name=f"{field_name}[{index}].project_id")
        else:
            project_id = ""
        normalized.append(
            {
                "memory_id": memory_id,
                "summary": _require_text(row.get("summary"), field_name=f"{field_name}[{index}].summary"),
                "category": _require_text(row.get("category"), field_name=f"{field_name}[{index}].category"),
                "position": _require_text(row.get("position"), field_name=f"{field_name}[{index}].position"),
                "project_scope": project_scope,
                "project_id": project_id,
                "citation_refs": _normalize_string_list(
                    row.get("citation_refs"),
                    field_name=f"{field_name}[{index}].citation_refs",
                    min_items=1,
                ),
            }
        )
    normalized.sort(key=lambda row: (row["memory_id"], row["position"], row["summary"], row["project_id"]))
    return normalized


def _req_034_normalize_prior_call_handoffs(
    value: Any,
    *,
    field_name: str = "prior_call_handoffs",
) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise Req034Error(f"{field_name} must be an array")

    normalized: list[dict[str, Any]] = []
    seen_sequences: set[int] = set()
    seen_call_ids: set[str] = set()
    for index, raw_row in enumerate(value):
        row = _require_mapping(raw_row, field_name=f"{field_name}[{index}]")
        sequence = row.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int):
            raise Req034Error(f"{field_name}[{index}].sequence must be an integer")
        if sequence < 1:
            raise Req034Error(f"{field_name}[{index}].sequence must be >= 1")
        if sequence in seen_sequences:
            raise Req034Error(f"{field_name}[{index}].sequence must be unique")
        seen_sequences.add(sequence)
        call_id = _require_text(row.get("call_id"), field_name=f"{field_name}[{index}].call_id")
        if call_id in seen_call_ids:
            raise Req034Error(f"{field_name}[{index}].call_id must be unique")
        seen_call_ids.add(call_id)
        normalized.append(
            {
                "sequence": sequence,
                "call_id": call_id,
                "phase": _require_text(row.get("phase"), field_name=f"{field_name}[{index}].phase"),
                "output_ref": _require_text(row.get("output_ref"), field_name=f"{field_name}[{index}].output_ref"),
                "memory_items": _req_034_normalize_memory_items(
                    row.get("memory_items"),
                    field_name=f"{field_name}[{index}].memory_items",
                ),
            }
        )

    normalized.sort(key=lambda row: row["sequence"])
    expected_sequences = list(range(1, len(normalized) + 1))
    if [row["sequence"] for row in normalized] != expected_sequences:
        raise Req034Error(f"{field_name}.sequence must be contiguous starting at 1")
    if len(normalized) < 2:
        raise Req034Error(f"{field_name} must include at least 2 prior calls")
    return normalized


def _req_034_normalize_candidate_recommendations(
    value: Any,
    *,
    field_name: str = "candidate_recommendations",
) -> list[dict[str, Any]]:
    if value is None:
        rows: Sequence[Any] = []
    else:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            raise Req034Error(f"{field_name} must be an array")
        rows = value

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_row in enumerate(rows):
        row = _require_mapping(raw_row, field_name=f"{field_name}[{index}]")
        recommendation_id = _req_029_recommendation_id_from_candidate(row, index=index)
        if recommendation_id in seen_ids:
            raise Req034Error(f"{field_name}[{index}].recommendation_id must be unique")
        seen_ids.add(recommendation_id)
        recommendation_scope = _require_text(
            row.get("recommendation_scope"),
            field_name=f"{field_name}[{index}].recommendation_scope",
        ).lower()
        if recommendation_scope not in REQ_029_ALLOWED_RECOMMENDATION_SCOPES:
            raise Req034Error(
                f"{field_name}[{index}].recommendation_scope must be one of {sorted(REQ_029_ALLOWED_RECOMMENDATION_SCOPES)}"
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
            raise Req034Error(f"{field_name}[{index}].requires_earth_evidence must be a boolean")
        synthesized_from_call_sequence = row.get("synthesized_from_call_sequence")
        if isinstance(synthesized_from_call_sequence, bool) or not isinstance(synthesized_from_call_sequence, int):
            raise Req034Error(f"{field_name}[{index}].synthesized_from_call_sequence must be an integer")
        memory_anchor_ids = _normalize_string_list(
            row.get("memory_anchor_ids"),
            field_name=f"{field_name}[{index}].memory_anchor_ids",
            min_items=1,
        )
        for memory_id in memory_anchor_ids:
            if not REQ_034_MEMORY_ID_RE.match(memory_id):
                raise Req034Error(
                    f"{field_name}[{index}].memory_anchor_ids entries must match {REQ_034_MEMORY_ID_RE.pattern}"
                )
        normalized.append(
            {
                "recommendation_id": recommendation_id,
                "summary": _require_text(row.get("summary"), field_name=f"{field_name}[{index}].summary"),
                "rationale": _require_text(row.get("rationale"), field_name=f"{field_name}[{index}].rationale"),
                "recommendation_scope": recommendation_scope,
                "project_id": project_id,
                "requires_earth_evidence": requires_earth_evidence,
                "evidence_refs": _normalize_string_list(
                    row.get("evidence_refs"),
                    field_name=f"{field_name}[{index}].evidence_refs",
                    min_items=1,
                ),
                "next_step": _require_text(row.get("next_step"), field_name=f"{field_name}[{index}].next_step"),
                "synthesized_from_call_sequence": synthesized_from_call_sequence,
                "memory_anchor_ids": memory_anchor_ids,
            }
        )
    normalized.sort(key=lambda row: row["recommendation_id"])
    return normalized


def _req_034_canonical_input(
    *,
    target_project_root: str,
    earth_root: str,
    output_root: str,
    revision_identity: str,
    strategy_goal: str,
    call_id: str,
    checked_at_utc: str,
) -> dict[str, Any]:
    return {
        "runtime_mode": RUNTIME_MODE,
        "execution_mode": EXECUTION_MODE,
        "target_project_root": target_project_root,
        "earth_root": earth_root,
        "output_root": output_root,
        "revision_identity": revision_identity,
        "strategy_goal": strategy_goal,
        "analysis_type": REQ_034_ANALYSIS_TYPE,
        "call_id": call_id,
        "checked_at_utc": checked_at_utc,
    }


_req034_legacy_canonical_input = _req_034_canonical_input


def _req_034_canonical_processing_input(
    *,
    prior_call_handoffs: Sequence[Mapping[str, Any]],
    target_project_evidence_refs: Sequence[str],
    earth_sweep_evidence_refs: Sequence[str],
    cross_project_context: Sequence[Mapping[str, Any]],
    candidate_recommendations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "prior_call_handoffs": [dict(row) for row in prior_call_handoffs],
        "target_project_evidence_refs": list(target_project_evidence_refs),
        "earth_sweep_evidence_refs": list(earth_sweep_evidence_refs),
        "cross_project_context": [dict(row) for row in cross_project_context],
        "candidate_recommendations": [dict(row) for row in candidate_recommendations],
    }


def _req_034_build_trace_rows(
    *,
    processing_call_id: str,
    call_id: str,
    prior_call_handoffs: Sequence[Mapping[str, Any]],
    target_project_evidence_refs: Sequence[str],
    earth_sweep_evidence_refs: Sequence[str],
    cross_project_context: Sequence[Mapping[str, Any]],
    candidate_recommendations: Sequence[Mapping[str, Any]],
    active_memory_count: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    prior_handoff_refs: list[str] = []
    cross_project_refs = _collect_unique_refs(*[row["evidence_refs"] for row in cross_project_context])
    for row in prior_call_handoffs:
        output_ref = str(row["output_ref"])
        handoff_ref = _req_034_handoff_ref(output_ref=output_ref)
        rows.append(
            {
                "schema_version": REQ_034_LLM_CALL_TRACE_SCHEMA_VERSION,
                "requirement_id": REQ_034_REQUIREMENT_ID,
                "processing_call_id": processing_call_id,
                "call_id": str(row["call_id"]),
                "sequence": int(row["sequence"]),
                "call_objective": str(row["phase"]),
                "input_refs": list(prior_handoff_refs),
                "output_refs": [output_ref, handoff_ref],
                "handoff_summary": (
                    f"Call {int(row['sequence'])} hands off "
                    f"{min(len(row['memory_items']), REQ_034_MAX_MEMORY_ITEMS_PER_CALL)} bounded memory item(s) "
                    f"via {handoff_ref}."
                ),
            }
        )
        prior_handoff_refs.append(handoff_ref)

    final_sequence = len(prior_call_handoffs) + 1
    final_output_ref = _req_034_contract_output_ref(call_id=call_id)
    final_input_refs = _dedupe_preserving_order(
        prior_handoff_refs
        + list(target_project_evidence_refs)
        + list(earth_sweep_evidence_refs)
        + list(cross_project_refs)
        + [ref for row in candidate_recommendations for ref in row["evidence_refs"]]
    )
    rows.append(
        {
            "schema_version": REQ_034_LLM_CALL_TRACE_SCHEMA_VERSION,
            "requirement_id": REQ_034_REQUIREMENT_ID,
            "processing_call_id": processing_call_id,
            "call_id": call_id,
            "sequence": final_sequence,
            "call_objective": REQ_034_ANALYSIS_TYPE,
            "input_refs": final_input_refs,
            "output_refs": [final_output_ref],
            "handoff_summary": (
                f"Call {final_sequence} emits memory_handoff_contract with {len(prior_call_handoffs)} "
                f"prior handoff(s) and {active_memory_count} active memory item(s)."
            ),
        }
    )
    return rows


def build_req_034_cross_call_memory_handoff_contract(
    *,
    target_project_root: str,
    earth_root: str,
    output_root: str,
    revision_identity: str,
    strategy_goal: str,
    prior_call_handoffs: Sequence[Mapping[str, Any]],
    candidate_recommendations: Sequence[Mapping[str, Any]],
    cross_project_context: Sequence[Mapping[str, Any]] | None = None,
    target_project_evidence_refs: Sequence[Any] | None = None,
    earth_sweep_evidence_refs: Sequence[Any] | None = None,
    call_id: str = "call-memory-handoff",
    checked_at_utc: str | None = None,
) -> dict[str, Any]:
    normalized_target_root = _normalize_root(target_project_root, field_name="target_project_root")
    normalized_earth_root = _normalize_root(earth_root, field_name="earth_root")
    normalized_output_root = _normalize_root(output_root, field_name="output_root")
    normalized_revision_identity = _require_text(revision_identity, field_name="revision_identity")
    normalized_strategy_goal = _require_text(strategy_goal, field_name="strategy_goal")
    normalized_call_id = _require_text(call_id, field_name="call_id")
    normalized_checked_at_utc = _require_text(checked_at_utc or utc_now_iso(), field_name="checked_at_utc")
    normalized_prior_call_handoffs = _req_034_normalize_prior_call_handoffs(prior_call_handoffs)
    normalized_candidate_recommendations = _req_034_normalize_candidate_recommendations(candidate_recommendations)
    normalized_cross_project_context = _normalize_cross_project_context(cross_project_context)
    normalized_target_refs = _normalize_string_list(
        target_project_evidence_refs,
        field_name="target_project_evidence_refs",
    )
    normalized_earth_refs = _normalize_string_list(
        earth_sweep_evidence_refs,
        field_name="earth_sweep_evidence_refs",
    )

    cross_project_refs = _collect_unique_refs(*[row["evidence_refs"] for row in normalized_cross_project_context])
    base_available_refs = set(
        _collect_unique_refs(
            normalized_target_refs,
            normalized_earth_refs,
            cross_project_refs,
            [row["output_ref"] for row in normalized_prior_call_handoffs],
        )
    )
    context_by_project = {str(row["project_id"]): row for row in normalized_cross_project_context}
    contract_output_ref = _req_034_contract_output_ref(call_id=normalized_call_id)

    open_risks: list[dict[str, Any]] = []
    memory_handoffs: list[dict[str, Any]] = []
    memory_rows_by_id: dict[str, list[dict[str, Any]]] = {}
    handoff_refs: list[str] = []

    for row in normalized_prior_call_handoffs:
        bounded_memory_items = list(row["memory_items"][:REQ_034_MAX_MEMORY_ITEMS_PER_CALL])
        handoff_ref = _req_034_handoff_ref(output_ref=str(row["output_ref"]))
        handoff_refs.append(handoff_ref)
        emitted_memory_items: list[dict[str, Any]] = []
        handoff_citation_refs = _collect_unique_refs(*[item["citation_refs"] for item in bounded_memory_items])
        for item in bounded_memory_items:
            supported = True
            uncited_refs = sorted(set(item["citation_refs"]) - base_available_refs)
            if uncited_refs:
                supported = False
                open_risks.append(
                    {
                        "risk_id": f"risk-{item['memory_id']}-citation",
                        "reason_code": "uncited_memory_claim",
                        "summary": item["summary"],
                        "required_evidence_refs": _collect_unique_refs([row["output_ref"]], uncited_refs),
                    }
                )
            if item["project_scope"] == "cross-project":
                if item["project_id"] not in context_by_project:
                    supported = False
                    open_risks.append(
                        {
                            "risk_id": f"risk-{item['memory_id']}-context",
                            "reason_code": "missing_cross_project_context",
                            "summary": item["summary"],
                            "required_evidence_refs": _collect_unique_refs([row["output_ref"]], item["citation_refs"]),
                        }
                    )
                if not any(_is_earth_evidence_ref(ref) for ref in item["citation_refs"]):
                    supported = False
                    open_risks.append(
                        {
                            "risk_id": f"risk-{item['memory_id']}-earth-evidence",
                            "reason_code": "missing_earth_sweep_evidence_refs",
                            "summary": item["summary"],
                            "required_evidence_refs": _collect_unique_refs([row["output_ref"]], item["citation_refs"]),
                        }
                    )
            emitted_memory_items.append(
                {
                    "memory_id": item["memory_id"],
                    "summary": item["summary"],
                    "category": item["category"],
                    "position": item["position"],
                    "project_scope": item["project_scope"],
                    "project_id": item["project_id"],
                    "citation_refs": list(item["citation_refs"]),
                    "supported": supported,
                }
            )
            memory_rows_by_id.setdefault(item["memory_id"], []).append(
                {
                    "memory_id": item["memory_id"],
                    "summary": item["summary"],
                    "position": item["position"],
                    "project_scope": item["project_scope"],
                    "project_id": item["project_id"],
                    "citation_refs": list(item["citation_refs"]),
                    "source_call_sequence": int(row["sequence"]),
                    "source_call_id": str(row["call_id"]),
                    "source_output_ref": str(row["output_ref"]),
                    "handoff_ref": handoff_ref,
                    "supported": supported,
                }
            )
        memory_handoffs.append(
            {
                "source_call_sequence": int(row["sequence"]),
                "source_call_id": str(row["call_id"]),
                "phase": str(row["phase"]),
                "source_output_ref": str(row["output_ref"]),
                "handoff_ref": handoff_ref,
                "bounded_item_count": len(bounded_memory_items),
                "truncated_item_count": max(0, len(row["memory_items"]) - len(bounded_memory_items)),
                "citation_refs": handoff_citation_refs,
                "memory_items": emitted_memory_items,
            }
        )

    suppressed_memory_ids: set[str] = set()
    active_memory_by_id: dict[str, dict[str, Any]] = {}
    for memory_id, rows in memory_rows_by_id.items():
        supported_rows = [row for row in rows if row["supported"]]
        if not supported_rows:
            suppressed_memory_ids.add(memory_id)
            continue
        supported_rows.sort(key=lambda row: row["source_call_sequence"])
        if len({str(row["position"]) for row in supported_rows}) > 1:
            suppressed_memory_ids.add(memory_id)
            open_risks.append(
                {
                    "risk_id": f"risk-{memory_id}-contradiction",
                    "reason_code": "cross_call_contradiction",
                    "summary": supported_rows[-1]["summary"],
                    "required_evidence_refs": _collect_unique_refs(
                        [row["source_output_ref"] for row in supported_rows],
                        *[row["citation_refs"] for row in supported_rows],
                    ),
                }
            )
            continue
        active_memory_by_id[memory_id] = supported_rows[-1]

    recommended_actions: list[dict[str, Any]] = []
    cross_project_obligations: list[dict[str, Any]] = []
    blocked_recommendation_ids: set[str] = set()
    available_recommendation_refs = set(
        _collect_unique_refs(
            normalized_target_refs,
            normalized_earth_refs,
            cross_project_refs,
            [row["output_ref"] for row in normalized_prior_call_handoffs],
            handoff_refs,
            *[row["citation_refs"] for row in active_memory_by_id.values()],
        )
    )
    for row in normalized_candidate_recommendations:
        recommendation_id = str(row["recommendation_id"])
        blocked_reason_code = ""
        missing_anchor_ids = [memory_id for memory_id in row["memory_anchor_ids"] if memory_id not in active_memory_by_id]
        contradicted_anchor_ids = [memory_id for memory_id in row["memory_anchor_ids"] if memory_id in suppressed_memory_ids]
        active_anchor_rows = [
            active_memory_by_id[memory_id]
            for memory_id in row["memory_anchor_ids"]
            if memory_id in active_memory_by_id
        ]
        all_anchor_rows = [
            anchor_row
            for memory_id in row["memory_anchor_ids"]
            for anchor_row in memory_rows_by_id.get(memory_id, [])
        ]
        blocked_anchor_evidence_refs = _collect_unique_refs(
            *[
                anchor_row["citation_refs"]
                for anchor_row in all_anchor_rows
            ]
        )
        blocked_anchor_output_refs = _collect_unique_refs(
            [anchor_row["source_output_ref"] for anchor_row in all_anchor_rows]
        )
        anchor_evidence_refs = _collect_unique_refs(*[anchor_row["citation_refs"] for anchor_row in active_anchor_rows])
        anchor_output_refs = _collect_unique_refs([anchor_row["source_output_ref"] for anchor_row in active_anchor_rows])
        uncited_refs = sorted(set(row["evidence_refs"]) - available_recommendation_refs)
        if contradicted_anchor_ids:
            blocked_reason_code = "cross_call_contradiction"
        elif missing_anchor_ids:
            blocked_reason_code = "missing_memory_handoff"
        elif uncited_refs:
            blocked_reason_code = "uncited_strategic_claim"
        elif row["recommendation_scope"] == "cross-project" and row["requires_earth_evidence"] and not normalized_earth_refs:
            blocked_reason_code = "missing_earth_sweep_evidence_refs"
        elif row["recommendation_scope"] == "cross-project" and row["project_id"] not in context_by_project:
            blocked_reason_code = "missing_cross_project_context"

        if blocked_reason_code:
            blocked_recommendation_ids.add(recommendation_id)
            required_refs = _collect_unique_refs(
                [contract_output_ref],
                blocked_anchor_output_refs,
                row["evidence_refs"],
                blocked_anchor_evidence_refs,
            )
            if uncited_refs:
                required_refs = _collect_unique_refs([contract_output_ref], blocked_anchor_output_refs, uncited_refs)
            open_risks.append(
                {
                    "risk_id": f"risk-{recommendation_id}",
                    "reason_code": blocked_reason_code,
                    "summary": row["summary"],
                    "required_evidence_refs": required_refs,
                }
            )
            continue

        action = {
            "recommendation_id": recommendation_id,
            "summary": str(row["summary"]),
            "rationale": str(row["rationale"]),
            "next_step": str(row["next_step"]),
            "memory_anchor_ids": list(row["memory_anchor_ids"]),
            "source_output_refs": anchor_output_refs,
            "evidence_refs": _collect_unique_refs(anchor_output_refs, row["evidence_refs"], anchor_evidence_refs),
        }
        if row["recommendation_scope"] == "cross-project":
            project_context = context_by_project[str(row["project_id"])]
            cross_project_obligations.append(
                {
                    "obligation_id": f"obligation-{recommendation_id}",
                    "project_id": str(row["project_id"]),
                    **action,
                    "evidence_refs": _collect_unique_refs(
                        action["evidence_refs"],
                        project_context["evidence_refs"],
                        normalized_earth_refs,
                    ),
                }
            )
            continue
        recommended_actions.append(action)

    recommended_actions.sort(key=lambda row: row["recommendation_id"])
    cross_project_obligations.sort(key=lambda row: row["obligation_id"])
    memory_handoffs.sort(key=lambda row: (row["source_call_sequence"], row["source_call_id"]))
    open_risks.sort(key=lambda row: row["risk_id"])
    active_memory_ids = sorted(active_memory_by_id)

    recommendation_refs = _collect_unique_refs(
        normalized_target_refs,
        normalized_earth_refs,
        cross_project_refs,
        [row["output_ref"] for row in normalized_prior_call_handoffs],
        handoff_refs,
        *[row["citation_refs"] for row in active_memory_by_id.values()],
        *[row["evidence_refs"] for row in recommended_actions],
        *[row["evidence_refs"] for row in cross_project_obligations],
        *[row["required_evidence_refs"] for row in open_risks],
    )
    promoted_actions: list[dict[str, Any]] = list(recommended_actions) + list(cross_project_obligations)
    decision = _recommendation_decision(recommended_actions=promoted_actions, open_risks=open_risks)
    rationale = (
        f"handoffs={len(memory_handoffs)} active_memory={len(active_memory_ids)} "
        f"local={len(recommended_actions)} obligations={len(cross_project_obligations)} "
        f"open_risks={len(open_risks)}"
    )
    confidence = _recommendation_confidence(evidence_refs=recommendation_refs, open_risks=open_risks)

    canonical_input = _req034_legacy_canonical_input(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        output_root=normalized_output_root,
        revision_identity=normalized_revision_identity,
        strategy_goal=normalized_strategy_goal,
        call_id=normalized_call_id,
        checked_at_utc=normalized_checked_at_utc,
    )
    canonical_processing_input = _req_034_canonical_processing_input(
        prior_call_handoffs=normalized_prior_call_handoffs,
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        cross_project_context=normalized_cross_project_context,
        candidate_recommendations=normalized_candidate_recommendations,
    )
    processing_sha = _canonical_digest(canonical_processing_input)
    processing_call_id = f"req034-processing-{processing_sha[:16]}"
    llm_call_trace_rows = _req_034_build_trace_rows(
        processing_call_id=processing_call_id,
        call_id=normalized_call_id,
        prior_call_handoffs=normalized_prior_call_handoffs,
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        cross_project_context=normalized_cross_project_context,
        candidate_recommendations=normalized_candidate_recommendations,
        active_memory_count=len(active_memory_ids),
    )

    return {
        "schema_version": REQ_034_SCHEMA_VERSION,
        "requirement_id": REQ_034_REQUIREMENT_ID,
        "analysis_type": REQ_034_ANALYSIS_TYPE,
        "call_id": normalized_call_id,
        "checked_at_utc": normalized_checked_at_utc,
        "processing_behavior": {
            "strategy": REQ_034_PROCESSING_STRATEGY,
            "reasoning_mode": REQ_034_REASONING_MODE,
            "bounded_context": True,
            "context_inputs": {
                "target_project": {
                    "project_root": normalized_target_root,
                    "evidence_refs": list(normalized_target_refs),
                },
                "earth_sweep": {
                    "earth_root": normalized_earth_root,
                    "evidence_refs": list(normalized_earth_refs),
                },
                "prior_call_handoffs": [dict(row) for row in normalized_prior_call_handoffs],
                "cross_project_context": [dict(row) for row in normalized_cross_project_context],
                "candidate_recommendations": [dict(row) for row in normalized_candidate_recommendations],
            },
            "context_usage": {
                "prior_call_handoffs_used": bool(normalized_prior_call_handoffs),
                "bounded_context_used": True,
                "earth_sweep_context_used": bool(normalized_earth_refs),
                "cross_project_context_used": bool(normalized_cross_project_context),
                "prior_call_ids_considered": [str(row["call_id"]) for row in normalized_prior_call_handoffs],
                "handoff_refs_emitted": list(handoff_refs),
                "cross_project_projects_considered": sorted(
                    {str(row["project_id"]) for row in normalized_cross_project_context}
                ),
                "candidate_recommendation_ids_considered": [
                    str(row["recommendation_id"]) for row in normalized_candidate_recommendations
                ],
                "active_memory_ids": active_memory_ids,
                "suppressed_memory_ids": sorted(suppressed_memory_ids),
                "recommended_action_ids_emitted": [
                    str(row["recommendation_id"]) for row in recommended_actions
                ],
                "cross_project_obligation_ids_emitted": [
                    str(row["obligation_id"]) for row in cross_project_obligations
                ],
                "open_risk_ids_emitted": [str(row["risk_id"]) for row in open_risks],
                "evidence_refs_used": list(recommendation_refs),
            },
            "handoff_contract": {
                "memory_window_per_call": REQ_034_MAX_MEMORY_ITEMS_PER_CALL,
                "contract_output_ref": contract_output_ref,
                "active_memory_ids": active_memory_ids,
                "suppressed_memory_ids": sorted(suppressed_memory_ids),
                "handoff_count": len(memory_handoffs),
            },
            "recommendation": {
                "decision": decision,
                "rationale": rationale,
                "confidence": confidence,
                "evidence_refs": list(recommendation_refs),
                "memory_handoffs": memory_handoffs,
                "recommended_actions": recommended_actions,
                "cross_project_obligations": cross_project_obligations,
                "open_risks": open_risks,
            },
        },
        "call_metadata": {
            "reproducibility": "deterministic-input-fingerprint",
            "canonical_input": canonical_input,
            "canonical_input_sha256": _canonical_digest(canonical_input),
            "reproducible_call_id": f"req034-{_canonical_digest(canonical_input)[:16]}",
            "canonical_processing_input": canonical_processing_input,
            "processing_input_sha256": processing_sha,
            "processing_call_id": processing_call_id,
            "llm_call_trace_schema_version": REQ_034_LLM_CALL_TRACE_SCHEMA_VERSION,
            "llm_call_trace_path": LLM_CALL_TRACE_RELATIVE_PATH,
            "llm_call_trace_sha256": _canonical_digest(llm_call_trace_rows),
            "llm_call_trace_rows": llm_call_trace_rows,
        },
    }


def validate_req_034_cross_call_memory_handoff_contract(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    if payload.get("schema_version") != REQ_034_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_034_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_034_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_034_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_034_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_034_ANALYSIS_TYPE}")
    if not _as_text(payload.get("call_id")):
        errors.append("call_id is required")
    if not _as_text(payload.get("checked_at_utc")):
        errors.append("checked_at_utc is required")

    processing_behavior = payload.get("processing_behavior")
    if not isinstance(processing_behavior, Mapping):
        return errors + ["processing_behavior must be an object"]
    if processing_behavior.get("strategy") != REQ_034_PROCESSING_STRATEGY:
        errors.append(f"processing_behavior.strategy must be {REQ_034_PROCESSING_STRATEGY}")
    if processing_behavior.get("reasoning_mode") != REQ_034_REASONING_MODE:
        errors.append(f"processing_behavior.reasoning_mode must be {REQ_034_REASONING_MODE}")
    if processing_behavior.get("bounded_context") is not True:
        errors.append("processing_behavior.bounded_context must be true")

    context_inputs = processing_behavior.get("context_inputs")
    normalized_prior_call_handoffs: list[dict[str, Any]] = []
    normalized_target_refs: list[str] = []
    normalized_earth_refs: list[str] = []
    normalized_cross_project_context: list[dict[str, Any]] = []
    normalized_candidate_recommendations: list[dict[str, Any]] = []
    if not isinstance(context_inputs, Mapping):
        return errors + ["processing_behavior.context_inputs must be an object"]
    target_project = context_inputs.get("target_project")
    if not isinstance(target_project, Mapping):
        errors.append("processing_behavior.context_inputs.target_project must be an object")
    else:
        normalized_target_refs = sorted(
            {_as_text(ref) for ref in target_project.get("evidence_refs", []) if _as_text(ref)}
        )
    earth_sweep = context_inputs.get("earth_sweep")
    if not isinstance(earth_sweep, Mapping):
        errors.append("processing_behavior.context_inputs.earth_sweep must be an object")
    else:
        normalized_earth_refs = sorted(
            {_as_text(ref) for ref in earth_sweep.get("evidence_refs", []) if _as_text(ref)}
        )
    try:
        normalized_prior_call_handoffs = _req_034_normalize_prior_call_handoffs(context_inputs.get("prior_call_handoffs"))
    except Req034Error as exc:
        errors.append(str(exc))
    try:
        normalized_cross_project_context = _normalize_cross_project_context(context_inputs.get("cross_project_context"))
    except ValueError as exc:
        errors.append(str(exc))
    try:
        normalized_candidate_recommendations = _req_034_normalize_candidate_recommendations(
            context_inputs.get("candidate_recommendations")
        )
    except Req034Error as exc:
        errors.append(str(exc))

    context_usage = processing_behavior.get("context_usage")
    if not isinstance(context_usage, Mapping):
        errors.append("processing_behavior.context_usage must be an object")
    else:
        for key in (
            "prior_call_handoffs_used",
            "bounded_context_used",
            "earth_sweep_context_used",
            "cross_project_context_used",
        ):
            if not isinstance(context_usage.get(key), bool):
                errors.append(f"processing_behavior.context_usage.{key} must be a boolean")
        for key in (
            "prior_call_ids_considered",
            "handoff_refs_emitted",
            "cross_project_projects_considered",
            "candidate_recommendation_ids_considered",
            "active_memory_ids",
            "suppressed_memory_ids",
            "recommended_action_ids_emitted",
            "cross_project_obligation_ids_emitted",
            "open_risk_ids_emitted",
            "evidence_refs_used",
        ):
            value = context_usage.get(key)
            if not isinstance(value, list) or any(not _as_text(item) for item in value):
                errors.append(f"processing_behavior.context_usage.{key} must be a string array")

    handoff_contract = processing_behavior.get("handoff_contract")
    if not isinstance(handoff_contract, Mapping):
        errors.append("processing_behavior.handoff_contract must be an object")
    else:
        if handoff_contract.get("memory_window_per_call") != REQ_034_MAX_MEMORY_ITEMS_PER_CALL:
            errors.append(
                f"processing_behavior.handoff_contract.memory_window_per_call must be {REQ_034_MAX_MEMORY_ITEMS_PER_CALL}"
            )
        if not _as_text(handoff_contract.get("contract_output_ref")):
            errors.append("processing_behavior.handoff_contract.contract_output_ref is required")

    recommendation = processing_behavior.get("recommendation")
    if not isinstance(recommendation, Mapping):
        return errors + ["processing_behavior.recommendation must be an object"]
    required_recommendation_keys = {
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "memory_handoffs",
        "recommended_actions",
        "cross_project_obligations",
        "open_risks",
    }
    missing_recommendation_keys = sorted(required_recommendation_keys - set(recommendation.keys()))
    if missing_recommendation_keys:
        errors.append(f"processing_behavior.recommendation missing keys: {missing_recommendation_keys}")
    if not isinstance(recommendation.get("evidence_refs"), list) or not recommendation.get("evidence_refs"):
        errors.append("processing_behavior.recommendation.evidence_refs must be a non-empty list")
    for key in ("memory_handoffs", "recommended_actions", "cross_project_obligations", "open_risks"):
        if not isinstance(recommendation.get(key), list):
            errors.append(f"processing_behavior.recommendation.{key} must be a list")

    metadata = payload.get("call_metadata")
    if not isinstance(metadata, Mapping):
        return errors + ["call_metadata must be an object"]
    if metadata.get("reproducibility") != "deterministic-input-fingerprint":
        errors.append("call_metadata.reproducibility must be deterministic-input-fingerprint")

    canonical_input = metadata.get("canonical_input")
    if not isinstance(canonical_input, Mapping):
        errors.append("call_metadata.canonical_input must be an object")
    else:
        expected_canonical_input = _req034_legacy_canonical_input(
            target_project_root=_as_text(target_project.get("project_root")) if isinstance(target_project, Mapping) else "",
            earth_root=_as_text(earth_sweep.get("earth_root")) if isinstance(earth_sweep, Mapping) else "",
            output_root=_as_text(canonical_input.get("output_root")),
            revision_identity=_as_text(canonical_input.get("revision_identity")),
            strategy_goal=_as_text(canonical_input.get("strategy_goal")),
            call_id=_as_text(payload.get("call_id")),
            checked_at_utc=_as_text(payload.get("checked_at_utc")),
        )
        if dict(canonical_input) != expected_canonical_input:
            errors.append("call_metadata.canonical_input must mirror normalized invocation anchors")
        expected_input_sha = _canonical_digest(expected_canonical_input)
        if metadata.get("canonical_input_sha256") != expected_input_sha:
            errors.append("call_metadata.canonical_input_sha256 does not match canonical input")
        if metadata.get("reproducible_call_id") != f"req034-{expected_input_sha[:16]}":
            errors.append("call_metadata.reproducible_call_id does not match canonical digest")

    canonical_processing_input = metadata.get("canonical_processing_input")
    if not isinstance(canonical_processing_input, Mapping):
        errors.append("call_metadata.canonical_processing_input must be an object")
    else:
        expected_processing_input = _req_034_canonical_processing_input(
            prior_call_handoffs=normalized_prior_call_handoffs,
            target_project_evidence_refs=normalized_target_refs,
            earth_sweep_evidence_refs=normalized_earth_refs,
            cross_project_context=normalized_cross_project_context,
            candidate_recommendations=normalized_candidate_recommendations,
        )
        if dict(canonical_processing_input) != expected_processing_input:
            errors.append("call_metadata.canonical_processing_input must mirror normalized handoff inputs")
        expected_processing_sha = _canonical_digest(expected_processing_input)
        if metadata.get("processing_input_sha256") != expected_processing_sha:
            errors.append("call_metadata.processing_input_sha256 does not match processing input")
        if metadata.get("processing_call_id") != f"req034-processing-{expected_processing_sha[:16]}":
            errors.append("call_metadata.processing_call_id does not match processing digest")

    if metadata.get("llm_call_trace_schema_version") != REQ_034_LLM_CALL_TRACE_SCHEMA_VERSION:
        errors.append(
            f"call_metadata.llm_call_trace_schema_version must be {REQ_034_LLM_CALL_TRACE_SCHEMA_VERSION}"
        )
    if metadata.get("llm_call_trace_path") != LLM_CALL_TRACE_RELATIVE_PATH:
        errors.append(f"call_metadata.llm_call_trace_path must be {LLM_CALL_TRACE_RELATIVE_PATH}")
    llm_call_trace_rows = metadata.get("llm_call_trace_rows")
    if not isinstance(llm_call_trace_rows, list):
        errors.append("call_metadata.llm_call_trace_rows must be a list")
    else:
        expected_trace_rows = _req_034_build_trace_rows(
            processing_call_id=_as_text(metadata.get("processing_call_id")),
            call_id=_as_text(payload.get("call_id")),
            prior_call_handoffs=normalized_prior_call_handoffs,
            target_project_evidence_refs=normalized_target_refs,
            earth_sweep_evidence_refs=normalized_earth_refs,
            cross_project_context=normalized_cross_project_context,
            candidate_recommendations=normalized_candidate_recommendations,
            active_memory_count=len(context_usage.get("active_memory_ids", []))
            if isinstance(context_usage, Mapping) and isinstance(context_usage.get("active_memory_ids"), list)
            else 0,
        )
        if llm_call_trace_rows != expected_trace_rows:
            errors.append("call_metadata.llm_call_trace_rows must mirror deterministic trace rows")
        if metadata.get("llm_call_trace_sha256") != _canonical_digest(expected_trace_rows):
            errors.append("call_metadata.llm_call_trace_sha256 does not match llm_call_trace_rows")

    return errors


def _req_030_normalize_call_chain(
    value: Any,
    *,
    field_name: str = "call_chain",
) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise Req030Error(f"{field_name} must be an array")

    normalized: list[dict[str, Any]] = []
    seen_sequences: set[int] = set()
    seen_call_ids: set[str] = set()
    for index, raw_row in enumerate(value):
        row = _require_mapping(raw_row, field_name=f"{field_name}[{index}]")
        sequence = row.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int):
            raise Req030Error(f"{field_name}[{index}].sequence must be an integer")
        if sequence < 1:
            raise Req030Error(f"{field_name}[{index}].sequence must be >= 1")
        if sequence in seen_sequences:
            raise Req030Error(f"{field_name}[{index}].sequence must be unique")
        seen_sequences.add(sequence)

        call_id = _require_text(row.get("call_id"), field_name=f"{field_name}[{index}].call_id")
        if call_id in seen_call_ids:
            raise Req030Error(f"{field_name}[{index}].call_id must be unique")
        seen_call_ids.add(call_id)

        normalized.append(
            {
                "sequence": sequence,
                "call_id": call_id,
                "phase": _require_text(row.get("phase"), field_name=f"{field_name}[{index}].phase"),
                "output_ref": _require_text(row.get("output_ref"), field_name=f"{field_name}[{index}].output_ref"),
            }
        )

    normalized.sort(key=lambda row: row["sequence"])
    expected_sequences = list(range(1, len(normalized) + 1))
    actual_sequences = [row["sequence"] for row in normalized]
    if actual_sequences != expected_sequences:
        raise Req030Error(f"{field_name}.sequence must be contiguous starting at 1")
    if len(normalized) < 5:
        raise Req030Error(f"{field_name} must include at least 5 calls for Call-5 sequencing")
    return normalized


def _req_030_lane_id_from_candidate(row: Mapping[str, Any], *, index: int) -> str:
    provided = _as_text(row.get("lane_id"))
    if provided:
        if not REQ_030_LANE_ID_RE.match(provided):
            raise Req030Error(
                f"candidate_lane_designs[{index}].lane_id must match {REQ_030_LANE_ID_RE.pattern}"
            )
        return provided

    summary = _require_text(row.get("summary"), field_name=f"candidate_lane_designs[{index}].summary")
    return f"lane.{_req_029_slugify(summary)}"


def _req_030_recommendation_id_from_candidate(row: Mapping[str, Any], *, index: int) -> str:
    recommendation_id = _require_text(
        row.get("recommendation_id"),
        field_name=f"candidate_lane_designs[{index}].recommendation_id",
    )
    if not REQ_030_RECOMMENDATION_ID_RE.match(recommendation_id):
        raise Req030Error(
            f"candidate_lane_designs[{index}].recommendation_id must match {REQ_030_RECOMMENDATION_ID_RE.pattern}"
        )
    return recommendation_id


def _req_030_normalize_candidate_lane_designs(
    value: Any,
    *,
    field_name: str = "candidate_lane_designs",
) -> list[dict[str, Any]]:
    if value is None:
        rows: Sequence[Any] = []
    else:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            raise Req030Error(f"{field_name} must be an array")
        rows = value

    normalized: list[dict[str, Any]] = []
    seen_lane_ids: set[str] = set()
    for index, raw_row in enumerate(rows):
        row = _require_mapping(raw_row, field_name=f"{field_name}[{index}]")
        lane_id = _req_030_lane_id_from_candidate(row, index=index)
        if lane_id in seen_lane_ids:
            raise Req030Error(f"{field_name}[{index}].lane_id must be unique")
        seen_lane_ids.add(lane_id)

        recommendation_id = _req_030_recommendation_id_from_candidate(row, index=index)
        lane_scope = _require_text(row.get("lane_scope"), field_name=f"{field_name}[{index}].lane_scope").lower()
        if lane_scope not in REQ_030_ALLOWED_LANE_SCOPES:
            raise Req030Error(f"{field_name}[{index}].lane_scope must be one of {sorted(REQ_030_ALLOWED_LANE_SCOPES)}")

        project_id = _as_text(row.get("project_id"))
        if lane_scope == "cross-project":
            project_id = _require_text(project_id, field_name=f"{field_name}[{index}].project_id")
        else:
            project_id = ""

        requires_earth_evidence = row.get("requires_earth_evidence")
        if requires_earth_evidence is None:
            requires_earth_evidence = lane_scope == "cross-project"
        if not isinstance(requires_earth_evidence, bool):
            raise Req030Error(f"{field_name}[{index}].requires_earth_evidence must be a boolean")

        synthesized_from_call_sequence = row.get("synthesized_from_call_sequence")
        if isinstance(synthesized_from_call_sequence, bool) or not isinstance(synthesized_from_call_sequence, int):
            raise Req030Error(f"{field_name}[{index}].synthesized_from_call_sequence must be an integer")

        lane_order = row.get("lane_order")
        if isinstance(lane_order, bool) or not isinstance(lane_order, int):
            raise Req030Error(f"{field_name}[{index}].lane_order must be an integer")
        if lane_order < 1:
            raise Req030Error(f"{field_name}[{index}].lane_order must be >= 1")

        normalized.append(
            {
                "lane_id": lane_id,
                "recommendation_id": recommendation_id,
                "summary": _require_text(row.get("summary"), field_name=f"{field_name}[{index}].summary"),
                "rationale": _require_text(row.get("rationale"), field_name=f"{field_name}[{index}].rationale"),
                "sequencing_rationale": _require_text(
                    row.get("sequencing_rationale"),
                    field_name=f"{field_name}[{index}].sequencing_rationale",
                ),
                "lane_order": lane_order,
                "lane_scope": lane_scope,
                "project_id": project_id,
                "requires_earth_evidence": requires_earth_evidence,
                "evidence_refs": _normalize_string_list(
                    row.get("evidence_refs"),
                    field_name=f"{field_name}[{index}].evidence_refs",
                    min_items=1,
                ),
                "next_step": _require_text(row.get("next_step"), field_name=f"{field_name}[{index}].next_step"),
                "synthesized_from_call_sequence": synthesized_from_call_sequence,
            }
        )

    normalized.sort(key=lambda row: (row["lane_order"], row["recommendation_id"], row["lane_id"]))
    return normalized


def _req_030_normalize_strategic_claims(
    value: Any,
    *,
    field_name: str = "strategic_claims",
    call_depth: int,
) -> list[dict[str, Any]]:
    if value is None:
        rows: Sequence[Any] = []
    else:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            raise Req030Error(f"{field_name} must be an array")
        rows = value

    normalized: list[dict[str, Any]] = []
    for index, raw_row in enumerate(rows):
        row = _require_mapping(raw_row, field_name=f"{field_name}[{index}]")
        source_call_sequence = row.get("source_call_sequence")
        if isinstance(source_call_sequence, bool) or not isinstance(source_call_sequence, int):
            raise Req030Error(f"{field_name}[{index}].source_call_sequence must be an integer")
        if source_call_sequence < 1 or source_call_sequence > call_depth:
            raise Req030Error(f"{field_name}[{index}].source_call_sequence must be between 1 and {call_depth}")
        normalized.append(
            {
                "claim_id": _require_text(row.get("claim_id"), field_name=f"{field_name}[{index}].claim_id"),
                "phase": _require_text(row.get("phase"), field_name=f"{field_name}[{index}].phase").lower(),
                "summary": _require_text(row.get("summary"), field_name=f"{field_name}[{index}].summary"),
                "position": _require_text(row.get("position"), field_name=f"{field_name}[{index}].position"),
                "source_call_sequence": source_call_sequence,
                "evidence_refs": _normalize_string_list(
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


def _req_030_build_trace_rows(
    *,
    synthesis_call_id: str,
    call_chain: Sequence[Mapping[str, Any]],
    recommendation_ids: Sequence[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    prior_output_refs: list[str] = []
    for row in call_chain:
        sequence = int(row["sequence"])
        call_id = str(row["call_id"])
        output_ref = str(row["output_ref"])
        rows.append(
            {
                "schema_version": REQ_030_LLM_CALL_TRACE_SCHEMA_VERSION,
                "requirement_id": REQ_030_REQUIREMENT_ID,
                "processing_call_id": synthesis_call_id,
                "call_id": call_id,
                "sequence": sequence,
                "call_objective": str(row["phase"]),
                "input_refs": list(prior_output_refs),
                "output_refs": [output_ref],
                "handoff_summary": (
                    f"Call {sequence} supplies {output_ref}."
                    if sequence < 5
                    else f"Call 5 emits lane_blueprints for {len(recommendation_ids)} recommendation(s)."
                ),
            }
        )
        prior_output_refs.append(output_ref)
    return rows


def _req_030_canonical_input(
    *,
    target_project_root: str,
    earth_root: str,
    output_root: str,
    revision_identity: str,
    strategy_goal: str,
    call_id: str,
    checked_at_utc: str,
) -> dict[str, Any]:
    return {
        "runtime_mode": RUNTIME_MODE,
        "execution_mode": EXECUTION_MODE,
        "target_project_root": target_project_root,
        "earth_root": earth_root,
        "output_root": output_root,
        "revision_identity": revision_identity,
        "strategy_goal": strategy_goal,
        "analysis_type": REQ_030_ANALYSIS_TYPE,
        "call_id": call_id,
        "checked_at_utc": checked_at_utc,
    }


def _req_030_canonical_processing_input(
    *,
    call_chain: Sequence[Mapping[str, Any]],
    target_project_evidence_refs: Sequence[str],
    earth_sweep_evidence_refs: Sequence[str],
    cross_project_context: Sequence[Mapping[str, Any]],
    candidate_lane_designs: Sequence[Mapping[str, Any]],
    strategic_claims: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "call_chain": [dict(row) for row in call_chain],
        "target_project_evidence_refs": list(target_project_evidence_refs),
        "earth_sweep_evidence_refs": list(earth_sweep_evidence_refs),
        "cross_project_context": [dict(row) for row in cross_project_context],
        "candidate_lane_designs": [dict(row) for row in candidate_lane_designs],
        "strategic_claims": [dict(row) for row in strategic_claims],
    }


def build_req_030_call_5_sequencing_and_lane_design_reasoning(
    *,
    target_project_root: str,
    earth_root: str,
    output_root: str,
    revision_identity: str,
    strategy_goal: str,
    call_chain: Sequence[Mapping[str, Any]],
    candidate_lane_designs: Sequence[Mapping[str, Any]],
    strategic_claims: Sequence[Mapping[str, Any]] | None = None,
    cross_project_context: Sequence[Mapping[str, Any]] | None = None,
    target_project_evidence_refs: Sequence[Any] | None = None,
    earth_sweep_evidence_refs: Sequence[Any] | None = None,
    call_id: str = "call-5",
    checked_at_utc: str | None = None,
) -> dict[str, Any]:
    normalized_target_root = _normalize_root(target_project_root, field_name="target_project_root")
    normalized_earth_root = _normalize_root(earth_root, field_name="earth_root")
    normalized_output_root = _normalize_root(output_root, field_name="output_root")
    normalized_revision_identity = _require_text(revision_identity, field_name="revision_identity")
    normalized_strategy_goal = _require_text(strategy_goal, field_name="strategy_goal")
    normalized_call_id = _require_text(call_id, field_name="call_id")
    normalized_checked_at_utc = _require_text(checked_at_utc or utc_now_iso(), field_name="checked_at_utc")
    normalized_call_chain = _req_030_normalize_call_chain(call_chain)
    normalized_target_refs = _normalize_string_list(
        target_project_evidence_refs,
        field_name="target_project_evidence_refs",
    )
    normalized_earth_refs = _normalize_string_list(
        earth_sweep_evidence_refs,
        field_name="earth_sweep_evidence_refs",
    )
    normalized_cross_project_context = _normalize_cross_project_context(cross_project_context)
    normalized_candidate_lane_designs = _req_030_normalize_candidate_lane_designs(candidate_lane_designs)
    normalized_strategic_claims = _req_030_normalize_strategic_claims(
        strategic_claims,
        call_depth=len(normalized_call_chain),
    )

    cross_project_refs = _collect_unique_refs(*[row["evidence_refs"] for row in normalized_cross_project_context])
    available_citation_refs = set(
        _collect_unique_refs(
            normalized_target_refs,
            normalized_earth_refs,
            cross_project_refs,
            [row["output_ref"] for row in normalized_call_chain],
        )
    )
    output_ref_by_sequence = {int(row["sequence"]): str(row["output_ref"]) for row in normalized_call_chain}
    context_by_project = {str(row["project_id"]): row for row in normalized_cross_project_context}

    blocked_ids: set[str] = set()
    open_risks: list[dict[str, Any]] = []
    claim_rows_by_id: dict[str, list[dict[str, Any]]] = {}
    for claim in normalized_strategic_claims:
        claim_rows_by_id.setdefault(str(claim["claim_id"]), []).append(claim)
        source_output_ref = output_ref_by_sequence.get(int(claim["source_call_sequence"]), "")
        citation_refs = list(claim["evidence_refs"])
        if not citation_refs or not set(citation_refs).issubset(available_citation_refs):
            open_risks.append(
                {
                    "risk_id": f"risk-claim-{claim['claim_id']}-citation",
                    "reason_code": "uncited_strategic_claim",
                    "summary": str(claim["summary"]),
                    "required_evidence_refs": _collect_unique_refs([source_output_ref], citation_refs),
                }
            )

    for claim_id, claim_rows in claim_rows_by_id.items():
        analysis_rows = [row for row in claim_rows if row["phase"] == "analysis"]
        synthesis_rows = [row for row in claim_rows if row["phase"] == "synthesis"]
        contradiction_found = False
        for analysis_row in analysis_rows:
            for synthesis_row in synthesis_rows:
                if analysis_row["position"] == synthesis_row["position"]:
                    continue
                open_risks.append(
                    {
                        "risk_id": f"risk-claim-{claim_id}-contradiction",
                        "reason_code": "cross_call_contradiction",
                        "summary": str(synthesis_row["summary"]),
                        "required_evidence_refs": _collect_unique_refs(
                            [output_ref_by_sequence.get(int(analysis_row["source_call_sequence"]), "")],
                            [output_ref_by_sequence.get(int(synthesis_row["source_call_sequence"]), "")],
                            analysis_row["evidence_refs"],
                            synthesis_row["evidence_refs"],
                        ),
                    }
                )
                contradiction_found = True
                break
            if contradiction_found:
                break

    lane_blueprints: list[dict[str, Any]] = []
    for row in normalized_candidate_lane_designs:
        recommendation_id = str(row["recommendation_id"])
        source_output_ref = output_ref_by_sequence.get(int(row["synthesized_from_call_sequence"]), "")
        uncited_refs = sorted(set(row["evidence_refs"]) - available_citation_refs)
        if uncited_refs:
            blocked_ids.add(recommendation_id)
            open_risks.append(
                {
                    "risk_id": f"risk-{recommendation_id}-citation",
                    "reason_code": "uncited_strategic_claim",
                    "summary": str(row["summary"]),
                    "required_evidence_refs": _collect_unique_refs([source_output_ref], uncited_refs),
                }
            )
            continue

        project_context = context_by_project.get(str(row["project_id"]))
        project_evidence_refs = list(project_context["evidence_refs"]) if project_context else []
        if row["lane_scope"] == "cross-project":
            if row["requires_earth_evidence"] and not normalized_earth_refs:
                blocked_ids.add(recommendation_id)
                open_risks.append(
                    {
                        "risk_id": f"risk-{recommendation_id}-earth-evidence",
                        "reason_code": "missing_earth_sweep_evidence_refs",
                        "summary": str(row["summary"]),
                        "required_evidence_refs": _collect_unique_refs([source_output_ref], row["evidence_refs"]),
                    }
                )
                continue
            if project_context is None:
                blocked_ids.add(recommendation_id)
                open_risks.append(
                    {
                        "risk_id": f"risk-{recommendation_id}-context",
                        "reason_code": "missing_cross_project_context",
                        "summary": str(row["summary"]),
                        "required_evidence_refs": _collect_unique_refs([source_output_ref], row["evidence_refs"]),
                    }
                )
                continue

        lane_blueprints.append(
            {
                "lane_id": str(row["lane_id"]),
                "recommendation_id": recommendation_id,
                "summary": str(row["summary"]),
                "rationale": str(row["rationale"]),
                "sequencing_rationale": str(row["sequencing_rationale"]),
                "lane_order": int(row["lane_order"]),
                "lane_scope": str(row["lane_scope"]),
                "project_id": str(row["project_id"]),
                "next_step": str(row["next_step"]),
                "synthesized_from_call_sequence": int(row["synthesized_from_call_sequence"]),
                "source_output_ref": source_output_ref,
                "evidence_refs": _collect_unique_refs(
                    [source_output_ref],
                    row["evidence_refs"],
                    project_evidence_refs,
                    normalized_earth_refs if row["lane_scope"] == "cross-project" else [],
                ),
            }
        )

    lane_blueprints.sort(key=lambda row: (row["lane_order"], row["recommendation_id"], row["lane_id"]))
    open_risks.sort(key=lambda row: row["risk_id"])

    emitted_recommendation_ids = _dedupe_preserving_order(row["recommendation_id"] for row in lane_blueprints)
    evidence_refs = _collect_unique_refs(
        normalized_target_refs,
        normalized_earth_refs,
        cross_project_refs,
        [row["output_ref"] for row in normalized_call_chain],
        *[row["evidence_refs"] for row in lane_blueprints],
        *[row["required_evidence_refs"] for row in open_risks],
    )
    if lane_blueprints and not open_risks:
        decision = "proceed"
    elif lane_blueprints and open_risks:
        decision = "proceed-with-open-risks"
    elif open_risks:
        decision = "blocked"
    else:
        decision = "insufficient-context"
    confidence = "high" if lane_blueprints and not open_risks else "medium" if lane_blueprints else "low"

    canonical_input = _req_030_canonical_input(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        output_root=normalized_output_root,
        revision_identity=normalized_revision_identity,
        strategy_goal=normalized_strategy_goal,
        call_id=normalized_call_id,
        checked_at_utc=normalized_checked_at_utc,
    )
    canonical_processing_input = _req_030_canonical_processing_input(
        call_chain=normalized_call_chain,
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        cross_project_context=normalized_cross_project_context,
        candidate_lane_designs=normalized_candidate_lane_designs,
        strategic_claims=normalized_strategic_claims,
    )
    processing_sha = _canonical_digest(canonical_processing_input)
    processing_call_id = f"req030-processing-{processing_sha[:16]}"
    llm_call_trace_rows = _req_030_build_trace_rows(
        synthesis_call_id=processing_call_id,
        call_chain=normalized_call_chain,
        recommendation_ids=emitted_recommendation_ids,
    )

    return {
        "schema_version": REQ_030_SCHEMA_VERSION,
        "requirement_id": REQ_030_REQUIREMENT_ID,
        "analysis_type": REQ_030_ANALYSIS_TYPE,
        "call_id": normalized_call_id,
        "checked_at_utc": normalized_checked_at_utc,
        "processing_behavior": {
            "strategy": REQ_030_PROCESSING_STRATEGY,
            "reasoning_mode": REQ_030_REASONING_MODE,
            "strict_evidence_discipline": True,
            "context_inputs": {
                "call_chain": [dict(row) for row in normalized_call_chain],
                "target_project": {
                    "project_root": normalized_target_root,
                    "evidence_refs": list(normalized_target_refs),
                },
                "earth_sweep": {
                    "earth_root": normalized_earth_root,
                    "evidence_refs": list(normalized_earth_refs),
                },
                "cross_project_context": [dict(row) for row in normalized_cross_project_context],
                "candidate_lane_designs": [dict(row) for row in normalized_candidate_lane_designs],
                "strategic_claims": [dict(row) for row in normalized_strategic_claims],
            },
            "context_usage": {
                "call_ids_considered": [str(row["call_id"]) for row in normalized_call_chain],
                "candidate_recommendation_ids_considered": _dedupe_preserving_order(
                    row["recommendation_id"] for row in normalized_candidate_lane_designs
                ),
                "emitted_recommendation_ids": emitted_recommendation_ids,
                "emitted_lane_ids": [str(row["lane_id"]) for row in lane_blueprints],
                "blocked_recommendation_ids": sorted(blocked_ids),
                "open_risk_ids_emitted": [str(row["risk_id"]) for row in open_risks],
                "evidence_refs_used": list(evidence_refs),
            },
            "lane_design": {
                "decision": decision,
                "rationale": (
                    f"lane_blueprints={len(lane_blueprints)} open_risks={len(open_risks)} "
                    f"blocked={len(blocked_ids)}"
                ),
                "confidence": confidence,
                "evidence_refs": list(evidence_refs),
                "lane_blueprints": lane_blueprints,
                "open_risks": open_risks,
            },
        },
        "call_metadata": {
            "reproducibility": "deterministic-input-fingerprint",
            "canonical_input": canonical_input,
            "canonical_input_sha256": _canonical_digest(canonical_input),
            "reproducible_call_id": f"req030-{_canonical_digest(canonical_input)[:16]}",
            "canonical_processing_input": canonical_processing_input,
            "processing_input_sha256": processing_sha,
            "processing_call_id": processing_call_id,
            "llm_call_trace_schema_version": REQ_030_LLM_CALL_TRACE_SCHEMA_VERSION,
            "llm_call_trace_path": LLM_CALL_TRACE_RELATIVE_PATH,
            "llm_call_trace_sha256": _canonical_digest(llm_call_trace_rows),
            "llm_call_trace_rows": llm_call_trace_rows,
        },
    }


def validate_req_030_call_5_sequencing_and_lane_design_reasoning(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    if payload.get("schema_version") != REQ_030_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_030_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_030_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_030_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_030_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_030_ANALYSIS_TYPE}")
    if not _as_text(payload.get("call_id")):
        errors.append("call_id is required")
    if not _as_text(payload.get("checked_at_utc")):
        errors.append("checked_at_utc is required")

    processing_behavior = payload.get("processing_behavior")
    if not isinstance(processing_behavior, Mapping):
        errors.append("processing_behavior must be an object")
        return errors
    if processing_behavior.get("strategy") != REQ_030_PROCESSING_STRATEGY:
        errors.append(f"processing_behavior.strategy must be {REQ_030_PROCESSING_STRATEGY}")
    if processing_behavior.get("reasoning_mode") != REQ_030_REASONING_MODE:
        errors.append(f"processing_behavior.reasoning_mode must be {REQ_030_REASONING_MODE}")
    if processing_behavior.get("strict_evidence_discipline") is not True:
        errors.append("processing_behavior.strict_evidence_discipline must be true")

    context_inputs = processing_behavior.get("context_inputs")
    normalized_call_chain: list[dict[str, Any]] = []
    normalized_target_refs: list[str] = []
    normalized_earth_refs: list[str] = []
    normalized_cross_project_context: list[dict[str, Any]] = []
    normalized_candidate_lane_designs: list[dict[str, Any]] = []
    normalized_strategic_claims: list[dict[str, Any]] = []
    if not isinstance(context_inputs, Mapping):
        errors.append("processing_behavior.context_inputs must be an object")
        return errors
    try:
        normalized_call_chain = _req_030_normalize_call_chain(context_inputs.get("call_chain"))
    except Req030Error as exc:
        errors.append(str(exc))
    target_project = context_inputs.get("target_project")
    if not isinstance(target_project, Mapping):
        errors.append("processing_behavior.context_inputs.target_project must be an object")
    else:
        normalized_target_refs = sorted(
            {_as_text(ref) for ref in target_project.get("evidence_refs", []) if _as_text(ref)}
        )
    earth_sweep = context_inputs.get("earth_sweep")
    if not isinstance(earth_sweep, Mapping):
        errors.append("processing_behavior.context_inputs.earth_sweep must be an object")
    else:
        normalized_earth_refs = sorted(
            {_as_text(ref) for ref in earth_sweep.get("evidence_refs", []) if _as_text(ref)}
        )
    try:
        normalized_cross_project_context = _normalize_cross_project_context(context_inputs.get("cross_project_context"))
    except ValueError as exc:
        errors.append(str(exc))
    try:
        normalized_candidate_lane_designs = _req_030_normalize_candidate_lane_designs(
            context_inputs.get("candidate_lane_designs")
        )
    except Req030Error as exc:
        errors.append(str(exc))
    try:
        normalized_strategic_claims = _req_030_normalize_strategic_claims(
            context_inputs.get("strategic_claims"),
            call_depth=len(normalized_call_chain) if normalized_call_chain else 5,
        )
    except Req030Error as exc:
        errors.append(str(exc))

    lane_design = processing_behavior.get("lane_design")
    if not isinstance(lane_design, Mapping):
        errors.append("processing_behavior.lane_design must be an object")
        return errors
    if not isinstance(lane_design.get("evidence_refs"), list):
        errors.append("processing_behavior.lane_design.evidence_refs must be a list")
    lane_blueprints = lane_design.get("lane_blueprints")
    if not isinstance(lane_blueprints, list):
        errors.append("processing_behavior.lane_design.lane_blueprints must be a list")
        lane_blueprints = []
    previous_sort_key: tuple[int, str, str] | None = None
    for index, row in enumerate(lane_blueprints):
        if not isinstance(row, Mapping):
            errors.append(f"processing_behavior.lane_design.lane_blueprints[{index}] must be an object")
            continue
        lane_id = _as_text(row.get("lane_id"))
        recommendation_id = _as_text(row.get("recommendation_id"))
        if not REQ_030_LANE_ID_RE.match(lane_id):
            errors.append(
                f"processing_behavior.lane_design.lane_blueprints[{index}].lane_id must match {REQ_030_LANE_ID_RE.pattern}"
            )
        if not REQ_030_RECOMMENDATION_ID_RE.match(recommendation_id):
            errors.append(
                "processing_behavior.lane_design.lane_blueprints"
                f"[{index}].recommendation_id must match {REQ_030_RECOMMENDATION_ID_RE.pattern}"
            )
        lane_order = row.get("lane_order")
        if isinstance(lane_order, bool) or not isinstance(lane_order, int):
            errors.append(f"processing_behavior.lane_design.lane_blueprints[{index}].lane_order must be an integer")
            lane_order = 0
        current_sort_key = (lane_order, recommendation_id, lane_id)
        if previous_sort_key is not None and current_sort_key < previous_sort_key:
            errors.append("processing_behavior.lane_design.lane_blueprints must be sorted deterministically")
        previous_sort_key = current_sort_key
        for field_name in ("summary", "rationale", "sequencing_rationale", "next_step", "source_output_ref"):
            if not _as_text(row.get(field_name)):
                errors.append(f"processing_behavior.lane_design.lane_blueprints[{index}].{field_name} is required")
        if not isinstance(row.get("evidence_refs"), list) or not row.get("evidence_refs"):
            errors.append(
                f"processing_behavior.lane_design.lane_blueprints[{index}].evidence_refs must be non-empty list"
            )

    open_risks = lane_design.get("open_risks")
    if not isinstance(open_risks, list):
        errors.append("processing_behavior.lane_design.open_risks must be a list")
        open_risks = []
    for index, row in enumerate(open_risks):
        if not isinstance(row, Mapping):
            errors.append(f"processing_behavior.lane_design.open_risks[{index}] must be an object")
            continue
        if not _as_text(row.get("risk_id")):
            errors.append(f"processing_behavior.lane_design.open_risks[{index}].risk_id is required")
        if not _as_text(row.get("reason_code")):
            errors.append(f"processing_behavior.lane_design.open_risks[{index}].reason_code is required")
        if not isinstance(row.get("required_evidence_refs"), list) or not row.get("required_evidence_refs"):
            errors.append(
                f"processing_behavior.lane_design.open_risks[{index}].required_evidence_refs must be non-empty list"
            )

    metadata = payload.get("call_metadata")
    if not isinstance(metadata, Mapping):
        errors.append("call_metadata must be an object")
        return errors
    if metadata.get("reproducibility") != "deterministic-input-fingerprint":
        errors.append("call_metadata.reproducibility must be deterministic-input-fingerprint")
    canonical_input = metadata.get("canonical_input")
    if not isinstance(canonical_input, Mapping):
        errors.append("call_metadata.canonical_input must be an object")
    else:
        expected_canonical_input = _req_030_canonical_input(
            target_project_root=_as_text(context_inputs.get("target_project", {}).get("project_root"))
            if isinstance(context_inputs.get("target_project"), Mapping)
            else "",
            earth_root=_as_text(context_inputs.get("earth_sweep", {}).get("earth_root"))
            if isinstance(context_inputs.get("earth_sweep"), Mapping)
            else "",
            output_root=_as_text(canonical_input.get("output_root")),
            revision_identity=_as_text(canonical_input.get("revision_identity")),
            strategy_goal=_as_text(canonical_input.get("strategy_goal")),
            call_id=_as_text(payload.get("call_id")),
            checked_at_utc=_as_text(payload.get("checked_at_utc")),
        )
        if dict(canonical_input) != expected_canonical_input:
            errors.append("call_metadata.canonical_input must mirror normalized invocation anchors")
        expected_input_sha = _canonical_digest(expected_canonical_input)
        if metadata.get("canonical_input_sha256") != expected_input_sha:
            errors.append("call_metadata.canonical_input_sha256 does not match canonical input")
        if metadata.get("reproducible_call_id") != f"req030-{expected_input_sha[:16]}":
            errors.append("call_metadata.reproducible_call_id does not match canonical digest")

    canonical_processing_input = metadata.get("canonical_processing_input")
    if not isinstance(canonical_processing_input, Mapping):
        errors.append("call_metadata.canonical_processing_input must be an object")
    else:
        expected_processing_input = _req_030_canonical_processing_input(
            call_chain=normalized_call_chain,
            target_project_evidence_refs=normalized_target_refs,
            earth_sweep_evidence_refs=normalized_earth_refs,
            cross_project_context=normalized_cross_project_context,
            candidate_lane_designs=normalized_candidate_lane_designs,
            strategic_claims=normalized_strategic_claims,
        )
        if dict(canonical_processing_input) != expected_processing_input:
            errors.append("call_metadata.canonical_processing_input must mirror normalized lane-design inputs")
        expected_processing_sha = _canonical_digest(expected_processing_input)
        if metadata.get("processing_input_sha256") != expected_processing_sha:
            errors.append("call_metadata.processing_input_sha256 does not match processing input")
        if metadata.get("processing_call_id") != f"req030-processing-{expected_processing_sha[:16]}":
            errors.append("call_metadata.processing_call_id does not match processing digest")

    if metadata.get("llm_call_trace_schema_version") != REQ_030_LLM_CALL_TRACE_SCHEMA_VERSION:
        errors.append(
            f"call_metadata.llm_call_trace_schema_version must be {REQ_030_LLM_CALL_TRACE_SCHEMA_VERSION}"
        )
    if metadata.get("llm_call_trace_path") != LLM_CALL_TRACE_RELATIVE_PATH:
        errors.append(f"call_metadata.llm_call_trace_path must be {LLM_CALL_TRACE_RELATIVE_PATH}")
    llm_call_trace_rows = metadata.get("llm_call_trace_rows")
    if not isinstance(llm_call_trace_rows, list):
        errors.append("call_metadata.llm_call_trace_rows must be a list")
    else:
        expected_trace_rows = _req_030_build_trace_rows(
            synthesis_call_id=_as_text(metadata.get("processing_call_id")),
            call_chain=normalized_call_chain,
            recommendation_ids=_dedupe_preserving_order(
                _as_text(row.get("recommendation_id")) for row in lane_blueprints if isinstance(row, Mapping)
            ),
        )
        if llm_call_trace_rows != expected_trace_rows:
            errors.append("call_metadata.llm_call_trace_rows must mirror deterministic trace rows")
        if metadata.get("llm_call_trace_sha256") != _canonical_digest(expected_trace_rows):
            errors.append("call_metadata.llm_call_trace_sha256 does not match llm_call_trace_rows")

    return errors



_legacy_build_req_034_cross_call_memory_handoff_contract = build_req_034_cross_call_memory_handoff_contract
_legacy_validate_req_034_cross_call_memory_handoff_contract = validate_req_034_cross_call_memory_handoff_contract


def _req_034_require_positive_int(
    value: Any,
    *,
    field_name: str,
    minimum: int = 1,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise Req034Error(f"{field_name} must be an integer")
    if value < minimum:
        raise Req034Error(f"{field_name} must be at least {minimum}")
    return value


def _req_034_normalize_current_call(
    value: Any,
    *,
    field_name: str,
) -> dict[str, str]:
    row = _require_mapping(value, field_name=field_name)
    return {
        "call_id": _require_text(row.get("call_id"), field_name=f"{field_name}.call_id").lower(),
        "objective": _require_text(row.get("objective"), field_name=f"{field_name}.objective"),
    }


def _req_034_normalize_call_chain(
    value: Any,
    *,
    field_name: str,
    current_call_id: str,
) -> list[dict[str, Any]]:
    if value is None or not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise Req034Error(f"{field_name} must be an array")

    normalized: list[dict[str, Any]] = []
    seen_call_ids: set[str] = set()
    for index, raw_row in enumerate(value):
        row = _require_mapping(raw_row, field_name=f"{field_name}[{index}]")
        sequence = row.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int):
            raise Req034Error(f"{field_name}[{index}].sequence must be an integer")
        if sequence != index + 1:
            raise Req034Error(f"{field_name}[{index}].sequence must be {index + 1}")
        call_id = _require_text(row.get("call_id"), field_name=f"{field_name}[{index}].call_id").lower()
        if call_id in seen_call_ids:
            raise Req034Error(f"{field_name}[{index}].call_id must be unique")
        seen_call_ids.add(call_id)
        normalized.append(
            {
                "sequence": sequence,
                "call_id": call_id,
                "phase": _require_text(row.get("phase"), field_name=f"{field_name}[{index}].phase"),
                "output_ref": _require_text(row.get("output_ref"), field_name=f"{field_name}[{index}].output_ref"),
            }
        )

    if len(normalized) < 2:
        raise Req034Error(f"{field_name} must include at least one prior call plus {current_call_id}")
    if normalized[-1]["call_id"] != current_call_id:
        raise Req034Error(f"{field_name} must terminate with current_call.call_id {current_call_id}")
    return normalized


def _req_034_normalize_memory_budget(
    value: Any,
    *,
    field_name: str,
) -> dict[str, int]:
    if value is None:
        return {
            "max_entries": REQ_034_DEFAULT_MAX_ENTRIES,
            "max_citation_refs_per_entry": REQ_034_DEFAULT_MAX_CITATION_REFS_PER_ENTRY,
        }
    row = _require_mapping(value, field_name=field_name)
    return {
        "max_entries": _req_034_require_positive_int(
            row.get("max_entries", REQ_034_DEFAULT_MAX_ENTRIES),
            field_name=f"{field_name}.max_entries",
        ),
        "max_citation_refs_per_entry": _req_034_require_positive_int(
            row.get("max_citation_refs_per_entry", REQ_034_DEFAULT_MAX_CITATION_REFS_PER_ENTRY),
            field_name=f"{field_name}.max_citation_refs_per_entry",
        ),
    }


def _req_034_normalize_handoff_item(
    value: Any,
    *,
    field_name: str,
    source_call_id: str,
    source_output_ref: str,
) -> dict[str, Any]:
    row = _require_mapping(value, field_name=field_name)
    kind = _require_text(row.get("kind"), field_name=f"{field_name}.kind").lower()
    if kind not in REQ_034_ALLOWED_ENTRY_KINDS:
        raise Req034Error(f"{field_name}.kind must be one of {sorted(REQ_034_ALLOWED_ENTRY_KINDS)}")
    carry_forward = row.get("carry_forward")
    if not isinstance(carry_forward, bool):
        raise Req034Error(f"{field_name}.carry_forward must be a boolean")
    return {
        "memory_id": _require_text(row.get("memory_id"), field_name=f"{field_name}.memory_id"),
        "memory_key": _require_text(row.get("memory_key"), field_name=f"{field_name}.memory_key"),
        "kind": kind,
        "summary": _require_text(row.get("summary"), field_name=f"{field_name}.summary"),
        "position": _require_text(row.get("position"), field_name=f"{field_name}.position"),
        "source_call_id": source_call_id,
        "source_output_ref": source_output_ref,
        "carry_forward": carry_forward,
        "supersedes_memory_ids": _normalize_string_list(
            row.get("supersedes_memory_ids"),
            field_name=f"{field_name}.supersedes_memory_ids",
        ),
        "citation_refs": _normalize_string_list(
            row.get("citation_refs"),
            field_name=f"{field_name}.citation_refs",
            min_items=1,
        ),
    }


def _req_034_normalize_prior_call_memory(
    value: Any,
    *,
    field_name: str,
    call_chain: Sequence[Mapping[str, Any]],
    current_call_id: str,
) -> list[dict[str, Any]]:
    if value is None or not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise Req034Error(f"{field_name} must be an array")

    chain_by_call_id = {str(row["call_id"]): row for row in call_chain}
    expected_prior_call_ids = [str(row["call_id"]) for row in call_chain[:-1]]
    seen_call_ids: set[str] = set()
    seen_memory_ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, raw_row in enumerate(value):
        row = _require_mapping(raw_row, field_name=f"{field_name}[{index}]")
        call_id = _require_text(row.get("call_id"), field_name=f"{field_name}[{index}].call_id").lower()
        if call_id == current_call_id or call_id not in chain_by_call_id:
            raise Req034Error(f"{field_name}[{index}].call_id must reference a prior call from call_chain")
        if call_id in seen_call_ids:
            raise Req034Error(f"{field_name}[{index}].call_id must be unique")
        seen_call_ids.add(call_id)
        source_output_ref = _require_text(row.get("output_ref"), field_name=f"{field_name}[{index}].output_ref")
        if source_output_ref != chain_by_call_id[call_id]["output_ref"]:
            raise Req034Error(f"{field_name}[{index}].output_ref must match call_chain for {call_id}")
        raw_items = row.get("handoff_items")
        if raw_items is None or not isinstance(raw_items, Sequence) or isinstance(raw_items, (str, bytes, bytearray)):
            raise Req034Error(f"{field_name}[{index}].handoff_items must be a non-empty array")
        if not raw_items:
            raise Req034Error(f"{field_name}[{index}].handoff_items must be a non-empty array")
        handoff_items: list[dict[str, Any]] = []
        for item_index, raw_item in enumerate(raw_items):
            item = _req_034_normalize_handoff_item(
                raw_item,
                field_name=f"{field_name}[{index}].handoff_items[{item_index}]",
                source_call_id=call_id,
                source_output_ref=source_output_ref,
            )
            if item["memory_id"] in seen_memory_ids:
                raise Req034Error(f"{field_name}[{index}].handoff_items[{item_index}].memory_id must be unique")
            seen_memory_ids.add(item["memory_id"])
            handoff_items.append(item)
        handoff_items.sort(key=lambda item: item["memory_id"])
        normalized.append(
            {
                "call_id": call_id,
                "sequence": chain_by_call_id[call_id]["sequence"],
                "output_ref": source_output_ref,
                "summary": _require_text(row.get("summary"), field_name=f"{field_name}[{index}].summary"),
                "handoff_items": handoff_items,
            }
        )

    if sorted(seen_call_ids) != sorted(expected_prior_call_ids):
        raise Req034Error(
            f"{field_name} must include exactly {expected_prior_call_ids} so every prior call contributes bounded memory"
        )
    normalized.sort(key=lambda row: int(row["sequence"]))
    return normalized


def _req_034_canonical_input(
    *,
    target_project_id: str,
    current_call: Mapping[str, Any],
    call_chain: Sequence[Mapping[str, Any]],
    memory_budget: Mapping[str, Any],
    allowed_context_refs: Sequence[str],
    prior_call_memory: Sequence[Mapping[str, Any]],
    checked_at_utc: str,
) -> dict[str, Any]:
    return {
        "requirement_id": REQ_034_REQUIREMENT_ID,
        "analysis_type": REQ_034_ANALYSIS_TYPE,
        "call_id": current_call["call_id"],
        "checked_at_utc": checked_at_utc,
        "target_project": {"project_id": target_project_id},
        "current_call": {
            "call_id": current_call["call_id"],
            "objective": current_call["objective"],
        },
        "call_chain": [
            {
                "sequence": row["sequence"],
                "call_id": row["call_id"],
                "phase": row["phase"],
                "output_ref": row["output_ref"],
            }
            for row in call_chain
        ],
        "memory_budget": {
            "max_entries": memory_budget["max_entries"],
            "max_citation_refs_per_entry": memory_budget["max_citation_refs_per_entry"],
        },
        "allowed_context_refs": list(allowed_context_refs),
        "prior_call_memory": [
            {
                "call_id": row["call_id"],
                "output_ref": row["output_ref"],
                "summary": row["summary"],
                "handoff_items": [
                    {
                        "memory_id": item["memory_id"],
                        "memory_key": item["memory_key"],
                        "kind": item["kind"],
                        "summary": item["summary"],
                        "position": item["position"],
                        "carry_forward": item["carry_forward"],
                        "supersedes_memory_ids": list(item["supersedes_memory_ids"]),
                        "citation_refs": list(item["citation_refs"]),
                    }
                    for item in row["handoff_items"]
                ],
            }
            for row in prior_call_memory
        ],
    }


def _build_req_034_open_risk(
    *,
    reason_code: str,
    memory_id: str,
    memory_key: str,
    source_call_id: str,
    summary: str,
    required_citation_refs: Sequence[str],
) -> dict[str, Any]:
    return {
        "risk_id": f"risk-{reason_code}-{memory_id}",
        "reason_code": reason_code,
        "summary": summary,
        "memory_id": memory_id,
        "memory_key": memory_key,
        "source_call_id": source_call_id,
        "required_citation_refs": list(required_citation_refs),
    }


def _build_req_034_handoff_materialization(
    *,
    prior_call_memory: Sequence[Mapping[str, Any]],
    memory_budget: Mapping[str, Any],
    allowed_context_refs: Sequence[str],
    call_chain: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]], int, int, int]:
    available_context_refs = set(allowed_context_refs) | {
        _require_text(row.get("output_ref"), field_name="call_chain[].output_ref") for row in call_chain
    }
    retained_by_key: dict[str, dict[str, Any]] = {}
    superseded_memory_ids: set[str] = set()
    open_risks: list[dict[str, Any]] = []
    citation_refs_truncated_count = 0
    input_item_count = 0
    for row in prior_call_memory:
        for item in row["handoff_items"]:
            input_item_count += 1
            if not item["carry_forward"]:
                continue
            blocked_citation_refs = sorted(set(item["citation_refs"]) - available_context_refs)
            if blocked_citation_refs:
                open_risks.append(
                    _build_req_034_open_risk(
                        reason_code="context_leakage_prevented",
                        memory_id=str(item["memory_id"]),
                        memory_key=str(item["memory_key"]),
                        source_call_id=str(item["source_call_id"]),
                        summary=(
                            f"Blocked memory '{item['memory_id']}' from {item['source_call_id']} because it cited "
                            "refs outside the bounded context window."
                        ),
                        required_citation_refs=blocked_citation_refs,
                    )
                )
                continue
            trimmed_citation_refs = list(item["citation_refs"][: memory_budget["max_citation_refs_per_entry"]])
            citation_refs_truncated_count += len(item["citation_refs"]) - len(trimmed_citation_refs)
            candidate = {
                "memory_id": item["memory_id"],
                "memory_key": item["memory_key"],
                "kind": item["kind"],
                "summary": item["summary"],
                "position": item["position"],
                "source_call_id": item["source_call_id"],
                "source_output_ref": item["source_output_ref"],
                "source_call_sequence": row["sequence"],
                "carry_forward": item["carry_forward"],
                "supersedes_memory_ids": list(item["supersedes_memory_ids"]),
                "citation_refs": trimmed_citation_refs,
            }
            existing = retained_by_key.get(str(item["memory_key"]))
            if existing is None:
                retained_by_key[str(item["memory_key"])] = candidate
                continue
            if (
                str(item["position"]) != str(existing["position"])
                and str(existing["memory_id"]) not in item["supersedes_memory_ids"]
            ):
                open_risks.append(
                    _build_req_034_open_risk(
                        reason_code="contradiction_drift_prevented",
                        memory_id=str(item["memory_id"]),
                        memory_key=str(item["memory_key"]),
                        source_call_id=str(item["source_call_id"]),
                        summary=(
                            f"Blocked memory '{item['memory_id']}' from {item['source_call_id']} because it contradicted "
                            f"earlier memory for key '{item['memory_key']}' without superseding it."
                        ),
                        required_citation_refs=_collect_unique_refs(
                            existing["citation_refs"],
                            item["citation_refs"],
                            [str(existing["source_output_ref"])],
                            [str(item["source_output_ref"])],
                        ),
                    )
                )
                continue
            superseded_memory_ids.add(str(existing["memory_id"]))
            retained_by_key[str(item["memory_key"])] = candidate

    retained_items = list(retained_by_key.values())
    retained_items.sort(key=lambda item: (-int(item["source_call_sequence"]), str(item["memory_id"])))
    kept_items = retained_items[: memory_budget["max_entries"]]
    dropped_due_to_budget_count = max(0, len(retained_items) - len(kept_items))
    final_items = sorted(kept_items, key=lambda item: (int(item["source_call_sequence"]), str(item["memory_id"])))
    return (
        final_items,
        sorted(superseded_memory_ids),
        sorted(open_risks, key=lambda risk: str(risk["risk_id"])),
        input_item_count,
        citation_refs_truncated_count,
        dropped_due_to_budget_count,
    )


def _build_req_034_llm_call_trace_rows(
    *,
    processing_call_id: str,
    call_chain: Sequence[Mapping[str, Any]],
    prior_call_memory: Sequence[Mapping[str, Any]],
    retained_items: Sequence[Mapping[str, Any]],
    open_risks: Sequence[Mapping[str, Any]],
    current_call: Mapping[str, Any],
    max_entries: int,
) -> list[dict[str, Any]]:
    input_rows_by_call_id = {str(row["call_id"]): row for row in prior_call_memory}
    retained_by_call_id: dict[str, list[Mapping[str, Any]]] = {}
    for item in retained_items:
        retained_by_call_id.setdefault(str(item["source_call_id"]), []).append(item)
    open_risks_by_call_id: dict[str, list[Mapping[str, Any]]] = {}
    for risk in open_risks:
        open_risks_by_call_id.setdefault(str(risk["source_call_id"]), []).append(risk)

    trace_rows: list[dict[str, Any]] = []
    previous_output_ref = ""
    terminal_call_id = str(current_call["call_id"])
    for row in call_chain:
        call_id = str(row["call_id"])
        if call_id != terminal_call_id:
            source_row = input_rows_by_call_id[call_id]
            citation_refs = _req_026_dedupe_preserving_order(
                [ref for item in source_row["handoff_items"] for ref in item["citation_refs"]]
            )
            input_refs = _req_026_dedupe_preserving_order(
                ([previous_output_ref] if previous_output_ref else []) + citation_refs
            )
            retained_count = len(retained_by_call_id.get(call_id, []))
            blocked_count = len(open_risks_by_call_id.get(call_id, []))
            handoff_summary = (
                f"Call {row['sequence']} contributes {retained_count} retained memory item(s) via {row['output_ref']} "
                f"for {terminal_call_id}; {blocked_count} item(s) were blocked before final handoff."
            )
            trace_rows.append(
                {
                    "schema_version": REQ_034_LLM_CALL_TRACE_SCHEMA_VERSION,
                    "requirement_id": REQ_034_REQUIREMENT_ID,
                    "processing_call_id": processing_call_id,
                    "call_id": call_id,
                    "sequence": row["sequence"],
                    "call_objective": f"Preserve cited handoff memory from {call_id} into {terminal_call_id}.",
                    "input_refs": input_refs,
                    "output_refs": [row["output_ref"]],
                    "handoff_summary": handoff_summary,
                }
            )
            previous_output_ref = str(row["output_ref"])
            continue

        input_refs = _req_026_dedupe_preserving_order(
            [str(source_row["output_ref"]) for source_row in prior_call_memory]
            + [ref for item in retained_items for ref in item["citation_refs"]]
            + [ref for risk in open_risks for ref in risk["required_citation_refs"]]
        )
        trace_rows.append(
            {
                "schema_version": REQ_034_LLM_CALL_TRACE_SCHEMA_VERSION,
                "requirement_id": REQ_034_REQUIREMENT_ID,
                "processing_call_id": processing_call_id,
                "call_id": call_id,
                "sequence": row["sequence"],
                "call_objective": str(current_call["objective"]),
                "input_refs": input_refs,
                "output_refs": [row["output_ref"]],
                "handoff_summary": (
                    f"Call {row['sequence']} receives {len(retained_items)} retained memory item(s) with "
                    f"{len(open_risks)} open risk(s) under a max_entries budget of {max_entries}."
                ),
            }
        )
    return trace_rows


def build_req_034_cross_call_memory_handoff_contract(
    *,
    target_project: Mapping[str, Any],
    current_call: Mapping[str, Any],
    call_chain: Sequence[Mapping[str, Any]],
    prior_call_memory: Sequence[Mapping[str, Any]],
    allowed_context_refs: Sequence[str],
    memory_budget: Mapping[str, Any] | None = None,
    analysis_type: str = REQ_034_ANALYSIS_TYPE,
    call_id: str | None = None,
    checked_at_utc: str | None = None,
) -> dict[str, Any]:
    if analysis_type != REQ_034_ANALYSIS_TYPE:
        raise Req034Error(f"analysis_type must be {REQ_034_ANALYSIS_TYPE}")

    project = _require_mapping(target_project, field_name="target_project")
    project_id = _require_text(project.get("project_id"), field_name="target_project.project_id")
    normalized_current_call = _req_034_normalize_current_call(current_call, field_name="current_call")
    if call_id is not None and _require_text(call_id, field_name="call_id").lower() != normalized_current_call["call_id"]:
        raise Req034Error("call_id must match current_call.call_id when provided")
    normalized_call_chain = _req_034_normalize_call_chain(
        call_chain,
        field_name="call_chain",
        current_call_id=normalized_current_call["call_id"],
    )
    normalized_memory_budget = _req_034_normalize_memory_budget(memory_budget, field_name="memory_budget")
    normalized_allowed_context_refs = _normalize_string_list(
        allowed_context_refs,
        field_name="allowed_context_refs",
        min_items=1,
    )
    normalized_prior_call_memory = _req_034_normalize_prior_call_memory(
        prior_call_memory,
        field_name="prior_call_memory",
        call_chain=normalized_call_chain,
        current_call_id=normalized_current_call["call_id"],
    )
    normalized_checked_at_utc = _require_text(checked_at_utc or utc_now_iso(), field_name="checked_at_utc")
    canonical_input = _req_034_canonical_input(
        target_project_id=project_id,
        current_call=normalized_current_call,
        call_chain=normalized_call_chain,
        memory_budget=normalized_memory_budget,
        allowed_context_refs=normalized_allowed_context_refs,
        prior_call_memory=normalized_prior_call_memory,
        checked_at_utc=normalized_checked_at_utc,
    )
    canonical_input_sha = _canonical_digest(canonical_input)
    processing_call_id = f"req034-processing-{canonical_input_sha[:16]}"
    (
        retained_items,
        superseded_memory_ids,
        open_risks,
        input_item_count,
        citation_refs_truncated_count,
        dropped_due_to_budget_count,
    ) = (
        _build_req_034_handoff_materialization(
            prior_call_memory=normalized_prior_call_memory,
            memory_budget=normalized_memory_budget,
            allowed_context_refs=normalized_allowed_context_refs,
            call_chain=normalized_call_chain,
        )
    )
    llm_call_trace_rows = _build_req_034_llm_call_trace_rows(
        processing_call_id=processing_call_id,
        call_chain=normalized_call_chain,
        prior_call_memory=normalized_prior_call_memory,
        retained_items=retained_items,
        open_risks=open_risks,
        current_call=normalized_current_call,
        max_entries=normalized_memory_budget["max_entries"],
    )
    llm_call_trace_sha = _canonical_digest(llm_call_trace_rows)
    evidence_refs_used = _collect_unique_refs(*[item["citation_refs"] for item in retained_items])
    allowed_context_refs_used = sorted(set(evidence_refs_used) & set(normalized_allowed_context_refs))

    return {
        "ok": True,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "schema_version": REQ_034_SCHEMA_VERSION,
        "requirement_id": REQ_034_REQUIREMENT_ID,
        "analysis_type": REQ_034_ANALYSIS_TYPE,
        "call_id": normalized_current_call["call_id"],
        "checked_at_utc": normalized_checked_at_utc,
        "cross_call_memory_handoff": {
            "target_project": {"project_id": project_id},
            "current_call": {
                "call_id": normalized_current_call["call_id"],
                "objective": normalized_current_call["objective"],
            },
            "source_calls": [row["call_id"] for row in normalized_prior_call_memory],
            "handoff_items": retained_items,
            "bounded_context": {
                "max_entries": normalized_memory_budget["max_entries"],
                "max_citation_refs_per_entry": normalized_memory_budget["max_citation_refs_per_entry"],
                "source_call_count": len(normalized_prior_call_memory),
                "input_item_count": input_item_count,
                "retained_item_count": len(retained_items),
                "dropped_item_count": input_item_count - len(retained_items),
                "dropped_due_to_budget_count": dropped_due_to_budget_count,
                "citation_ref_count": sum(len(item["citation_refs"]) for item in retained_items),
                "citation_refs_truncated_count": citation_refs_truncated_count,
            },
            "summary": {
                "source_call_count": len(normalized_prior_call_memory),
                "input_item_count": input_item_count,
                "retained_item_count": len(retained_items),
                "superseded_item_count": len(superseded_memory_ids),
                "open_risk_count": len(open_risks),
            },
        },
        "processing_behavior": {
            "strategy": REQ_034_PROCESSING_STRATEGY,
            "reasoning_mode": REQ_034_REASONING_MODE,
            "strict_evidence_discipline": True,
            "context_inputs": {
                "current_call": normalized_current_call,
                "call_chain": normalized_call_chain,
                "prior_call_memory": normalized_prior_call_memory,
                "allowed_context_refs": normalized_allowed_context_refs,
                "memory_budget": normalized_memory_budget,
            },
            "context_usage": {
                "source_call_ids_used": [row["call_id"] for row in normalized_prior_call_memory],
                "source_output_refs_used": [row["output_ref"] for row in normalized_prior_call_memory],
                "allowed_context_refs_used": allowed_context_refs_used,
                "retained_memory_ids": [item["memory_id"] for item in retained_items],
                "superseded_memory_ids": superseded_memory_ids,
                "open_risk_ids_emitted": [risk["risk_id"] for risk in open_risks],
                "reason_codes_emitted": [risk["reason_code"] for risk in open_risks],
                "evidence_refs_used": evidence_refs_used,
            },
            "handoff_rules": {
                "required_handoff_fields": list(REQ_034_REQUIRED_HANDOFF_FIELDS),
                "allowed_entry_kinds": sorted(REQ_034_ALLOWED_ENTRY_KINDS),
                "max_entries": normalized_memory_budget["max_entries"],
                "max_citation_refs_per_entry": normalized_memory_budget["max_citation_refs_per_entry"],
                "contradiction_requires_supersession": True,
                "citation_refs_required": True,
            },
            "diagnostics": {
                "open_risks": open_risks,
            },
        },
        "source": {
            "source_call_count": len(normalized_prior_call_memory),
            "input_item_count": input_item_count,
            "retained_item_count": len(retained_items),
            "open_risk_count": len(open_risks),
            "evidence_ref_count": len(evidence_refs_used),
        },
        "call_metadata": {
            "reproducibility": "deterministic-input-fingerprint",
            "canonical_input_sha256": canonical_input_sha,
            "reproducible_call_id": f"req034-{canonical_input_sha[:16]}",
            "canonical_input": canonical_input,
            "processing_call_id": processing_call_id,
            "llm_call_trace_schema_version": REQ_034_LLM_CALL_TRACE_SCHEMA_VERSION,
            "llm_call_trace_path": LLM_CALL_TRACE_RELATIVE_PATH,
            "llm_call_trace_sha256": llm_call_trace_sha,
            "llm_call_trace_rows": llm_call_trace_rows,
        },
    }


def validate_req_034_cross_call_memory_handoff_contract(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []

    if payload.get("ok") is not True:
        errors.append("ok must be true")
    if payload.get("tool") != TOOL:
        errors.append(f"tool must be {TOOL}")
    if payload.get("tool_version") != TOOL_VERSION:
        errors.append(f"tool_version must be {TOOL_VERSION}")
    if payload.get("schema_version") != REQ_034_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_034_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_034_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_034_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_034_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_034_ANALYSIS_TYPE}")
    if not _as_text(payload.get("call_id")):
        errors.append("call_id is required")
    if not _as_text(payload.get("checked_at_utc")):
        errors.append("checked_at_utc is required")

    handoff = payload.get("cross_call_memory_handoff")
    retained_memory_ids: list[str] = []
    superseded_memory_ids: list[str] = []
    evidence_refs_used: list[str] = []
    open_risks: list[Any] = []
    if not isinstance(handoff, Mapping):
        errors.append("cross_call_memory_handoff must be an object")
        handoff = {}
    else:
        target_project = handoff.get("target_project")
        if not isinstance(target_project, Mapping):
            errors.append("cross_call_memory_handoff.target_project must be an object")
        elif not _as_text(target_project.get("project_id")):
            errors.append("cross_call_memory_handoff.target_project.project_id is required")

        current_call = handoff.get("current_call")
        if not isinstance(current_call, Mapping):
            errors.append("cross_call_memory_handoff.current_call must be an object")
        else:
            current_call_id = _as_text(current_call.get("call_id"))
            if not current_call_id:
                errors.append("cross_call_memory_handoff.current_call.call_id is required")
            elif _as_text(payload.get("call_id")) != current_call_id:
                errors.append("call_id must match cross_call_memory_handoff.current_call.call_id")
            if not _as_text(current_call.get("objective")):
                errors.append("cross_call_memory_handoff.current_call.objective is required")

        source_calls = handoff.get("source_calls")
        if not isinstance(source_calls, list) or not source_calls or any(not _as_text(item) for item in source_calls):
            errors.append("cross_call_memory_handoff.source_calls must be a non-empty string array")
            source_calls = []

        handoff_items = handoff.get("handoff_items")
        if not isinstance(handoff_items, list):
            errors.append("cross_call_memory_handoff.handoff_items must be an array")
            handoff_items = []
        seen_memory_ids: set[str] = set()
        for index, row in enumerate(handoff_items):
            if not isinstance(row, Mapping):
                errors.append(f"cross_call_memory_handoff.handoff_items[{index}] must be an object")
                continue
            for key in REQ_034_REQUIRED_HANDOFF_FIELDS:
                if key not in row:
                    errors.append(f"cross_call_memory_handoff.handoff_items[{index}].{key} is required")
            memory_id = _as_text(row.get("memory_id"))
            if not memory_id:
                errors.append(f"cross_call_memory_handoff.handoff_items[{index}].memory_id is required")
            elif memory_id in seen_memory_ids:
                errors.append(f"cross_call_memory_handoff.handoff_items[{index}].memory_id must be unique")
            else:
                seen_memory_ids.add(memory_id)
                retained_memory_ids.append(memory_id)
            if _as_text(row.get("kind")) not in REQ_034_ALLOWED_ENTRY_KINDS:
                errors.append(
                    "cross_call_memory_handoff.handoff_items"
                    f"[{index}].kind must be one of {sorted(REQ_034_ALLOWED_ENTRY_KINDS)}"
                )
            if _as_text(row.get("source_call_id")) and _as_text(row.get("source_call_id")) not in source_calls:
                errors.append(
                    f"cross_call_memory_handoff.handoff_items[{index}].source_call_id must reference source_calls"
                )
            citation_refs = row.get("citation_refs")
            if not isinstance(citation_refs, list) or not citation_refs or any(not _as_text(item) for item in citation_refs):
                errors.append(
                    f"cross_call_memory_handoff.handoff_items[{index}].citation_refs must be a non-empty string array"
                )
            else:
                evidence_refs_used.extend([_as_text(item) for item in citation_refs])

        bounded_context = handoff.get("bounded_context")
        if not isinstance(bounded_context, Mapping):
            errors.append("cross_call_memory_handoff.bounded_context must be an object")
        else:
            max_entries = bounded_context.get("max_entries")
            max_citation_refs_per_entry = bounded_context.get("max_citation_refs_per_entry")
            if not isinstance(max_entries, int) or max_entries <= 0:
                errors.append("cross_call_memory_handoff.bounded_context.max_entries must be a positive integer")
            if not isinstance(max_citation_refs_per_entry, int) or max_citation_refs_per_entry <= 0:
                errors.append(
                    "cross_call_memory_handoff.bounded_context.max_citation_refs_per_entry must be a positive integer"
                )
            for key in (
                "source_call_count",
                "input_item_count",
                "retained_item_count",
                "dropped_item_count",
                "dropped_due_to_budget_count",
                "citation_ref_count",
                "citation_refs_truncated_count",
            ):
                value = bounded_context.get(key)
                if not isinstance(value, int) or value < 0:
                    errors.append(f"cross_call_memory_handoff.bounded_context.{key} must be a non-negative integer")
            if isinstance(max_entries, int) and len(retained_memory_ids) > max_entries:
                errors.append("cross_call_memory_handoff.handoff_items must stay within bounded_context.max_entries")
            if isinstance(max_citation_refs_per_entry, int):
                for index, row in enumerate(handoff_items):
                    if isinstance(row, Mapping) and isinstance(row.get("citation_refs"), list):
                        if len(row["citation_refs"]) > max_citation_refs_per_entry:
                            errors.append(
                                "cross_call_memory_handoff.handoff_items"
                                f"[{index}].citation_refs must not exceed bounded_context.max_citation_refs_per_entry"
                            )
            if bounded_context.get("retained_item_count") != len(retained_memory_ids):
                errors.append("cross_call_memory_handoff.bounded_context.retained_item_count must match handoff_items")
            if bounded_context.get("source_call_count") != len(source_calls):
                errors.append("cross_call_memory_handoff.bounded_context.source_call_count must match source_calls")
            if bounded_context.get("citation_ref_count") != len(evidence_refs_used):
                errors.append("cross_call_memory_handoff.bounded_context.citation_ref_count must match citation_refs used")

        summary = handoff.get("summary")
        if not isinstance(summary, Mapping):
            errors.append("cross_call_memory_handoff.summary must be an object")
        else:
            if summary.get("source_call_count") != len(source_calls):
                errors.append("cross_call_memory_handoff.summary.source_call_count must match source_calls")
            if summary.get("retained_item_count") != len(retained_memory_ids):
                errors.append("cross_call_memory_handoff.summary.retained_item_count must match handoff_items")

    processing_behavior = payload.get("processing_behavior")
    context_inputs: Mapping[str, Any] = {}
    if not isinstance(processing_behavior, Mapping):
        errors.append("processing_behavior must be an object")
    else:
        if processing_behavior.get("strategy") != REQ_034_PROCESSING_STRATEGY:
            errors.append(f"processing_behavior.strategy must be {REQ_034_PROCESSING_STRATEGY}")
        if processing_behavior.get("reasoning_mode") != REQ_034_REASONING_MODE:
            errors.append(f"processing_behavior.reasoning_mode must be {REQ_034_REASONING_MODE}")
        if processing_behavior.get("strict_evidence_discipline") is not True:
            errors.append("processing_behavior.strict_evidence_discipline must be true")
        context_inputs = processing_behavior.get("context_inputs") if isinstance(processing_behavior.get("context_inputs"), Mapping) else {}
        if not context_inputs:
            errors.append("processing_behavior.context_inputs must be an object")
        else:
            allowed_context_refs = context_inputs.get("allowed_context_refs")
            if (
                not isinstance(allowed_context_refs, list)
                or not allowed_context_refs
                or any(not _as_text(item) for item in allowed_context_refs)
            ):
                errors.append("processing_behavior.context_inputs.allowed_context_refs must be a non-empty string array")
            if not isinstance(context_inputs.get("memory_budget"), Mapping):
                errors.append("processing_behavior.context_inputs.memory_budget must be an object")
            chain_rows = context_inputs.get("call_chain")
            if not isinstance(chain_rows, list) or len(chain_rows) < 2:
                errors.append("processing_behavior.context_inputs.call_chain must contain at least two rows")
            prior_rows = context_inputs.get("prior_call_memory")
            if not isinstance(prior_rows, list) or not prior_rows:
                errors.append("processing_behavior.context_inputs.prior_call_memory must be a non-empty array")

        context_usage = processing_behavior.get("context_usage")
        if not isinstance(context_usage, Mapping):
            errors.append("processing_behavior.context_usage must be an object")
        else:
            for key in (
                "source_call_ids_used",
                "source_output_refs_used",
                "allowed_context_refs_used",
                "retained_memory_ids",
                "superseded_memory_ids",
                "open_risk_ids_emitted",
                "reason_codes_emitted",
                "evidence_refs_used",
            ):
                value = context_usage.get(key)
                if not isinstance(value, list) or any(not _as_text(item) for item in value):
                    errors.append(f"processing_behavior.context_usage.{key} must be a string array")
            if context_usage.get("retained_memory_ids") != retained_memory_ids:
                errors.append("processing_behavior.context_usage.retained_memory_ids must match handoff_items")
            superseded_memory_ids = context_usage.get("superseded_memory_ids") if isinstance(
                context_usage.get("superseded_memory_ids"), list
            ) else []
            if context_usage.get("evidence_refs_used") != sorted(set(evidence_refs_used)):
                errors.append("processing_behavior.context_usage.evidence_refs_used must match handoff citation refs")

        handoff_rules = processing_behavior.get("handoff_rules")
        if not isinstance(handoff_rules, Mapping):
            errors.append("processing_behavior.handoff_rules must be an object")
        else:
            if handoff_rules.get("required_handoff_fields") != REQ_034_REQUIRED_HANDOFF_FIELDS:
                errors.append("processing_behavior.handoff_rules.required_handoff_fields must match the canonical list")
            if handoff_rules.get("allowed_entry_kinds") != sorted(REQ_034_ALLOWED_ENTRY_KINDS):
                errors.append("processing_behavior.handoff_rules.allowed_entry_kinds must match the canonical list")
            if handoff_rules.get("contradiction_requires_supersession") is not True:
                errors.append("processing_behavior.handoff_rules.contradiction_requires_supersession must be true")
            if handoff_rules.get("citation_refs_required") is not True:
                errors.append("processing_behavior.handoff_rules.citation_refs_required must be true")

        diagnostics = processing_behavior.get("diagnostics")
        if not isinstance(diagnostics, Mapping):
            errors.append("processing_behavior.diagnostics must be an object")
        else:
            open_risks = diagnostics.get("open_risks")
            if not isinstance(open_risks, list):
                errors.append("processing_behavior.diagnostics.open_risks must be an array")
                open_risks = []
            for index, row in enumerate(open_risks):
                if not isinstance(row, Mapping):
                    errors.append(f"processing_behavior.diagnostics.open_risks[{index}] must be an object")
                    continue
                for key in ("risk_id", "reason_code", "summary", "memory_id", "memory_key", "source_call_id"):
                    if not _as_text(row.get(key)):
                        errors.append(f"processing_behavior.diagnostics.open_risks[{index}].{key} is required")
                required_citation_refs = row.get("required_citation_refs")
                if (
                    not isinstance(required_citation_refs, list)
                    or not required_citation_refs
                    or any(not _as_text(item) for item in required_citation_refs)
                ):
                    errors.append(
                        "processing_behavior.diagnostics.open_risks"
                        f"[{index}].required_citation_refs must be a non-empty string array"
                    )
            if isinstance(processing_behavior.get("context_usage"), Mapping):
                usage = processing_behavior["context_usage"]
                if usage.get("open_risk_ids_emitted") != [
                    _as_text(row.get("risk_id")) for row in open_risks if isinstance(row, Mapping)
                ]:
                    errors.append("processing_behavior.context_usage.open_risk_ids_emitted must match diagnostics.open_risks")
                if usage.get("reason_codes_emitted") != [
                    _as_text(row.get("reason_code")) for row in open_risks if isinstance(row, Mapping)
                ]:
                    errors.append("processing_behavior.context_usage.reason_codes_emitted must match diagnostics.open_risks")

    source = payload.get("source")
    if not isinstance(source, Mapping):
        errors.append("source must be an object")
    else:
        if source.get("retained_item_count") != len(retained_memory_ids):
            errors.append("source.retained_item_count must match handoff_items length")
        if source.get("open_risk_count") != len(open_risks):
            errors.append("source.open_risk_count must match diagnostics.open_risks length")
        if source.get("evidence_ref_count") != len(sorted(set(evidence_refs_used))):
            errors.append("source.evidence_ref_count must match unique citation refs in handoff_items")

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
            if metadata.get("llm_call_trace_schema_version") != REQ_034_LLM_CALL_TRACE_SCHEMA_VERSION:
                errors.append(
                    f"call_metadata.llm_call_trace_schema_version must be {REQ_034_LLM_CALL_TRACE_SCHEMA_VERSION}"
                )
            if metadata.get("llm_call_trace_path") != LLM_CALL_TRACE_RELATIVE_PATH:
                errors.append(f"call_metadata.llm_call_trace_path must be {LLM_CALL_TRACE_RELATIVE_PATH}")
            rows = metadata.get("llm_call_trace_rows")
            if not isinstance(rows, list):
                errors.append("call_metadata.llm_call_trace_rows must be an array")
                rows = []
            expected_trace_rows: list[dict[str, Any]] = []
            if isinstance(context_inputs, Mapping):
                chain_rows = context_inputs.get("call_chain")
                prior_rows = context_inputs.get("prior_call_memory")
                current_call = context_inputs.get("current_call")
                memory_budget = context_inputs.get("memory_budget")
                if (
                    isinstance(chain_rows, list)
                    and isinstance(prior_rows, list)
                    and isinstance(current_call, Mapping)
                    and isinstance(memory_budget, Mapping)
                ):
                    try:
                        expected_trace_rows = _build_req_034_llm_call_trace_rows(
                            processing_call_id=_require_text(
                                metadata.get("processing_call_id"),
                                field_name="call_metadata.processing_call_id",
                            ),
                            call_chain=[
                                _require_mapping(row, field_name=f"processing_behavior.context_inputs.call_chain[{index}]")
                                for index, row in enumerate(chain_rows)
                            ],
                            prior_call_memory=[
                                _require_mapping(
                                    row,
                                    field_name=f"processing_behavior.context_inputs.prior_call_memory[{index}]",
                                )
                                for index, row in enumerate(prior_rows)
                            ],
                            retained_items=[
                                _require_mapping(
                                    row,
                                    field_name=f"cross_call_memory_handoff.handoff_items[{index}]",
                                )
                                for index, row in enumerate(handoff.get("handoff_items", []))
                            ],
                            open_risks=[
                                _require_mapping(
                                    row,
                                    field_name=f"processing_behavior.diagnostics.open_risks[{index}]",
                                )
                                for index, row in enumerate(open_risks)
                            ],
                            current_call=_require_mapping(
                                current_call,
                                field_name="processing_behavior.context_inputs.current_call",
                            ),
                            max_entries=_req_034_require_positive_int(
                                memory_budget.get("max_entries"),
                                field_name="processing_behavior.context_inputs.memory_budget.max_entries",
                            ),
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



_req034_v2_build_req_034_cross_call_memory_handoff_contract = build_req_034_cross_call_memory_handoff_contract
_req034_v2_validate_req_034_cross_call_memory_handoff_contract = validate_req_034_cross_call_memory_handoff_contract


def build_req_034_cross_call_memory_handoff_contract(
    *,
    target_project: Mapping[str, Any] | None = None,
    current_call: Mapping[str, Any] | None = None,
    call_chain: Sequence[Mapping[str, Any]] | None = None,
    prior_call_memory: Sequence[Mapping[str, Any]] | None = None,
    allowed_context_refs: Sequence[str] | None = None,
    memory_budget: Mapping[str, Any] | None = None,
    analysis_type: str = REQ_034_ANALYSIS_TYPE,
    call_id: str | None = None,
    checked_at_utc: str | None = None,
    target_project_root: str | None = None,
    earth_root: str | None = None,
    output_root: str | None = None,
    revision_identity: str | None = None,
    strategy_goal: str | None = None,
    prior_call_handoffs: Sequence[Mapping[str, Any]] | None = None,
    candidate_recommendations: Sequence[Mapping[str, Any]] | None = None,
    cross_project_context: Sequence[Mapping[str, Any]] | None = None,
    target_project_evidence_refs: Sequence[Any] | None = None,
    earth_sweep_evidence_refs: Sequence[Any] | None = None,
) -> dict[str, Any]:
    if (
        target_project is not None
        or current_call is not None
        or prior_call_memory is not None
        or allowed_context_refs is not None
    ):
        return _req034_v2_build_req_034_cross_call_memory_handoff_contract(
            target_project=target_project,
            current_call=current_call,
            call_chain=call_chain or [],
            prior_call_memory=prior_call_memory or [],
            allowed_context_refs=allowed_context_refs or [],
            memory_budget=memory_budget,
            analysis_type=analysis_type,
            call_id=call_id,
            checked_at_utc=checked_at_utc,
        )
    return _legacy_build_req_034_cross_call_memory_handoff_contract(
        target_project_root=target_project_root,
        earth_root=earth_root,
        output_root=output_root,
        revision_identity=revision_identity,
        strategy_goal=strategy_goal,
        prior_call_handoffs=prior_call_handoffs or [],
        candidate_recommendations=candidate_recommendations or [],
        cross_project_context=cross_project_context,
        target_project_evidence_refs=target_project_evidence_refs,
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        call_id=call_id or "call-memory-handoff",
        checked_at_utc=checked_at_utc,
    )


def validate_req_034_cross_call_memory_handoff_contract(payload: Mapping[str, Any]) -> list[str]:
    if payload.get("ok") is True and isinstance(payload.get("cross_call_memory_handoff"), Mapping):
        return _req034_v2_validate_req_034_cross_call_memory_handoff_contract(payload)
    return _legacy_validate_req_034_cross_call_memory_handoff_contract(payload)

def _req_031_estimate_id(*, recommendation_id: str, kpi_id: str) -> str:
    return f"estimate::{recommendation_id}::{kpi_id}"


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
        expected_sequence = index + 1
        if sequence != expected_sequence:
            raise Req031Error(f"{field_name}[{index}].sequence must be {expected_sequence}")

        call_id = _require_text(row.get("call_id"), field_name=f"{field_name}[{index}].call_id")
        expected_call_id = f"call-{expected_sequence}"
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

    if len(normalized) != 6:
        raise Req031Error(f"{field_name} must contain exactly 6 rows for Call-6 KPI estimation")
    return normalized


def _req_031_normalize_recommendation_adoptions(
    value: Any,
    *,
    field_name: str = "recommendation_adoptions",
) -> list[dict[str, Any]]:
    if value is None:
        rows: Sequence[Any] = []
    else:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            raise Req031Error(f"{field_name} must be an array")
        rows = value

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_row in enumerate(rows):
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
    if value is None:
        rows: Sequence[Any] = []
    else:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            raise Req031Error(f"{field_name} must be an array")
        rows = value

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_row in enumerate(rows):
        row = _require_mapping(raw_row, field_name=f"{field_name}[{index}]")
        kpi_id = _require_text(row.get("kpi_id"), field_name=f"{field_name}[{index}].kpi_id")
        if not REQ_031_KPI_ID_RE.match(kpi_id):
            raise Req031Error(f"{field_name}[{index}].kpi_id must match {REQ_031_KPI_ID_RE.pattern}")
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
                "kpi_name": _require_text(row.get("kpi_name"), field_name=f"{field_name}[{index}].kpi_name"),
                "baseline_value": _require_number(
                    row.get("baseline_value"),
                    field_name=f"{field_name}[{index}].baseline_value",
                ),
                "unit": _require_text(row.get("unit"), field_name=f"{field_name}[{index}].unit"),
                "desired_direction": desired_direction,
                "evidence_refs": _normalize_string_list(
                    row.get("evidence_refs"),
                    field_name=f"{field_name}[{index}].evidence_refs",
                    min_items=1,
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
    if value is None:
        rows: Sequence[Any] = []
    else:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            raise Req031Error(f"{field_name} must be an array")
        rows = value

    normalized: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for index, raw_row in enumerate(rows):
        row = _require_mapping(raw_row, field_name=f"{field_name}[{index}]")
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
        if confidence not in REQ_031_ALLOWED_CONFIDENCE:
            raise Req031Error(
                f"{field_name}[{index}].confidence must be one of {sorted(REQ_031_ALLOWED_CONFIDENCE)}"
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
                "recommendation_id": recommendation_id,
                "kpi_id": kpi_id,
                "expected_movement_lower": expected_movement_lower,
                "expected_movement_upper": expected_movement_upper,
                "reasoning_summary": _require_text(
                    row.get("reasoning_summary"),
                    field_name=f"{field_name}[{index}].reasoning_summary",
                ),
                "confidence": confidence,
                "caveats": _normalize_string_list(
                    row.get("caveats"),
                    field_name=f"{field_name}[{index}].caveats",
                    min_items=1,
                ),
                "evidence_backed_assumptions": _normalize_string_list(
                    row.get("evidence_backed_assumptions"),
                    field_name=f"{field_name}[{index}].evidence_backed_assumptions",
                    min_items=1,
                ),
                "evidence_refs": evidence_refs,
            }
        )

    if not normalized:
        raise Req031Error(f"{field_name} must contain at least 1 item(s)")
    normalized.sort(key=lambda row: (row["recommendation_id"], row["kpi_id"]))
    return normalized


def _req_031_build_trace_rows(
    *,
    processing_call_id: str,
    call_chain: Sequence[Mapping[str, Any]],
    target_project_evidence_refs: Sequence[str],
    earth_sweep_evidence_refs: Sequence[str],
    estimate_ids: Sequence[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    base_input_refs = _collect_unique_refs(target_project_evidence_refs, earth_sweep_evidence_refs)
    prior_output_refs: list[str] = []
    for row in call_chain:
        sequence = int(row["sequence"])
        call_id = str(row["call_id"])
        output_ref = str(row["output_ref"])
        input_refs = _collect_unique_refs(base_input_refs, prior_output_refs)
        next_call_id = f"call-{sequence + 1}" if sequence < len(call_chain) else ""
        handoff_summary = (
            f"Call {sequence} hands off {output_ref} to {next_call_id} after consuming {len(input_refs)} input ref(s)."
            if next_call_id
            else (
                f"Call 6 emits kpi_estimates via {output_ref} for {len(estimate_ids)} recommendation/KPI pair(s)."
            )
        )
        rows.append(
            {
                "schema_version": REQ_031_LLM_CALL_TRACE_SCHEMA_VERSION,
                "requirement_id": REQ_031_REQUIREMENT_ID,
                "processing_call_id": processing_call_id,
                "call_id": call_id,
                "sequence": sequence,
                "call_objective": REQ_031_CALL_OBJECTIVES.get(call_id, str(row["phase"])),
                "input_refs": input_refs,
                "output_refs": [output_ref],
                "handoff_summary": handoff_summary,
            }
        )
        prior_output_refs.append(output_ref)
    return rows


def _req_031_canonical_input(
    *,
    target_project_root: str,
    earth_root: str,
    output_root: str,
    revision_identity: str,
    strategy_goal: str,
    call_id: str,
    checked_at_utc: str,
) -> dict[str, Any]:
    return {
        "runtime_mode": RUNTIME_MODE,
        "execution_mode": EXECUTION_MODE,
        "target_project_root": target_project_root,
        "earth_root": earth_root,
        "output_root": output_root,
        "revision_identity": revision_identity,
        "strategy_goal": strategy_goal,
        "analysis_type": REQ_031_ANALYSIS_TYPE,
        "call_id": call_id,
        "checked_at_utc": checked_at_utc,
    }


def _req_031_canonical_processing_input(
    *,
    call_chain: Sequence[Mapping[str, Any]],
    target_project_evidence_refs: Sequence[str],
    earth_sweep_evidence_refs: Sequence[str],
    recommendation_adoptions: Sequence[Mapping[str, Any]],
    kpi_definitions: Sequence[Mapping[str, Any]],
    impact_assumptions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "call_chain": [dict(row) for row in call_chain],
        "target_project_evidence_refs": list(target_project_evidence_refs),
        "earth_sweep_evidence_refs": list(earth_sweep_evidence_refs),
        "recommendation_adoptions": [dict(row) for row in recommendation_adoptions],
        "kpi_definitions": [dict(row) for row in kpi_definitions],
        "impact_assumptions": [dict(row) for row in impact_assumptions],
    }


def build_req_031_call_6_kpi_impact_estimation_reasoning(
    *,
    target_project_root: str,
    earth_root: str,
    output_root: str,
    revision_identity: str,
    strategy_goal: str,
    call_chain: Sequence[Mapping[str, Any]],
    recommendation_adoptions: Sequence[Mapping[str, Any]],
    kpi_definitions: Sequence[Mapping[str, Any]],
    impact_assumptions: Sequence[Mapping[str, Any]],
    target_project_evidence_refs: Sequence[Any] | None = None,
    earth_sweep_evidence_refs: Sequence[Any] | None = None,
    call_id: str = "call-6",
    checked_at_utc: str | None = None,
) -> dict[str, Any]:
    normalized_target_root = _normalize_root(target_project_root, field_name="target_project_root")
    normalized_earth_root = _normalize_root(earth_root, field_name="earth_root")
    normalized_output_root = _normalize_root(output_root, field_name="output_root")
    normalized_revision_identity = _require_text(revision_identity, field_name="revision_identity")
    normalized_strategy_goal = _require_text(strategy_goal, field_name="strategy_goal")
    normalized_call_id = _require_text(call_id, field_name="call_id")
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
    normalized_recommendation_adoptions = _req_031_normalize_recommendation_adoptions(recommendation_adoptions)
    normalized_kpi_definitions = _req_031_normalize_kpi_definitions(kpi_definitions)

    base_available_evidence_refs = set(
        _collect_unique_refs(
            normalized_target_refs,
            normalized_earth_refs,
            [row["output_ref"] for row in normalized_call_chain],
            *[row["evidence_refs"] for row in normalized_recommendation_adoptions],
            *[row["evidence_refs"] for row in normalized_kpi_definitions],
        )
    )
    normalized_impact_assumptions = _req_031_normalize_impact_assumptions(
        impact_assumptions,
        recommendation_ids={row["recommendation_id"] for row in normalized_recommendation_adoptions},
        kpi_ids={row["kpi_id"] for row in normalized_kpi_definitions},
        available_evidence_refs=base_available_evidence_refs,
    )

    adoption_by_id = {str(row["recommendation_id"]): row for row in normalized_recommendation_adoptions}
    kpi_by_id = {str(row["kpi_id"]): row for row in normalized_kpi_definitions}
    output_ref_by_sequence = {int(row["sequence"]): str(row["output_ref"]) for row in normalized_call_chain}
    call_5_output_ref = output_ref_by_sequence[5]

    blocked_recommendation_ids: set[str] = set()
    open_risks: list[dict[str, Any]] = []
    kpi_estimates: list[dict[str, Any]] = []
    for row in normalized_impact_assumptions:
        recommendation = adoption_by_id[str(row["recommendation_id"])]
        kpi = kpi_by_id[str(row["kpi_id"])]
        recommendation_id = str(recommendation["recommendation_id"])
        if recommendation["requires_earth_evidence"] and not normalized_earth_refs:
            blocked_recommendation_ids.add(recommendation_id)
            open_risks.append(
                {
                    "risk_id": f"risk-{recommendation_id}-earth-evidence",
                    "reason_code": "missing_earth_sweep_evidence_refs",
                    "summary": str(recommendation["summary"]),
                    "required_evidence_refs": _collect_unique_refs(
                        [call_5_output_ref],
                        recommendation["evidence_refs"],
                        row["evidence_refs"],
                    ),
                }
            )
            continue

        desired_direction = str(kpi["desired_direction"])
        lower = float(row["expected_movement_lower"])
        upper = float(row["expected_movement_upper"])
        if desired_direction == "increase" and lower < 0:
            raise Req031Error(
                f"impact_assumptions for {recommendation_id}/{kpi['kpi_id']} must stay non-negative for increase KPIs"
            )
        if desired_direction == "decrease" and upper > 0:
            raise Req031Error(
                f"impact_assumptions for {recommendation_id}/{kpi['kpi_id']} must stay non-positive for decrease KPIs"
            )

        baseline_value = float(kpi["baseline_value"])
        estimated_post_adoption_range = {
            "lower": baseline_value + lower,
            "upper": baseline_value + upper,
        }
        estimate_id = _req_031_estimate_id(recommendation_id=recommendation_id, kpi_id=str(kpi["kpi_id"]))
        kpi_estimates.append(
            {
                "estimate_id": estimate_id,
                "recommendation_id": recommendation_id,
                "recommendation_summary": str(recommendation["summary"]),
                "kpi_id": str(kpi["kpi_id"]),
                "kpi_name": str(kpi["kpi_name"]),
                "baseline_value": baseline_value,
                "unit": str(kpi["unit"]),
                "desired_direction": desired_direction,
                "adoption_status": str(recommendation["adoption_status"]),
                "adoption_window": str(recommendation["adoption_window"]),
                "expected_movement": {
                    "lower": lower,
                    "upper": upper,
                },
                "estimated_post_adoption_range": estimated_post_adoption_range,
                "reasoning_summary": str(row["reasoning_summary"]),
                "confidence": str(row["confidence"]),
                "caveats": list(row["caveats"]),
                "evidence_backed_assumptions": list(row["evidence_backed_assumptions"]),
                "evidence_refs": _collect_unique_refs(
                    recommendation["evidence_refs"],
                    kpi["evidence_refs"],
                    row["evidence_refs"],
                    [call_5_output_ref],
                ),
            }
        )

    kpi_estimates.sort(key=lambda row: (row["recommendation_id"], row["kpi_id"], row["estimate_id"]))
    open_risks.sort(key=lambda row: row["risk_id"])
    estimate_ids = [str(row["estimate_id"]) for row in kpi_estimates]
    low_confidence_estimate_ids = [
        str(row["estimate_id"]) for row in kpi_estimates if str(row["confidence"]) == "low"
    ]
    evidence_refs = _collect_unique_refs(
        normalized_target_refs,
        normalized_earth_refs,
        [row["output_ref"] for row in normalized_call_chain],
        *[row["evidence_refs"] for row in kpi_estimates],
        *[row["required_evidence_refs"] for row in open_risks],
    )
    if kpi_estimates and not open_risks:
        decision = "proceed"
    elif kpi_estimates and open_risks:
        decision = "proceed-with-open-risks"
    elif open_risks:
        decision = "blocked"
    else:
        decision = "insufficient-context"
    confidence = (
        "high"
        if kpi_estimates and not low_confidence_estimate_ids and not open_risks
        else "medium"
        if kpi_estimates
        else "low"
    )

    canonical_input = _req_031_canonical_input(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        output_root=normalized_output_root,
        revision_identity=normalized_revision_identity,
        strategy_goal=normalized_strategy_goal,
        call_id=normalized_call_id,
        checked_at_utc=normalized_checked_at_utc,
    )
    canonical_processing_input = _req_031_canonical_processing_input(
        call_chain=normalized_call_chain,
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        recommendation_adoptions=normalized_recommendation_adoptions,
        kpi_definitions=normalized_kpi_definitions,
        impact_assumptions=normalized_impact_assumptions,
    )
    processing_sha = _canonical_digest(canonical_processing_input)
    processing_call_id = f"req031-processing-{processing_sha[:16]}"
    llm_call_trace_rows = _req_031_build_trace_rows(
        processing_call_id=processing_call_id,
        call_chain=normalized_call_chain,
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        estimate_ids=estimate_ids,
    )

    return {
        "schema_version": REQ_031_SCHEMA_VERSION,
        "requirement_id": REQ_031_REQUIREMENT_ID,
        "analysis_type": REQ_031_ANALYSIS_TYPE,
        "call_id": normalized_call_id,
        "checked_at_utc": normalized_checked_at_utc,
        "processing_behavior": {
            "strategy": REQ_031_PROCESSING_STRATEGY,
            "reasoning_mode": REQ_031_REASONING_MODE,
            "strict_evidence_discipline": True,
            "context_inputs": {
                "call_chain": [dict(row) for row in normalized_call_chain],
                "target_project": {
                    "project_root": normalized_target_root,
                    "evidence_refs": list(normalized_target_refs),
                },
                "earth_sweep": {
                    "earth_root": normalized_earth_root,
                    "evidence_refs": list(normalized_earth_refs),
                },
                "recommendation_adoptions": [dict(row) for row in normalized_recommendation_adoptions],
                "kpi_definitions": [dict(row) for row in normalized_kpi_definitions],
                "impact_assumptions": [dict(row) for row in normalized_impact_assumptions],
            },
            "context_usage": {
                "call_ids_considered": [str(row["call_id"]) for row in normalized_call_chain],
                "recommendation_ids_considered": [
                    str(row["recommendation_id"]) for row in normalized_recommendation_adoptions
                ],
                "kpi_ids_considered": [str(row["kpi_id"]) for row in normalized_kpi_definitions],
                "estimate_ids_emitted": estimate_ids,
                "low_confidence_estimate_ids": low_confidence_estimate_ids,
                "blocked_recommendation_ids": sorted(blocked_recommendation_ids),
                "open_risk_ids_emitted": [str(row["risk_id"]) for row in open_risks],
                "evidence_refs_used": list(evidence_refs),
            },
            "kpi_impact_estimation": {
                "decision": decision,
                "rationale": (
                    f"estimates={len(kpi_estimates)} open_risks={len(open_risks)} "
                    f"blocked={len(blocked_recommendation_ids)} low_confidence={len(low_confidence_estimate_ids)}"
                ),
                "confidence": confidence,
                "evidence_refs": list(evidence_refs),
                "kpi_estimates": kpi_estimates,
                "open_risks": open_risks,
            },
        },
        "call_metadata": {
            "reproducibility": "deterministic-input-fingerprint",
            "canonical_input": canonical_input,
            "canonical_input_sha256": _canonical_digest(canonical_input),
            "reproducible_call_id": f"req031-{_canonical_digest(canonical_input)[:16]}",
            "canonical_processing_input": canonical_processing_input,
            "processing_input_sha256": processing_sha,
            "processing_call_id": processing_call_id,
            "llm_call_trace_schema_version": REQ_031_LLM_CALL_TRACE_SCHEMA_VERSION,
            "llm_call_trace_path": LLM_CALL_TRACE_RELATIVE_PATH,
            "llm_call_trace_sha256": _canonical_digest(llm_call_trace_rows),
            "llm_call_trace_rows": llm_call_trace_rows,
        },
    }


def validate_req_031_call_6_kpi_impact_estimation_reasoning(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    if payload.get("schema_version") != REQ_031_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_031_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_031_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_031_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_031_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_031_ANALYSIS_TYPE}")
    if _as_text(payload.get("call_id")) != "call-6":
        errors.append("call_id must be call-6")
    if not _as_text(payload.get("checked_at_utc")):
        errors.append("checked_at_utc is required")

    processing_behavior = payload.get("processing_behavior")
    if not isinstance(processing_behavior, Mapping):
        errors.append("processing_behavior must be an object")
        return errors
    if processing_behavior.get("strategy") != REQ_031_PROCESSING_STRATEGY:
        errors.append(f"processing_behavior.strategy must be {REQ_031_PROCESSING_STRATEGY}")
    if processing_behavior.get("reasoning_mode") != REQ_031_REASONING_MODE:
        errors.append(f"processing_behavior.reasoning_mode must be {REQ_031_REASONING_MODE}")
    if processing_behavior.get("strict_evidence_discipline") is not True:
        errors.append("processing_behavior.strict_evidence_discipline must be true")

    context_inputs = processing_behavior.get("context_inputs")
    normalized_call_chain: list[dict[str, Any]] = []
    normalized_target_refs: list[str] = []
    normalized_earth_refs: list[str] = []
    normalized_recommendation_adoptions: list[dict[str, Any]] = []
    normalized_kpi_definitions: list[dict[str, Any]] = []
    normalized_impact_assumptions: list[dict[str, Any]] = []
    if not isinstance(context_inputs, Mapping):
        errors.append("processing_behavior.context_inputs must be an object")
        return errors
    try:
        normalized_call_chain = _req_031_normalize_call_chain(context_inputs.get("call_chain"))
    except Req031Error as exc:
        errors.append(str(exc))
    target_project = context_inputs.get("target_project")
    if not isinstance(target_project, Mapping):
        errors.append("processing_behavior.context_inputs.target_project must be an object")
    else:
        normalized_target_refs = sorted(
            {_as_text(ref) for ref in target_project.get("evidence_refs", []) if _as_text(ref)}
        )
        if not _as_text(target_project.get("project_root")):
            errors.append("processing_behavior.context_inputs.target_project.project_root is required")
    earth_sweep = context_inputs.get("earth_sweep")
    if not isinstance(earth_sweep, Mapping):
        errors.append("processing_behavior.context_inputs.earth_sweep must be an object")
    else:
        normalized_earth_refs = sorted(
            {_as_text(ref) for ref in earth_sweep.get("evidence_refs", []) if _as_text(ref)}
        )
        if not _as_text(earth_sweep.get("earth_root")):
            errors.append("processing_behavior.context_inputs.earth_sweep.earth_root is required")
    try:
        normalized_recommendation_adoptions = _req_031_normalize_recommendation_adoptions(
            context_inputs.get("recommendation_adoptions")
        )
    except Req031Error as exc:
        errors.append(str(exc))
    try:
        normalized_kpi_definitions = _req_031_normalize_kpi_definitions(context_inputs.get("kpi_definitions"))
    except Req031Error as exc:
        errors.append(str(exc))
    available_evidence_refs = set(
        _collect_unique_refs(
            normalized_target_refs,
            normalized_earth_refs,
            [row["output_ref"] for row in normalized_call_chain],
            *[row["evidence_refs"] for row in normalized_recommendation_adoptions],
            *[row["evidence_refs"] for row in normalized_kpi_definitions],
        )
    )
    try:
        normalized_impact_assumptions = _req_031_normalize_impact_assumptions(
            context_inputs.get("impact_assumptions"),
            recommendation_ids={row["recommendation_id"] for row in normalized_recommendation_adoptions},
            kpi_ids={row["kpi_id"] for row in normalized_kpi_definitions},
            available_evidence_refs=available_evidence_refs,
        )
    except Req031Error as exc:
        errors.append(str(exc))

    estimation = processing_behavior.get("kpi_impact_estimation")
    if not isinstance(estimation, Mapping):
        errors.append("processing_behavior.kpi_impact_estimation must be an object")
        return errors
    if not isinstance(estimation.get("evidence_refs"), list):
        errors.append("processing_behavior.kpi_impact_estimation.evidence_refs must be a list")
    kpi_estimates = estimation.get("kpi_estimates")
    if not isinstance(kpi_estimates, list):
        errors.append("processing_behavior.kpi_impact_estimation.kpi_estimates must be a list")
        kpi_estimates = []
    for index, row in enumerate(kpi_estimates):
        if not isinstance(row, Mapping):
            errors.append(f"processing_behavior.kpi_impact_estimation.kpi_estimates[{index}] must be an object")
            continue
        estimate_id = _as_text(row.get("estimate_id"))
        if not REQ_031_ESTIMATE_ID_RE.match(estimate_id):
            errors.append(
                "processing_behavior.kpi_impact_estimation.kpi_estimates"
                f"[{index}].estimate_id must match {REQ_031_ESTIMATE_ID_RE.pattern}"
            )
        if not REQ_029_RECOMMENDATION_ID_RE.match(_as_text(row.get("recommendation_id"))):
            errors.append(
                f"processing_behavior.kpi_impact_estimation.kpi_estimates[{index}].recommendation_id must be valid"
            )
        if not REQ_031_KPI_ID_RE.match(_as_text(row.get("kpi_id"))):
            errors.append(f"processing_behavior.kpi_impact_estimation.kpi_estimates[{index}].kpi_id must be valid")
        if not _as_text(row.get("recommendation_summary")):
            errors.append(
                f"processing_behavior.kpi_impact_estimation.kpi_estimates[{index}].recommendation_summary is required"
            )
        if not _as_text(row.get("kpi_name")):
            errors.append(f"processing_behavior.kpi_impact_estimation.kpi_estimates[{index}].kpi_name is required")
        baseline_value = row.get("baseline_value")
        if isinstance(baseline_value, bool) or not isinstance(baseline_value, (int, float)):
            errors.append(
                f"processing_behavior.kpi_impact_estimation.kpi_estimates[{index}].baseline_value must be numeric"
            )
        if _as_text(row.get("desired_direction")) not in REQ_031_ALLOWED_DIRECTIONS:
            errors.append(
                f"processing_behavior.kpi_impact_estimation.kpi_estimates[{index}].desired_direction must be valid"
            )
        if _as_text(row.get("adoption_status")) not in REQ_031_ALLOWED_ADOPTION_STATUSES:
            errors.append(
                f"processing_behavior.kpi_impact_estimation.kpi_estimates[{index}].adoption_status must be valid"
            )
        if _as_text(row.get("confidence")) not in REQ_031_ALLOWED_CONFIDENCE:
            errors.append(
                f"processing_behavior.kpi_impact_estimation.kpi_estimates[{index}].confidence must be valid"
            )
        if not isinstance(row.get("expected_movement"), Mapping):
            errors.append(
                f"processing_behavior.kpi_impact_estimation.kpi_estimates[{index}].expected_movement must be an object"
            )
        if not isinstance(row.get("estimated_post_adoption_range"), Mapping):
            errors.append(
                "processing_behavior.kpi_impact_estimation.kpi_estimates"
                f"[{index}].estimated_post_adoption_range must be an object"
            )
        if not _as_text(row.get("reasoning_summary")):
            errors.append(
                f"processing_behavior.kpi_impact_estimation.kpi_estimates[{index}].reasoning_summary is required"
            )
        if not isinstance(row.get("caveats"), list) or not row.get("caveats"):
            errors.append(f"processing_behavior.kpi_impact_estimation.kpi_estimates[{index}].caveats must be non-empty")
        if (
            not isinstance(row.get("evidence_backed_assumptions"), list)
            or not row.get("evidence_backed_assumptions")
        ):
            errors.append(
                "processing_behavior.kpi_impact_estimation.kpi_estimates"
                f"[{index}].evidence_backed_assumptions must be non-empty"
            )
        if not isinstance(row.get("evidence_refs"), list) or not row.get("evidence_refs"):
            errors.append(
                f"processing_behavior.kpi_impact_estimation.kpi_estimates[{index}].evidence_refs must be non-empty"
            )

    open_risks = estimation.get("open_risks")
    if not isinstance(open_risks, list):
        errors.append("processing_behavior.kpi_impact_estimation.open_risks must be a list")
        open_risks = []
    for index, row in enumerate(open_risks):
        if not isinstance(row, Mapping):
            errors.append(f"processing_behavior.kpi_impact_estimation.open_risks[{index}] must be an object")
            continue
        if not _as_text(row.get("risk_id")):
            errors.append(f"processing_behavior.kpi_impact_estimation.open_risks[{index}].risk_id is required")
        if not _as_text(row.get("reason_code")):
            errors.append(f"processing_behavior.kpi_impact_estimation.open_risks[{index}].reason_code is required")
        if not isinstance(row.get("required_evidence_refs"), list) or not row.get("required_evidence_refs"):
            errors.append(
                "processing_behavior.kpi_impact_estimation.open_risks"
                f"[{index}].required_evidence_refs must be non-empty"
            )

    usage = processing_behavior.get("context_usage")
    if not isinstance(usage, Mapping):
        errors.append("processing_behavior.context_usage must be an object")
    else:
        for key in (
            "call_ids_considered",
            "recommendation_ids_considered",
            "kpi_ids_considered",
            "estimate_ids_emitted",
            "low_confidence_estimate_ids",
            "blocked_recommendation_ids",
            "open_risk_ids_emitted",
            "evidence_refs_used",
        ):
            value = usage.get(key)
            if not isinstance(value, list) or any(not _as_text(item) for item in value):
                errors.append(f"processing_behavior.context_usage.{key} must be a string array")

    metadata = payload.get("call_metadata")
    if not isinstance(metadata, Mapping):
        errors.append("call_metadata must be an object")
        return errors
    if metadata.get("reproducibility") != "deterministic-input-fingerprint":
        errors.append("call_metadata.reproducibility must be deterministic-input-fingerprint")
    canonical_input = metadata.get("canonical_input")
    if not isinstance(canonical_input, Mapping):
        errors.append("call_metadata.canonical_input must be an object")
    else:
        expected_canonical_input = _req_031_canonical_input(
            target_project_root=_as_text(context_inputs.get("target_project", {}).get("project_root"))
            if isinstance(context_inputs.get("target_project"), Mapping)
            else "",
            earth_root=_as_text(context_inputs.get("earth_sweep", {}).get("earth_root"))
            if isinstance(context_inputs.get("earth_sweep"), Mapping)
            else "",
            output_root=_as_text(canonical_input.get("output_root")),
            revision_identity=_as_text(canonical_input.get("revision_identity")),
            strategy_goal=_as_text(canonical_input.get("strategy_goal")),
            call_id=_as_text(payload.get("call_id")),
            checked_at_utc=_as_text(payload.get("checked_at_utc")),
        )
        if dict(canonical_input) != expected_canonical_input:
            errors.append("call_metadata.canonical_input must mirror normalized invocation anchors")
        expected_input_sha = _canonical_digest(expected_canonical_input)
        if metadata.get("canonical_input_sha256") != expected_input_sha:
            errors.append("call_metadata.canonical_input_sha256 does not match canonical input")
        if metadata.get("reproducible_call_id") != f"req031-{expected_input_sha[:16]}":
            errors.append("call_metadata.reproducible_call_id does not match canonical digest")

    canonical_processing_input = metadata.get("canonical_processing_input")
    if not isinstance(canonical_processing_input, Mapping):
        errors.append("call_metadata.canonical_processing_input must be an object")
    else:
        expected_processing_input = _req_031_canonical_processing_input(
            call_chain=normalized_call_chain,
            target_project_evidence_refs=normalized_target_refs,
            earth_sweep_evidence_refs=normalized_earth_refs,
            recommendation_adoptions=normalized_recommendation_adoptions,
            kpi_definitions=normalized_kpi_definitions,
            impact_assumptions=normalized_impact_assumptions,
        )
        if dict(canonical_processing_input) != expected_processing_input:
            errors.append("call_metadata.canonical_processing_input must mirror normalized estimation inputs")
        expected_processing_sha = _canonical_digest(expected_processing_input)
        if metadata.get("processing_input_sha256") != expected_processing_sha:
            errors.append("call_metadata.processing_input_sha256 does not match processing input")
        if metadata.get("processing_call_id") != f"req031-processing-{expected_processing_sha[:16]}":
            errors.append("call_metadata.processing_call_id does not match processing digest")

    if metadata.get("llm_call_trace_schema_version") != REQ_031_LLM_CALL_TRACE_SCHEMA_VERSION:
        errors.append(
            f"call_metadata.llm_call_trace_schema_version must be {REQ_031_LLM_CALL_TRACE_SCHEMA_VERSION}"
        )
    if metadata.get("llm_call_trace_path") != LLM_CALL_TRACE_RELATIVE_PATH:
        errors.append(f"call_metadata.llm_call_trace_path must be {LLM_CALL_TRACE_RELATIVE_PATH}")
    llm_call_trace_rows = metadata.get("llm_call_trace_rows")
    if not isinstance(llm_call_trace_rows, list):
        errors.append("call_metadata.llm_call_trace_rows must be a list")
    else:
        expected_trace_rows = _req_031_build_trace_rows(
            processing_call_id=_as_text(metadata.get("processing_call_id")),
            call_chain=normalized_call_chain,
            target_project_evidence_refs=normalized_target_refs,
            earth_sweep_evidence_refs=normalized_earth_refs,
            estimate_ids=[_as_text(row.get("estimate_id")) for row in kpi_estimates if isinstance(row, Mapping)],
        )
        if llm_call_trace_rows != expected_trace_rows:
            errors.append("call_metadata.llm_call_trace_rows must mirror deterministic trace rows")
        if metadata.get("llm_call_trace_sha256") != _canonical_digest(expected_trace_rows):
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
    normalized.sort(key=lambda row: (row["project_id"], row["project_root"], row["context_note"]))
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
    normalized.sort(
        key=lambda row: (
            row["recommendation_id"],
            row["recommendation_scope"],
            row["project_id"],
            row["summary"],
        )
    )
    return normalized


def _req_026_normalize_broad_sweep_context(value: Any, *, field_name: str) -> dict[str, Any]:
    if value is None:
        container: Mapping[str, Any] = {}
    else:
        container = _require_mapping(value, field_name=field_name)
    cross_project_context = _req_026_normalize_cross_project_context(
        container.get("cross_project_context", []),
        field_name=f"{field_name}.cross_project_context",
    )
    candidate_recommendations = _req_026_normalize_candidate_recommendations(
        container.get("candidate_recommendations", []),
        field_name=f"{field_name}.candidate_recommendations",
    )
    cross_project_context.sort(
        key=lambda row: (row["project_id"], row["project_root"], row["context_note"])
    )
    return {
        "earth_sweep_evidence_refs": _req_026_normalize_string_list(
            container.get("earth_sweep_evidence_refs", []),
            field_name=f"{field_name}.earth_sweep_evidence_refs",
        ),
        "cross_project_context": cross_project_context,
        "candidate_recommendations": candidate_recommendations,
        "strategic_claims": _normalize_strategic_claims(
            container.get("strategic_claims", []),
            call_depth=MAX_CALL_DEPTH,
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


def _req_026_claim_source_output_ref(*, source_call_sequence: int, phase: str) -> str:
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
    strategic_claims = list(broad_sweep_context.get("strategic_claims", []))
    context_by_project = {
        str(row["project_id"]): row for row in cross_project_context
    }
    cross_project_refs = _req_026_dedupe_preserving_order(
        [ref for row in cross_project_context for ref in row["evidence_refs"]]
    )
    available_citation_refs = set(
        _req_026_dedupe_preserving_order(
            list(planning_refs)
            + list(runtime_refs)
            + list(earth_sweep_evidence_refs)
            + cross_project_refs
            + [ref for row in candidate_recommendations for ref in row["evidence_refs"]]
        )
    )

    recommended_next_actions: list[dict[str, Any]] = []
    cross_project_obligations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []

    claim_rows_by_id: dict[str, list[dict[str, Any]]] = {}
    for claim in strategic_claims:
        claim_rows_by_id.setdefault(str(claim["claim_id"]), []).append(claim)
        citation_refs = list(claim["evidence_refs"])
        if not citation_refs or not set(citation_refs).issubset(available_citation_refs):
            open_risks.append(
                {
                    "risk_id": f"risk-claim-{claim['claim_id']}-citation",
                    "reason_code": "uncited_strategic_claim",
                    "summary": str(claim["summary"]),
                    "required_evidence_refs": _req_026_dedupe_preserving_order(
                        [
                            _req_026_claim_source_output_ref(
                                source_call_sequence=int(claim["source_call_sequence"]),
                                phase=str(claim["phase"]),
                            )
                        ]
                        + citation_refs
                    ),
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
                    "summary": str(synthesis_row["summary"]),
                    "required_evidence_refs": _req_026_dedupe_preserving_order(
                        [
                            _req_026_claim_source_output_ref(
                                source_call_sequence=int(analysis_row["source_call_sequence"]),
                                phase=str(analysis_row["phase"]),
                            ),
                            _req_026_claim_source_output_ref(
                                source_call_sequence=int(synthesis_row["source_call_sequence"]),
                                phase=str(synthesis_row["phase"]),
                            ),
                        ]
                        + list(analysis_row["evidence_refs"])
                        + list(synthesis_row["evidence_refs"])
                    ),
                }
                break
            if contradiction_row is not None:
                break
        if contradiction_row is not None:
            open_risks.append(
                {
                    "risk_id": f"risk-claim-{claim_id}-contradiction",
                    "reason_code": "cross_call_contradiction",
                    "summary": contradiction_row["summary"],
                    "required_evidence_refs": contradiction_row["required_evidence_refs"],
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

    recommended_next_actions.sort(key=lambda row: str(row["recommendation_id"]))
    cross_project_obligations.sort(key=lambda row: str(row["obligation_id"]))
    open_risks.sort(key=lambda row: str(row["risk_id"]))

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
            _req_026_claim_source_output_ref(
                source_call_sequence=int(row["source_call_sequence"]),
                phase=str(row["phase"]),
            )
            for row in broad_sweep_context.get("strategic_claims", [])
        ]
        + [
            ref
            for row in broad_sweep_context.get("strategic_claims", [])
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

    context_inputs = processing_behavior.get("context_inputs")
    if not isinstance(context_inputs, Mapping):
        errors.append("processing_behavior.context_inputs must be an object")
        context_inputs = {}
    broad_sweep_context = context_inputs.get("broad_sweep_context")
    if not isinstance(broad_sweep_context, Mapping):
        errors.append("processing_behavior.context_inputs.broad_sweep_context must be an object")
        broad_sweep_context = {}
    for key in ("earth_sweep_evidence_refs", "cross_project_context", "candidate_recommendations"):
        if not isinstance(broad_sweep_context.get(key), list):
            errors.append(f"processing_behavior.context_inputs.broad_sweep_context.{key} must be an array")

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

def _normalize_req_032_policy_decision(value: Any, *, field_name: str) -> str:
    decision = _require_text(value, field_name=field_name).lower()
    if decision not in {"monitor", "mitigate-locally", "fallback-then-escalate", "escalate-immediately"}:
        raise ValueError(
            f"{field_name} must be monitor|mitigate-locally|fallback-then-escalate|escalate-immediately"
        )
    return decision

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

def _normalize_req_032_call_sequence(raw_value: Any) -> int:
    if isinstance(raw_value, bool) or not isinstance(raw_value, int):
        raise ValueError("call_sequence must be an integer")
    if raw_value != REQ_032_CALL_SEQUENCE:
        raise ValueError(f"call_sequence must be {REQ_032_CALL_SEQUENCE}")
    return raw_value

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

def _slug_id_fragment(value: Any) -> str:
    text = _as_text(value).lower()
    chars = [ch if ch.isalnum() else "-" for ch in text]
    collapsed = "".join(chars).strip("-")
    while "--" in collapsed:
        collapsed = collapsed.replace("--", "-")
    return collapsed or "unknown"

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

def _normalize_req_033_strategic_claims(raw_value: Any) -> list[dict[str, Any]]:
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
        normalized.append(
            {
                "claim_id": claim_id,
                "phase": phase,
                "summary": summary,
                "position": position,
                "source_output_ref": source_output_ref,
                "evidence_refs": _normalize_string_list(
                    item.get("evidence_refs"),
                    field_name=f"strategic_claims[{index}].evidence_refs",
                ),
            }
        )
    normalized.sort(key=lambda row: (row["claim_id"], row["phase"], row["source_output_ref"], row["position"]))
    return normalized

def _normalize_req_033_call_sequence(raw_value: Any) -> int:
    if isinstance(raw_value, bool) or not isinstance(raw_value, int):
        raise ValueError("call_sequence must be an integer")
    if raw_value != REQ_033_CALL_SEQUENCE:
        raise ValueError(f"call_sequence must be {REQ_033_CALL_SEQUENCE}")
    return raw_value

def _collect_req_033_trace_input_refs(canonical_processing_input: Mapping[str, Any]) -> list[str]:
    cross_project_context = canonical_processing_input.get("cross_project_context")
    constraint_candidates = canonical_processing_input.get("constraint_candidates")
    strategic_claims = canonical_processing_input.get("strategic_claims")

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
    if isinstance(strategic_claims, Sequence) and not isinstance(strategic_claims, (str, bytes, bytearray)):
        for row in strategic_claims:
            if not isinstance(row, Mapping):
                continue
            source_output_ref = _as_text(row.get("source_output_ref"))
            if source_output_ref:
                source_output_refs.append(source_output_ref)

    required_evidence_refs = canonical_processing_input.get("required_evidence_refs")
    if not isinstance(required_evidence_refs, Sequence) or isinstance(required_evidence_refs, (str, bytes, bytearray)):
        required_evidence_refs = []

    return _collect_unique_refs(
        [_as_text(ref) for ref in required_evidence_refs if _as_text(ref)],
        source_output_refs,
        *(_rows_to_evidence_refs(cross_project_context)),
        *(_rows_to_evidence_refs(constraint_candidates)),
        *(_rows_to_evidence_refs(strategic_claims)),
    )

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
    strategic_claims: list[dict[str, Any]],
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
        "strategic_claims": [
            {
                "claim_id": row["claim_id"],
                "phase": row["phase"],
                "summary": row["summary"],
                "position": row["position"],
                "source_output_ref": row["source_output_ref"],
                "evidence_refs": list(row["evidence_refs"]),
            }
            for row in strategic_claims
        ],
    }

def _req_033_recommendation_id(candidate_id: str) -> str:
    return f"rec-call-8-{_slug_id_fragment(candidate_id)}"

def _req_033_recommendation_decision(
    *,
    planner_contract: Mapping[str, Any],
    open_risks: Sequence[Mapping[str, Any]],
) -> str:
    reason_codes = {_as_text(row.get("reason_code")) for row in open_risks}
    if {"cross_call_contradiction", "uncited_strategic_claim"}.intersection(reason_codes):
        return "resolve-strategy-gaps"
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
    if decision == "resolve-strategy-gaps":
        return "Contradictory or uncited strategy claims must be resolved before planner-facing classifications can be trusted."
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
    strategic_claims: list[dict[str, Any]],
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
            "recommendation_id": _req_033_recommendation_id(row["candidate_id"]),
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
            "recommendation_id": _req_033_recommendation_id(row["candidate_id"]),
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
            "recommendation_id": _req_033_recommendation_id(row["candidate_id"]),
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

    available_citation_refs = set(
        _collect_unique_refs(
            target_project_evidence_refs,
            earth_sweep_evidence_refs,
            cross_project_refs,
            *[row["evidence_refs"] for row in classification_reasoning],
        )
    )

    open_risks: list[dict[str, Any]] = []
    claim_rows_by_id: dict[str, list[dict[str, Any]]] = {}
    for claim in strategic_claims:
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
            "strategic_claims": [
                {
                    "claim_id": row["claim_id"],
                    "phase": row["phase"],
                    "summary": row["summary"],
                    "position": row["position"],
                    "source_output_ref": row["source_output_ref"],
                    "evidence_refs": list(row["evidence_refs"]),
                }
                for row in strategic_claims
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
    output_refs = [
        _build_call_output_ref(
            plan_id=plan_id,
            call_id=call_id,
            expected_output=expected_output,
        )
        for expected_output in (REQ_033_TRACE_EXPECTED_OUTPUT, *REQ_033_TRACE_BUCKET_OUTPUTS)
    ]
    primary_output_ref = output_refs[0]
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
            "output_refs": output_refs,
            "handoff_summary": (
                f"Call {REQ_033_CALL_SEQUENCE} hands off {REQ_033_TRACE_EXPECTED_OUTPUT} via {primary_output_ref} "
                "with explicit bucket outputs for hard constraints, soft preferences, speculative ideas, "
                "and planner contract reuse "
                f"after classifying {hard_constraint_count} hard constraint(s), "
                f"{soft_preference_count} soft preference(s), and {speculative_idea_count} speculative idea(s)."
            ),
        }
    ]

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
    strategic_claims: Sequence[Mapping[str, Any]] | None = None,
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
    normalized_strategic_claims = _normalize_req_033_strategic_claims(strategic_claims)

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
        strategic_claims=normalized_strategic_claims,
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
        strategic_claims=normalized_strategic_claims,
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
    normalized_strategic_claims: list[dict[str, Any]] = []
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
        try:
            normalized_strategic_claims = _normalize_req_033_strategic_claims(
                context_inputs.get("strategic_claims")
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
                strategic_claims=normalized_strategic_claims,
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
                        *[row["evidence_refs"] for row in normalized_strategic_claims],
                    )
                )
            ),
            target_project_evidence_refs=normalized_target_project_refs,
            earth_sweep_evidence_refs=normalized_earth_sweep_refs,
            cross_project_context=normalized_cross_project_context,
            constraint_candidates=normalized_constraint_candidates,
            strategic_claims=normalized_strategic_claims,
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

def _normalize_req_028_call_sequence(raw_value: Any) -> int:
    if isinstance(raw_value, bool) or not isinstance(raw_value, int):
        raise ValueError("call_sequence must be an integer")
    if raw_value != REQ_028_CALL_SEQUENCE:
        raise ValueError(f"call_sequence must be {REQ_028_CALL_SEQUENCE}")
    return raw_value

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

def _detect_requirement(payload: Mapping[str, Any]) -> str:
    analysis_type = _as_text(payload.get("analysis_type"))
    surface = _as_text(payload.get("surface"))
    requirement_id = _as_text(payload.get("requirement_id"))

    if payload.get("analysis_type") == REQ_046_ANALYSIS_TYPE or "validated_call_outputs" in payload:
        return REQ_046_REQUIREMENT_ID
    if analysis_type == REQ_047_ANALYSIS_TYPE or (
        "llm_call_trace_rows" in payload and "decision_ledger" in payload and "final_output_artifacts" in payload
    ):
        return REQ_047_REQUIREMENT_ID
    if analysis_type == REQ_039_ANALYSIS_TYPE or (
        "quality_policy" in payload and "recommendations" in payload and "now_utc" in payload
    ):
        return REQ_039_REQUIREMENT_ID
    if "priority_weights" in payload and "recommendations" in payload:
        return REQ_038_REQUIREMENT_ID
    if requirement_id == REQ_041_REQUIREMENT_ID or surface == REQ_041_SURFACE:
        return REQ_041_REQUIREMENT_ID
    if (
        "resource_constraints" in payload
        and "dependency_readiness" in payload
        and "repo_maturity" in payload
        and "candidate_recommendations" in payload
    ):
        return REQ_040_REQUIREMENT_ID
    if (
        "active_project_id" in payload
        and "existing_functionality_candidates" in payload
        and "build_new_assessment" in payload
    ):
        return REQ_042_REQUIREMENT_ID
    if analysis_type == REQ_044_ANALYSIS_TYPE or (
        "mission_required_recommendation_classes" in payload
        and "ecosystem_required_recommendation_classes" in payload
        and "candidate_recommendations" in payload
    ):
        return REQ_044_REQUIREMENT_ID
    if analysis_type == REQ_043_ANALYSIS_TYPE or (
        "project_obligation_candidates" in payload and "target_project_profile" in payload
    ):
        return REQ_043_REQUIREMENT_ID
    if analysis_type == REQ_045_ANALYSIS_TYPE or (
        "scenario_candidates" in payload and "uncertainty_score" in payload and "conflict_score" in payload
    ):
        return REQ_045_REQUIREMENT_ID
    if payload.get("analysis_type") == REQ_035_ANALYSIS_TYPE:
        return REQ_035_REQUIREMENT_ID
    if "recommendation_drafts" in payload:
        return REQ_037_REQUIREMENT_ID
    if "constraint_candidates" in payload:
        return REQ_033_REQUIREMENT_ID
    if "blocker_candidates" in payload or "risk_policy_candidates" in payload:
        return REQ_032_REQUIREMENT_ID
    if (
        "local_mission_summary" in payload
        or "gap_candidates" in payload
        or "opportunity_candidates" in payload
        or "unresolved_ideas" in payload
    ):
        return REQ_028_REQUIREMENT_ID
    if payload.get("analysis_type") == REQ_031_ANALYSIS_TYPE or "impact_assumptions" in payload:
        return REQ_031_REQUIREMENT_ID
    if payload.get("analysis_type") == REQ_027_ANALYSIS_TYPE:
        return REQ_027_REQUIREMENT_ID
    if "call_outputs" in payload and "contradiction_resolutions" in payload:
        return REQ_036_REQUIREMENT_ID
    if payload.get("analysis_type") == REQ_030_ANALYSIS_TYPE or "candidate_lane_designs" in payload:
        return REQ_030_REQUIREMENT_ID
    if payload.get("analysis_type") == REQ_034_ANALYSIS_TYPE or "prior_call_handoffs" in payload:
        return REQ_034_REQUIREMENT_ID
    if payload.get("analysis_type") == REQ_029_ANALYSIS_TYPE or "call_chain" in payload:
        return REQ_029_REQUIREMENT_ID
    if "target_project_root" in payload:
        return REQ_025_REQUIREMENT_ID
    if "target_project" in payload or payload.get("analysis_type") == REQ_026_ANALYSIS_TYPE:
        return REQ_026_REQUIREMENT_ID
    raise ValueError(
        "input payload does not match REQ-025, REQ-026, REQ-027, REQ-028, REQ-029, REQ-030, REQ-031, REQ-032, "
        "REQ-033, REQ-034, REQ-035, REQ-036, REQ-037, REQ-038, REQ-039, REQ-040, REQ-041, REQ-042, REQ-043, "
        "REQ-044, REQ-045, REQ-046, or REQ-047 contract anchors"
    )


def run(payload: Mapping[str, Any], *, trace_root: str | Path | None = None) -> dict[str, Any]:
    requirement_id = _detect_requirement(payload)
    if requirement_id == REQ_046_REQUIREMENT_ID:
        return build_req_046_final_strategy_synthesis_composer(payload)
    if requirement_id == REQ_047_REQUIREMENT_ID:
        return build_req_047_llm_call_trace_and_decision_ledger(dict(payload))
    if requirement_id == REQ_045_REQUIREMENT_ID:
        return build_req_045_alternative_strategic_scenario_generator(
            generated_at_utc=payload.get("generated_at_utc"),
            target_project_root=payload.get("target_project_root"),
            earth_root=payload.get("earth_root"),
            output_root=payload.get("output_root"),
            revision_identity=payload.get("revision_identity"),
            strategy_goal=payload.get("strategy_goal"),
            uncertainty_score=payload.get("uncertainty_score"),
            conflict_score=payload.get("conflict_score"),
            scenario_candidates=payload.get("scenario_candidates"),
            uncertainty_signals=payload.get("uncertainty_signals"),
            conflict_signals=payload.get("conflict_signals"),
            target_project_evidence_refs=payload.get("target_project_evidence_refs"),
            earth_sweep_evidence_refs=payload.get("earth_sweep_evidence_refs"),
        )
    if requirement_id == REQ_044_REQUIREMENT_ID:
        return build_req_044_recommendation_omission_detector(
            target_project_root=payload.get("target_project_root"),
            earth_root=payload.get("earth_root"),
            output_root=payload.get("output_root"),
            revision_identity=payload.get("revision_identity"),
            strategy_goal=payload.get("strategy_goal"),
            mission_required_recommendation_classes=payload.get("mission_required_recommendation_classes"),
            ecosystem_required_recommendation_classes=payload.get("ecosystem_required_recommendation_classes"),
            candidate_recommendations=payload.get("candidate_recommendations"),
            call_chain=payload.get("call_chain"),
            strategic_claims=payload.get("strategic_claims"),
            cross_project_context=payload.get("cross_project_context"),
            target_project_evidence_refs=payload.get("target_project_evidence_refs"),
            earth_sweep_evidence_refs=payload.get("earth_sweep_evidence_refs"),
            call_id=_as_text(payload.get("call_id")) or None,
            checked_at_utc=_as_text(payload.get("checked_at_utc")) or None,
        )
    if requirement_id == REQ_043_REQUIREMENT_ID:
        return build_req_043_project_obligation_reasoning(
            target_project_root=payload.get("target_project_root"),
            earth_root=payload.get("earth_root"),
            output_root=payload.get("output_root"),
            revision_identity=payload.get("revision_identity"),
            strategy_goal=payload.get("strategy_goal"),
            target_project_profile=payload.get("target_project_profile"),
            project_obligation_candidates=payload.get("project_obligation_candidates"),
            call_chain=payload.get("call_chain"),
            strategic_claims=payload.get("strategic_claims"),
            cross_project_context=payload.get("cross_project_context"),
            target_project_evidence_refs=payload.get("target_project_evidence_refs"),
            earth_sweep_evidence_refs=payload.get("earth_sweep_evidence_refs"),
            call_id=_as_text(payload.get("call_id")) or None,
            checked_at_utc=_as_text(payload.get("checked_at_utc")) or None,
        )
    if requirement_id == REQ_042_REQUIREMENT_ID:
        return build_req_042_existing_functionality_interaction_reasoning(
            target_project_root=payload.get("target_project_root"),
            earth_root=payload.get("earth_root"),
            active_project_id=payload.get("active_project_id"),
            capability_need=payload.get("capability_need"),
            build_new_assessment=payload.get("build_new_assessment"),
            existing_functionality_candidates=payload.get("existing_functionality_candidates"),
            target_project_evidence_refs=payload.get("target_project_evidence_refs"),
            earth_sweep_evidence_refs=payload.get("earth_sweep_evidence_refs"),
            cross_project_context=payload.get("cross_project_context"),
            strategic_claims=payload.get("strategic_claims"),
            evaluated_at=payload.get("evaluated_at"),
        )
    if requirement_id == REQ_041_REQUIREMENT_ID:
        effective_trace_root = trace_root or payload.get("trace_root")
        return build_req_041_recommendation_dependency_effect_modeling(
            target_project_root=payload.get("target_project_root", DEFAULT_TARGET_PROJECT_ROOT),
            earth_root=payload.get("earth_root", DEFAULT_EARTH_ROOT),
            output_root=payload.get("output_root", DEFAULT_OUTPUT_ROOT),
            revision_identity=payload.get("revision_identity", _req38_41.DEFAULT_REQ_041_REVISION_ID),
            recommendations=payload.get("recommendations"),
            broad_sweep_context=payload.get("broad_sweep_context"),
            modeled_at=payload.get("modeled_at"),
            persist_llm_call_trace=bool(effective_trace_root) or bool(payload.get("persist_llm_call_trace")),
            trace_root=effective_trace_root,
        )
    if requirement_id == REQ_040_REQUIREMENT_ID:
        return build_req_040_recommendation_feasibility_scoring(
            target_project_root=payload.get("target_project_root"),
            earth_root=payload.get("earth_root"),
            output_root=payload.get("output_root"),
            revision_identity=payload.get("revision_identity"),
            resource_constraints=payload.get("resource_constraints"),
            dependency_readiness=payload.get("dependency_readiness"),
            repo_maturity=payload.get("repo_maturity"),
            candidate_recommendations=payload.get("candidate_recommendations"),
            llm_call_trace_path=payload.get("llm_call_trace_path", _req40.REQ_040_DEFAULT_LLM_CALL_TRACE_PATH),
            persist_llm_call_trace=bool(payload.get("persist_llm_call_trace", True)),
        )
    if requirement_id == REQ_039_REQUIREMENT_ID:
        return build_req_039_recommendation_rationale_quality_scoring(dict(payload))
    if requirement_id == REQ_038_REQUIREMENT_ID:
        effective_trace_root = trace_root or payload.get("trace_root")
        return build_req_038_recommendation_priority_calibration(
            target_project_root=payload.get("target_project_root", DEFAULT_TARGET_PROJECT_ROOT),
            earth_root=payload.get("earth_root", DEFAULT_EARTH_ROOT),
            output_root=payload.get("output_root", DEFAULT_OUTPUT_ROOT),
            revision_identity=payload.get("revision_identity", _req38_41.DEFAULT_REQ_038_REVISION_ID),
            recommendations=payload.get("recommendations"),
            priority_weights=payload.get("priority_weights"),
            broad_sweep_context=payload.get("broad_sweep_context"),
            calibrated_at=payload.get("calibrated_at"),
            persist_llm_call_trace=bool(effective_trace_root) or bool(payload.get("persist_llm_call_trace")),
            trace_root=effective_trace_root,
        )
    if requirement_id == REQ_036_REQUIREMENT_ID:
        return build_req_036_cross_call_contradiction_detection(**dict(payload))
    if requirement_id == REQ_035_REQUIREMENT_ID:
        return build_req_035_evidence_citation_discipline_in_reasoning_calls(dict(payload))
    if requirement_id == REQ_037_REQUIREMENT_ID:
        return build_req_037_recommendation_deduplication_and_merge(
            recommendation_drafts=payload.get("recommendation_drafts"),
            strategic_claims=payload.get("strategic_claims"),
            target_project_root=payload.get("target_project_root", DEFAULT_TARGET_PROJECT_ROOT),
            earth_root=payload.get("earth_root", DEFAULT_EARTH_ROOT),
            output_root=payload.get("output_root", DEFAULT_OUTPUT_ROOT),
            revision_identity=payload.get("revision_identity", DEFAULT_REQ_037_REVISION_ID),
            target_project_evidence_refs=payload.get("target_project_evidence_refs"),
            earth_sweep_evidence_refs=payload.get("earth_sweep_evidence_refs"),
            cross_project_context=payload.get("cross_project_context"),
            merged_at=_as_text(payload.get("merged_at")) or None,
        )
    if requirement_id == REQ_033_REQUIREMENT_ID:
        return build_req_033_call_8_constraint_classification_reasoning(
            target_project_root=payload.get("target_project_root", DEFAULT_TARGET_PROJECT_ROOT),
            earth_root=payload.get("earth_root", DEFAULT_EARTH_ROOT),
            output_root=payload.get("output_root", DEFAULT_OUTPUT_ROOT),
            revision_identity=payload.get("revision_identity", DEFAULT_REQ_033_REVISION_ID),
            strategy_goal=payload.get("strategy_goal"),
            call_sequence=payload.get("call_sequence", REQ_033_CALL_SEQUENCE),
            evidence_refs=payload.get("evidence_refs"),
            target_project_evidence_refs=payload.get("target_project_evidence_refs"),
            earth_sweep_evidence_refs=payload.get("earth_sweep_evidence_refs"),
            cross_project_context=payload.get("cross_project_context"),
            constraint_candidates=payload.get("constraint_candidates"),
            strategic_claims=payload.get("strategic_claims"),
        )
    if requirement_id == REQ_032_REQUIREMENT_ID:
        return build_req_032_call_7_blocker_and_risk_policy_reasoning(
            target_project_root=payload.get("target_project_root", DEFAULT_TARGET_PROJECT_ROOT),
            earth_root=payload.get("earth_root", DEFAULT_EARTH_ROOT),
            output_root=payload.get("output_root", DEFAULT_OUTPUT_ROOT),
            revision_identity=payload.get("revision_identity", DEFAULT_REQ_032_REVISION_ID),
            strategy_goal=payload.get("strategy_goal"),
            call_sequence=payload.get("call_sequence", REQ_032_CALL_SEQUENCE),
            evidence_refs=payload.get("evidence_refs"),
            target_project_evidence_refs=payload.get("target_project_evidence_refs"),
            earth_sweep_evidence_refs=payload.get("earth_sweep_evidence_refs"),
            cross_project_context=payload.get("cross_project_context"),
            blocker_candidates=payload.get("blocker_candidates"),
            risk_policy_candidates=payload.get("risk_policy_candidates"),
            strategic_claims=payload.get("strategic_claims"),
        )
    if requirement_id == REQ_028_REQUIREMENT_ID:
        return build_req_028_call_3_gap_and_opportunity_reasoning(
            target_project_root=payload.get("target_project_root"),
            earth_root=payload.get("earth_root"),
            output_root=payload.get("output_root"),
            revision_identity=payload.get("revision_identity"),
            strategy_goal=payload.get("strategy_goal"),
            call_sequence=payload.get("call_sequence", REQ_028_CALL_SEQUENCE),
            evidence_refs=payload.get("evidence_refs"),
            target_project_evidence_refs=payload.get("target_project_evidence_refs"),
            earth_sweep_evidence_refs=payload.get("earth_sweep_evidence_refs"),
            local_mission_summary=payload.get("local_mission_summary"),
            cross_project_context=payload.get("cross_project_context"),
            unresolved_ideas=payload.get("unresolved_ideas"),
            gap_candidates=payload.get("gap_candidates"),
            opportunity_candidates=payload.get("opportunity_candidates"),
            strategic_claims=payload.get("strategic_claims"),
        )
    if requirement_id == REQ_031_REQUIREMENT_ID:
        return build_req_031_call_6_kpi_impact_estimation_reasoning(
            target_project_root=payload.get("target_project_root"),
            earth_root=payload.get("earth_root"),
            output_root=payload.get("output_root"),
            revision_identity=payload.get("revision_identity"),
            strategy_goal=payload.get("strategy_goal"),
            call_chain=payload.get("call_chain"),
            recommendation_adoptions=payload.get("recommendation_adoptions"),
            kpi_definitions=payload.get("kpi_definitions"),
            impact_assumptions=payload.get("impact_assumptions"),
            target_project_evidence_refs=payload.get("target_project_evidence_refs"),
            earth_sweep_evidence_refs=payload.get("earth_sweep_evidence_refs"),
            call_id=_as_text(payload.get("call_id")) or "call-6",
            checked_at_utc=_as_text(payload.get("checked_at_utc")) or None,
        )
    if requirement_id == REQ_027_REQUIREMENT_ID:
        return build_req_027_call_2_ecosystem_linkage_reasoning(dict(payload))
    if requirement_id == REQ_030_REQUIREMENT_ID:
        return build_req_030_call_5_sequencing_and_lane_design_reasoning(
            target_project_root=payload.get("target_project_root"),
            earth_root=payload.get("earth_root"),
            output_root=payload.get("output_root"),
            revision_identity=payload.get("revision_identity"),
            strategy_goal=payload.get("strategy_goal"),
            call_chain=payload.get("call_chain"),
            candidate_lane_designs=payload.get("candidate_lane_designs"),
            strategic_claims=payload.get("strategic_claims"),
            cross_project_context=payload.get("cross_project_context"),
            target_project_evidence_refs=payload.get("target_project_evidence_refs"),
            earth_sweep_evidence_refs=payload.get("earth_sweep_evidence_refs"),
            call_id=_as_text(payload.get("call_id")) or "call-5",
            checked_at_utc=_as_text(payload.get("checked_at_utc")) or None,
        )
    if requirement_id == REQ_034_REQUIREMENT_ID:
        if (
            payload.get("analysis_type") == REQ_034_ANALYSIS_TYPE
            and (
                "prior_call_memory" in payload
                or "current_call" in payload
                or "allowed_context_refs" in payload
            )
        ):
            return build_req_034_cross_call_memory_handoff_contract(
                target_project=payload.get("target_project"),
                current_call=payload.get("current_call"),
                call_chain=payload.get("call_chain"),
                prior_call_memory=payload.get("prior_call_memory"),
                allowed_context_refs=payload.get("allowed_context_refs"),
                memory_budget=payload.get("memory_budget"),
                analysis_type=_as_text(payload.get("analysis_type")) or REQ_034_ANALYSIS_TYPE,
                call_id=_as_text(payload.get("call_id")) or None,
                checked_at_utc=_as_text(payload.get("checked_at_utc")) or None,
            )
        return build_req_034_cross_call_memory_handoff_contract(
            target_project_root=payload.get("target_project_root"),
            earth_root=payload.get("earth_root"),
            output_root=payload.get("output_root"),
            revision_identity=payload.get("revision_identity"),
            strategy_goal=payload.get("strategy_goal"),
            prior_call_handoffs=payload.get("prior_call_handoffs"),
            candidate_recommendations=payload.get("candidate_recommendations"),
            cross_project_context=payload.get("cross_project_context"),
            target_project_evidence_refs=payload.get("target_project_evidence_refs"),
            earth_sweep_evidence_refs=payload.get("earth_sweep_evidence_refs"),
            call_id=_as_text(payload.get("call_id")) or "call-memory-handoff",
            checked_at_utc=_as_text(payload.get("checked_at_utc")) or None,
        )
    if requirement_id == REQ_029_REQUIREMENT_ID:
        return build_req_029_call_4_recommendation_synthesis(
            target_project_root=payload.get("target_project_root"),
            earth_root=payload.get("earth_root"),
            output_root=payload.get("output_root"),
            revision_identity=payload.get("revision_identity"),
            strategy_goal=payload.get("strategy_goal"),
            call_chain=payload.get("call_chain"),
            candidate_recommendations=payload.get("candidate_recommendations"),
            strategic_claims=payload.get("strategic_claims"),
            cross_project_context=payload.get("cross_project_context"),
            target_project_evidence_refs=payload.get("target_project_evidence_refs"),
            earth_sweep_evidence_refs=payload.get("earth_sweep_evidence_refs"),
            call_id=_as_text(payload.get("call_id")) or "call-4",
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
    if requirement_id == REQ_046_REQUIREMENT_ID:
        return validate_req_046_final_strategy_synthesis_composer(payload)
    if requirement_id == REQ_047_REQUIREMENT_ID:
        return validate_req_047_llm_call_trace_and_decision_ledger(payload)
    if requirement_id == REQ_045_REQUIREMENT_ID:
        return validate_req_045_alternative_strategic_scenario_generator(payload)
    if requirement_id == REQ_044_REQUIREMENT_ID:
        return validate_req_044_recommendation_omission_detector(payload)
    if requirement_id == REQ_043_REQUIREMENT_ID:
        return validate_req_043_project_obligation_reasoning(payload)
    if requirement_id == REQ_042_REQUIREMENT_ID:
        return validate_req_042_existing_functionality_interaction_reasoning(payload)
    if requirement_id == REQ_041_REQUIREMENT_ID:
        return validate_req_041_recommendation_dependency_effect_modeling(payload)
    if requirement_id == REQ_040_REQUIREMENT_ID:
        return validate_req_040_recommendation_feasibility_scoring(payload)
    if requirement_id == REQ_039_REQUIREMENT_ID:
        return validate_req_039_recommendation_rationale_quality_scoring(payload)
    if requirement_id == REQ_038_REQUIREMENT_ID:
        return validate_req_038_recommendation_priority_calibration(payload)
    if requirement_id == REQ_036_REQUIREMENT_ID:
        return validate_req_036_cross_call_contradiction_detection(payload)
    if requirement_id == REQ_035_REQUIREMENT_ID:
        return validate_req_035_evidence_citation_discipline_in_reasoning_calls(payload)
    if requirement_id == REQ_037_REQUIREMENT_ID:
        return validate_req_037_recommendation_deduplication_and_merge(payload)
    if requirement_id == REQ_033_REQUIREMENT_ID:
        return validate_req_033_call_8_constraint_classification_reasoning(payload)
    if requirement_id == REQ_032_REQUIREMENT_ID:
        return validate_req_032_call_7_blocker_and_risk_policy_reasoning(payload)
    if requirement_id == REQ_028_REQUIREMENT_ID:
        return validate_req_028_call_3_gap_and_opportunity_reasoning(payload)
    if requirement_id == REQ_031_REQUIREMENT_ID:
        return validate_req_031_call_6_kpi_impact_estimation_reasoning(payload)
    if requirement_id == REQ_027_REQUIREMENT_ID:
        return validate_req_027_call_2_ecosystem_linkage_reasoning(payload)
    if requirement_id == REQ_030_REQUIREMENT_ID:
        return validate_req_030_call_5_sequencing_and_lane_design_reasoning(payload)
    if requirement_id == REQ_034_REQUIREMENT_ID:
        return validate_req_034_cross_call_memory_handoff_contract(payload)
    if requirement_id == REQ_029_REQUIREMENT_ID:
        return validate_req_029_call_4_recommendation_synthesis(payload)
    if requirement_id == REQ_025_REQUIREMENT_ID:
        return validate_req_025_multi_call_strategy_pipeline_planner(payload)
    if requirement_id == REQ_026_REQUIREMENT_ID:
        return validate_req_026_call_1_situational_analysis_reasoning(payload)
    return [f"unsupported requirement_id {requirement_id or '<missing>'}"]


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Emit REQ-025 through REQ-047 strategy pipeline payloads, including recovered "
            "REQ-038/039/040/041/042/043/044/045/047 contract surfaces."
        )
    )
    parser.add_argument("--input-json", required=True, help="Input JSON path or '-' for stdin.")
    parser.add_argument("--output-json", default="", help="Optional output JSON path.")
    parser.add_argument("--json-pretty", action="store_true", help="Pretty-print JSON output.")
    parser.add_argument(
        "--trace-root",
        default="",
        help="Optional absolute or relative root used when builders persist trace artifacts.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    _enforce_log_budget(LOG_ROOT)

    try:
        input_payload = _parse_cli_input(args.input_json)
        requirement_id = _detect_requirement(input_payload)
        quiet_cli = requirement_id == REQ_046_REQUIREMENT_ID
        if not quiet_cli:
            _timestamped_print(f"Starting {requirement_id} pipeline build from input source: {args.input_json}")
        output_payload = run(input_payload, trace_root=args.trace_root or None)
    except (
        Req026Error,
        Req029Error,
        Req030Error,
        Req031Error,
        Req034Error,
        Req043Error,
        Req044Error,
        Req045Error,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        detected_requirement_id = locals().get("requirement_id", "")
        if isinstance(exc, Req026Error):
            requirement_id = REQ_026_REQUIREMENT_ID
        elif isinstance(exc, Req029Error):
            requirement_id = REQ_029_REQUIREMENT_ID
        elif isinstance(exc, Req030Error):
            requirement_id = REQ_030_REQUIREMENT_ID
        elif isinstance(exc, Req031Error):
            requirement_id = REQ_031_REQUIREMENT_ID
        elif isinstance(exc, Req034Error):
            requirement_id = REQ_034_REQUIREMENT_ID
        elif isinstance(exc, Req043Error):
            requirement_id = REQ_043_REQUIREMENT_ID
        elif isinstance(exc, Req044Error):
            requirement_id = REQ_044_REQUIREMENT_ID
        elif isinstance(exc, Req045Error):
            requirement_id = REQ_045_REQUIREMENT_ID
        else:
            requirement_id = detected_requirement_id
        if requirement_id != REQ_046_REQUIREMENT_ID:
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
        if requirement_id != REQ_046_REQUIREMENT_ID:
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

    requirement_id = _as_text(output_payload.get("requirement_id"))
    call_metadata = output_payload.get("call_metadata")
    if isinstance(call_metadata, Mapping) and _as_text(call_metadata.get("llm_call_trace_path")):
        trace_output_path = _write_llm_call_trace(output_payload)
        _timestamped_print(f"Wrote {requirement_id} call trace to {trace_output_path}")
    serialized_output = _json_dumps(output_payload, pretty=args.json_pretty)
    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialized_output, encoding="utf-8")
        if requirement_id != REQ_046_REQUIREMENT_ID:
            _timestamped_print(f"Wrote {requirement_id} pipeline payload to {output_path}")
    else:
        if requirement_id != REQ_046_REQUIREMENT_ID:
            _timestamped_print(f"{requirement_id} pipeline payload generated successfully and emitted to stdout.")
    print(serialized_output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
