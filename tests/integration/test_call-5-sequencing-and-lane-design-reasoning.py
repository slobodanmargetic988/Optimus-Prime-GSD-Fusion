from scripts import strategy_llm_pipeline as pipeline

import json
import shutil
from pathlib import Path


def _reset_call_trace() -> None:
    trace_path = Path("strategy/current/llm_call_trace.jsonl")
    if trace_path.exists():
        trace_path.unlink()
    artifacts_dir = Path("strategy/current/llm_call_trace_artifacts")
    if artifacts_dir.exists():
        shutil.rmtree(artifacts_dir, ignore_errors=True)


def _read_last_trace_row() -> dict:
    trace_path = Path("strategy/current/llm_call_trace.jsonl")
    lines = trace_path.read_text(encoding="utf-8").splitlines()
    assert lines
    return json.loads(lines[-1])


def test_req030_processing_emits_lanes_sequence_and_evidence_gated_cross_project_obligations() -> None:
    _reset_call_trace()
    payload = {
        "analysis_type": pipeline.REQ_030_ANALYSIS_TYPE,
        "now_utc": "2026-03-16T12:10:00Z",
        "target_project": {
            "project_id": "optimus-prime-gsd-fusion",
            "project_root": "/workspace/projects/optimus-prime-gsd-fusion",
        },
        "constraints": {
            "max_parallel_lanes": 3,
            "max_active_work_items": 5,
            "notes": [
                "Keep cross-project coordination evidence-backed.",
                "Prefer deterministic sequencing over ad-hoc parallelism.",
            ],
        },
        "recommendations": [
            {
                "recommendation_id": "rec.local-implementation",
                "summary": "Implement the REQ-030 processing layer for Call-5 sequencing and lane design reasoning.",
                "rationale": "The contract normalizer exists, but the processing behavior is required for broad-sweep evidence gating.",
                "expected_impact": "Deterministic call-5 outputs and lane sequencing under constraints.",
                "risk_level": "medium",
            },
            {
                "recommendation_id": "rec.earth-ops-alignment",
                "summary": "Coordinate sequencing assumptions with earth-ops before promoting cross-project lane execution.",
                "rationale": "Cross-project coordination must be grounded in Earth-sweep evidence refs and explicit context.",
                "expected_impact": "Avoid cross-project drift while lanes execute in parallel.",
                "risk_level": "low",
            },
            {
                "recommendation_id": "rec.analytics-hub-sync",
                "summary": "Coordinate the lane/reporting interface with analytics-hub.",
                "rationale": "This is a cross-project idea but must not be promoted without matched cross-project context evidence refs.",
                "expected_impact": "Clarify reporting expectations for sequencing output artifacts.",
                "risk_level": "low",
            },
        ],
        "broad_sweep_context": {
            "earth_sweep_evidence_refs": [
                "reports/earth/sweeps/2026-03-16/portfolio.json",
            ],
            "cross_project_context": [
                {
                    "project_id": "earth-ops",
                    "project_root": "/workspace/projects/Earth/earth-ops",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-16/earth-ops.json",
                    ],
                    "context_note": "Earth-ops owns cross-project release/coordination conventions referenced by sequencing.",
                }
            ],
        },
    }

    result = pipeline.process_req_030_call_5_sequencing_and_lane_design_reasoning(payload)

    assert result["ok"] is True
    assert result["schema_version"] == pipeline.REQ_030_PROCESSING_SCHEMA_VERSION

    assert pipeline.validate_req_030_call_5_sequencing_and_lane_design_reasoning(
        {
            "ok": True,
            "schema_version": pipeline.REQ_030_SCHEMA_VERSION,
            "requirement_id": pipeline.REQ_030_REQUIREMENT_ID,
            "analysis_type": pipeline.REQ_030_ANALYSIS_TYPE,
            "call_id": pipeline.REQ_030_CALL_ID,
            "checked_at_utc": result["checked_at_utc"],
            "target_project": result["target_project"],
            "constraints": result["constraints"],
            "recommendations": result["recommendations"],
            "sequencing_and_lane_design_reasoning": result["sequencing_and_lane_design_reasoning"],
            "totals": result["totals"],
        }
    ) == []

    processing = result["processing_behavior"]
    usage = processing["context_usage"]
    recommendation = processing["recommendation"]

    expected_recommendation_fields = {
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "recommended_actions",
        "cross_project_obligations",
        "open_risks",
    }
    assert set(recommendation.keys()) == expected_recommendation_fields
    assert usage["cross_project_context_used"] is True
    assert usage["earth_sweep_context_used"] is True
    assert "earth-ops" in usage["cross_project_projects_considered"]

    assert "reports/earth/sweeps/2026-03-16/portfolio.json" in recommendation["evidence_refs"]
    assert any(row["project_id"] == "earth-ops" for row in recommendation["cross_project_obligations"])
    assert any(
        "missing_cross_project_context" in str(row.get("reason_code"))
        for row in recommendation["open_risks"]
    )

    reasoning = result["sequencing_and_lane_design_reasoning"]
    lane_names = {row["lane_name"] for row in reasoning["lanes"]}
    assert "Cross-project coordination" in lane_names
    assert "Local implementation" in lane_names
    assert "Evidence collection" in lane_names

    sequenced_ids = [row["recommendation_id"] for row in reasoning["sequence"]]
    assert "rec.analytics-hub-sync" not in sequenced_ids
    assert "rec.earth-ops-alignment" in sequenced_ids

    cross_item = next(row for row in reasoning["sequence"] if row["recommendation_id"] == "rec.earth-ops-alignment")
    assert cross_item["coordination_dependencies"]
    assert cross_item["coordination_dependencies"][0]["depends_on_type"] == "external"
    assert cross_item["coordination_dependencies"][0]["depends_on"] == "earth-ops"
    assert cross_item["why_now"]

    row = _read_last_trace_row()
    metadata = result["call_metadata"]
    assert metadata["llm_call_trace_rows"] == [row]
    assert metadata["llm_call_trace_schema_version"] == "optimus-prime.llm-call-trace.v1"
    assert metadata["llm_call_trace_path"] == "strategy/current/llm_call_trace.jsonl"
    assert metadata["reproducibility"] == "deterministic-input-fingerprint"
    assert metadata["reproducible_call_id"].startswith("req030-")
    assert metadata["processing_call_id"].startswith("req030-processing-")
    assert row["requirement_id"] == pipeline.REQ_030_REQUIREMENT_ID
    assert row["call_id"] == pipeline.REQ_030_CALL_ID
    assert row["call_objective"]
    assert row["input_refs"]
    assert row["output_refs"]
    assert row["handoff_summary"]
    assert row["artifacts"]
    for artifact in row["artifacts"]:
        assert Path(artifact["path"]).exists()


def test_req030_processing_without_earth_sweep_evidence_does_not_invent_cross_project_obligations() -> None:
    _reset_call_trace()
    payload = {
        "analysis_type": pipeline.REQ_030_ANALYSIS_TYPE,
        "now_utc": "2026-03-16T12:20:00Z",
        "target_project": {
            "project_id": "optimus-prime-gsd-fusion",
            "project_root": "/workspace/projects/optimus-prime-gsd-fusion",
        },
        "constraints": {
            "max_parallel_lanes": 2,
            "max_active_work_items": 3,
            "notes": [],
        },
        "recommendations": [
            {
                "recommendation_id": "rec.local-verify",
                "summary": "Keep local verification explicitly sequenced before promotion.",
                "rationale": "High-risk work should be validated deterministically.",
                "expected_impact": "Stable lane output and fewer recovery regressions.",
                "risk_level": "high",
            },
            {
                "recommendation_id": "rec.earth-ops-alignment",
                "summary": "Coordinate sequencing assumptions with earth-ops before promoting cross-project lane execution.",
                "rationale": "Cross-project coordination must not be promoted without Earth-sweep evidence refs.",
                "expected_impact": "Avoid cross-project drift while lanes execute in parallel.",
                "risk_level": "low",
            },
        ],
        "broad_sweep_context": {
            "earth_sweep_evidence_refs": [],
            "cross_project_context": [
                {
                    "project_id": "earth-ops",
                    "project_root": "/workspace/projects/Earth/earth-ops",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-16/earth-ops.json",
                    ],
                    "context_note": "Context exists, but Earth-sweep evidence refs are missing for this call.",
                }
            ],
        },
    }

    result = pipeline.process_req_030_call_5_sequencing_and_lane_design_reasoning(payload)
    recommendation = result["processing_behavior"]["recommendation"]

    assert recommendation["cross_project_obligations"] == []
    assert any(row["reason_code"] == "missing_earth_sweep_evidence_refs" for row in recommendation["open_risks"])

    sequenced_ids = [row["recommendation_id"] for row in result["sequencing_and_lane_design_reasoning"]["sequence"]]
    assert "rec.earth-ops-alignment" not in sequenced_ids
    assert "rec.local-verify" in sequenced_ids

    row = _read_last_trace_row()
    assert row["totals"]["sequence_items"] == len(result["sequencing_and_lane_design_reasoning"]["sequence"])


def test_req030_processing_call_metadata_is_replay_stable_across_input_reordering() -> None:
    _reset_call_trace()
    payload = {
        "analysis_type": pipeline.REQ_030_ANALYSIS_TYPE,
        "now_utc": "2026-03-16T12:40:00Z",
        "target_project": {
            "project_id": "optimus-prime-gsd-fusion",
            "project_root": "/workspace/projects/optimus-prime-gsd-fusion",
        },
        "constraints": {
            "max_parallel_lanes": 3,
            "max_active_work_items": 5,
            "notes": [
                "Expose coordination dependencies explicitly.",
                "Keep sequencing deterministic.",
            ],
        },
        "recommendations": [
            {
                "recommendation_id": "rec.earth-ops-alignment",
                "summary": "Coordinate sequencing assumptions with earth-ops before promotion.",
                "rationale": "Cross-project coordination must stay evidence-backed.",
                "expected_impact": "Reduce sequencing drift.",
                "risk_level": "low",
            },
            {
                "recommendation_id": "rec.local-implementation",
                "summary": "Implement the REQ-030 processing layer for Call-5 sequencing and lane design reasoning.",
                "rationale": "The contract normalizer exists, but processing metadata must stay replay-stable.",
                "expected_impact": "Deterministic call-5 outputs and metadata.",
                "risk_level": "medium",
            },
        ],
        "broad_sweep_context": {
            "earth_sweep_evidence_refs": [
                "reports/earth/sweeps/2026-03-16/portfolio.json",
            ],
            "cross_project_context": [
                {
                    "project_id": "earth-ops",
                    "project_root": "/workspace/projects/Earth/earth-ops",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-16/earth-ops.json",
                    ],
                    "context_note": "Earth-ops owns release coordination conventions.",
                },
                {
                    "project_id": "analytics-hub",
                    "project_root": "/workspace/projects/Earth/analytics-hub",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-16/analytics-hub.json",
                    ],
                    "context_note": "Analytics-hub consumes sequencing output for reporting.",
                },
            ],
        },
    }

    first = pipeline.process_req_030_call_5_sequencing_and_lane_design_reasoning(payload)

    _reset_call_trace()
    reordered = dict(payload)
    reordered["recommendations"] = list(reversed(payload["recommendations"]))
    reordered["broad_sweep_context"] = dict(payload["broad_sweep_context"])
    reordered["broad_sweep_context"]["cross_project_context"] = list(
        reversed(payload["broad_sweep_context"]["cross_project_context"])
    )
    second = pipeline.process_req_030_call_5_sequencing_and_lane_design_reasoning(reordered)

    assert first["call_metadata"] == second["call_metadata"]
    assert first["call_metadata"]["canonical_processing_input"] == second["call_metadata"]["canonical_processing_input"]
    assert first["call_metadata"]["llm_call_trace_rows"] == second["call_metadata"]["llm_call_trace_rows"]
