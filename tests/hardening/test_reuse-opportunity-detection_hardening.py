import json
from pathlib import Path

from scripts.strategy_context_sweep import (
    detect_reuse_opportunities,
    serialize_reuse_opportunity_context_bundle,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "reuse-opportunity-detection.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_016_stale_earth_sweep_source_artifact_emits_deterministic_reason_code() -> None:
    payload = _read_json(FIXTURE_PATH)
    payload["earth_sweep_source_artifacts"] = [
        {
            "artifact_ref": "reports/earth/sweeps/2026-03-15/earth-core-runtime.json",
            "status": "stale",
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-15/earth-core-runtime.audit.json",
            ],
        }
    ]

    output = detect_reuse_opportunities(payload, evaluated_at="2026-03-15T01:30:00Z")

    stale_risks = [row for row in output["open_risks"] if row["reason_code"] == "stale_earth_sweep_source_artifact"]
    assert len(stale_risks) == 1
    assert stale_risks[0]["risk_id"].startswith("risk-earth-source-")
    assert stale_risks[0]["required_evidence_refs"] == [
        "reports/earth/sweeps/2026-03-15/earth-core-runtime.audit.json",
        "reports/earth/sweeps/2026-03-15/earth-core-runtime.json",
    ]
    assert output["decision"] == "partial_reuse_recommended_with_open_risks"


def test_req_016_missing_mission_scope_and_peer_project_docs_emit_explicit_reason_codes() -> None:
    payload = _read_json(FIXTURE_PATH)
    payload["required_context_documents"] = [
        {
            "doc_kind": "mission",
            "doc_ref": "mission.md",
            "status": "missing",
            "evidence_refs": [
                "reports/optimus-prime/planning/evidence/TASK-051/TASK_EVIDENCE.json",
            ],
        },
        {
            "doc_kind": "scope",
            "doc_ref": "scope.md",
            "status": "missing",
            "evidence_refs": [
                "reports/optimus-prime/planning/evidence/TASK-051/TASK_EVIDENCE.json",
            ],
        },
        {
            "doc_kind": "peer-project",
            "project_id": "earth-core-runtime",
            "doc_ref": "docs/earth-core-runtime/overview.md",
            "status": "missing",
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-15/earth-core-runtime.json",
            ],
        },
    ]

    output = detect_reuse_opportunities(payload, evaluated_at="2026-03-15T01:30:00Z")

    assert sorted(row["reason_code"] for row in output["open_risks"]) == [
        "missing_mission_doc",
        "missing_peer_project_doc",
        "missing_scope_doc",
    ]
    assert output["decision"] == "partial_reuse_recommended_with_open_risks"
    for row in output["open_risks"]:
        assert row["required_evidence_refs"]


def test_req_016_context_bundle_serialization_is_replay_stable_across_repeated_runs() -> None:
    first = {
        "active_project_id": "optimus-prime-gsd-fusion",
        "required_capabilities": [
            {
                "capability_id": "reuse-signal-ranking",
                "intent": "Reuse ranking heuristics for cross-project recommendation ordering.",
                "required_interfaces": [
                    "risk-weight-v2",
                    "risk-weight-v2",
                ],
            },
            {
                "capability_id": "ground-graph-snapshot-ingestion",
                "intent": "Reuse stable ground-graph ingestion instead of rebuilding parsing and lineage normalization.",
                "required_interfaces": [
                    "lineage-anchor-index",
                    "json-canonical-v1",
                ],
            },
        ],
        "existing_functionality": [
            {
                "source_project_id": "shared-observability",
                "capability_id": "reuse-signal-ranking",
                "functionality": "Ranks reuse opportunities by historical incident density and latency budgets.",
                "provided_interfaces": [
                    "csv-export",
                    "risk-weight-v1",
                ],
                "adoption_path": [
                    "Load ranking profile from shared-observability runbook export.",
                    "Map ranking output into strategy recommendation order.",
                ],
                "compatibility_constraints": [
                    "Ranking engine currently emits risk-weight-v1 only.",
                    "Upgrade adapter to risk-weight-v2 before production usage.",
                ],
                "evidence_refs": [
                    "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
                ],
            },
            {
                "source_project_id": "earth-core-runtime",
                "capability_id": "ground-graph-snapshot-ingestion",
                "functionality": "Canonical lineage ingestion and checksum generation for ground graph snapshots.",
                "provided_interfaces": [
                    "cli",
                    "lineage-anchor-index",
                    "json-canonical-v1",
                ],
                "adoption_path": [
                    "Import scripts/strategy_context_sweep.py::ingest_ground_graph_snapshot into strategy orchestration.",
                    "Pass source snapshot path and ingested_at timestamp from active run context.",
                    "Persist canonical output as REQ-016 evidence before planning packets are emitted.",
                ],
                "compatibility_constraints": [
                    "Input snapshot must include project_id, era_id, plan_id, phase_id, run_id, linked_project_id, relationship.",
                    "Ingestion output must preserve sorted unique lineage indexes for deterministic diffs.",
                ],
                "evidence_refs": [
                    "strategy/current/samples/REQ-007_ground-graph-snapshot-ingestion.sample.json",
                    "contracts/req/REQ-007_ground-graph-snapshot-ingestion.md",
                ],
            },
            {
                "source_project_id": "earth-core-runtime",
                "capability_id": "ground-graph-snapshot-ingestion",
                "functionality": "Canonical lineage ingestion and checksum generation for ground graph snapshots.",
                "provided_interfaces": [
                    "json-canonical-v1",
                    "cli",
                    "lineage-anchor-index",
                ],
                "adoption_path": [
                    "Import scripts/strategy_context_sweep.py::ingest_ground_graph_snapshot into strategy orchestration.",
                    "Pass source snapshot path and ingested_at timestamp from active run context.",
                    "Persist canonical output as REQ-016 evidence before planning packets are emitted.",
                ],
                "compatibility_constraints": [
                    "Input snapshot must include project_id, era_id, plan_id, phase_id, run_id, linked_project_id, relationship.",
                    "Ingestion output must preserve sorted unique lineage indexes for deterministic diffs.",
                ],
                "evidence_refs": [
                    "contracts/req/REQ-007_ground-graph-snapshot-ingestion.md",
                    "strategy/current/samples/REQ-007_ground-graph-snapshot-ingestion.sample.json",
                ],
            },
        ],
        "earth_sweep_source_artifacts": [
            {
                "artifact_ref": "reports/earth/sweeps/2026-03-15/earth-core-runtime.json",
                "status": "stale",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/earth-core-runtime.audit.json",
                ],
            },
            {
                "artifact_ref": "reports/earth/sweeps/2026-03-15/shared-observability.json",
                "status": "fresh",
                "evidence_refs": [],
            },
        ],
        "required_context_documents": [
            {
                "doc_kind": "peer-project",
                "project_id": "earth-core-runtime",
                "doc_ref": "docs/earth-core-runtime/overview.md",
                "status": "missing",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/earth-core-runtime.json",
                ],
            },
            {
                "doc_kind": "mission",
                "doc_ref": "mission.md",
                "status": "present",
                "evidence_refs": [],
            },
        ],
    }
    second = {
        "active_project_id": "optimus-prime-gsd-fusion",
        "required_capabilities": [
            {
                "capability_id": "ground-graph-snapshot-ingestion",
                "intent": "Reuse stable ground-graph ingestion instead of rebuilding parsing and lineage normalization.",
                "required_interfaces": [
                    "json-canonical-v1",
                    "lineage-anchor-index",
                ],
            },
            {
                "capability_id": "reuse-signal-ranking",
                "intent": "Reuse ranking heuristics for cross-project recommendation ordering.",
                "required_interfaces": [
                    "risk-weight-v2",
                ],
            },
        ],
        "existing_functionality": [
            {
                "source_project_id": "earth-core-runtime",
                "capability_id": "ground-graph-snapshot-ingestion",
                "functionality": "Canonical lineage ingestion and checksum generation for ground graph snapshots.",
                "provided_interfaces": [
                    "lineage-anchor-index",
                    "json-canonical-v1",
                    "cli",
                ],
                "adoption_path": [
                    "Import scripts/strategy_context_sweep.py::ingest_ground_graph_snapshot into strategy orchestration.",
                    "Pass source snapshot path and ingested_at timestamp from active run context.",
                    "Persist canonical output as REQ-016 evidence before planning packets are emitted.",
                ],
                "compatibility_constraints": [
                    "Input snapshot must include project_id, era_id, plan_id, phase_id, run_id, linked_project_id, relationship.",
                    "Ingestion output must preserve sorted unique lineage indexes for deterministic diffs.",
                ],
                "evidence_refs": [
                    "contracts/req/REQ-007_ground-graph-snapshot-ingestion.md",
                    "strategy/current/samples/REQ-007_ground-graph-snapshot-ingestion.sample.json",
                ],
            },
            {
                "source_project_id": "shared-observability",
                "capability_id": "reuse-signal-ranking",
                "functionality": "Ranks reuse opportunities by historical incident density and latency budgets.",
                "provided_interfaces": [
                    "risk-weight-v1",
                    "csv-export",
                ],
                "adoption_path": [
                    "Load ranking profile from shared-observability runbook export.",
                    "Map ranking output into strategy recommendation order.",
                ],
                "compatibility_constraints": [
                    "Ranking engine currently emits risk-weight-v1 only.",
                    "Upgrade adapter to risk-weight-v2 before production usage.",
                ],
                "evidence_refs": [
                    "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
                ],
            },
        ],
        "earth_sweep_source_artifacts": [
            {
                "artifact_ref": "reports/earth/sweeps/2026-03-15/shared-observability.json",
                "status": "fresh",
                "evidence_refs": [],
            },
            {
                "artifact_ref": "reports/earth/sweeps/2026-03-15/earth-core-runtime.json",
                "status": "stale",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/earth-core-runtime.audit.json",
                ],
            },
        ],
        "required_context_documents": [
            {
                "doc_kind": "mission",
                "doc_ref": "mission.md",
                "status": "present",
                "evidence_refs": [],
            },
            {
                "doc_kind": "peer-project",
                "project_id": "earth-core-runtime",
                "doc_ref": "docs/earth-core-runtime/overview.md",
                "status": "missing",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/earth-core-runtime.json",
                ],
            },
        ],
    }

    first_bundle = serialize_reuse_opportunity_context_bundle(first)
    second_bundle = serialize_reuse_opportunity_context_bundle(second)

    assert first_bundle["serialization_format"] == "json-canonical-v1"
    assert first_bundle["serialized_payload"] == second_bundle["serialized_payload"]
    assert first_bundle["checksum_sha256"] == second_bundle["checksum_sha256"]
