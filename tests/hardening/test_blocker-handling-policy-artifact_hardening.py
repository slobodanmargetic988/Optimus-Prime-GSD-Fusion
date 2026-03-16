import json
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "blocker-handling-policy-artifact.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def test_req_057_hardening_artifact_regeneration_has_no_semantic_drift() -> None:
    fixture = _read_json(FIXTURE_PATH)
    run_one = module.build_req_057_blocker_handling_policy_artifact(fixture["input"])
    run_two = module.build_req_057_blocker_handling_policy_artifact(fixture["input"])

    assert module.validate_req_057_blocker_handling_policy_artifact(run_one) == []
    assert module.validate_req_057_blocker_handling_policy_artifact(run_two) == []
    assert _canonical_json(run_one) == _canonical_json(run_two)


def test_req_057_hardening_planner_hook_receives_complete_recommendation_mapping_set() -> None:
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_057_blocker_handling_policy_artifact(fixture["input"])
    assert module.validate_req_057_blocker_handling_policy_artifact(payload) == []

    policies_by_id = {
        row["policy_id"]: row for row in payload["blocker_handling_policy_artifact"]["policies"]
    }
    recommendation = payload["processing_behavior"]["recommendation"]
    actions_by_policy = {row["policy_id"]: row for row in recommendation["recommended_actions"]}
    obligations_by_policy = {row["policy_id"]: row for row in recommendation["cross_project_obligations"]}
    risks_by_policy = {row["policy_id"]: row for row in recommendation["open_risks"]}

    planner_mapping = {
        policy_id: {
            "policy_row": policies_by_id[policy_id],
            "recommended_action": actions_by_policy[policy_id],
            "cross_project_obligation": obligations_by_policy.get(policy_id),
            "open_risk": risks_by_policy.get(policy_id),
        }
        for policy_id in sorted(policies_by_id)
    }

    assert set(planner_mapping) == set(policies_by_id) == set(actions_by_policy)
    for policy_id, row in planner_mapping.items():
        policy_row = row["policy_row"]
        assert set(policy_row["escalation_trigger"]) == {"trigger_type", "threshold", "window"}
        assert policy_row["owner_hints"]
        assert policy_row["fallback_paths"]
        assert row["recommended_action"]["evidence_refs"] == policy_row["evidence_refs"]
        assert row["recommended_action"]["action_scope"] in {"local", "cross-project"}

        is_cross_project = bool(policy_row.get("project_id"))
        if is_cross_project:
            assert row["cross_project_obligation"] is not None
            assert row["open_risk"] is None
        else:
            assert row["cross_project_obligation"] is None
            assert row["open_risk"] is None


def test_req_057_hardening_acceptance_packet_includes_required_evidence_refs_and_open_risk_handling() -> None:
    fixture = _read_json(FIXTURE_PATH)
    run_one = module.build_req_057_blocker_handling_policy_artifact(
        fixture["missing_earth_sweep_evidence_input"]
    )
    run_two = module.build_req_057_blocker_handling_policy_artifact(
        fixture["missing_earth_sweep_evidence_input"]
    )

    assert module.validate_req_057_blocker_handling_policy_artifact(run_one) == []
    assert module.validate_req_057_blocker_handling_policy_artifact(run_two) == []

    recommendation_one = run_one["processing_behavior"]["recommendation"]
    usage_one = run_one["processing_behavior"]["cross_project_context_usage"]

    assert recommendation_one["decision"] == "collect-earth-evidence"
    assert usage_one["cross_project_obligation_count"] == 0
    assert usage_one["open_risk_count"] == 1

    open_risks_one = recommendation_one["open_risks"]
    assert len(open_risks_one) == 1
    risk_one = open_risks_one[0]
    assert risk_one["reason_code"] == "missing_earth_sweep_evidence_refs"
    assert risk_one["required_evidence_refs"] == [
        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json"
    ]
    assert set(risk_one["required_evidence_refs"]).issubset(set(recommendation_one["evidence_refs"]))

    acceptance_packet_one = {
        "decision": recommendation_one["decision"],
        "evidence_refs": recommendation_one["evidence_refs"],
        "open_risks": recommendation_one["open_risks"],
    }
    acceptance_packet_two = {
        "decision": run_two["processing_behavior"]["recommendation"]["decision"],
        "evidence_refs": run_two["processing_behavior"]["recommendation"]["evidence_refs"],
        "open_risks": run_two["processing_behavior"]["recommendation"]["open_risks"],
    }
    assert _canonical_json(acceptance_packet_one) == _canonical_json(acceptance_packet_two)
