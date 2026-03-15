from pathlib import Path

from scripts.strategy_context_sweep import (
    detect_integration_opportunities,
    load_ground_graph_snapshot,
    serialize_integration_opportunity_context_bundle,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "ground-graph-snapshot-ingestion.json"


def _base_broad_context() -> dict:
    return {
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
                ],
            }
        ],
    }


def test_req_015_hardening_detects_stale_source_artifact_during_earth_sweep() -> None:
    snapshot = load_ground_graph_snapshot(SNAPSHOT_FIXTURE_PATH)
    broad_context = _base_broad_context()
    broad_context["earth_sweep_started_at"] = "2026-03-14T22:30:00Z"
    broad_context["source_artifact_max_age_seconds"] = 1200

    output = detect_integration_opportunities(
        snapshot,
        broad_sweep_context=broad_context,
        source_path="examples/fixtures/ground-graph-snapshot-ingestion.json",
        evaluated_at="2026-03-15T02:30:00Z",
    )

    stale_rows = [
        row
        for row in output["recommendation"]["open_risks"]
        if row.get("reason_code") == "source_artifact_stale_during_earth_sweep"
    ]
    assert len(stale_rows) == 1

    stale = stale_rows[0]
    assert stale["reason"] == "source_artifact_stale_during_earth_sweep"
    assert stale["source_age_seconds"] == 3600
    assert stale["max_source_age_seconds"] == 1200
    assert stale["evidence_refs"] == [
        "examples/fixtures/ground-graph-snapshot-ingestion.json",
        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
        "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
    ]


def test_req_015_hardening_reports_reason_codes_for_missing_docs() -> None:
    snapshot = load_ground_graph_snapshot(SNAPSHOT_FIXTURE_PATH)
    broad_context = _base_broad_context()
    broad_context["active_project_docs"] = {
        "mission": "",
        "scope": "projects/optimus-prime-gsd-fusion/scope.md",
    }
    broad_context["peer_project_docs"] = {
        "earth-core-runtime": "projects/earth-core-runtime/mission.md",
    }

    output = detect_integration_opportunities(
        snapshot,
        broad_sweep_context=broad_context,
        source_path="examples/fixtures/ground-graph-snapshot-ingestion.json",
        evaluated_at="2026-03-15T02:40:00Z",
    )

    reason_rows = [
        row
        for row in output["recommendation"]["open_risks"]
        if row.get("reason_code")
        in {
            "active_project_missing_mission_or_scope_doc",
            "linked_project_missing_peer_doc",
        }
    ]
    assert len(reason_rows) == 2

    active_docs_row = next(
        row for row in reason_rows if row["reason_code"] == "active_project_missing_mission_or_scope_doc"
    )
    assert active_docs_row["missing_docs"] == ["mission"]
    assert active_docs_row["evidence_refs"] == [
        "examples/fixtures/ground-graph-snapshot-ingestion.json",
        "projects/optimus-prime-gsd-fusion/scope.md",
        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
        "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
    ]

    peer_docs_row = next(row for row in reason_rows if row["reason_code"] == "linked_project_missing_peer_doc")
    assert peer_docs_row["linked_project_id"] == "shared-observability"
    assert peer_docs_row["evidence_refs"] == [
        "examples/fixtures/ground-graph-snapshot-ingestion.json",
        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
        "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
    ]


def test_req_015_hardening_context_bundle_serialization_replay_is_stable() -> None:
    snapshot = load_ground_graph_snapshot(SNAPSHOT_FIXTURE_PATH)
    broad_context = _base_broad_context()
    broad_context["earth_sweep_started_at"] = "2026-03-14T22:30:00Z"
    broad_context["source_artifact_max_age_seconds"] = 1200
    broad_context["active_project_docs"] = {
        "mission": "projects/optimus-prime-gsd-fusion/mission.md",
        "scope": "projects/optimus-prime-gsd-fusion/scope.md",
    }
    broad_context["peer_project_docs"] = {
        "earth-core-runtime": "projects/earth-core-runtime/mission.md",
        "shared-observability": "projects/shared-observability/mission.md",
    }

    first = detect_integration_opportunities(
        snapshot,
        broad_sweep_context=broad_context,
        source_path="examples/fixtures/ground-graph-snapshot-ingestion.json",
        evaluated_at="2026-03-15T02:50:00Z",
    )
    second = detect_integration_opportunities(
        snapshot,
        broad_sweep_context=broad_context,
        source_path="examples/fixtures/ground-graph-snapshot-ingestion.json",
        evaluated_at="2026-03-15T02:50:00Z",
    )

    first_bundle = serialize_integration_opportunity_context_bundle(first)
    second_bundle = serialize_integration_opportunity_context_bundle(second)

    assert first_bundle == second_bundle
    assert first_bundle["checksum_sha256"] == second_bundle["checksum_sha256"]
    assert first_bundle["serialized_payload"] == second_bundle["serialized_payload"]

