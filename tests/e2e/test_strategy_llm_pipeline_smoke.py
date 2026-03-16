import json
import shutil
from pathlib import Path

from scripts import strategy_llm_pipeline as pipeline


def _reset_trace_state() -> None:
    trace_path = Path("strategy/current/llm_call_trace.jsonl")
    if trace_path.exists():
        trace_path.unlink()
    artifacts_dir = Path("strategy/current/llm_call_trace_artifacts")
    if artifacts_dir.exists():
        shutil.rmtree(artifacts_dir)


def test_strategy_llm_pipeline_emits_req027_call_trace_and_evidence_references() -> None:
    _reset_trace_state()
    payload = {
        "analysis_type": pipeline.REQ_027_ANALYSIS_TYPE,
        "now_utc": "2026-03-16T12:00:00Z",
        "target_project": {
            "project_id": "optimus-prime-gsd-fusion",
            "project_root": "/workspace/projects/optimus-prime-gsd-fusion",
        },
        "peer_projects": [
            {"project_id": "earth-ops", "project_root": "/workspace/projects/Earth/earth-ops"},
        ],
        "broad_sweep_context": {
            "earth_sweep_evidence_refs": [
                "reports/earth/sweeps/2026-03-14/portfolio.json",
            ],
            "earth_sweep": {
                "projects": [
                    {
                        "project_id": "earth-ops",
                        "obligations": [
                            {
                                "summary": "Adopt shared release tag format for handoff reports.",
                                "earth_sweep_evidence_refs": [
                                    "reports/earth-ops/planning/evidence/TASK-042/TASK_EVIDENCE.json",
                                ],
                            }
                        ],
                    }
                ]
            },
            "cross_project_context": [
                {
                    "project_id": "earth-ops",
                    "project_root": "/workspace/projects/Earth/earth-ops",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-14/earth-ops.json",
                    ],
                    "context_note": "Earth-wide context for shared release conventions.",
                }
            ],
        },
    }

    result = pipeline.process_req_027_call_2_ecosystem_linkage_reasoning(payload)
    assert result["ok"] is True

    trace_path = Path("strategy/current/llm_call_trace.jsonl")
    lines = trace_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])

    assert row["requirement_id"] == pipeline.REQ_027_REQUIREMENT_ID
    assert row["call_id"] == pipeline.REQ_027_CALL_ID
    assert row["analysis_type"] == pipeline.REQ_027_ANALYSIS_TYPE
    assert row["checked_at_utc"] == payload["now_utc"]
    assert row["call_objective"]
    assert row["input_refs"]
    assert row["output_refs"]
    assert row["handoff_summary"]
    assert row["artifacts"]

    for artifact in row["artifacts"]:
        assert Path(artifact["path"]).exists()
        assert artifact["sha256"]

    evidence_path = Path("reports/optimus-prime/planning/evidence/TASK-089/TASK_EVIDENCE.json")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    artifacts = evidence["dev"]["artifacts"]
    assert "strategy/current/llm_call_trace.jsonl" in artifacts
    assert any("strategy/current/llm_call_trace_artifacts/req-027/call-2" in item for item in artifacts)

