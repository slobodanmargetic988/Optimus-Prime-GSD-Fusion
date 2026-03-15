import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "strategy_context_sweep.py"
FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "fixtures"
    / "deficit-and-need-signal-extraction.json"
)
SPEC = importlib.util.spec_from_file_location("strategy_context_sweep", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _load_fixture_payload() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_integration_need_signal_recommendation_is_complete_and_uses_cross_project_context() -> None:
    payload = _load_fixture_payload()
    payload["broad_sweep_context"] = {
        "projects_considered": ["earth-north", "earth-south"],
        "evidence_refs_by_project": {
            "earth-north": ["SRC-1001"],
            "earth-south": ["SRC-2001", "SRC-2002"],
        },
    }

    out = MODULE.run(payload)
    recommendation = out["recommendation"]
    evidence_references = out["evidence_references"]

    assert set(recommendation.keys()) == {
        "decision",
        "rationale",
        "top_signal_id",
        "evidence_refs",
        "cross_project_context",
        "obligations",
        "open_risks",
    }
    assert recommendation["decision"] == "prioritize_need_signals"
    assert recommendation["top_signal_id"] == "NEED-0001"
    assert recommendation["rationale"]

    signal_evidence_refs = {row["citation_id"] for row in evidence_references}
    earth_sweep_refs = {"SRC-1001", "SRC-2001", "SRC-2002"}
    recommendation_refs = recommendation["evidence_refs"]
    assert recommendation_refs
    assert all(ref in (signal_evidence_refs | earth_sweep_refs) for ref in recommendation_refs)
    assert signal_evidence_refs.issubset(set(recommendation_refs))
    assert earth_sweep_refs.issubset(set(recommendation_refs))

    context = recommendation["cross_project_context"]
    assert context["cross_project"] is True
    assert context["projects_considered"] == ["earth-north", "earth-south"]
    assert context["projects_with_evidence_refs"] == ["earth-north", "earth-south"]
    assert context["projects_without_evidence_refs"] == []
    assert context["evidence_refs_by_project"]["earth-north"] == ["SRC-1001"]
    assert context["evidence_refs_by_project"]["earth-south"] == ["SRC-2001", "SRC-2002"]
    assert context["earth_sweep_evidence_refs"] == ["SRC-1001", "SRC-2001", "SRC-2002"]

    obligations = recommendation["obligations"]
    assert obligations == [
        {
            "obligation_id": "OBL-NEED-0001",
            "summary": "Validate prioritized need signals against Earth-sweep cross-project evidence before execution.",
            "evidence_refs": ["SRC-1001", "SRC-2001", "SRC-2002"],
        }
    ]
    assert recommendation["open_risks"] == []


def test_integration_need_signal_records_open_risk_when_cross_project_evidence_is_missing() -> None:
    payload = _load_fixture_payload()
    payload["broad_sweep_context"] = {
        "projects_considered": ["earth-north", "earth-south"],
        "evidence_refs_by_project": {
            "earth-north": [],
            "earth-south": [],
        },
    }

    out = MODULE.run(payload)
    recommendation = out["recommendation"]
    context = recommendation["cross_project_context"]

    assert context["cross_project"] is True
    assert context["projects_considered"] == ["earth-north", "earth-south"]
    assert context["projects_with_evidence_refs"] == []
    assert context["projects_without_evidence_refs"] == ["earth-north", "earth-south"]
    assert context["earth_sweep_evidence_refs"] == []

    assert recommendation["obligations"] == []
    risk_ids = {row["risk_id"] for row in recommendation["open_risks"]}
    assert "RISK-NEED-0001" in risk_ids
    assert "RISK-NEED-0002" in risk_ids
    for risk in recommendation["open_risks"]:
        assert risk["summary"]
        assert risk["evidence_refs"] == []
