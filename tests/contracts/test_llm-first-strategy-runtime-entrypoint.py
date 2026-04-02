import json
from pathlib import Path

from scripts import strategy_context_sweep as module

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "llm-first-strategy-runtime-entrypoint.json"
SAMPLE_PATH = REPO_ROOT / "strategy" / "current" / "samples" / "REQ-001_llm-first-strategy-runtime-entrypoint.sample.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_001_builder_matches_fixture_expected_payload():
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_001_runtime_entrypoint(**fixture["input"])
    assert module.validate_req_001_runtime_entrypoint(payload) == []
    assert payload == fixture["expected_payload"]


def test_req_001_call_metadata_is_reproducible_for_identical_invocations():
    fixture = _read_json(FIXTURE_PATH)
    first = module.build_req_001_runtime_entrypoint(**fixture["input"])
    second = module.build_req_001_runtime_entrypoint(**fixture["input"])
    assert first["call_metadata"] == second["call_metadata"]

    changed_revision_input = dict(fixture["input"])
    changed_revision_input["revision_identity"] = "rev-req001-fixture-r2"
    changed = module.build_req_001_runtime_entrypoint(**changed_revision_input)
    assert changed["call_metadata"]["canonical_input_sha256"] != first["call_metadata"]["canonical_input_sha256"]
    assert changed["call_metadata"]["reproducible_call_id"] != first["call_metadata"]["reproducible_call_id"]


def test_req_001_sample_payload_is_valid_contract_shape():
    sample = _read_json(SAMPLE_PATH)
    assert module.validate_req_001_runtime_entrypoint(sample) == []
    assert sample["strategy_runtime_entrypoint"]["runtime_mode"] == module.RUNTIME_MODE
    assert sample["strategy_runtime_entrypoint"]["execution_mode"] == module.EXECUTION_MODE
    assert sample["processing_behavior"]["strategy"] == "llm-first-broad-sweep"
    assert sample["processing_behavior"]["reasoning_mode"] == module.EXECUTION_MODE
    assert sample["requirement_id"] == module.REQUIREMENT_ID


def test_req_001_cli_writes_valid_payload(tmp_path: Path):
    out_path = tmp_path / "req001-payload.json"
    exit_code = module.main(
        [
            "--target-project-root",
            "/opt/optimus-prime/project-root",
            "--earth-root",
            "/opt/optimus-prime/Earth",
            "--output-root",
            "/opt/optimus-prime/project-root/strategy-out",
            "--revision-identity",
            "rev-req001-cli-r1",
            "--output-path",
            str(out_path),
        ]
    )
    assert exit_code == 0
    payload = _read_json(out_path)
    assert module.validate_req_001_runtime_entrypoint(payload) == []
    assert payload["strategy_runtime_entrypoint"]["execution_mode"] == "long-thinking"
    assert payload["processing_behavior"]["heuristic_summarization_only"] is False
    assert payload["processing_behavior"]["recommendation"]["decision"] == "insufficient-context"
