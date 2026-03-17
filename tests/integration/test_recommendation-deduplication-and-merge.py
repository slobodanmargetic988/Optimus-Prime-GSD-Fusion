import json
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "recommendation-deduplication-and-merge.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_037_integration_recommendation_is_complete_and_uses_cross_project_context() -> None:
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_037_recommendation_deduplication_and_merge(
        target_project_root=fixture["target_project_root"],
        earth_root=fixture["earth_root"],
        output_root=fixture["output_root"],
        revision_identity=fixture["revision_identity"],
        target_project_evidence_refs=fixture["target_project_evidence_refs"],
        earth_sweep_evidence_refs=fixture["earth_sweep_evidence_refs"],
        cross_project_context=fixture["cross_project_context"],
        recommendation_drafts=fixture["recommendation_drafts"],
        merged_at="2026-03-16T12:00:00Z",
    )

    assert module.validate_req_037_recommendation_deduplication_and_merge(payload) == []

    processing = payload["processing_behavior"]
    usage = processing["context_usage"]
    recommendation = processing["recommendation"]

    assert usage["cross_project_context_used"] is True
    assert usage["earth_sweep_context_used"] is True
    assert usage["cross_project_projects_considered"] == ["runtime-orchestrator"]

    expected_recommendation_fields = {
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "merged_recommendations",
        "cross_project_obligations",
        "open_risks",
    }
    assert set(recommendation.keys()) == expected_recommendation_fields
    assert recommendation["merged_recommendations"] == payload["merged_recommendations"]
    assert recommendation["open_risks"] == []
    assert recommendation["cross_project_obligations"] == [
        {
            "obligation_id": "obligation-rec-runtime-bridge-alignment",
            "project_id": "runtime-orchestrator",
            "summary": "Align runtime bridge assumptions before planner promotion.",
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-15/portfolio.json",
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                "reports/optimus-prime/planning/evidence/TASK-127/TASK_EVIDENCE.json",
                "strategy/current/llm_call_trace.jsonl",
                "strategy/current/samples/REQ-025_multi-call-strategy-pipeline-planner.sample.json",
            ],
        }
    ]

    evidence_refs = recommendation["evidence_refs"]
    assert "reports/optimus-prime/planning/evidence/TASK-127/TASK_EVIDENCE.json" in evidence_refs
    assert "reports/earth/sweeps/2026-03-15/portfolio.json" in evidence_refs
    assert "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json" in evidence_refs
    assert "strategy/current/llm_call_trace.jsonl" in evidence_refs


def test_req_037_cross_project_merge_without_earth_evidence_becomes_open_risk() -> None:
    fixture = _read_json(FIXTURE_PATH)
    drafts = []
    for row in fixture["recommendation_drafts"]:
        cloned = dict(row)
        if cloned["recommendation_id"] == "rec.runtime-bridge-alignment":
            cloned["evidence_refs"] = [
                "reports/optimus-prime/planning/evidence/TASK-127/TASK_EVIDENCE.json",
                "strategy/current/llm_call_trace.jsonl",
            ]
        drafts.append(cloned)

    payload = module.build_req_037_recommendation_deduplication_and_merge(
        target_project_root=fixture["target_project_root"],
        earth_root=fixture["earth_root"],
        output_root=fixture["output_root"],
        revision_identity="rev-req037-integration-risk-r1",
        target_project_evidence_refs=fixture["target_project_evidence_refs"],
        earth_sweep_evidence_refs=[],
        cross_project_context=fixture["cross_project_context"],
        recommendation_drafts=drafts,
        merged_at="2026-03-16T12:00:00Z",
    )

    assert module.validate_req_037_recommendation_deduplication_and_merge(payload) == []

    recommendation = payload["processing_behavior"]["recommendation"]
    assert recommendation["cross_project_obligations"] == []
    assert recommendation["decision"] == "proceed-with-open-risks"
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk-rec-runtime-bridge-alignment",
            "summary": "Align runtime bridge assumptions before planner promotion.",
            "reason_code": "missing_earth_sweep_evidence_refs",
            "required_evidence_refs": [
                "reports/optimus-prime/planning/evidence/TASK-127/TASK_EVIDENCE.json",
                "strategy/current/llm_call_trace.jsonl",
            ],
        }
    ]


def test_req_037_emits_replay_stable_per_call_trace_rows() -> None:
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_037_recommendation_deduplication_and_merge(
        target_project_root=fixture["target_project_root"],
        earth_root=fixture["earth_root"],
        output_root=fixture["output_root"],
        revision_identity=fixture["revision_identity"],
        target_project_evidence_refs=fixture["target_project_evidence_refs"],
        earth_sweep_evidence_refs=fixture["earth_sweep_evidence_refs"],
        cross_project_context=fixture["cross_project_context"],
        recommendation_drafts=fixture["recommendation_drafts"],
        merged_at="2026-03-16T12:00:00Z",
    )
    replay_payload = module.build_req_037_recommendation_deduplication_and_merge(
        target_project_root=fixture["target_project_root"],
        earth_root=fixture["earth_root"],
        output_root=fixture["output_root"],
        revision_identity=fixture["revision_identity"],
        target_project_evidence_refs=fixture["target_project_evidence_refs"],
        earth_sweep_evidence_refs=fixture["earth_sweep_evidence_refs"],
        cross_project_context=fixture["cross_project_context"],
        recommendation_drafts=fixture["recommendation_drafts"],
        merged_at="2026-03-16T12:00:00Z",
    )

    metadata = payload["call_metadata"]
    replay_metadata = replay_payload["call_metadata"]
    trace_rows = metadata["llm_call_trace_rows"]

    assert metadata == replay_metadata
    assert metadata["llm_call_trace_schema_version"] == module.REQ_025_LLM_CALL_TRACE_SCHEMA_VERSION
    assert metadata["llm_call_trace_path"] == module.LLM_CALL_TRACE_RELATIVE_PATH
    assert metadata["llm_call_trace_sha256"] == module._canonical_digest(trace_rows)
    assert len(trace_rows) == len(fixture["recommendation_drafts"])
    assert [row["sequence"] for row in trace_rows] == [1, 2, 3]
    assert all(row["call_objective"] for row in trace_rows)
    assert all(row["input_refs"] for row in trace_rows)
    assert all(row["output_refs"] for row in trace_rows)
    assert all(row["handoff_summary"] for row in trace_rows)
    assert trace_rows[0]["depends_on"] == []
    assert trace_rows[1]["depends_on"] == [trace_rows[0]["call_id"]]
    assert trace_rows[2]["depends_on"] == [trace_rows[1]["call_id"]]
    assert "recommendation decision proceed across 2 merged recommendation(s)." in trace_rows[2]["handoff_summary"]
