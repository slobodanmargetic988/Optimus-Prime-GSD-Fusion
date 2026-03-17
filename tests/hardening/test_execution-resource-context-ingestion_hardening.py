import json

from scripts import strategy_context_sweep as module


def test_req_019_hardening_stale_source_artifact_detected_during_earth_sweep() -> None:
    payload = module.build_req_019_execution_resource_context_ingestion(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req019-hardening-r1",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-061/TASK_EVIDENCE.json"
        ],
        earth_sweep_source_artifacts=[
            {
                "artifact_ref": "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                "status": "stale",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.audit.json"
                ],
            }
        ],
        candidate_recommendations=[
            {
                "action_id": "action-local-hardening",
                "summary": "Keep hardening checks running while stale source is refreshed.",
                "rationale": "Local checks can continue with explicit stale-source risk tracking.",
                "action_scope": "local",
                "requires_earth_evidence": False,
                "project_id": "",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-061/TASK_EVIDENCE.json"
                ],
                "next_step": "Continue hardening and annotate stale-source reason code.",
                "resource_intensity": "low",
                "estimated_tokens": 10000,
            }
        ],
        execution_resource_context={
            "hardware_profiles": [{"profile_id": "cpu-only", "cpu_cores": 8, "memory_gb": 32, "gpu_count": 0}],
            "rate_limit_windows": [
                {
                    "provider": "openai",
                    "model": "gpt-5",
                    "requests_per_minute": 30,
                    "tokens_per_minute": 120000,
                }
            ],
            "model_catalog": [
                {"model_id": "gpt-5-balanced", "reasoning_tier": "balanced"},
                {"model_id": "gpt-5-mini", "reasoning_tier": "light"},
            ],
            "runtime_budget": {"max_parallel_actions": 2, "max_daily_tokens": 1000000},
        },
    )

    assert module.validate_req_019_execution_resource_context_ingestion(payload) == []
    open_risks = payload["processing_behavior"]["recommendation"]["open_risks"]
    stale_rows = [row for row in open_risks if row["reason_code"] == "stale_earth_sweep_source_artifact"]
    assert len(stale_rows) == 1
    assert stale_rows[0]["required_evidence_refs"] == [
        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.audit.json",
        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
    ]
    assert "stale_earth_sweep_source_artifact_detected" in payload["resource_policy"]["sequencing_policy_suggestions"][
        "reason_codes"
    ]


def test_req_019_hardening_missing_mission_scope_or_peer_project_doc_with_reason_codes() -> None:
    payload = module.build_req_019_execution_resource_context_ingestion(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req019-hardening-r2",
        required_context_documents=[
            {
                "doc_kind": "mission",
                "doc_ref": "mission.md",
                "status": "missing",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-061/TASK_EVIDENCE.json"
                ],
            },
            {
                "doc_kind": "scope",
                "doc_ref": "scope.md",
                "status": "missing",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-061/TASK_EVIDENCE.json"
                ],
            },
            {
                "doc_kind": "peer-project",
                "project_id": "runtime-orchestrator",
                "doc_ref": "docs/runtime-orchestrator/overview.md",
                "status": "missing",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json"
                ],
            },
        ],
        execution_resource_context={
            "hardware_profiles": [{"profile_id": "cpu-only", "cpu_cores": 8, "memory_gb": 32, "gpu_count": 0}],
            "rate_limit_windows": [
                {
                    "provider": "openai",
                    "model": "gpt-5",
                    "requests_per_minute": 20,
                    "tokens_per_minute": 90000,
                }
            ],
            "model_catalog": [
                {"model_id": "gpt-5-balanced", "reasoning_tier": "balanced"},
                {"model_id": "gpt-5-mini", "reasoning_tier": "light"},
            ],
            "runtime_budget": {"max_parallel_actions": 2, "max_daily_tokens": 1000000},
        },
    )

    assert module.validate_req_019_execution_resource_context_ingestion(payload) == []
    open_risks = payload["processing_behavior"]["recommendation"]["open_risks"]
    assert sorted(row["reason_code"] for row in open_risks) == [
        "missing_mission_doc",
        "missing_peer_project_doc",
        "missing_scope_doc",
    ]
    for row in open_risks:
        assert row["required_evidence_refs"]
    assert "required_context_document_missing" in payload["resource_policy"]["sequencing_policy_suggestions"][
        "reason_codes"
    ]


def test_req_019_hardening_context_bundle_serialization_replay_stable_across_repeated_runs() -> None:
    first = module.build_req_019_execution_resource_context_ingestion(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req019-hardening-r3",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-061/TASK_EVIDENCE.json",
            "reports/optimus-prime/planning/evidence/TASK-061/TASK_EVIDENCE.json",
        ],
        candidate_recommendations=[
            {
                "action_id": "action-alpha",
                "summary": "Action alpha",
                "rationale": "Alpha rationale",
                "action_scope": "local",
                "requires_earth_evidence": False,
                "project_id": "",
                "evidence_refs": ["reports/optimus-prime/planning/evidence/TASK-061/TASK_EVIDENCE.json"],
                "next_step": "Run alpha.",
                "resource_intensity": "low",
                "estimated_tokens": 10000,
            },
            {
                "action_id": "action-beta",
                "summary": "Action beta",
                "rationale": "Beta rationale",
                "action_scope": "local",
                "requires_earth_evidence": False,
                "project_id": "",
                "evidence_refs": [],
                "next_step": "Run beta.",
                "resource_intensity": "high",
                "estimated_tokens": 20000,
            },
        ],
        execution_resource_context={
            "hardware_profiles": [
                {"profile_id": "gpu", "cpu_cores": 12, "memory_gb": 64, "gpu_count": 1}
            ],
            "rate_limit_windows": [
                {
                    "provider": "openai",
                    "model": "gpt-5",
                    "requests_per_minute": 60,
                    "tokens_per_minute": 250000,
                }
            ],
            "model_catalog": [
                {"model_id": "gpt-5-mini", "reasoning_tier": "light"},
                {"model_id": "gpt-5", "reasoning_tier": "high"},
                {"model_id": "gpt-5-balanced", "reasoning_tier": "balanced"},
            ],
            "runtime_budget": {"max_parallel_actions": 3, "max_daily_tokens": 1200000},
        },
    )

    second = module.build_req_019_execution_resource_context_ingestion(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req019-hardening-r3",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-061/TASK_EVIDENCE.json"
        ],
        candidate_recommendations=[
            {
                "action_id": "action-beta",
                "summary": "Action beta",
                "rationale": "Beta rationale",
                "action_scope": "local",
                "requires_earth_evidence": False,
                "project_id": "",
                "evidence_refs": [],
                "next_step": "Run beta.",
                "resource_intensity": "high",
                "estimated_tokens": 20000,
            },
            {
                "action_id": "action-alpha",
                "summary": "Action alpha",
                "rationale": "Alpha rationale",
                "action_scope": "local",
                "requires_earth_evidence": False,
                "project_id": "",
                "evidence_refs": ["reports/optimus-prime/planning/evidence/TASK-061/TASK_EVIDENCE.json"],
                "next_step": "Run alpha.",
                "resource_intensity": "low",
                "estimated_tokens": 10000,
            },
        ],
        execution_resource_context={
            "hardware_profiles": [
                {"profile_id": "gpu", "cpu_cores": 12, "memory_gb": 64, "gpu_count": 1}
            ],
            "rate_limit_windows": [
                {
                    "provider": "openai",
                    "model": "gpt-5",
                    "requests_per_minute": 60,
                    "tokens_per_minute": 250000,
                }
            ],
            "model_catalog": [
                {"model_id": "gpt-5", "reasoning_tier": "high"},
                {"model_id": "gpt-5-balanced", "reasoning_tier": "balanced"},
                {"model_id": "gpt-5-mini", "reasoning_tier": "light"},
            ],
            "runtime_budget": {"max_parallel_actions": 3, "max_daily_tokens": 1200000},
        },
    )

    assert module.validate_req_019_execution_resource_context_ingestion(first) == []
    assert module.validate_req_019_execution_resource_context_ingestion(second) == []
    assert first["call_metadata"]["canonical_processing_input"] == second["call_metadata"]["canonical_processing_input"]
    assert first["call_metadata"]["processing_input_sha256"] == second["call_metadata"]["processing_input_sha256"]
    assert first["context_bundle"]["canonical_json"] == second["context_bundle"]["canonical_json"]
    assert first["context_bundle"]["sha256"] == second["context_bundle"]["sha256"]

    parsed = json.loads(first["context_bundle"]["canonical_json"])
    canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    assert first["context_bundle"]["canonical_json"] == canonical
