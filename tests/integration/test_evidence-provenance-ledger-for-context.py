import json
from pathlib import Path

from scripts import strategy_context_sweep as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "evidence-provenance-ledger-for-context.json"


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_req_021_claims_map_to_concrete_source_artifacts_and_evidence_refs() -> None:
    fixture = _load_fixture()
    payload = module.build_req_021_evidence_provenance_ledger_for_context(**fixture["input"])

    assert module.validate_req_021_evidence_provenance_ledger_for_context(payload) == []
    assert payload["processing_behavior"]["recommendation"]["decision"] == "ledger-ready"
    assert payload["processing_behavior"]["context_usage"]["provenance_claim_ids"] == payload["provenance_ledger"]["claim_ids"]

    for claim in payload["provenance_ledger"]["claims"]:
        assert claim["source_artifacts"]
        assert claim["evidence_refs"]
        for source_artifact in claim["source_artifacts"]:
            assert source_artifact["artifact_ref"]
            assert source_artifact["status"] in {"present", "fresh", "referenced"}
            assert source_artifact["evidence_refs"]

    peer_claim = next(row for row in payload["provenance_ledger"]["claims"] if row["claim_id"] == "claim-peer-runtime")
    peer_refs = [row["artifact_ref"] for row in peer_claim["source_artifacts"]]
    assert peer_refs == [
        "docs/runtime-orchestrator/overview.md",
        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
    ]


def test_req_021_replay_is_stable_for_reordered_claim_rows_and_duplicate_refs() -> None:
    fixture = _load_fixture()
    forward = module.build_req_021_evidence_provenance_ledger_for_context(**fixture["input"])

    reversed_input = dict(fixture["input"])
    reversed_input["target_project_evidence_refs"] = [
        fixture["input"]["target_project_evidence_refs"][0],
        fixture["input"]["target_project_evidence_refs"][0],
    ]
    reversed_input["context_claims"] = list(reversed(fixture["input"]["context_claims"]))
    reversed_payload = module.build_req_021_evidence_provenance_ledger_for_context(**reversed_input)

    assert forward == reversed_payload
    assert forward["context_bundle"]["sha256"] == reversed_payload["context_bundle"]["sha256"]
    assert json.loads(forward["context_bundle"]["canonical_json"])["provenance_ledger"]["claim_ids"] == [
        "claim-mission-authority",
        "claim-peer-runtime",
        "claim-scope-ledger",
    ]
