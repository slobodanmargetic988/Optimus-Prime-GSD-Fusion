import copy
import json
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "recommendation-deduplication-and-merge.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _base_input() -> dict:
    return copy.deepcopy(_read_json(FIXTURE_PATH))


def test_req_037_cross_call_contradiction_between_analysis_and_synthesis_outputs_emits_deterministic_reason_code() -> None:
    payload = module.build_req_037_recommendation_deduplication_and_merge(
        **_base_input(),
        merged_at="2026-03-16T12:00:00Z",
        strategic_claims=[
            {
                "claim_id": "claim-runtime-bridge-alignment",
                "phase": "analysis",
                "summary": "Analysis concludes the runtime bridge alignment should be promoted immediately.",
                "position": "promote-runtime-bridge-alignment",
                "source_output_ref": "REQ-035::call::call-2::output::analysis-runtime-bridge-alignment",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
            },
            {
                "claim_id": "claim-runtime-bridge-alignment",
                "phase": "synthesis",
                "summary": "Synthesis concludes the runtime bridge alignment should remain deferred pending another merge pass.",
                "position": "defer-runtime-bridge-alignment",
                "source_output_ref": "REQ-036::call::call-3::output::synthesis-runtime-bridge-alignment",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
            },
        ],
    )

    assert module.validate_req_037_recommendation_deduplication_and_merge(payload) == []

    contradiction_risk = next(
        row
        for row in payload["processing_behavior"]["recommendation"]["open_risks"]
        if row["reason_code"] == "cross_call_contradiction"
    )
    assert contradiction_risk == {
        "risk_id": "risk-claim-claim-runtime-bridge-alignment-contradiction",
        "summary": "Synthesis concludes the runtime bridge alignment should remain deferred pending another merge pass.",
        "reason_code": "cross_call_contradiction",
        "required_evidence_refs": [
            "REQ-035::call::call-2::output::analysis-runtime-bridge-alignment",
            "REQ-036::call::call-3::output::synthesis-runtime-bridge-alignment",
            "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
        ],
    }
    assert payload["processing_behavior"]["recommendation"]["decision"] == "resolve-strategy-gaps"


def test_req_037_uncited_strategic_claim_is_blocked_by_citation_discipline() -> None:
    payload = module.build_req_037_recommendation_deduplication_and_merge(
        **_base_input(),
        merged_at="2026-03-16T12:00:00Z",
        strategic_claims=[
            {
                "claim_id": "claim-uncited-citation-discipline",
                "phase": "analysis",
                "summary": "Analysis proposes a merge rationale override without attaching evidence refs.",
                "position": "override-merge-rationale",
                "source_output_ref": "REQ-035::call::call-2::output::analysis-merge-rationale-override",
                "evidence_refs": [],
            }
        ],
    )

    assert module.validate_req_037_recommendation_deduplication_and_merge(payload) == []

    uncited_risk = next(
        row
        for row in payload["processing_behavior"]["recommendation"]["open_risks"]
        if row["reason_code"] == "uncited_strategic_claim"
    )
    assert uncited_risk == {
        "risk_id": "risk-claim-claim-uncited-citation-discipline-citation",
        "summary": "Analysis proposes a merge rationale override without attaching evidence refs.",
        "reason_code": "uncited_strategic_claim",
        "required_evidence_refs": [
            "REQ-035::call::call-2::output::analysis-merge-rationale-override",
        ],
    }
    assert payload["processing_behavior"]["recommendation"]["decision"] == "resolve-strategy-gaps"


def test_req_037_call_chain_replay_keeps_recommendation_ids_and_ordering_stable() -> None:
    first = module.build_req_037_recommendation_deduplication_and_merge(
        **_base_input(),
        merged_at="2026-03-16T12:00:00Z",
    )

    replay_input = _base_input()
    replay_input["recommendation_drafts"] = [
        replay_input["recommendation_drafts"][2],
        replay_input["recommendation_drafts"][0],
        replay_input["recommendation_drafts"][1],
    ]
    replay = module.build_req_037_recommendation_deduplication_and_merge(
        **replay_input,
        merged_at="2026-03-16T12:00:00Z",
    )

    assert module.validate_req_037_recommendation_deduplication_and_merge(first) == []
    assert module.validate_req_037_recommendation_deduplication_and_merge(replay) == []
    assert first["call_metadata"]["canonical_processing_input"] == replay["call_metadata"]["canonical_processing_input"]
    assert first["call_metadata"]["processing_input_sha256"] == replay["call_metadata"]["processing_input_sha256"]
    assert first["call_metadata"]["processing_call_id"] == replay["call_metadata"]["processing_call_id"]
    assert first["call_metadata"]["llm_call_trace_rows"] == replay["call_metadata"]["llm_call_trace_rows"]
    assert first["merged_recommendations"] == replay["merged_recommendations"]
    assert first["processing_behavior"]["recommendation"]["merged_recommendations"] == replay["processing_behavior"][
        "recommendation"
    ]["merged_recommendations"]
    assert first["deduplication_index"]["recommendation_ids"] == [
        "rec.runtime-bridge-alignment",
        "rec.trace-citation-discipline",
    ]
    assert first["deduplication_index"]["recommendation_ids"] == replay["deduplication_index"]["recommendation_ids"]
