import copy
import json
from pathlib import Path

from scripts import strategy_context_sweep as module

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "research-packet-ingestion-and-normalization.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_008_hardening_detects_stale_source_artifact_during_earth_sweep():
    fixture = _read_json(FIXTURE_PATH)
    test_input = copy.deepcopy(fixture["input"])

    for evidence_row in test_input["research_packet"]["evidence_refs"]:
        if evidence_row["artifact_id"] == "artifact.dispatch-cycle-canary-20260314":
            evidence_row["status"] = "stale"

    payload = module.build_req_008_research_packet_ingestion_and_normalization(**test_input)
    assert module.validate_req_008_research_packet_ingestion_and_normalization(payload) == []

    by_target = {
        row.get("target_project_id"): row
        for row in payload["strategy_context"]["open_risks"]
        if isinstance(row, dict)
    }
    stale_row = by_target["prj.runtime-core"]
    assert stale_row["reason_code"] == module.REASON_CODE_EARTH_SWEEP_STALE_SOURCE_ARTIFACT
    assert stale_row["evidence_refs"]
    assert {ref["artifact_id"] for ref in stale_row["evidence_refs"]} == {
        "artifact.dispatch-cycle-canary-20260314"
    }


def test_req_008_hardening_emits_reason_codes_for_missing_context_or_peer_docs():
    fixture = _read_json(FIXTURE_PATH)
    test_input = copy.deepcopy(fixture["input"])

    test_input["research_packet"]["context"]["mission_refs"] = [
        "docs/does-not-exist-mission.md"
    ]
    cross_project_obligation = test_input["research_packet"]["context"]["broad_sweep_context"][
        "cross_project_obligations"
    ][0]
    cross_project_obligation["peer_project_doc_refs"] = [
        "docs/does-not-exist-peer-project.md"
    ]

    payload = module.build_req_008_research_packet_ingestion_and_normalization(**test_input)
    assert module.validate_req_008_research_packet_ingestion_and_normalization(payload) == []

    reason_codes = {
        row["reason_code"]
        for row in payload["strategy_context"]["open_risks"]
        if isinstance(row, dict) and row.get("reason_code")
    }
    assert module.REASON_CODE_CONTEXT_DOC_MISSING in reason_codes
    assert module.REASON_CODE_PEER_PROJECT_DOC_MISSING in reason_codes

    for row in payload["strategy_context"]["open_risks"]:
        if not isinstance(row, dict):
            continue
        if row.get("reason_code") in {
            module.REASON_CODE_CONTEXT_DOC_MISSING,
            module.REASON_CODE_PEER_PROJECT_DOC_MISSING,
        }:
            assert row["evidence_refs"]


def test_req_008_hardening_replay_context_bundle_serialization_is_stable():
    fixture = _read_json(FIXTURE_PATH)
    test_input = copy.deepcopy(fixture["input"])
    test_input.pop("normalized_at_utc", None)

    payload_first = module.build_req_008_research_packet_ingestion_and_normalization(**copy.deepcopy(test_input))
    payload_second = module.build_req_008_research_packet_ingestion_and_normalization(**copy.deepcopy(test_input))

    bundle_first = module.serialize_req_008_context_bundle(payload_first)
    bundle_second = module.serialize_req_008_context_bundle(payload_second)

    assert bundle_first == bundle_second
    assert payload_first["source"]["context_bundle_sha256"] == payload_second["source"]["context_bundle_sha256"]
