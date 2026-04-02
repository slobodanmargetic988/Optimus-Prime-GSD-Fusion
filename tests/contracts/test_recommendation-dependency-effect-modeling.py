import json
import subprocess
import sys
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "recommendation-dependency-effect-modeling.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-041_recommendation-dependency-effect-modeling.sample.json"
)
CONTRACT_DOC_PATH = (
    REPO_ROOT
    / "contracts"
    / "req"
    / "REQ-041_recommendation-dependency-effect-modeling.md"
)
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_llm_pipeline.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_041_models_dependency_effects_across_affected_projects() -> None:
    fixture = _read_json(FIXTURE_PATH)

    payload = module.build_req_041_recommendation_dependency_effect_modeling(
        target_project_root=fixture["target_project_root"],
        earth_root=fixture["earth_root"],
        output_root=fixture["output_root"],
        revision_identity=fixture["revision_identity"],
        recommendations=fixture["recommendations"],
        modeled_at="2026-03-16T12:45:00Z",
    )

    assert module.validate_req_041_recommendation_dependency_effect_modeling(payload) == []
    assert set(payload.keys()) == {
        "requirement_id",
        "surface",
        "schema_version",
        "recommendation_dependency_effect_modeling_entrypoint",
        "processing_behavior",
        "call_metadata",
        "modeled_at",
        "dependency_effect_models",
        "evidence_refs",
        "summary",
    }
    assert payload["requirement_id"] == "REQ-041"
    assert payload["surface"] == "recommendation_dependency_effect_modeling"
    assert payload["schema_version"] == "req-041.recommendation-dependency-effect-modeling.v1"

    models = payload["dependency_effect_models"]
    assert [row["recommendation_id"] for row in models] == [
        "rec.recommendation-evidence-fanout",
        "rec.runtime-contract-alignment",
    ]

    first_model = models[0]
    assert first_model["affected_project_count"] == 1
    assert first_model["blocker_count"] == 2
    assert first_model["mitigation_hook_count"] == 2
    assert first_model["highest_blocker_severity"] == "critical"
    assert first_model["affected_project_ids"] == ["shared-observability"]

    first_effect = first_model["affected_project_effects"][0]
    assert first_effect["project_id"] == "shared-observability"
    assert first_effect["effect_type"] == "evidence_fanout"
    assert [row["blocker_id"] for row in first_effect["likely_blockers"]] == [
        "blocker.missing-evidence-lineage",
        "blocker.telemetry-tag-gap",
    ]
    assert [row["hook_id"] for row in first_effect["mitigation_hooks"]] == [
        "hook.lineage-export-replay",
        "hook.telemetry-tag-schema-check",
    ]

    second_model = models[1]
    assert second_model["affected_project_ids"] == [
        "ground-control-hub",
        "runtime-orchestrator",
    ]
    assert second_model["highest_blocker_severity"] == "high"

    assert payload["summary"] == {
        "recommendation_count": 2,
        "affected_project_count": 3,
        "likely_blocker_count": 4,
        "mitigation_hook_count": 4,
        "highest_blocker_severity": "critical",
    }

    call_metadata = payload["call_metadata"]
    assert call_metadata["reproducibility"] == "deterministic-input-fingerprint"
    assert call_metadata["llm_call_trace_schema_version"] == (
        "req-041.recommendation-dependency-effect-modeling.trace-row.v1"
    )
    assert call_metadata["llm_call_trace_path"] == "strategy/current/llm_call_trace.jsonl"
    assert len(call_metadata["llm_call_trace_rows"]) == 2


def test_req_041_validator_rejects_missing_mitigation_hooks() -> None:
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_041_recommendation_dependency_effect_modeling(
        target_project_root=fixture["target_project_root"],
        earth_root=fixture["earth_root"],
        output_root=fixture["output_root"],
        revision_identity=fixture["revision_identity"],
        recommendations=fixture["recommendations"],
        modeled_at="2026-03-16T12:45:00Z",
    )
    payload["dependency_effect_models"][0]["affected_project_effects"][0]["mitigation_hooks"] = []
    payload["dependency_effect_models"][0]["affected_project_effects"][0]["mitigation_hook_count"] = 0

    errors = module.validate_req_041_recommendation_dependency_effect_modeling(payload)
    assert (
        "dependency_effect_models[0].affected_project_effects[0].mitigation_hooks must be a non-empty array"
        in errors
    )


def test_req_041_sample_matches_builder_output_for_fixture() -> None:
    fixture = _read_json(FIXTURE_PATH)
    expected = module.build_req_041_recommendation_dependency_effect_modeling(
        target_project_root=fixture["target_project_root"],
        earth_root=fixture["earth_root"],
        output_root=fixture["output_root"],
        revision_identity=fixture["revision_identity"],
        recommendations=fixture["recommendations"],
        modeled_at="2026-03-16T12:45:00Z",
    )

    assert _read_json(SAMPLE_PATH) == expected


def test_req_041_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
    fixture = _read_json(FIXTURE_PATH)
    fixture["modeled_at"] = "2026-03-16T12:45:00Z"

    input_json = tmp_path / "req041-input.json"
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
    assert out["requirement_id"] == "REQ-041"
    assert out["surface"] == "recommendation_dependency_effect_modeling"
    assert len(out["dependency_effect_models"]) == 2
    assert out["call_metadata"]["llm_call_trace_artifact"]["relative_path"] == "strategy/current/llm_call_trace.jsonl"


def test_req_041_contract_doc_records_sample_structure() -> None:
    doc_text = CONTRACT_DOC_PATH.read_text(encoding="utf-8")

    assert "REQ-041 Recommendation Dependency-Effect Modeling" in doc_text
    assert "strategy/current/samples/REQ-041_recommendation-dependency-effect-modeling.sample.json" in doc_text
    assert "dependency_effect_models" in doc_text
    assert "mitigation_hooks" in doc_text
