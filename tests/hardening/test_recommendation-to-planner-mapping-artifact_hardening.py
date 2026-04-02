import copy
import json
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "recommendation-to-planner-mapping-artifact.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _payload_with_broad_context() -> dict:
    payload = copy.deepcopy(_read_json(FIXTURE_PATH))
    payload["broad_sweep_context"] = {
        "projects_considered": [
            "earth-core-runtime",
            "earth-shared-observability",
            "earth-ops-pipeline",
        ],
        "earth_sweep_evidence_refs": [
            "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
            "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
            "reports/earth/sweeps/earth-ops-pipeline/planner-packet-gaps-2026-03-15.json",
        ],
        "cross_project_obligations": [
            {
                "obligation_id": "obligation-runtime-canary-alignment",
                "summary": "Coordinate runtime canary windows before widening rollout.",
                "recommendation_ids": ["rec.align-earth-runtime-canary"],
                "project_ids": ["earth-core-runtime"],
                "earth_sweep_evidence_refs": [
                    "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
                ],
            },
            {
                "obligation_id": "obligation-missing-earth-evidence",
                "summary": "Link reuse contract updates to cross-project ownership evidence.",
                "recommendation_ids": ["rec.review-reuse-contracts"],
                "project_ids": ["earth-shared-observability"],
                "earth_sweep_evidence_refs": [],
            },
            {
                "obligation_id": "obligation-unknown-recommendation",
                "summary": "Sync planner packet queue with a recommendation not present in mapping rows.",
                "recommendation_ids": ["rec.unknown"],
                "project_ids": ["earth-ops-pipeline"],
                "earth_sweep_evidence_refs": [
                    "reports/earth/sweeps/earth-ops-pipeline/planner-packet-gaps-2026-03-15.json",
                ],
            },
        ],
        "unresolved_ideas": [
            {
                "idea_id": "idea.reuse-ownership-followup",
                "summary": "Validate shared ownership handoff before adding new cross-project packets.",
                "recommendation_ids": ["rec.review-reuse-contracts"],
                "project_ids": ["earth-shared-observability"],
                "required_earth_sweep_evidence_refs": [
                    "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
                ],
            },
            {
                "idea_id": "idea.unscoped-evidence-gap",
                "summary": "Capture missing Earth sweep references for planner intake risk review.",
                "recommendation_ids": [],
                "project_ids": ["earth-ops-pipeline"],
                "required_earth_sweep_evidence_refs": [],
            },
        ],
    }
    return payload


def _planner_hook_payload(output: dict) -> dict:
    artifact = output["recommendation_to_planner_mapping_artifact"]
    return {
        "recommendation_ids": list(artifact["recommendation_ids"]),
        "planner_task_intent_handles": list(artifact["planner_task_intent_handles"]),
        "recommendation_to_task_intent_mappings": [
            {
                "mapping_id": row["mapping_id"],
                "recommendation_id": row["recommendation_id"],
                "planner_task_intent_handle": row["planner_task_intent_handle"],
                "traceability_refs": list(row["traceability_refs"]),
            }
            for row in artifact["recommendation_to_task_intent_mappings"]
        ],
    }


def _acceptance_packet(output: dict) -> dict:
    recommendation = output["processing_behavior"]["recommendation"]
    return {
        "req_id": "REQ-054",
        "summary": recommendation["rationale"],
        "evidence_refs": list(recommendation["evidence_refs"]),
        "consumability_verdict": recommendation["decision"],
        "open_risks": [
            {
                "source_id": row["source_id"],
                "reason_code": row["reason_code"],
                "required_evidence_refs": list(row["required_evidence_refs"]),
                "linked_recommendation_ids": list(row["linked_recommendation_ids"]),
                "linked_planner_task_intent_handles": list(row["linked_planner_task_intent_handles"]),
            }
            for row in recommendation["open_risks"]
        ],
    }


def test_req_054_hardening_no_change_rerun_regenerates_without_semantic_drift() -> None:
    payload = _payload_with_broad_context()

    run_one = module.build_req_054_recommendation_to_planner_mapping_artifact(copy.deepcopy(payload))
    run_two = module.build_req_054_recommendation_to_planner_mapping_artifact(copy.deepcopy(payload))

    assert run_one == run_two
    assert json.dumps(run_one, sort_keys=True, separators=(",", ":")) == json.dumps(
        run_two,
        sort_keys=True,
        separators=(",", ":"),
    )
    assert [row["mapping_id"] for row in run_one["recommendation_to_planner_mapping_artifact"]["recommendation_to_task_intent_mappings"]] == [
        row["mapping_id"] for row in run_two["recommendation_to_planner_mapping_artifact"]["recommendation_to_task_intent_mappings"]
    ]
    assert [
        row["reason_code"] for row in run_one["processing_behavior"]["recommendation"]["open_risks"]
    ] == [
        row["reason_code"] for row in run_two["processing_behavior"]["recommendation"]["open_risks"]
    ]


def test_req_054_hardening_planner_hook_receives_complete_recommendation_mapping_set() -> None:
    output = module.build_req_054_recommendation_to_planner_mapping_artifact(_payload_with_broad_context())
    planner_hook = _planner_hook_payload(output)
    artifact = output["recommendation_to_planner_mapping_artifact"]

    assert planner_hook["recommendation_ids"] == artifact["recommendation_ids"]
    assert planner_hook["planner_task_intent_handles"] == artifact["planner_task_intent_handles"]
    assert len(planner_hook["recommendation_to_task_intent_mappings"]) == output["totals"]["mapping_rows"]
    assert {
        (row["recommendation_id"], row["planner_task_intent_handle"])
        for row in planner_hook["recommendation_to_task_intent_mappings"]
    } == {
        (row["recommendation_id"], row["planner_task_intent_handle"])
        for row in artifact["recommendation_to_task_intent_mappings"]
    }
    assert [
        row["planner_task_intent_handle"]
        for row in planner_hook["recommendation_to_task_intent_mappings"]
        if row["recommendation_id"] == "rec.review-reuse-contracts"
    ] == [
        "intent.reuse-contract-review",
        "intent.cross-project-reuse-ownership-clarification",
    ]
    for row in planner_hook["recommendation_to_task_intent_mappings"]:
        assert row["traceability_refs"]


def test_req_054_hardening_acceptance_packet_includes_required_evidence_refs_and_open_risk_handling() -> None:
    output = module.build_req_054_recommendation_to_planner_mapping_artifact(_payload_with_broad_context())
    acceptance_packet = _acceptance_packet(output)
    evidence_refs = set(acceptance_packet["evidence_refs"])

    assert acceptance_packet["req_id"] == "REQ-054"
    assert acceptance_packet["consumability_verdict"] == "planning_with_open_risks"
    assert acceptance_packet["summary"] == "mappings=4 obligations=3 approved=1 open_risks=4"
    assert {row["source_id"]: row["reason_code"] for row in acceptance_packet["open_risks"]} == {
        "idea.reuse-ownership-followup": "unresolved_idea_open_risk",
        "idea.unscoped-evidence-gap": "unresolved_idea_open_risk",
        "obligation-missing-earth-evidence": "missing_earth_sweep_evidence_refs",
        "obligation-unknown-recommendation": "unknown_recommendation_ids",
    }
    for row in acceptance_packet["open_risks"]:
        assert row["required_evidence_refs"]
        assert set(row["required_evidence_refs"]).issubset(evidence_refs)
    assert "missing:earth-sweep-evidence-ref" in evidence_refs
    assert "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json" in evidence_refs
    assert "reports/runtime/telemetry/freshness-gap-2026-03-15.json" in evidence_refs
