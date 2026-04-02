import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "strategy-md-generator.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-048_strategy-md-generator.sample.json"
)
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-048_strategy-md-generator.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_artifacts_handoff.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_048_builder_matches_sample_and_validates() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    sample_payload = _read_json(SAMPLE_PATH)

    built_payload = module.build_req_048_strategy_md_generator(fixture_payload)

    assert module.validate_req_048_strategy_md_generator(built_payload) == []
    assert module.validate_req_048_strategy_md_generator(sample_payload) == []
    assert built_payload == sample_payload
    assert built_payload["strategy_md"]["artifact_path"] == "STRATEGY.md"
    assert built_payload["totals"]["final_recommendations"] == 2
    assert built_payload["totals"]["multi_call_trace_rows"] == 3


def test_req_048_strategy_markdown_is_diff_friendly_and_machine_aligned() -> None:
    payload = _read_json(SAMPLE_PATH)
    strategy_md = payload["strategy_md"]
    markdown = strategy_md["markdown"]
    alignment = strategy_md["alignment"]

    assert markdown.startswith("# STRATEGY\n")
    for heading in (
        "## Final Recommendations",
        "## Deferred Recommendations",
        "## Open Risks",
        "## Strategy Packet Inputs",
        "## Multi-Call Trace",
        "## Machine Alignment",
    ):
        assert heading in markdown

    for key, ids in alignment.items():
        assert ids == sorted(set(ids))
        for anchor_id in ids:
            assert anchor_id in markdown, f"missing {key} anchor in markdown: {anchor_id}"

    sections = strategy_md["sections"]
    assert [row["section_id"] for row in sections] == [
        "final-recommendations",
        "deferred-recommendations",
        "open-risks",
        "strategy-packet-inputs",
        "multi-call-trace",
    ]


def test_req_048_validator_rejects_markdown_hash_drift() -> None:
    payload = _read_json(SAMPLE_PATH)
    broken = deepcopy(payload)
    broken["strategy_md"]["content_sha256"] = "deadbeef"

    errors = module.validate_req_048_strategy_md_generator(broken)

    assert "strategy_md.content_sha256 must match strategy_md.markdown" in errors


def test_req_048_contract_doc_references_documented_sample_structure() -> None:
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "strategy/current/samples/REQ-048_strategy-md-generator.sample.json" in contract_text
    for key in (
        "strategy_md.markdown",
        "strategy_md.sections",
        "strategy_md.alignment",
        "totals",
    ):
        assert key in contract_text


def test_req_048_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
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


def test_req_048_builder_rejects_missing_final_recommendations_anchor() -> None:
    fixture_payload = deepcopy(_read_json(FIXTURE_PATH))
    del fixture_payload["final_strategy_synthesis"]["final_recommendations"]

    with pytest.raises(ValueError, match=r"final_recommendations"):
        module.build_req_048_strategy_md_generator(fixture_payload)
