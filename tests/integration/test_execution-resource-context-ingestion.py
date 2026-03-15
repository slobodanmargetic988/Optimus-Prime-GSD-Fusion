from scripts import strategy_context_sweep as module


def test_req_019_recommendation_is_complete_and_uses_cross_project_context() -> None:
    payload = module.build_req_019_execution_resource_context_ingestion(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req019-integration-r1",
        execution_resource_context={
            "hardware_profile": {
                "cpu_cores": 6,
                "memory_gb": 48,
                "gpu_count": 1,
                "storage_tier": "high-throughput",
                "evidence_refs": ["reports/runtime/hardware/profile-2026-03-15.json"],
            },
            "rate_limits": {
                "max_parallel_tasks": 2,
                "tokens_per_minute": 14000,
                "requests_per_minute": 120,
                "daily_token_budget": 50000,
                "evidence_refs": ["reports/runtime/rate-limits/policy-2026-03-15.json"],
            },
            "runtime_budget": {
                "max_execution_minutes": 4,
                "checkpoint_interval_minutes": 2,
                "evidence_refs": ["reports/runtime/budget/window-2026-03-15.json"],
            },
            "model_inventory": [
                {
                    "model_id": "gpt-5-mini",
                    "routing_tier": "fast",
                    "max_output_tokens": 8000,
                    "requests_per_minute_cap": 90,
                    "evidence_refs": ["reports/runtime/models/gpt-5-mini.json"],
                },
                {
                    "model_id": "gpt-5",
                    "routing_tier": "balanced",
                    "max_output_tokens": 16000,
                    "requests_per_minute_cap": 60,
                    "evidence_refs": ["reports/runtime/models/gpt-5.json"],
                },
                {
                    "model_id": "gpt-5-pro",
                    "routing_tier": "heavy",
                    "max_output_tokens": 32000,
                    "requests_per_minute_cap": 25,
                    "evidence_refs": ["reports/runtime/models/gpt-5-pro.json"],
                },
            ],
        },
        execution_candidates=[
            {
                "action_id": "action-resource-rebalance",
                "summary": "Rebalance execution lanes for shared runtime consumers.",
                "priority": "high",
                "complexity": "medium",
                "estimated_token_cost": 6000,
                "requires_gpu": False,
                "preferred_model_tier": "balanced",
                "evidence_refs": ["contracts/req/REQ-019_execution-resource-context-ingestion.md"],
                "next_step": "Coordinate routing changes before rollout.",
            },
            {
                "action_id": "action-runtime-audit",
                "summary": "Audit heavy runtime scans against shared GPU capacity.",
                "priority": "medium",
                "complexity": "high",
                "estimated_token_cost": 15000,
                "requires_gpu": True,
                "preferred_model_tier": "heavy",
                "evidence_refs": ["reports/planning/TASK-060/runtime-audit-inputs.json"],
                "next_step": "Schedule after the rebalance action is approved.",
            },
        ],
        earth_sweep_evidence_refs=["reports/earth/sweeps/2026-03-15/resource-portfolio.json"],
        cross_project_context=[
            {
                "project_id": "runtime-orchestrator",
                "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                "evidence_refs": ["reports/earth/sweeps/2026-03-15/runtime-orchestrator.json"],
                "context_note": "Shared rate-limit envelope for the runtime fleet.",
            }
        ],
    )

    assert module.validate_req_019_execution_resource_context_ingestion(payload) == []

    processing = payload["processing_behavior"]
    recommendation = processing["recommendation"]
    usage = processing["context_usage"]
    evidence_refs = recommendation["evidence_refs"]

    assert set(recommendation.keys()) == {
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "sequencing_policy_suggestions",
        "model_routing_policy_suggestions",
        "cross_project_context",
        "cross_project_obligations",
        "open_risks",
    }
    assert "contracts/req/REQ-019_execution-resource-context-ingestion.md" in evidence_refs
    assert "reports/earth/sweeps/2026-03-15/resource-portfolio.json" in evidence_refs
    assert "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json" in evidence_refs
    assert "reports/runtime/rate-limits/policy-2026-03-15.json" in evidence_refs

    assert usage["resource_context_used"] is True
    assert usage["earth_sweep_context_used"] is True
    assert usage["cross_project_context_used"] is True
    assert usage["cross_project_projects_considered"] == ["runtime-orchestrator"]
    assert usage["cross_project_projects_with_evidence_refs"] == ["runtime-orchestrator"]
    assert usage["cross_project_projects_without_evidence_refs"] == []

    assert recommendation["cross_project_context"] == {
        "cross_project": True,
        "projects_considered": ["runtime-orchestrator"],
        "projects_with_evidence_refs": ["runtime-orchestrator"],
        "projects_without_evidence_refs": [],
        "earth_sweep_evidence_refs": ["reports/earth/sweeps/2026-03-15/resource-portfolio.json"],
        "evidence_refs_by_project": {
            "runtime-orchestrator": ["reports/earth/sweeps/2026-03-15/runtime-orchestrator.json"]
        },
    }
    assert recommendation["cross_project_obligations"] == [
        {
            "obligation_id": "obligation-resource-runtime-orchestrator",
            "project_id": "runtime-orchestrator",
            "summary": (
                "Coordinate execution-resource sequencing and model-routing policy with "
                "'runtime-orchestrator' before shared execution."
            ),
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-15/resource-portfolio.json",
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
            ],
        }
    ]


def test_req_019_cross_project_context_without_earth_evidence_becomes_open_risk() -> None:
    payload = module.build_req_019_execution_resource_context_ingestion(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req019-integration-r2",
        execution_resource_context={
            "hardware_profile": {
                "cpu_cores": 8,
                "memory_gb": 64,
                "gpu_count": 0,
                "storage_tier": "standard",
                "evidence_refs": ["reports/runtime/hardware/profile-2026-03-15.json"],
            },
            "rate_limits": {
                "max_parallel_tasks": 3,
                "tokens_per_minute": 18000,
                "requests_per_minute": 120,
                "daily_token_budget": 64000,
                "evidence_refs": ["reports/runtime/rate-limits/policy-2026-03-15.json"],
            },
            "runtime_budget": {
                "max_execution_minutes": 4,
                "checkpoint_interval_minutes": 2,
                "evidence_refs": ["reports/runtime/budget/window-2026-03-15.json"],
            },
            "model_inventory": [
                {
                    "model_id": "gpt-5-mini",
                    "routing_tier": "fast",
                    "max_output_tokens": 8000,
                    "requests_per_minute_cap": 90,
                    "evidence_refs": ["reports/runtime/models/gpt-5-mini.json"],
                },
                {
                    "model_id": "gpt-5",
                    "routing_tier": "balanced",
                    "max_output_tokens": 16000,
                    "requests_per_minute_cap": 60,
                    "evidence_refs": ["reports/runtime/models/gpt-5.json"],
                },
            ],
        },
        execution_candidates=[
            {
                "action_id": "action-resource-rebalance",
                "summary": "Rebalance execution lanes for shared runtime consumers.",
                "priority": "high",
                "complexity": "medium",
                "estimated_token_cost": 6000,
                "requires_gpu": False,
                "preferred_model_tier": "balanced",
                "evidence_refs": ["contracts/req/REQ-019_execution-resource-context-ingestion.md"],
                "next_step": "Hold model-routing changes until Earth evidence is attached.",
            }
        ],
        earth_sweep_evidence_refs=[],
        cross_project_context=[
            {
                "project_id": "runtime-orchestrator",
                "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                "evidence_refs": ["reports/earth/sweeps/2026-03-15/runtime-orchestrator.json"],
                "context_note": "Shared rate-limit envelope for the runtime fleet.",
            }
        ],
    )

    assert module.validate_req_019_execution_resource_context_ingestion(payload) == []

    recommendation = payload["processing_behavior"]["recommendation"]
    assert recommendation["cross_project_obligations"] == []
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk-cross-project-earth-evidence-runtime-orchestrator",
            "reason_code": "missing_earth_sweep_evidence_refs",
            "summary": (
                "Cross-project execution-resource coordination for 'runtime-orchestrator' remains unresolved "
                "until Earth-sweep evidence refs are attached."
            ),
            "required_evidence_refs": ["reports/earth/sweeps/2026-03-15/runtime-orchestrator.json"],
        }
    ]


def test_req_019_validation_rejects_duplicate_cross_project_project_ids() -> None:
    payload = module.build_req_019_execution_resource_context_ingestion(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req019-integration-r3",
        execution_resource_context={
            "hardware_profile": {
                "cpu_cores": 6,
                "memory_gb": 48,
                "gpu_count": 1,
                "storage_tier": "high-throughput",
                "evidence_refs": ["reports/runtime/hardware/profile-2026-03-15.json"],
            },
            "rate_limits": {
                "max_parallel_tasks": 2,
                "tokens_per_minute": 14000,
                "requests_per_minute": 120,
                "daily_token_budget": 50000,
                "evidence_refs": ["reports/runtime/rate-limits/policy-2026-03-15.json"],
            },
            "runtime_budget": {
                "max_execution_minutes": 4,
                "checkpoint_interval_minutes": 2,
                "evidence_refs": ["reports/runtime/budget/window-2026-03-15.json"],
            },
            "model_inventory": [
                {
                    "model_id": "gpt-5-mini",
                    "routing_tier": "fast",
                    "max_output_tokens": 8000,
                    "requests_per_minute_cap": 90,
                    "evidence_refs": ["reports/runtime/models/gpt-5-mini.json"],
                },
                {
                    "model_id": "gpt-5",
                    "routing_tier": "balanced",
                    "max_output_tokens": 16000,
                    "requests_per_minute_cap": 60,
                    "evidence_refs": ["reports/runtime/models/gpt-5.json"],
                },
            ],
        },
        execution_candidates=[
            {
                "action_id": "action-resource-rebalance",
                "summary": "Rebalance execution lanes for shared runtime consumers.",
                "priority": "high",
                "complexity": "medium",
                "estimated_token_cost": 6000,
                "requires_gpu": False,
                "preferred_model_tier": "balanced",
                "evidence_refs": ["contracts/req/REQ-019_execution-resource-context-ingestion.md"],
                "next_step": "Coordinate routing changes before rollout.",
            }
        ],
        earth_sweep_evidence_refs=["reports/earth/sweeps/2026-03-15/resource-portfolio.json"],
        cross_project_context=[
            {
                "project_id": "runtime-orchestrator",
                "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                "evidence_refs": ["reports/earth/sweeps/2026-03-15/runtime-orchestrator.json"],
                "context_note": "Shared rate-limit envelope for the runtime fleet.",
            }
        ],
    )

    duplicate = dict(payload["processing_behavior"]["context_inputs"]["broad_sweep_context"]["cross_project_context"][0])
    duplicate["project_root"] = "/workspace/projects/Earth/runtime-orchestrator-shadow"
    duplicate["evidence_refs"] = ["reports/earth/sweeps/2026-03-15/runtime-orchestrator-shadow.json"]
    payload["processing_behavior"]["context_inputs"]["broad_sweep_context"]["cross_project_context"].append(duplicate)

    assert module.validate_req_019_execution_resource_context_ingestion(payload) == [
        "cross_project_context[1].project_id must be unique"
    ]
