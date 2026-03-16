import copy
import json
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "call-7-blocker-and-risk-policy-reasoning.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _base_input() -> dict:
    return copy.deepcopy(_read_json(FIXTURE_PATH)["input"])


def test_req_032_cross_call_contradiction_between_analysis_and_synthesis_outputs_emits_deterministic_reason_code() -> None:
    payload = module.build_req_032_call_7_blocker_and_risk_policy_reasoning(
        **_base_input(),
        strategic_claims=[
            {
                "claim_id": "claim-runtime-handshake-policy",
                "phase": "analysis",
                "summary": "Analysis concludes the runtime handshake policy should escalate immediately.",
                "position": "escalate-runtime-handshake-immediately",
                "source_output_ref": "REQ-030::call::call-5::output::analysis-runtime-handshake-policy",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                ],
            },
            {
                "claim_id": "claim-runtime-handshake-policy",
                "phase": "synthesis",
                "summary": "Synthesis concludes the runtime handshake policy should freeze promotion before escalation.",
                "position": "freeze-then-escalate-runtime-handshake",
                "source_output_ref": "REQ-031::call::call-6::output::synthesis-runtime-handshake-policy",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                ],
            },
        ],
    )

    assert module.validate_req_032_call_7_blocker_and_risk_policy_reasoning(payload) == []

    contradiction_risk = next(
        row
        for row in payload["processing_behavior"]["recommendation"]["open_risks"]
        if row["reason_code"] == "cross_call_contradiction"
    )
    assert contradiction_risk == {
        "risk_id": "risk-claim-claim-runtime-handshake-policy-contradiction",
        "summary": "Synthesis concludes the runtime handshake policy should freeze promotion before escalation.",
        "reason_code": "cross_call_contradiction",
        "required_evidence_refs": [
            "REQ-030::call::call-5::output::analysis-runtime-handshake-policy",
            "REQ-031::call::call-6::output::synthesis-runtime-handshake-policy",
            "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
        ],
    }
    assert payload["processing_behavior"]["recommendation"]["decision"] == "resolve-strategy-gaps"


def test_req_032_uncited_strategic_claim_is_blocked_by_citation_discipline() -> None:
    payload = module.build_req_032_call_7_blocker_and_risk_policy_reasoning(
        **_base_input(),
        strategic_claims=[
            {
                "claim_id": "claim-uncited-trace-policy",
                "phase": "analysis",
                "summary": "Analysis proposes a blocker-policy override without attaching any evidence refs.",
                "position": "override-blocker-policy",
                "source_output_ref": "REQ-030::call::call-5::output::analysis-blocker-policy-override",
                "evidence_refs": [],
            }
        ],
    )

    assert module.validate_req_032_call_7_blocker_and_risk_policy_reasoning(payload) == []

    uncited_risk = next(
        row
        for row in payload["processing_behavior"]["recommendation"]["open_risks"]
        if row["reason_code"] == "uncited_strategic_claim"
    )
    assert uncited_risk == {
        "risk_id": "risk-claim-claim-uncited-trace-policy-citation",
        "summary": "Analysis proposes a blocker-policy override without attaching any evidence refs.",
        "reason_code": "uncited_strategic_claim",
        "required_evidence_refs": [
            "REQ-030::call::call-5::output::analysis-blocker-policy-override",
        ],
    }
    assert payload["processing_behavior"]["recommendation"]["decision"] == "resolve-strategy-gaps"


def test_req_032_call_chain_replay_keeps_recommendation_ids_and_ordering_stable() -> None:
    first = module.build_req_032_call_7_blocker_and_risk_policy_reasoning(**_base_input())

    replay_input = _base_input()
    replay_input["evidence_refs"] = list(reversed(replay_input["evidence_refs"]))
    replay_input["target_project_evidence_refs"] = list(reversed(replay_input["target_project_evidence_refs"]))
    replay_input["earth_sweep_evidence_refs"] = list(reversed(replay_input["earth_sweep_evidence_refs"]))
    replay_input["cross_project_context"] = list(reversed(replay_input["cross_project_context"]))
    replay_input["blocker_candidates"] = list(reversed(replay_input["blocker_candidates"]))
    for blocker in replay_input["blocker_candidates"]:
        blocker["escalation_triggers"] = list(reversed(blocker["escalation_triggers"]))
        blocker["fallback_paths"] = list(reversed(blocker["fallback_paths"]))
        blocker["affected_project_ids"] = list(reversed(blocker["affected_project_ids"]))
        blocker["evidence_refs"] = list(reversed(blocker["evidence_refs"]))
    replay_input["risk_policy_candidates"] = list(reversed(replay_input["risk_policy_candidates"]))
    for policy in replay_input["risk_policy_candidates"]:
        policy["preferred_fallback_ids"] = list(reversed(policy["preferred_fallback_ids"]))
        policy["escalation_trigger_ids"] = list(reversed(policy["escalation_trigger_ids"]))
        policy["evidence_refs"] = list(reversed(policy["evidence_refs"]))

    replay = module.build_req_032_call_7_blocker_and_risk_policy_reasoning(**replay_input)

    assert module.validate_req_032_call_7_blocker_and_risk_policy_reasoning(first) == []
    assert module.validate_req_032_call_7_blocker_and_risk_policy_reasoning(replay) == []
    assert first["call_metadata"]["canonical_processing_input"] == replay["call_metadata"]["canonical_processing_input"]
    assert first["call_metadata"]["processing_input_sha256"] == replay["call_metadata"]["processing_input_sha256"]
    assert first["call_metadata"]["processing_call_id"] == replay["call_metadata"]["processing_call_id"]
    assert first["call_metadata"]["llm_call_trace_rows"] == replay["call_metadata"]["llm_call_trace_rows"]
    assert first["processing_behavior"]["recommendation"] == replay["processing_behavior"]["recommendation"]
    assert first["processing_behavior"]["context_usage"]["policy_ids_considered"] == [
        "policy.runtime-handshake-fallback",
        "policy.trace-citation-escalate",
    ]
    assert [row["trigger_id"] for row in first["processing_behavior"]["recommendation"]["escalation_triggers"]] == [
        "trigger.runtime-heartbeat-mismatch",
        "trigger.trace-proof-missing",
    ]
    assert [row["fallback_id"] for row in first["processing_behavior"]["recommendation"]["fallback_sequence"]] == [
        "fallback.freeze-canary-promotion",
        "fallback.publish-bridge-note",
    ]
    assert (
        first["processing_behavior"]["context_usage"]["policy_ids_considered"]
        == replay["processing_behavior"]["context_usage"]["policy_ids_considered"]
    )
