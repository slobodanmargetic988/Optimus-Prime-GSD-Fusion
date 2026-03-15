import json
from pathlib import Path

from scripts import strategy_context_sweep as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "strategy-context-bundle-serialization.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-024_strategy-context-bundle-serialization.sample.json"
)
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-024_strategy-context-bundle-serialization.md"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_024_builder_serializes_expected_contract_anchors():
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_024_strategy_context_bundle_serialization(**fixture["input"])
    assert module.validate_req_024_strategy_context_bundle_serialization(payload) == []

    anchors = fixture["expected_contract_anchors"]
    assert payload["schema_version"] == anchors["schema_version"]
    assert payload["requirement_id"] == anchors["requirement_id"]

    serialization = payload["strategy_context_bundle_serialization"]
    assert serialization["bundle_schema_version"] == anchors["bundle_schema_version"]
    assert serialization["serialization_format"] == anchors["serialization_format"]
    assert serialization["bundle_generated_at_utc"] == anchors["bundle_generated_at_utc"]
    assert serialization["context_bundle_sha256"] == anchors["context_bundle_sha256"]
    assert serialization["context_bundle_byte_length"] == anchors["context_bundle_byte_length"]

    stage_ids = [row["stage_id"] for row in serialization["llm_call_chain"]["stages"]]
    assert stage_ids == anchors["stage_ids"]

    bundle = json.loads(serialization["serialized_context_bundle"])
    assert [row["stage_id"] for row in bundle["llm_call_chain"]["stages"]] == anchors["stage_ids"]
    processing_behavior = bundle["strategy_context"]["processing_behavior"]
    assert processing_behavior["strategy"] == "llm-first-broad-sweep"
    assert processing_behavior["reasoning_mode"] == module.EXECUTION_MODE
    assert processing_behavior["heuristic_summarization_only"] is False
    assert processing_behavior["context_usage"]["cross_project_context_used"] is True
    assert processing_behavior["context_usage"]["cross_project_projects_considered"] == [
        "ground-control-hub",
        "runtime-orchestrator",
    ]
    recommendation = processing_behavior["recommendation"]
    assert set(recommendation.keys()) == {
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "recommended_actions",
        "cross_project_obligations",
        "open_risks",
    }
    assert recommendation["decision"] == "proceed"
    assert recommendation["confidence"] == "high"
    assert recommendation["evidence_refs"] == processing_behavior["context_usage"]["evidence_refs_used"]
    assert [row["action_id"] for row in recommendation["recommended_actions"]] == [
        "action-local-bundle-hardening",
        "action-runtime-orchestration-alignment",
    ]
    assert [row["obligation_id"] for row in recommendation["cross_project_obligations"]] == [
        "obligation-action-runtime-orchestration-alignment"
    ]
    assert recommendation["open_risks"] == []
    assert bundle["strategy_context"]["open_risks"][0]["evidence_refs"] == [
        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
        "reports/optimus-prime/planning/evidence/TASK-076/TASK_EVIDENCE.json",
    ]

    metadata = payload["call_metadata"]
    assert metadata["canonical_input_sha256"] == anchors["canonical_input_sha256"]
    assert metadata["reproducible_call_id"] == anchors["reproducible_call_id"]


def test_req_024_builder_normalizes_stage_order_and_required_context_keys_for_replay_stability():
    fixture = _read_json(FIXTURE_PATH)
    payload_a = module.build_req_024_strategy_context_bundle_serialization(**fixture["input"])

    reordered_input = json.loads(json.dumps(fixture["input"]))
    reordered_input["llm_call_chain"]["stages"] = list(reversed(reordered_input["llm_call_chain"]["stages"]))
    reordered_input["llm_call_chain"]["stages"][0]["required_context_keys"] = [
        "processing_behavior",
        "open_risks",
        "strategy_runtime_entrypoint",
        "processing_behavior",
    ]
    reordered_input["strategy_context"]["processing_behavior"]["context_inputs"]["cross_project_context"] = list(
        reversed(reordered_input["strategy_context"]["processing_behavior"]["context_inputs"]["cross_project_context"])
    )
    reordered_input["strategy_context"]["processing_behavior"]["context_inputs"]["candidate_recommendations"] = list(
        reversed(
            reordered_input["strategy_context"]["processing_behavior"]["context_inputs"]["candidate_recommendations"]
        )
    )
    payload_b = module.build_req_024_strategy_context_bundle_serialization(**reordered_input)

    assert payload_a == payload_b
    assert module.validate_req_024_strategy_context_bundle_serialization(payload_b) == []


def test_req_024_builder_uses_deterministic_timestamp_fallback_when_omitted():
    fixture = _read_json(FIXTURE_PATH)
    input_payload = dict(fixture["input"])
    input_payload.pop("bundle_generated_at_utc")

    payload = module.build_req_024_strategy_context_bundle_serialization(**input_payload)
    assert module.validate_req_024_strategy_context_bundle_serialization(payload) == []
    assert (
        payload["strategy_context_bundle_serialization"]["bundle_generated_at_utc"]
        == module.REQ_024_FALLBACK_BUNDLE_GENERATED_AT_UTC
    )


def test_req_024_validator_reports_digest_mismatch_without_throwing():
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_024_strategy_context_bundle_serialization(**fixture["input"])
    payload["strategy_context_bundle_serialization"]["context_bundle_sha256"] = "0" * 64

    errors = module.validate_req_024_strategy_context_bundle_serialization(payload)
    assert errors
    assert (
        "strategy_context_bundle_serialization.context_bundle_sha256 must match serialized_context_bundle digest"
        in errors
    )


def test_req_024_sample_payload_and_contract_doc_are_aligned():
    sample = _read_json(SAMPLE_PATH)
    assert module.validate_req_024_strategy_context_bundle_serialization(sample) == []

    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-024_strategy-context-bundle-serialization.sample.json" in contract_text


def test_req_024_cli_writes_contract_valid_payload(tmp_path: Path):
    fixture = _read_json(FIXTURE_PATH)
    cli_input = dict(fixture["input"])
    cli_input["analysis_type"] = "strategy_context_bundle_serialization"

    input_path = tmp_path / "req024-input.json"
    input_path.write_text(json.dumps(cli_input, indent=2) + "\n", encoding="utf-8")

    output_path = tmp_path / "req024-output.json"
    exit_code = module.main(
        [
            "--input-json",
            str(input_path),
            "--output-json",
            str(output_path),
            "--json-pretty",
        ]
    )
    assert exit_code == 0

    output_payload = _read_json(output_path)
    assert module.validate_req_024_strategy_context_bundle_serialization(output_payload) == []
    assert output_payload["requirement_id"] == module.REQ_024_REQUIREMENT_ID
    assert output_payload["schema_version"] == module.REQ_024_SCHEMA_VERSION
