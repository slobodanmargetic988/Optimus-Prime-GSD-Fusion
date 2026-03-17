import json
import subprocess
import sys
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "recommendation-priority-calibration.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-038_recommendation-priority-calibration.sample.json"
)
CONTRACT_DOC_PATH = REPO_ROOT / "contracts" / "req" / "REQ-038_recommendation-priority-calibration.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_llm_pipeline.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_038_calibrates_priority_using_ecosystem_impact_feasibility_and_urgency() -> None:
    fixture = _read_json(FIXTURE_PATH)

    payload = module.build_req_038_recommendation_priority_calibration(
        target_project_root=fixture["target_project_root"],
        earth_root=fixture["earth_root"],
        output_root=fixture["output_root"],
        revision_identity=fixture["revision_identity"],
        recommendations=fixture["recommendations"],
        priority_weights=fixture["priority_weights"],
        calibrated_at="2026-03-16T12:30:00Z",
    )

    assert module.validate_req_038_recommendation_priority_calibration(payload) == []
    assert set(payload.keys()) == {
        "requirement_id",
        "surface",
        "schema_version",
        "recommendation_priority_calibration_entrypoint",
        "processing_behavior",
        "call_metadata",
        "calibrated_at",
        "priority_weights",
        "priority_calibrations",
        "evidence_refs",
        "summary",
    }

    assert payload["requirement_id"] == "REQ-038"
    assert payload["surface"] == "recommendation_priority_calibration"
    assert payload["schema_version"] == "req-038.recommendation-priority-calibration.v1"
    assert payload["priority_weights"] == {
        "ecosystem_impact": 0.5,
        "feasibility": 0.3,
        "urgency": 0.2,
    }

    ranked = payload["priority_calibrations"]
    assert [row["rank"] for row in ranked] == [1, 2, 3]
    assert [row["recommendation_id"] for row in ranked] == [
        "rec.runtime-bridge-alignment",
        "rec.contract-drift-guardrails",
        "rec.llm-trace-retention",
    ]
    assert [row["priority_score"] for row in ranked] == [7.9, 7.8, 7.2]

    top = ranked[0]
    assert top["scoring_contributors"] == {
        "ecosystem_impact": {
            "weight": 0.5,
            "score": 9.0,
            "weighted_contribution": 4.5,
        },
        "feasibility": {
            "weight": 0.3,
            "score": 6.0,
            "weighted_contribution": 1.8,
        },
        "urgency": {
            "weight": 0.2,
            "score": 8.0,
            "weighted_contribution": 1.6,
        },
    }

    assert payload["summary"] == {
        "recommendation_count": 3,
        "top_recommendation_id": "rec.runtime-bridge-alignment",
        "top_priority_score": 7.9,
        "bottom_recommendation_id": "rec.llm-trace-retention",
        "bottom_priority_score": 7.2,
        "score_spread": 0.7,
    }

    call_metadata = payload["call_metadata"]
    assert call_metadata["reproducibility"] == "deterministic-input-fingerprint"
    assert call_metadata["llm_call_trace_schema_version"] == "req-038.recommendation-priority-calibration.trace-row.v1"
    assert call_metadata["llm_call_trace_path"] == "strategy/current/llm_call_trace.jsonl"
    assert len(call_metadata["llm_call_trace_rows"]) == 3


def test_req_038_sample_matches_builder_output_for_fixture() -> None:
    fixture = _read_json(FIXTURE_PATH)
    expected = module.build_req_038_recommendation_priority_calibration(
        target_project_root=fixture["target_project_root"],
        earth_root=fixture["earth_root"],
        output_root=fixture["output_root"],
        revision_identity=fixture["revision_identity"],
        recommendations=fixture["recommendations"],
        priority_weights=fixture["priority_weights"],
        calibrated_at="2026-03-16T12:30:00Z",
    )
    assert _read_json(SAMPLE_PATH) == expected


def test_req_038_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
    fixture = _read_json(FIXTURE_PATH)
    fixture["calibrated_at"] = "2026-03-16T12:30:00Z"

    input_json = tmp_path / "req038-input.json"
    input_json.write_text(json.dumps(fixture), encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--input-json",
            str(input_json),
            "--trace-root",
            str(tmp_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out["requirement_id"] == "REQ-038"
    assert out["surface"] == "recommendation_priority_calibration"
    assert len(out["priority_calibrations"]) == 3
    assert out["call_metadata"]["llm_call_trace_artifact"]["relative_path"] == "strategy/current/llm_call_trace.jsonl"


def test_req_038_contract_doc_records_sample_structure() -> None:
    doc_text = CONTRACT_DOC_PATH.read_text(encoding="utf-8")

    assert "REQ-038 Recommendation Priority Calibration" in doc_text
    assert "strategy/current/samples/REQ-038_recommendation-priority-calibration.sample.json" in doc_text
    assert "priority_calibrations" in doc_text
    assert "scoring_contributors" in doc_text
