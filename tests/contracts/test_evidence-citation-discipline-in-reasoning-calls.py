import json
import subprocess
import sys
from pathlib import Path

from scripts import strategy_llm_pipeline as pipeline


def test_req035_builder_matches_sample_and_validates() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    fixture_path = repo_root / "examples" / "fixtures" / "evidence-citation-discipline-in-reasoning-calls.json"
    sample_path = (
        repo_root
        / "strategy"
        / "current"
        / "samples"
        / "REQ-035_evidence-citation-discipline-in-reasoning-calls.sample.json"
    )

    fixture_payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    built_payload = pipeline.build_req_035_evidence_citation_discipline_in_reasoning_calls(fixture_payload)
    sample_payload = json.loads(sample_path.read_text(encoding="utf-8"))

    assert pipeline.validate_req_035_evidence_citation_discipline_in_reasoning_calls(built_payload) == []
    assert pipeline.validate_req_035_evidence_citation_discipline_in_reasoning_calls(sample_payload) == []
    assert built_payload == sample_payload


def test_req035_flags_uncited_claims_and_excludes_from_final_recommendations() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    fixture_path = repo_root / "examples" / "fixtures" / "evidence-citation-discipline-in-reasoning-calls.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    out = pipeline.build_req_035_evidence_citation_discipline_in_reasoning_calls(payload)
    discipline = out["evidence_citation_discipline"]

    flagged_ids = {row["recommendation_id"] for row in discipline["flagged_claims"]}
    final_ids = {row["recommendation_id"] for row in discipline["final_recommendations"]}

    assert flagged_ids
    assert final_ids
    assert flagged_ids.isdisjoint(final_ids)

    reason_codes = {
        reason
        for row in discipline["flagged_claims"]
        for reason in row["flag_reason_codes"]
    }
    assert "uncited_strategic_claim" in reason_codes
    assert "evidence_id_not_in_context_provenance_ledger" in reason_codes


def test_req035_contract_doc_references_sample_structure() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    contract_path = (
        repo_root
        / "contracts"
        / "req"
        / "REQ-035_evidence-citation-discipline-in-reasoning-calls.md"
    )
    contract_text = contract_path.read_text(encoding="utf-8")

    assert (
        "strategy/current/samples/REQ-035_evidence-citation-discipline-in-reasoning-calls.sample.json"
        in contract_text
    )


def test_req035_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    fixture_path = repo_root / "examples" / "fixtures" / "evidence-citation-discipline-in-reasoning-calls.json"
    sample_path = (
        repo_root
        / "strategy"
        / "current"
        / "samples"
        / "REQ-035_evidence-citation-discipline-in-reasoning-calls.sample.json"
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
