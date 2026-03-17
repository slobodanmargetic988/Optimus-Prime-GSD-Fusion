#!/usr/bin/env python3
"""Facade over the root strategy validator CLI for the strategy tool subtree."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping


REQ_068_INGESTION_HOOK_FILE = "REQ-068_op-plan-strategy-ingestion-hook.sample.json"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _root_validator_script() -> Path:
    return _repo_root() / "scripts" / "strategy_packet_validate.py"


def load_json_file(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_json_schema(path: str | Path) -> Mapping[str, Any]:
    payload = load_json_file(path)
    if not isinstance(payload, Mapping):
        raise ValueError("schema file must contain a JSON object")
    return payload


def _with_legacy_compatibility(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    diagnostics = normalized.get("diagnostics")
    if not isinstance(diagnostics, list):
        diagnostics = []

    error_count = sum(
        1 for row in diagnostics if isinstance(row, Mapping) and row.get("severity") == "error"
    )
    warning_count = sum(
        1 for row in diagnostics if isinstance(row, Mapping) and row.get("severity") == "warning"
    )

    normalized["ready_for_consumption"] = bool(
        normalized.get("ok") and normalized.get("planner_consumability") != "planner_blocked"
    )
    if "summary" in normalized and not isinstance(normalized.get("summary"), Mapping):
        normalized["summary_text"] = normalized.get("summary")
    normalized["summary"] = {
        "diagnostic_count": int(normalized.get("diagnostic_count", len(diagnostics))),
        "error_count": error_count,
        "warning_count": warning_count,
    }
    return normalized


def _maybe_resolve_ingestion_hook(
    input_path: str | Path | None,
    explicit_hook_path: str | Path | None,
) -> Path | None:
    if explicit_hook_path is not None:
        candidate = Path(explicit_hook_path)
        if candidate.exists():
            return candidate.resolve()
        repo_candidate = (_repo_root() / candidate).resolve()
        if repo_candidate.exists():
            return repo_candidate
        return candidate

    if input_path is None:
        return None

    candidate = Path(input_path)
    if not candidate.is_absolute():
        candidate = (_repo_root() / candidate).resolve()
    if not candidate.exists():
        return None

    discovered = candidate.parent / "samples" / REQ_068_INGESTION_HOOK_FILE
    if discovered.exists():
        return discovered.resolve()
    return None


def _run_root_validator(
    *,
    input_path: Path,
    schema_path: Path,
    aggregate_verdict: bool = False,
    op_plan_ingestion_hook_path: Path | None = None,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(_root_validator_script()),
        "--input",
        str(input_path),
        "--schema",
        str(schema_path),
    ]
    if aggregate_verdict:
        command.append("--aggregate-verdict")
    if op_plan_ingestion_hook_path is not None:
        command.extend(["--op-plan-ingestion-hook", str(op_plan_ingestion_hook_path)])

    proc = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        cwd=str(_repo_root()),
    )
    if not proc.stdout.strip():
        raise RuntimeError(
            f"Root strategy validator returned no JSON output.\nstderr:\n{proc.stderr.strip()}"
        )
    return json.loads(proc.stdout)


def validate_strategy_packet_file(
    input_path: str | Path,
    schema_path: str | Path,
    *,
    op_plan_ingestion_hook_path: str | Path | None = None,
) -> dict[str, Any]:
    hook_path = _maybe_resolve_ingestion_hook(input_path, op_plan_ingestion_hook_path)
    payload = _run_root_validator(
        input_path=Path(input_path).resolve(),
        schema_path=Path(schema_path).resolve(),
        op_plan_ingestion_hook_path=hook_path,
    )
    return _with_legacy_compatibility(payload)


def run_strategy_packet_validator_runner_files(
    input_path: str | Path,
    schema_path: str | Path,
    *,
    op_plan_ingestion_hook_path: str | Path | None = None,
) -> dict[str, Any]:
    hook_path = _maybe_resolve_ingestion_hook(input_path, op_plan_ingestion_hook_path)
    return _run_root_validator(
        input_path=Path(input_path).resolve(),
        schema_path=Path(schema_path).resolve(),
        aggregate_verdict=True,
        op_plan_ingestion_hook_path=hook_path,
    )


def validate_strategy_packet_payload(
    packet: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    input_path: str | Path | None = None,
    schema_path: str | Path | None = None,
    op_plan_ingestion_hook: Any | None = None,
    op_plan_ingestion_hook_path: str | Path | None = None,
    require_op_plan_ingestion_hook: bool = False,
) -> dict[str, Any]:
    hook_payload = op_plan_ingestion_hook
    hook_path = _maybe_resolve_ingestion_hook(input_path, op_plan_ingestion_hook_path)
    if hook_payload is None and require_op_plan_ingestion_hook and hook_path is not None:
        hook_payload = load_json_file(hook_path)

    with tempfile.TemporaryDirectory(prefix="strategy-validator-") as tmpdir:
        tmpdir_path = Path(tmpdir)
        packet_file = tmpdir_path / "packet.json"
        schema_file = tmpdir_path / "schema.json"
        packet_file.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        schema_file.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        hook_file: Path | None = None
        if hook_payload is not None:
            hook_file = tmpdir_path / "req068.json"
            hook_file.write_text(json.dumps(hook_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        elif hook_path is not None:
            hook_file = hook_path

        payload = _run_root_validator(
            input_path=packet_file,
            schema_path=schema_file,
            op_plan_ingestion_hook_path=hook_file,
        )
    return _with_legacy_compatibility(payload)


def validate_strategy_packet(
    packet: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    input_path: str | Path | None = None,
    schema_path: str | Path | None = None,
    op_plan_ingestion_hook: Any | None = None,
    op_plan_ingestion_hook_path: str | Path | None = None,
    require_op_plan_ingestion_hook: bool = False,
) -> dict[str, Any]:
    return validate_strategy_packet_payload(
        packet,
        schema,
        input_path=input_path,
        schema_path=schema_path,
        op_plan_ingestion_hook=op_plan_ingestion_hook,
        op_plan_ingestion_hook_path=op_plan_ingestion_hook_path,
        require_op_plan_ingestion_hook=require_op_plan_ingestion_hook or input_path is not None,
    )
