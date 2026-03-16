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


def _read_last_trace_row() -> dict:
    trace_path = Path("strategy/current/llm_call_trace.jsonl")
    lines = trace_path.read_text(encoding="utf-8").splitlines()
    assert lines
    return json.loads(lines[-1])


def test_req035_processing_enforces_citations_and_uses_cross_project_context() -> None:
    _reset_call_trace()
    payload = {
        "analysis_type": pipeline.REQ_035_ANALYSIS_TYPE,
        "now_utc": "2026-03-16T12:50:00Z",
        "context_provenance_ledger": {
            "ledger_requirement_id": "REQ-021",
            "ledger_scope": "strategy_context_sweep.processing_behavior",
            "evidence_ids": [
                "claim-111111111111",
                "claim-222222222222",
                "claim-333333333333",
                "claim-444444444444",
            ],
        },
        "reasoning_calls": [
            {
                "call_id": "call-2",
                "strategic_claims": [
                    {
                        "strategic_claim_id": "sc.call2.local-cited",
                        "summary": "Local linkage preservation claim is cited and promotable.",
                        "evidence_ids": [
                            "claim-111111111111",
                        ],
                        "recommendation": {
                            "recommendation_id": "rec.req-035.local-cited",
                            "summary": "Promote local cited recommendation.",
                            "rationale": "Cited local claim is valid for promotion.",
                            "confidence_tag": "high",
                        },
                    },
                    {
                        "strategic_claim_id": "sc.call2.missing-citation",
                        "summary": "Missing citation claim must be excluded.",
                        "evidence_ids": [],
                        "recommendation": {
                            "recommendation_id": "rec.req-035.uncited",
                            "summary": "Do not promote uncited claim.",
                            "rationale": "Uncited strategic claim violates citation discipline.",
                            "confidence_tag": "low",
                        },
                    },
                ],
            },
            {
                "call_id": "call-5",
                "strategic_claims": [
                    {
                        "strategic_claim_id": "sc.call5.cross-project-cited",
                        "summary": "Cross-project coordination with earth-ops is evidence-backed.",
                        "evidence_ids": [
                            "claim-222222222222",
                            "claim-333333333333",
                        ],
                        "recommendation": {
                            "recommendation_id": "rec.req-035.earth-ops-sync",
                            "summary": "Coordinate citation discipline output with earth-ops.",
                            "rationale": "Cross-project coordination is supported by context and citations.",
                            "confidence_tag": "high",
                        },
                    },
                    {
                        "strategic_claim_id": "sc.call5.unknown-evidence",
                        "summary": "Unknown evidence IDs must be flagged.",
                        "evidence_ids": [
                            "claim-not-in-ledger",
                        ],
                        "recommendation": {
                            "recommendation_id": "rec.req-035.unknown-ledger",
                            "summary": "Block unknown-ledger recommendation.",
                            "rationale": "Evidence IDs outside the ledger are not promotable.",
                            "confidence_tag": "medium",
                        },
                    },
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
                    "context_note": "Earth-ops owns cross-project evidence review conventions.",
                }
            ],
            "earth_sweep": {
                "projects": [
                    {
                        "project_id": "earth-ops",
                        "unresolved_ideas": [
                            {
                                "idea": "Confirm future extension for analytics-hub once Earth refs are complete.",
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

    result = pipeline.process_req_035_evidence_citation_discipline_in_reasoning_calls(payload)

    assert result["ok"] is True
    assert result["schema_version"] == pipeline.REQ_035_PROCESSING_SCHEMA_VERSION

    discipline = result["evidence_citation_discipline"]
    flagged_ids = {row["recommendation_id"] for row in discipline["flagged_claims"]}
    final_ids = {row["recommendation_id"] for row in discipline["final_recommendations"]}
    assert flagged_ids
    assert final_ids
    assert flagged_ids.isdisjoint(final_ids)

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
    assert "reports/earth/sweeps/2026-03-16/earth-ops.json" in recommendation["evidence_refs"]
    assert any(row["project_id"] == "earth-ops" for row in recommendation["cross_project_obligations"])
    assert any(row["reason_code"] == "uncited_strategic_claim" for row in recommendation["open_risks"])
    assert any(
        "evidence_id_not_in_context_provenance_ledger" in row["reason_code"] for row in recommendation["open_risks"]
    )

    metadata = result["call_metadata"]
    row = metadata["llm_call_trace_rows"][0]
    assert metadata["llm_call_trace_rows"] == [row]
    assert metadata["llm_call_trace_schema_version"] == "optimus-prime.llm-call-trace.v1"
    assert metadata["llm_call_trace_path"] == "strategy/current/llm_call_trace.jsonl"
    assert metadata["reproducibility"] == "deterministic-input-fingerprint"
    assert metadata["reproducible_call_id"].startswith("req035-")
    assert metadata["processing_call_id"].startswith("req035-processing-")

    trace_row = _read_last_trace_row()
    assert trace_row == row
    assert row["requirement_id"] == pipeline.REQ_035_REQUIREMENT_ID
    assert row["call_id"] == pipeline.REQ_035_CALL_ID
    assert row["input_refs"]
    assert row["output_refs"]
    assert row["handoff_summary"]
    for artifact in row["artifacts"]:
        assert Path(artifact["path"]).exists()


def test_req035_processing_without_earth_refs_gates_cross_project_obligations() -> None:
    _reset_call_trace()
    payload = {
        "analysis_type": pipeline.REQ_035_ANALYSIS_TYPE,
        "now_utc": "2026-03-16T13:00:00Z",
        "context_provenance_ledger": {
            "ledger_requirement_id": "REQ-021",
            "ledger_scope": "strategy_context_sweep.processing_behavior",
            "evidence_ids": [
                "claim-555555555555",
            ],
        },
        "reasoning_calls": [
            {
                "call_id": "call-5",
                "strategic_claims": [
                    {
                        "strategic_claim_id": "sc.call5.cross-project-cited",
                        "summary": "Coordinate with earth-ops on citation expectations.",
                        "evidence_ids": [
                            "claim-555555555555",
                        ],
                        "recommendation": {
                            "recommendation_id": "rec.req-035.earth-ops-sync",
                            "summary": "Align citation review with earth-ops.",
                            "rationale": "Cross-project follow-up should only proceed when Earth evidence is attached.",
                            "confidence_tag": "high",
                        },
                    }
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
                    "context_note": "Cross-project context exists, but Earth refs are missing.",
                }
            ],
        },
    }

    result = pipeline.process_req_035_evidence_citation_discipline_in_reasoning_calls(payload)
    recommendation = result["processing_behavior"]["recommendation"]
    usage = result["processing_behavior"]["context_usage"]

    assert recommendation["cross_project_obligations"] == []
    assert any(row["reason_code"] == "missing_earth_sweep_evidence_refs" for row in recommendation["open_risks"])
    assert recommendation["decision"] == "collect-earth-evidence"
    assert usage["cross_project_context_used"] is True
    assert usage["earth_sweep_context_used"] is False
