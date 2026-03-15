import json
from pathlib import Path

from scripts import strategy_context_sweep as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "evidence-provenance-ledger-for-context.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-021_evidence-provenance-ledger-for-context.sample.json"
)
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-021_evidence-provenance-ledger-for-context.md"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_021_builder_matches_expected_contract_anchors() -> None:
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_021_evidence_provenance_ledger_for_context(**fixture["input"])
    anchors = fixture["expected_contract_anchors"]

    assert module.validate_req_021_evidence_provenance_ledger_for_context(payload) == []
    assert payload["schema_version"] == anchors["schema_version"]
    assert payload["requirement_id"] == anchors["requirement_id"]
    assert payload["processing_behavior"]["strategy"] == anchors["strategy"]
    assert payload["provenance_ledger"]["claim_ids"] == anchors["claim_ids"]
    assert payload["processing_behavior"]["recommendation"]["decision"] == anchors["decision"]

    peer_claim = next(
        row for row in payload["provenance_ledger"]["claims"] if row["claim_id"] == "claim-peer-runtime"
    )
    assert [row["status"] for row in peer_claim["source_artifacts"]] == anchors["peer_claim_source_statuses"]


def test_req_021_call_metadata_is_reproducible_for_identical_invocations() -> None:
    fixture = _read_json(FIXTURE_PATH)

    first = module.build_req_021_evidence_provenance_ledger_for_context(**fixture["input"])
    second = module.build_req_021_evidence_provenance_ledger_for_context(**fixture["input"])
    assert first["call_metadata"] == second["call_metadata"]

    changed_input = dict(fixture["input"])
    changed_input["context_claims"] = [
        *fixture["input"]["context_claims"],
        fixture["determinism_probe"]["append_context_claim"],
    ]
    changed = module.build_req_021_evidence_provenance_ledger_for_context(**changed_input)

    assert changed["call_metadata"]["canonical_input_sha256"] == first["call_metadata"]["canonical_input_sha256"]
    assert changed["call_metadata"]["reproducible_call_id"] == first["call_metadata"]["reproducible_call_id"]
    assert changed["call_metadata"]["processing_input_sha256"] != first["call_metadata"]["processing_input_sha256"]
    assert changed["provenance_ledger"]["claim_count"] == first["provenance_ledger"]["claim_count"] + 1


def test_req_021_sample_payload_and_contract_doc_are_aligned() -> None:
    sample = _read_json(SAMPLE_PATH)
    assert module.validate_req_021_evidence_provenance_ledger_for_context(sample) == []

    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-021_evidence-provenance-ledger-for-context.sample.json" in contract_text
