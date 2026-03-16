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
