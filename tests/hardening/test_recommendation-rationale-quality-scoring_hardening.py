from __future__ import annotations

import copy
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


def test_hardening_cross_call_contradiction_between_analysis_and_synthesis_outputs() -> None:
    _reset_call_trace()
    payload = {
        "analysis_type": pipeline.REQ_039_ANALYSIS_TYPE,
        "now_utc": "2026-03-16T15:00:00Z",
        "quality_policy": {
            "minimum_evidence_ref_count": 2,
            "minimum_tradeoff_count": 1,
            "passing_score": 4,
        },
        "recommendations": [
            {
                "recommendation_id": "rec.req-039.local-consistent",
                "summary": "Keep local recommendation quality checks deterministic.",
                "rationale": "Local recommendation remains evidence-backed and explicit about tradeoffs.",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-138/TASK_EVIDENCE.json",
                    "strategy/current/samples/REQ-039_recommendation-rationale-quality-scoring.sample.json",
                ],
                "tradeoffs": [
                    "Raises quality threshold and can delay recommendation emission.",
                ],
            }
        ],
        "broad_sweep_context": {
            "earth_sweep_evidence_refs": [
                "reports/earth/sweeps/2026-03-16/portfolio.json",
            ],
            "analysis_synthesis_citation_status": [
                {
                    "strategic_claim_id": "sc.req039.shared",
                    "call_id": "call-2",
                    "recommendation_id": "rec.req-039.analysis-view",
                    "citation_status": "cited",
                    "summary": "Analysis output treats the claim as cited.",
                    "evidence_refs": [
                        "reports/optimus-prime/planning/evidence/TASK-138/analysis_claim.json",
                    ],
                },
                {
                    "strategic_claim_id": "sc.req039.shared",
                    "call_id": "call-5",
                    "recommendation_id": "rec.req-039.synthesis-view",
                    "citation_status": "uncited",
                    "summary": "Synthesis output marks the same claim as uncited.",
                    "evidence_refs": [],
                },
            ],
        },
    }

    out = pipeline.process_req_039_recommendation_rationale_quality_scoring(payload)
    recommendation = out["processing_behavior"]["recommendation"]

    contradiction_rows = [
        row
        for row in recommendation["open_risks"]
        if row["reason_code"] == "analysis_synthesis_contradiction_cross_call_citation_status"
    ]
    assert len(contradiction_rows) == 1
    assert "reports/optimus-prime/planning/evidence/TASK-138/analysis_claim.json" in contradiction_rows[0][
        "required_evidence_refs"
    ]
    assert recommendation["decision"] == "proceed-with-open-risks"


def test_hardening_uncited_strategic_claim_blocked_by_citation_discipline() -> None:
    _reset_call_trace()
    payload = {
        "analysis_type": pipeline.REQ_039_ANALYSIS_TYPE,
        "now_utc": "2026-03-16T15:10:00Z",
        "quality_policy": {
            "minimum_evidence_ref_count": 2,
            "minimum_tradeoff_count": 1,
            "passing_score": 4,
        },
        "recommendations": [
            {
                "recommendation_id": "rec.req-039.earth-ops-sync",
                "summary": "Coordinate recommendation scoring with earth-ops before packet emission.",
                "rationale": "Cross-project scoring alignment is valuable when the claim remains cited.",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-138/TASK_EVIDENCE.json",
                    "strategy/current/samples/REQ-035_evidence-citation-discipline-in-reasoning-calls.sample.json",
                ],
                "tradeoffs": [
                    "Coordination improves quality but increases lead time.",
                ],
            }
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
                    "context_note": "Earth-ops owns cross-project recommendation policy alignment.",
                }
            ],
            "analysis_synthesis_citation_status": [
                {
                    "strategic_claim_id": "sc.req039.uncited",
                    "call_id": "call-5",
                    "recommendation_id": "rec.req-039.earth-ops-sync",
                    "citation_status": "uncited",
                    "summary": "Synthesis output has no citation-ready backing for this claim.",
                    "evidence_refs": [],
                }
            ],
        },
    }

    out = pipeline.process_req_039_recommendation_rationale_quality_scoring(payload)
    recommendation = out["processing_behavior"]["recommendation"]

    assert recommendation["recommended_actions"] == []
    assert recommendation["cross_project_obligations"] == []
    uncited_rows = [row for row in recommendation["open_risks"] if row["reason_code"] == "uncited_strategic_claim"]
    assert len(uncited_rows) == 1
    assert "reports/optimus-prime/planning/evidence/TASK-138/TASK_EVIDENCE.json" in uncited_rows[0][
        "required_evidence_refs"
    ]
    assert recommendation["decision"] == "resolve-context-gaps"


def test_hardening_call_chain_replay_produces_stable_recommendation_ids_and_ordering() -> None:
    _reset_call_trace()
    payload_first = {
        "analysis_type": pipeline.REQ_039_ANALYSIS_TYPE,
        "now_utc": "2026-03-16T15:20:00Z",
        "quality_policy": {
            "minimum_evidence_ref_count": 2,
            "minimum_tradeoff_count": 1,
            "passing_score": 4,
        },
        "recommendations": [
            {
                "recommendation_id": "rec.req-039.zeta-local",
                "summary": "Keep local recommendation quality thresholds strict.",
                "rationale": "Local recommendation remains fully cited with explicit tradeoffs.",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-138/TASK_EVIDENCE.json",
                    "strategy/current/samples/REQ-039_recommendation-rationale-quality-scoring.sample.json",
                ],
                "tradeoffs": [
                    "Higher rationale quality thresholds may defer low-substance ideas.",
                ],
            },
            {
                "recommendation_id": "rec.req-039.alpha-earth-ops",
                "summary": "Coordinate recommendation scoring expectations with earth-ops.",
                "rationale": "Cross-project scoring conventions should align before packet emission.",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-138/TASK_EVIDENCE.json",
                    "strategy/current/samples/REQ-035_evidence-citation-discipline-in-reasoning-calls.sample.json",
                ],
                "tradeoffs": [
                    "Alignment reduces drift but adds coordination overhead.",
                ],
            },
            {
                "recommendation_id": "rec.req-039.beta-analytics",
                "summary": "Coordinate rejected-recommendation ledger expectations with analytics-hub.",
                "rationale": "Analytics consumers should align with rationale quality rejection semantics.",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-138/TASK_EVIDENCE.json",
                    "strategy/current/samples/REQ-030_call-5-sequencing-and-lane-design-reasoning.sample.json",
                ],
                "tradeoffs": [
                    "Coordination improves downstream interpretation but slows immediate emission.",
                ],
            },
        ],
        "broad_sweep_context": {
            "earth_sweep_evidence_refs": [
                "reports/earth/sweeps/2026-03-16/portfolio.json",
            ],
            "cross_project_context": [
                {
                    "project_id": "analytics-hub",
                    "project_root": "/workspace/projects/Earth/analytics-hub",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-16/analytics-hub.json",
                    ],
                    "context_note": "Analytics-hub consumes rejected recommendation ledgers.",
                },
                {
                    "project_id": "earth-ops",
                    "project_root": "/workspace/projects/Earth/earth-ops",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-16/earth-ops.json",
                    ],
                    "context_note": "Earth-ops governs recommendation evidence conventions.",
                },
            ],
            "analysis_synthesis_citation_status": [
                {
                    "strategic_claim_id": "sc.req039.alpha",
                    "call_id": "call-2",
                    "recommendation_id": "rec.req-039.alpha-earth-ops",
                    "citation_status": "cited",
                    "summary": "Analysis view: cited claim.",
                    "evidence_refs": [
                        "reports/optimus-prime/planning/evidence/TASK-138/claim_alpha.json",
                    ],
                },
                {
                    "strategic_claim_id": "sc.req039.beta",
                    "call_id": "call-5",
                    "recommendation_id": "rec.req-039.beta-analytics",
                    "citation_status": "cited",
                    "summary": "Synthesis view: cited claim.",
                    "evidence_refs": [
                        "reports/optimus-prime/planning/evidence/TASK-138/claim_beta.json",
                    ],
                },
            ],
        },
    }

    payload_second = copy.deepcopy(payload_first)
    payload_second["recommendations"] = list(reversed(payload_second["recommendations"]))
    payload_second["broad_sweep_context"]["cross_project_context"] = list(
        reversed(payload_second["broad_sweep_context"]["cross_project_context"])
    )
    payload_second["broad_sweep_context"]["analysis_synthesis_citation_status"] = list(
        reversed(payload_second["broad_sweep_context"]["analysis_synthesis_citation_status"])
    )

    first = pipeline.process_req_039_recommendation_rationale_quality_scoring(payload_first)
    second = pipeline.process_req_039_recommendation_rationale_quality_scoring(payload_second)

    first_recommendation = first["processing_behavior"]["recommendation"]
    second_recommendation = second["processing_behavior"]["recommendation"]
    assert first_recommendation["recommended_actions"] == second_recommendation["recommended_actions"]
    assert first_recommendation["open_risks"] == second_recommendation["open_risks"]
    assert first_recommendation["cross_project_obligations"] == second_recommendation["cross_project_obligations"]
    assert [row["recommendation_id"] for row in first_recommendation["recommended_actions"]] == sorted(
        row["recommendation_id"] for row in first_recommendation["recommended_actions"]
    )

    first_meta = first["call_metadata"]
    second_meta = second["call_metadata"]
    assert first_meta["reproducible_call_id"] == second_meta["reproducible_call_id"]
    assert first_meta["processing_call_id"] == second_meta["processing_call_id"]
    assert first_meta["llm_call_trace_rows"] == second_meta["llm_call_trace_rows"]
