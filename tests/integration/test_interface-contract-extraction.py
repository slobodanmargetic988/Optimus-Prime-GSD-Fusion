import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "strategy_context_sweep.py"
SPEC = importlib.util.spec_from_file_location("strategy_context_sweep", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


FIXTURE_PATH = Path(__file__).resolve().parents[2] / "examples" / "fixtures" / "interface-contract-extraction.json"


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_req012_recommendations_have_complete_fields_and_evidence_refs():
    payload = _load_fixture()
    out = MODULE.extract_interface_contracts(payload, generated_at="2026-03-15T00:00:00Z")
    recommendations = out["cross_project_recommendations"]

    assert recommendations
    assert out["summary"]["recommendation_count"] == len(recommendations)
    assert out["summary"]["open_risk_count"] == 0

    required_fields = {
        "recommendation_id",
        "recommendation_type",
        "source_project_id",
        "target_project_id",
        "interface_id",
        "obligation_id",
        "obligation_level",
        "summary",
        "rationale",
        "source_provenance",
        "evidence_refs",
        "cross_project_context",
    }
    for recommendation in recommendations:
        assert required_fields.issubset(recommendation.keys())
        assert recommendation["recommendation_type"] == "interface_obligation"
        assert recommendation["source_project_id"] in {"earth-shared-interfaces", "earth-targeted-interface"}
        assert recommendation["target_project_id"] == "optimus-prime-gsd-fusion"
        assert recommendation["obligation_level"] in {"required", "optional"}
        assert isinstance(recommendation["summary"], str) and recommendation["summary"]
        assert isinstance(recommendation["rationale"], str) and recommendation["rationale"]
        assert isinstance(recommendation["source_provenance"], list) and recommendation["source_provenance"]
        assert isinstance(recommendation["evidence_refs"], list) and recommendation["evidence_refs"]
        assert all(ref.startswith("earth-sweep/") for ref in recommendation["evidence_refs"])

        context = recommendation["cross_project_context"]
        assert context["context_type"] == "earth_sweep"
        assert isinstance(context["match_keys"], list) and context["match_keys"]
        assert context["evidence_ref_count"] == len(recommendation["evidence_refs"])


def test_req012_uses_cross_project_earth_sweep_context_deterministically():
    payload = _load_fixture()
    out = MODULE.extract_interface_contracts(payload, generated_at="2026-03-15T00:00:00Z")

    assert out["summary"]["earth_contract_source_count"] == 3
    assert out["summary"]["relevant_source_count"] == 2
    assert out["summary"]["shared_interface_contract_count"] == 3
    assert out["summary"]["total_obligation_count"] == 6
    assert out["summary"]["recommendation_count"] == 6
    assert out["summary"]["open_risk_count"] == 0
    assert out["summary"]["earth_sweep_context_entry_count"] == 6
    assert out["summary"]["earth_sweep_evidence_refs_used_count"] == 6

    unique_refs = {
        ref
        for recommendation in out["cross_project_recommendations"]
        for ref in recommendation["evidence_refs"]
    }
    assert len(unique_refs) == out["summary"]["earth_sweep_evidence_refs_used_count"]


def test_req012_missing_earth_sweep_ref_records_open_risk_instead_of_recommendation():
    payload = _load_fixture()
    payload["earth_sweep_context"]["evidence_refs"] = [
        item
        for item in payload["earth_sweep_context"]["evidence_refs"]
        if not (
            item["peer_project_id"] == "earth-shared-interfaces"
            and item["source_path"] == "earth/contracts/shared-interfaces.md"
            and item["line_number"] == 2
        )
    ]

    out = MODULE.extract_interface_contracts(payload, generated_at="2026-03-15T00:00:00Z")

    assert out["summary"]["recommendation_count"] == 5
    assert out["summary"]["open_risk_count"] == 1
    assert len(out["open_risks"]) == 1

    open_risk = out["open_risks"][0]
    assert open_risk["risk_type"] == "missing_earth_sweep_evidence"
    assert open_risk["reason_code"] == "missing_earth_sweep_evidence_refs"
    assert open_risk["recommendation_type"] == "interface_obligation"
    assert open_risk["source_project_id"] == "earth-shared-interfaces"
    assert open_risk["target_project_id"] == "optimus-prime-gsd-fusion"
    assert open_risk["required_context_match_keys"] == [
        "earth-shared-interfaces:earth/contracts/shared-interfaces.md:2"
    ]
    assert isinstance(open_risk["source_provenance"], list) and open_risk["source_provenance"]
    assert open_risk["evidence_refs"] == []
