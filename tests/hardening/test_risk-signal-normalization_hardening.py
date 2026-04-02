import copy
import json
from pathlib import Path

from scripts import strategy_context_sweep as module

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "risk-signal-normalization.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _base_req_020_input() -> dict:
    fixture = _read_json(FIXTURE_PATH)
    return copy.deepcopy(fixture["input"])


def test_req_020_hardening_emits_open_risks_for_cross_project_signals_without_earth_evidence():
    test_input = _base_req_020_input()
    test_input["earth_sweep_evidence_refs"] = []

    payload = module.build_req_020_risk_signal_normalization(**test_input)
    assert module.validate_req_020_risk_signal_normalization(payload) == []

    recommendation = payload["processing_behavior"]["recommendation"]
    assert recommendation["cross_project_obligations"] == []

    open_risks = recommendation["open_risks"]
    assert open_risks
    reason_codes = {row.get("reason_code") for row in open_risks if isinstance(row, dict)}
    assert "missing_earth_sweep_evidence_refs" in reason_codes

    for row in open_risks:
        if isinstance(row, dict) and row.get("reason_code") == "missing_earth_sweep_evidence_refs":
            assert row["required_evidence_refs"]


def test_req_020_hardening_preserves_stale_earth_sweep_reason_code_and_evidence_refs():
    test_input = _base_req_020_input()
    test_input["risk_sources"]["blockers"].append(
        {
            "signal_ref": "blocker.earth-sweep-stale-artifact",
            "summary": "Earth sweep detected a stale upstream planning artifact during replay hardening.",
            "risk_level": "high",
            "reason_codes": ["stale_source_artifact_detected"],
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.audit.json",
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
            ],
            "detected_at_utc": "2026-03-15T09:57:00Z",
        }
    )

    payload = module.build_req_020_risk_signal_normalization(**test_input)
    assert module.validate_req_020_risk_signal_normalization(payload) == []

    stale_signal = next(
        row
        for row in payload["risk_signal_normalization"]["normalized_risk_signals"]
        if row["signal_ref"] == "blocker.earth-sweep-stale-artifact"
    )
    assert stale_signal["signal_kind"] == "blocker"
    assert stale_signal["reason_codes"] == ["stale_source_artifact_detected"]
    assert stale_signal["evidence_refs"] == [
        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.audit.json",
        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
    ]


def test_req_020_hardening_preserves_missing_doc_reason_codes_with_explicit_evidence_refs():
    test_input = _base_req_020_input()
    test_input["risk_sources"] = {
        "blockers": [
            {
                "signal_ref": "blocker.target-mission-missing",
                "summary": "Target mission document is missing from the replay context bundle.",
                "reason_codes": ["mission_missing"],
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-064/mission.md#missing",
                ],
            },
            {
                "signal_ref": "blocker.target-scope-missing",
                "summary": "Target scope document is missing from the replay context bundle.",
                "reason_codes": ["scope_missing"],
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-064/scope.md#missing",
                ],
            },
            {
                "signal_ref": "blocker.peer-project-doc-missing",
                "project_id": "ground-control-hub",
                "summary": "Required peer-project handoff doc is missing during gate review replay.",
                "reason_codes": ["missing_peer_project_doc"],
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/ground-control-hub.json",
                ],
            },
        ],
        "retries": [],
        "watchdog_exits": [],
        "regression_patterns": [],
    }

    payload = module.build_req_020_risk_signal_normalization(**test_input)
    assert module.validate_req_020_risk_signal_normalization(payload) == []

    reason_codes_by_signal = {
        row["signal_ref"]: row["reason_codes"]
        for row in payload["risk_signal_normalization"]["normalized_risk_signals"]
    }
    evidence_by_signal = {
        row["signal_ref"]: row["evidence_refs"]
        for row in payload["risk_signal_normalization"]["normalized_risk_signals"]
    }

    assert reason_codes_by_signal["blocker.target-mission-missing"] == ["mission_missing"]
    assert reason_codes_by_signal["blocker.target-scope-missing"] == ["scope_missing"]
    assert reason_codes_by_signal["blocker.peer-project-doc-missing"] == ["missing_peer_project_doc"]
    assert evidence_by_signal["blocker.target-mission-missing"] == [
        "reports/optimus-prime/planning/evidence/TASK-064/mission.md#missing",
    ]
    assert evidence_by_signal["blocker.target-scope-missing"] == [
        "reports/optimus-prime/planning/evidence/TASK-064/scope.md#missing",
    ]
    assert evidence_by_signal["blocker.peer-project-doc-missing"] == [
        "reports/earth/sweeps/2026-03-15/ground-control-hub.json",
    ]


def test_req_020_hardening_context_bundle_serialization_is_replay_stable():
    first_input = _base_req_020_input()
    first_input["target_project_evidence_refs"] = [
        "reports/optimus-prime/planning/evidence/TASK-064/context.json",
        "reports/optimus-prime/planning/evidence/TASK-063/TASK_EVIDENCE.json",
        "reports/optimus-prime/planning/evidence/TASK-064/context.json",
    ]
    first_input["earth_sweep_evidence_refs"] = [
        "reports/earth/sweeps/2026-03-15/portfolio.json",
        "reports/earth/sweeps/2026-03-15/portfolio.json",
    ]
    first_input["risk_sources"]["blockers"].append(
        {
            "signal_ref": "blocker.serialization-stability",
            "summary": "Serialization stability must survive repeated replay runs.",
            "reason_codes": ["replay_serialization_check"],
            "evidence_refs": [
                "reports/optimus-prime/planning/evidence/TASK-064/context.json",
            ],
        }
    )

    second_input = _base_req_020_input()
    second_input["target_project_evidence_refs"] = [
        "reports/optimus-prime/planning/evidence/TASK-063/TASK_EVIDENCE.json",
        "reports/optimus-prime/planning/evidence/TASK-064/context.json",
    ]
    second_input["earth_sweep_evidence_refs"] = [
        "reports/earth/sweeps/2026-03-15/portfolio.json",
    ]
    second_input["risk_sources"]["blockers"].append(
        {
            "signal_ref": "blocker.serialization-stability",
            "summary": "Serialization stability must survive repeated replay runs.",
            "reason_codes": ["replay_serialization_check"],
            "evidence_refs": [
                "reports/optimus-prime/planning/evidence/TASK-064/context.json",
            ],
        }
    )

    first = module.build_req_020_risk_signal_normalization(**first_input)
    second = module.build_req_020_risk_signal_normalization(**second_input)
    third = module.build_req_020_risk_signal_normalization(**first_input)

    assert module.validate_req_020_risk_signal_normalization(first) == []
    assert module.validate_req_020_risk_signal_normalization(second) == []
    assert module.validate_req_020_risk_signal_normalization(third) == []

    first_bundle = json.dumps(
        first["call_metadata"]["canonical_processing_input"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    second_bundle = json.dumps(
        second["call_metadata"]["canonical_processing_input"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    third_bundle = json.dumps(
        third["call_metadata"]["canonical_processing_input"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    assert first_bundle == second_bundle == third_bundle
    assert first["call_metadata"]["processing_input_sha256"] == second["call_metadata"]["processing_input_sha256"]
    assert second["call_metadata"]["processing_input_sha256"] == third["call_metadata"]["processing_input_sha256"]
    assert first["call_metadata"]["processing_call_id"] == second["call_metadata"]["processing_call_id"]
    assert second["call_metadata"]["processing_call_id"] == third["call_metadata"]["processing_call_id"]
