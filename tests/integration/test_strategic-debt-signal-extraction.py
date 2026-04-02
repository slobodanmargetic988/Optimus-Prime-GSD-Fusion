import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "strategy_context_sweep.py"
FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "fixtures"
    / "strategic-debt-signal-extraction.json"
)
SPEC = importlib.util.spec_from_file_location("strategy_context_sweep", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _load_fixture_payload() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_integration_strategic_debt_recommendation_is_complete_and_uses_cross_project_context() -> None:
    payload = _load_fixture_payload()

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
    assert recommendation["decision"] == "mitigate_strategic_debt_signals"
    assert recommendation["top_signal_id"] == "DEBT-SIGNAL-0001"
    assert recommendation["rationale"]

    signal_evidence_refs = {row["citation_id"] for row in evidence_references}
    earth_sweep_refs = {
        "reports/earth/sweeps/2026-03-15/optimus-prime-gsd-fusion.json",
        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
        "reports/earth/sweeps/2026-03-15/test-train-manager.json",
    }
    recommendation_refs = recommendation["evidence_refs"]
    assert recommendation_refs
    assert signal_evidence_refs.issubset(set(recommendation_refs))
    assert earth_sweep_refs.issubset(set(recommendation_refs))

    context = recommendation["cross_project_context"]
    assert context["cross_project"] is True
    assert context["projects_considered"] == [
        "optimus-prime-gsd-fusion",
        "runtime-orchestrator",
        "test-train-manager",
    ]
    assert context["projects_with_evidence_refs"] == [
        "optimus-prime-gsd-fusion",
        "runtime-orchestrator",
        "test-train-manager",
    ]
    assert context["projects_without_evidence_refs"] == []
    assert context["earth_sweep_evidence_refs"] == sorted(earth_sweep_refs)

    obligations = recommendation["obligations"]
    assert obligations == [
        {
            "obligation_id": "OBL-DEBT-0001",
            "summary": "Use Earth-sweep evidence to scope cross-project mitigation for prioritized strategic debt signals.",
            "evidence_refs": sorted(earth_sweep_refs),
        }
    ]
    assert recommendation["open_risks"] == []


def test_integration_strategic_debt_records_open_risks_when_cross_project_evidence_is_missing() -> None:
    payload = _load_fixture_payload()
    payload["broad_sweep_context"] = {
        "projects_considered": [
            "optimus-prime-gsd-fusion",
            "runtime-orchestrator",
        ],
        "evidence_refs_by_project": {
            "optimus-prime-gsd-fusion": [],
            "runtime-orchestrator": [],
        },
        "unresolved_ideas": [
            {
                "summary": "Standardize retry policy mitigation with runtime-orchestrator after Earth-sweep evidence is collected.",
                "evidence_refs": [
                    "ideas/strategic-debt/retry-policy-sync.md",
                ],
            }
        ],
    }

    out = MODULE.run(payload)
    recommendation = out["recommendation"]
    context = recommendation["cross_project_context"]

    assert context["cross_project"] is True
    assert context["projects_considered"] == [
        "optimus-prime-gsd-fusion",
        "runtime-orchestrator",
    ]
    assert context["projects_with_evidence_refs"] == []
    assert context["projects_without_evidence_refs"] == [
        "optimus-prime-gsd-fusion",
        "runtime-orchestrator",
    ]
    assert context["earth_sweep_evidence_refs"] == []

    assert recommendation["obligations"] == []
    assert recommendation["open_risks"] == [
        {
            "risk_id": "RISK-DEBT-0001",
            "summary": "Cross-project strategic debt mitigation is unresolved because Earth-sweep evidence refs are missing.",
            "reason_code": "earth_sweep_evidence_missing",
            "evidence_refs": [],
        },
        {
            "risk_id": "RISK-DEBT-0002",
            "summary": (
                "Earth-sweep evidence refs are missing for cross-project context rows: "
                "optimus-prime-gsd-fusion, runtime-orchestrator"
            ),
            "reason_code": "earth_sweep_evidence_missing",
            "evidence_refs": [],
        },
        {
            "risk_id": "RISK-DEBT-0003",
            "summary": (
                "Standardize retry policy mitigation with runtime-orchestrator after Earth-sweep evidence is"
                " collected."
            ),
            "reason_code": "unresolved_cross_project_idea",
            "evidence_refs": [
                "ideas/strategic-debt/retry-policy-sync.md",
            ],
        },
    ]
    assert "ideas/strategic-debt/retry-policy-sync.md" in recommendation["evidence_refs"]
