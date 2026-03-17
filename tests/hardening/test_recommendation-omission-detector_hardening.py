from scripts import strategy_llm_pipeline as module


def _base_input() -> dict:
    return {
        "target_project_root": "/workspace/projects/optimus-prime",
        "earth_root": "/workspace/projects/Earth",
        "output_root": "/workspace/projects/optimus-prime/strategy/out",
        "revision_identity": "rev-req044-hardening-r1",
        "strategy_goal": "Harden replay and failure-path omission detection for required recommendation classes.",
        "call_id": "call-recommendation-omission-detector",
        "checked_at_utc": "2026-03-16T18:05:00Z",
        "call_chain": [
            {
                "sequence": 1,
                "call_id": "call-1",
                "phase": "analysis",
                "output_ref": "REQ-044::call::call-1::output::situational_analysis",
            },
            {
                "sequence": 2,
                "call_id": "call-2",
                "phase": "synthesis",
                "output_ref": "REQ-044::call::call-2::output::recommendation_synthesis",
            },
        ],
        "target_project_evidence_refs": [
            "reports/optimus-prime/planning/evidence/TASK-158/TASK_EVIDENCE.json"
        ],
        "earth_sweep_evidence_refs": [
            "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json"
        ],
        "cross_project_context": [
            {
                "project_id": "runtime-orchestrator",
                "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json"
                ],
                "context_note": "Runtime orchestrator owns the shared recovery envelope.",
            }
        ],
        "mission_required_recommendation_classes": [
            {
                "class_id": "class.local-determinism",
                "summary": "Mission requires deterministic local diagnostics to stay replay-stable.",
                "required_scope": "local",
                "project_id": "",
                "critical": True,
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-158/TASK_EVIDENCE.json"
                ],
            },
            {
                "class_id": "class.runtime-sync",
                "summary": "Mission requires runtime-orchestrator synchronization for shared recovery behavior.",
                "required_scope": "cross-project",
                "project_id": "runtime-orchestrator",
                "critical": True,
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json"
                ],
            },
        ],
        "ecosystem_required_recommendation_classes": [
            {
                "class_id": "class.analytics-routing",
                "summary": "Ecosystem needs cross-project analytics routing coverage for omission telemetry.",
                "required_scope": "cross-project",
                "project_id": "analytics-hub",
                "critical": False,
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/analytics-hub.json"
                ],
            }
        ],
        "candidate_recommendations": [
            {
                "recommendation_id": "rec.local-determinism",
                "recommendation_class_id": "class.local-determinism",
                "summary": "Keep local diagnostics deterministic across repeated runs.",
                "rationale": "Mission evidence ties branch reliability to stable local diagnostics.",
                "recommendation_scope": "local",
                "project_id": "",
                "requires_earth_evidence": False,
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-158/TASK_EVIDENCE.json"
                ],
                "next_step": "Run deterministic contract checks and attach evidence packets.",
            },
            {
                "recommendation_id": "rec.runtime-sync",
                "recommendation_class_id": "class.runtime-sync",
                "summary": "Coordinate runtime replay synchronization with runtime-orchestrator.",
                "rationale": "Mission requires a shared cross-project runtime synchronization obligation.",
                "recommendation_scope": "cross-project",
                "project_id": "runtime-orchestrator",
                "requires_earth_evidence": True,
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json"
                ],
                "next_step": "Open a runtime-orchestrator cross-project follow-up with earth evidence attached.",
            },
        ],
        "strategic_claims": [],
    }


def test_req_044_hardening_cross_call_contradiction_between_analysis_and_synthesis_is_blocked() -> None:
    input_payload = _base_input()
    input_payload["candidate_recommendations"][1]["strategic_claim_ids"] = [
        "claim.runtime-sync-position"
    ]
    input_payload["strategic_claims"] = [
        {
            "claim_id": "claim.runtime-sync-position",
            "phase": "analysis",
            "summary": "Analysis says runtime synchronization must stay cross-project.",
            "position": "coordinate",
            "source_call_sequence": 1,
            "evidence_refs": [
                "reports/optimus-prime/planning/evidence/TASK-158/TASK_EVIDENCE.json"
            ],
        },
        {
            "claim_id": "claim.runtime-sync-position",
            "phase": "synthesis",
            "summary": "Synthesis says runtime synchronization can be localized.",
            "position": "local-only",
            "source_call_sequence": 2,
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json"
            ],
        },
    ]

    payload = module.build_req_044_recommendation_omission_detector(**input_payload)

    assert module.validate_req_044_recommendation_omission_detector(payload) == []
    recommendation = payload["processing_behavior"]["recommendation"]
    runtime_omission = next(
        row
        for row in recommendation["omitted_recommendation_classes"]
        if row["class_id"] == "class.runtime-sync"
    )
    contradiction_risk = next(
        row
        for row in recommendation["open_risks"]
        if row["risk_id"] == "risk-claim-claim.runtime-sync-position-contradiction"
    )

    assert recommendation["decision"] == "resolve-strategy-gaps"
    assert runtime_omission["reason_code"] == "cross_call_contradiction"
    assert runtime_omission["required_evidence_refs"] == [
        "REQ-044::call::call-1::output::situational_analysis",
        "REQ-044::call::call-2::output::recommendation_synthesis",
        "REQ-044::call::call-recommendation-omission-detector::output::recommendation_omission_detector",
        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
        "reports/optimus-prime/planning/evidence/TASK-158/TASK_EVIDENCE.json",
    ]
    assert contradiction_risk["reason_code"] == "cross_call_contradiction"
    assert contradiction_risk["required_evidence_refs"] == [
        "REQ-044::call::call-1::output::situational_analysis",
        "REQ-044::call::call-2::output::recommendation_synthesis",
        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
        "reports/optimus-prime/planning/evidence/TASK-158/TASK_EVIDENCE.json",
    ]


def test_req_044_hardening_uncited_strategic_claim_is_blocked_by_citation_discipline() -> None:
    input_payload = _base_input()
    input_payload["ecosystem_required_recommendation_classes"] = []
    input_payload["mission_required_recommendation_classes"] = [
        input_payload["mission_required_recommendation_classes"][0]
    ]
    input_payload["candidate_recommendations"] = [
        {
            **input_payload["candidate_recommendations"][0],
            "strategic_claim_ids": ["claim.local-determinism-proof"],
        }
    ]
    input_payload["strategic_claims"] = [
        {
            "claim_id": "claim.local-determinism-proof",
            "phase": "synthesis",
            "summary": "Synthesis references uncited local diagnostic proof.",
            "position": "preserve",
            "source_call_sequence": 2,
            "evidence_refs": [
                "reports/optimus-prime/planning/evidence/TASK-158/uncited-claim.md"
            ],
        }
    ]

    payload = module.build_req_044_recommendation_omission_detector(**input_payload)

    assert module.validate_req_044_recommendation_omission_detector(payload) == []
    recommendation = payload["processing_behavior"]["recommendation"]
    local_omission = recommendation["omitted_recommendation_classes"][0]
    citation_risk = next(
        row
        for row in recommendation["open_risks"]
        if row["risk_id"] == "risk-claim-claim.local-determinism-proof-citation"
    )

    assert recommendation["decision"] == "resolve-strategy-gaps"
    assert local_omission["reason_code"] == "uncited_strategic_claim"
    assert local_omission["required_evidence_refs"] == [
        "REQ-044::call::call-2::output::recommendation_synthesis",
        "REQ-044::call::call-recommendation-omission-detector::output::recommendation_omission_detector",
        "reports/optimus-prime/planning/evidence/TASK-158/TASK_EVIDENCE.json",
        "reports/optimus-prime/planning/evidence/TASK-158/uncited-claim.md",
    ]
    assert citation_risk["reason_code"] == "uncited_strategic_claim"
    assert payload["processing_behavior"]["context_usage"]["blocked_recommendation_ids"] == [
        "rec.local-determinism"
    ]


def test_req_044_hardening_replay_keeps_recommendation_ids_and_order_stable() -> None:
    first = module.build_req_044_recommendation_omission_detector(**_base_input())

    second_input = _base_input()
    second_input["call_chain"] = list(reversed(second_input["call_chain"]))
    second_input["candidate_recommendations"] = list(reversed(second_input["candidate_recommendations"]))
    second = module.build_req_044_recommendation_omission_detector(**second_input)

    assert module.validate_req_044_recommendation_omission_detector(first) == []
    assert module.validate_req_044_recommendation_omission_detector(second) == []
    assert (
        first["processing_behavior"]["context_usage"]["emitted_recommendation_ids"]
        == second["processing_behavior"]["context_usage"]["emitted_recommendation_ids"]
        == ["rec.local-determinism", "rec.runtime-sync"]
    )
    assert first["call_metadata"]["canonical_processing_input"] == second["call_metadata"]["canonical_processing_input"]
    assert first["call_metadata"]["processing_input_sha256"] == second["call_metadata"]["processing_input_sha256"]
