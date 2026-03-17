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
      "reports/unbounded/leak.json"
    ]

    payload = module.build_req_034_cross_call_memory_handoff_contract(**fixture["input"])

    assert module.validate_req_034_cross_call_memory_handoff_contract(payload) == []
    assert any(
        row["reason_code"] == "context_leakage_prevented"
        for row in payload["processing_behavior"]["diagnostics"]["open_risks"]
    )
    assert "mem.scope-lock.v1" not in payload["processing_behavior"]["context_usage"]["retained_memory_ids"]
