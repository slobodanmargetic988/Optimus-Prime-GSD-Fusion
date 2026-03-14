from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _print_human(message: str) -> None:
    print(f"[{_utc_timestamp()}] {message}")


def _error(reason_code: str, message: str) -> dict[str, str]:
    return {"reason_code": reason_code, "message": message}


def _normalize_anchor(anchor: Any, *, field: str) -> tuple[str | None, str | None, list[dict[str, str]]]:
    errors: list[dict[str, str]] = []

    if anchor is None:
        errors.append(_error(f"{field}_missing", f"target_project.{field} is required"))
        return None, None, errors

    if isinstance(anchor, str):
        text = anchor.strip()
        if not text:
            errors.append(_error(f"{field}_empty", f"target_project.{field} must not be empty"))
            return None, None, errors
        return text, "inline", errors

    if isinstance(anchor, Mapping):
        raw_text = anchor.get("text")
        if not isinstance(raw_text, str):
            errors.append(_error(f"{field}_text_missing", f"target_project.{field}.text is required"))
            return None, None, errors

        text = raw_text.strip()
        if not text:
            errors.append(_error(f"{field}_empty", f"target_project.{field}.text must not be empty"))
            return None, None, errors

        raw_source = anchor.get("source", "inline")
        if raw_source is None:
            source = "inline"
        elif isinstance(raw_source, str):
            source = raw_source.strip() or "inline"
        else:
            errors.append(
                _error(
                    f"{field}_source_invalid_type",
                    f"target_project.{field}.source must be a string when provided",
                )
            )
            return None, None, errors
        return text, source, errors

    errors.append(
        _error(
            f"{field}_invalid_type",
            f"target_project.{field} must be either a string or an object with text/source",
        )
    )
    return None, None, errors


def _failure(errors: list[dict[str, str]]) -> dict[str, Any]:
    reason_codes = []
    for item in errors:
        code = item["reason_code"]
        if code not in reason_codes:
            reason_codes.append(code)
    return {
        "ok": False,
        "reason_codes": reason_codes,
        "errors": errors,
    }


def _as_non_empty_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = _as_non_empty_text(item)
        if text and text not in out:
            out.append(text)
    return out


def _extract_earth_sweep_projects(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    broad_sweep = payload.get("broad_sweep_context")
    if not isinstance(broad_sweep, Mapping):
        return []

    earth_sweep = broad_sweep.get("earth_sweep")
    if isinstance(earth_sweep, list):
        return [item for item in earth_sweep if isinstance(item, Mapping)]
    if not isinstance(earth_sweep, Mapping):
        return []

    projects = earth_sweep.get("projects")
    if not isinstance(projects, list):
        return []
    return [item for item in projects if isinstance(item, Mapping)]


def _project_label(project: Mapping[str, Any], fallback_index: int) -> str:
    for key in ("project_id", "project", "name", "id"):
        label = _as_non_empty_text(project.get(key))
        if label:
            return label
    return f"project-{fallback_index:03d}"


def _extract_item_text(item: Any) -> str | None:
    if isinstance(item, str):
        return _as_non_empty_text(item)
    if not isinstance(item, Mapping):
        return None
    for key in ("recommendation", "summary", "title", "text", "idea"):
        text = _as_non_empty_text(item.get(key))
        if text:
            return text
    return None


def _extract_evidence_refs(item: Any) -> list[str]:
    if not isinstance(item, Mapping):
        return []
    if "earth_sweep_evidence_refs" in item:
        refs = _normalize_string_list(item.get("earth_sweep_evidence_refs"))
        if refs:
            return refs
    return _normalize_string_list(item.get("evidence_refs"))


def _collect_cross_project_recommendations(payload: Mapping[str, Any]) -> dict[str, Any]:
    action_items: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    evidence_refs: list[str] = []
    projects = _extract_earth_sweep_projects(payload)
    projects_by_label = sorted(
        ((_project_label(project, idx), project) for idx, project in enumerate(projects)),
        key=lambda item: item[0],
    )

    for project_label, project in projects_by_label:
        obligations = project.get("obligations")
        if isinstance(obligations, list):
            for obligation in obligations:
                recommendation = _extract_item_text(obligation)
                if not recommendation:
                    continue
                refs = _extract_evidence_refs(obligation)
                if refs:
                    for ref in refs:
                        if ref not in evidence_refs:
                            evidence_refs.append(ref)
                    action_items.append(
                        {
                            "source_project": project_label,
                            "recommendation": recommendation,
                            "earth_sweep_evidence_refs": refs,
                        }
                    )
                else:
                    open_risks.append(
                        {
                            "risk_code": "missing_earth_sweep_evidence_refs",
                            "source_project": project_label,
                            "item": recommendation,
                            "resolution_hint": "attach Earth-sweep evidence refs before promotion",
                        }
                    )

        unresolved = project.get("unresolved_ideas")
        if isinstance(unresolved, list):
            for idea in unresolved:
                idea_text = _extract_item_text(idea)
                if not idea_text:
                    continue
                refs = _extract_evidence_refs(idea)
                if refs:
                    for ref in refs:
                        if ref not in evidence_refs:
                            evidence_refs.append(ref)
                open_risks.append(
                    {
                        "risk_code": "unresolved_cross_project_idea",
                        "source_project": project_label,
                        "item": idea_text,
                        "earth_sweep_evidence_refs": refs,
                        "resolution_hint": "triage idea before implementation",
                    }
                )

    action_items.sort(key=lambda item: (item["source_project"], item["recommendation"]))
    open_risks.sort(key=lambda item: (item["source_project"], item["risk_code"], item["item"]))
    evidence_refs.sort()

    return {
        "cross_project_inputs_considered": len(projects_by_label),
        "cross_project_context_used": bool(projects_by_label),
        "earth_sweep_evidence_refs": evidence_refs,
        "action_items": action_items,
        "open_risks": open_risks,
    }


def ingest_target_project_mission_scope(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Ingest target-project mission/scope anchors as authoritative constraints.

    REQ-003 scope:
    - mission/scope are required authoritative anchors.
    - missing or incomplete anchors are rejected with explicit reason codes.
    - no fallback behavior is applied.
    """

    if not isinstance(payload, Mapping):
        return _failure([_error("invalid_payload_type", "payload must be an object")])

    target_project = payload.get("target_project")
    if target_project is None:
        return _failure([_error("target_project_missing", "target_project object is required")])
    if not isinstance(target_project, Mapping):
        return _failure(
            [_error("target_project_invalid_type", "target_project must be an object")]
        )

    mission_text, mission_source, mission_errors = _normalize_anchor(
        target_project.get("mission"), field="mission"
    )
    scope_text, scope_source, scope_errors = _normalize_anchor(
        target_project.get("scope"), field="scope"
    )
    errors = mission_errors + scope_errors
    if errors:
        return _failure(errors)

    cross_project = _collect_cross_project_recommendations(payload)

    return {
        "ok": True,
        "reason_codes": [],
        "target_project_constraints": {
            "mission": {
                "text": mission_text,
                "source": mission_source,
                "authoritative": True,
            },
            "scope": {
                "text": scope_text,
                "source": scope_source,
                "authoritative": True,
            },
        },
        "context_ingestion": {
            "input_source": "broad_sweep_context",
            "cross_project_context_used": cross_project["cross_project_context_used"],
            "cross_project_inputs_considered": cross_project["cross_project_inputs_considered"],
            "earth_sweep_evidence_refs": cross_project["earth_sweep_evidence_refs"],
        },
        "recommendation_generation": {
            "base_constraints_source": "target_project_mission_scope",
            "authoritative_fields": ["mission", "scope"],
            "required_recommendation_fields": [
                "target_project_constraints",
                "context_ingestion",
                "recommendations",
            ],
            "recommendation_fields_complete": True,
            "cross_project_context_used": cross_project["cross_project_context_used"],
            "evidence_ref_policy": "earth_sweep_refs_required_for_cross_project_obligations",
        },
        "recommendations": {
            "action_items": cross_project["action_items"],
            "open_risks": cross_project["open_risks"],
        },
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="REQ-003 target project mission/scope ingestion contract check."
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to JSON payload containing target_project.mission and target_project.scope.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.input.exists():
        _print_human(f"Input file not found: {args.input}")
        return 2

    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _print_human(f"Invalid JSON in input file: {exc}")
        return 2

    result = ingest_target_project_mission_scope(payload)
    _print_human("Completed target project mission/scope ingestion.")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
