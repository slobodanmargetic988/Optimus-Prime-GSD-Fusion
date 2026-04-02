from scripts import strategy_context_sweep as sweep


def _previous_revision_payload() -> dict:
    return {
        "revision_id": "strategy-2026-03-14T08:00:00Z",
        "mission_scope": {
            "primary_objective": "Stabilize planner reliability",
            "focus_areas": ["contract coverage", "runtime readiness"],
            "constraints": {"task_floor": 400, "change_budget": "medium"},
        },
        "runtime_data": {
            "runtime_mode": "shared",
            "queue_backlog": 3,
            "blocked_cycles": 0,
            "active_incidents": [],
        },
        "ecosystem_signals": {
            "upstream_projects": [{"project_id": "prj.tetris", "signal": "stable"}],
            "risk_flags": ["none"],
        },
        "recommendations": [
            {
                "recommendation_id": "rec.scope-refresh",
                "summary": "Refresh mission/scope alignment with ecosystem evidence.",
                "anchors": ["mission_scope"],
            },
            {
                "recommendation_id": "rec.runtime-hardening",
                "summary": "Keep runtime lane stable for planner throughput.",
                "anchors": ["runtime_data"],
            },
            {
                "recommendation_id": "rec.ecosystem-signal-response",
                "summary": "Adjust integration priorities based on upstream signals.",
                "anchors": ["ecosystem_signals"],
            },
        ],
        "evidence_refs": [
            "strategy/history/strategy-2026-03-14T08:00:00Z/STRATEGY.json",
            "reports/runtime/runtime-status-2026-03-14.json",
        ],
    }


def _current_revision_payload() -> dict:
    return {
        "revision_id": "strategy-2026-03-15T08:00:00Z",
        "mission_scope": {
            "primary_objective": "Stabilize planner reliability",
            "focus_areas": ["contract coverage", "runtime readiness", "delta traceability"],
            "constraints": {"task_floor": 400, "change_budget": "tight"},
        },
        "runtime_data": {
            "runtime_mode": "isolated",
            "queue_backlog": 5,
            "blocked_cycles": 2,
            "active_incidents": ["runtime_contention"],
        },
        "ecosystem_signals": {
            "upstream_projects": [{"project_id": "prj.tetris", "signal": "degraded"}],
            "risk_flags": ["none", "integration_latency"],
        },
        "recommendations": [
            {
                "recommendation_id": "rec.scope-refresh",
                "summary": "Refresh mission/scope alignment with ecosystem evidence.",
                "anchors": ["mission_scope"],
            },
            {
                "recommendation_id": "rec.runtime-hardening",
                "summary": "Increase isolation to recover planner throughput.",
                "anchors": ["runtime_data"],
            },
            {
                "recommendation_id": "rec.ecosystem-signal-response",
                "summary": "Adjust integration priorities based on upstream signals.",
                "anchors": ["ecosystem_signals"],
            },
        ],
        "evidence_refs": [
            "strategy/current/STRATEGY.json",
            "reports/runtime/runtime-status-2026-03-15.json",
            "reports/ecosystem/signals-2026-03-15.json",
        ],
        "broad_sweep_inputs": {
            "include_rule": "direct_child_repository_roots_only",
            "direct_child_count": 4,
            "discovered_project_ids": ["prj.optimus-prime-gsd-fusion", "prj.tetris"],
            "source_ref_coverage": {
                "project_count": 2,
                "complete_project_count": 1,
                "partial_project_count": 1,
                "mission_ref_count": 2,
                "scope_ref_count": 1,
            },
            "excluded_reason_counts": {
                "exclude_non_directory": 0,
                "exclude_hidden_path": 0,
                "exclude_archived_path": 1,
                "exclude_non_owner_path": 0,
                "exclude_non_repository_path": 1,
            },
        },
        "cross_project_context": [
            {
                "project_id": "prj.optimus-prime-gsd-fusion",
                "context_status": "complete",
                "summary": "Primary project has complete mission/scope evidence.",
                "evidence_refs": [
                    "Optimus-Prime-GSD-Fusion/.git",
                    "Optimus-Prime-GSD-Fusion/mission.md",
                    "Optimus-Prime-GSD-Fusion/scope.md",
                ],
            },
            {
                "project_id": "prj.tetris",
                "context_status": "partial",
                "summary": "Peer project is missing scope evidence.",
                "reason_codes": ["missing_scope_doc"],
                "evidence_refs": [
                    "Tetris/.git",
                    "Tetris/mission.md",
                    "missing:Tetris/scope.md#missing_scope_doc",
                ],
            },
        ],
        "earth_sweep_evidence_refs": [
            "Optimus-Prime-GSD-Fusion/.git",
            "Optimus-Prime-GSD-Fusion/mission.md",
            "Optimus-Prime-GSD-Fusion/scope.md",
            "Tetris/.git",
            "Tetris/mission.md",
            "missing:Tetris/scope.md#missing_scope_doc",
        ],
        "proposed_cross_project_obligations": [
            {
                "obligation_id": "obl.cross-project.runtime-sync",
                "title": "Coordinate runtime hardening across active projects.",
                "project_ids": ["prj.optimus-prime-gsd-fusion", "prj.tetris"],
                "evidence_refs": ["Optimus-Prime-GSD-Fusion/mission.md", "Tetris/mission.md"],
            },
            {
                "obligation_id": "obl.cross-project.pending-peer-scope",
                "title": "Publish peer scope before integration expansion.",
                "project_ids": ["prj.tetris"],
                "evidence_refs": [],
            },
        ],
    }


def test_req010_integration_enforces_evidence_backed_cross_project_usage():
    payload = sweep.build_change_detection_since_previous_strategy_revision(
        _previous_revision_payload(),
        _current_revision_payload(),
    )

    assert sweep.validate_change_detection_since_previous_strategy_revision(payload) == []

    evidence_refs = payload["evidence_refs"]
    assert evidence_refs == sorted(set(evidence_refs))
    assert "Optimus-Prime-GSD-Fusion/mission.md" in evidence_refs
    assert "Tetris/mission.md" in evidence_refs

    context_inputs = payload["context_inputs"]
    assert sorted(context_inputs.keys()) == [
        "broad_sweep_inputs",
        "cross_project_context",
        "earth_sweep_evidence_refs",
        "evidence_refs",
    ]
    assert context_inputs["broad_sweep_inputs"]["discovered_project_ids"] == [
        "prj.optimus-prime-gsd-fusion",
        "prj.tetris",
    ]
    assert context_inputs["earth_sweep_evidence_refs"] == sorted(context_inputs["earth_sweep_evidence_refs"])

    usage = payload["cross_project_context_usage"]
    assert sorted(usage.keys()) == ["context_project_ids", "evidence_refs", "obligations", "open_risks"]
    assert usage["context_project_ids"] == ["prj.optimus-prime-gsd-fusion", "prj.tetris"]

    obligations = usage["obligations"]
    assert [row["obligation_id"] for row in obligations] == ["obl.cross-project.runtime-sync"]
    for row in obligations:
        assert row["evidence_refs"]
        for ref in row["evidence_refs"]:
            assert ref in context_inputs["earth_sweep_evidence_refs"]

    open_risk_ids = {row["risk_id"] for row in usage["open_risks"]}
    assert "risk.req010.cross-project-context-partial" in open_risk_ids
    assert "risk.req010.cross-project-obligation.obl.cross-project.pending-peer-scope" in open_risk_ids
    for row in usage["open_risks"]:
        assert row["reason_code"] == "missing_peer_project_doc"
        assert row["evidence_refs"]

    detected_change_ids = set(payload["change_summary"]["change_ids"])
    referenced_change_ids = {
        change_id
        for row in payload["recommendation_deltas"]
        for change_id in row["change_ids"]
    }
    assert referenced_change_ids == detected_change_ids

    for row in payload["recommendation_deltas"]:
        assert sorted(row.keys()) == [
            "anchors",
            "change_ids",
            "delta_type",
            "evidence_refs",
            "linked_context_project_ids",
            "recommendation_id",
            "summary",
        ]
        assert row["linked_context_project_ids"] == usage["context_project_ids"]
        assert row["evidence_refs"] == sorted(set(row["evidence_refs"]))
        for ref in row["evidence_refs"]:
            assert ref in evidence_refs
