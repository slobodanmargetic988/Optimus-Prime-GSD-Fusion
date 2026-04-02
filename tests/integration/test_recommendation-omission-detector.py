from scripts import strategy_llm_pipeline as module


def _base_input() -> dict:
    return {
        "target_project_root": "/workspace/projects/optimus-prime",
        "earth_root": "/workspace/projects/Earth",
        "output_root": "/workspace/projects/optimus-prime/strategy/out",
        "revision_identity": "rev-req044-integration-r1",
        "strategy_goal": "Detect missing recommendation classes required by mission and ecosystem anchors before strategy promotion.",
        "call_id": "call-recommendation-omission-detector",
        "checked_at_utc": "2026-03-16T15:05:00Z",
        "target_project_evidence_refs": [
            "reports/optimus-prime/planning/evidence/TASK-156/TASK_EVIDENCE.json"
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
                    "reports/optimus-prime/planning/evidence/TASK-156/TASK_EVIDENCE.json"
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
                    "reports/optimus-prime/planning/evidence/TASK-156/TASK_EVIDENCE.json"
                ],
                "next_step": "Run deterministic contract checks and attach evidence packets.",
            },
            {
                "recommendation_id": "rec.runtime-sync-local",
                "recommendation_class_id": "class.runtime-sync",
                "summary": "Attempt runtime sync actions without cross-project obligation framing.",
                "rationale": "Local-only framing was attempted but misses the required shared obligation.",
                "recommendation_scope": "local",
                "project_id": "",
                "requires_earth_evidence": False,
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json"
                ],
                "next_step": "Reframe this class as a cross-project obligation.",
            },
        ],
    }


def test_req_044_integration_emits_complete_recommendation_fields_and_evidence_refs() -> None:
    payload = module.build_req_044_recommendation_omission_detector(**_base_input())

    assert module.validate_req_044_recommendation_omission_detector(payload) == []

    processing = payload["processing_behavior"]
    context_usage = processing["context_usage"]
    recommendation = processing["recommendation"]
    required_recommendation_keys = {
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "recommended_actions",
        "cross_project_obligations",
        "omitted_recommendation_classes",
        "open_risks",
    }
    assert set(recommendation.keys()) == required_recommendation_keys

    expected_evidence_refs = [
        "reports/earth/sweeps/2026-03-16/analytics-hub.json",
        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
        "reports/optimus-prime/planning/evidence/TASK-156/TASK_EVIDENCE.json",
    ]
    assert context_usage["evidence_refs_used"] == expected_evidence_refs
    assert recommendation["evidence_refs"] == expected_evidence_refs
    assert recommendation["decision"] == "resolve-strategy-gaps"
    assert recommendation["cross_project_obligations"] == []

    required_action_keys = {
        "recommendation_id",
        "class_id",
        "summary",
        "rationale",
        "next_step",
        "anchor_sources",
        "critical",
        "evidence_refs",
    }
    for row in recommendation["recommended_actions"]:
        assert set(row.keys()) == required_action_keys
        assert row["evidence_refs"]

    required_omission_keys = {
        "class_id",
        "anchor_sources",
        "required_scope",
        "project_id",
        "critical",
        "summary",
        "reason_code",
        "required_evidence_refs",
    }
    for row in recommendation["omitted_recommendation_classes"]:
        assert set(row.keys()) == required_omission_keys
        assert row["required_evidence_refs"]

    required_risk_keys = {"risk_id", "reason_code", "summary", "required_evidence_refs"}
    for row in recommendation["open_risks"]:
        assert set(row.keys()) == required_risk_keys
        assert row["required_evidence_refs"]

    assert set(payload["call_metadata"]["canonical_processing_input"].keys()) == {
        "mission_required_recommendation_classes",
        "ecosystem_required_recommendation_classes",
        "candidate_recommendations",
        "cross_project_context",
        "target_project_evidence_refs",
        "earth_sweep_evidence_refs",
    }


def test_req_044_integration_uses_cross_project_context_for_obligation_promotion() -> None:
    input_payload = _base_input()
    input_payload["candidate_recommendations"] = [
        input_payload["candidate_recommendations"][0],
        {
            "recommendation_id": "rec.runtime-sync",
            "recommendation_class_id": "class.runtime-sync",
            "summary": "Coordinate runtime replay synchronization with the runtime orchestrator project.",
            "rationale": "Mission requires a shared cross-project runtime synchronization obligation.",
            "recommendation_scope": "cross-project",
            "project_id": "runtime-orchestrator",
            "requires_earth_evidence": False,
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json"
            ],
            "next_step": "Open a runtime-orchestrator cross-project follow-up with earth evidence attached.",
        },
    ]
    payload = module.build_req_044_recommendation_omission_detector(**input_payload)

    assert module.validate_req_044_recommendation_omission_detector(payload) == []

    context_inputs = payload["processing_behavior"]["context_inputs"]
    context_usage = payload["processing_behavior"]["context_usage"]
    recommendation = payload["processing_behavior"]["recommendation"]
    obligation = recommendation["cross_project_obligations"][0]

    assert context_inputs["candidate_recommendations"][1]["requires_earth_evidence"] is True
    assert context_usage["local_only_plan_detected"] is False
    assert context_usage["cross_project_obligation_ids_emitted"] == ["obligation-class.runtime-sync"]
    assert recommendation["decision"] == "proceed-with-open-risks"
    assert [row["class_id"] for row in recommendation["omitted_recommendation_classes"]] == ["class.analytics-routing"]

    assert obligation["obligation_id"] == "obligation-class.runtime-sync"
    assert obligation["project_id"] == "runtime-orchestrator"
    assert obligation["anchor_sources"] == ["mission"]
    assert obligation["critical"] is True
    assert obligation["evidence_refs"] == ["reports/earth/sweeps/2026-03-16/runtime-orchestrator.json"]


def test_req_044_integration_blocks_cross_project_obligations_without_earth_sweep_evidence() -> None:
    input_payload = _base_input()
    input_payload["candidate_recommendations"] = [
        input_payload["candidate_recommendations"][0],
        {
            "recommendation_id": "rec.runtime-sync",
            "recommendation_class_id": "class.runtime-sync",
            "summary": "Coordinate runtime replay synchronization with the runtime orchestrator project.",
            "rationale": "Mission requires a shared cross-project runtime synchronization obligation.",
            "recommendation_scope": "cross-project",
            "project_id": "runtime-orchestrator",
            "requires_earth_evidence": False,
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json"
            ],
            "next_step": "Open a runtime-orchestrator cross-project follow-up with earth evidence attached.",
        },
    ]
    input_payload["earth_sweep_evidence_refs"] = []
    payload = module.build_req_044_recommendation_omission_detector(**input_payload)

    assert module.validate_req_044_recommendation_omission_detector(payload) == []

    recommendation = payload["processing_behavior"]["recommendation"]
    omitted = recommendation["omitted_recommendation_classes"]
    runtime_omission = next(row for row in omitted if row["class_id"] == "class.runtime-sync")

    assert recommendation["cross_project_obligations"] == []
    assert recommendation["decision"] == "resolve-strategy-gaps"
    assert runtime_omission["reason_code"] == "missing_earth_sweep_evidence_refs"

