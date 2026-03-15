import copy
import json
from pathlib import Path

from scripts import strategy_context_sweep as module

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "integration-opportunity-detection.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_015_integration_keeps_evidence_refs_and_recommendation_fields_complete():
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_015_integration_opportunity_detection(**fixture["input"])
    assert module.validate_req_015_integration_opportunity_detection(payload) == []

    evidence_ids = {row["artifact_id"] for row in fixture["input"]["evidence_refs"]}
    recommendation_ids = {row["recommendation_id"] for row in fixture["input"]["recommendations"]}

    for row in payload["integration_opportunities"]:
        assert row["evidence_refs"]
        assert {ref["artifact_id"] for ref in row["evidence_refs"]}.issubset(evidence_ids)

        assert row["recommendation_id"] in recommendation_ids
        fields = row["recommendation_fields"]
        assert set(fields.keys()) == {"summary", "rationale", "expected_impact", "risk_level"}
        assert fields["summary"]
        assert fields["rationale"]
        assert fields["expected_impact"]
        assert fields["risk_level"] in module.ALLOWED_RISK_LEVELS


def test_req_015_integration_uses_cross_project_context_and_open_risks_for_unresolved_items():
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_015_integration_opportunity_detection(**fixture["input"])
    assert module.validate_req_015_integration_opportunity_detection(payload) == []

    opportunity_peer_ids = {row["peer_project_id"] for row in payload["integration_opportunities"]}
    assert opportunity_peer_ids == {"prj.runtime-core"}

    reason_codes = {row["reason_code"] for row in payload["open_risks"]}
    assert reason_codes == {"earth_sweep_evidence_missing", "unresolved_idea_open_risk"}

    open_risk_targets = {row.get("target_project_id") for row in payload["open_risks"]}
    assert open_risk_targets == {"prj.analytics-hub", "prj.runtime-observability"}

    for row in payload["integration_opportunities"]:
        assert "broad_sweep_context.cross_project_obligations[]" in row["provenance"]["source_fields"]


def test_req_015_integration_requires_obligation_level_earth_sweep_evidence():
    fixture = _read_json(FIXTURE_PATH)
    test_input = copy.deepcopy(fixture["input"])
    broad_sweep = test_input["broad_sweep_context"]
    broad_sweep["cross_project_obligations"] = [
        {
            "target_project_id": "prj.example-without-local-evidence",
            "summary": "Candidate obligation missing local evidence.",
            "recommendation_ids": ["rec.dispatch-signal-watcher"],
            "expected_interaction_contract": {
                "interaction_type": "batch_export",
                "producer_component": "dispatcher",
                "consumer_component": "example-loader",
                "interface": "example-ingestion-v1",
                "data_contract": "cycle_id, queue_depth"
            },
            "dependency_side_effect_notes": [
                "Missing local evidence must keep this in open risk state."
            ]
        }
    ]
    broad_sweep["unresolved_ideas"] = []

    payload = module.build_req_015_integration_opportunity_detection(**test_input)
    assert module.validate_req_015_integration_opportunity_detection(payload) == []
    assert payload["integration_opportunities"] == []
    assert [row["open_risk_id"] for row in payload["open_risks"]] == [
        "open-risk.001.prj-example-without-local-evidence"
    ]
    assert payload["open_risks"][0]["reason_code"] == "earth_sweep_evidence_missing"
