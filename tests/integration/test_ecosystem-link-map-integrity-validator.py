import copy

from scripts import strategy_artifacts_handoff as module


def _base_payload() -> dict:
    return {
        "analysis_type": "ecosystem_link_map_integrity_validator",
        "now_utc": "2026-03-16T12:30:00Z",
        "target_project": {
            "project_id": "prj.optimus-prime-gsd-fusion",
            "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion",
        },
        "link_map_ref": "strategy/current/ECOSYSTEM_LINK_MAP.json",
        "broad_sweep_context": {
            "projects_considered": [
                "prj.analytics-hub",
                "prj.runtime-core",
            ],
            "earth_sweep_evidence_refs": [
                "reports/earth/sweeps/2026-03-16/analytics-hub.json",
                "reports/earth/sweeps/2026-03-16/runtime-core.json",
            ],
        },
        "discovered_projects": [
            {
                "project_id": "prj.optimus-prime-gsd-fusion",
                "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion",
            },
            {
                "project_id": "prj.runtime-core",
                "project_root": "/Users/slobodan/projects/Earth/Runtime-Core",
            },
            {
                "project_id": "prj.analytics-hub",
                "project_root": "/Users/slobodan/projects/Earth/Analytics-Hub",
            },
        ],
        "links": [
            {
                "link_id": "link.runtime-core.depends-on",
                "source_project_id": "prj.optimus-prime-gsd-fusion",
                "target_project_id": "prj.runtime-core",
                "link_type": "depends_on",
                "declared_in": "strategy/current/ECOSYSTEM_LINK_MAP.json#links[0]",
                "source_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-230/link-runtime-core.md#L1",
                    "strategy/current/strategy_packet.v1.json#strategy.link_map_ref",
                ],
            },
            {
                "link_id": "link.analytics-export.emits-to",
                "source_project_id": "prj.optimus-prime-gsd-fusion",
                "target_project_id": "prj.analytics-lab",
                "link_type": "emits_to",
                "declared_in": "strategy/current/ECOSYSTEM_LINK_MAP.json#links[1]",
                "source_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-230/link-analytics-lab.md#L1",
                ],
            },
            {
                "link_id": "link.runtime-core.self-loop",
                "source_project_id": "prj.runtime-core",
                "target_project_id": "prj.runtime-core",
                "link_type": "depends_on",
                "declared_in": "strategy/current/ECOSYSTEM_LINK_MAP.json#links[2]",
                "source_refs": [
                    "strategy/current/ECOSYSTEM_LINK_MAP.json#links[2]",
                ],
            },
        ],
    }


def test_req_063_integration_emits_evidence_backed_processing_behavior() -> None:
    payload = module.build_req_063_ecosystem_link_map_integrity_validator(_base_payload())

    assert module.validate_req_063_ecosystem_link_map_integrity_validator(payload) == []

    processing = payload["processing_behavior"]
    usage = processing["cross_project_context_usage"]
    recommendation = processing["recommendation"]

    assert usage == {
        "cross_project_context_provided": True,
        "cross_project_context_used": True,
        "projects_considered": [
            "prj.analytics-hub",
            "prj.analytics-lab",
            "prj.runtime-core",
        ],
        "earth_sweep_evidence_refs_considered": [
            "reports/earth/sweeps/2026-03-16/analytics-hub.json",
            "reports/earth/sweeps/2026-03-16/runtime-core.json",
        ],
        "link_ids_with_cross_project_context": [
            "link.analytics-export.emits-to",
            "link.runtime-core.depends-on",
            "link.runtime-core.self-loop",
        ],
        "cross_project_obligation_count": 1,
        "open_risk_count": 1,
        "evidence_refs_used": [
            "reports/earth/sweeps/2026-03-16/analytics-hub.json",
            "reports/earth/sweeps/2026-03-16/runtime-core.json",
            "reports/optimus-prime/planning/evidence/TASK-230/link-analytics-lab.md#L1",
            "reports/optimus-prime/planning/evidence/TASK-230/link-runtime-core.md#L1",
            "strategy/current/ECOSYSTEM_LINK_MAP.json#links[2]",
            "strategy/current/strategy_packet.v1.json#strategy.link_map_ref",
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
    assert recommendation["decision"] == "proceed-with-open-risks"
    assert recommendation["confidence"] == "medium"
    assert recommendation["rationale"] == "links=3 valid=1 orphaned=1 broken=1 obligations=1 open_risks=1"
    assert recommendation["evidence_refs"] == usage["evidence_refs_used"]

    actions = {row["link_id"]: row for row in recommendation["recommended_actions"]}
    assert sorted(actions) == [
        "link.analytics-export.emits-to",
        "link.runtime-core.depends-on",
        "link.runtime-core.self-loop",
    ]
    for row in recommendation["recommended_actions"]:
        assert set(row.keys()) == {
            "action_id",
            "link_id",
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

    assert actions["link.runtime-core.depends-on"]["action_scope"] == "cross-project"
    assert actions["link.analytics-export.emits-to"]["action_scope"] == "cross-project"
    assert actions["link.runtime-core.self-loop"]["action_scope"] == "cross-project"

    assert recommendation["cross_project_obligations"] == [
        {
            "obligation_id": "obligation.link.runtime-core.depends-on.prj.runtime-core",
            "link_id": "link.runtime-core.depends-on",
            "project_id": "prj.runtime-core",
            "summary": (
                "Keep ecosystem link 'link.runtime-core.depends-on' synchronized with discovered project "
                "'prj.runtime-core'."
            ),
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-16/analytics-hub.json",
                "reports/earth/sweeps/2026-03-16/runtime-core.json",
            ],
        }
    ]
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk.link.analytics-export.emits-to",
            "link_id": "link.analytics-export.emits-to",
            "summary": (
                "Link 'link.analytics-export.emits-to' references undiscovered project ids: prj.analytics-lab."
            ),
            "reason_code": "missing_discovered_project",
            "required_evidence_refs": [
                "reports/earth/sweeps/2026-03-16/analytics-hub.json",
                "reports/earth/sweeps/2026-03-16/runtime-core.json",
                "reports/optimus-prime/planning/evidence/TASK-230/link-analytics-lab.md#L1",
            ],
        }
    ]


def test_req_063_integration_keeps_cross_project_link_as_open_risk_without_earth_refs() -> None:
    payload_input = copy.deepcopy(_base_payload())
    payload_input["broad_sweep_context"]["earth_sweep_evidence_refs"] = []

    payload = module.build_req_063_ecosystem_link_map_integrity_validator(payload_input)

    assert module.validate_req_063_ecosystem_link_map_integrity_validator(payload) == []

    usage = payload["processing_behavior"]["cross_project_context_usage"]
    recommendation = payload["processing_behavior"]["recommendation"]

    assert usage["cross_project_context_used"] is True
    assert usage["earth_sweep_evidence_refs_considered"] == []
    assert usage["cross_project_obligation_count"] == 0
    assert usage["open_risk_count"] == 2

    assert recommendation["decision"] == "collect-earth-evidence"
    assert recommendation["cross_project_obligations"] == []
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk.link.analytics-export.emits-to",
            "link_id": "link.analytics-export.emits-to",
            "summary": (
                "Link 'link.analytics-export.emits-to' references undiscovered project ids: prj.analytics-lab."
            ),
            "reason_code": "missing_discovered_project",
            "required_evidence_refs": [
                "reports/optimus-prime/planning/evidence/TASK-230/link-analytics-lab.md#L1",
            ],
        },
        {
            "risk_id": "risk.link.runtime-core.depends-on",
            "link_id": "link.runtime-core.depends-on",
            "summary": (
                "Cross-project link 'link.runtime-core.depends-on' should stay evidence-backed, but Earth-sweep refs "
                "are missing."
            ),
            "reason_code": "missing_earth_sweep_evidence_refs",
            "required_evidence_refs": ["missing:earth-sweep-evidence-ref"],
        },
    ]
