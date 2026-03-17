import json
import subprocess
import sys
from pathlib import Path

from scripts.strategy_validators import validate_strategy_packet


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKET_PATH = REPO_ROOT / "strategy" / "current" / "strategy_packet.v1.json"
SCHEMA_PATH = REPO_ROOT / "contracts" / "strategy_packet.v1.schema.json"
CONTEXT_PATH = REPO_ROOT / "strategy" / "current" / "strategy_packet.context.v1.json"
STABILITY_CONTRACT_PATH = REPO_ROOT / "contracts" / "recommendation_id_stability_contract.v1.json"
CLI_PATH = REPO_ROOT / "scripts" / "strategy_packet_validate.py"
FIXTURES_DIR = REPO_ROOT / "tests" / "integration" / "fixtures"


def _run_cli(packet_path: Path, *, stability_contract_path: Path = STABILITY_CONTRACT_PATH) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(CLI_PATH),
            "--input",
            str(packet_path),
            "--schema",
            str(SCHEMA_PATH),
            "--context",
            str(CONTEXT_PATH),
            "--stability-contract",
            str(stability_contract_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_req_062_validator_passes_valid_packet_and_contract() -> None:
    verdict = validate_strategy_packet(
        packet_path=PACKET_PATH,
        schema_path=SCHEMA_PATH,
        context_path=CONTEXT_PATH,
        stability_contract_path=STABILITY_CONTRACT_PATH,
    )

    assert verdict["ok"] is True
    assert verdict["verdict"] == "pass"
    assert verdict["blocking"] is False
    assert verdict["validated_requirements"] == ["REQ-056", "REQ-062"]
    assert verdict["diagnostics"] == []
    assert verdict["reason_codes"] == []
    assert verdict["gate"]["status"] == "pass"
    assert verdict["gate"]["decision"] == "allow_consume"
    assert verdict["gate"]["failing_field_paths"] == []

    proc = _run_cli(PACKET_PATH)
    assert proc.returncode == 0
    assert proc.stderr == ""
    cli_payload = json.loads(proc.stdout)
    assert cli_payload["ok"] is True
    assert cli_payload["recommendation_id_stability_contract_path"] == str(STABILITY_CONTRACT_PATH.resolve())


def test_req_062_validator_fails_duplicate_ids_with_deterministic_field_paths() -> None:
    invalid_packet = FIXTURES_DIR / "strategy_packet.req062.duplicate-id.json"

    first = validate_strategy_packet(
        packet_path=invalid_packet,
        schema_path=SCHEMA_PATH,
        context_path=CONTEXT_PATH,
        stability_contract_path=STABILITY_CONTRACT_PATH,
    )
    second = validate_strategy_packet(
        packet_path=invalid_packet,
        schema_path=SCHEMA_PATH,
        context_path=CONTEXT_PATH,
        stability_contract_path=STABILITY_CONTRACT_PATH,
    )

    assert first["ok"] is False
    assert first["verdict"] == "fail"
    assert first["blocking"] is True
    assert first["reason_codes"] == second["reason_codes"] == ["recommendation_id_collision"]
    assert first["diagnostics"] == second["diagnostics"]
    assert first["counts"]["error_count"] == 2
    assert first["gate"]["status"] == "fail"
    assert first["gate"]["decision"] == "block_consume"
    assert first["gate"]["failing_field_paths"] == [
        "recommendations[0].recommendation_id",
        "recommendations[1].recommendation_id",
    ]
    assert first["diagnostics"] == [
        {
            "severity": "error",
            "reason_code": "recommendation_id_collision",
            "field_path": "recommendations[0].recommendation_id",
            "message": "recommendation_id rec.dispatch-quality-first must be unique within revision strat.20260312-r1",
            "details": {
                "recommendation_id": "rec.dispatch-quality-first",
                "revision_id": "strat.20260312-r1",
                "conflicting_indexes": [0, 1],
            },
        },
        {
            "severity": "error",
            "reason_code": "recommendation_id_collision",
            "field_path": "recommendations[1].recommendation_id",
            "message": "recommendation_id rec.dispatch-quality-first must be unique within revision strat.20260312-r1",
            "details": {
                "recommendation_id": "rec.dispatch-quality-first",
                "revision_id": "strat.20260312-r1",
                "conflicting_indexes": [0, 1],
            },
        },
    ]

    proc = _run_cli(invalid_packet)
    assert proc.returncode == 1
    assert proc.stderr == ""
    cli_payload = json.loads(proc.stdout)
    assert cli_payload["reason_codes"] == ["recommendation_id_collision"]


def test_req_062_validator_fails_summary_mismatch_against_stability_contract() -> None:
    invalid_packet = FIXTURES_DIR / "strategy_packet.req062.summary-mismatch.json"

    verdict = validate_strategy_packet(
        packet_path=invalid_packet,
        schema_path=SCHEMA_PATH,
        context_path=CONTEXT_PATH,
        stability_contract_path=STABILITY_CONTRACT_PATH,
    )

    assert verdict["ok"] is False
    assert verdict["verdict"] == "fail"
    assert verdict["reason_codes"] == ["recommendation_id_stability_basis_mismatch"]
    assert verdict["counts"]["error_count"] == 1
    assert verdict["diagnostics"] == [
        {
            "severity": "error",
            "reason_code": "recommendation_id_stability_basis_mismatch",
            "field_path": "recommendations[0].summary",
            "message": (
                "recommendation_id rec.dispatch-quality-first does not match the REQ-062 stability contract for summary"
            ),
            "details": {
                "recommendation_id": "rec.dispatch-quality-first",
                "basis_field": "summary",
                "expected": (
                    "Implement watcher-driven cycle release and redispatch-quality controls before broader runtime features."
                ),
                "actual": "Escalate telemetry freshness guardrails before the next autonomous canary pass.",
            },
        }
    ]


def test_req_062_validator_fails_drift_and_non_traceable_ids() -> None:
    drift_verdict = validate_strategy_packet(
        packet_path=PACKET_PATH,
        schema_path=SCHEMA_PATH,
        context_path=CONTEXT_PATH,
        stability_contract_path=FIXTURES_DIR / "recommendation_id_stability_contract.req062.drift.json",
    )

    assert drift_verdict["ok"] is False
    assert drift_verdict["verdict"] == "fail"
    assert drift_verdict["reason_codes"] == ["recommendation_id_drift"]
    assert drift_verdict["diagnostics"] == [
        {
            "severity": "error",
            "reason_code": "recommendation_id_drift",
            "field_path": "recommendations[1].recommendation_id",
            "message": "recommendation_key runtime-canary-coverage drifted across revisions",
            "details": {
                "recommendation_key": "runtime-canary-coverage",
                "previous_revision_id": "strat.20260305-r0",
                "current_revision_id": "strat.20260312-r1",
                "previous_recommendation_id": "rec.runtime-canary-rollout-window",
                "current_recommendation_id": "rec.runtime-canary-coverage",
            },
        }
    ]

    invalid_packet = FIXTURES_DIR / "strategy_packet.req062.id-not-traceable.json"
    traceability_verdict = validate_strategy_packet(
        packet_path=invalid_packet,
        schema_path=SCHEMA_PATH,
        context_path=CONTEXT_PATH,
        stability_contract_path=STABILITY_CONTRACT_PATH,
    )

    assert traceability_verdict["ok"] is False
    assert traceability_verdict["verdict"] == "fail"
    assert traceability_verdict["reason_codes"] == [
        "recommendation_id_missing_from_contract",
        "recommendation_id_stability_collision",
    ]
    assert traceability_verdict["diagnostics"] == [
        {
            "severity": "error",
            "reason_code": "recommendation_id_missing_from_contract",
            "field_path": "recommendations[1].recommendation_id",
            "message": "recommendation_id rec.runtime-canary-rollout-window is not traceable to the REQ-062 contract",
            "details": {
                "recommendation_id": "rec.runtime-canary-rollout-window",
            },
        },
        {
            "severity": "error",
            "reason_code": "recommendation_id_stability_collision",
            "field_path": "recommendations[1].recommendation_id",
            "message": "recommendation basis is already assigned to another recommendation_id",
            "details": {
                "recommendation_id": "rec.runtime-canary-rollout-window",
                "expected_recommendation_id": "rec.runtime-canary-coverage",
                "recommendation_key": "runtime-canary-coverage",
            },
        },
    ]

    proc = _run_cli(invalid_packet)
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["reason_codes"] == [
        "recommendation_id_missing_from_contract",
        "recommendation_id_stability_collision",
    ]
