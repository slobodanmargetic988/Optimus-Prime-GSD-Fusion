import json
from pathlib import Path

from scripts import strategy_llm_pipeline as module

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "alternative-strategic-scenario-generator.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-045_alternative-strategic-scenario-generator.sample.json"
)
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-045_alternative-strategic-scenario-generator.md"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_045_builder_matches_fixture_expected_payload() -> None:
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_045_alternative_strategic_scenario_generator(**fixture["input"])

    assert module.validate_req_045_alternative_strategic_scenario_generator(payload) == []
    assert payload == fixture["expected_payload"]


def test_req_045_builder_is_deterministic_for_identical_invocations() -> None:
    fixture = _read_json(FIXTURE_PATH)

    first = module.build_req_045_alternative_strategic_scenario_generator(**fixture["input"])
    second = module.build_req_045_alternative_strategic_scenario_generator(**fixture["input"])

    assert first == second


def test_req_045_sample_payload_and_contract_doc_are_aligned() -> None:
    sample = _read_json(SAMPLE_PATH)

    assert module.validate_req_045_alternative_strategic_scenario_generator(sample) == []
    assert sample["schema_version"] == module.REQ_045_SCHEMA_VERSION
    assert sample["requirement_id"] == module.REQ_045_REQUIREMENT_ID
    assert sample["alternative_strategic_scenario_generator"]["comparative_summary"]["scenario_count"] == len(
        sample["alternative_strategic_scenario_generator"]["scenarios"]
    )

    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-045_alternative-strategic-scenario-generator.sample.json" in contract_text
    assert "comparative_tradeoffs" in contract_text
    assert "trigger_conditions" in contract_text


def test_req_045_cli_writes_contract_valid_payload(tmp_path: Path) -> None:
    fixture = _read_json(FIXTURE_PATH)
    input_path = tmp_path / "req045-input.json"
    input_path.write_text(json.dumps(fixture["input"], indent=2) + "\n", encoding="utf-8")

    output_path = tmp_path / "req045-output.json"
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
    assert module.validate_req_045_alternative_strategic_scenario_generator(output_payload) == []
    assert output_payload == fixture["expected_payload"]
