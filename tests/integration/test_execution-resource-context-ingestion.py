from scripts import strategy_context_sweep as module


def test_req_019_resource_constraints_prioritize_low_intensity_and_balanced_model_routes() -> None:
    payload = module.build_req_019_execution_resource_context_ingestion(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req019-integration-r1",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-061/TASK_EVIDENCE.json",
        ],
        earth_sweep_evidence_refs=[
            "reports/earth/sweeps/2026-03-15/portfolio.json",
        ],
        candidate_recommendations=[
            {
                "action_id": "action-low",
                "summary": "Run low-cost consistency check.",
                "rationale": "Establish baseline before deep reasoning.",
                "action_scope": "local",
                "requires_earth_evidence": False,
                "project_id": "",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-061/TASK_EVIDENCE.json",
                ],
                "next_step": "Execute low-cost check first.",
                "resource_intensity": "low",
                "estimated_tokens": 12000,
            },
            {
                "action_id": "action-high",
                "summary": "Run deep reasoning lane after baseline.",
                "rationale": "Needs larger token budget and stronger routing policy.",
                "action_scope": "local",
                "requires_earth_evidence": False,
                "project_id": "",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/portfolio.json",
                ],
                "next_step": "Execute deep lane after low-cost gate.",
                "resource_intensity": "high",
                "estimated_tokens": 140000,
            },
        ],
        execution_resource_context={
            "hardware_profiles": [
                {"profile_id": "cpu-only", "cpu_cores": 12, "memory_gb": 48, "gpu_count": 0}
            ],
            "rate_limit_windows": [
                {
                    "provider": "openai",
                    "model": "gpt-5",
                    "requests_per_minute": 30,
                    "tokens_per_minute": 90000,
                }
            ],
            "model_catalog": [
                {"model_id": "gpt-5", "reasoning_tier": "high"},
                {"model_id": "gpt-5-balanced", "reasoning_tier": "balanced"},
                {"model_id": "gpt-5-mini", "reasoning_tier": "light"},
            ],
            "runtime_budget": {"max_parallel_actions": 3, "max_daily_tokens": 900000},
        },
    )

    assert module.validate_req_019_execution_resource_context_ingestion(payload) == []
    sequencing = payload["resource_policy"]["sequencing_policy_suggestions"]
    assert sequencing["ordered_action_ids"] == ["action-low", "action-high"]
    assert sequencing["max_parallel_actions"] == 1
    assert sequencing["reason_codes"] == [
        "cpu_only_execution_context",
        "tight_rate_limit_parallelism_reduced",
    ]

    by_action = {
        row["action_id"]: row for row in payload["resource_policy"]["model_routing_policy_suggestions"]
    }
    assert by_action["action-low"]["selected_model"] == "gpt-5-mini"
    assert by_action["action-high"]["selected_model"] == "gpt-5-balanced"
    assert "rate_limit_tight_route_to_balanced_model" in by_action["action-high"]["reason_codes"]


def test_req_019_relaxed_resource_context_allows_parallel_and_high_tier_routes() -> None:
    payload = module.build_req_019_execution_resource_context_ingestion(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req019-integration-r2",
        candidate_recommendations=[
            {
                "action_id": "action-high",
                "summary": "Run deep reasoning lane.",
                "rationale": "High-tier model route is available and affordable.",
                "action_scope": "local",
                "requires_earth_evidence": False,
                "project_id": "",
                "evidence_refs": [],
                "next_step": "Run deep lane now.",
                "resource_intensity": "high",
                "estimated_tokens": 80000,
            },
            {
                "action_id": "action-medium",
                "summary": "Run medium complexity analysis lane.",
                "rationale": "Balanced model route is enough for this step.",
                "action_scope": "local",
                "requires_earth_evidence": False,
                "project_id": "",
                "evidence_refs": [],
                "next_step": "Run medium lane in parallel.",
                "resource_intensity": "medium",
                "estimated_tokens": 30000,
            },
        ],
        execution_resource_context={
            "hardware_profiles": [
                {"profile_id": "gpu-enabled", "cpu_cores": 24, "memory_gb": 96, "gpu_count": 2}
            ],
            "rate_limit_windows": [
                {
                    "provider": "openai",
                    "model": "gpt-5",
                    "requests_per_minute": 100,
                    "tokens_per_minute": 500000,
                }
            ],
            "model_catalog": [
                {"model_id": "gpt-5", "reasoning_tier": "high"},
                {"model_id": "gpt-5-balanced", "reasoning_tier": "balanced"},
                {"model_id": "gpt-5-mini", "reasoning_tier": "light"},
            ],
            "runtime_budget": {"max_parallel_actions": 4, "max_daily_tokens": 2000000},
        },
    )

    assert module.validate_req_019_execution_resource_context_ingestion(payload) == []
    sequencing = payload["resource_policy"]["sequencing_policy_suggestions"]
    assert sequencing["ordered_action_ids"] == ["action-high", "action-medium"]
    assert sequencing["max_parallel_actions"] == 4
    assert sequencing["reason_codes"] == ["resource_context_ready"]

    by_action = {
        row["action_id"]: row for row in payload["resource_policy"]["model_routing_policy_suggestions"]
    }
    assert by_action["action-high"]["selected_model"] == "gpt-5"
    assert by_action["action-medium"]["selected_model"] == "gpt-5-balanced"
