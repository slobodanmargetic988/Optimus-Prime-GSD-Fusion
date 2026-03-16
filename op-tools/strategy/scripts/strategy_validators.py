#!/usr/bin/env python3
"""Deterministic validators for strategy packet consumability gates."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator


PROJECT_ID_PATTERN = r"^prj\.[a-z0-9][a-z0-9-]{1,95}$"

SCHEMA_REASON_CODES = {
    "required": "schema.required",
    "additionalProperties": "schema.additional_properties",
    "type": "schema.type",
    "enum": "schema.enum",
    "pattern": "schema.pattern",
    "minItems": "schema.min_items",
    "minimum": "schema.minimum",
    "maximum": "schema.maximum",
    "const": "schema.const",
    "minLength": "schema.min_length",
}

LINK_MAP_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["artifact_type", "project_id", "discovered_projects", "links"],
    "properties": {
        "artifact_type": {"const": "ecosystem-link-map.v1"},
        "project_id": {
            "type": "string",
            "pattern": PROJECT_ID_PATTERN,
        },
        "discovered_projects": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["project_id"],
                "properties": {
                    "project_id": {
                        "type": "string",
                        "pattern": PROJECT_ID_PATTERN,
                    },
                    "repo": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "label": {
                        "type": "string",
                        "minLength": 1,
                    },
                },
            },
        },
        "links": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "source_project_id",
                    "target_project_id",
                    "relationship",
                    "status",
                    "summary",
                ],
                "properties": {
                    "source_project_id": {
                        "type": "string",
                        "pattern": PROJECT_ID_PATTERN,
                    },
                    "target_project_id": {
                        "type": "string",
                        "pattern": PROJECT_ID_PATTERN,
                    },
                    "relationship": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "status": {
                        "type": "string",
                        "enum": ["current", "missing", "proposed"],
                    },
                    "summary": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "evidence_refs": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "minLength": 1,
                        },
                    },
                },
            },
        },
    },
}


@dataclass(frozen=True, slots=True)
class Diagnostic:
    severity: str
    reason_code: str
    field_path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def load_json_file(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_strategy_packet_file(
    input_path: str | Path,
    schema_path: str | Path,
) -> dict[str, Any]:
    packet = load_json_file(input_path)
    schema = load_json_file(schema_path)
    return validate_strategy_packet_payload(packet, schema, packet_source=input_path)


def validate_strategy_packet_payload(
    packet: Any,
    schema: Mapping[str, Any],
    *,
    packet_source: str | Path | None = None,
) -> dict[str, Any]:
    diagnostics: list[Diagnostic] = []

    diagnostics.extend(_collect_schema_diagnostics(packet, schema))
    if isinstance(packet, Mapping):
        diagnostics.extend(_collect_req_063_diagnostics(packet, packet_source=packet_source))

    ordered_diagnostics = sorted(
        diagnostics,
        key=lambda item: (item.severity, item.field_path, item.reason_code, item.message),
    )
    error_count = sum(1 for item in ordered_diagnostics if item.severity == "error")
    warning_count = sum(1 for item in ordered_diagnostics if item.severity == "warning")
    ok = error_count == 0

    return {
        "ok": ok,
        "verdict": "pass" if ok else "fail",
        "ready_for_consumption": ok,
        "diagnostics": [item.to_dict() for item in ordered_diagnostics],
        "summary": {
            "diagnostic_count": len(ordered_diagnostics),
            "error_count": error_count,
            "warning_count": warning_count,
        },
    }


def _collect_schema_diagnostics(
    packet: Any,
    schema: Mapping[str, Any],
    *,
    field_path_prefix: str | None = None,
    reason_code_prefix: str = "schema",
) -> list[Diagnostic]:
    validator = Draft202012Validator(schema)
    diagnostics = []

    for error in validator.iter_errors(packet):
        field_path = _schema_error_field_path(error, field_path_prefix=field_path_prefix)
        suffix = SCHEMA_REASON_CODES.get(error.validator, f"schema.{error.validator}").split(".", 1)[1]
        diagnostics.append(
            Diagnostic(
                severity="error",
                reason_code=f"{reason_code_prefix}.{suffix}",
                field_path=field_path,
                message=error.message,
            )
        )

    return diagnostics


def _schema_error_field_path(error: Any, *, field_path_prefix: str | None = None) -> str:
    path = list(error.absolute_path)
    if error.validator == "required":
        missing = _extract_quoted_name(error.message)
        if missing is not None:
            path.append(missing)
    elif error.validator == "additionalProperties":
        unexpected = _extract_quoted_name(error.message)
        if unexpected is not None:
            path.append(unexpected)
    field_path = _format_field_path(path)
    if not field_path_prefix:
        return field_path
    if field_path == "<root>":
        return field_path_prefix
    return f"{field_path_prefix}.{field_path}"


def _collect_req_063_diagnostics(
    packet: Mapping[str, Any],
    *,
    packet_source: str | Path | None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []

    strategy = packet.get("strategy")
    if not isinstance(strategy, Mapping):
        return diagnostics

    link_map_ref = strategy.get("link_map_ref")
    if link_map_ref is None:
        return diagnostics
    if not isinstance(link_map_ref, str) or not link_map_ref.strip():
        diagnostics.append(
            _diagnostic(
                "req063.invalid_link_map_ref",
                "strategy.link_map_ref",
                "REQ-063 strategy.link_map_ref must be a non-empty string path.",
            )
        )
        return diagnostics

    link_map_path = _resolve_reference_path(packet_source, link_map_ref)
    if not link_map_path.exists():
        diagnostics.append(
            _diagnostic(
                "req063.link_map_not_found",
                "strategy.link_map_ref",
                f"REQ-063 ecosystem link-map file was not found at {link_map_ref}.",
            )
        )
        return diagnostics
    if not link_map_path.is_file():
        diagnostics.append(
            _diagnostic(
                "req063.link_map_not_file",
                "strategy.link_map_ref",
                f"REQ-063 ecosystem link-map reference must resolve to a file: {link_map_ref}.",
            )
        )
        return diagnostics

    try:
        link_map = load_json_file(link_map_path)
    except json.JSONDecodeError as error:
        diagnostics.append(
            _diagnostic(
                "req063.invalid_link_map_json",
                "strategy.link_map_ref",
                (
                    "REQ-063 ecosystem link-map file must contain valid JSON; "
                    f"parse failed at line {error.lineno} column {error.colno}."
                ),
            )
        )
        return diagnostics
    except OSError as error:
        diagnostics.append(
            _diagnostic(
                "req063.link_map_unreadable",
                "strategy.link_map_ref",
                f"REQ-063 ecosystem link-map file could not be read: {error.strerror or error}.",
            )
        )
        return diagnostics

    diagnostics.extend(
        _collect_schema_diagnostics(
            link_map,
            LINK_MAP_SCHEMA,
            field_path_prefix="strategy.link_map",
            reason_code_prefix="req063.link_map_schema",
        )
    )
    if not isinstance(link_map, Mapping):
        return diagnostics

    packet_project_id = _extract_packet_project_id(packet)
    discovered_project_ids = _collect_discovered_project_ids(link_map, diagnostics)

    if packet_project_id and discovered_project_ids and packet_project_id not in discovered_project_ids:
        diagnostics.append(
            _diagnostic(
                "req063.packet_project_missing",
                "strategy.link_map.discovered_projects",
                (
                    "REQ-063 discovered_projects must include the packet identity.project_id "
                    f"{packet_project_id}."
                ),
            )
        )

    link_map_project_id = link_map.get("project_id")
    if (
        packet_project_id
        and isinstance(link_map_project_id, str)
        and link_map_project_id != packet_project_id
    ):
        diagnostics.append(
            _diagnostic(
                "req063.root_project_mismatch",
                "strategy.link_map.project_id",
                (
                    "REQ-063 link-map project_id must match the packet identity.project_id "
                    f"{packet_project_id}."
                ),
            )
        )

    links = link_map.get("links")
    if not isinstance(links, list):
        return diagnostics

    for index, link in enumerate(links):
        if not isinstance(link, Mapping):
            continue

        source_project_id = link.get("source_project_id")
        if (
            isinstance(source_project_id, str)
            and discovered_project_ids
            and source_project_id not in discovered_project_ids
        ):
            diagnostics.append(
                _diagnostic(
                    "req063.orphaned_link_source",
                    f"strategy.link_map.links[{index}].source_project_id",
                    (
                        "REQ-063 link source_project_id must reference a discovered project; "
                        f"{source_project_id} is missing from discovered_projects."
                    ),
                )
            )

        target_project_id = link.get("target_project_id")
        if (
            isinstance(target_project_id, str)
            and discovered_project_ids
            and target_project_id not in discovered_project_ids
        ):
            diagnostics.append(
                _diagnostic(
                    "req063.orphaned_link_target",
                    f"strategy.link_map.links[{index}].target_project_id",
                    (
                        "REQ-063 link target_project_id must reference a discovered project; "
                        f"{target_project_id} is missing from discovered_projects."
                    ),
                )
            )

    return diagnostics


def _diagnostic(reason_code: str, field_path: str, message: str) -> Diagnostic:
    return Diagnostic(
        severity="error",
        reason_code=reason_code,
        field_path=field_path,
        message=message,
    )


def _extract_packet_project_id(packet: Mapping[str, Any]) -> str | None:
    identity = packet.get("identity")
    if not isinstance(identity, Mapping):
        return None
    project_id = identity.get("project_id")
    return project_id if isinstance(project_id, str) else None


def _collect_discovered_project_ids(
    link_map: Mapping[str, Any],
    diagnostics: list[Diagnostic],
) -> set[str]:
    discovered_projects = link_map.get("discovered_projects")
    if not isinstance(discovered_projects, list):
        return set()

    discovered_project_ids: set[str] = set()
    for index, project in enumerate(discovered_projects):
        if not isinstance(project, Mapping):
            continue
        project_id = project.get("project_id")
        if not isinstance(project_id, str):
            continue
        if project_id in discovered_project_ids:
            diagnostics.append(
                _diagnostic(
                    "req063.duplicate_discovered_project",
                    f"strategy.link_map.discovered_projects[{index}].project_id",
                    f"REQ-063 discovered_projects contains duplicate project_id {project_id}.",
                )
            )
            continue
        discovered_project_ids.add(project_id)

    return discovered_project_ids


def _resolve_reference_path(packet_source: str | Path | None, reference: str) -> Path:
    reference_path = Path(reference)
    if reference_path.is_absolute():
        return reference_path

    search_roots: list[Path] = []
    if packet_source is not None:
        packet_path = Path(packet_source)
        search_roots.append(packet_path.parent)
        search_roots.extend(packet_path.parents)
    else:
        search_roots.append(Path.cwd())

    for root in search_roots:
        candidate = root / reference_path
        if candidate.exists():
            return candidate

    return search_roots[0] / reference_path


def _extract_quoted_name(message: str) -> str | None:
    match = re.search(r"'([^']+)'", message)
    return None if match is None else match.group(1)


def _format_field_path(path: Sequence[Any]) -> str:
    if not path:
        return "<root>"

    parts: list[str] = []
    for item in path:
        if isinstance(item, int):
            if not parts:
                parts.append(f"[{item}]")
            else:
                parts[-1] = f"{parts[-1]}[{item}]"
            continue
        parts.append(str(item))
    return ".".join(parts)
