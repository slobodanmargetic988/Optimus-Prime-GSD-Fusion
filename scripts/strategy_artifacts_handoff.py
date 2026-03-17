#!/usr/bin/env python3
"""Facade for strategy artifact handoff requirement families."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
for candidate in (SCRIPTS_ROOT,):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from scripts import _strategy_artifacts_req052 as _req052
from scripts import _strategy_artifacts_req049 as _req049
from scripts import _strategy_artifacts_req054_060_066 as _req054_060_066
from scripts import _strategy_artifacts_req056_057_063_069 as _req056_057_063_069
from scripts import _strategy_artifacts_req056_059 as _req056_059
from scripts import _strategy_artifacts_req056_062_068 as _req056_062_068
from scripts import _strategy_artifacts_req058_064_070 as _req058_064_070
from scripts import _strategy_artifacts_req069 as _req069

REQ_048_ANALYSIS_TYPE = getattr(_req052, "REQ_048_ANALYSIS_TYPE", "strategy_md_generator")
REQ_049_ANALYSIS_TYPE = getattr(_req049, "REQ_049_ANALYSIS_TYPE", "strategy_json_generator")
REQ_050_ANALYSIS_TYPE = getattr(_req052, "REQ_050_ANALYSIS_TYPE", "ecosystem_link_map_json_generator")
REQ_051_ANALYSIS_TYPE = getattr(_req052, "REQ_051_ANALYSIS_TYPE", "strategy_changelog_md_generator")
REQ_052_ANALYSIS_TYPE = getattr(_req052, "REQ_052_ANALYSIS_TYPE", "strategy_packet_v1_generator")
REQ_053_ANALYSIS_TYPE = getattr(_req052, "REQ_053_ANALYSIS_TYPE", "recommendation_id_stability_contract")
REQ_054_ANALYSIS_TYPE = getattr(_req054_060_066, "REQ_054_ANALYSIS_TYPE", "recommendation_to_planner_mapping_artifact")
REQ_056_ANALYSIS_TYPE = getattr(_req056_062_068, "REQ_056_ANALYSIS_TYPE", "kpi_target_artifact")
REQ_057_ANALYSIS_TYPE = getattr(_req056_057_063_069, "REQ_057_ANALYSIS_TYPE", "blocker_handling_policy_artifact")
REQ_058_ANALYSIS_TYPE = getattr(_req058_064_070, "REQ_058_ANALYSIS_TYPE", "ecosystem_obligation_artifact")
REQ_059_ANALYSIS_TYPE = getattr(_req056_059, "REQ_059_ANALYSIS_TYPE", "strategy_quality_report_artifact")
REQ_060_ANALYSIS_TYPE = getattr(_req054_060_066, "REQ_060_ANALYSIS_TYPE", "strategy_packet_v1_schema_validator")
REQ_062_ANALYSIS_TYPE = getattr(_req056_062_068, "REQ_062_ANALYSIS_TYPE", "recommendation_id_uniqueness_validator")
REQ_063_ANALYSIS_TYPE = getattr(_req056_057_063_069, "REQ_063_ANALYSIS_TYPE", "ecosystem_link_map_integrity_validator")
REQ_064_ANALYSIS_TYPE = getattr(_req058_064_070, "REQ_064_ANALYSIS_TYPE", "source_traceability_validator")
REQ_066_ANALYSIS_TYPE = getattr(_req054_060_066, "REQ_066_ANALYSIS_TYPE", "validator_runner_and_aggregate_verdict")
REQ_068_ANALYSIS_TYPE = getattr(_req056_062_068, "REQ_068_ANALYSIS_TYPE", "op_plan_strategy_ingestion_hook")
REQ_069_ANALYSIS_TYPE = getattr(_req069, "REQ_069_ANALYSIS_TYPE", "strategy_revision_history_and_diff_workflow")
REQ_070_ANALYSIS_TYPE = getattr(
    _req058_064_070,
    "REQ_070_ANALYSIS_TYPE",
    "end_to_end_autonomous_strategy_run_acceptance_packet",
)

build_req_048_strategy_md_generator = _req052.build_req_048_strategy_md_generator
validate_req_048_strategy_md_generator = _req052.validate_req_048_strategy_md_generator
build_req_049_strategy_json_generator = _req049.build_req_049_strategy_json_generator
validate_req_049_strategy_json_generator = _req049.validate_req_049_strategy_json_generator
build_req_050_ecosystem_link_map_json_generator = _req052.build_req_050_ecosystem_link_map_json_generator
validate_req_050_ecosystem_link_map_json_generator = _req052.validate_req_050_ecosystem_link_map_json_generator
build_req_051_strategy_changelog_md_generator = _req052.build_req_051_strategy_changelog_md_generator
validate_req_051_strategy_changelog_md_generator = _req052.validate_req_051_strategy_changelog_md_generator
build_req_052_strategy_packet_v1_generator = _req052.build_req_052_strategy_packet_v1_generator
validate_req_052_strategy_packet_v1_generator = _req052.validate_req_052_strategy_packet_v1_generator
build_req_053_recommendation_id_stability_contract = _req052.build_req_053_recommendation_id_stability_contract
validate_req_053_recommendation_id_stability_contract = _req052.validate_req_053_recommendation_id_stability_contract

build_req_054_recommendation_to_planner_mapping_artifact = (
    _req054_060_066.build_req_054_recommendation_to_planner_mapping_artifact
)
validate_req_054_recommendation_to_planner_mapping_artifact = (
    _req054_060_066.validate_req_054_recommendation_to_planner_mapping_artifact
)
build_req_060_strategy_packet_v1_schema_validator = _req054_060_066.build_req_060_strategy_packet_v1_schema_validator
validate_req_060_strategy_packet_v1_schema_validator = (
    _req054_060_066.validate_req_060_strategy_packet_v1_schema_validator
)
build_req_066_validator_runner_and_aggregate_verdict = (
    _req054_060_066.build_req_066_validator_runner_and_aggregate_verdict
)
validate_req_066_validator_runner_and_aggregate_verdict = (
    _req054_060_066.validate_req_066_validator_runner_and_aggregate_verdict
)

build_req_056_kpi_target_artifact = _req056_062_068.build_req_056_kpi_target_artifact
validate_req_056_kpi_target_artifact = _req056_062_068.validate_req_056_kpi_target_artifact
build_req_062_recommendation_id_uniqueness_validator = (
    _req056_062_068.build_req_062_recommendation_id_uniqueness_validator
)
validate_req_062_recommendation_id_uniqueness_validator = (
    _req056_062_068.validate_req_062_recommendation_id_uniqueness_validator
)
build_req_068_op_plan_strategy_ingestion_hook = _req056_062_068.build_req_068_op_plan_strategy_ingestion_hook
validate_req_068_op_plan_strategy_ingestion_hook = (
    _req056_062_068.validate_req_068_op_plan_strategy_ingestion_hook
)

build_req_057_blocker_handling_policy_artifact = _req056_057_063_069.build_req_057_blocker_handling_policy_artifact
validate_req_057_blocker_handling_policy_artifact = (
    _req056_057_063_069.validate_req_057_blocker_handling_policy_artifact
)
build_req_058_ecosystem_obligation_artifact = _req058_064_070.build_req_058_ecosystem_obligation_artifact
validate_req_058_ecosystem_obligation_artifact = _req058_064_070.validate_req_058_ecosystem_obligation_artifact
build_req_063_ecosystem_link_map_integrity_validator = (
    _req056_057_063_069.build_req_063_ecosystem_link_map_integrity_validator
)
validate_req_063_ecosystem_link_map_integrity_validator = (
    _req056_057_063_069.validate_req_063_ecosystem_link_map_integrity_validator
)
build_req_064_source_traceability_validator = _req058_064_070.build_req_064_source_traceability_validator
validate_req_064_source_traceability_validator = _req058_064_070.validate_req_064_source_traceability_validator
build_req_069_strategy_revision_history_and_diff_workflow = _req069.build_req_069_strategy_revision_history_and_diff_workflow
validate_req_069_strategy_revision_history_and_diff_workflow = (
    _req069.validate_req_069_strategy_revision_history_and_diff_workflow
)
build_req_070_end_to_end_autonomous_strategy_run_acceptance_packet = (
    _req058_064_070.build_req_070_end_to_end_autonomous_strategy_run_acceptance_packet
)
validate_req_070_end_to_end_autonomous_strategy_run_acceptance_packet = (
    _req058_064_070.validate_req_070_end_to_end_autonomous_strategy_run_acceptance_packet
)

build_req_059_strategy_quality_report_artifact = _req056_059.build_req_059_strategy_quality_report_artifact
build_req_059_strategy_quality_report_delivery_bundle = _req056_059.build_req_059_strategy_quality_report_delivery_bundle
validate_req_059_strategy_quality_report_artifact = _req056_059.validate_req_059_strategy_quality_report_artifact


def _utc_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


_BUILDERS: dict[str, Callable[[Mapping[str, Any]], dict[str, Any]]] = {
    REQ_048_ANALYSIS_TYPE: build_req_048_strategy_md_generator,
    REQ_049_ANALYSIS_TYPE: build_req_049_strategy_json_generator,
    REQ_050_ANALYSIS_TYPE: build_req_050_ecosystem_link_map_json_generator,
    REQ_051_ANALYSIS_TYPE: build_req_051_strategy_changelog_md_generator,
    REQ_052_ANALYSIS_TYPE: build_req_052_strategy_packet_v1_generator,
    REQ_053_ANALYSIS_TYPE: build_req_053_recommendation_id_stability_contract,
    REQ_054_ANALYSIS_TYPE: build_req_054_recommendation_to_planner_mapping_artifact,
    REQ_056_ANALYSIS_TYPE: build_req_056_kpi_target_artifact,
    REQ_057_ANALYSIS_TYPE: build_req_057_blocker_handling_policy_artifact,
    REQ_058_ANALYSIS_TYPE: build_req_058_ecosystem_obligation_artifact,
    REQ_059_ANALYSIS_TYPE: build_req_059_strategy_quality_report_artifact,
    REQ_060_ANALYSIS_TYPE: build_req_060_strategy_packet_v1_schema_validator,
    REQ_062_ANALYSIS_TYPE: build_req_062_recommendation_id_uniqueness_validator,
    REQ_063_ANALYSIS_TYPE: build_req_063_ecosystem_link_map_integrity_validator,
    REQ_064_ANALYSIS_TYPE: build_req_064_source_traceability_validator,
    REQ_066_ANALYSIS_TYPE: build_req_066_validator_runner_and_aggregate_verdict,
    REQ_068_ANALYSIS_TYPE: build_req_068_op_plan_strategy_ingestion_hook,
    REQ_069_ANALYSIS_TYPE: build_req_069_strategy_revision_history_and_diff_workflow,
    REQ_070_ANALYSIS_TYPE: build_req_070_end_to_end_autonomous_strategy_run_acceptance_packet,
}


def build_strategy_artifact(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build a strategy artifact based on payload analysis_type."""
    analysis_type = str(payload.get("analysis_type") or "").strip()
    if not analysis_type:
        return build_req_056_kpi_target_artifact(payload)
    builder = _BUILDERS.get(analysis_type)
    if builder is None:
        supported = ", ".join(sorted(_BUILDERS))
        raise ValueError(f"analysis_type must be one of: {supported}")
    return builder(payload)


def run(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_strategy_artifact(payload)


def _load_input_payload(path_value: str) -> dict[str, Any]:
    if path_value == "-":
        raw_text = sys.stdin.read()
    else:
        raw_text = Path(path_value).read_text(encoding="utf-8")
    loaded = json.loads(raw_text)
    if not isinstance(loaded, dict):
        raise ValueError("input payload must be a JSON object")
    return loaded


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Emit strategy artifact handoff payloads.")
    parser.add_argument("--input-json", required=True, help='Input payload path or "-" for stdin.')
    parser.add_argument("--output-json", default="-", help='Output path or "-" for stdout.')
    parser.add_argument("--json-pretty", action="store_true", help="Pretty-print JSON output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    try:
        payload = _load_input_payload(args.input_json)
        output_payload = build_strategy_artifact(payload)
        rendered = json.dumps(output_payload, indent=2 if args.json_pretty else None, sort_keys=False)
        if args.output_json == "-":
            print(rendered)
        else:
            output_path = Path(args.output_json)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(rendered + "\n", encoding="utf-8")
        return 0
    except Exception as exc:  # pragma: no cover - CLI guardrail
        sys.stderr.write(f"[{_utc_timestamp()}] strategy artifact CLI failed: {exc}\n")
        return 1


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
