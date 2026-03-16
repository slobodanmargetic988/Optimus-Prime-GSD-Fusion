import json
import subprocess
import sys
from pathlib import Path

from scripts import strategy_llm_pipeline as pipeline


def test_req027_builder_matches_sample_and_validates() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    fixture_path = repo_root / "examples" / "fixtures" / "call-2-ecosystem-linkage-reasoning.json"
    sample_path = (
        repo_root
        / "strategy"
        / "current"
        / "samples"
        / "REQ-027_call-2-ecosystem-linkage-reasoning.sample.json"
    )

    fixture_payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    built_payload = pipeline.build_req_027_call_2_ecosystem_linkage_reasoning(fixture_payload)
    sample_payload = json.loads(sample_path.read_text(encoding="utf-8"))

    assert pipeline.validate_req_027_call_2_ecosystem_linkage_reasoning(built_payload) == []
    assert pipeline.validate_req_027_call_2_ecosystem_linkage_reasoning(sample_payload) == []
    assert built_payload == sample_payload


def test_req027_contract_doc_references_sample_structure() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    contract_path = repo_root / "contracts" / "req" / "REQ-027_call-2-ecosystem-linkage-reasoning.md"
    contract_text = contract_path.read_text(encoding="utf-8")

    assert (
        "strategy/current/samples/REQ-027_call-2-ecosystem-linkage-reasoning.sample.json"
        in contract_text
    )


def test_req027_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    fixture_path = repo_root / "examples" / "fixtures" / "call-2-ecosystem-linkage-reasoning.json"
    sample_path = (
        repo_root
        / "strategy"
        / "current"
        / "samples"
        / "REQ-027_call-2-ecosystem-linkage-reasoning.sample.json"
    )
    script_path = repo_root / "scripts" / "strategy_llm_pipeline.py"

    fixture_payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    input_json = tmp_path / "input.json"
    input_json.write_text(json.dumps(fixture_payload), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(script_path), "--input-json", str(input_json)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    expected = json.loads(sample_path.read_text(encoding="utf-8"))
    assert out == expected

