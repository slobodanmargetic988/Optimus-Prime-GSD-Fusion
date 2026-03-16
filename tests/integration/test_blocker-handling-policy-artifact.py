import copy
import json
import subprocess
import sys
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "blocker-handling-policy-artifact.json"
PACKET_PATH = REPO_ROOT / "strategy" / "current" / "strategy_packet.v1.json"
SCHEMA_PATH = REPO_ROOT / "contracts" / "strategy_packet.v1.schema.json"
VALIDATOR_SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_packet_validate.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_057_integration_emits_complete_recommendation_with_evidence_refs() -> None:
    fixture = _read_json(FIXTURE_PATH)

    payload = module.build_req_057_blocker_handling_policy_artifact(fixture["input"])
    assert module.validate_req_057_blocker_handling_policy_artifact(payload) == []

    processing = payload["processing_behavior"]
    usage = processing["cross_project_context_usage"]
    recommendation = processing["recommendation"]

    assert usage == {
        "cross_project_context_provided": True,
        "cross_project_context_used": True,
        "projects_considered": ["ground-control-hub", "runtime-orchestrator"],
        "earth_sweep_evidence_refs_considered": [
            "reports/earth/sweeps/2026-03-15/ground-control-hub.json",
            "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
        ],
        "policy_ids_with_cross_project_context": ["policy.cross-project-rate-limit"],
        "cross_project_obligation_count": 1,
        "open_risk_count": 0,
        "evidence_refs_used": [
            "contracts/req/REQ-057_blocker-handling-policy-artifact.md",
            "reports/earth/sweeps/2026-03-15/ground-control-hub.json",
            "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
            "reports/optimus-prime/planning/evidence/TASK-205/TASK_EVIDENCE.json",
        ],
    }

    assert set(recommendation.keys()) == {
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "recommended_actions",
        "cross_project_obligations",
        "open_risks",
    }
    assert recommendation["decision"] == "proceed"
    assert recommendation["confidence"] == "high"
    assert recommendation["rationale"]
    assert recommendation["evidence_refs"] == usage["evidence_refs_used"]
    assert recommendation["open_risks"] == []

    action_by_policy = {row["policy_id"]: row for row in recommendation["recommended_actions"]}
    assert set(action_by_policy) == {
        "policy.cross-project-rate-limit",
        "policy.validation-contract-mismatch",
    }
    for row in recommendation["recommended_actions"]:
        assert set(row.keys()) == {
            "action_id",
            "policy_id",
            "action_scope",
            "summary",
            "rationale",
            "next_step",
            "evidence_refs",
        }
        assert row["summary"]
        assert row["rationale"]
        assert row["next_step"]
        assert row["evidence_refs"]

    assert recommendation["cross_project_obligations"] == [
        {
            "obligation_id": "obligation-policy.cross-project-rate-limit",
            "policy_id": "policy.cross-project-rate-limit",
            "project_id": "runtime-orchestrator",
            "summary": "Apply policy 'policy.cross-project-rate-limit' for project 'runtime-orchestrator'.",
            "evidence_refs": ["reports/earth/sweeps/2026-03-15/runtime-orchestrator.json"],
        }
    ]


def test_req_057_integration_keeps_cross_project_policy_as_open_risk_without_earth_refs() -> None:
    fixture = _read_json(FIXTURE_PATH)

    payload = module.build_req_057_blocker_handling_policy_artifact(fixture["missing_earth_sweep_evidence_input"])
    assert module.validate_req_057_blocker_handling_policy_artifact(payload) == []

    usage = payload["processing_behavior"]["cross_project_context_usage"]
    recommendation = payload["processing_behavior"]["recommendation"]

    assert usage["cross_project_context_used"] is True
    assert usage["earth_sweep_evidence_refs_considered"] == []
    assert usage["cross_project_obligation_count"] == 0
    assert usage["open_risk_count"] == 1

    assert recommendation["decision"] == "collect-earth-evidence"
    assert recommendation["cross_project_obligations"] == []
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk-policy.cross-project-rate-limit",
            "policy_id": "policy.cross-project-rate-limit",
            "summary": (
                "Cross-project blocker policy 'policy.cross-project-rate-limit' cannot emit obligation "
                "without Earth-sweep evidence refs."
            ),
            "reason_code": "missing_earth_sweep_evidence_refs",
            "required_evidence_refs": ["reports/earth/sweeps/2026-03-15/runtime-orchestrator.json"],
        }
    ]


def test_req_057_strategy_packet_validator_accepts_current_packet() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR_SCRIPT_PATH),
            "--input",
            str(PACKET_PATH),
            "--schema",
            str(SCHEMA_PATH),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0
    assert proc.stderr == ""
    payload = json.loads(proc.stdout)
    assert payload == {
        "ok": True,
        "checked_at_utc": payload["checked_at_utc"],
        "verdict": "pass",
        "planner_consumability": "planner_ready",
        "reason_codes": [],
        "diagnostic_count": 0,
        "summary": "Strategy packet is planner/runtime-consumable.",
        "input_path": str(PACKET_PATH.resolve()),
        "schema_path": str(SCHEMA_PATH.resolve()),
        "gate": {
            "schema_valid": True,
            "req_057_blocker_policy_consumable": True,
        },
        "diagnostics": [],
    }
    assert payload["checked_at_utc"].endswith("Z")


def test_req_057_strategy_packet_validator_rejects_invalid_policy_fixture_with_deterministic_diagnostics(
    tmp_path: Path,
) -> None:
    invalid_packet = copy.deepcopy(_read_json(PACKET_PATH))
    invalid_packet["blocker_handling_policy_artifact"]["policies"][0]["fallback_paths"] = []
    invalid_packet["blocker_handling_policy_artifact"]["policies"][1]["owner_hints"] = [
        "planner-worker",
        "developer-worker",
        "planner-worker",
    ]

    invalid_path = tmp_path / "invalid-strategy_packet.v1.json"
    invalid_path.write_text(json.dumps(invalid_packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR_SCRIPT_PATH),
            "--input",
            str(invalid_path),
            "--schema",
            str(SCHEMA_PATH),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 1
    assert proc.stderr == ""
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["verdict"] == "fail"
    assert payload["planner_consumability"] == "planner_blocked"
    assert payload["reason_codes"] == [
        "req_057_list_duplicate",
        "req_057_list_min_items",
        "req_057_list_unsorted",
    ]
    assert payload["diagnostic_count"] == 3
    assert payload["summary"] == (
        "Strategy packet is not planner/runtime-consumable; 3 blocking diagnostics detected."
    )
    assert payload["gate"] == {
        "schema_valid": True,
        "req_057_blocker_policy_consumable": False,
    }
    assert payload["diagnostics"] == [
        {
            "severity": "error",
            "reason_code": "req_057_list_min_items",
            "field_path": "blocker_handling_policy_artifact.policies[0].fallback_paths",
            "message": (
                "blocker_handling_policy_artifact.policies[0].fallback_paths "
                "must include at least 1 item(s)."
            ),
        },
        {
            "severity": "error",
            "reason_code": "req_057_list_duplicate",
            "field_path": "blocker_handling_policy_artifact.policies[1].owner_hints",
            "message": "blocker_handling_policy_artifact.policies[1].owner_hints must not contain duplicate values.",
        },
        {
            "severity": "error",
            "reason_code": "req_057_list_unsorted",
            "field_path": "blocker_handling_policy_artifact.policies[1].owner_hints",
            "message": "blocker_handling_policy_artifact.policies[1].owner_hints must be sorted in ascending order.",
        },
    ]
