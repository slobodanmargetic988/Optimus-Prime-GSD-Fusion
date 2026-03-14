import copy
import json
from pathlib import Path

from scripts import strategy_context_sweep as module

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "research-packet-ingestion-and-normalization.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_008_integration_keeps_evidence_and_recommendation_fields_complete():
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_008_research_packet_ingestion_and_normalization(**fixture["input"])
    assert module.validate_req_008_research_packet_ingestion_and_normalization(payload) == []

    packet_evidence_ids = {
        row["artifact_id"]
        for row in fixture["input"]["research_packet"]["evidence_refs"]
    }

    for risk_row in payload["strategy_context"]["risk_evidence"]:
        assert risk_row["evidence_refs"]
        assert {ref["artifact_id"] for ref in risk_row["evidence_refs"]} == packet_evidence_ids

    for cross_project_row in payload["strategy_context"]["cross_project_context"]:
        assert cross_project_row["evidence_refs"]
        assert {ref["artifact_id"] for ref in cross_project_row["evidence_refs"]}.issubset(packet_evidence_ids)

    by_recommendation = {
        row["recommendation_id"]: row for row in payload["recommendation_rationale_provenance"]
    }
    for recommendation_id, row in by_recommendation.items():
        assert row["provenance_refs"]
        assert {ref["artifact_id"] for ref in row["provenance_refs"]} == packet_evidence_ids

        fields = row["recommendation_fields"]
        assert set(fields.keys()) == {"summary", "rationale", "expected_impact", "risk_level"}
        assert fields["summary"]
        assert fields["rationale"]
        assert fields["expected_impact"]
        assert fields["risk_level"] in module.ALLOWED_RISK_LEVELS
        assert recommendation_id in fixture["input"]["recommendation_ids"]


def test_req_008_integration_uses_cross_project_context_and_open_risks_links():
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_008_research_packet_ingestion_and_normalization(**fixture["input"])
    assert module.validate_req_008_research_packet_ingestion_and_normalization(payload) == []

    cross_context_ids = {
        row["cross_project_context_id"] for row in payload["strategy_context"]["cross_project_context"]
    }
    open_risk_ids = {
        row["open_risk_id"] for row in payload["strategy_context"]["open_risks"]
    }
    assert cross_context_ids == {"cross-project-context.001.prj-runtime-core"}
    assert open_risk_ids == {"open-risk.001.prj-analytics-hub", "open-risk.002.prj-runtime-observability"}

    by_recommendation = {
        row["recommendation_id"]: row for row in payload["recommendation_rationale_provenance"]
    }
    assert by_recommendation["rec.dispatch-signal-watcher"]["linked_cross_project_context_ids"] == [
        "cross-project-context.001.prj-runtime-core"
    ]
    assert by_recommendation["rec.dispatch-signal-watcher"]["linked_open_risk_ids"] == []

    assert by_recommendation["rec.rate-limit-safety-lane"]["linked_cross_project_context_ids"] == []
    assert by_recommendation["rec.rate-limit-safety-lane"]["linked_open_risk_ids"] == [
        "open-risk.001.prj-analytics-hub",
        "open-risk.002.prj-runtime-observability",
    ]


def test_req_008_integration_requires_obligation_level_earth_evidence():
    fixture = _read_json(FIXTURE_PATH)
    test_input = copy.deepcopy(fixture["input"])
    broad_sweep = test_input["research_packet"]["context"]["broad_sweep_context"]
    broad_sweep["earth_sweep_evidence_refs"] = ["artifact.dispatch-cycle-canary-20260314"]
    broad_sweep["cross_project_obligations"] = [
        {
            "target_project_id": "prj.example-without-local-evidence",
            "summary": "Candidate obligation missing local evidence.",
            "recommendation_ids": ["rec.dispatch-signal-watcher"],
        }
    ]
    broad_sweep["unresolved_ideas"] = []

    payload = module.build_req_008_research_packet_ingestion_and_normalization(**test_input)
    assert module.validate_req_008_research_packet_ingestion_and_normalization(payload) == []
    assert payload["strategy_context"]["cross_project_context"] == []
    assert [row["open_risk_id"] for row in payload["strategy_context"]["open_risks"]] == [
        "open-risk.001.prj-example-without-local-evidence"
    ]
