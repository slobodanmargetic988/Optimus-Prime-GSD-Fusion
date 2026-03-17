import json
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "recommendation-dependency-effect-modeling.json"


def _read_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_req_041_hardening_blocks_cross_call_contradiction_between_analysis_and_synthesis_outputs() -> None:
    fixture = _read_fixture()
    payload = module.build_req_041_recommendation_dependency_effect_modeling(
        target_project_root=fixture["target_project_root"],
        earth_root=fixture["earth_root"],
        output_root=fixture["output_root"],
        revision_identity=fixture["revision_identity"],
        recommendations=fixture["recommendations"],
        broad_sweep_context={
            "cross_call_reconciliations": [
                {
                    "call_id": "req041-call-02-13e4dba580",
                    "analysis_output": "expand rec.runtime-contract-alignment rollout",
                    "synthesis_output": "defer rec.runtime-contract-alignment rollout",
                    "project_ids": ["runtime-orchestrator"],
                    "evidence_refs": [
                        "strategy/current/llm_call_trace.jsonl#L2",
                        "reports/optimus-prime/planning/evidence/TASK-146/req041_cli_output.json",
                    ],
                }
            ]
        },
        modeled_at="2026-03-16T12:45:00Z",
    )

    assert module.validate_req_041_recommendation_dependency_effect_modeling(payload) == []
    assert payload["processing_behavior"]["recommendation"]["decision"] == "model_with_open_risks"
    contradiction_risk = next(
        row
        for row in payload["processing_behavior"]["recommendation"]["open_risks"]
        if row["reason_code"] == module.REASON_CODE_CROSS_CALL_ANALYSIS_SYNTHESIS_CONTRADICTION
    )
    assert contradiction_risk == {
        "risk_id": "risk.req041.cross_call_contradiction.req041-call-02-13e4dba580",
        "summary": (
            "Cross-call contradiction detected for req041-call-02-13e4dba580: "
            "analysis and synthesis outputs disagree."
        ),
        "reason_code": module.REASON_CODE_CROSS_CALL_ANALYSIS_SYNTHESIS_CONTRADICTION,
        "required_evidence_refs": [
            "reports/optimus-prime/planning/evidence/TASK-146/req041_cli_output.json",
            "strategy/current/llm_call_trace.jsonl#L2",
        ],
        "context_project_ids": ["runtime-orchestrator"],
        "evidence_refs": [
            "reports/optimus-prime/planning/evidence/TASK-146/req041_cli_output.json",
            "strategy/current/llm_call_trace.jsonl#L2",
        ],
    }


def test_req_041_hardening_blocks_uncited_strategic_claim_with_citation_discipline() -> None:
    fixture = _read_fixture()
    payload = module.build_req_041_recommendation_dependency_effect_modeling(
        target_project_root=fixture["target_project_root"],
        earth_root=fixture["earth_root"],
        output_root=fixture["output_root"],
        revision_identity=fixture["revision_identity"],
        recommendations=fixture["recommendations"],
        broad_sweep_context={
            "strategic_claims": [
                {
                    "claim_id": "claim.req041.expand-cross-project",
                    "summary": "Expand dependency-effect rollout without citation anchors.",
                    "project_ids": ["ground-control-hub"],
                    "citation_refs": [],
                    "evidence_refs": [
                        "reports/optimus-prime/planning/evidence/TASK-146/TASK_EVIDENCE.json",
                    ],
                }
            ]
        },
        modeled_at="2026-03-16T12:45:00Z",
    )

    assert module.validate_req_041_recommendation_dependency_effect_modeling(payload) == []
    uncited_risk = next(
        row
        for row in payload["processing_behavior"]["recommendation"]["open_risks"]
        if row["reason_code"] == module.REASON_CODE_CITATION_DISCIPLINE_UNCITED_STRATEGIC_CLAIM
    )
    assert uncited_risk == {
        "risk_id": "risk.req041.citation_discipline.claim.req041.expand-cross-project",
        "summary": "Citation discipline blocked uncited strategic claim: Expand dependency-effect rollout without citation anchors.",
        "reason_code": module.REASON_CODE_CITATION_DISCIPLINE_UNCITED_STRATEGIC_CLAIM,
        "required_evidence_refs": [
            "reports/optimus-prime/planning/evidence/TASK-146/TASK_EVIDENCE.json",
        ],
        "context_project_ids": ["ground-control-hub"],
        "evidence_refs": [
            "reports/optimus-prime/planning/evidence/TASK-146/TASK_EVIDENCE.json",
        ],
    }


def test_req_041_hardening_call_chain_replay_keeps_recommendation_ids_and_ordering_stable() -> None:
    fixture = _read_fixture()
    first_payload = module.build_req_041_recommendation_dependency_effect_modeling(
        target_project_root=fixture["target_project_root"],
        earth_root=fixture["earth_root"],
        output_root=fixture["output_root"],
        revision_identity=fixture["revision_identity"],
        recommendations=fixture["recommendations"],
        modeled_at="2026-03-16T12:45:00Z",
    )
    second_payload = module.build_req_041_recommendation_dependency_effect_modeling(
        target_project_root=fixture["target_project_root"],
        earth_root=fixture["earth_root"],
        output_root=fixture["output_root"],
        revision_identity=fixture["revision_identity"],
        recommendations=list(reversed(fixture["recommendations"])),
        modeled_at="2026-03-16T12:45:00Z",
    )

    assert module.validate_req_041_recommendation_dependency_effect_modeling(first_payload) == []
    assert module.validate_req_041_recommendation_dependency_effect_modeling(second_payload) == []
    assert [row["recommendation_id"] for row in first_payload["dependency_effect_models"]] == [
        row["recommendation_id"] for row in second_payload["dependency_effect_models"]
    ]
    assert [row["call_id"] for row in first_payload["call_metadata"]["llm_call_trace_rows"]] == [
        row["call_id"] for row in second_payload["call_metadata"]["llm_call_trace_rows"]
    ]
    assert [row["depends_on"] for row in first_payload["call_metadata"]["llm_call_trace_rows"]] == [
        row["depends_on"] for row in second_payload["call_metadata"]["llm_call_trace_rows"]
    ]
