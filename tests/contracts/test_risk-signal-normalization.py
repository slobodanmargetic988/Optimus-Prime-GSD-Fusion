import json
from pathlib import Path

from scripts import strategy_context_sweep as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "risk-signal-normalization.json"
SAMPLE_PATH = REPO_ROOT / "strategy" / "current" / "samples" / "REQ-020_risk-signal-normalization.sample.json"
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-020_risk-signal-normalization.md"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_020_builder_normalizes_risk_signals_with_taxonomy_compatibility():
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_020_risk_signal_normalization(**fixture["input"])
    assert module.validate_req_020_risk_signal_normalization(payload) == []

    anchors = fixture["expected_contract_anchors"]
    assert payload["schema_version"] == anchors["schema_version"]
    assert payload["requirement_id"] == anchors["requirement_id"]
    assert payload["risk_signal_normalization"]["normalized_at_utc"] == anchors["normalized_at_utc"]

    normalization = payload["risk_signal_normalization"]
    assert [row["normalized_signal_id"] for row in normalization["signals"]] == anchors["normalized_signal_ids"]
    assert normalization["reason_code_taxonomy"]["canonical_reason_codes"] == anchors["canonical_reason_codes"]
    assert normalization["reason_code_taxonomy"]["source_reason_code_aliases_applied"] == anchors["alias_pairs"]

    summary = normalization["summary"]
    assert summary["source_counts"] == anchors["source_counts"]
    assert summary["severity_counts"] == anchors["severity_counts"]
    assert summary["total_input_signals"] == anchors["total_input_signals"]
    assert summary["total_normalized_signals"] == anchors["total_normalized_signals"]

    metadata = payload["call_metadata"]
    assert metadata["canonical_input_sha256"] == anchors["canonical_input_sha256"]
    assert metadata["reproducible_call_id"] == anchors["reproducible_call_id"]


def test_req_020_builder_is_deterministic_when_normalized_at_utc_is_omitted():
    fixture = _read_json(FIXTURE_PATH)
    omitted_timestamp_input = dict(fixture["input"])
    omitted_timestamp_input.pop("normalized_at_utc")

    payload_a = module.build_req_020_risk_signal_normalization(**omitted_timestamp_input)
    payload_b = module.build_req_020_risk_signal_normalization(**omitted_timestamp_input)
    assert payload_a == payload_b
    assert module.validate_req_020_risk_signal_normalization(payload_a) == []
    assert (
        payload_a["risk_signal_normalization"]["normalized_at_utc"]
        == fixture["expected_contract_anchors"]["derived_normalized_at_utc_when_omitted"]
    )


def test_req_020_builder_uses_deterministic_fallback_when_observed_timestamps_are_missing():
    payload = module.build_req_020_risk_signal_normalization(
        risk_signals=[
            {
                "signal_source": "retry",
                "reason_code": "retry_exhausted",
                "summary": "Retry budget exhausted without observed timestamps.",
                "severity": "medium",
                "occurrence_count": 1,
                "evidence_refs": ["reports/optimus-prime/retries/no-observed-timestamp.json"],
            }
        ]
    )
    assert module.validate_req_020_risk_signal_normalization(payload) == []
    assert payload["risk_signal_normalization"]["normalized_at_utc"] == module.REQ_020_FALLBACK_NORMALIZED_AT_UTC


def test_req_020_validator_reports_alias_row_field_errors_without_throwing():
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_020_risk_signal_normalization(**fixture["input"])
    payload["risk_signal_normalization"]["reason_code_taxonomy"]["source_reason_code_aliases_applied"] = [
        {
            "source_reason_code": 17,
            "normalized_reason_code": {"invalid": True},
        }
    ]

    errors = module.validate_req_020_risk_signal_normalization(payload)
    assert errors
    assert (
        "risk_signal_normalization.reason_code_taxonomy.source_reason_code_aliases_applied[0].source_reason_code"
        " must be a string when provided"
    ) in errors
    assert (
        "risk_signal_normalization.reason_code_taxonomy.source_reason_code_aliases_applied[0].normalized_reason_code"
        " must be a string when provided"
    ) in errors


def test_req_020_sample_payload_and_contract_doc_are_aligned():
    sample = _read_json(SAMPLE_PATH)
    assert module.validate_req_020_risk_signal_normalization(sample) == []

    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-020_risk-signal-normalization.sample.json" in contract_text


def test_req_020_cli_writes_contract_valid_payload(tmp_path: Path):
    fixture = _read_json(FIXTURE_PATH)
    input_path = tmp_path / "req020-input.json"
    input_path.write_text(json.dumps(fixture["input"], indent=2) + "\n", encoding="utf-8")

    output_path = tmp_path / "req020-output.json"
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
    assert module.validate_req_020_risk_signal_normalization(output_payload) == []
    assert output_payload["requirement_id"] == module.REQ_020_REQUIREMENT_ID
    assert output_payload["schema_version"] == module.REQ_020_SCHEMA_VERSION
