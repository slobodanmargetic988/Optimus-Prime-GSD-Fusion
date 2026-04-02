import json
import subprocess
import sys
from pathlib import Path

from scripts import strategy_llm_pipeline as pipeline


def test_req039_builder_matches_sample_and_validates() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    fixture_path = repo_root / "examples" / "fixtures" / "recommendation-rationale-quality-scoring.json"
    sample_path = (
        repo_root
        / "strategy"
        / "current"
        / "samples"
        / "REQ-039_recommendation-rationale-quality-scoring.sample.json"
    )

    fixture_payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    built_payload = pipeline.build_req_039_recommendation_rationale_quality_scoring(fixture_payload)
    sample_payload = json.loads(sample_path.read_text(encoding="utf-8"))

    assert pipeline.validate_req_039_recommendation_rationale_quality_scoring(built_payload) == []
    assert pipeline.validate_req_039_recommendation_rationale_quality_scoring(sample_payload) == []
    assert built_payload == sample_payload


def test_req039_rejects_low_substance_recommendations_before_packet_emission() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    fixture_path = repo_root / "examples" / "fixtures" / "recommendation-rationale-quality-scoring.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    out = pipeline.build_req_039_recommendation_rationale_quality_scoring(payload)
    scoring = out["recommendation_rationale_quality_scoring"]

    accepted_ids = {row["recommendation_id"] for row in scoring["accepted_recommendations"]}
    rejected = {
        row["recommendation_id"]: row["rejection_reason_codes"]
        for row in scoring["rejected_recommendations"]
    }
    status_by_id = {
        row["recommendation_id"]: (row["quality_status"], row["quality_score"])
        for row in scoring["scored_recommendations"]
    }

    assert accepted_ids == {"rec.req-039.contract-surface-evidence"}
    assert rejected == {
        "rec.req-039.packet-emission-tradeoffs": ["missing_explicit_tradeoffs"],
        "rec.req-039.quick-win-claim": ["insufficient_evidence_refs"],
    }
    assert status_by_id["rec.req-039.contract-surface-evidence"] == ("accepted", 4)
    assert status_by_id["rec.req-039.packet-emission-tradeoffs"] == ("rejected", 2)
    assert status_by_id["rec.req-039.quick-win-claim"] == ("rejected", 3)
    assert accepted_ids.isdisjoint(rejected)


def test_req039_contract_doc_references_sample_structure() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    contract_path = (
        repo_root
        / "contracts"
        / "req"
        / "REQ-039_recommendation-rationale-quality-scoring.md"
    )
    contract_text = contract_path.read_text(encoding="utf-8")

    assert (
        "strategy/current/samples/REQ-039_recommendation-rationale-quality-scoring.sample.json"
        in contract_text
    )


def test_req039_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    fixture_path = repo_root / "examples" / "fixtures" / "recommendation-rationale-quality-scoring.json"
    sample_path = (
        repo_root
        / "strategy"
        / "current"
        / "samples"
        / "REQ-039_recommendation-rationale-quality-scoring.sample.json"
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
