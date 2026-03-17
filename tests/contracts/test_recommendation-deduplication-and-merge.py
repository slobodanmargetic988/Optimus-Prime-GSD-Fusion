import json
from pathlib import Path

import pytest

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "recommendation-deduplication-and-merge.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-037_recommendation-deduplication-and-merge.sample.json"
)
CONTRACT_DOC_PATH = REPO_ROOT / "contracts" / "req" / "REQ-037_recommendation-deduplication-and-merge.md"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_037_merges_duplicate_recommendation_drafts_preserving_rationale_and_evidence() -> None:
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_037_recommendation_deduplication_and_merge(
        target_project_root=fixture["target_project_root"],
        earth_root=fixture["earth_root"],
        output_root=fixture["output_root"],
        revision_identity=fixture["revision_identity"],
        target_project_evidence_refs=fixture["target_project_evidence_refs"],
        earth_sweep_evidence_refs=fixture["earth_sweep_evidence_refs"],
        cross_project_context=fixture["cross_project_context"],
        recommendation_drafts=fixture["recommendation_drafts"],
        merged_at="2026-03-16T12:00:00Z",
    )

    assert module.validate_req_037_recommendation_deduplication_and_merge(payload) == []
    assert set(payload.keys()) == {
        "requirement_id",
        "surface",
        "schema_version",
        "recommendation_deduplication_and_merge_entrypoint",
        "processing_behavior",
        "call_metadata",
        "merged_at",
        "deduplication_index",
        "merged_recommendations",
        "evidence_refs",
        "summary",
    }
    assert payload["requirement_id"] == "REQ-037"
    assert payload["surface"] == "recommendation_deduplication_and_merge"
    assert payload["schema_version"] == "req-037.recommendation-deduplication-and-merge.v1"
    assert payload["recommendation_deduplication_and_merge_entrypoint"] == {
        "runtime_mode": "llm-first",
        "execution_mode": "long-thinking",
        "target_project_root": fixture["target_project_root"],
        "earth_root": fixture["earth_root"],
        "output_root": fixture["output_root"],
        "revision_identity": fixture["revision_identity"],
        "merged_at": "2026-03-16T12:00:00Z",
    }
    assert payload["deduplication_index"] == {
        "input_draft_count": 3,
        "merged_recommendation_count": 2,
        "duplicate_group_count": 1,
        "recommendation_ids": [
            "rec.runtime-bridge-alignment",
            "rec.trace-citation-discipline",
        ],
        "semantic_signatures": [
            "runtime-bridge-alignment",
            "trace-citation-discipline",
        ],
    }
    assert payload["call_metadata"] == {
        "reproducibility": "deterministic-input-fingerprint",
        "canonical_input_sha256": "cce4a434cf1302eeb3b621ae7c8a9ef81b0488cc6cc97dd906a36f6fffc25eff",
        "reproducible_call_id": "req037-cce4a434cf1302ee",
        "canonical_input": {
            "runtime_mode": "llm-first",
            "execution_mode": "long-thinking",
            "target_project_root": fixture["target_project_root"],
            "earth_root": fixture["earth_root"],
            "output_root": fixture["output_root"],
            "revision_identity": fixture["revision_identity"],
            "merged_at": "2026-03-16T12:00:00Z",
        },
        "processing_input_sha256": "59d82eb0a4b05d17b0b5e6b55fe0d614315cbf3295ef2d35bab1903701cd10b5",
        "processing_call_id": "req037-processing-59d82eb0a4b05d17",
        "canonical_processing_input": {
            "target_project_evidence_refs": fixture["target_project_evidence_refs"],
            "earth_sweep_evidence_refs": fixture["earth_sweep_evidence_refs"],
            "cross_project_context": fixture["cross_project_context"],
            "recommendation_drafts": [
                {
                    "draft_id": "draft-earth-runtime-001",
                    "recommendation_id": "rec.runtime-bridge-alignment",
                    "semantic_signature": "runtime-bridge-alignment",
                    "summary": "Align runtime bridge assumptions before planner promotion.",
                    "rationale": "Earth sweep evidence shows the runtime bridge is already shared across planning packets.",
                    "action_scope": "cross-project",
                    "requires_earth_evidence": True,
                    "project_id": "runtime-orchestrator",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                        "strategy/current/samples/REQ-025_multi-call-strategy-pipeline-planner.sample.json",
                    ],
                    "next_step": "Merge the runtime alignment recommendation under one stable ID before promotion.",
                },
                {
                    "draft_id": "draft-local-runtime-002",
                    "recommendation_id": "rec.runtime-bridge-alignment",
                    "semantic_signature": "runtime-bridge-alignment",
                    "summary": "Align planner promotion with shared runtime bridge assumptions.",
                    "rationale": "Local planner traces show the same action already exists under the stable recommendation ID.",
                    "action_scope": "cross-project",
                    "requires_earth_evidence": True,
                    "project_id": "runtime-orchestrator",
                    "evidence_refs": [
                        "reports/optimus-prime/planning/evidence/TASK-127/TASK_EVIDENCE.json",
                        "strategy/current/llm_call_trace.jsonl",
                    ],
                    "next_step": "Retain Earth-backed runtime citations when duplicate drafts are merged.",
                },
                {
                    "draft_id": "draft-local-trace-003",
                    "recommendation_id": "rec.trace-citation-discipline",
                    "semantic_signature": "trace-citation-discipline",
                    "summary": "Keep merged recommendations citation-complete.",
                    "rationale": "Merged recommendation output must retain per-source rationale and evidence links for replay.",
                    "action_scope": "local",
                    "requires_earth_evidence": False,
                    "project_id": "",
                    "evidence_refs": [
                        "contracts/req/REQ-025_multi-call-strategy-pipeline-planner.md",
                    ],
                    "next_step": "Keep evidence refs and source rationales replay-stable in the merged output.",
                },
            ],
        },
        "llm_call_trace_schema_version": "req-025.llm-call-trace-row.v1",
        "llm_call_trace_path": "strategy/current/llm_call_trace.jsonl",
        "llm_call_trace_sha256": "87de381b167620cc601b2a635ba5ed468692fbe25d9b5ebc4087a27f1473e826",
        "llm_call_trace_rows": [
            {
                "schema_version": "req-025.llm-call-trace-row.v1",
                "requirement_id": "REQ-037",
                "plan_id": "req037-plan-59d82eb0a4b05d17",
                "processing_call_id": "req037-processing-59d82eb0a4b05d17",
                "call_id": "req037-call-01-978d919bbe",
                "sequence": 1,
                "call_objective": "Merge recommendation draft draft-earth-runtime-001 into stable recommendation rec.runtime-bridge-alignment while preserving rationale, evidence refs, and semantic signature runtime-bridge-alignment.",
                "depends_on": [],
                "expected_output": "recommendation_merge_state_01_rec-runtime-bridge-alignment_draft-earth-runtime-001",
                "input_refs": [
                    "reports/earth/sweeps/2026-03-15/portfolio.json",
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                    "reports/optimus-prime/planning/evidence/TASK-127/TASK_EVIDENCE.json",
                    "strategy/current/samples/REQ-025_multi-call-strategy-pipeline-planner.sample.json",
                ],
                "output_refs": [
                    "req037-plan-59d82eb0a4b05d17::call::req037-call-01-978d919bbe::output::recommendation_merge_state_01_rec-runtime-bridge-alignment_draft-earth-runtime-001",
                ],
                "handoff_summary": "Call 1 hands off draft draft-earth-runtime-001 for rec.runtime-bridge-alignment via req037-plan-59d82eb0a4b05d17::call::req037-call-01-978d919bbe::output::recommendation_merge_state_01_rec-runtime-bridge-alignment_draft-earth-runtime-001 to req037-call-02-43890b102e after consuming 4 input refs.",
            },
            {
                "schema_version": "req-025.llm-call-trace-row.v1",
                "requirement_id": "REQ-037",
                "plan_id": "req037-plan-59d82eb0a4b05d17",
                "processing_call_id": "req037-processing-59d82eb0a4b05d17",
                "call_id": "req037-call-02-43890b102e",
                "sequence": 2,
                "call_objective": "Merge recommendation draft draft-local-runtime-002 into stable recommendation rec.runtime-bridge-alignment while preserving rationale, evidence refs, and semantic signature runtime-bridge-alignment.",
                "depends_on": [
                    "req037-call-01-978d919bbe",
                ],
                "expected_output": "recommendation_merge_state_02_rec-runtime-bridge-alignment_draft-local-runtime-002",
                "input_refs": [
                    "reports/earth/sweeps/2026-03-15/portfolio.json",
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                    "reports/optimus-prime/planning/evidence/TASK-127/TASK_EVIDENCE.json",
                    "req037-plan-59d82eb0a4b05d17::call::req037-call-01-978d919bbe::output::recommendation_merge_state_01_rec-runtime-bridge-alignment_draft-earth-runtime-001",
                    "strategy/current/llm_call_trace.jsonl",
                ],
                "output_refs": [
                    "req037-plan-59d82eb0a4b05d17::call::req037-call-02-43890b102e::output::recommendation_merge_state_02_rec-runtime-bridge-alignment_draft-local-runtime-002",
                ],
                "handoff_summary": "Call 2 hands off draft draft-local-runtime-002 for rec.runtime-bridge-alignment via req037-plan-59d82eb0a4b05d17::call::req037-call-02-43890b102e::output::recommendation_merge_state_02_rec-runtime-bridge-alignment_draft-local-runtime-002 to req037-call-03-0343daff06 after consuming 5 input refs.",
            },
            {
                "schema_version": "req-025.llm-call-trace-row.v1",
                "requirement_id": "REQ-037",
                "plan_id": "req037-plan-59d82eb0a4b05d17",
                "processing_call_id": "req037-processing-59d82eb0a4b05d17",
                "call_id": "req037-call-03-0343daff06",
                "sequence": 3,
                "call_objective": "Merge recommendation draft draft-local-trace-003 into stable recommendation rec.trace-citation-discipline while preserving rationale, evidence refs, and semantic signature trace-citation-discipline.",
                "depends_on": [
                    "req037-call-02-43890b102e",
                ],
                "expected_output": "recommendation_merge_state_03_rec-trace-citation-discipline_draft-local-trace-003",
                "input_refs": [
                    "contracts/req/REQ-025_multi-call-strategy-pipeline-planner.md",
                    "reports/earth/sweeps/2026-03-15/portfolio.json",
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                    "reports/optimus-prime/planning/evidence/TASK-127/TASK_EVIDENCE.json",
                    "req037-plan-59d82eb0a4b05d17::call::req037-call-02-43890b102e::output::recommendation_merge_state_02_rec-runtime-bridge-alignment_draft-local-runtime-002",
                ],
                "output_refs": [
                    "req037-plan-59d82eb0a4b05d17::call::req037-call-03-0343daff06::output::recommendation_merge_state_03_rec-trace-citation-discipline_draft-local-trace-003",
                ],
                "handoff_summary": "Call 3 hands off draft draft-local-trace-003 for rec.trace-citation-discipline via req037-plan-59d82eb0a4b05d17::call::req037-call-03-0343daff06::output::recommendation_merge_state_03_rec-trace-citation-discipline_draft-local-trace-003 as the terminal merge output with recommendation decision proceed across 2 merged recommendation(s).",
            },
        ],
    }

    merged_runtime = payload["merged_recommendations"][0]
    assert merged_runtime["recommendation_id"] == "rec.runtime-bridge-alignment"
    assert merged_runtime["duplicate_count"] == 2
    assert merged_runtime["merged_from_draft_ids"] == [
        "draft-earth-runtime-001",
        "draft-local-runtime-002",
    ]
    assert merged_runtime["summary_variants"] == [
        "Align planner promotion with shared runtime bridge assumptions.",
        "Align runtime bridge assumptions before planner promotion.",
    ]
    assert [row["draft_id"] for row in merged_runtime["source_rationales"]] == merged_runtime["merged_from_draft_ids"]
    assert merged_runtime["evidence_refs"] == [
        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
        "reports/optimus-prime/planning/evidence/TASK-127/TASK_EVIDENCE.json",
        "strategy/current/llm_call_trace.jsonl",
        "strategy/current/samples/REQ-025_multi-call-strategy-pipeline-planner.sample.json",
    ]
    recommendation = payload["processing_behavior"]["recommendation"]
    assert recommendation["cross_project_obligations"] == [
        {
            "obligation_id": "obligation-rec-runtime-bridge-alignment",
            "project_id": "runtime-orchestrator",
            "summary": "Align runtime bridge assumptions before planner promotion.",
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-15/portfolio.json",
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                "reports/optimus-prime/planning/evidence/TASK-127/TASK_EVIDENCE.json",
                "strategy/current/llm_call_trace.jsonl",
                "strategy/current/samples/REQ-025_multi-call-strategy-pipeline-planner.sample.json",
            ],
        }
    ]
    assert recommendation["open_risks"] == []


def test_req_037_sample_matches_builder_output_for_fixture() -> None:
    fixture = _read_json(FIXTURE_PATH)
    expected = module.build_req_037_recommendation_deduplication_and_merge(
        target_project_root=fixture["target_project_root"],
        earth_root=fixture["earth_root"],
        output_root=fixture["output_root"],
        revision_identity=fixture["revision_identity"],
        target_project_evidence_refs=fixture["target_project_evidence_refs"],
        earth_sweep_evidence_refs=fixture["earth_sweep_evidence_refs"],
        cross_project_context=fixture["cross_project_context"],
        recommendation_drafts=fixture["recommendation_drafts"],
        merged_at="2026-03-16T12:00:00Z",
    )
    sample = _read_json(SAMPLE_PATH)
    assert sample == expected


def test_req_037_contract_doc_includes_sample_structure_reference() -> None:
    content = CONTRACT_DOC_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-037_recommendation-deduplication-and-merge.sample.json" in content
    for key in [
        "requirement_id",
        "surface",
        "schema_version",
        "recommendation_deduplication_and_merge_entrypoint",
        "processing_behavior",
        "call_metadata",
        "merged_at",
        "deduplication_index",
        "merged_recommendations",
        "evidence_refs",
        "summary",
    ]:
        assert f"`{key}`" in content


def test_req_037_rejects_semantic_duplication_across_multiple_stable_ids() -> None:
    fixture = _read_json(FIXTURE_PATH)
    conflicting = list(fixture["recommendation_drafts"])
    conflicting.append(
        {
            "draft_id": "draft-conflict-004",
            "recommendation_id": "rec.conflicting-stable-id",
            "semantic_signature": "runtime-bridge-alignment",
            "summary": "Align runtime bridge assumptions before planner promotion.",
            "rationale": "A conflicting stable ID should be rejected.",
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
            ],
        }
    )

    with pytest.raises(ValueError, match=r"multiple stable recommendation_ids"):
        module.build_req_037_recommendation_deduplication_and_merge(
            target_project_root=fixture["target_project_root"],
            earth_root=fixture["earth_root"],
            output_root=fixture["output_root"],
            revision_identity=fixture["revision_identity"],
            target_project_evidence_refs=fixture["target_project_evidence_refs"],
            earth_sweep_evidence_refs=fixture["earth_sweep_evidence_refs"],
            cross_project_context=fixture["cross_project_context"],
            recommendation_drafts=conflicting,
            merged_at="2026-03-16T12:00:00Z",
        )
