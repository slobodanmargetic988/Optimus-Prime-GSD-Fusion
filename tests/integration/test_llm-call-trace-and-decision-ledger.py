import json
import shutil
from pathlib import Path

from scripts import strategy_llm_pipeline as pipeline


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "llm-call-trace-and-decision-ledger.json"


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


def _base_payload() -> dict:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return {
        "analysis_type": pipeline.REQ_047_ANALYSIS_TYPE,
        "now_utc": fixture["now_utc"],
        "llm_call_trace_rows": fixture["llm_call_trace_rows"],
        "final_output_artifacts": fixture["final_output_artifacts"],
        "decision_ledger": fixture["decision_ledger"],
    }


def test_req047_processing_uses_cross_project_context_and_has_complete_recommendation_fields() -> None:
    _reset_call_trace()
    payload = _base_payload()
    payload["broad_sweep_context"] = {
        "earth_sweep_evidence_refs": [
            "reports/earth/sweeps/2026-03-16/portfolio.json",
        ],
        "cross_project_context": [
            {
                "project_id": "apollo",
                "project_root": "/workspace/projects/Earth/apollo",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/apollo.json",
                ],
                "context_note": "Apollo shares packet-level sequencing contracts with Optimus Prime.",
            },
            {
                "project_id": "earth-index",
                "project_root": "/workspace/projects/Earth/earth-index",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/earth-index.json",
                ],
                "context_note": "Earth-index consumes replay-analysis outputs for audit rollups.",
            },
        ],
        "earth_sweep": {
            "projects": [
                {
                    "project_id": "apollo",
                    "unresolved_ideas": [
                        {
                            "idea": "Confirm whether apollo should receive hold/revise decision mirrors next cycle.",
                            "evidence_refs": [
                                "reports/earth/sweeps/2026-03-16/apollo.json",
                            ],
                        }
                    ],
                }
            ]
        },
    }

    result = pipeline.process_req_047_llm_call_trace_and_decision_ledger(payload)

    assert result["ok"] is True
    assert result["schema_version"] == pipeline.REQ_047_PROCESSING_SCHEMA_VERSION
    assert (
        pipeline.validate_req_047_llm_call_trace_and_decision_ledger(
            {
                "ok": True,
                "schema_version": pipeline.REQ_047_SCHEMA_VERSION,
                "requirement_id": pipeline.REQ_047_REQUIREMENT_ID,
                "analysis_type": pipeline.REQ_047_ANALYSIS_TYPE,
                "call_id": pipeline.REQ_047_CALL_ID,
                "checked_at_utc": result["checked_at_utc"],
                "llm_call_trace_rows": result["llm_call_trace_rows"],
                "final_output_artifacts": result["final_output_artifacts"],
                "llm_call_trace_and_decision_ledger": result["llm_call_trace_and_decision_ledger"],
                "totals": result["totals"],
            }
        )
        == []
    )

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
    assert usage["cross_project_projects_considered"] == ["apollo", "earth-index"]
    assert "reports/earth/sweeps/2026-03-16/portfolio.json" in recommendation["evidence_refs"]
    assert "reports/earth/sweeps/2026-03-16/apollo.json" in recommendation["evidence_refs"]
    assert "reports/earth/sweeps/2026-03-16/earth-index.json" in recommendation["evidence_refs"]
    assert recommendation["recommended_actions"]
    assert any(row["project_id"] == "apollo" for row in recommendation["cross_project_obligations"])
    assert any(row["project_id"] == "earth-index" for row in recommendation["cross_project_obligations"])
    assert any(row["reason_code"] == "unresolved_cross_project_idea" for row in recommendation["open_risks"])

    metadata = result["call_metadata"]
    assert metadata["reproducibility"] == "deterministic-input-fingerprint"
    assert metadata["reproducible_call_id"].startswith("req047-")
    assert metadata["processing_call_id"].startswith("req047-processing-")
    assert metadata["llm_call_trace_schema_version"] == "optimus-prime.llm-call-trace.v1"
    assert metadata["llm_call_trace_path"] == "strategy/current/llm_call_trace.jsonl"
    assert metadata["llm_call_trace_sha256"]
    assert metadata["decision_ledger_entries"] == len(payload["decision_ledger"])

    trace_rows = _read_trace_rows()
    assert metadata["llm_call_trace_rows"] == trace_rows
    assert len(trace_rows) == len(payload["llm_call_trace_rows"])
    for trace_row in trace_rows:
        assert trace_row["call_objective"]
        assert trace_row["input_refs"]
        assert trace_row["output_refs"]
        assert trace_row["handoff_summary"]
        assert trace_row["linked_final_output_artifact_refs"]
        assert set(trace_row["linked_final_output_artifact_refs"]).issubset(set(trace_row["output_refs"]))
        for artifact in trace_row["artifacts"]:
            assert artifact["path"].startswith("strategy/current/llm_call_trace_artifacts/req-047/")
            assert Path(artifact["path"]).exists()


def test_req047_processing_without_earth_refs_blocks_cross_project_obligations() -> None:
    _reset_call_trace()
    payload = _base_payload()
    payload["broad_sweep_context"] = {
        "earth_sweep_evidence_refs": [],
        "cross_project_context": [
            {
                "project_id": "apollo",
                "project_root": "/workspace/projects/Earth/apollo",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/apollo.json",
                ],
                "context_note": "Cross-project context exists, but Earth refs are not attached yet.",
            }
        ],
    }

    result = pipeline.process_req_047_llm_call_trace_and_decision_ledger(payload)
    recommendation = result["processing_behavior"]["recommendation"]
    usage = result["processing_behavior"]["context_usage"]

    assert recommendation["recommended_actions"] == []
    assert recommendation["cross_project_obligations"] == []
    assert any(row["reason_code"] == "missing_earth_sweep_evidence_refs" for row in recommendation["open_risks"])
    assert recommendation["decision"] == "collect-earth-evidence"
    assert usage["cross_project_context_used"] is True
    assert usage["earth_sweep_context_used"] is False


def test_req047_processing_call_metadata_is_replay_stable_across_input_reordering() -> None:
    _reset_call_trace()
    payload = _base_payload()
    payload["broad_sweep_context"] = {
        "earth_sweep_evidence_refs": [
            "reports/earth/sweeps/2026-03-16/portfolio.json",
        ],
        "cross_project_context": [
            {
                "project_id": "apollo",
                "project_root": "/workspace/projects/Earth/apollo",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/apollo.json",
                ],
                "context_note": "Apollo shares packet-level sequencing contracts with Optimus Prime.",
            },
            {
                "project_id": "earth-index",
                "project_root": "/workspace/projects/Earth/earth-index",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/earth-index.json",
                ],
                "context_note": "Earth-index consumes replay-analysis outputs for audit rollups.",
            },
        ],
    }

    first = pipeline.process_req_047_llm_call_trace_and_decision_ledger(payload)

    _reset_call_trace()
    reordered = dict(payload)
    reordered["llm_call_trace_rows"] = list(reversed(payload["llm_call_trace_rows"]))
    reordered["final_output_artifacts"] = list(reversed(payload["final_output_artifacts"]))
    reordered["decision_ledger"] = list(reversed(payload["decision_ledger"]))
    reordered["broad_sweep_context"] = dict(payload["broad_sweep_context"])
    reordered["broad_sweep_context"]["cross_project_context"] = list(
        reversed(payload["broad_sweep_context"]["cross_project_context"])
    )
    second = pipeline.process_req_047_llm_call_trace_and_decision_ledger(reordered)

    assert first["call_metadata"] == second["call_metadata"]
    assert first["call_metadata"]["canonical_input"] == second["call_metadata"]["canonical_input"]
    assert first["call_metadata"]["canonical_processing_input"] == second["call_metadata"]["canonical_processing_input"]
    assert first["call_metadata"]["llm_call_trace_rows"] == second["call_metadata"]["llm_call_trace_rows"]
