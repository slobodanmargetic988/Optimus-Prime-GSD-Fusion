import json
from pathlib import Path

from scripts import strategy_context_sweep as module

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "risk-signal-normalization.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_020_integration_normalizes_risk_signals_with_evidence_and_recommendation_fields():
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_020_risk_signal_normalization(**fixture["input"])
    assert module.validate_req_020_risk_signal_normalization(payload) == []

    normalized_signals = payload["risk_signal_normalization"]["normalized_risk_signals"]
    assert normalized_signals

    for row in normalized_signals:
        assert row["evidence_refs"]
        assert row["risk_level"] in module.REQ_020_ALLOWED_RISK_LEVELS
        assert row["signal_kind"] in module.REQ_020_ALLOWED_SIGNAL_KINDS

    recommendation = payload["processing_behavior"]["recommendation"]
    assert set(recommendation.keys()) == {
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "recommended_actions",
        "cross_project_obligations",
        "open_risks",
    }
    assert recommendation["decision"] in module.REQ_020_ALLOWED_DECISIONS
    assert recommendation["rationale"]
    assert recommendation["confidence"] in module.REQ_020_ALLOWED_CONFIDENCE_LABELS
    assert recommendation["evidence_refs"]


def test_req_020_integration_uses_cross_project_context_evidence_refs_when_linked():
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_020_risk_signal_normalization(**fixture["input"])
    assert module.validate_req_020_risk_signal_normalization(payload) == []

    cross_ref = "reports/earth/sweeps/2026-03-15/ground-control-hub.json"
    cross_project_used = payload["processing_behavior"]["context_usage"]
    assert cross_project_used["cross_project_context_used"] is True
    assert cross_ref in cross_project_used["cross_project_refs_used"]
    assert cross_ref in cross_project_used["evidence_refs_used"]

    linked_signals = [
        row
        for row in payload["risk_signal_normalization"]["normalized_risk_signals"]
        if cross_ref in row["evidence_refs"]
    ]
    assert linked_signals

