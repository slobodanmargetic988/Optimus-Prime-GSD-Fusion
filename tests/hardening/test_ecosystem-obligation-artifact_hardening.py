import json
from copy import deepcopy
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
ACCEPTANCE_PATH = REPO_ROOT / "reports" / "optimus-prime" / "planning" / "evidence" / "TASK-211" / "ACCEPTANCE_REQ-058.json"
TASK_EVIDENCE_PATH = REPO_ROOT / "reports" / "optimus-prime" / "planning" / "evidence" / "TASK-211" / "TASK_EVIDENCE.json"


def _build_payload() -> dict:
    return {
        "analysis_type": "ecosystem_obligation_artifact",
        "now_utc": "2026-03-16T11:30:00Z",
        "target_project": {
            "project_id": "optimus-prime-gsd-fusion",
            "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion",
        },
        "ecosystem_obligations": [
            {
                "obligation_id": "obl.consume-runtime-heartbeats",
                "peer_project_id": "earth-core-runtime",
                "responsibility": "consume",
                "artifact": "runtime_lease_heartbeat_events",
                "obligation_summary": "Consume runtime heartbeat events for stale-worker detection.",
                "dependency_prerequisites": [
                    "dep.runtime-heartbeat-contract",
                    "dep.state-artifact-cadence",
                ],
                "evidence_refs": [
                    "earth-sweep/ref-runtime",
                    "strategy/current/samples/REQ-007_ground-graph-snapshot-ingestion.sample.json#lineage_index",
                ],
            }
        ],
        "broad_sweep_context": {
            "earth_sweep_evidence_refs": [
                "earth-sweep/ref-health",
                "earth-sweep/ref-runtime",
            ],
            "projects_considered": [
                "earth-analytics-hub",
                "earth-core-runtime",
                "earth-orchestrator",
            ],
            "cross_project_obligations": [
                {
                    "obligation_id": "obl.produce-strategy-health-summary",
                    "peer_project_id": "earth-analytics-hub",
                    "responsibility": "produce",
                    "artifact": "strategy_health_summary_v1",
                    "obligation_summary": "Produce strategy cycle health summary packets for analytics baselines.",
                    "dependency_prerequisites": [
                        "dep.analytics-schema-v2",
                        "dep.runtime-heartbeat-contract",
                    ],
                    "evidence_refs": [
                        "earth-sweep/ref-health",
                    ],
                },
                {
                    "obligation_id": "obl.produce-unverified-obligation",
                    "peer_project_id": "earth-orchestrator",
                    "responsibility": "produce",
                    "artifact": "handoff_bridge_v2",
                    "obligation_summary": "Candidate obligation without Earth-sweep evidence must remain an open risk.",
                    "dependency_prerequisites": [
                        "dep.handoff-contract-v2",
                    ],
                    "evidence_refs": [],
                },
            ],
            "unresolved_ideas": [
                {
                    "risk_id": "risk.idea-bridge-contract",
                    "summary": "Evaluate additional bridge-contract rollout after sweep evidence is refreshed.",
                    "reason_code": "needs_followup_validation",
                    "required_evidence_refs": [
                        "earth-sweep/ref-bridge-contract",
                    ],
                }
            ],
        },
    }


def test_req_058_artifact_regeneration_has_no_semantic_drift_on_no_change_rerun() -> None:
    first = module.build_req_058_ecosystem_obligation_artifact(_build_payload())
    second = module.build_req_058_ecosystem_obligation_artifact(deepcopy(_build_payload()))

    assert module.validate_req_058_ecosystem_obligation_artifact(first) == []
    assert module.validate_req_058_ecosystem_obligation_artifact(second) == []
    assert json.dumps(first, sort_keys=True, separators=(",", ":"), ensure_ascii=False) == json.dumps(
        second,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    assert [
        row["reason_code"] for row in first["processing_behavior"]["recommendation"]["open_risks"]
    ] == [
        row["reason_code"] for row in second["processing_behavior"]["recommendation"]["open_risks"]
    ]


def test_req_058_planner_hook_receives_complete_recommendation_mapping_set() -> None:
    payload = module.build_req_058_ecosystem_obligation_artifact(_build_payload())
    recommendation = payload["processing_behavior"]["recommendation"]
    expected_fields = {
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "context_project_ids",
        "cross_project_context",
        "approved_ecosystem_obligations",
        "open_risks",
    }

    assert set(recommendation.keys()) == expected_fields
    assert recommendation["decision"] == "proceed-with-open-risks"
    assert recommendation["context_project_ids"] == [
        "earth-analytics-hub",
        "earth-core-runtime",
        "earth-orchestrator",
    ]
    assert recommendation["cross_project_context"] == {
        "projects_considered": [
            "earth-analytics-hub",
            "earth-core-runtime",
            "earth-orchestrator",
        ],
        "earth_sweep_evidence_refs": [
            "earth-sweep/ref-health",
            "earth-sweep/ref-runtime",
        ],
        "cross_project_obligation_ids": [
            "obl.produce-strategy-health-summary",
            "obl.produce-unverified-obligation",
        ],
        "unresolved_idea_ids": [
            "risk.idea-bridge-contract",
        ],
    }
    assert recommendation["approved_ecosystem_obligations"] == [
        {
            "obligation_id": row["obligation_id"],
            "peer_project_id": row["peer_project_id"],
            "responsibility": row["responsibility"],
            "artifact": row["artifact"],
            "evidence_refs": row["evidence_refs"],
        }
        for row in payload["ecosystem_obligation_artifact"]["ecosystem_obligations"]
    ]
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk.idea-bridge-contract",
            "summary": "Evaluate additional bridge-contract rollout after sweep evidence is refreshed.",
            "reason_code": "unresolved_idea",
            "required_evidence_refs": [
                "earth-sweep/ref-bridge-contract",
            ],
        },
        {
            "risk_id": "risk.obl.produce-unverified-obligation",
            "summary": (
                "Cross-project obligation withheld until Earth-sweep evidence refs are attached: "
                "Candidate obligation without Earth-sweep evidence must remain an open risk."
            ),
            "reason_code": "missing_earth_sweep_evidence_refs",
            "required_evidence_refs": [],
        },
    ]


def test_req_058_acceptance_packet_includes_required_evidence_refs_and_open_risk_handling() -> None:
    acceptance = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
    task_evidence = json.loads(TASK_EVIDENCE_PATH.read_text(encoding="utf-8"))

    assert acceptance["req_id"] == "REQ-058"
    assert acceptance["consumability_verdict"] == "accepted_with_open_risks"
    assert len(acceptance["open_risks"]) == 2
    assert acceptance["evidence_refs"] == [
        {
            "type": "test_output",
            "test_path": "tests/contracts/test_ecosystem-obligation-artifact.py",
            "command": "python3 -m pytest tests/contracts/test_ecosystem-obligation-artifact.py -q",
            "output_ref": "reports/optimus-prime/planning/evidence/TASK-211/contract_ecosystem-obligation-artifact.output.txt",
            "observed_output": "pending verification",
        },
        {
            "type": "test_output",
            "test_path": "tests/integration/test_ecosystem-obligation-artifact.py",
            "command": "python3 -m pytest tests/integration/test_ecosystem-obligation-artifact.py -q",
            "output_ref": "reports/optimus-prime/planning/evidence/TASK-211/integration_ecosystem-obligation-artifact.output.txt",
            "observed_output": "pending verification",
        },
        {
            "type": "test_output",
            "test_path": "tests/hardening/test_ecosystem-obligation-artifact_hardening.py",
            "command": "python3 -m pytest tests/hardening/test_ecosystem-obligation-artifact_hardening.py -q",
            "output_ref": "reports/optimus-prime/planning/evidence/TASK-211/hardening_ecosystem-obligation-artifact.output.txt",
            "observed_output": "pending verification",
        },
        {
            "type": "task_evidence",
            "path": "reports/optimus-prime/planning/evidence/TASK-211/TASK_EVIDENCE.json",
            "notes": "TASK-211 edge cases remain free of unresolved blockers after deterministic replay verification.",
        },
    ]

    assert task_evidence["task_id"] == "TASK-211"
    assert task_evidence["requirement_ids"] == ["REQ-058"]
    assert task_evidence["dev"]["artifacts"][-1] == "reports/optimus-prime/planning/evidence/TASK-211/ACCEPTANCE_REQ-058.json"
    assert task_evidence["dev"]["edge_case_blockers"] == [
        {
            "edge_case": "artifact_regeneration_no_semantic_drift_on_no_change_rerun",
            "unresolved_blockers": [],
        },
        {
            "edge_case": "planner_hook_receives_complete_recommendation_mapping_set",
            "unresolved_blockers": [],
        },
        {
            "edge_case": "acceptance_packet_includes_required_evidence_refs_and_open_risk_handling",
            "unresolved_blockers": [],
        },
    ]
