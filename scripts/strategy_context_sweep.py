#!/usr/bin/env python3
"""REQ-001 contract surface for the LLM-first strategy runtime entrypoint."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "req-001.llm-first-strategy-runtime-entrypoint.v1"
REQUIREMENT_ID = "REQ-001"
RUNTIME_MODE = "llm-first"
EXECUTION_MODE = "long-thinking"


def _require_nonempty_text(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must be a non-empty string")
    return text


def _normalize_root(raw_path: str, *, field_name: str) -> str:
    normalized = str(Path(_require_nonempty_text(raw_path, field_name=field_name)).expanduser().resolve())
    if not normalized.startswith("/"):
        raise ValueError(f"{field_name} must normalize to an absolute path")
    return normalized


def _canonical_call_input(
    *,
    target_project_root: str,
    earth_root: str,
    output_root: str,
    revision_identity: str,
) -> dict[str, str]:
    return {
        "earth_root": earth_root,
        "execution_mode": EXECUTION_MODE,
        "output_root": output_root,
        "revision_identity": revision_identity,
        "runtime_mode": RUNTIME_MODE,
        "target_project_root": target_project_root,
    }


def _canonical_input_digest(canonical_input: Mapping[str, str]) -> str:
    raw = json.dumps(canonical_input, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_req_001_runtime_entrypoint(
    *,
    target_project_root: str,
    earth_root: str,
    output_root: str,
    revision_identity: str,
) -> dict[str, Any]:
    """Build the REQ-001 runtime entrypoint payload."""
    normalized_target_root = _normalize_root(target_project_root, field_name="target_project_root")
    normalized_earth_root = _normalize_root(earth_root, field_name="earth_root")
    normalized_output_root = _normalize_root(output_root, field_name="output_root")
    normalized_revision_identity = _require_nonempty_text(revision_identity, field_name="revision_identity")

    canonical_input = _canonical_call_input(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        output_root=normalized_output_root,
        revision_identity=normalized_revision_identity,
    )
    digest = _canonical_input_digest(canonical_input)

    return {
        "schema_version": SCHEMA_VERSION,
        "requirement_id": REQUIREMENT_ID,
        "strategy_runtime_entrypoint": {
            "runtime_mode": RUNTIME_MODE,
            "execution_mode": EXECUTION_MODE,
            "target_project_root": normalized_target_root,
            "earth_root": normalized_earth_root,
            "output_root": normalized_output_root,
            "revision_identity": normalized_revision_identity,
        },
        "call_metadata": {
            "reproducibility": "deterministic-input-fingerprint",
            "canonical_input_sha256": digest,
            "reproducible_call_id": f"req001-{digest[:16]}",
            "canonical_input": canonical_input,
        },
    }


def validate_req_001_runtime_entrypoint(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-001 payload shape and deterministic call metadata."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    top_keys = set(payload.keys())
    required_top = {"schema_version", "requirement_id", "strategy_runtime_entrypoint", "call_metadata"}
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - required_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQUIREMENT_ID}")

    entrypoint = payload.get("strategy_runtime_entrypoint")
    if not isinstance(entrypoint, Mapping):
        errors.append("strategy_runtime_entrypoint must be an object")
        return errors

    required_entrypoint = {
        "runtime_mode",
        "execution_mode",
        "target_project_root",
        "earth_root",
        "output_root",
        "revision_identity",
    }
    entrypoint_keys = set(entrypoint.keys())
    missing_entrypoint = sorted(required_entrypoint - entrypoint_keys)
    if missing_entrypoint:
        errors.append(f"strategy_runtime_entrypoint missing keys: {missing_entrypoint}")
    unexpected_entrypoint = sorted(entrypoint_keys - required_entrypoint)
    if unexpected_entrypoint:
        errors.append(f"strategy_runtime_entrypoint has unexpected keys: {unexpected_entrypoint}")

    if entrypoint.get("runtime_mode") != RUNTIME_MODE:
        errors.append(f"runtime_mode must be {RUNTIME_MODE}")
    if entrypoint.get("execution_mode") != EXECUTION_MODE:
        errors.append(f"execution_mode must be {EXECUTION_MODE}")

    for root_field in ("target_project_root", "earth_root", "output_root"):
        value = entrypoint.get(root_field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{root_field} must be non-empty string")
        elif not value.startswith("/"):
            errors.append(f"{root_field} must be absolute path")

    revision_identity = entrypoint.get("revision_identity")
    if not isinstance(revision_identity, str) or not revision_identity.strip():
        errors.append("revision_identity must be non-empty string")

    metadata = payload.get("call_metadata")
    if not isinstance(metadata, Mapping):
        errors.append("call_metadata must be an object")
        return errors

    required_metadata = {
        "reproducibility",
        "canonical_input_sha256",
        "reproducible_call_id",
        "canonical_input",
    }
    metadata_keys = set(metadata.keys())
    missing_metadata = sorted(required_metadata - metadata_keys)
    if missing_metadata:
        errors.append(f"call_metadata missing keys: {missing_metadata}")
    unexpected_metadata = sorted(metadata_keys - required_metadata)
    if unexpected_metadata:
        errors.append(f"call_metadata has unexpected keys: {unexpected_metadata}")

    if metadata.get("reproducibility") != "deterministic-input-fingerprint":
        errors.append("call_metadata.reproducibility must be deterministic-input-fingerprint")

    canonical_input = metadata.get("canonical_input")
    if not isinstance(canonical_input, Mapping):
        errors.append("call_metadata.canonical_input must be an object")
        return errors

    expected_canonical_input = _canonical_call_input(
        target_project_root=str(entrypoint.get("target_project_root", "")),
        earth_root=str(entrypoint.get("earth_root", "")),
        output_root=str(entrypoint.get("output_root", "")),
        revision_identity=str(entrypoint.get("revision_identity", "")),
    )
    if dict(canonical_input) != expected_canonical_input:
        errors.append("call_metadata.canonical_input must mirror normalized invocation anchors")

    expected_digest = _canonical_input_digest(expected_canonical_input)
    expected_call_id = f"req001-{expected_digest[:16]}"
    if metadata.get("canonical_input_sha256") != expected_digest:
        errors.append("call_metadata.canonical_input_sha256 does not match canonical input")
    if metadata.get("reproducible_call_id") != expected_call_id:
        errors.append("call_metadata.reproducible_call_id does not match canonical digest")

    return errors


def _write_payload(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Emit REQ-001 LLM-first strategy runtime entrypoint payload.")
    parser.add_argument("--target-project-root", required=True)
    parser.add_argument("--earth-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--revision-identity", required=True)
    parser.add_argument(
        "--output-path",
        default="-",
        help='Output path for payload JSON. Use "-" for stdout (default).',
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    payload = build_req_001_runtime_entrypoint(
        target_project_root=args.target_project_root,
        earth_root=args.earth_root,
        output_root=args.output_root,
        revision_identity=args.revision_identity,
    )
    errors = validate_req_001_runtime_entrypoint(payload)
    if errors:
        for error in errors:
            print(f"validation_error: {error}", file=sys.stderr)
        return 2

    if args.output_path == "-":
        print(json.dumps(payload, indent=2, sort_keys=False))
    else:
        _write_payload(Path(args.output_path), payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
