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


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_021_builder_matches_fixture_expected_payload():
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_021_evidence_provenance_ledger_for_context(**fixture["input"])
    assert module.validate_req_021_evidence_provenance_ledger_for_context(payload) == []
    assert payload == fixture["expected_payload"]


def test_req_021_call_metadata_is_reproducible_for_identical_invocations():
    fixture = _read_json(FIXTURE_PATH)
    first = module.build_req_021_evidence_provenance_ledger_for_context(**fixture["input"])
    second = module.build_req_021_evidence_provenance_ledger_for_context(**fixture["input"])
    assert first["call_metadata"] == second["call_metadata"]

    changed_revision_input = dict(fixture["input"])
    changed_revision_input["revision_identity"] = "rev-req021-fixture-r2"
    changed = module.build_req_021_evidence_provenance_ledger_for_context(**changed_revision_input)
    assert changed["call_metadata"]["canonical_input_sha256"] != first["call_metadata"]["canonical_input_sha256"]
    assert changed["call_metadata"]["reproducible_call_id"] != first["call_metadata"]["reproducible_call_id"]


def test_req_021_sample_payload_is_valid_contract_shape():
    sample = _read_json(SAMPLE_PATH)
    assert module.validate_req_021_evidence_provenance_ledger_for_context(sample) == []
    assert sample["requirement_id"] == module.REQ_021_REQUIREMENT_ID
    assert sample["schema_version"] == module.REQ_021_SCHEMA_VERSION
    ledger = sample["evidence_provenance_ledger_for_context"]
    assert ledger["ledger_scope"] == module.REQ_021_LEDGER_SCOPE
    assert ledger["claim_count"] == len(ledger["context_claims"])


def test_req_021_validator_rejects_missing_artifact_refs_index_union_when_empty():
    fixture = _read_json(FIXTURE_PATH)
    payload = fixture["expected_payload"]
    mutated = json.loads(json.dumps(payload))
    ledger = mutated["evidence_provenance_ledger_for_context"]
    assert ledger["artifact_refs_index"]
    ledger["artifact_refs_index"] = []

    errors = module.validate_req_021_evidence_provenance_ledger_for_context(mutated)
    assert "evidence_provenance_ledger_for_context.artifact_refs_index must equal union of claim sources" in errors


def test_req_021_validator_rejects_tampered_claim_id_even_when_format_looks_valid():
    fixture = _read_json(FIXTURE_PATH)
    mutated = json.loads(json.dumps(fixture["expected_payload"]))
    first_claim = mutated["evidence_provenance_ledger_for_context"]["context_claims"][0]
    assert first_claim["claim_id"].startswith("claim-")
    first_claim["claim_id"] = "claim-000000000000"

    errors = module.validate_req_021_evidence_provenance_ledger_for_context(mutated)
    assert (
        "evidence_provenance_ledger_for_context.context_claims[0].claim_id must equal deterministic digest of claim_key plus normalized source_artifact_refs"
        in errors
    )


def test_req_021_validator_rejects_claim_id_that_does_not_match_contract_format():
    fixture = _read_json(FIXTURE_PATH)
    mutated = json.loads(json.dumps(fixture["expected_payload"]))
    mutated["evidence_provenance_ledger_for_context"]["context_claims"][0]["claim_id"] = "not-deterministic"

    errors = module.validate_req_021_evidence_provenance_ledger_for_context(mutated)
    assert (
        "evidence_provenance_ledger_for_context.context_claims[0].claim_id must match claim-<12 hex>"
        in errors
    )
