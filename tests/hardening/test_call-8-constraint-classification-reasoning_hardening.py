import json

from scripts import strategy_llm_pipeline as module


def _build_payload(**overrides: object) -> dict:
    payload = {
        "target_project_root": "/workspace/projects/optimus-prime",
        "earth_root": "/workspace/projects/Earth",
        "output_root": "/workspace/projects/optimus-prime/strategy/out",
        "revision_identity": "rev-req033-hardening-r1",
        "strategy_goal": "Harden REQ-033 replay and failure-path diagnostics.",
        "evidence_refs": [
            "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
            "reports/earth/sweeps/2026-03-16/shared-observability.json",
            "reports/optimus-prime/planning/evidence/TASK-114/TASK_EVIDENCE.json",
        ],
        "target_project_evidence_refs": [
            "reports/optimus-prime/planning/evidence/TASK-114/TASK_EVIDENCE.json",
        ],
        "earth_sweep_evidence_refs": [
            "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
            "reports/earth/sweeps/2026-03-16/shared-observability.json",
        ],
        "cross_project_context": [
            {
                "project_id": "runtime-orchestrator",
                "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                ],
                "context_note": "Runtime orchestrator evidence anchors fallback ordering constraints.",
            },
            {
                "project_id": "shared-observability",
                "project_root": "/workspace/projects/Earth/shared-observability",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/shared-observability.json",
                ],
                "context_note": "Shared observability evidence anchors citation discipline.",
            },
        ],
        "constraint_candidates": [
            {
                "candidate_id": "constraint.trace-citations-required",
                "summary": "Planner outputs must retain citation-complete evidence refs.",
                "classification": "hard-constraint",
                "classification_rationale": "Citation discipline is mandatory before planner promotion.",
                "planner_implication": "Attach evidence refs and source output refs to every planner-facing row.",
                "source_output_refs": [
                    "strategy/current/samples/REQ-025_multi-call-strategy-pipeline-planner.sample.json#/call_metadata/llm_call_trace_rows",
                ],
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/shared-observability.json",
                    "reports/optimus-prime/planning/evidence/TASK-114/TASK_EVIDENCE.json",
                ],
            },
            {
                "candidate_id": "constraint.no-new-managers",
                "summary": "Do not introduce new managers or gates.",
                "classification": "hard-constraint",
                "classification_rationale": "Scope lock forbids net-new orchestration layers.",
                "planner_implication": "Keep remediation inside existing execution surfaces.",
                "source_output_refs": [
                    "strategy/current/samples/REQ-032_call-7-blocker-and-risk-policy-reasoning.sample.json#/processing_behavior/recommendation/fallback_sequence",
                ],
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-114/TASK_EVIDENCE.json",
                ],
            },
            {
                "candidate_id": "preference.fallback-aware-ordering",
                "summary": "Prefer fallback-backed mitigation before escalation follow-up.",
                "classification": "soft-preference",
                "classification_rationale": "Fallback-first sequencing improves resilience when evidence remains unchanged.",
                "planner_implication": "Bias the plan toward mitigation work before escalation-only branches.",
                "source_output_refs": [
                    "strategy/current/samples/REQ-032_call-7-blocker-and-risk-policy-reasoning.sample.json#/processing_behavior/recommendation/escalation_triggers",
                ],
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                ],
            },
            {
                "candidate_id": "idea.shared-constraint-summary",
                "summary": "Publish a shared constraint summary after planner output stabilizes.",
                "classification": "speculative-idea",
                "classification_rationale": "Useful downstream, but not yet planner-binding.",
                "planner_implication": "Track as optional follow-on work only.",
                "source_output_refs": [
                    "strategy/current/samples/REQ-028_call-3-gap-and-opportunity-reasoning.sample.json#/processing_behavior/recommendation/recommended_opportunities",
                ],
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                    "reports/earth/sweeps/2026-03-16/shared-observability.json",
                ],
            },
        ],
        "strategic_claims": [],
    }
    payload.update(overrides)
    return payload


def test_req_033_cross_call_contradiction_between_analysis_and_synthesis_outputs_emits_deterministic_reason_code() -> None:
    payload = module.build_req_033_call_8_constraint_classification_reasoning(
        **_build_payload(
            strategic_claims=[
                {
                    "claim_id": "claim-fallback-ordering",
                    "phase": "analysis",
                    "summary": "Analysis says fallback mitigation must land first.",
                    "position": "fallback-first",
                    "source_output_ref": "strategy/current/samples/REQ-028_call-3-gap-and-opportunity-reasoning.sample.json#/processing_behavior/recommendation/recommended_opportunities",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                    ],
                },
                {
                    "claim_id": "claim-fallback-ordering",
                    "phase": "synthesis",
                    "summary": "Synthesis says escalation work should land before fallback mitigation.",
                    "position": "escalation-first",
                    "source_output_ref": "strategy/current/samples/REQ-032_call-7-blocker-and-risk-policy-reasoning.sample.json#/processing_behavior/recommendation/escalation_triggers",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                    ],
                },
            ]
        )
    )

    assert module.validate_req_033_call_8_constraint_classification_reasoning(payload) == []
    contradiction_risk = next(
        row
        for row in payload["processing_behavior"]["recommendation"]["open_risks"]
        if row["reason_code"] == "cross_call_contradiction"
    )
    assert contradiction_risk == {
        "risk_id": "risk-claim-claim-fallback-ordering-contradiction",
        "summary": "Synthesis says escalation work should land before fallback mitigation.",
        "reason_code": "cross_call_contradiction",
        "required_evidence_refs": [
            "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
            "strategy/current/samples/REQ-028_call-3-gap-and-opportunity-reasoning.sample.json#/processing_behavior/recommendation/recommended_opportunities",
            "strategy/current/samples/REQ-032_call-7-blocker-and-risk-policy-reasoning.sample.json#/processing_behavior/recommendation/escalation_triggers",
        ],
    }
    assert payload["processing_behavior"]["recommendation"]["decision"] == "resolve-strategy-gaps"


def test_req_033_uncited_strategic_claim_is_blocked_by_citation_discipline() -> None:
    payload = module.build_req_033_call_8_constraint_classification_reasoning(
        **_build_payload(
            strategic_claims=[
                {
                    "claim_id": "claim-unbacked-promotion",
                    "phase": "analysis",
                    "summary": "Analysis promotes a planner shortcut without attached evidence.",
                    "position": "promote-shortcut",
                    "source_output_ref": "strategy/current/samples/REQ-025_multi-call-strategy-pipeline-planner.sample.json#/call_metadata/llm_call_trace_rows",
                    "evidence_refs": [],
                }
            ]
        )
    )

    assert module.validate_req_033_call_8_constraint_classification_reasoning(payload) == []
    uncited_risk = next(
        row
        for row in payload["processing_behavior"]["recommendation"]["open_risks"]
        if row["reason_code"] == "uncited_strategic_claim"
    )
    assert uncited_risk == {
        "risk_id": "risk-claim-claim-unbacked-promotion-citation",
        "summary": "Analysis promotes a planner shortcut without attached evidence.",
        "reason_code": "uncited_strategic_claim",
        "required_evidence_refs": [
            "strategy/current/samples/REQ-025_multi-call-strategy-pipeline-planner.sample.json#/call_metadata/llm_call_trace_rows",
        ],
    }
    assert payload["processing_behavior"]["recommendation"]["decision"] == "resolve-strategy-gaps"


def test_req_033_call_chain_replay_keeps_recommendation_ids_and_ordering_stable() -> None:
    first = module.build_req_033_call_8_constraint_classification_reasoning(
        **_build_payload(
            revision_identity="rev-req033-hardening-r3",
            constraint_candidates=list(reversed(_build_payload()["constraint_candidates"])),
            strategic_claims=[
                {
                    "claim_id": "claim-fallback-ordering",
                    "phase": "synthesis",
                    "summary": "Synthesis keeps fallback-first ordering intact.",
                    "position": "fallback-first",
                    "source_output_ref": "strategy/current/samples/REQ-032_call-7-blocker-and-risk-policy-reasoning.sample.json#/processing_behavior/recommendation/fallback_sequence",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                    ],
                },
                {
                    "claim_id": "claim-citation-discipline",
                    "phase": "analysis",
                    "summary": "Analysis preserves citation-complete planner promotion.",
                    "position": "citation-complete",
                    "source_output_ref": "strategy/current/samples/REQ-025_multi-call-strategy-pipeline-planner.sample.json#/call_metadata/llm_call_trace_rows",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-16/shared-observability.json",
                    ],
                },
            ],
        )
    )
    second = module.build_req_033_call_8_constraint_classification_reasoning(
        **_build_payload(
            revision_identity="rev-req033-hardening-r3",
            constraint_candidates=_build_payload()["constraint_candidates"],
            strategic_claims=[
                {
                    "claim_id": "claim-citation-discipline",
                    "phase": "analysis",
                    "summary": "Analysis preserves citation-complete planner promotion.",
                    "position": "citation-complete",
                    "source_output_ref": "strategy/current/samples/REQ-025_multi-call-strategy-pipeline-planner.sample.json#/call_metadata/llm_call_trace_rows",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-16/shared-observability.json",
                    ],
                },
                {
                    "claim_id": "claim-fallback-ordering",
                    "phase": "synthesis",
                    "summary": "Synthesis keeps fallback-first ordering intact.",
                    "position": "fallback-first",
                    "source_output_ref": "strategy/current/samples/REQ-032_call-7-blocker-and-risk-policy-reasoning.sample.json#/processing_behavior/recommendation/fallback_sequence",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                    ],
                },
            ],
        )
    )

    assert module.validate_req_033_call_8_constraint_classification_reasoning(first) == []
    assert module.validate_req_033_call_8_constraint_classification_reasoning(second) == []
    assert first["call_metadata"]["canonical_processing_input"] == second["call_metadata"]["canonical_processing_input"]
    assert first["call_metadata"]["processing_input_sha256"] == second["call_metadata"]["processing_input_sha256"]
    assert first["call_metadata"]["processing_call_id"] == second["call_metadata"]["processing_call_id"]

    first_contract = first["processing_behavior"]["recommendation"]["planner_contract"]
    second_contract = second["processing_behavior"]["recommendation"]["planner_contract"]
    assert first_contract == second_contract

    first_ids = [
        row["recommendation_id"]
        for key in ("hard_constraints", "soft_preferences", "speculative_ideas")
        for row in first_contract[key]
    ]
    second_ids = [
        row["recommendation_id"]
        for key in ("hard_constraints", "soft_preferences", "speculative_ideas")
        for row in second_contract[key]
    ]
    assert first_ids == second_ids == [
        "rec-call-8-constraint-no-new-managers",
        "rec-call-8-constraint-trace-citations-required",
        "rec-call-8-preference-fallback-aware-ordering",
        "rec-call-8-idea-shared-constraint-summary",
    ]

    first_bundle = json.dumps(first_contract, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    second_bundle = json.dumps(second_contract, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert first_bundle == second_bundle
