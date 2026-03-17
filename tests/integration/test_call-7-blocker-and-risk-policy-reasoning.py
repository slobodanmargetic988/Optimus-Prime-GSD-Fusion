import copy
import json
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "call-7-blocker-and-risk-policy-reasoning.json"
EARTH_REFS = [
    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
    "reports/earth/sweeps/2026-03-16/shared-observability.json",
]
TASK_107_EVIDENCE_REF = "reports/optimus-prime/planning/evidence/TASK-107/TASK_EVIDENCE.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_032_integration_emits_evidence_backed_policy_and_cross_project_usage() -> None:
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_032_call_7_blocker_and_risk_policy_reasoning(**fixture["input"])

    assert module.validate_req_032_call_7_blocker_and_risk_policy_reasoning(payload) == []

    context_usage = payload["processing_behavior"]["context_usage"]
    assert context_usage["cross_project_context_used"] is True
    assert context_usage["cross_project_projects_considered"] == [
        "runtime-orchestrator",
        "shared-observability",
    ]
    assert context_usage["cross_project_refs_used"] == EARTH_REFS
    assert context_usage["escalation_project_ids"] == [
        "runtime-orchestrator",
        "shared-observability",
    ]

    call_7_reasoning = payload["processing_behavior"]["call_7_reasoning"]
    assert call_7_reasoning["blocker_count"] == 2
    assert call_7_reasoning["policy_count"] == 2
    assert call_7_reasoning["escalation_trigger_count"] == 3
    assert call_7_reasoning["fallback_path_count"] == 3
    for row in call_7_reasoning["blocker_reasoning"]:
        assert row["linked_context_projects"]
        assert row["evidence_refs"]
        assert row["escalation_triggers"]
        assert row["fallback_paths"]
        assert row["applicable_policies"]

    recommendation = payload["processing_behavior"]["recommendation"]
    assert recommendation["decision"] == "fallback-then-escalate"
    assert recommendation["rationale"]
    assert recommendation["confidence"] == "high"
    assert recommendation["open_risks"] == []
    assert recommendation["evidence_refs"] == [*EARTH_REFS, TASK_107_EVIDENCE_REF]
    assert [row["trigger_id"] for row in recommendation["escalation_triggers"]] == [
        "trigger.runtime-heartbeat-mismatch",
        "trigger.trace-proof-missing",
    ]
    assert [row["fallback_id"] for row in recommendation["fallback_sequence"]] == [
        "fallback.freeze-canary-promotion",
        "fallback.publish-bridge-note",
    ]
    for row in recommendation["escalation_triggers"]:
        assert row["blocker_id"]
        assert row["policy_id"]
        assert row["summary"]
        assert row["fire_when"]
        assert row["urgency"]
        assert row["evidence_refs"]
        assert any(ref.startswith("reports/earth/") for ref in row["evidence_refs"])
    for row in recommendation["fallback_sequence"]:
        assert row["blocker_id"]
        assert row["policy_id"]
        assert row["summary"]
        assert row["activates_when"]
        assert row["next_step"]
        assert row["evidence_refs"]

    trace_rows = payload["call_metadata"]["llm_call_trace_rows"]
    assert payload["call_metadata"]["llm_call_trace_path"] == module.LLM_CALL_TRACE_RELATIVE_PATH
    assert len(trace_rows) == 1
    assert trace_rows[0]["requirement_id"] == module.REQ_032_REQUIREMENT_ID
    assert trace_rows[0]["sequence"] == module.REQ_032_CALL_SEQUENCE
    assert trace_rows[0]["call_objective"] == module.REQ_032_TRACE_CALL_OBJECTIVE
    assert trace_rows[0]["input_refs"] == [*EARTH_REFS, TASK_107_EVIDENCE_REF]
    assert trace_rows[0]["output_refs"]
    assert "blockers" in trace_rows[0]["handoff_summary"]
    assert "escalation triggers" in trace_rows[0]["handoff_summary"]


def test_req_032_missing_trigger_context_becomes_open_risk_instead_of_promoted_escalation() -> None:
    fixture = _read_json(FIXTURE_PATH)
    mutated_input = copy.deepcopy(fixture["input"])
    mutated_input["blocker_candidates"].append(
        {
            "blocker_id": "blocker.release-coordination-unknown",
            "summary": "A release coordination escalation path was suggested without Earth-sweep context coverage.",
            "severity": "high",
            "affected_project_ids": [
                "shared-observability",
            ],
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-16/shared-observability.json",
            ],
            "escalation_triggers": [
                {
                    "trigger_id": "trigger.release-coordination-sync",
                    "project_id": "release-coordination",
                    "summary": "Escalate only after release coordination confirms the blocker signal contract.",
                    "fire_when": "A new release coordination dependency is proposed for the blocker policy.",
                    "urgency": "high",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-16/shared-observability.json",
                    ],
                }
            ],
            "fallback_paths": [
                {
                    "fallback_id": "fallback.defer-release-coordination",
                    "sequence": 1,
                    "summary": "Keep the policy local until release coordination has Earth-sweep evidence.",
                    "activates_when": "The blocker policy introduces an unverified release coordination dependency.",
                    "next_step": "Record the dependency as an open risk and re-run Call-7 after the Earth sweep lands.",
                    "evidence_refs": [
                        TASK_107_EVIDENCE_REF,
                    ],
                }
            ],
        }
    )
    mutated_input["risk_policy_candidates"].append(
        {
            "policy_id": "policy.release-coordination-escalate",
            "blocker_id": "blocker.release-coordination-unknown",
            "policy_decision": "escalate-immediately",
            "rationale": "If release coordination is truly required, the dependency must be evidence-backed before promotion.",
            "preferred_fallback_ids": [],
            "escalation_trigger_ids": [
                "trigger.release-coordination-sync",
            ],
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-16/shared-observability.json",
            ],
        }
    )

    payload = module.build_req_032_call_7_blocker_and_risk_policy_reasoning(**mutated_input)

    assert module.validate_req_032_call_7_blocker_and_risk_policy_reasoning(payload) == []

    recommendation = payload["processing_behavior"]["recommendation"]
    assert recommendation["decision"] == "resolve-context-gaps"
    assert "trigger.release-coordination-sync" not in {
        row["trigger_id"] for row in recommendation["escalation_triggers"]
    }
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk-blocker.release-coordination-unknown-trigger.release-coordination-sync-context",
            "summary": "Escalate only after release coordination confirms the blocker signal contract.",
            "reason_code": "missing_escalation_project_context",
            "affected_project_ids": ["release-coordination"],
            "required_evidence_refs": [
                "reports/earth/sweeps/2026-03-16/shared-observability.json",
            ],
        }
    ]
    assert payload["processing_behavior"]["context_usage"]["cross_project_projects_considered"] == [
        "runtime-orchestrator",
        "shared-observability",
    ]
