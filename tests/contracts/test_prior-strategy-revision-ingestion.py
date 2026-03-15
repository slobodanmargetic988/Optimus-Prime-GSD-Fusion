import json
from pathlib import Path

import pytest

from scripts import strategy_context_sweep as module

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "prior-strategy-revision-ingestion.json"
SAMPLE_PATH = REPO_ROOT / "strategy" / "current" / "samples" / "REQ-009_prior-strategy-revision-ingestion.sample.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_009_builder_matches_fixture_expected_payload():
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_009_prior_strategy_revision_ingestion(**fixture["input"])
    assert module.validate_req_009_prior_strategy_revision_ingestion(payload) == []
    assert payload == fixture["expected_payload"]


def test_req_009_call_metadata_is_reproducible_for_identical_invocations():
    fixture = _read_json(FIXTURE_PATH)
    first = module.build_req_009_prior_strategy_revision_ingestion(**fixture["input"])
    second = module.build_req_009_prior_strategy_revision_ingestion(**fixture["input"])
    assert first["call_metadata"] == second["call_metadata"]

    changed_revision_input = dict(fixture["input"])
    changed_revision_input["current_revision_identity"] = "rev-req009-fixture-r5"
    changed = module.build_req_009_prior_strategy_revision_ingestion(**changed_revision_input)
    assert changed["call_metadata"]["canonical_input_sha256"] != first["call_metadata"]["canonical_input_sha256"]
    assert changed["call_metadata"]["reproducible_call_id"] != first["call_metadata"]["reproducible_call_id"]


def test_req_009_sample_payload_is_valid_contract_shape():
    sample = _read_json(SAMPLE_PATH)
    assert module.validate_req_009_prior_strategy_revision_ingestion(sample) == []
    assert sample["requirement_id"] == module.REQ_009_REQUIREMENT_ID
    assert sample["schema_version"] == module.REQ_009_SCHEMA_VERSION
    assert sample["prior_strategy_revision_ingestion"]["analysis"]["composition_context"]["prior_revision_count"] >= 1


def test_req_009_rejects_duplicate_prior_revision_identity():
    fixture = _read_json(FIXTURE_PATH)
    duplicate = dict(fixture["input"]["prior_strategy_revisions"][0])
    bad_input = dict(fixture["input"])
    bad_input["prior_strategy_revisions"] = list(fixture["input"]["prior_strategy_revisions"]) + [duplicate]

    with pytest.raises(ValueError, match="revision_identity must be unique"):
        module.build_req_009_prior_strategy_revision_ingestion(**bad_input)
