from copy import deepcopy
import json
import subprocess
import sys
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "recommendation-to-planner-mapping-artifact.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-054_recommendation-to-planner-mapping-artifact.sample.json"
)
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-054_recommendation-to-planner-mapping-artifact.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_artifacts_handoff.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_054_builder_matches_sample_and_validates() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    sample_payload = _read_json(SAMPLE_PATH)

    built_payload = module.build_req_054_recommendation_to_planner_mapping_artifact(fixture_payload)

    assert module.validate_req_054_recommendation_to_planner_mapping_artifact(built_payload) == []
    assert module.validate_req_054_recommendation_to_planner_mapping_artifact(sample_payload) == []
    assert built_payload == sample_payload


def test_req_054_mapping_rows_preserve_traceability_and_audit_anchors() -> None:
    payload = _read_json(SAMPLE_PATH)
    artifact = payload["recommendation_to_planner_mapping_artifact"]
    mappings = artifact["recommendation_to_task_intent_mappings"]
    by_recommendation: dict[str, list[dict]] = {}
    for row in mappings:
        by_recommendation.setdefault(row["recommendation_id"], []).append(row)
        audit = row["downstream_audit_trail"]
        assert audit["emitted_by_requirement_id"] == "REQ-054"
        assert audit["emitted_at_utc"] == payload["checked_at_utc"]
        assert set(audit["source_call_trace_refs"]).issubset(set(row["traceability_refs"]))
        assert set(audit["source_evidence_refs"]).issubset(set(row["traceability_refs"]))
        assert set(audit["source_packet_refs"]).issubset(set(row["traceability_refs"]))

    assert len(by_recommendation["rec.review-reuse-contracts"]) == 2
    assert artifact["recommendation_ids"] == sorted(by_recommendation.keys())
    assert artifact["planner_task_intent_handles"] == sorted(
        {row["planner_task_intent_handle"] for row in mappings}
    )


def test_req_054_validator_rejects_duplicate_recommendation_to_handle_pair() -> None:
    broken_payload = deepcopy(_read_json(SAMPLE_PATH))
    mappings = broken_payload["recommendation_to_planner_mapping_artifact"]["recommendation_to_task_intent_mappings"]
    duplicate = deepcopy(mappings[0])
    duplicate["mapping_id"] = "rtp.duplicate0001"
    mappings.append(duplicate)

    errors = module.validate_req_054_recommendation_to_planner_mapping_artifact(broken_payload)

    assert any("duplicate recommendation_id + planner_task_intent_handle pair" in error for error in errors)


def test_req_054_contract_doc_references_documented_sample_structure() -> None:
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "strategy/current/samples/REQ-054_recommendation-to-planner-mapping-artifact.sample.json" in contract_text
    for key in (
        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings",
        "recommendation_to_planner_mapping_artifact.recommendation_ids",
        "recommendation_to_planner_mapping_artifact.planner_task_intent_handles",
        "downstream_audit_trail",
        "totals",
    ):
        assert key in contract_text


def test_req_054_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    input_json = tmp_path / "input.json"
    input_json.write_text(json.dumps(fixture_payload), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--input-json", str(input_json)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0
    assert proc.stderr == ""
    assert json.loads(proc.stdout) == _read_json(SAMPLE_PATH)
