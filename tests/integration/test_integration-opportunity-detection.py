from pathlib import Path

from scripts.strategy_context_sweep import detect_integration_opportunities, load_ground_graph_snapshot


REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "ground-graph-snapshot-ingestion.json"


def test_req_015_integration_opportunity_detection_reconciles_evidence_and_defers_out_of_scope_refs() -> None:
    snapshot = load_ground_graph_snapshot(SNAPSHOT_FIXTURE_PATH)
    broad_context = {
        "active_project_id": "optimus-prime-gsd-fusion",
        "earth_sweep_evidence_refs": [
            "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
            "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
        ],
        "integration_opportunity_candidates": [
            {
                "linked_project_id": "earth-core-runtime",
                "action": "Align canary rollout checkpoint with run-131 stabilization outputs.",
                "interaction_contract": {
                    "contract_ref": "contracts/req/REQ-007_ground-graph-snapshot-ingestion.md",
                    "expected_interactions": ["json-canonical-v1"],
                },
                "dependency_side_effect_notes": "May require coordination with stabilization run timelines.",
                "evidence_refs": [
                    "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
                    "reports/optimus-prime/planning/evidence/TASK-022/ACCEPTANCE_REQ-007.json",
                ],
            }
        ],
    }

    output = detect_integration_opportunities(
        snapshot,
        broad_sweep_context=broad_context,
        source_path="examples/fixtures/ground-graph-snapshot-ingestion.json",
        evaluated_at="2026-03-15T02:20:00Z",
    )

    assert output["evidence_refs"]["earth_sweep"] == [
        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
        "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
    ]
    assert output["evidence_refs"]["recommendation"] == [
        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
    ]

    recommendation = output["recommendation"]
    assert recommendation["decision"] == "ready_for_planning"
    assert recommendation["open_risks"] == []

    opportunities = recommendation["integration_opportunities"]
    assert len(opportunities) == 1
    opportunity = opportunities[0]
    assert opportunity["evidence_refs"] == [
        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
    ]
    assert opportunity["out_of_scope_evidence_refs"] == [
        "reports/optimus-prime/planning/evidence/TASK-022/ACCEPTANCE_REQ-007.json",
    ]

    deferred = recommendation["deferred_opportunities"]
    assert deferred == [
        {
            "linked_project_id": "earth-core-runtime",
            "action": "Align canary rollout checkpoint with run-131 stabilization outputs.",
            "reason": "candidate_includes_non_earth_evidence_refs",
            "reason_code": "candidate_includes_non_earth_evidence_refs",
            "out_of_scope_evidence_refs": [
                "reports/optimus-prime/planning/evidence/TASK-022/ACCEPTANCE_REQ-007.json",
            ],
        }
    ]

