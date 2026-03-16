#!/usr/bin/env python3
"""REQ-027 contract surface for Call-2 ecosystem linkage reasoning.

This module intentionally focuses on REQ-027 only. It normalizes, validates, and
emits a deterministic payload describing:
- existing links between the target and peer projects,
- missing links (expected but absent),
- proposed links (candidate future integrations),
each annotated with confidence tags and bounded interaction obligations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping


REQ_027_SCHEMA_VERSION = "req-027.call-2-ecosystem-linkage-reasoning.v1"
REQ_027_REQUIREMENT_ID = "REQ-027"
REQ_027_ANALYSIS_TYPE = "call_2_ecosystem_linkage_reasoning"
REQ_027_CALL_ID = "call-2"

_CONFIDENCE_TAGS = ("high", "medium", "low")
_DIRECTIONS = ("target_to_peer", "peer_to_target", "bidirectional")
_OBLIGATED_PARTIES = ("target", "peer", "both")


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _require_nonempty_text(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must be a non-empty string")
    return text


def _normalize_root(raw_path: Any, *, field_name: str) -> str:
    normalized = str(Path(_require_nonempty_text(raw_path, field_name=field_name)).expanduser().resolve())
    if not normalized.startswith("/"):
        raise ValueError(f"{field_name} must normalize to an absolute path")
    return normalized


def _normalize_string_list(raw_value: Any, *, field_name: str) -> list[str]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError(f"{field_name} must be a list of strings")
    normalized: set[str] = set()
    for index, item in enumerate(raw_value):
        normalized.add(_require_nonempty_text(item, field_name=f"{field_name}[{index}]"))
    return sorted(normalized)


def _normalize_direction(raw_value: Any, *, field_name: str) -> str:
    if raw_value is None:
        return "bidirectional"
    direction = _require_nonempty_text(raw_value, field_name=field_name).lower()
    if direction not in _DIRECTIONS:
        raise ValueError(f"{field_name} must be one of: {list(_DIRECTIONS)}")
    return direction


def _normalize_confidence_tag(raw_value: Any, *, field_name: str) -> str:
    if raw_value is None:
        raise ValueError(f"{field_name} must be set to one of: {list(_CONFIDENCE_TAGS)}")
    tag = _require_nonempty_text(raw_value, field_name=field_name).lower()
    if tag not in _CONFIDENCE_TAGS:
        raise ValueError(f"{field_name} must be one of: {list(_CONFIDENCE_TAGS)}")
    return tag


def _stable_id_fragment(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _normalize_target_project(raw_value: Any) -> dict[str, str]:
    target = _require_mapping(raw_value, field_name="target_project")
    project_id = _require_nonempty_text(target.get("project_id"), field_name="target_project.project_id")
    project_root = _normalize_root(target.get("project_root"), field_name="target_project.project_root")
    normalized = {"project_id": project_id, "project_root": project_root}
    extra = sorted(set(target.keys()) - set(normalized.keys()))
    if extra:
        raise ValueError(f"target_project has unexpected keys: {extra}")
    return normalized


def _normalize_peer_projects(raw_value: Any) -> list[dict[str, str]]:
    if not isinstance(raw_value, list) or not raw_value:
        raise ValueError("peer_projects must be a non-empty list")
    peers: list[dict[str, str]] = []
    for index, item in enumerate(raw_value):
        peer = _require_mapping(item, field_name=f"peer_projects[{index}]")
        project_id = _require_nonempty_text(peer.get("project_id"), field_name=f"peer_projects[{index}].project_id")
        project_root = _normalize_root(peer.get("project_root"), field_name=f"peer_projects[{index}].project_root")
        row = {"project_id": project_id, "project_root": project_root}
        extra = sorted(set(peer.keys()) - set(row.keys()))
        if extra:
            raise ValueError(f"peer_projects[{index}] has unexpected keys: {extra}")
        peers.append(row)
    peers.sort(key=lambda row: row["project_id"])
    return peers


def _normalize_interaction_obligations(
    raw_value: Any,
    *,
    field_name: str,
    target_project_id: str,
    peer_project_id: str,
    link_kind: str,
    direction: str,
) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError(f"{field_name} must be a list")
    obligations: list[dict[str, Any]] = []
    for index, item in enumerate(raw_value):
        obligation = _require_mapping(item, field_name=f"{field_name}[{index}]")
        obligated_party = _require_nonempty_text(
            obligation.get("obligated_party"),
            field_name=f"{field_name}[{index}].obligated_party",
        ).lower()
        if obligated_party not in _OBLIGATED_PARTIES:
            raise ValueError(f"{field_name}[{index}].obligated_party must be one of: {list(_OBLIGATED_PARTIES)}")
        summary = _require_nonempty_text(obligation.get("summary"), field_name=f"{field_name}[{index}].summary")
        obligation_kind = _require_nonempty_text(
            obligation.get("obligation_kind"),
            field_name=f"{field_name}[{index}].obligation_kind",
        )
        evidence_refs = _normalize_string_list(
            obligation.get("evidence_refs"),
            field_name=f"{field_name}[{index}].evidence_refs",
        )
        obligation_id = f"obl.{_stable_id_fragment(target_project_id, peer_project_id, link_kind, direction, obligation_kind, summary)}"
        row = {
            "obligation_id": obligation_id,
            "obligated_party": obligated_party,
            "obligation_kind": obligation_kind,
            "summary": summary,
            "evidence_refs": evidence_refs,
        }
        extra = sorted(set(obligation.keys()) - {"obligated_party", "obligation_kind", "summary", "evidence_refs"})
        if extra:
            raise ValueError(f"{field_name}[{index}] has unexpected keys: {extra}")
        obligations.append(row)
    obligations.sort(key=lambda row: (row["obligated_party"], row["obligation_kind"], row["obligation_id"]))
    return obligations


def _normalize_link_rows(
    raw_value: Any,
    *,
    field_name: str,
    target_project_id: str,
    peer_project_ids: set[str],
    bucket: str,
) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError(f"{field_name} must be a list")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_value):
        link = _require_mapping(item, field_name=f"{field_name}[{index}]")
        peer_project_id = _require_nonempty_text(
            link.get("peer_project_id"),
            field_name=f"{field_name}[{index}].peer_project_id",
        )
        if peer_project_id not in peer_project_ids:
            raise ValueError(f"{field_name}[{index}].peer_project_id must be declared in peer_projects")
        link_kind = _require_nonempty_text(link.get("link_kind"), field_name=f"{field_name}[{index}].link_kind")
        direction = _normalize_direction(link.get("direction"), field_name=f"{field_name}[{index}].direction")
        summary = _require_nonempty_text(link.get("summary"), field_name=f"{field_name}[{index}].summary")
        evidence_refs = _normalize_string_list(
            link.get("evidence_refs"),
            field_name=f"{field_name}[{index}].evidence_refs",
        )
        confidence_tag = _normalize_confidence_tag(
            link.get("confidence_tag"),
            field_name=f"{field_name}[{index}].confidence_tag",
        )
        interaction_obligations = _normalize_interaction_obligations(
            link.get("interaction_obligations"),
            field_name=f"{field_name}[{index}].interaction_obligations",
            target_project_id=target_project_id,
            peer_project_id=peer_project_id,
            link_kind=link_kind,
            direction=direction,
        )
        link_id = f"lnk.{_stable_id_fragment(target_project_id, peer_project_id, link_kind, direction, bucket)}"
        row = {
            "link_id": link_id,
            "peer_project_id": peer_project_id,
            "link_kind": link_kind,
            "direction": direction,
            "summary": summary,
            "evidence_refs": evidence_refs,
            "confidence_tag": confidence_tag,
            "interaction_obligations": interaction_obligations,
        }
        extra = sorted(
            set(link.keys())
            - {
                "peer_project_id",
                "link_kind",
                "direction",
                "summary",
                "evidence_refs",
                "confidence_tag",
                "interaction_obligations",
            }
        )
        if extra:
            raise ValueError(f"{field_name}[{index}] has unexpected keys: {extra}")
        normalized.append(row)
    normalized.sort(key=lambda row: (row["peer_project_id"], row["link_kind"], row["direction"], row["link_id"]))
    return normalized


def build_req_027_call_2_ecosystem_linkage_reasoning(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build normalized REQ-027 payload for ecosystem linkage reasoning."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_027_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_027_ANALYSIS_TYPE}")
    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")

    target_project = _normalize_target_project(raw.get("target_project"))
    peer_projects = _normalize_peer_projects(raw.get("peer_projects"))
    peer_project_ids = {row["project_id"] for row in peer_projects}

    existing_links = _normalize_link_rows(
        raw.get("existing_links"),
        field_name="existing_links",
        target_project_id=target_project["project_id"],
        peer_project_ids=peer_project_ids,
        bucket="existing",
    )
    missing_links = _normalize_link_rows(
        raw.get("missing_links"),
        field_name="missing_links",
        target_project_id=target_project["project_id"],
        peer_project_ids=peer_project_ids,
        bucket="missing",
    )
    proposed_links = _normalize_link_rows(
        raw.get("proposed_links"),
        field_name="proposed_links",
        target_project_id=target_project["project_id"],
        peer_project_ids=peer_project_ids,
        bucket="proposed",
    )

    totals = {
        "peer_projects": len(peer_projects),
        "existing_links": len(existing_links),
        "missing_links": len(missing_links),
        "proposed_links": len(proposed_links),
        "interaction_obligations": sum(
            len(row["interaction_obligations"]) for row in (existing_links + missing_links + proposed_links)
        ),
    }

    output_payload = {
        "ok": True,
        "schema_version": REQ_027_SCHEMA_VERSION,
        "requirement_id": REQ_027_REQUIREMENT_ID,
        "analysis_type": REQ_027_ANALYSIS_TYPE,
        "call_id": REQ_027_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "target_project": target_project,
        "peer_projects": peer_projects,
        "linkage_reasoning": {
            "existing_links": existing_links,
            "missing_links": missing_links,
            "proposed_links": proposed_links,
        },
        "totals": totals,
    }

    errors = validate_req_027_call_2_ecosystem_linkage_reasoning(output_payload)
    if errors:
        raise ValueError(f"built REQ-027 payload failed validation: {errors}")
    return output_payload


def validate_req_027_call_2_ecosystem_linkage_reasoning(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-027 Call-2 ecosystem linkage reasoning payload shape."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    required_top = {
        "ok",
        "schema_version",
        "requirement_id",
        "analysis_type",
        "call_id",
        "checked_at_utc",
        "target_project",
        "peer_projects",
        "linkage_reasoning",
        "totals",
    }
    top_keys = set(payload.keys())
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - required_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("ok") is not True:
        errors.append("ok must be true")
    if payload.get("schema_version") != REQ_027_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_027_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_027_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_027_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_027_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_027_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_027_CALL_ID:
        errors.append(f"call_id must be {REQ_027_CALL_ID}")
    if not isinstance(payload.get("checked_at_utc"), str) or not str(payload.get("checked_at_utc")).strip():
        errors.append("checked_at_utc must be a non-empty string")

    target_project = payload.get("target_project")
    if not isinstance(target_project, Mapping):
        errors.append("target_project must be an object")
        target_project = {}
    else:
        expected_target_keys = {"project_id", "project_root"}
        target_keys = set(target_project.keys())
        missing_target = sorted(expected_target_keys - target_keys)
        if missing_target:
            errors.append(f"target_project missing keys: {missing_target}")
        unexpected_target = sorted(target_keys - expected_target_keys)
        if unexpected_target:
            errors.append(f"target_project has unexpected keys: {unexpected_target}")
        if not isinstance(target_project.get("project_id"), str) or not str(target_project.get("project_id")).strip():
            errors.append("target_project.project_id must be a non-empty string")
        root = target_project.get("project_root")
        if not isinstance(root, str) or not root.strip():
            errors.append("target_project.project_root must be a non-empty string")
        elif not root.startswith("/"):
            errors.append("target_project.project_root must be an absolute path")

    peer_projects = payload.get("peer_projects")
    peer_project_ids: set[str] = set()
    if not isinstance(peer_projects, list) or not peer_projects:
        errors.append("peer_projects must be a non-empty list")
        peer_projects = []
    else:
        for index, item in enumerate(peer_projects):
            if not isinstance(item, Mapping):
                errors.append(f"peer_projects[{index}] must be an object")
                continue
            expected_peer_keys = {"project_id", "project_root"}
            peer_keys = set(item.keys())
            missing_peer = sorted(expected_peer_keys - peer_keys)
            if missing_peer:
                errors.append(f"peer_projects[{index}] missing keys: {missing_peer}")
            unexpected_peer = sorted(peer_keys - expected_peer_keys)
            if unexpected_peer:
                errors.append(f"peer_projects[{index}] has unexpected keys: {unexpected_peer}")
            project_id = item.get("project_id")
            if not isinstance(project_id, str) or not project_id.strip():
                errors.append(f"peer_projects[{index}].project_id must be a non-empty string")
            else:
                peer_project_ids.add(project_id)
            root = item.get("project_root")
            if not isinstance(root, str) or not root.strip():
                errors.append(f"peer_projects[{index}].project_root must be a non-empty string")
            elif not root.startswith("/"):
                errors.append(f"peer_projects[{index}].project_root must be an absolute path")

    linkage_reasoning = payload.get("linkage_reasoning")
    if not isinstance(linkage_reasoning, Mapping):
        errors.append("linkage_reasoning must be an object")
        return errors

    expected_reasoning_keys = {"existing_links", "missing_links", "proposed_links"}
    reasoning_keys = set(linkage_reasoning.keys())
    missing_reasoning = sorted(expected_reasoning_keys - reasoning_keys)
    if missing_reasoning:
        errors.append(f"linkage_reasoning missing keys: {missing_reasoning}")
    unexpected_reasoning = sorted(reasoning_keys - expected_reasoning_keys)
    if unexpected_reasoning:
        errors.append(f"linkage_reasoning has unexpected keys: {unexpected_reasoning}")

    for bucket in ("existing_links", "missing_links", "proposed_links"):
        rows = linkage_reasoning.get(bucket)
        if not isinstance(rows, list):
            errors.append(f"linkage_reasoning.{bucket} must be a list")
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                errors.append(f"linkage_reasoning.{bucket}[{index}] must be an object")
                continue
            expected_link_keys = {
                "link_id",
                "peer_project_id",
                "link_kind",
                "direction",
                "summary",
                "evidence_refs",
                "confidence_tag",
                "interaction_obligations",
            }
            row_keys = set(row.keys())
            missing_link = sorted(expected_link_keys - row_keys)
            if missing_link:
                errors.append(f"linkage_reasoning.{bucket}[{index}] missing keys: {missing_link}")
            unexpected_link = sorted(row_keys - expected_link_keys)
            if unexpected_link:
                errors.append(f"linkage_reasoning.{bucket}[{index}] has unexpected keys: {unexpected_link}")
            link_id = row.get("link_id")
            if not isinstance(link_id, str) or not link_id.startswith("lnk.") or len(link_id) < 6:
                errors.append(f"linkage_reasoning.{bucket}[{index}].link_id must be a string like lnk.<id>")
            peer_project_id = row.get("peer_project_id")
            if not isinstance(peer_project_id, str) or not peer_project_id.strip():
                errors.append(f"linkage_reasoning.{bucket}[{index}].peer_project_id must be a non-empty string")
            elif peer_project_ids and peer_project_id not in peer_project_ids:
                errors.append(
                    f"linkage_reasoning.{bucket}[{index}].peer_project_id must be declared in peer_projects"
                )
            link_kind = row.get("link_kind")
            if not isinstance(link_kind, str) or not link_kind.strip():
                errors.append(f"linkage_reasoning.{bucket}[{index}].link_kind must be a non-empty string")
            direction = row.get("direction")
            if direction not in _DIRECTIONS:
                errors.append(f"linkage_reasoning.{bucket}[{index}].direction must be one of: {list(_DIRECTIONS)}")
            summary = row.get("summary")
            if not isinstance(summary, str) or not summary.strip():
                errors.append(f"linkage_reasoning.{bucket}[{index}].summary must be a non-empty string")
            evidence_refs = row.get("evidence_refs")
            if not isinstance(evidence_refs, list):
                errors.append(f"linkage_reasoning.{bucket}[{index}].evidence_refs must be a list of strings")
            else:
                for ev_index, ev in enumerate(evidence_refs):
                    if not isinstance(ev, str) or not ev.strip():
                        errors.append(
                            f"linkage_reasoning.{bucket}[{index}].evidence_refs[{ev_index}] must be non-empty string"
                        )
            confidence_tag = row.get("confidence_tag")
            if confidence_tag not in _CONFIDENCE_TAGS:
                errors.append(
                    f"linkage_reasoning.{bucket}[{index}].confidence_tag must be one of: {list(_CONFIDENCE_TAGS)}"
                )
            obligations = row.get("interaction_obligations")
            if not isinstance(obligations, list):
                errors.append(f"linkage_reasoning.{bucket}[{index}].interaction_obligations must be a list")
                continue
            for ob_index, obligation in enumerate(obligations):
                if not isinstance(obligation, Mapping):
                    errors.append(
                        f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}] must be an object"
                    )
                    continue
                expected_ob_keys = {"obligation_id", "obligated_party", "obligation_kind", "summary", "evidence_refs"}
                ob_keys = set(obligation.keys())
                missing_ob = sorted(expected_ob_keys - ob_keys)
                if missing_ob:
                    errors.append(
                        f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}] missing keys: {missing_ob}"
                    )
                unexpected_ob = sorted(ob_keys - expected_ob_keys)
                if unexpected_ob:
                    errors.append(
                        f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}] has unexpected keys: {unexpected_ob}"
                    )
                ob_id = obligation.get("obligation_id")
                if not isinstance(ob_id, str) or not ob_id.startswith("obl.") or len(ob_id) < 6:
                    errors.append(
                        f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}].obligation_id must be like obl.<id>"
                    )
                obligated_party = obligation.get("obligated_party")
                if obligated_party not in _OBLIGATED_PARTIES:
                    errors.append(
                        f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}].obligated_party must be one of: {list(_OBLIGATED_PARTIES)}"
                    )
                obligation_kind = obligation.get("obligation_kind")
                if not isinstance(obligation_kind, str) or not obligation_kind.strip():
                    errors.append(
                        f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}].obligation_kind must be a non-empty string"
                    )
                ob_summary = obligation.get("summary")
                if not isinstance(ob_summary, str) or not ob_summary.strip():
                    errors.append(
                        f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}].summary must be a non-empty string"
                    )
                ob_evidence = obligation.get("evidence_refs")
                if not isinstance(ob_evidence, list):
                    errors.append(
                        f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}].evidence_refs must be a list of strings"
                    )
                else:
                    for ev_index, ev in enumerate(ob_evidence):
                        if not isinstance(ev, str) or not ev.strip():
                            errors.append(
                                f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}].evidence_refs[{ev_index}] must be non-empty string"
                            )

    totals = payload.get("totals")
    if not isinstance(totals, Mapping):
        errors.append("totals must be an object")
    else:
        expected_total_keys = {
            "peer_projects",
            "existing_links",
            "missing_links",
            "proposed_links",
            "interaction_obligations",
        }
        total_keys = set(totals.keys())
        missing_totals = sorted(expected_total_keys - total_keys)
        if missing_totals:
            errors.append(f"totals missing keys: {missing_totals}")
        unexpected_totals = sorted(total_keys - expected_total_keys)
        if unexpected_totals:
            errors.append(f"totals has unexpected keys: {unexpected_totals}")
        for key in expected_total_keys:
            value = totals.get(key)
            if not isinstance(value, int) or value < 0:
                errors.append(f"totals.{key} must be a non-negative integer")

    return errors


def run(payload: dict[str, Any]) -> dict[str, Any]:
    analysis_type = str(payload.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_027_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_027_ANALYSIS_TYPE}")
    return build_req_027_call_2_ecosystem_linkage_reasoning(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="REQ-027 Call-2 ecosystem linkage reasoning contract surface.")
    parser.add_argument("--input-json", required=True, help='Input payload path or "-" for stdin.')
    parser.add_argument("--output-json", default="-", help='Output path or "-" for stdout.')
    parser.add_argument("--json-pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args(sys.argv[1:] if argv is None else list(argv))

    if args.input_json == "-":
        raw_payload = json.loads(sys.stdin.read())
    else:
        raw_payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    if not isinstance(raw_payload, dict):
        raise SystemExit("input payload must be a JSON object")

    output_payload = run(raw_payload)
    rendered = json.dumps(output_payload, indent=2 if args.json_pretty else None, sort_keys=False)
    if args.output_json == "-":
        print(rendered)
    else:
        target = Path(args.output_json)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

