from scripts.strategy_context_sweep import (
    extract_strategic_debt_signals,
    serialize_req_018_context_bundle,
)


def _base_payload() -> dict:
    return {
        "analysis_type": "strategic_debt_signal_extraction",
        "evaluated_at": "2026-03-15T03:20:00Z",
        "active_project_id": "optimus-prime-gsd-fusion",
        "thresholds": {
            "min_recurrence_count": 3,
            "min_likely_blast_radius": 2,
        },
        "max_signals": 1,
        "broad_sweep_context": {
            "projects_considered": [
                "optimus-prime-gsd-fusion",
                "runtime-orchestrator",
            ],
            "evidence_refs_by_project": {
                "optimus-prime-gsd-fusion": [
                    "reports/earth/sweeps/2026-03-15/optimus-prime-gsd-fusion.json",
                ],
                "runtime-orchestrator": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
            },
        },
        "debt_observations": [
            {
                "debt_id": "DEBT-900",
                "summary": "Retries mask flaky strategic debt signals across projects.",
                "category": "runtime",
                "recurrence_count": 5,
                "likely_blast_radius": 3,
                "evidence_refs": [
                    "reports/runtime/retry-policy-diff-2026-03-14.json",
                ],
            }
        ],
    }


def test_req_018_hardening_detects_stale_source_artifact_during_earth_sweep() -> None:
    payload = _base_payload()
    payload["broad_sweep_context"]["earth_sweep_source_artifacts"] = [
        {
            "artifact_ref": "artifact.dispatch-cycle-canary-20260315",
            "status": "stale",
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
            ],
        }
    ]

    out = extract_strategic_debt_signals(payload)
    stale_rows = [
        row
        for row in out["recommendation"]["open_risks"]
        if row.get("reason_code") == "earth_sweep_stale_source_artifact"
    ]
    assert len(stale_rows) == 1

    stale = stale_rows[0]
    assert stale["artifact_ref"] == "artifact.dispatch-cycle-canary-20260315"
    assert stale["evidence_refs"] == [
        "artifact.dispatch-cycle-canary-20260315",
        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
    ]


def test_req_018_hardening_reports_reason_codes_for_missing_docs() -> None:
    payload = _base_payload()
    payload["broad_sweep_context"]["required_context_documents"] = [
        {
            "doc_kind": "mission",
            "doc_ref": "projects/optimus-prime-gsd-fusion/mission.md",
            "status": "missing",
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-15/optimus-prime-gsd-fusion.json",
            ],
        },
        {
            "doc_kind": "scope",
            "doc_ref": "projects/optimus-prime-gsd-fusion/scope.md",
            "status": "missing",
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-15/optimus-prime-gsd-fusion.json",
            ],
        },
        {
            "doc_kind": "peer-project",
            "doc_ref": "projects/runtime-orchestrator/mission.md",
            "project_id": "runtime-orchestrator",
            "status": "missing",
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
            ],
        },
    ]

    out = extract_strategic_debt_signals(payload)
    reason_rows = [
        row
        for row in out["recommendation"]["open_risks"]
        if row.get("reason_code") in {"context_doc_missing", "peer_project_doc_missing"}
    ]
    assert len(reason_rows) == 3

    mission_row = next(row for row in reason_rows if row.get("doc_kind") == "mission")
    assert mission_row["reason_code"] == "context_doc_missing"
    assert mission_row["evidence_refs"] == [
        "projects/optimus-prime-gsd-fusion/mission.md",
        "reports/earth/sweeps/2026-03-15/optimus-prime-gsd-fusion.json",
    ]

    scope_row = next(row for row in reason_rows if row.get("doc_kind") == "scope")
    assert scope_row["reason_code"] == "context_doc_missing"
    assert scope_row["evidence_refs"] == [
        "projects/optimus-prime-gsd-fusion/scope.md",
        "reports/earth/sweeps/2026-03-15/optimus-prime-gsd-fusion.json",
    ]

    peer_row = next(row for row in reason_rows if row.get("doc_kind") == "peer-project")
    assert peer_row["reason_code"] == "peer_project_doc_missing"
    assert peer_row["project_id"] == "runtime-orchestrator"
    assert peer_row["evidence_refs"] == [
        "projects/runtime-orchestrator/mission.md",
        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
    ]


def test_req_018_hardening_context_bundle_serialization_replay_is_stable() -> None:
    payload_a = _base_payload()
    payload_b = _base_payload()
    payload_b["broad_sweep_context"] = {
        "projects_considered": [
            "runtime-orchestrator",
            "optimus-prime-gsd-fusion",
        ],
        "evidence_refs_by_project": {
            "runtime-orchestrator": [
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
            ],
            "optimus-prime-gsd-fusion": [
                "reports/earth/sweeps/2026-03-15/optimus-prime-gsd-fusion.json",
            ],
        },
    }
    payload_b["debt_observations"] = [
        {
            "debt_id": "DEBT-900",
            "summary": "Retries mask flaky strategic debt signals across projects.",
            "category": "runtime",
            "recurrence_count": 5,
            "likely_blast_radius": 3,
            "evidence_refs": [
                "reports/runtime/retry-policy-diff-2026-03-14.json",
            ],
        }
    ]

    first_bundle = serialize_req_018_context_bundle(payload_a)
    second_bundle = serialize_req_018_context_bundle(payload_a)
    third_bundle = serialize_req_018_context_bundle(payload_b)

    assert first_bundle == second_bundle
    assert first_bundle == third_bundle

    first_out = extract_strategic_debt_signals(payload_a)
    second_out = extract_strategic_debt_signals(payload_a)
    assert first_out == second_out
