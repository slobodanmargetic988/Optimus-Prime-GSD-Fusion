#!/usr/bin/env python3
"""REQ-008 research packet ingestion and normalization contract surface."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

TOOL = "strategy-context-sweep"
TOOL_VERSION = "1.0.0"
REQUIREMENT_ID = "REQ-008"
SCHEMA_VERSION = "req-008.research-packet-ingestion-and-normalization.v1"
ALLOWED_RISK_LEVELS = {"low", "medium", "high", "critical"}

LOG_ROOT = Path("/Users/slobodan/projects/LOGS")
LOG_PATH = LOG_ROOT / "strategy_context_sweep.log"
LOG_BUDGET_CHECK_STAMP = LOG_ROOT / ".log_budget_check.strategy_context_sweep"
LOG_BUDGET_CHECK_INTERVAL_SECONDS = 15 * 60
LOG_BUDGET_MAX_BYTES = 3 * 1024 * 1024 * 1024


class Req008Error(ValueError):
    """Raised when REQ-008 normalization input is malformed."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


def _require_text(value: Any, *, field_name: str) -> str:
    text = _as_text(value)
    if not text:
        raise Req008Error(f"{field_name} must be a non-empty string")
    return text


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise Req008Error(f"{field_name} must be an object")
    return value


def _require_sequence(value: Any, *, field_name: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise Req008Error(f"{field_name} must be an array")
    return value


def _normalize_slug(raw_id: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", raw_id.lower()).strip("-")
    return slug or "x"


def _normalize_identity(identity: Mapping[str, Any]) -> dict[str, str]:
    normalized = {
        "project_id": _require_text(identity.get("project_id"), field_name="research_packet.identity.project_id"),
        "run_id": _require_text(identity.get("run_id"), field_name="research_packet.identity.run_id"),
        "event_id": _require_text(identity.get("event_id"), field_name="research_packet.identity.event_id"),
    }
    for optional_key in ("era_id", "plan_id"):
        optional_value = _as_text(identity.get(optional_key))
        if optional_value:
            normalized[optional_key] = optional_value
    return normalized


def _normalize_topics(topics_raw: Sequence[Any]) -> list[dict[str, Any]]:
    if not topics_raw:
        raise Req008Error("research_packet.topics must contain at least one topic")

    normalized_topics: list[dict[str, Any]] = []
    topic_ids: set[str] = set()
    for index, row in enumerate(topics_raw):
        topic = _require_mapping(row, field_name=f"research_packet.topics[{index}]")
        topic_id = _require_text(topic.get("topic_id"), field_name=f"research_packet.topics[{index}].topic_id")
        if topic_id in topic_ids:
            raise Req008Error(f"research_packet.topics[{index}].topic_id duplicates {topic_id}")
        topic_ids.add(topic_id)

        title = _require_text(topic.get("title"), field_name=f"research_packet.topics[{index}].title")
        recommendation_summary = _require_text(
            topic.get("recommendation_summary"),
            field_name=f"research_packet.topics[{index}].recommendation_summary",
        )
        risk_level = _require_text(topic.get("risk_level"), field_name=f"research_packet.topics[{index}].risk_level")
        if risk_level not in ALLOWED_RISK_LEVELS:
            raise Req008Error(
                f"research_packet.topics[{index}].risk_level must be one of {sorted(ALLOWED_RISK_LEVELS)}"
            )

        tradeoffs_raw = _require_sequence(topic.get("tradeoffs"), field_name=f"research_packet.topics[{index}].tradeoffs")
        tradeoffs = [
            _require_text(item, field_name=f"research_packet.topics[{index}].tradeoffs[{tradeoff_index}]")
            for tradeoff_index, item in enumerate(tradeoffs_raw)
        ]
        if not tradeoffs:
            raise Req008Error(f"research_packet.topics[{index}].tradeoffs must contain at least one item")

        normalized_topics.append(
            {
                "topic_id": topic_id,
                "title": title,
                "recommendation_summary": recommendation_summary,
                "risk_level": risk_level,
                "tradeoffs": tradeoffs,
            }
        )
    return normalized_topics


def _normalize_unknown_questions(open_questions_raw: Sequence[Any]) -> list[str]:
    normalized: list[str] = []
    for index, raw_question in enumerate(open_questions_raw):
        normalized.append(_require_text(raw_question, field_name=f"research_packet.open_questions[{index}]"))
    return normalized


def _normalize_evidence_refs(evidence_refs_raw: Sequence[Any]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    seen_artifact_ids: set[str] = set()
    for index, row in enumerate(evidence_refs_raw):
        evidence = _require_mapping(row, field_name=f"research_packet.evidence_refs[{index}]")
        artifact_id = _require_text(
            evidence.get("artifact_id"), field_name=f"research_packet.evidence_refs[{index}].artifact_id"
        )
        if artifact_id in seen_artifact_ids:
            raise Req008Error(f"research_packet.evidence_refs[{index}].artifact_id duplicates {artifact_id}")
        seen_artifact_ids.add(artifact_id)

        normalized_row: dict[str, str] = {
            "artifact_id": artifact_id,
            "kind": _require_text(evidence.get("kind"), field_name=f"research_packet.evidence_refs[{index}].kind"),
            "uri": _require_text(evidence.get("uri"), field_name=f"research_packet.evidence_refs[{index}].uri"),
        }
        notes = _as_text(evidence.get("notes"))
        if notes:
            normalized_row["notes"] = notes
        normalized.append(normalized_row)
    return normalized


def _normalize_recommendation_ids(recommendation_ids: Sequence[Any]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(recommendation_ids):
        recommendation_id = _require_text(value, field_name=f"recommendation_ids[{index}]")
        if recommendation_id in seen:
            raise Req008Error(f"recommendation_ids[{index}] duplicates {recommendation_id}")
        seen.add(recommendation_id)
        normalized.append(recommendation_id)
    if not normalized:
        raise Req008Error("recommendation_ids must contain at least one recommendation id")
    return normalized


def _normalize_recommendation_topic_map(
    recommendation_ids: Sequence[str],
    topic_ids: Sequence[str],
    recommendation_topic_map: Mapping[str, Any] | None,
) -> dict[str, list[str]]:
    topic_id_set = set(topic_ids)
    defaults = list(topic_ids)

    if recommendation_topic_map is None:
        return {recommendation_id: list(defaults) for recommendation_id in recommendation_ids}

    normalized: dict[str, list[str]] = {}
    provided_keys = set(recommendation_topic_map.keys())

    unknown_keys = sorted(provided_keys - set(recommendation_ids))
    if unknown_keys:
        raise Req008Error(f"recommendation_topic_map contains unknown recommendation ids: {unknown_keys}")

    for recommendation_id in recommendation_ids:
        raw_topics = recommendation_topic_map.get(recommendation_id)
        if raw_topics is None:
            normalized[recommendation_id] = list(defaults)
            continue

        topic_values = _require_sequence(raw_topics, field_name=f"recommendation_topic_map.{recommendation_id}")
        unique_topics: list[str] = []
        seen_topics: set[str] = set()
        for topic_index, raw_topic_id in enumerate(topic_values):
            topic_id = _require_text(
                raw_topic_id,
                field_name=f"recommendation_topic_map.{recommendation_id}[{topic_index}]",
            )
            if topic_id not in topic_id_set:
                raise Req008Error(
                    f"recommendation_topic_map.{recommendation_id}[{topic_index}] references unknown topic_id {topic_id}"
                )
            if topic_id in seen_topics:
                continue
            seen_topics.add(topic_id)
            unique_topics.append(topic_id)

        if not unique_topics:
            raise Req008Error(f"recommendation_topic_map.{recommendation_id} must include at least one topic_id")
        normalized[recommendation_id] = unique_topics

    return normalized


def _normalize_timestamp(raw_value: Any) -> str:
    if raw_value is None:
        return utc_now_iso()
    text = _require_text(raw_value, field_name="normalized_at_utc")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Req008Error(f"normalized_at_utc must be a valid ISO-8601 timestamp: {exc}") from exc
    if parsed.tzinfo is None:
        raise Req008Error("normalized_at_utc must include timezone information")
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_req_008_research_packet_ingestion_and_normalization(
    *,
    research_packet: Mapping[str, Any],
    recommendation_ids: Sequence[Any],
    recommendation_topic_map: Mapping[str, Any] | None = None,
    normalized_at_utc: str | None = None,
) -> dict[str, Any]:
    """Normalize research packet anchors into strategy context for REQ-008."""
    packet = _require_mapping(research_packet, field_name="research_packet")
    packet_schema_version = _require_text(
        packet.get("schema_version"), field_name="research_packet.schema_version"
    )
    identity = _normalize_identity(_require_mapping(packet.get("identity"), field_name="research_packet.identity"))

    topics = _normalize_topics(_require_sequence(packet.get("topics"), field_name="research_packet.topics"))
    open_questions = _normalize_unknown_questions(
        _require_sequence(packet.get("open_questions"), field_name="research_packet.open_questions")
    )
    evidence_refs = _normalize_evidence_refs(
        _require_sequence(packet.get("evidence_refs"), field_name="research_packet.evidence_refs")
    )

    normalized_recommendation_ids = _normalize_recommendation_ids(recommendation_ids)
    topic_ids = [topic["topic_id"] for topic in topics]
    recommendation_topic_links = _normalize_recommendation_topic_map(
        normalized_recommendation_ids,
        topic_ids,
        recommendation_topic_map,
    )

    normalized_timestamp = _normalize_timestamp(normalized_at_utc)

    assumptions: list[dict[str, Any]] = []
    unknowns: list[dict[str, Any]] = []
    risk_evidence: list[dict[str, Any]] = []

    topic_to_assumption_id: dict[str, str] = {}
    topic_to_risk_id: dict[str, str] = {}

    for index, topic in enumerate(topics, start=1):
        slug = _normalize_slug(topic["topic_id"])
        assumption_id = f"assumption.{index:03d}.{slug}"
        risk_id = f"risk-evidence.{index:03d}.{slug}"

        assumptions.append(
            {
                "assumption_id": assumption_id,
                "topic_id": topic["topic_id"],
                "statement": topic["recommendation_summary"],
                "provenance": {
                    "research_event_id": identity["event_id"],
                    "source_field": "topics[].recommendation_summary",
                },
            }
        )
        topic_to_assumption_id[topic["topic_id"]] = assumption_id

        risk_evidence.append(
            {
                "risk_evidence_id": risk_id,
                "topic_id": topic["topic_id"],
                "risk_level": topic["risk_level"],
                "risk_statement": topic["tradeoffs"][0],
                "evidence_refs": [dict(row) for row in evidence_refs],
                "provenance": {
                    "research_event_id": identity["event_id"],
                    "source_fields": ["topics[].risk_level", "topics[].tradeoffs", "evidence_refs[]"],
                },
            }
        )
        topic_to_risk_id[topic["topic_id"]] = risk_id

    for index, question in enumerate(open_questions, start=1):
        unknowns.append(
            {
                "unknown_id": f"unknown.{index:03d}",
                "question": question,
                "provenance": {
                    "research_event_id": identity["event_id"],
                    "source_field": "open_questions[]",
                },
            }
        )

    all_unknown_ids = [row["unknown_id"] for row in unknowns]
    recommendation_rationale_provenance: list[dict[str, Any]] = []

    for recommendation_id in normalized_recommendation_ids:
        linked_topic_ids = recommendation_topic_links[recommendation_id]
        linked_assumption_ids = [topic_to_assumption_id[topic_id] for topic_id in linked_topic_ids]
        linked_risk_ids = [topic_to_risk_id[topic_id] for topic_id in linked_topic_ids]

        recommendation_rationale_provenance.append(
            {
                "recommendation_id": recommendation_id,
                "rationale_field": "rationale",
                "linked_assumption_ids": linked_assumption_ids,
                "linked_unknown_ids": list(all_unknown_ids),
                "linked_risk_evidence_ids": linked_risk_ids,
                "research_provenance": {
                    "research_packet_event_id": identity["event_id"],
                    "source_schema_version": packet_schema_version,
                    "linked_topic_ids": linked_topic_ids,
                },
                "provenance_refs": [dict(row) for row in evidence_refs],
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "requirement_id": REQUIREMENT_ID,
        "research_packet_identity": identity,
        "strategy_context": {
            "assumptions": assumptions,
            "unknowns": unknowns,
            "risk_evidence": risk_evidence,
        },
        "recommendation_rationale_provenance": recommendation_rationale_provenance,
        "source": {
            "normalized_from_schema_version": packet_schema_version,
            "normalized_at_utc": normalized_timestamp,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
        },
    }


def validate_req_008_research_packet_ingestion_and_normalization(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-008 normalized payload structure and linkage invariants."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be an object"]

    required_top_level = {
        "schema_version",
        "requirement_id",
        "research_packet_identity",
        "strategy_context",
        "recommendation_rationale_provenance",
        "source",
    }
    top_keys = set(payload.keys())
    missing_top = sorted(required_top_level - top_keys)
    unexpected_top = sorted(top_keys - required_top_level)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQUIREMENT_ID}")

    identity = payload.get("research_packet_identity")
    if not isinstance(identity, Mapping):
        errors.append("research_packet_identity must be an object")
        identity = {}

    for key in ("project_id", "run_id", "event_id"):
        if not _as_text(identity.get(key)):
            errors.append(f"research_packet_identity.{key} must be a non-empty string")

    strategy_context = payload.get("strategy_context")
    if not isinstance(strategy_context, Mapping):
        errors.append("strategy_context must be an object")
        strategy_context = {}

    assumptions = strategy_context.get("assumptions")
    if not isinstance(assumptions, Sequence) or isinstance(assumptions, (str, bytes, bytearray)):
        errors.append("strategy_context.assumptions must be an array")
        assumptions = []

    unknowns = strategy_context.get("unknowns")
    if not isinstance(unknowns, Sequence) or isinstance(unknowns, (str, bytes, bytearray)):
        errors.append("strategy_context.unknowns must be an array")
        unknowns = []

    risk_evidence = strategy_context.get("risk_evidence")
    if not isinstance(risk_evidence, Sequence) or isinstance(risk_evidence, (str, bytes, bytearray)):
        errors.append("strategy_context.risk_evidence must be an array")
        risk_evidence = []

    assumption_ids: set[str] = set()
    unknown_ids: set[str] = set()
    risk_ids: set[str] = set()
    topic_ids: set[str] = set()
    evidence_ids: set[str] = set()

    for index, row in enumerate(assumptions):
        if not isinstance(row, Mapping):
            errors.append(f"strategy_context.assumptions[{index}] must be an object")
            continue
        assumption_id = _as_text(row.get("assumption_id"))
        topic_id = _as_text(row.get("topic_id"))
        statement = _as_text(row.get("statement"))
        provenance = row.get("provenance")

        if not assumption_id:
            errors.append(f"strategy_context.assumptions[{index}].assumption_id is required")
        elif assumption_id in assumption_ids:
            errors.append(f"strategy_context.assumptions[{index}].assumption_id duplicates {assumption_id}")
        else:
            assumption_ids.add(assumption_id)

        if not topic_id:
            errors.append(f"strategy_context.assumptions[{index}].topic_id is required")
        else:
            topic_ids.add(topic_id)

        if not statement:
            errors.append(f"strategy_context.assumptions[{index}].statement is required")

        if not isinstance(provenance, Mapping):
            errors.append(f"strategy_context.assumptions[{index}].provenance must be an object")
        else:
            if _as_text(provenance.get("research_event_id")) != _as_text(identity.get("event_id")):
                errors.append(
                    f"strategy_context.assumptions[{index}].provenance.research_event_id must match research_packet_identity.event_id"
                )
            if not _as_text(provenance.get("source_field")):
                errors.append(f"strategy_context.assumptions[{index}].provenance.source_field is required")

    for index, row in enumerate(unknowns):
        if not isinstance(row, Mapping):
            errors.append(f"strategy_context.unknowns[{index}] must be an object")
            continue
        unknown_id = _as_text(row.get("unknown_id"))
        question = _as_text(row.get("question"))
        provenance = row.get("provenance")

        if not unknown_id:
            errors.append(f"strategy_context.unknowns[{index}].unknown_id is required")
        elif unknown_id in unknown_ids:
            errors.append(f"strategy_context.unknowns[{index}].unknown_id duplicates {unknown_id}")
        else:
            unknown_ids.add(unknown_id)

        if not question:
            errors.append(f"strategy_context.unknowns[{index}].question is required")

        if not isinstance(provenance, Mapping):
            errors.append(f"strategy_context.unknowns[{index}].provenance must be an object")
        else:
            if _as_text(provenance.get("research_event_id")) != _as_text(identity.get("event_id")):
                errors.append(
                    f"strategy_context.unknowns[{index}].provenance.research_event_id must match research_packet_identity.event_id"
                )
            if not _as_text(provenance.get("source_field")):
                errors.append(f"strategy_context.unknowns[{index}].provenance.source_field is required")

    for index, row in enumerate(risk_evidence):
        if not isinstance(row, Mapping):
            errors.append(f"strategy_context.risk_evidence[{index}] must be an object")
            continue
        risk_id = _as_text(row.get("risk_evidence_id"))
        topic_id = _as_text(row.get("topic_id"))
        risk_level = _as_text(row.get("risk_level"))
        risk_statement = _as_text(row.get("risk_statement"))
        evidence_refs = row.get("evidence_refs")
        provenance = row.get("provenance")

        if not risk_id:
            errors.append(f"strategy_context.risk_evidence[{index}].risk_evidence_id is required")
        elif risk_id in risk_ids:
            errors.append(f"strategy_context.risk_evidence[{index}].risk_evidence_id duplicates {risk_id}")
        else:
            risk_ids.add(risk_id)

        if not topic_id:
            errors.append(f"strategy_context.risk_evidence[{index}].topic_id is required")
        else:
            topic_ids.add(topic_id)

        if risk_level not in ALLOWED_RISK_LEVELS:
            errors.append(
                f"strategy_context.risk_evidence[{index}].risk_level must be one of {sorted(ALLOWED_RISK_LEVELS)}"
            )
        if not risk_statement:
            errors.append(f"strategy_context.risk_evidence[{index}].risk_statement is required")

        if not isinstance(evidence_refs, Sequence) or isinstance(evidence_refs, (str, bytes, bytearray)):
            errors.append(f"strategy_context.risk_evidence[{index}].evidence_refs must be an array")
        else:
            for evidence_index, evidence_row in enumerate(evidence_refs):
                if not isinstance(evidence_row, Mapping):
                    errors.append(
                        f"strategy_context.risk_evidence[{index}].evidence_refs[{evidence_index}] must be an object"
                    )
                    continue
                artifact_id = _as_text(evidence_row.get("artifact_id"))
                kind = _as_text(evidence_row.get("kind"))
                uri = _as_text(evidence_row.get("uri"))
                if not artifact_id:
                    errors.append(
                        f"strategy_context.risk_evidence[{index}].evidence_refs[{evidence_index}].artifact_id is required"
                    )
                else:
                    evidence_ids.add(artifact_id)
                if not kind:
                    errors.append(
                        f"strategy_context.risk_evidence[{index}].evidence_refs[{evidence_index}].kind is required"
                    )
                if not uri:
                    errors.append(
                        f"strategy_context.risk_evidence[{index}].evidence_refs[{evidence_index}].uri is required"
                    )

        if not isinstance(provenance, Mapping):
            errors.append(f"strategy_context.risk_evidence[{index}].provenance must be an object")
        else:
            if _as_text(provenance.get("research_event_id")) != _as_text(identity.get("event_id")):
                errors.append(
                    f"strategy_context.risk_evidence[{index}].provenance.research_event_id must match research_packet_identity.event_id"
                )
            source_fields = provenance.get("source_fields")
            if not isinstance(source_fields, Sequence) or isinstance(source_fields, (str, bytes, bytearray)):
                errors.append(f"strategy_context.risk_evidence[{index}].provenance.source_fields must be an array")

    rationale_links = payload.get("recommendation_rationale_provenance")
    if not isinstance(rationale_links, Sequence) or isinstance(rationale_links, (str, bytes, bytearray)):
        errors.append("recommendation_rationale_provenance must be an array")
        rationale_links = []

    for index, row in enumerate(rationale_links):
        if not isinstance(row, Mapping):
            errors.append(f"recommendation_rationale_provenance[{index}] must be an object")
            continue

        recommendation_id = _as_text(row.get("recommendation_id"))
        rationale_field = _as_text(row.get("rationale_field"))
        linked_assumptions = row.get("linked_assumption_ids")
        linked_unknowns = row.get("linked_unknown_ids")
        linked_risks = row.get("linked_risk_evidence_ids")
        research_provenance = row.get("research_provenance")
        provenance_refs = row.get("provenance_refs")

        if not recommendation_id:
            errors.append(f"recommendation_rationale_provenance[{index}].recommendation_id is required")
        if rationale_field != "rationale":
            errors.append(f"recommendation_rationale_provenance[{index}].rationale_field must equal rationale")

        for field_name, linked_value, known_ids in (
            ("linked_assumption_ids", linked_assumptions, assumption_ids),
            ("linked_unknown_ids", linked_unknowns, unknown_ids),
            ("linked_risk_evidence_ids", linked_risks, risk_ids),
        ):
            if not isinstance(linked_value, Sequence) or isinstance(linked_value, (str, bytes, bytearray)):
                errors.append(f"recommendation_rationale_provenance[{index}].{field_name} must be an array")
                continue
            if not linked_value:
                errors.append(f"recommendation_rationale_provenance[{index}].{field_name} must not be empty")
                continue
            for link_index, linked_id_raw in enumerate(linked_value):
                linked_id = _as_text(linked_id_raw)
                if not linked_id:
                    errors.append(
                        f"recommendation_rationale_provenance[{index}].{field_name}[{link_index}] must be non-empty"
                    )
                    continue
                if linked_id not in known_ids:
                    errors.append(
                        f"recommendation_rationale_provenance[{index}].{field_name}[{link_index}] references unknown id {linked_id}"
                    )

        if not isinstance(research_provenance, Mapping):
            errors.append(f"recommendation_rationale_provenance[{index}].research_provenance must be an object")
        else:
            if _as_text(research_provenance.get("research_packet_event_id")) != _as_text(identity.get("event_id")):
                errors.append(
                    f"recommendation_rationale_provenance[{index}].research_provenance.research_packet_event_id must match research_packet_identity.event_id"
                )
            linked_topics = research_provenance.get("linked_topic_ids")
            if not isinstance(linked_topics, Sequence) or isinstance(linked_topics, (str, bytes, bytearray)):
                errors.append(
                    f"recommendation_rationale_provenance[{index}].research_provenance.linked_topic_ids must be an array"
                )
            else:
                for topic_index, topic_raw in enumerate(linked_topics):
                    topic_id = _as_text(topic_raw)
                    if not topic_id:
                        errors.append(
                            f"recommendation_rationale_provenance[{index}].research_provenance.linked_topic_ids[{topic_index}] must be non-empty"
                        )
                    elif topic_id not in topic_ids:
                        errors.append(
                            f"recommendation_rationale_provenance[{index}].research_provenance.linked_topic_ids[{topic_index}] references unknown topic {topic_id}"
                        )

        if not isinstance(provenance_refs, Sequence) or isinstance(provenance_refs, (str, bytes, bytearray)):
            errors.append(f"recommendation_rationale_provenance[{index}].provenance_refs must be an array")
        else:
            for ref_index, ref_row in enumerate(provenance_refs):
                if not isinstance(ref_row, Mapping):
                    errors.append(
                        f"recommendation_rationale_provenance[{index}].provenance_refs[{ref_index}] must be an object"
                    )
                    continue
                artifact_id = _as_text(ref_row.get("artifact_id"))
                if not artifact_id:
                    errors.append(
                        f"recommendation_rationale_provenance[{index}].provenance_refs[{ref_index}].artifact_id is required"
                    )
                    continue
                if artifact_id not in evidence_ids:
                    errors.append(
                        f"recommendation_rationale_provenance[{index}].provenance_refs[{ref_index}] references unknown artifact_id {artifact_id}"
                    )

    source = payload.get("source")
    if not isinstance(source, Mapping):
        errors.append("source must be an object")
    else:
        if _as_text(source.get("normalized_from_schema_version")) == "":
            errors.append("source.normalized_from_schema_version must be a non-empty string")
        if _as_text(source.get("normalized_at_utc")) == "":
            errors.append("source.normalized_at_utc must be a non-empty string")
        if source.get("tool") != TOOL:
            errors.append(f"source.tool must be {TOOL}")
        if source.get("tool_version") != TOOL_VERSION:
            errors.append(f"source.tool_version must be {TOOL_VERSION}")

    return errors


def _json_dumps(payload: Mapping[str, Any], pretty: bool) -> str:
    if pretty:
        return json.dumps(payload, indent=2, sort_keys=False) + "\n"
    return json.dumps(payload, separators=(",", ":"), sort_keys=False) + "\n"


def _enforce_log_budget(log_root: Path) -> None:
    log_root.mkdir(parents=True, exist_ok=True)
    now_epoch = time.time()
    if LOG_BUDGET_CHECK_STAMP.exists():
        last_checked = LOG_BUDGET_CHECK_STAMP.stat().st_mtime
        if (now_epoch - last_checked) < LOG_BUDGET_CHECK_INTERVAL_SECONDS:
            return

    log_files = [path for path in log_root.rglob("*") if path.is_file() and path != LOG_BUDGET_CHECK_STAMP]
    total_bytes = sum(path.stat().st_size for path in log_files)
    if total_bytes > LOG_BUDGET_MAX_BYTES:
        for path in sorted(log_files, key=lambda item: item.stat().st_mtime):
            original_size = path.stat().st_size
            if original_size <= 0:
                continue
            path.write_text("", encoding="utf-8")
            total_bytes -= original_size
            if total_bytes <= LOG_BUDGET_MAX_BYTES:
                break
    LOG_BUDGET_CHECK_STAMP.touch()


def _timestamped_print(message: str) -> None:
    stamp = utc_now_iso()
    line = f"[{TOOL} {stamp}] {message}"
    print(line, file=sys.stderr, flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _parse_cli_input(input_path: str) -> Mapping[str, Any]:
    raw = sys.stdin.read() if input_path == "-" else Path(input_path).read_text(encoding="utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, Mapping):
        raise Req008Error("input payload must be an object")
    return payload


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Emit REQ-008 research packet normalization payload.")
    parser.add_argument("--input-json", required=True, help="Input JSON path or '-' for stdin.")
    parser.add_argument("--output-json", default="", help="Optional output JSON path.")
    parser.add_argument("--json-pretty", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    _enforce_log_budget(LOG_ROOT)
    _timestamped_print(f"Starting REQ-008 normalization from input source: {args.input_json}")

    try:
        input_payload = _parse_cli_input(args.input_json)
        output_payload = build_req_008_research_packet_ingestion_and_normalization(
            research_packet=_require_mapping(input_payload.get("research_packet"), field_name="input.research_packet"),
            recommendation_ids=_require_sequence(
                input_payload.get("recommendation_ids"), field_name="input.recommendation_ids"
            ),
            recommendation_topic_map=(
                _require_mapping(input_payload.get("recommendation_topic_map"), field_name="input.recommendation_topic_map")
                if input_payload.get("recommendation_topic_map") is not None
                else None
            ),
            normalized_at_utc=input_payload.get("normalized_at_utc"),
        )
    except (Req008Error, json.JSONDecodeError) as exc:
        _timestamped_print(f"REQ-008 normalization failed during input processing: {exc}")
        error_payload = {
            "ok": False,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "requirement_id": REQUIREMENT_ID,
            "reason_code": "input_error",
            "error": _as_text(exc),
        }
        sys.stdout.write(_json_dumps(error_payload, args.json_pretty))
        return 1

    validation_errors = validate_req_008_research_packet_ingestion_and_normalization(output_payload)
    if validation_errors:
        _timestamped_print(
            "REQ-008 normalization failed validation with "
            f"{len(validation_errors)} issue(s)."
        )
        error_payload = {
            "ok": False,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "requirement_id": REQUIREMENT_ID,
            "reason_code": "contract_validation_failed",
            "errors": validation_errors,
        }
        sys.stdout.write(_json_dumps(error_payload, args.json_pretty))
        return 1

    if _as_text(args.output_json):
        output_path = Path(args.output_json).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(_json_dumps(output_payload, True), encoding="utf-8")
        _timestamped_print(f"Wrote REQ-008 normalized payload to {output_path.as_posix()}.")

    _timestamped_print(
        "Completed REQ-008 normalization for "
        f"{len(output_payload['recommendation_rationale_provenance'])} recommendation rationale link row(s)."
    )
    sys.stdout.write(_json_dumps(output_payload, args.json_pretty))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
