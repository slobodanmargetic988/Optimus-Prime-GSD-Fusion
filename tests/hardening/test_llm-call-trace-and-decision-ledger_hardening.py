import json
import shutil
from pathlib import Path

from scripts import strategy_llm_pipeline as pipeline


def _reset_call_trace() -> None:
    trace_path = Path("strategy/current/llm_call_trace.jsonl")
    if trace_path.exists():
        trace_path.unlink()
    artifacts_dir = Path("strategy/current/llm_call_trace_artifacts")
    if artifacts_dir.exists():
        shutil.rmtree(artifacts_dir, ignore_errors=True)


def _write_json(path: Path, payload: dict) -> str:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return str(path)


def _trace_row(
    *,
    requirement_id: str,
    analysis_type: str,
    call_id: str,
    doc_ref: str,
    sha_seed: str,
) -> dict:
    return {
        "checked_at_utc": "2026-03-16T12:00:00Z",
        "requirement_id": requirement_id,
        "analysis_type": analysis_type,
        "call_id": call_id,
        "call_objective": f"Replay diagnostics for {requirement_id} {call_id}.",
        "target_project_id": "optimus-prime",
        "peer_project_ids": [],
        "input_refs": [doc_ref],
        "output_refs": [doc_ref],
        "artifacts": [
            {
                "kind": "output_snapshot",
                "path": doc_ref,
                "sha256": sha_seed * 64,
            }
        ],
        "handoff_summary": f"{requirement_id} {call_id} handoff recorded for replay diagnostics.",
        "totals": {
            "strategic_claims": 1,
        },
    }


def _base_payload(*, llm_call_trace_rows: list[dict], decision_ledger: list[dict]) -> dict:
    return {
        "analysis_type": pipeline.REQ_047_ANALYSIS_TYPE,
        "now_utc": "2026-03-16T12:00:00Z",
        "llm_call_trace_rows": llm_call_trace_rows,
        "final_output_artifacts": [
            {
                "artifact_ref": "reports/optimus-prime/final/strategy-packet.json",
                "artifact_role": "final_strategy_packet",
                "sha256": "a" * 64,
            }
        ],
        "decision_ledger": decision_ledger,
    }


def test_req047_hardening_cross_call_contradiction_emits_actionable_reason_code(tmp_path: Path) -> None:
    _reset_call_trace()
    analysis_ref = _write_json(
        tmp_path / "analysis.json",
        {
            "recommendations": [
                {
                    "recommendation_id": "rec.req-047.shared-runtime",
                    "position": "coordinate",
                    "evidence_refs": [
                        "reports/optimus-prime/planning/evidence/TASK-171/TASK_EVIDENCE.json",
                    ],
                }
            ]
        },
    )
    synthesis_ref = _write_json(
        tmp_path / "synthesis.json",
        {
            "recommendations": [
                {
                    "recommendation_id": "rec.req-047.shared-runtime",
                    "position": "local-only",
                    "evidence_refs": [
                        "REQ-047::call::call-4::output::recommendation_synthesis",
                    ],
                }
            ]
        },
    )
    payload = _base_payload(
        llm_call_trace_rows=[
            _trace_row(
                requirement_id="REQ-026",
                analysis_type="call_1_situational_analysis_reasoning",
                call_id="call-1",
                doc_ref=analysis_ref,
                sha_seed="1",
            ),
            _trace_row(
                requirement_id="REQ-039",
                analysis_type="recommendation_rationale_quality_scoring",
                call_id="call-4",
                doc_ref=synthesis_ref,
                sha_seed="2",
            ),
        ],
        decision_ledger=[
            {
                "decision_id": "dec.emit-shared-runtime",
                "decision_type": "emit",
                "summary": "Emit the shared-runtime recommendation when replay diagnostics stay coherent.",
                "rationale": "The output should halt if analysis and synthesis disagree on the same recommendation.",
                "source_call_refs": [
                    "REQ-026::call::call-1",
                    "REQ-039::call::call-4",
                ],
                "final_output_artifact_refs": [
                    "reports/optimus-prime/final/strategy-packet.json",
                ],
                "evidence_refs": [
                    analysis_ref,
                    synthesis_ref,
                ],
            }
        ],
    )

    result = pipeline.process_req_047_llm_call_trace_and_decision_ledger(payload)

    contradiction_risk = next(
        row
        for row in result["processing_behavior"]["recommendation"]["open_risks"]
        if row["reason_code"] == "cross_call_contradiction"
    )
    assert contradiction_risk["recommendation_ids"] == ["rec.req-047.shared-runtime"]
    assert contradiction_risk["source_call_refs"] == [
        "REQ-026::call::call-1",
        "REQ-039::call::call-4",
    ]
    assert analysis_ref in contradiction_risk["required_evidence_refs"]
    assert synthesis_ref in contradiction_risk["required_evidence_refs"]
    assert "reports/optimus-prime/planning/evidence/TASK-171/TASK_EVIDENCE.json" in contradiction_risk["required_evidence_refs"]


def test_req047_hardening_uncited_claim_is_blocked_by_citation_discipline(tmp_path: Path) -> None:
    _reset_call_trace()
    uncited_note = str(tmp_path / "uncited-note.md")
    citation_ref = _write_json(
        tmp_path / "citation.json",
        {
            "flagged_claims": [
                {
                    "recommendation_id": "rec.req-047.collect-citations",
                    "flag_reason_codes": [
                        "uncited_strategic_claim",
                    ],
                    "evidence_refs": [
                        uncited_note,
                    ],
                    "excluded_from_final_recommendations": True,
                }
            ]
        },
    )
    payload = _base_payload(
        llm_call_trace_rows=[
            _trace_row(
                requirement_id="REQ-035",
                analysis_type="evidence_citation_discipline_in_reasoning_calls",
                call_id="call-2",
                doc_ref=citation_ref,
                sha_seed="3",
            )
        ],
        decision_ledger=[
            {
                "decision_id": "dec.emit-citation-blocked",
                "decision_type": "emit",
                "summary": "Emit the recommendation only when citation discipline passes.",
                "rationale": "Uncited strategic claims must stay blocked in replay diagnostics.",
                "source_call_refs": [
                    "REQ-035::call::call-2",
                ],
                "final_output_artifact_refs": [
                    "reports/optimus-prime/final/strategy-packet.json",
                ],
                "evidence_refs": [
                    citation_ref,
                ],
            }
        ],
    )

    result = pipeline.process_req_047_llm_call_trace_and_decision_ledger(payload)

    recommendation = result["processing_behavior"]["recommendation"]
    citation_risk = next(
        row for row in recommendation["open_risks"] if row["reason_code"] == "uncited_strategic_claim"
    )
    assert recommendation["decision"] == "resolve-citation-gaps"
    assert recommendation["recommended_actions"] == []
    assert result["processing_behavior"]["context_usage"]["blocked_recommendation_ids"] == [
        "rec.req-047.collect-citations"
    ]
    assert citation_risk["recommendation_ids"] == ["rec.req-047.collect-citations"]
    assert citation_ref in citation_risk["required_evidence_refs"]
    assert uncited_note in citation_risk["required_evidence_refs"]


def test_req047_hardening_replay_keeps_recommendation_ids_and_order_stable(tmp_path: Path) -> None:
    _reset_call_trace()
    first_ref = _write_json(
        tmp_path / "first.json",
        {
            "recommendations": [
                {
                    "recommendation_id": "rec.req-047.alpha",
                    "position": "coordinate",
                    "evidence_refs": [
                        "reports/optimus-prime/planning/evidence/TASK-171/TASK_EVIDENCE.json",
                    ],
                },
                {
                    "recommendation_id": "rec.req-047.beta",
                    "position": "coordinate",
                    "evidence_refs": [
                        "reports/optimus-prime/planning/evidence/TASK-171/TASK_EVIDENCE.json",
                    ],
                },
            ]
        },
    )
    second_ref = _write_json(
        tmp_path / "second.json",
        {
            "recommendations": [
                {
                    "recommendation_id": "rec.req-047.beta",
                    "position": "coordinate",
                    "evidence_refs": [
                        "reports/optimus-prime/planning/evidence/TASK-171/TASK_EVIDENCE.json",
                    ],
                },
                {
                    "recommendation_id": "rec.req-047.alpha",
                    "position": "coordinate",
                    "evidence_refs": [
                        "reports/optimus-prime/planning/evidence/TASK-171/TASK_EVIDENCE.json",
                    ],
                },
            ]
        },
    )
    payload = _base_payload(
        llm_call_trace_rows=[
            _trace_row(
                requirement_id="REQ-026",
                analysis_type="call_1_situational_analysis_reasoning",
                call_id="call-1",
                doc_ref=first_ref,
                sha_seed="4",
            ),
            _trace_row(
                requirement_id="REQ-039",
                analysis_type="recommendation_rationale_quality_scoring",
                call_id="call-4",
                doc_ref=second_ref,
                sha_seed="5",
            ),
        ],
        decision_ledger=[
            {
                "decision_id": "dec.emit-stable-ordering",
                "decision_type": "emit",
                "summary": "Emit replay-ready recommendations with stable ids and ordering.",
                "rationale": "Replay analysis should not depend on input ordering.",
                "source_call_refs": [
                    "REQ-026::call::call-1",
                    "REQ-039::call::call-4",
                ],
                "final_output_artifact_refs": [
                    "reports/optimus-prime/final/strategy-packet.json",
                ],
                "evidence_refs": [
                    second_ref,
                    first_ref,
                ],
            }
        ],
    )

    first = pipeline.process_req_047_llm_call_trace_and_decision_ledger(payload)

    _reset_call_trace()
    replay = dict(payload)
    replay["llm_call_trace_rows"] = list(reversed(payload["llm_call_trace_rows"]))
    replay["decision_ledger"] = [
        {
            **payload["decision_ledger"][0],
            "source_call_refs": list(reversed(payload["decision_ledger"][0]["source_call_refs"])),
            "evidence_refs": list(reversed(payload["decision_ledger"][0]["evidence_refs"])),
        }
    ]
    second = pipeline.process_req_047_llm_call_trace_and_decision_ledger(replay)

    first_usage = first["processing_behavior"]["context_usage"]
    second_usage = second["processing_behavior"]["context_usage"]
    assert first_usage["emitted_recommendation_ids"] == second_usage["emitted_recommendation_ids"] == [
        "rec.req-047.alpha",
        "rec.req-047.beta",
    ]
    assert first["processing_behavior"]["recommendation"]["recommended_actions"][0]["recommendation_ids"] == [
        "rec.req-047.alpha",
        "rec.req-047.beta",
    ]
    assert second["processing_behavior"]["recommendation"]["recommended_actions"][0]["recommendation_ids"] == [
        "rec.req-047.alpha",
        "rec.req-047.beta",
    ]
    assert first["call_metadata"]["canonical_processing_input"] == second["call_metadata"]["canonical_processing_input"]
    assert first["call_metadata"]["canonical_processing_input_sha256"] == second["call_metadata"]["canonical_processing_input_sha256"]
