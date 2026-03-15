import json
from pathlib import Path

from scripts import strategy_context_sweep as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "context-compaction-for-llm-call-budget.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-023_context-compaction-for-llm-call-budget.sample.json"
)
CONTRACT_PATH = (
    REPO_ROOT
    / "contracts"
    / "req"
    / "REQ-023_context-compaction-for-llm-call-budget.md"
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_023_builder_matches_sample_payload():
    fixture = _read_json(FIXTURE_PATH)
    sample = _read_json(SAMPLE_PATH)

    payload = module.build_req_023_context_compaction_for_llm_call_budget(**fixture["input"])

    assert module.validate_req_023_context_compaction_for_llm_call_budget(payload) == []
    assert payload == sample


def test_req_023_compaction_stays_bounded_and_preserves_coverage():
    sample = _read_json(SAMPLE_PATH)
    compaction = sample["processing_behavior"]["context_compaction"]
    budget = compaction["llm_call_budget"]
    coverage = compaction["coverage"]
    packets = compaction["compacted_packets"]
    hard_constraint_ids = coverage["hard_constraint_ids"]

    assert len(packets) <= budget["max_context_packets"]
    assert coverage["uncovered_action_ids"] == []
    assert coverage["uncovered_obligation_ids"] == []
    assert coverage["uncovered_risk_ids"] == []
    assert coverage["uncovered_hard_constraint_ids"] == []

    for packet in packets:
        assert len(packet["focus_points"]) <= budget["max_focus_points_per_packet"]
        assert len(packet["evidence_focus_refs"]) <= budget["max_evidence_refs_per_packet"]
        assert packet["hard_constraint_ids"] == hard_constraint_ids


def test_req_023_call_metadata_is_reproducible_for_identical_invocations():
    fixture = _read_json(FIXTURE_PATH)

    first = module.build_req_023_context_compaction_for_llm_call_budget(**fixture["input"])
    second = module.build_req_023_context_compaction_for_llm_call_budget(**fixture["input"])

    assert first["call_metadata"] == second["call_metadata"]

    changed_input = dict(fixture["input"])
    changed_input["revision_identity"] = "rev-req023-sample-r2"
    changed = module.build_req_023_context_compaction_for_llm_call_budget(**changed_input)

    assert changed["call_metadata"]["canonical_input_sha256"] != first["call_metadata"]["canonical_input_sha256"]
    assert changed["call_metadata"]["reproducible_call_id"] != first["call_metadata"]["reproducible_call_id"]


def test_req_023_contract_doc_references_sample_structure():
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "strategy/current/samples/REQ-023_context-compaction-for-llm-call-budget.sample.json" in contract_text
    assert "processing_behavior.context_compaction" in contract_text
