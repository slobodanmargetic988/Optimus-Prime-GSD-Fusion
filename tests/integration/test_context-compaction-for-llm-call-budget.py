import copy
import json
from pathlib import Path

from scripts import strategy_context_sweep as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "context-compaction-for-llm-call-budget.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_023_integration_compacts_broad_sweep_context_into_traceable_packets() -> None:
    fixture = _read_json(FIXTURE_PATH)

    payload = module.build_req_023_context_compaction_for_llm_call_budget(**fixture["input"])
    assert module.validate_req_023_context_compaction_for_llm_call_budget(payload) == []

    processing = payload["processing_behavior"]
    recommendation = processing["recommendation"]
    usage = processing["context_usage"]
    compaction = processing["context_compaction"]
    coverage = compaction["coverage"]

    assert recommendation["decision"] == "proceed-with-open-risks"
    assert set(recommendation.keys()) == {
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "recommended_actions",
        "cross_project_obligations",
        "open_risks",
    }
    assert recommendation["rationale"]
    assert recommendation["confidence"]
    assert recommendation["evidence_refs"] == compaction["mandatory_traceability_refs"]
    assert recommendation["evidence_refs"] == usage["context_compaction_traceability_refs_used"]
    assert recommendation["evidence_refs"] == usage["evidence_refs_used"]

    assert coverage["uncovered_action_ids"] == []
    assert coverage["uncovered_obligation_ids"] == []
    assert coverage["uncovered_risk_ids"] == []
    assert coverage["uncovered_hard_constraint_ids"] == []

    assert usage["cross_project_context_used"] is True
    assert usage["cross_project_projects_considered"] == [
        "ground-control-hub",
        "runtime-orchestrator",
    ]
    assert usage["cross_project_refs_used"] == [
        "reports/earth/sweeps/2026-03-15/ground-control-hub.json",
        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
    ]
    assert usage["context_compaction_used"] is True
    assert usage["context_compaction_packet_ids"] == [row["packet_id"] for row in compaction["compacted_packets"]]

    assert [row["action_id"] for row in recommendation["recommended_actions"]] == [
        "compact-constraint-preservation",
        "compact-context-traceability",
        "compact-req-023-contract",
    ]
    for row in recommendation["recommended_actions"]:
        assert set(row.keys()) == {
            "action_id",
            "summary",
            "rationale",
            "action_scope",
            "next_step",
            "evidence_refs",
        }
        assert row["summary"]
        assert row["rationale"]
        assert row["next_step"]
        assert row["evidence_refs"]

    assert recommendation["cross_project_obligations"] == [
        {
            "obligation_id": "obligation-compact-constraint-preservation",
            "project_id": "runtime-orchestrator",
            "summary": "Retain hard constraints when context is compacted for multiple LLM calls.",
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-15/portfolio.json",
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
            ],
        },
        {
            "obligation_id": "obligation-compact-context-traceability",
            "project_id": "ground-control-hub",
            "summary": "Preserve traceability refs inside compacted context packets.",
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-15/ground-control-hub.json",
                "reports/earth/sweeps/2026-03-15/portfolio.json",
            ],
        },
    ]

    for row in recommendation["open_risks"]:
        assert set(row.keys()) == {"risk_id", "summary", "reason_code", "required_evidence_refs"}
        assert row["summary"]
        assert row["required_evidence_refs"]

    packet_project_ids = {
        project_id
        for row in compaction["compacted_packets"]
        for project_id in row["project_ids"]
    }
    assert packet_project_ids == {"ground-control-hub", "runtime-orchestrator"}


def test_req_023_integration_keeps_cross_project_ideas_as_open_risks_without_earth_refs() -> None:
    fixture = _read_json(FIXTURE_PATH)
    test_input = copy.deepcopy(fixture["input"])
    test_input["earth_sweep_evidence_refs"] = []

    payload = module.build_req_023_context_compaction_for_llm_call_budget(**test_input)
    assert module.validate_req_023_context_compaction_for_llm_call_budget(payload) == []

    processing = payload["processing_behavior"]
    recommendation = processing["recommendation"]
    usage = processing["context_usage"]
    compaction = processing["context_compaction"]

    assert recommendation["decision"] == "proceed-with-open-risks"
    assert [row["action_id"] for row in recommendation["recommended_actions"]] == [
        "compact-req-023-contract"
    ]
    assert recommendation["cross_project_obligations"] == []
    assert usage["cross_project_context_used"] is True
    assert usage["cross_project_projects_considered"] == [
        "ground-control-hub",
        "runtime-orchestrator",
    ]
    assert "reports/earth/sweeps/2026-03-15/ground-control-hub.json" in recommendation["evidence_refs"]
    assert "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json" in recommendation["evidence_refs"]
    assert compaction["mandatory_traceability_refs"] == recommendation["evidence_refs"]

    missing_earth_risks = [
        row for row in recommendation["open_risks"] if row["reason_code"] == "missing_earth_sweep_evidence_refs"
    ]
    assert missing_earth_risks == [
        {
            "risk_id": "risk-compact-constraint-preservation",
            "summary": "Retain hard constraints when context is compacted for multiple LLM calls.",
            "reason_code": "missing_earth_sweep_evidence_refs",
            "required_evidence_refs": [
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
            ],
        },
        {
            "risk_id": "risk-compact-context-traceability",
            "summary": "Preserve traceability refs inside compacted context packets.",
            "reason_code": "missing_earth_sweep_evidence_refs",
            "required_evidence_refs": [
                "reports/earth/sweeps/2026-03-15/ground-control-hub.json",
            ],
        },
    ]
