import copy

from scripts import strategy_artifacts_handoff as module


def _base_input() -> dict:
    return {
        "analysis_type": "recommendation_quality_validator",
        "now_utc": "2026-03-16T10:20:00Z",
        "target_project": {
            "project_id": "optimus-prime-gsd-fusion",
            "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion",
        },
        "broad_sweep_context": {
            "earth_sweep_evidence_refs": [
                "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
                "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
            ],
            "projects_considered": [
                "earth-core-runtime",
                "earth-shared-observability",
            ],
            "cross_project_obligations": [
                {
                    "obligation_id": "obligation-align-earth-runtime-gates",
                    "project_id": "earth-core-runtime",
                    "summary": "Align Earth runtime quality gating before planner packet rollout.",
                    "earth_sweep_evidence_refs": [
                        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json"
                    ],
                }
            ],
            "unresolved_ideas": [
                {
                    "idea_id": "idea-review-shared-observability-handoff",
                    "summary": (
                        "Validate earth-shared-observability ownership before promoting "
                        "more shared packet routing changes."
                    ),
                    "earth_sweep_evidence_refs": [
                        "reports/earth/sweeps/shared-observability/signals-2026-03-14.json"
                    ],
                }
            ],
        },
        "quality_thresholds": {
            "min_rationale_word_count": 12,
            "min_evidence_citations": 2,
        },
        "recommendations": [
            {
                "recommendation_id": "rec.contract-enforce-quality-floor",
                "summary": "Enforce recommendation quality checks before planner packet handoff.",
                "rationale": (
                    "The planner packet should only ship recommendations with enough substance "
                    "to explain sequencing and cite the source artifacts that justify execution."
                ),
                "packet_kind": "target-project",
                "lane": "execution",
                "priority": "high",
                "sequence_hint": 1,
                "evidence_refs": [
                    "contracts/req/REQ-046_final-strategy-synthesis-composer.md",
                    "reports/quality/req-039-rationale-quality-score.json",
                ],
            },
            {
                "recommendation_id": "rec.align-earth-runtime-canary",
                "summary": "Align the Earth runtime canary stabilization window before widening rollout.",
                "rationale": (
                    "Cross-project packet routing stays defensible when the recommendation keeps "
                    "explicit Earth-sweep evidence that ties the dependency to a concrete runtime plan."
                ),
                "packet_kind": "cross-project",
                "lane": "coordination",
                "priority": "high",
                "sequence_hint": 2,
                "evidence_refs": [
                    "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
                    "reports/quality/req-039-rationale-quality-score.json",
                ],
            },
            {
                "recommendation_id": "rec.review-reuse-drift",
                "summary": "Review reuse drift before widening shared contract rollout.",
                "rationale": "Needs more proof soon.",
                "packet_kind": "cross-project",
                "lane": "coordination",
                "priority": "medium",
                "sequence_hint": 3,
                "evidence_refs": [
                    "reports/earth/sweeps/shared-observability/signals-2026-03-14.json"
                ],
            },
            {
                "recommendation_id": "rec.fill-routing-gap",
                "summary": "Fill routing metadata before planner handoff.",
                "rationale": (
                    "Cross-project packet routing must stay explicit so the planner can place "
                    "this recommendation on the correct lane without inventing missing context "
                    "from surrounding prose."
                ),
                "packet_kind": "target-project",
                "priority": "medium",
                "sequence_hint": 4,
                "evidence_refs": [
                    "contracts/req/REQ-055_constraint-classification-artifact.md",
                    "strategy/current/samples/REQ-046_final-strategy-synthesis-composer.sample.json",
                ],
            },
        ],
    }


def test_req_061_integration_uses_broad_sweep_context_for_planner_facing_recommendations() -> None:
    payload = module.build_req_061_recommendation_quality_validator(_base_input())
    assert module.validate_req_061_recommendation_quality_validator(payload) == []

    quality_validation = payload["quality_validation"]
    processing = payload["processing_behavior"]
    recommendation = processing["recommendation"]
    usage = processing["context_usage"]

    assert quality_validation["planner_readiness"]["allowed_recommendation_ids"] == [
        "rec.contract-enforce-quality-floor",
        "rec.align-earth-runtime-canary",
    ]
    assert quality_validation["planner_readiness"]["blocked_recommendation_ids"] == [
        "rec.review-reuse-drift",
        "rec.fill-routing-gap",
    ]

    assert recommendation["decision"] == "allow-planner-packet-with-open-risks"
    assert recommendation["confidence"] == "medium"
    assert [row["recommendation_id"] for row in recommendation["recommended_actions"]] == [
        "rec.contract-enforce-quality-floor",
        "rec.align-earth-runtime-canary",
    ]
    for row in recommendation["recommended_actions"]:
        assert set(row.keys()) == {
            "action_id",
            "recommendation_id",
            "summary",
            "rationale",
            "packet_kind",
            "lane",
            "priority",
            "sequence_hint",
            "evidence_refs",
        }
        assert row["evidence_refs"]

    cross_project = recommendation["recommended_actions"][1]
    assert cross_project["packet_kind"] == "cross-project"
    assert "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json" in cross_project["evidence_refs"]

    assert recommendation["cross_project_obligations"] == [
        {
            "obligation_id": "obligation-align-earth-runtime-gates",
            "project_id": "earth-core-runtime",
            "summary": "Align Earth runtime quality gating before planner packet rollout.",
            "evidence_refs": [
                "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
                "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
            ],
        }
    ]
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk-idea-review-shared-observability-handoff",
            "summary": "Validate earth-shared-observability ownership before promoting more shared packet routing changes.",
            "reason_code": "unresolved_idea_open_risk",
            "evidence_refs": [
                "reports/earth/sweeps/shared-observability/signals-2026-03-14.json"
            ],
            "required_evidence_refs": [
                "reports/earth/sweeps/shared-observability/signals-2026-03-14.json"
            ],
        }
    ]

    assert usage["cross_project_context_provided"] is True
    assert usage["cross_project_context_used"] is True
    assert usage["earth_sweep_context_used"] is True
    assert usage["projects_considered"] == [
        "earth-core-runtime",
        "earth-shared-observability",
    ]
    assert usage["earth_sweep_evidence_refs_considered"] == [
        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
        "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
    ]
    assert usage["accepted_recommendation_ids"] == [
        "rec.contract-enforce-quality-floor",
        "rec.align-earth-runtime-canary",
    ]
    assert usage["blocked_recommendation_ids"] == [
        "rec.review-reuse-drift",
        "rec.fill-routing-gap",
    ]
    assert usage["recommendation_fields_complete"] is True
    assert usage["required_recommendation_fields"] == [
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "recommended_actions",
        "cross_project_obligations",
        "open_risks",
    ]


def test_req_061_integration_records_open_risks_when_cross_project_context_lacks_earth_refs() -> None:
    test_input = copy.deepcopy(_base_input())
    test_input["broad_sweep_context"]["earth_sweep_evidence_refs"] = []
    test_input["broad_sweep_context"]["projects_considered"] = []

    payload = module.build_req_061_recommendation_quality_validator(test_input)
    assert module.validate_req_061_recommendation_quality_validator(payload) == []

    recommendation = payload["processing_behavior"]["recommendation"]
    usage = payload["processing_behavior"]["context_usage"]

    assert [row["recommendation_id"] for row in recommendation["recommended_actions"]] == [
        "rec.contract-enforce-quality-floor"
    ]
    assert recommendation["cross_project_obligations"] == []

    missing_earth_risks = [
        row for row in recommendation["open_risks"] if row["reason_code"] == "missing_earth_sweep_evidence_refs"
    ]
    assert missing_earth_risks == [
        {
            "risk_id": "risk-obligation-align-earth-runtime-gates",
            "summary": "Align Earth runtime quality gating before planner packet rollout.",
            "reason_code": "missing_earth_sweep_evidence_refs",
            "evidence_refs": [
                "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json"
            ],
            "required_evidence_refs": [
                "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json"
            ],
        },
        {
            "risk_id": "risk-rec.align-earth-runtime-canary",
            "summary": "Align the Earth runtime canary stabilization window before widening rollout.",
            "reason_code": "missing_earth_sweep_evidence_refs",
            "evidence_refs": [
                "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
                "reports/quality/req-039-rationale-quality-score.json",
            ],
            "required_evidence_refs": [
                "missing:earth-sweep-evidence-ref"
            ],
        },
    ]
    assert usage["cross_project_context_used"] is True
    assert usage["earth_sweep_context_used"] is False
