import json
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "cross-call-memory-handoff-contract.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-034_cross-call-memory-handoff-contract.sample.json"
)
CONTRACT_PATH = (
    REPO_ROOT
    / "contracts"
    / "req"
    / "REQ-034_cross-call-memory-handoff-contract.md"
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _base_input() -> dict:
    return {
        "target_project_root": "/workspace/projects/optimus-prime",
        "earth_root": "/workspace/projects/Earth",
        "output_root": "/workspace/projects/optimus-prime/strategy/out",
        "revision_identity": "rev-req034-contract-r1",
        "strategy_goal": "Carry bounded, cited memory across earlier calls without contradiction drift.",
        "call_id": "call-memory-handoff",
        "checked_at_utc": "2026-03-16T14:10:00Z",
        "target_project_evidence_refs": [
            "reports/optimus-prime/planning/evidence/TASK-118/TASK_EVIDENCE.json",
        ],
        "earth_sweep_evidence_refs": [
            "reports/earth/sweeps/2026-03-16/portfolio.json",
            "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
        ],
        "cross_project_context": [
            {
                "project_id": "runtime-orchestrator",
                "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                ],
                "context_note": "Runtime orchestrator still owns the shared recovery envelope.",
            }
        ],
        "prior_call_handoffs": [
            {
                "sequence": 1,
                "call_id": "call-1",
                "phase": "analysis",
                "output_ref": "REQ-034::call::call-1::output::situational_analysis",
                "memory_items": [
                    {
                        "memory_id": "memory.scope-guard",
                        "summary": "Keep the reasoning scope locked to the target project unless Earth evidence expands it.",
                        "category": "guardrail",
                        "position": "preserve",
                        "project_scope": "local",
                        "project_id": "",
                        "citation_refs": [
                            "reports/optimus-prime/planning/evidence/TASK-118/TASK_EVIDENCE.json",
                        ],
                    },
                    {
                        "memory_id": "memory.runtime-envelope",
                        "summary": "Runtime orchestrator remains the shared recovery owner.",
                        "category": "dependency",
                        "position": "preserve",
                        "project_scope": "cross-project",
                        "project_id": "runtime-orchestrator",
                        "citation_refs": [
                            "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                        ],
                    },
                ],
            },
            {
                "sequence": 2,
                "call_id": "call-2",
                "phase": "planning",
                "output_ref": "REQ-034::call::call-2::output::execution_plan",
                "memory_items": [
                    {
                        "memory_id": "memory.scope-guard",
                        "summary": "Planning keeps the scope locked to the target project.",
                        "category": "guardrail",
                        "position": "preserve",
                        "project_scope": "local",
                        "project_id": "",
                        "citation_refs": [
                            "reports/optimus-prime/planning/evidence/TASK-118/TASK_EVIDENCE.json",
                        ],
                    },
                    {
                        "memory_id": "memory.runtime-envelope",
                        "summary": "Planning still routes shared recovery changes through runtime orchestrator.",
                        "category": "dependency",
                        "position": "preserve",
                        "project_scope": "cross-project",
                        "project_id": "runtime-orchestrator",
                        "citation_refs": [
                            "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                        ],
                    },
                ],
            },
        ],
        "candidate_recommendations": [
            {
                "recommendation_id": "rec.local-diagnostics",
                "summary": "Keep local diagnostics replay-stable across later calls.",
                "rationale": "The local scope guard remains evidence-backed across the handoff window.",
                "recommendation_scope": "local",
                "project_id": "",
                "requires_earth_evidence": False,
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-118/TASK_EVIDENCE.json",
                ],
                "next_step": "Attach the same deterministic diagnostics packet to each later call.",
                "synthesized_from_call_sequence": 2,
                "memory_anchor_ids": ["memory.scope-guard"],
            },
            {
                "recommendation_id": "rec.runtime-sync",
                "summary": "Coordinate the shared recovery envelope with runtime orchestrator.",
                "rationale": "The bounded handoff window keeps the runtime dependency stable.",
                "recommendation_scope": "cross-project",
                "project_id": "runtime-orchestrator",
                "requires_earth_evidence": True,
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                ],
                "next_step": "Open the runtime follow-up with Earth evidence attached.",
                "synthesized_from_call_sequence": 2,
                "memory_anchor_ids": ["memory.runtime-envelope"],
            },
        ],
    }


def test_req_034_builder_emits_contract_valid_memory_handoff_payload() -> None:
    payload = module.build_req_034_cross_call_memory_handoff_contract(**_base_input())

    assert module.validate_req_034_cross_call_memory_handoff_contract(payload) == []
    assert payload["schema_version"] == module.REQ_034_SCHEMA_VERSION
    assert payload["requirement_id"] == module.REQ_034_REQUIREMENT_ID
    assert payload["analysis_type"] == module.REQ_034_ANALYSIS_TYPE

    processing = payload["processing_behavior"]
    recommendation = processing["recommendation"]

    assert processing["strategy"] == module.REQ_034_PROCESSING_STRATEGY
    assert processing["reasoning_mode"] == module.REQ_034_REASONING_MODE
    assert recommendation["decision"] == "proceed"
    assert processing["context_usage"]["active_memory_ids"] == [
        "memory.runtime-envelope",
        "memory.scope-guard",
    ]
    assert processing["context_usage"]["recommended_action_ids_emitted"] == ["rec.local-diagnostics"]
    assert processing["context_usage"]["cross_project_obligation_ids_emitted"] == [
        "obligation-rec.runtime-sync"
    ]
    assert recommendation["open_risks"] == []


def test_req_034_memory_anchor_ids_must_match_schema() -> None:
    invalid_input = _base_input()
    invalid_input["candidate_recommendations"] = [
        {
            **invalid_input["candidate_recommendations"][0],
            "memory_anchor_ids": ["MEMORY-INVALID"],
        }
    ]

    try:
        module.build_req_034_cross_call_memory_handoff_contract(**invalid_input)
    except module.Req034Error as exc:
        assert "candidate_recommendations[0].memory_anchor_ids entries must match" in str(exc)
    else:
        raise AssertionError("expected Req034Error for invalid memory anchor id schema")


def test_req_034_builder_emits_bounded_cited_memory_handoff() -> None:
    fixture = _read_json(FIXTURE_PATH)

    payload = module.build_req_034_cross_call_memory_handoff_contract(**fixture["input"])

    assert module.validate_req_034_cross_call_memory_handoff_contract(payload) == []

    anchors = fixture["expected_contract_anchors"]
    handoff = payload["cross_call_memory_handoff"]
    usage = payload["processing_behavior"]["context_usage"]

    assert payload["schema_version"] == anchors["schema_version"]
    assert payload["requirement_id"] == anchors["requirement_id"]
    assert payload["checked_at_utc"] == anchors["checked_at_utc"]
    assert payload["call_id"] == anchors["call_id"]
    assert handoff["target_project"]["project_id"] == anchors["project_id"]
    assert handoff["source_calls"] == anchors["source_calls"]
    assert [row["memory_id"] for row in handoff["handoff_items"]] == anchors["retained_memory_ids"]
    assert handoff["bounded_context"]["citation_ref_count"] == anchors["citation_ref_count"]
    assert handoff["summary"] == anchors["summary"]
    assert payload["processing_behavior"]["strategy"] == anchors["processing_strategy"]
    assert payload["processing_behavior"]["reasoning_mode"] == anchors["reasoning_mode"]
    assert usage["superseded_memory_ids"] == anchors["superseded_memory_ids"]
    assert usage["allowed_context_refs_used"] == anchors["allowed_context_refs_used"]
    assert usage["open_risk_ids_emitted"] == []

    for row in handoff["handoff_items"]:
        assert row["carry_forward"] is True
        assert len(row["citation_refs"]) <= handoff["bounded_context"]["max_citation_refs_per_entry"]


def test_req_034_sample_and_contract_doc_are_aligned() -> None:
    sample = _read_json(SAMPLE_PATH)
    assert module.validate_req_034_cross_call_memory_handoff_contract(sample) == []

    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-034_cross-call-memory-handoff-contract.sample.json" in contract_text


def test_req_034_blocks_contradiction_drift_without_explicit_supersession() -> None:
    fixture = _read_json(FIXTURE_PATH)
    runtime_item = fixture["input"]["prior_call_memory"][2]["handoff_items"][0]
    runtime_item["position"] = "keep-local-runtime-only"
    runtime_item["supersedes_memory_ids"] = []

    payload = module.build_req_034_cross_call_memory_handoff_contract(**fixture["input"])

    assert module.validate_req_034_cross_call_memory_handoff_contract(payload) == []
    assert any(
        row["reason_code"] == "contradiction_drift_prevented"
        for row in payload["processing_behavior"]["diagnostics"]["open_risks"]
    )
    assert "mem.runtime-dependency.v2" not in payload["processing_behavior"]["context_usage"]["retained_memory_ids"]


def test_req_034_blocks_context_leakage_outside_allowed_refs() -> None:
    fixture = _read_json(FIXTURE_PATH)
    fixture["input"]["prior_call_memory"][1]["handoff_items"][0]["citation_refs"] = [
        "REQ-027::call::call-2::output::constraint_refinement",
        "reports/unbounded/leak.json",
    ]

    payload = module.build_req_034_cross_call_memory_handoff_contract(**fixture["input"])

    assert module.validate_req_034_cross_call_memory_handoff_contract(payload) == []
    assert any(
        row["reason_code"] == "context_leakage_prevented"
        for row in payload["processing_behavior"]["diagnostics"]["open_risks"]
    )
    assert "mem.scope-lock.v1" not in payload["processing_behavior"]["context_usage"]["retained_memory_ids"]
