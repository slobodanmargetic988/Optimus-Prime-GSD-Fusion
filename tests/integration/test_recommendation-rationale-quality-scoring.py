import json
import shutil
from pathlib import Path

from scripts import strategy_llm_pipeline as pipeline


def _reset_call_trace() -> None:
    trace_path = Path("strategy/current/llm_call_trace.jsonl")
    if trace_path.exists():
        trace_path.unlink()
    artifacts_dir = Path("strategy/current/llm_call_trace_artifacts")
    if artifacts_dir.exists():
        shutil.rmtree(artifacts_dir, ignore_errors=True)


def _read_trace_rows() -> list[dict]:
    trace_path = Path("strategy/current/llm_call_trace.jsonl")
    lines = trace_path.read_text(encoding="utf-8").splitlines()
    assert lines
    return [json.loads(line) for line in lines]


def test_req039_processing_rejects_low_substance_recommendations_and_uses_cross_project_context() -> None:
    _reset_call_trace()
    payload = {
        "analysis_type": pipeline.REQ_039_ANALYSIS_TYPE,
        "now_utc": "2026-03-16T14:00:00Z",
        "quality_policy": {
            "minimum_evidence_ref_count": 2,
            "minimum_tradeoff_count": 1,
            "passing_score": 4,
        },
        "recommendations": [
            {
                "recommendation_id": "rec.req-039.local-emission-ready",
                "summary": "Keep local recommendation scoring behind grounded evidence.",
                "rationale": "Local recommendation is supported by multiple sources and explicit tradeoffs.",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-135/TASK_EVIDENCE.json",
                    "strategy/current/samples/REQ-035_evidence-citation-discipline-in-reasoning-calls.sample.json",
                ],
                "tradeoffs": [
                    "Raises the emission bar, which may defer thin recommendations.",
                ],
            },
            {
                "recommendation_id": "rec.req-039.earth-ops-sync",
                "summary": "Coordinate recommendation scoring expectations with earth-ops before packet emission.",
                "rationale": "Cross-project score handling should stay aligned with earth-ops evidence review conventions.",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-135/TASK_EVIDENCE.json",
                    "strategy/current/samples/REQ-030_call-5-sequencing-and-lane-design-reasoning.sample.json",
                ],
                "tradeoffs": [
                    "Cross-project coordination reduces drift but slows immediate packet emission.",
                ],
            },
            {
                "recommendation_id": "rec.req-039.single-source",
                "summary": "Ship a recommendation after citing only one source artifact.",
                "rationale": "The recommendation is directionally useful but under-evidenced.",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-135/TASK_EVIDENCE.json",
                ],
                "tradeoffs": [
                    "Faster emission now increases the chance of weak rationale quality.",
                ],
            },
            {
                "recommendation_id": "rec.req-039.no-tradeoffs",
                "summary": "Emit a recommendation without naming what it delays.",
                "rationale": "The evidence is present, but the recommendation still hides operator-facing tradeoffs.",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-135/TASK_EVIDENCE.json",
                    "strategy/current/samples/REQ-027_call-2-ecosystem-linkage-reasoning.sample.json",
                ],
                "tradeoffs": [],
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
                    "context_note": "Earth-ops owns cross-project scoring and evidence review conventions.",
                }
            ],
            "earth_sweep": {
                "projects": [
                    {
                        "project_id": "earth-ops",
                        "unresolved_ideas": [
                            {
                                "idea": "Confirm whether analytics-hub should consume the rejected-recommendation ledger later.",
                                "evidence_refs": [
                                    "reports/earth/sweeps/2026-03-16/earth-ops.json",
                                ],
                            }
                        ],
                    }
                ]
            },
        },
    }

    result = pipeline.process_req_039_recommendation_rationale_quality_scoring(payload)

    assert result["ok"] is True
    assert result["schema_version"] == pipeline.REQ_039_PROCESSING_SCHEMA_VERSION
    assert pipeline.validate_req_039_recommendation_rationale_quality_scoring(
        {
            "ok": True,
            "schema_version": pipeline.REQ_039_SCHEMA_VERSION,
            "requirement_id": pipeline.REQ_039_REQUIREMENT_ID,
            "analysis_type": pipeline.REQ_039_ANALYSIS_TYPE,
            "call_id": pipeline.REQ_039_CALL_ID,
            "checked_at_utc": result["checked_at_utc"],
            "quality_policy": result["quality_policy"],
            "recommendations": result["recommendations"],
            "recommendation_rationale_quality_scoring": result["recommendation_rationale_quality_scoring"],
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
    assert usage["cross_project_projects_considered"] == ["earth-ops"]
    assert "reports/earth/sweeps/2026-03-16/portfolio.json" in recommendation["evidence_refs"]
    assert "reports/earth/sweeps/2026-03-16/earth-ops.json" in recommendation["evidence_refs"]

    action_ids = {row["recommendation_id"] for row in recommendation["recommended_actions"]}
    assert action_ids == {
        "rec.req-039.earth-ops-sync",
        "rec.req-039.local-emission-ready",
    }
    assert any(row["coordination_required"] is True for row in recommendation["recommended_actions"])
    assert any(row["project_id"] == "earth-ops" for row in recommendation["cross_project_obligations"])
    assert any(row["reason_code"] == "insufficient_evidence_refs" for row in recommendation["open_risks"])
    assert any(row["reason_code"] == "missing_explicit_tradeoffs" for row in recommendation["open_risks"])
    assert any(row["reason_code"] == "unresolved_cross_project_idea" for row in recommendation["open_risks"])

    trace_rows = _read_trace_rows()
    metadata = result["call_metadata"]
    assert metadata["llm_call_trace_rows"] == trace_rows
    assert len(trace_rows) == len(payload["recommendations"])
    assert metadata["llm_call_trace_schema_version"] == "optimus-prime.llm-call-trace.v1"
    assert metadata["llm_call_trace_path"] == "strategy/current/llm_call_trace.jsonl"
    assert metadata["reproducibility"] == "deterministic-input-fingerprint"
    assert metadata["reproducible_call_id"].startswith("req039-")
    assert metadata["processing_call_id"].startswith("req039-processing-")
    assert metadata["llm_call_trace_sha256"]
    assert len({row["call_id"] for row in trace_rows}) == len(trace_rows)
    for trace_row in trace_rows:
        assert trace_row["requirement_id"] == pipeline.REQ_039_REQUIREMENT_ID
        assert trace_row["call_id"].startswith("score-")
        assert trace_row["call_objective"]
        assert trace_row["input_refs"]
        assert trace_row["output_refs"]
        assert trace_row["handoff_summary"]
        for artifact in trace_row["artifacts"]:
            assert Path(artifact["path"]).exists()


def test_req039_processing_without_earth_refs_does_not_emit_cross_project_obligations() -> None:
    _reset_call_trace()
    payload = {
        "analysis_type": pipeline.REQ_039_ANALYSIS_TYPE,
        "now_utc": "2026-03-16T14:10:00Z",
        "quality_policy": {
            "minimum_evidence_ref_count": 2,
            "minimum_tradeoff_count": 1,
            "passing_score": 4,
        },
        "recommendations": [
            {
                "recommendation_id": "rec.req-039.earth-ops-sync",
                "summary": "Coordinate recommendation scoring expectations with earth-ops before packet emission.",
                "rationale": "Cross-project score handling should stay aligned with earth-ops evidence review conventions.",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-135/TASK_EVIDENCE.json",
                    "strategy/current/samples/REQ-030_call-5-sequencing-and-lane-design-reasoning.sample.json",
                ],
                "tradeoffs": [
                    "Cross-project coordination reduces drift but slows immediate packet emission.",
                ],
            }
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
                    "context_note": "Context exists, but Earth refs are still missing.",
                }
            ],
        },
    }

    result = pipeline.process_req_039_recommendation_rationale_quality_scoring(payload)
    recommendation = result["processing_behavior"]["recommendation"]
    usage = result["processing_behavior"]["context_usage"]

    assert recommendation["recommended_actions"] == []
    assert recommendation["cross_project_obligations"] == []
    assert any(row["reason_code"] == "missing_earth_sweep_evidence_refs" for row in recommendation["open_risks"])
    assert recommendation["decision"] == "collect-earth-evidence"
    assert usage["cross_project_context_used"] is True
    assert usage["earth_sweep_context_used"] is False

    trace_rows = _read_trace_rows()
    assert len(trace_rows) == 1
    trace_row = trace_rows[0]
    assert trace_row["totals"]["accepted_recommendations"] == 1
    assert trace_row["totals"]["rejected_recommendations"] == 0


def test_req039_processing_call_metadata_is_replay_stable_across_input_reordering() -> None:
    _reset_call_trace()
    payload = {
        "analysis_type": pipeline.REQ_039_ANALYSIS_TYPE,
        "now_utc": "2026-03-16T14:20:00Z",
        "quality_policy": {
            "minimum_evidence_ref_count": 2,
            "minimum_tradeoff_count": 1,
            "passing_score": 4,
        },
        "recommendations": [
            {
                "recommendation_id": "rec.req-039.local",
                "summary": "Keep local recommendation scoring behind grounded evidence.",
                "rationale": "Local recommendation stays emission-ready with multiple refs and explicit tradeoffs.",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-135/TASK_EVIDENCE.json",
                    "strategy/current/samples/REQ-035_evidence-citation-discipline-in-reasoning-calls.sample.json",
                ],
                "tradeoffs": [
                    "Raises the emission bar for thin recommendations.",
                ],
            },
            {
                "recommendation_id": "rec.req-039.earth-ops-sync",
                "summary": "Coordinate recommendation scoring expectations with earth-ops before packet emission.",
                "rationale": "Cross-project score handling should stay aligned with earth-ops evidence review conventions.",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-135/TASK_EVIDENCE.json",
                    "strategy/current/samples/REQ-030_call-5-sequencing-and-lane-design-reasoning.sample.json",
                ],
                "tradeoffs": [
                    "Cross-project coordination reduces drift but slows immediate packet emission.",
                ],
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
                    "context_note": "Earth-ops owns cross-project scoring and evidence review conventions.",
                },
                {
                    "project_id": "analytics-hub",
                    "project_root": "/workspace/projects/Earth/analytics-hub",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-16/analytics-hub.json",
                    ],
                    "context_note": "Analytics-hub consumes rejected-recommendation insights.",
                },
            ],
        },
    }

    first = pipeline.process_req_039_recommendation_rationale_quality_scoring(payload)

    _reset_call_trace()
    reordered = dict(payload)
    reordered["recommendations"] = list(reversed(payload["recommendations"]))
    reordered["broad_sweep_context"] = dict(payload["broad_sweep_context"])
    reordered["broad_sweep_context"]["cross_project_context"] = list(
        reversed(payload["broad_sweep_context"]["cross_project_context"])
    )
    second = pipeline.process_req_039_recommendation_rationale_quality_scoring(reordered)

    assert first["call_metadata"] == second["call_metadata"]
    assert first["call_metadata"]["canonical_processing_input"] == second["call_metadata"]["canonical_processing_input"]
    assert first["call_metadata"]["llm_call_trace_rows"] == second["call_metadata"]["llm_call_trace_rows"]
