import json

from scripts import strategy_llm_pipeline as module


def _build_payload(**overrides: object) -> dict:
    payload = {
        "target_project_root": "/workspace/projects/optimus-prime",
        "earth_root": "/workspace/projects/Earth",
        "output_root": "/workspace/projects/optimus-prime/strategy/out",
        "revision_identity": "rev-req025-hardening-r1",
        "strategy_goal": "Harden REQ-025 replay and failure-path diagnostics.",
        "call_depth": 4,
        "evidence_refs": [
            "reports/optimus-prime/planning/evidence/TASK-081/TASK_EVIDENCE.json",
            "reports/earth/sweeps/2026-03-15/portfolio.json",
            "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
        ],
        "target_project_evidence_refs": [
            "reports/optimus-prime/planning/evidence/TASK-081/TASK_EVIDENCE.json",
        ],
        "earth_sweep_evidence_refs": [
            "reports/earth/sweeps/2026-03-15/portfolio.json",
            "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
        ],
        "cross_project_context": [
            {
                "project_id": "runtime-orchestrator",
                "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
                "context_note": "Shared runtime coordination context for REQ-025 hardening.",
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_req_025_cross_call_contradiction_between_analysis_and_synthesis_emits_deterministic_reason_code() -> None:
    payload = module.build_req_025_multi_call_strategy_pipeline_planner(
        **_build_payload(
            strategic_claims=[
                {
                    "claim_id": "claim-runtime-sync",
                    "phase": "analysis",
                    "summary": "Analysis concludes runtime-orchestrator coordination is mandatory.",
                    "position": "require-runtime-sync",
                    "source_call_sequence": 2,
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                    ],
                },
                {
                    "claim_id": "claim-runtime-sync",
                    "phase": "synthesis",
                    "summary": "Synthesis concludes runtime-orchestrator coordination should be deferred.",
                    "position": "defer-runtime-sync",
                    "source_call_sequence": 4,
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                    ],
                },
            ]
        )
    )

    assert module.validate_req_025_multi_call_strategy_pipeline_planner(payload) == []
    plan = payload["processing_behavior"]["pipeline_plan"]
    contradiction_risk = next(
        row
        for row in payload["processing_behavior"]["recommendation"]["open_risks"]
        if row["reason_code"] == "cross_call_contradiction"
    )
    expected_refs = sorted(
        [
            module._build_call_output_ref(
                plan_id=plan["plan_id"],
                call_id=plan["calls"][1]["call_id"],
                expected_output=plan["calls"][1]["expected_output"],
            ),
            module._build_call_output_ref(
                plan_id=plan["plan_id"],
                call_id=plan["calls"][3]["call_id"],
                expected_output=plan["calls"][3]["expected_output"],
            ),
            "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
        ]
    )
    assert contradiction_risk["risk_id"] == "risk-claim-claim-runtime-sync-contradiction"
    assert contradiction_risk["required_evidence_refs"] == expected_refs
    assert payload["processing_behavior"]["recommendation"]["decision"] == "resolve-strategy-gaps"


def test_req_025_uncited_strategic_claim_is_blocked_by_citation_discipline() -> None:
    payload = module.build_req_025_multi_call_strategy_pipeline_planner(
        **_build_payload(
            strategic_claims=[
                {
                    "claim_id": "claim-unbacked-acceleration",
                    "phase": "analysis",
                    "summary": "Analysis proposes an acceleration path without attaching evidence.",
                    "position": "accelerate-rollout",
                    "source_call_sequence": 3,
                    "evidence_refs": [],
                }
            ]
        )
    )

    assert module.validate_req_025_multi_call_strategy_pipeline_planner(payload) == []
    plan = payload["processing_behavior"]["pipeline_plan"]
    uncited_risk = next(
        row
        for row in payload["processing_behavior"]["recommendation"]["open_risks"]
        if row["reason_code"] == "uncited_strategic_claim"
    )
    expected_ref = module._build_call_output_ref(
        plan_id=plan["plan_id"],
        call_id=plan["calls"][2]["call_id"],
        expected_output=plan["calls"][2]["expected_output"],
    )
    assert uncited_risk == {
        "risk_id": "risk-claim-claim-unbacked-acceleration-citation",
        "summary": "Analysis proposes an acceleration path without attaching evidence.",
        "reason_code": "uncited_strategic_claim",
        "required_evidence_refs": [expected_ref],
    }
    assert payload["processing_behavior"]["recommendation"]["recommended_actions"] == []
    assert payload["processing_behavior"]["recommendation"]["decision"] == "resolve-strategy-gaps"


def test_req_025_call_chain_replay_keeps_recommendation_ids_and_ordering_stable() -> None:
    first = module.build_req_025_multi_call_strategy_pipeline_planner(
        **_build_payload(
            revision_identity="rev-req025-hardening-r3",
            candidate_recommendations=[
                {
                    "action_id": "action-zeta-follow-through",
                    "summary": "Keep final handoff packaging deterministic.",
                    "rationale": "Replay diagnostics depend on stable terminal recommendation ordering.",
                    "action_scope": "local",
                    "requires_earth_evidence": False,
                    "project_id": "",
                    "evidence_refs": [
                        "reports/optimus-prime/planning/evidence/TASK-081/TASK_EVIDENCE.json",
                    ],
                    "next_step": "Preserve stable recommendation ordering across repeated runs.",
                },
                {
                    "action_id": "action-alpha-runtime-sync",
                    "summary": "Coordinate runtime assumptions with runtime-orchestrator.",
                    "rationale": "Earth sweep evidence anchors the cross-project dependency.",
                    "action_scope": "cross-project",
                    "requires_earth_evidence": True,
                    "project_id": "runtime-orchestrator",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                    ],
                    "next_step": "Carry the obligation with Earth evidence refs attached.",
                },
                {
                    "action_id": "action-gamma-replay-hardening",
                    "summary": "Keep replay evidence compact and deterministic.",
                    "rationale": "Stable action identifiers simplify rerun diffing.",
                    "action_scope": "local",
                    "requires_earth_evidence": False,
                    "project_id": "",
                    "evidence_refs": [
                        "reports/optimus-prime/planning/evidence/TASK-081/TASK_EVIDENCE.json",
                    ],
                    "next_step": "Retain deterministic action sorting in recommendation output.",
                },
            ]
        )
    )
    second = module.build_req_025_multi_call_strategy_pipeline_planner(
        **_build_payload(
            revision_identity="rev-req025-hardening-r3",
            candidate_recommendations=[
                {
                    "action_id": "action-gamma-replay-hardening",
                    "summary": "Keep replay evidence compact and deterministic.",
                    "rationale": "Stable action identifiers simplify rerun diffing.",
                    "action_scope": "local",
                    "requires_earth_evidence": False,
                    "project_id": "",
                    "evidence_refs": [
                        "reports/optimus-prime/planning/evidence/TASK-081/TASK_EVIDENCE.json",
                    ],
                    "next_step": "Retain deterministic action sorting in recommendation output.",
                },
                {
                    "action_id": "action-zeta-follow-through",
                    "summary": "Keep final handoff packaging deterministic.",
                    "rationale": "Replay diagnostics depend on stable terminal recommendation ordering.",
                    "action_scope": "local",
                    "requires_earth_evidence": False,
                    "project_id": "",
                    "evidence_refs": [
                        "reports/optimus-prime/planning/evidence/TASK-081/TASK_EVIDENCE.json",
                    ],
                    "next_step": "Preserve stable recommendation ordering across repeated runs.",
                },
                {
                    "action_id": "action-alpha-runtime-sync",
                    "summary": "Coordinate runtime assumptions with runtime-orchestrator.",
                    "rationale": "Earth sweep evidence anchors the cross-project dependency.",
                    "action_scope": "cross-project",
                    "requires_earth_evidence": True,
                    "project_id": "runtime-orchestrator",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                    ],
                    "next_step": "Carry the obligation with Earth evidence refs attached.",
                },
            ]
        )
    )

    assert module.validate_req_025_multi_call_strategy_pipeline_planner(first) == []
    assert module.validate_req_025_multi_call_strategy_pipeline_planner(second) == []
    assert first["call_metadata"]["canonical_processing_input"] == second["call_metadata"]["canonical_processing_input"]
    assert first["call_metadata"]["processing_input_sha256"] == second["call_metadata"]["processing_input_sha256"]
    assert first["call_metadata"]["processing_call_id"] == second["call_metadata"]["processing_call_id"]
    assert first["processing_behavior"]["recommendation"]["recommended_actions"] == second["processing_behavior"][
        "recommendation"
    ]["recommended_actions"]
    assert [row["action_id"] for row in first["processing_behavior"]["recommendation"]["recommended_actions"]] == [
        "action-alpha-runtime-sync",
        "action-gamma-replay-hardening",
        "action-zeta-follow-through",
    ]

    first_bundle = json.dumps(
        first["processing_behavior"]["recommendation"]["recommended_actions"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    second_bundle = json.dumps(
        second["processing_behavior"]["recommendation"]["recommended_actions"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    assert first_bundle == second_bundle
