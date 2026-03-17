import json
from pathlib import Path

import pytest

from scripts.strategy_context_sweep import (
    extract_strategic_debt_signals,
    validate_req_018_strategic_debt_signal_extraction,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "strategic-debt-signal-extraction.json"
SAMPLE_PATH = REPO_ROOT / "strategy" / "current" / "samples" / "REQ-018_strategic-debt-signal-extraction.sample.json"
CONTRACT_DOC_PATH = REPO_ROOT / "contracts" / "req" / "REQ-018_strategic-debt-signal-extraction.md"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_018_extracts_strategic_debt_signals_with_recurrence_and_blast_radius() -> None:
    payload = _read_json(FIXTURE_PATH)
    output = extract_strategic_debt_signals(payload)

    assert output["ok"] is True
    assert output["requirement_id"] == "REQ-018"
    assert output["schema_version"] == "req-018.strategic-debt-signal-extraction.v1"
    assert output["analysis_type"] == "strategic_debt_signal_extraction"
    assert output["evaluated_at"] == "2026-03-15T03:20:00Z"
    assert output["analysis_anchors"] == [
        "future_velocity_degradation",
        "recurrence",
        "likely_blast_radius",
    ]
    assert output["thresholds"] == {
        "min_recurrence_count": 3,
        "min_likely_blast_radius": 2,
    }
    assert output["max_signals"] == 3

    strategic_debt_signals = output["strategic_debt_signals"]
    assert [row["signal_id"] for row in strategic_debt_signals] == [
        "DEBT-SIGNAL-0001",
        "DEBT-SIGNAL-0002",
        "DEBT-SIGNAL-0003",
    ]
    assert [row["debt_id"] for row in strategic_debt_signals] == ["DEBT-001", "DEBT-002", "DEBT-005"]
    assert strategic_debt_signals[0]["priority_score"] == 21.0
    assert strategic_debt_signals[0]["recurrence_count"] == 7
    assert strategic_debt_signals[0]["likely_blast_radius"] == 3
    assert strategic_debt_signals[1]["priority_score"] == 20.0
    assert strategic_debt_signals[1]["blast_radius_tier"] == "cross-project"
    assert strategic_debt_signals[2]["priority_score"] == 8.0
    assert strategic_debt_signals[2]["blast_radius_tier"] == "project-scoped"

    excluded = {row["debt_id"]: row for row in output["excluded_debt_observations"]}
    assert excluded["DEBT-003"]["reason_code"] == "recurrence_below_threshold"
    assert excluded["DEBT-003"]["failed_criteria"] == ["recurrence_below_threshold"]
    assert excluded["DEBT-004"]["reason_code"] == "blast_radius_below_threshold"
    assert excluded["DEBT-004"]["failed_criteria"] == ["blast_radius_below_threshold"]
    assert excluded["DEBT-006"]["reason_code"] == "max_signals_cap_reached"
    assert excluded["DEBT-006"]["failed_criteria"] == ["max_signals_cap_reached"]

    evidence_references = output["evidence_references"]
    assert [row["citation_id"] for row in evidence_references] == [
        "EVD-0001",
        "EVD-0002",
        "EVD-0003",
        "EVD-0004",
    ]
    assert evidence_references[0]["debt_id"] == "DEBT-001"
    assert evidence_references[-1]["debt_id"] == "DEBT-005"

    recommendation = output["recommendation"]
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
    assert recommendation["evidence_refs"] == [
        "EVD-0001",
        "EVD-0002",
        "EVD-0003",
        "EVD-0004",
        "reports/earth/sweeps/2026-03-15/optimus-prime-gsd-fusion.json",
        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
        "reports/earth/sweeps/2026-03-15/test-train-manager.json",
    ]
    assert recommendation["cross_project_context"] == {
        "cross_project": True,
        "projects_considered": [
            "optimus-prime-gsd-fusion",
            "runtime-orchestrator",
            "test-train-manager",
        ],
        "projects_with_evidence_refs": [
            "optimus-prime-gsd-fusion",
            "runtime-orchestrator",
            "test-train-manager",
        ],
        "projects_without_evidence_refs": [],
        "evidence_refs_by_project": {
            "optimus-prime-gsd-fusion": [
                "reports/earth/sweeps/2026-03-15/optimus-prime-gsd-fusion.json",
            ],
            "runtime-orchestrator": [
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
            ],
            "test-train-manager": [
                "reports/earth/sweeps/2026-03-15/test-train-manager.json",
            ],
        },
        "earth_sweep_evidence_refs": [
            "reports/earth/sweeps/2026-03-15/optimus-prime-gsd-fusion.json",
            "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
            "reports/earth/sweeps/2026-03-15/test-train-manager.json",
        ],
        "unresolved_ideas": [],
    }
    assert recommendation["obligations"] == [
        {
            "obligation_id": "OBL-DEBT-0001",
            "summary": "Use Earth-sweep evidence to scope cross-project mitigation for prioritized strategic debt signals.",
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-15/optimus-prime-gsd-fusion.json",
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                "reports/earth/sweeps/2026-03-15/test-train-manager.json",
            ],
        }
    ]
    assert recommendation["open_risks"] == []

    totals = output["totals"]
    assert totals == {
        "debt_observations": 6,
        "eligible": 4,
        "signals": 3,
        "excluded": 3,
        "evidence_references": 4,
    }

    assert validate_req_018_strategic_debt_signal_extraction(output) == []


def test_req_018_sample_matches_extraction_output_for_fixture() -> None:
    payload = _read_json(FIXTURE_PATH)
    expected = extract_strategic_debt_signals(payload)
    sample = _read_json(SAMPLE_PATH)
    assert sample == expected


def test_req_018_contract_doc_includes_sample_structure_reference() -> None:
    content = CONTRACT_DOC_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-018_strategic-debt-signal-extraction.sample.json" in content
    for key in [
        "requirement_id",
        "schema_version",
        "analysis_type",
        "evaluated_at",
        "analysis_anchors",
        "active_project_id",
        "thresholds",
        "max_signals",
        "strategic_debt_signals",
        "excluded_debt_observations",
        "evidence_references",
        "recommendation",
        "totals",
    ]:
        assert f"`{key}`" in content


def test_req_018_rejects_duplicate_debt_ids() -> None:
    payload = _read_json(FIXTURE_PATH)
    duplicated = dict(payload)
    duplicated["debt_observations"] = list(payload["debt_observations"])
    duplicated["debt_observations"][1] = dict(payload["debt_observations"][0])

    with pytest.raises(ValueError, match=r"debt_id must be unique"):
        extract_strategic_debt_signals(duplicated)
