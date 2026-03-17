from scripts import strategy_llm_pipeline as module


def _base_input() -> dict:
    return {
        "target_project_root": "/workspace/projects/optimus-prime",
        "earth_root": "/workspace/projects/Earth",
        "output_root": "/workspace/projects/optimus-prime/strategy/out",
        "revision_identity": "rev-req031-integration-r1",
        "strategy_goal": "Estimate call-6 KPI impact from replay-stable recommendation adoption inputs.",
        "call_id": "call-6",
        "checked_at_utc": "2026-03-16T14:20:00Z",
        "call_chain": [
            {
                "sequence": 1,
                "call_id": "call-1",
                "phase": "analysis",
                "output_ref": "REQ-031::call::call-1::output::situational_analysis",
            },
            {
                "sequence": 2,
                "call_id": "call-2",
                "phase": "planning",
                "output_ref": "REQ-031::call::call-2::output::execution_plan",
            },
            {
                "sequence": 3,
                "call_id": "call-3",
                "phase": "validation",
                "output_ref": "REQ-031::call::call-3::output::evidence_validation",
            },
            {
                "sequence": 4,
                "call_id": "call-4",
                "phase": "synthesis",
                "output_ref": "REQ-031::call::call-4::output::recommendation_synthesis",
            },
            {
                "sequence": 5,
                "call_id": "call-5",
                "phase": "sequencing",
                "output_ref": "REQ-031::call::call-5::output::lane_design_reasoning",
            },
            {
                "sequence": 6,
                "call_id": "call-6",
                "phase": "kpi-impact-estimation",
                "output_ref": "REQ-031::call::call-6::output::kpi_impact_estimation",
            },
        ],
        "target_project_evidence_refs": [
            "reports/optimus-prime/planning/evidence/TASK-105/TASK_EVIDENCE.json",
            "reports/optimus-prime/planning/evidence/TASK-102/TASK_EVIDENCE.json",
        ],
        "earth_sweep_evidence_refs": [
            "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
        ],
        "recommendation_adoptions": [
            {
                "recommendation_id": "rec.runtime-sync",
                "summary": "Adopt the cross-project runtime replay sync after local proof lands.",
                "adoption_status": "conditional",
                "adoption_window": "next wave",
                "project_id": "runtime-orchestrator",
                "requires_earth_evidence": True,
                "evidence_refs": [
                    "REQ-031::call::call-5::output::lane_design_reasoning",
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                ],
            },
            {
                "recommendation_id": "rec.local-determinism",
                "summary": "Keep deterministic replay diagnostics on the committed branch head.",
                "adoption_status": "planned",
                "adoption_window": "this wave",
                "project_id": "",
                "requires_earth_evidence": False,
                "evidence_refs": [
                    "REQ-031::call::call-5::output::lane_design_reasoning",
                    "reports/optimus-prime/planning/evidence/TASK-102/TASK_EVIDENCE.json",
                ],
            },
        ],
        "kpi_definitions": [
            {
                "kpi_id": "kpi.replay-failure-rate",
                "kpi_name": "Replay Failure Rate",
                "baseline_value": 0.12,
                "unit": "ratio",
                "desired_direction": "decrease",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-102/TASK_EVIDENCE.json",
                ],
            },
            {
                "kpi_id": "kpi.mean-time-to-diagnose",
                "kpi_name": "Mean Time To Diagnose",
                "baseline_value": 75.0,
                "unit": "minutes",
                "desired_direction": "decrease",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-105/TASK_EVIDENCE.json",
                ],
            },
        ],
        "impact_assumptions": [
            {
                "recommendation_id": "rec.runtime-sync",
                "kpi_id": "kpi.replay-failure-rate",
                "expected_movement_lower": -0.03,
                "expected_movement_upper": -0.01,
                "reasoning_summary": "Cross-project runtime alignment should remove a smaller class of replay mismatches.",
                "confidence": "low",
                "caveats": [
                    "Runtime-orchestrator adoption remains conditional on fresh earth evidence.",
                ],
                "evidence_backed_assumptions": [
                    "Lane 2 adoption stays aligned with the latest runtime-orchestrator sweep.",
                ],
                "evidence_refs": [
                    "REQ-031::call::call-5::output::lane_design_reasoning",
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                ],
            },
            {
                "recommendation_id": "rec.local-determinism",
                "kpi_id": "kpi.mean-time-to-diagnose",
                "expected_movement_lower": -15.0,
                "expected_movement_upper": -8.0,
                "reasoning_summary": "Committed deterministic diagnostics should shorten branch-head failure triage.",
                "confidence": "medium",
                "caveats": [
                    "Savings depend on keeping evidence packets attached to reruns.",
                ],
                "evidence_backed_assumptions": [
                    "Investigators continue to rely on branch-head trace artifacts for diagnosis.",
                ],
                "evidence_refs": [
                    "REQ-031::call::call-5::output::lane_design_reasoning",
                    "reports/optimus-prime/planning/evidence/TASK-105/TASK_EVIDENCE.json",
                ],
            },
            {
                "recommendation_id": "rec.local-determinism",
                "kpi_id": "kpi.replay-failure-rate",
                "expected_movement_lower": -0.04,
                "expected_movement_upper": -0.02,
                "reasoning_summary": "Local deterministic hardening should remove a larger share of replay failures.",
                "confidence": "high",
                "caveats": [
                    "The estimate assumes no new non-deterministic runtime inputs land mid-wave.",
                ],
                "evidence_backed_assumptions": [
                    "Branch-head diagnostics remain replay-stable across repeated smoke and integration runs.",
                ],
                "evidence_refs": [
                    "REQ-031::call::call-5::output::lane_design_reasoning",
                    "reports/optimus-prime/planning/evidence/TASK-102/TASK_EVIDENCE.json",
                ],
            },
        ],
    }


def test_req_031_integration_emits_trace_rows_and_structured_kpi_estimates() -> None:
    payload = module.build_req_031_call_6_kpi_impact_estimation_reasoning(**_base_input())

    assert module.validate_req_031_call_6_kpi_impact_estimation_reasoning(payload) == []

    estimation = payload["processing_behavior"]["kpi_impact_estimation"]
    estimates = estimation["kpi_estimates"]
    trace_rows = payload["call_metadata"]["llm_call_trace_rows"]

    assert estimation["decision"] == "proceed"
    assert [row["estimate_id"] for row in estimates] == [
        "estimate::rec.local-determinism::kpi.mean-time-to-diagnose",
        "estimate::rec.local-determinism::kpi.replay-failure-rate",
        "estimate::rec.runtime-sync::kpi.replay-failure-rate",
    ]
    assert estimates[0]["estimated_post_adoption_range"] == {"lower": 60.0, "upper": 67.0}
    assert estimates[-1]["confidence"] == "low"
    assert trace_rows[-1]["call_id"] == "call-6"
    assert trace_rows[-1]["call_objective"] == module.REQ_031_CALL_OBJECTIVES["call-6"]
    assert trace_rows[-1]["input_refs"] == [
        "REQ-031::call::call-1::output::situational_analysis",
        "REQ-031::call::call-2::output::execution_plan",
        "REQ-031::call::call-3::output::evidence_validation",
        "REQ-031::call::call-4::output::recommendation_synthesis",
        "REQ-031::call::call-5::output::lane_design_reasoning",
        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
        "reports/optimus-prime/planning/evidence/TASK-102/TASK_EVIDENCE.json",
        "reports/optimus-prime/planning/evidence/TASK-105/TASK_EVIDENCE.json",
    ]
    assert trace_rows[-1]["handoff_summary"] == (
        "Call 6 emits kpi_estimates via REQ-031::call::call-6::output::kpi_impact_estimation "
        "for 3 recommendation/KPI pair(s)."
    )
    assert len(trace_rows) == 6


def test_req_031_integration_replay_is_stable_across_input_order_changes() -> None:
    first = module.build_req_031_call_6_kpi_impact_estimation_reasoning(**_base_input())

    second_input = _base_input()
    second_input["recommendation_adoptions"] = list(reversed(second_input["recommendation_adoptions"]))
    second_input["kpi_definitions"] = list(reversed(second_input["kpi_definitions"]))
    second_input["impact_assumptions"] = list(reversed(second_input["impact_assumptions"]))
    second = module.build_req_031_call_6_kpi_impact_estimation_reasoning(**second_input)

    assert module.validate_req_031_call_6_kpi_impact_estimation_reasoning(first) == []
    assert module.validate_req_031_call_6_kpi_impact_estimation_reasoning(second) == []
    assert (
        first["call_metadata"]["canonical_processing_input"]
        == second["call_metadata"]["canonical_processing_input"]
    )
    assert first["call_metadata"]["processing_input_sha256"] == second["call_metadata"]["processing_input_sha256"]
    assert first["call_metadata"]["llm_call_trace_rows"] == second["call_metadata"]["llm_call_trace_rows"]
    assert (
        first["processing_behavior"]["context_usage"]["estimate_ids_emitted"]
        == second["processing_behavior"]["context_usage"]["estimate_ids_emitted"]
        == [
            "estimate::rec.local-determinism::kpi.mean-time-to-diagnose",
            "estimate::rec.local-determinism::kpi.replay-failure-rate",
            "estimate::rec.runtime-sync::kpi.replay-failure-rate",
        ]
    )
