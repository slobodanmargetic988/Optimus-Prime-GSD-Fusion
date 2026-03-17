from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts import strategy_llm_pipeline as pipeline


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "final-strategy-synthesis-composer.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_046_hardening_cross_call_contradiction_is_deferred_with_reason_code_and_evidence_refs() -> None:
    fixture_payload = copy.deepcopy(_read_json(FIXTURE_PATH))
    for call in fixture_payload["validated_call_outputs"]:
        if call["call_id"] != "rationale-quality-scoring":
            continue
        for recommendation in call["recommendations"]:
            if recommendation["recommendation_id"] != "rec.harden-telemetry-freshness":
                continue
            recommendation["packet_kind"] = "cross-project"
            recommendation["peer_project_id"] = "earth-core-runtime"

    payload = pipeline.build_req_046_final_strategy_synthesis_composer(fixture_payload)
    assert pipeline.validate_req_046_final_strategy_synthesis_composer(payload) == []

    deferred = payload["final_strategy_synthesis"]["deferred_recommendations"]
    deferred_by_id = {row["recommendation_id"]: row for row in deferred}
    contradiction = deferred_by_id["rec.harden-telemetry-freshness"]

    assert contradiction["deferred_reason_code"] == "conflicting_packet_routing"
    assert contradiction["evidence_refs"] == [
        "reports/quality/req-039-rationale-quality-score.json",
        "reports/runtime/telemetry/freshness-gap-2026-03-15.json",
    ]
    assert [row["trace_id"] for row in contradiction["call_trace_lineage"]] == [
        "trace-call-5-001",
        "trace-rationale-quality-001",
    ]


def test_req_046_hardening_uncited_claim_emits_citation_discipline_open_risk() -> None:
    fixture_payload = copy.deepcopy(_read_json(FIXTURE_PATH))
    for call in fixture_payload["validated_call_outputs"]:
        for recommendation in call["recommendations"]:
            if recommendation["recommendation_id"] != "rec.harden-telemetry-freshness":
                continue
            recommendation["evidence_refs"] = []

    payload = pipeline.build_req_046_final_strategy_synthesis_composer(fixture_payload)
    assert pipeline.validate_req_046_final_strategy_synthesis_composer(payload) == []

    synthesis = payload["final_strategy_synthesis"]
    final_ids = {row["recommendation_id"] for row in synthesis["final_recommendations"]}
    assert "rec.harden-telemetry-freshness" not in final_ids

    risks = [
        row
        for row in synthesis["open_risks"]
        if row["recommendation_id"] == "rec.harden-telemetry-freshness"
        and row["reason_code"] == "uncited_strategic_claim_blocked"
    ]
    assert len(risks) == 1
    risk = risks[0]
    assert risk["open_risk_id"] == (
        "open-risk."
        + pipeline._stable_id_fragment("rec.harden-telemetry-freshness", "uncited_strategic_claim_blocked")
    )
    assert risk["required_evidence_refs"] == ["missing:citation-evidence-ref"]
    assert risk["evidence_refs"] == []
    assert risk["linked_recommendation_ids"] == ["rec.harden-telemetry-freshness"]
    assert [row["trace_id"] for row in risk["call_trace_lineage"]] == [
        "trace-call-5-001",
        "trace-rationale-quality-001",
    ]


def test_req_046_hardening_call_chain_replay_keeps_recommendation_ids_and_ordering_stable() -> None:
    baseline_input = _read_json(FIXTURE_PATH)
    replay_input = copy.deepcopy(baseline_input)
    replay_input["validated_call_outputs"] = list(reversed(replay_input["validated_call_outputs"]))
    replay_input["broad_sweep_context"]["earth_sweep_evidence_refs"] = list(
        reversed(replay_input["broad_sweep_context"]["earth_sweep_evidence_refs"])
    )
    replay_input["broad_sweep_context"]["projects_considered"] = list(
        reversed(replay_input["broad_sweep_context"]["projects_considered"])
    )
    replay_input["broad_sweep_context"]["cross_project_obligations"] = list(
        reversed(replay_input["broad_sweep_context"]["cross_project_obligations"])
    )
    replay_input["broad_sweep_context"]["unresolved_ideas"] = list(
        reversed(replay_input["broad_sweep_context"]["unresolved_ideas"])
    )
    for call in replay_input["validated_call_outputs"]:
        call["recommendations"] = list(reversed(call["recommendations"]))

    baseline_output = pipeline.build_req_046_final_strategy_synthesis_composer(copy.deepcopy(baseline_input))
    replay_output_1 = pipeline.build_req_046_final_strategy_synthesis_composer(copy.deepcopy(replay_input))
    replay_output_2 = pipeline.build_req_046_final_strategy_synthesis_composer(copy.deepcopy(replay_input))

    assert pipeline.validate_req_046_final_strategy_synthesis_composer(baseline_output) == []
    assert pipeline.validate_req_046_final_strategy_synthesis_composer(replay_output_1) == []
    assert pipeline.validate_req_046_final_strategy_synthesis_composer(replay_output_2) == []
    assert baseline_output == replay_output_1 == replay_output_2

    synthesis = replay_output_1["final_strategy_synthesis"]
    assert [row["recommendation_id"] for row in synthesis["final_recommendations"]] == [
        "rec.harden-telemetry-freshness",
        "rec.align-earth-runtime-canary",
    ]
    assert [row["recommendation_id"] for row in synthesis["deferred_recommendations"]] == [
        "rec.review-reuse-contracts",
    ]
    assert [row["packet_input_id"] for row in synthesis["strategy_packet_inputs"]] == [
        "pkt.c3c7c38214ae",
        "pkt.9e0c566d663e",
    ]
