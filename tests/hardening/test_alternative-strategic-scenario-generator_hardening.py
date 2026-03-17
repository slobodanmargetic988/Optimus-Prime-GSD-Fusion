import copy
import json
from pathlib import Path

import pytest

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "alternative-strategic-scenario-generator.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _base_req_045_input() -> dict:
    fixture = _read_json(FIXTURE_PATH)
    return copy.deepcopy(fixture["input"])


def _build_payload(payload_input: dict) -> dict:
    payload = module.build_req_045_alternative_strategic_scenario_generator(**payload_input)
    assert module.validate_req_045_alternative_strategic_scenario_generator(payload) == []
    return payload


def test_req_045_hardening_blocks_cross_call_analysis_synthesis_contradiction() -> None:
    payload = _build_payload(_base_req_045_input())

    payload["processing_behavior"]["recommendation"]["decision"] = "single-path-sufficient"
    errors = module.validate_req_045_alternative_strategic_scenario_generator(payload)

    contradiction_errors = [
        row for row in errors if module.REQ_045_REASON_CODE_ANALYSIS_SYNTHESIS_CONTRADICTION in row
    ]
    assert contradiction_errors
    assert all("call_id:req045-" in row for row in contradiction_errors)

    with pytest.raises(module.Req045Error, match=module.REQ_045_REASON_CODE_ANALYSIS_SYNTHESIS_CONTRADICTION):
        module.build_req_045_llm_call_trace_rows(payload)


def test_req_045_hardening_blocks_uncited_strategic_claims_with_citation_discipline() -> None:
    payload = _build_payload(_base_req_045_input())

    payload["processing_behavior"]["recommendation"]["evidence_refs"] = [
        "reports/optimus-prime/planning/evidence/TASK-159/TASK_EVIDENCE.json"
    ]
    errors = module.validate_req_045_alternative_strategic_scenario_generator(payload)

    uncited_errors = [
        row for row in errors if module.REQ_045_REASON_CODE_UNCITED_STRATEGIC_CLAIM_BLOCKED in row
    ]
    assert uncited_errors
    assert any("scenario:scenario.cross-project-alignment-first" in row for row in uncited_errors)
    assert any("reports/earth/sweeps/2026-03-16/portfolio.json" in row for row in uncited_errors)

    with pytest.raises(module.Req045Error, match=module.REQ_045_REASON_CODE_UNCITED_STRATEGIC_CLAIM_BLOCKED):
        module.build_req_045_llm_call_trace_rows(payload)


def test_req_045_hardening_call_chain_replay_keeps_recommendation_ids_and_ordering_stable() -> None:
    first_input = _base_req_045_input()
    first_input["target_project_evidence_refs"] = [
        "reports/optimus-prime/planning/evidence/TASK-159/TASK_EVIDENCE.json",
        "reports/optimus-prime/planning/evidence/TASK-159/TASK_EVIDENCE.json",
    ]
    first_input["earth_sweep_evidence_refs"] = [
        "reports/earth/sweeps/2026-03-16/portfolio.json",
        "reports/earth/sweeps/2026-03-16/portfolio.json",
    ]
    first_input["scenario_candidates"] = list(reversed(first_input["scenario_candidates"]))

    second_input = _base_req_045_input()
    second_input["scenario_candidates"] = [
        second_input["scenario_candidates"][1],
        second_input["scenario_candidates"][2],
        second_input["scenario_candidates"][0],
    ]

    first = _build_payload(first_input)
    second = _build_payload(second_input)
    third = _build_payload(first_input)

    assert first == second == third

    first_ids = {
        "reproducible_call_id": first["call_metadata"]["reproducible_call_id"],
        "processing_call_id": first["call_metadata"]["processing_call_id"],
        "obligation_ids": [
            row["obligation_id"] for row in first["processing_behavior"]["recommendation"]["obligations"]
        ],
        "open_risk_ids": [
            row["risk_id"] for row in first["processing_behavior"]["recommendation"]["open_risks"]
        ],
    }
    second_ids = {
        "reproducible_call_id": second["call_metadata"]["reproducible_call_id"],
        "processing_call_id": second["call_metadata"]["processing_call_id"],
        "obligation_ids": [
            row["obligation_id"] for row in second["processing_behavior"]["recommendation"]["obligations"]
        ],
        "open_risk_ids": [
            row["risk_id"] for row in second["processing_behavior"]["recommendation"]["open_risks"]
        ],
    }
    third_ids = {
        "reproducible_call_id": third["call_metadata"]["reproducible_call_id"],
        "processing_call_id": third["call_metadata"]["processing_call_id"],
        "obligation_ids": [
            row["obligation_id"] for row in third["processing_behavior"]["recommendation"]["obligations"]
        ],
        "open_risk_ids": [
            row["risk_id"] for row in third["processing_behavior"]["recommendation"]["open_risks"]
        ],
    }

    assert first_ids == second_ids == third_ids
    assert first_ids["obligation_ids"] == sorted(first_ids["obligation_ids"])
    assert first_ids["open_risk_ids"] == sorted(first_ids["open_risk_ids"])

    trace_one = module.build_req_045_llm_call_trace_rows(
        first,
        output_payload_ref="reports/optimus-prime/planning/evidence/TASK-162/req045-output.json",
    )
    trace_two = module.build_req_045_llm_call_trace_rows(
        second,
        output_payload_ref="reports/optimus-prime/planning/evidence/TASK-162/req045-output.json",
    )
    trace_three = module.build_req_045_llm_call_trace_rows(
        third,
        output_payload_ref="reports/optimus-prime/planning/evidence/TASK-162/req045-output.json",
    )

    assert [row["call_index"] for row in trace_one] == [1, 2]
    assert trace_one == trace_two == trace_three
    assert [row["llm_call_id"] for row in trace_one] == [row["llm_call_id"] for row in trace_two]
    assert [row["llm_call_id"] for row in trace_two] == [row["llm_call_id"] for row in trace_three]
