#!/usr/bin/env python3
"""REQ-008 and REQ-015 contract/data-model surfaces for strategy context sweep."""

from __future__ import annotations

import argparse
import hashlib
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
REQ_015_REQUIREMENT_ID = "REQ-015"
REQ_015_SCHEMA_VERSION = "req-015.integration-opportunity-detection.v1"
ALLOWED_RISK_LEVELS = {"low", "medium", "high", "critical"}
REASON_CODE_EARTH_SWEEP_EVIDENCE_MISSING = "earth_sweep_evidence_missing"
REASON_CODE_EARTH_SWEEP_STALE_SOURCE_ARTIFACT = "earth_sweep_stale_source_artifact"
REASON_CODE_CONTEXT_DOC_MISSING = "context_doc_missing"
REASON_CODE_PEER_PROJECT_DOC_MISSING = "peer_project_doc_missing"
REASON_CODE_REQ_015_INTERACTION_CONTRACT_MISSING = "interaction_contract_missing"
REASON_CODE_REQ_015_SIDE_EFFECT_NOTES_MISSING = "dependency_side_effect_notes_missing"
REASON_CODE_REQ_015_RECOMMENDATION_CONTEXT_MISSING = "recommendation_context_missing"

LOG_ROOT = Path("/Users/slobodan/projects/LOGS")
LOG_PATH = LOG_ROOT / "strategy_context_sweep.log"
LOG_BUDGET_CHECK_STAMP = LOG_ROOT / ".log_budget_check.strategy_context_sweep"
LOG_BUDGET_CHECK_INTERVAL_SECONDS = 15 * 60
LOG_BUDGET_MAX_BYTES = 3 * 1024 * 1024 * 1024


class Req008Error(ValueError):
    """Raised when REQ-008 normalization input is malformed."""


class Req015Error(ValueError):
    """Raised when REQ-015 integration opportunity input is malformed."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = _as_text(value).lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return False


def _is_stale_evidence_row(row: Mapping[str, Any]) -> bool:
    if _to_bool(row.get("stale")):
        return True
    for field_name in ("status", "state", "freshness"):
        value = _as_text(row.get(field_name)).lower()
        if value in {"stale", "expired"}:
            return True
    return False


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


def _normalize_evidence_refs(evidence_refs_raw: Sequence[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_artifact_ids: set[str] = set()
    for index, row in enumerate(evidence_refs_raw):
        evidence = _require_mapping(row, field_name=f"research_packet.evidence_refs[{index}]")
        artifact_id = _require_text(
            evidence.get("artifact_id"), field_name=f"research_packet.evidence_refs[{index}].artifact_id"
        )
        if artifact_id in seen_artifact_ids:
            raise Req008Error(f"research_packet.evidence_refs[{index}].artifact_id duplicates {artifact_id}")
        seen_artifact_ids.add(artifact_id)

        normalized_row: dict[str, Any] = {
            "artifact_id": artifact_id,
            "kind": _require_text(evidence.get("kind"), field_name=f"research_packet.evidence_refs[{index}].kind"),
            "uri": _require_text(evidence.get("uri"), field_name=f"research_packet.evidence_refs[{index}].uri"),
        }
        notes = _as_text(evidence.get("notes"))
        if notes:
            normalized_row["notes"] = notes
        if _is_stale_evidence_row(evidence):
            normalized_row["stale"] = True
        normalized.append(normalized_row)
    return normalized


def _normalize_string_list(raw_values: Sequence[Any], *, field_name: str, min_items: int = 0) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(raw_values):
        text = _require_text(value, field_name=f"{field_name}[{index}]")
        if text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    if len(normalized) < min_items:
        raise Req008Error(f"{field_name} must contain at least {min_items} item(s)")
    return normalized


def _normalize_recommendation_ids(recommendation_ids: Sequence[Any], *, field_name: str = "recommendation_ids") -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(recommendation_ids):
        recommendation_id = _require_text(value, field_name=f"{field_name}[{index}]")
        if recommendation_id in seen:
            raise Req008Error(f"{field_name}[{index}] duplicates {recommendation_id}")
        seen.add(recommendation_id)
        normalized.append(recommendation_id)
    if not normalized:
        raise Req008Error(f"{field_name} must contain at least one recommendation id")
    return normalized


def _normalize_recommendations(
    *,
    recommendation_ids: Sequence[Any] | None,
    recommendations: Sequence[Any] | None,
) -> tuple[list[str], dict[str, dict[str, str]]]:
    normalized_recommendation_ids = (
        _normalize_recommendation_ids(recommendation_ids) if recommendation_ids is not None else []
    )
    recommendation_fields_by_id: dict[str, dict[str, str]] = {}

    if recommendations is not None:
        for index, row in enumerate(recommendations):
            recommendation = _require_mapping(row, field_name=f"recommendations[{index}]")
            recommendation_id = _require_text(
                recommendation.get("recommendation_id"),
                field_name=f"recommendations[{index}].recommendation_id",
            )
            if recommendation_id in recommendation_fields_by_id:
                raise Req008Error(f"recommendations[{index}].recommendation_id duplicates {recommendation_id}")
            risk_level = _require_text(
                recommendation.get("risk_level"),
                field_name=f"recommendations[{index}].risk_level",
            )
            if risk_level not in ALLOWED_RISK_LEVELS:
                raise Req008Error(
                    f"recommendations[{index}].risk_level must be one of {sorted(ALLOWED_RISK_LEVELS)}"
                )
            recommendation_fields_by_id[recommendation_id] = {
                "summary": _require_text(
                    recommendation.get("summary"),
                    field_name=f"recommendations[{index}].summary",
                ),
                "rationale": _require_text(
                    recommendation.get("rationale"),
                    field_name=f"recommendations[{index}].rationale",
                ),
                "expected_impact": _require_text(
                    recommendation.get("expected_impact"),
                    field_name=f"recommendations[{index}].expected_impact",
                ),
                "risk_level": risk_level,
            }

        if not recommendation_fields_by_id:
            raise Req008Error("recommendations must contain at least one recommendation")

        if normalized_recommendation_ids:
            missing_from_objects = sorted(set(normalized_recommendation_ids) - set(recommendation_fields_by_id.keys()))
            extra_in_objects = sorted(set(recommendation_fields_by_id.keys()) - set(normalized_recommendation_ids))
            if missing_from_objects or extra_in_objects:
                raise Req008Error(
                    "recommendation_ids must match recommendations[].recommendation_id "
                    f"(missing={missing_from_objects}, extra={extra_in_objects})"
                )
        else:
            normalized_recommendation_ids = list(recommendation_fields_by_id.keys())

    if not normalized_recommendation_ids:
        raise Req008Error("recommendation_ids or recommendations must include at least one recommendation")

    if not recommendation_fields_by_id:
        for recommendation_id in normalized_recommendation_ids:
            recommendation_fields_by_id[recommendation_id] = {
                "summary": "Not provided in input recommendation metadata.",
                "rationale": "Not provided in input recommendation metadata.",
                "expected_impact": "Not provided in input recommendation metadata.",
                "risk_level": "medium",
            }

    return normalized_recommendation_ids, recommendation_fields_by_id


def _normalize_context_refs(context: Mapping[str, Any] | None) -> dict[str, Any]:
    if context is None:
        return {"mission_refs": [], "scope_refs": []}
    mission_refs = _normalize_string_list(
        _require_sequence(context.get("mission_refs", []), field_name="research_packet.context.mission_refs"),
        field_name="research_packet.context.mission_refs",
    )
    scope_refs = _normalize_string_list(
        _require_sequence(context.get("scope_refs", []), field_name="research_packet.context.scope_refs"),
        field_name="research_packet.context.scope_refs",
    )
    normalized = {
        "mission_refs": mission_refs,
        "scope_refs": scope_refs,
    }
    strategy_ref = _as_text(context.get("strategy_ref"))
    if strategy_ref:
        normalized["strategy_ref"] = strategy_ref
    return normalized


def _resolve_ref_path(raw_ref: str) -> Path:
    path = Path(raw_ref).expanduser()
    if path.is_absolute():
        return path
    return (Path.cwd() / path).resolve()


def _missing_context_doc_refs(context_refs: Mapping[str, Any]) -> list[str]:
    missing: list[str] = []
    for field_name in ("mission_refs", "scope_refs"):
        refs = context_refs.get(field_name)
        if not isinstance(refs, Sequence) or isinstance(refs, (str, bytes, bytearray)):
            continue
        for ref in refs:
            ref_text = _as_text(ref)
            if not ref_text:
                continue
            if not _resolve_ref_path(ref_text).exists():
                missing.append(ref_text)
    return missing


def _resolve_optional_doc_refs(value: Any, *, field_name: str) -> list[str]:
    if value is None:
        return []
    refs = _normalize_string_list(_require_sequence(value, field_name=field_name), field_name=field_name)
    return refs


def _fallback_evidence_refs(
    *,
    preferred_artifact_ids: Sequence[str],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    fallback_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for artifact_id in preferred_artifact_ids:
        row = evidence_by_id.get(artifact_id)
        if row is None or artifact_id in seen:
            continue
        selected.append(dict(row))
        seen.add(artifact_id)

    if selected:
        return selected

    for row in fallback_rows:
        artifact_id = _as_text(row.get("artifact_id"))
        if not artifact_id or artifact_id in seen:
            continue
        selected.append(dict(row))
        seen.add(artifact_id)
    if not selected:
        selected.append(
            {
                "artifact_id": "artifact.req-008.synthetic-normalization-observation",
                "kind": "normalization_observation",
                "uri": "strategy-context-sweep://req-008/synthetic-observation",
                "notes": "Synthetic evidence row emitted when source packet omits evidence_refs.",
            }
        )
    return selected


def _resolve_artifact_id_candidates(raw_values: Sequence[Any], *, field_name: str) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(raw_values):
        artifact_id = ""
        if isinstance(value, Mapping):
            artifact_id = _as_text(value.get("artifact_id"))
            if not artifact_id:
                artifact_id = _require_text(value.get("id"), field_name=f"{field_name}[{index}].id")
        else:
            artifact_id = _require_text(value, field_name=f"{field_name}[{index}]")
        if artifact_id in seen:
            continue
        seen.add(artifact_id)
        normalized.append(artifact_id)
    return normalized


def _resolve_evidence_refs(
    *,
    artifact_ids: Sequence[str],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    field_name: str,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, artifact_id in enumerate(artifact_ids):
        row = evidence_by_id.get(artifact_id)
        if row is None:
            raise Req008Error(f"{field_name}[{index}] references unknown artifact_id {artifact_id}")
        normalized.append(dict(row))
    return normalized


def _normalize_recommendation_links(
    *,
    value: Any,
    recommendation_ids: Sequence[str],
    field_name: str,
) -> list[str]:
    known_ids = set(recommendation_ids)
    if value is None:
        return list(recommendation_ids)
    links = _normalize_recommendation_ids(
        _require_sequence(value, field_name=field_name),
        field_name=field_name,
    )
    for index, recommendation_id in enumerate(links):
        if recommendation_id not in known_ids:
            raise Req008Error(f"{field_name}[{index}] references unknown recommendation_id {recommendation_id}")
    return links


def _mapping_value_by_alias(mapping: Mapping[str, Any], aliases: Sequence[str]) -> Any:
    for alias in aliases:
        if alias in mapping:
            return mapping.get(alias)
    return None


def _normalize_broad_sweep_context(
    *,
    broad_sweep_context: Mapping[str, Any] | None,
    evidence_refs: Sequence[Mapping[str, Any]],
    recommendation_ids: Sequence[str],
    research_event_id: str,
    context_refs: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, list[str]], dict[str, list[str]]]:
    evidence_by_id = {row["artifact_id"]: row for row in evidence_refs}
    linked_cross_context_ids = {recommendation_id: [] for recommendation_id in recommendation_ids}
    linked_open_risk_ids = {recommendation_id: [] for recommendation_id in recommendation_ids}
    recommendation_ids_set = set(recommendation_ids)
    cross_project_context_rows: list[dict[str, Any]] = []
    open_risks_rows: list[dict[str, Any]] = []
    open_risk_counter = 0

    def append_open_risk(
        *,
        reason_code: str,
        risk_level: str,
        risk_statement: str,
        source_fields: Sequence[str],
        recommendation_links: Sequence[str],
        target_project_id: str = "",
        evidence_rows: Sequence[Mapping[str, Any]] | None = None,
    ) -> str:
        nonlocal open_risk_counter
        open_risk_counter += 1
        risk_slug = _normalize_slug(target_project_id or reason_code)
        open_risk_id = f"open-risk.{open_risk_counter:03d}.{risk_slug}"
        row: dict[str, Any] = {
            "open_risk_id": open_risk_id,
            "reason_code": reason_code,
            "risk_level": risk_level,
            "risk_statement": risk_statement,
            "evidence_refs": [dict(item) for item in (evidence_rows or [])],
            "provenance": {
                "research_event_id": research_event_id,
                "source_fields": list(source_fields),
            },
        }
        if target_project_id:
            row["target_project_id"] = target_project_id
        open_risks_rows.append(row)
        for recommendation_id in recommendation_links:
            linked_open_risk_ids[recommendation_id].append(open_risk_id)
        return open_risk_id

    global_evidence_artifact_ids_raw = _mapping_value_by_alias(
        broad_sweep_context,
        ("earth_sweep_evidence_refs", "earth_sweep_artifact_ids", "evidence_artifact_ids", "evidence_refs"),
    ) if broad_sweep_context is not None else None
    global_evidence_artifact_ids = []
    if global_evidence_artifact_ids_raw is not None:
        global_evidence_artifact_ids = _resolve_artifact_id_candidates(
            _require_sequence(
                global_evidence_artifact_ids_raw,
                field_name="broad_sweep_context.earth_sweep_evidence_refs",
            ),
            field_name="broad_sweep_context.earth_sweep_evidence_refs",
        )
        _resolve_evidence_refs(
            artifact_ids=global_evidence_artifact_ids,
            evidence_by_id=evidence_by_id,
            field_name="broad_sweep_context.earth_sweep_evidence_refs",
        )

    baseline_evidence_refs = _fallback_evidence_refs(
        preferred_artifact_ids=global_evidence_artifact_ids,
        evidence_by_id=evidence_by_id,
        fallback_rows=evidence_refs,
    )

    missing_context_refs = _missing_context_doc_refs(context_refs)
    if not context_refs.get("mission_refs"):
        missing_context_refs.append("mission_refs")
    if not context_refs.get("scope_refs"):
        missing_context_refs.append("scope_refs")
    for missing_ref in missing_context_refs:
        append_open_risk(
            reason_code=REASON_CODE_CONTEXT_DOC_MISSING,
            risk_level="high",
            risk_statement=f"Context doc is missing or unreadable: {missing_ref}",
            source_fields=["context.mission_refs[]", "context.scope_refs[]"],
            recommendation_links=list(recommendation_ids),
            evidence_rows=baseline_evidence_refs,
        )

    if broad_sweep_context is None:
        return cross_project_context_rows, open_risks_rows, linked_cross_context_ids, linked_open_risk_ids

    cross_project_raw = _mapping_value_by_alias(
        broad_sweep_context,
        ("cross_project_obligations", "cross_project_context", "projects"),
    )
    if cross_project_raw is not None:
        cross_project_rows = _require_sequence(cross_project_raw, field_name="broad_sweep_context.cross_project_obligations")
        for index, row in enumerate(cross_project_rows, start=1):
            obligation = _require_mapping(row, field_name=f"broad_sweep_context.cross_project_obligations[{index - 1}]")
            target_project_id = _require_text(
                _mapping_value_by_alias(obligation, ("target_project_id", "project_id")),
                field_name=f"broad_sweep_context.cross_project_obligations[{index - 1}].target_project_id",
            )
            summary = _require_text(
                _mapping_value_by_alias(obligation, ("summary", "rationale", "obligation", "statement")),
                field_name=f"broad_sweep_context.cross_project_obligations[{index - 1}].summary",
            )

            recommendation_links = _normalize_recommendation_links(
                value=_mapping_value_by_alias(obligation, ("recommendation_ids", "linked_recommendation_ids")),
                recommendation_ids=recommendation_ids,
                field_name=f"broad_sweep_context.cross_project_obligations[{index - 1}].recommendation_ids",
            )

            entry_evidence_raw = _mapping_value_by_alias(
                obligation,
                ("earth_sweep_evidence_refs", "earth_sweep_artifact_ids", "evidence_artifact_ids", "evidence_refs"),
            )
            entry_evidence_artifact_ids = (
                _resolve_artifact_id_candidates(
                    _require_sequence(
                        entry_evidence_raw,
                        field_name=f"broad_sweep_context.cross_project_obligations[{index - 1}].earth_sweep_evidence_refs",
                    ),
                    field_name=f"broad_sweep_context.cross_project_obligations[{index - 1}].earth_sweep_evidence_refs",
                )
                if entry_evidence_raw is not None
                else []
            )

            peer_doc_refs = _resolve_optional_doc_refs(
                _mapping_value_by_alias(
                    obligation,
                    ("peer_project_doc_refs", "peer_project_docs", "doc_refs", "project_doc_refs"),
                ),
                field_name=f"broad_sweep_context.cross_project_obligations[{index - 1}].peer_project_doc_refs",
            )
            missing_peer_doc_refs = [
                ref for ref in peer_doc_refs if not _resolve_ref_path(ref).exists()
            ]
            if missing_peer_doc_refs:
                append_open_risk(
                    reason_code=REASON_CODE_PEER_PROJECT_DOC_MISSING,
                    risk_level="high",
                    risk_statement=(
                        "Cross-project obligation blocked by missing peer-project docs "
                        f"for {target_project_id}: {', '.join(missing_peer_doc_refs)}"
                    ),
                    source_fields=[
                        "context.broad_sweep_context.cross_project_obligations[].peer_project_doc_refs[]",
                        "context.broad_sweep_context.cross_project_obligations[]",
                    ],
                    recommendation_links=recommendation_links,
                    target_project_id=target_project_id,
                    evidence_rows=_fallback_evidence_refs(
                        preferred_artifact_ids=entry_evidence_artifact_ids or global_evidence_artifact_ids,
                        evidence_by_id=evidence_by_id,
                        fallback_rows=baseline_evidence_refs,
                    ),
                )
                continue

            if not entry_evidence_artifact_ids:
                append_open_risk(
                    reason_code=REASON_CODE_EARTH_SWEEP_EVIDENCE_MISSING,
                    risk_level="high",
                    risk_statement=(
                        "Cross-project obligation omitted until Earth-sweep evidence is attached: "
                        f"{summary}"
                    ),
                    source_fields=["context.broad_sweep_context.cross_project_obligations[]"],
                    recommendation_links=recommendation_links,
                    target_project_id=target_project_id,
                    evidence_rows=baseline_evidence_refs,
                )
                continue

            normalized_evidence_refs = _resolve_evidence_refs(
                artifact_ids=entry_evidence_artifact_ids,
                evidence_by_id=evidence_by_id,
                field_name=f"broad_sweep_context.cross_project_obligations[{index - 1}].earth_sweep_evidence_refs",
            )
            stale_evidence_refs = [
                dict(row)
                for row in normalized_evidence_refs
                if _to_bool(row.get("stale"))
            ]
            if stale_evidence_refs:
                append_open_risk(
                    reason_code=REASON_CODE_EARTH_SWEEP_STALE_SOURCE_ARTIFACT,
                    risk_level="high",
                    risk_statement=(
                        "Cross-project obligation omitted because Earth-sweep source artifacts are stale: "
                        f"{summary}"
                    ),
                    source_fields=[
                        "context.broad_sweep_context.cross_project_obligations[].earth_sweep_evidence_refs[]",
                        "evidence_refs[]",
                    ],
                    recommendation_links=recommendation_links,
                    target_project_id=target_project_id,
                    evidence_rows=stale_evidence_refs,
                )
                continue

            context_id = f"cross-project-context.{index:03d}.{_normalize_slug(target_project_id)}"
            cross_project_context_rows.append(
                {
                    "cross_project_context_id": context_id,
                    "target_project_id": target_project_id,
                    "summary": summary,
                    "evidence_refs": normalized_evidence_refs,
                    "provenance": {
                        "research_event_id": research_event_id,
                        "source_fields": [
                            "context.broad_sweep_context.cross_project_obligations[]",
                            "evidence_refs[]",
                        ],
                    },
                }
            )
            for recommendation_id in recommendation_links:
                linked_cross_context_ids[recommendation_id].append(context_id)

    unresolved_raw = _mapping_value_by_alias(
        broad_sweep_context,
        ("unresolved_ideas", "open_risks", "unresolved"),
    )
    if unresolved_raw is not None:
        unresolved_rows = _require_sequence(unresolved_raw, field_name="broad_sweep_context.unresolved_ideas")
        for index, row in enumerate(unresolved_rows):
            summary = ""
            linked_recommendation_ids_value = None
            evidence_artifact_ids_value = None
            risk_level = "medium"
            target_project_id = ""

            if isinstance(row, Mapping):
                summary = _require_text(
                    _mapping_value_by_alias(row, ("summary", "idea", "risk_statement", "question", "statement")),
                    field_name=f"broad_sweep_context.unresolved_ideas[{index}].summary",
                )
                linked_recommendation_ids_value = _mapping_value_by_alias(row, ("recommendation_ids", "linked_recommendation_ids"))
                evidence_artifact_ids_value = _mapping_value_by_alias(
                    row,
                    ("earth_sweep_evidence_refs", "earth_sweep_artifact_ids", "evidence_artifact_ids", "evidence_refs"),
                )
                target_project_id = _as_text(_mapping_value_by_alias(row, ("target_project_id", "project_id")))
                risk_level_value = _as_text(row.get("risk_level"))
                if risk_level_value:
                    if risk_level_value not in ALLOWED_RISK_LEVELS:
                        raise Req008Error(
                            f"broad_sweep_context.unresolved_ideas[{index}].risk_level must be one of {sorted(ALLOWED_RISK_LEVELS)}"
                        )
                    risk_level = risk_level_value
            else:
                summary = _require_text(row, field_name=f"broad_sweep_context.unresolved_ideas[{index}]")

            linked_recommendation_ids = _normalize_recommendation_links(
                value=linked_recommendation_ids_value,
                recommendation_ids=recommendation_ids,
                field_name=f"broad_sweep_context.unresolved_ideas[{index}].recommendation_ids",
            )

            evidence_artifact_ids = (
                _resolve_artifact_id_candidates(
                    _require_sequence(
                        evidence_artifact_ids_value,
                        field_name=f"broad_sweep_context.unresolved_ideas[{index}].earth_sweep_evidence_refs",
                    ),
                    field_name=f"broad_sweep_context.unresolved_ideas[{index}].earth_sweep_evidence_refs",
                )
                if evidence_artifact_ids_value is not None
                else []
            )

            evidence_rows = _resolve_evidence_refs(
                artifact_ids=evidence_artifact_ids,
                evidence_by_id=evidence_by_id,
                field_name=f"broad_sweep_context.unresolved_ideas[{index}].earth_sweep_evidence_refs",
            )

            open_risk_id = append_open_risk(
                reason_code="unresolved_idea_open_risk",
                risk_level=risk_level,
                risk_statement=summary,
                source_fields=["context.broad_sweep_context.unresolved_ideas[]"],
                recommendation_links=[],
                target_project_id=target_project_id,
                evidence_rows=evidence_rows,
            )
            for recommendation_id in linked_recommendation_ids:
                if recommendation_id not in recommendation_ids_set:
                    raise Req008Error(
                        f"broad_sweep_context.unresolved_ideas[{index}] links unknown recommendation_id {recommendation_id}"
                    )
                linked_open_risk_ids[recommendation_id].append(open_risk_id)

    return cross_project_context_rows, open_risks_rows, linked_cross_context_ids, linked_open_risk_ids


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


def serialize_req_008_context_bundle(payload: Mapping[str, Any]) -> str:
    bundle = {
        "research_packet_identity": payload.get("research_packet_identity", {}),
        "strategy_context": payload.get("strategy_context", {}),
        "recommendation_rationale_provenance": payload.get("recommendation_rationale_provenance", []),
    }
    return json.dumps(bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _context_bundle_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(serialize_req_008_context_bundle(payload).encode("utf-8")).hexdigest()


def build_req_008_research_packet_ingestion_and_normalization(
    *,
    research_packet: Mapping[str, Any],
    recommendation_ids: Sequence[Any] | None = None,
    recommendations: Sequence[Any] | None = None,
    recommendation_topic_map: Mapping[str, Any] | None = None,
    broad_sweep_context: Mapping[str, Any] | None = None,
    normalized_at_utc: str | None = None,
) -> dict[str, Any]:
    """Normalize research packet anchors into strategy context for REQ-008."""
    packet = _require_mapping(research_packet, field_name="research_packet")
    packet_schema_version = _require_text(
        packet.get("schema_version"), field_name="research_packet.schema_version"
    )
    identity = _normalize_identity(_require_mapping(packet.get("identity"), field_name="research_packet.identity"))
    context_raw = (
        _require_mapping(packet.get("context"), field_name="research_packet.context")
        if packet.get("context") is not None
        else None
    )
    normalized_context_refs = _normalize_context_refs(context_raw)

    topics = _normalize_topics(_require_sequence(packet.get("topics"), field_name="research_packet.topics"))
    open_questions = _normalize_unknown_questions(
        _require_sequence(packet.get("open_questions"), field_name="research_packet.open_questions")
    )
    evidence_refs = _normalize_evidence_refs(
        _require_sequence(packet.get("evidence_refs"), field_name="research_packet.evidence_refs")
    )

    normalized_recommendation_ids, recommendation_fields_by_id = _normalize_recommendations(
        recommendation_ids=recommendation_ids,
        recommendations=recommendations,
    )
    topic_ids = [topic["topic_id"] for topic in topics]
    recommendation_topic_links = _normalize_recommendation_topic_map(
        normalized_recommendation_ids,
        topic_ids,
        recommendation_topic_map,
    )
    normalized_broad_sweep_context = broad_sweep_context
    if normalized_broad_sweep_context is None and context_raw is not None:
        for alias in ("broad_sweep_context", "broad_sweep", "earth_sweep"):
            candidate = context_raw.get(alias)
            if candidate is not None:
                normalized_broad_sweep_context = _require_mapping(
                    candidate,
                    field_name=f"research_packet.context.{alias}",
                )
                break
    if normalized_broad_sweep_context is None:
        for alias in ("broad_sweep_context", "broad_sweep", "earth_sweep"):
            candidate = packet.get(alias)
            if candidate is not None:
                normalized_broad_sweep_context = _require_mapping(
                    candidate,
                    field_name=f"research_packet.{alias}",
                )
                break

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

    (
        cross_project_context,
        open_risks,
        linked_cross_project_context_ids,
        linked_open_risk_ids,
    ) = _normalize_broad_sweep_context(
        broad_sweep_context=normalized_broad_sweep_context,
        evidence_refs=evidence_refs,
        recommendation_ids=normalized_recommendation_ids,
        research_event_id=identity["event_id"],
        context_refs=normalized_context_refs,
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
                "linked_cross_project_context_ids": list(linked_cross_project_context_ids[recommendation_id]),
                "linked_open_risk_ids": list(linked_open_risk_ids[recommendation_id]),
                "recommendation_fields": dict(recommendation_fields_by_id[recommendation_id]),
                "research_provenance": {
                    "research_packet_event_id": identity["event_id"],
                    "source_schema_version": packet_schema_version,
                    "linked_topic_ids": linked_topic_ids,
                    "context_mission_refs": list(normalized_context_refs["mission_refs"]),
                    "context_scope_refs": list(normalized_context_refs["scope_refs"]),
                },
                "provenance_refs": [dict(row) for row in evidence_refs],
            }
        )
        strategy_ref = _as_text(normalized_context_refs.get("strategy_ref"))
        if strategy_ref:
            recommendation_rationale_provenance[-1]["research_provenance"]["context_strategy_ref"] = strategy_ref

    output_payload = {
        "schema_version": SCHEMA_VERSION,
        "requirement_id": REQUIREMENT_ID,
        "research_packet_identity": identity,
        "strategy_context": {
            "assumptions": assumptions,
            "unknowns": unknowns,
            "risk_evidence": risk_evidence,
            "cross_project_context": cross_project_context,
            "open_risks": open_risks,
        },
        "recommendation_rationale_provenance": recommendation_rationale_provenance,
        "source": {
            "normalized_from_schema_version": packet_schema_version,
            "normalized_at_utc": normalized_timestamp,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
        },
    }
    output_payload["source"]["context_bundle_sha256"] = _context_bundle_sha256(output_payload)
    return output_payload


def _validate_evidence_refs_array(
    *,
    evidence_refs: Any,
    field_name: str,
    errors: list[str],
    evidence_ids: set[str],
    require_non_empty: bool = False,
) -> None:
    if not isinstance(evidence_refs, Sequence) or isinstance(evidence_refs, (str, bytes, bytearray)):
        errors.append(f"{field_name} must be an array")
        return
    if require_non_empty and not evidence_refs:
        errors.append(f"{field_name} must not be empty")
        return
    for evidence_index, evidence_row in enumerate(evidence_refs):
        if not isinstance(evidence_row, Mapping):
            errors.append(f"{field_name}[{evidence_index}] must be an object")
            continue
        artifact_id = _as_text(evidence_row.get("artifact_id"))
        kind = _as_text(evidence_row.get("kind"))
        uri = _as_text(evidence_row.get("uri"))
        if not artifact_id:
            errors.append(f"{field_name}[{evidence_index}].artifact_id is required")
        else:
            evidence_ids.add(artifact_id)
        if not kind:
            errors.append(f"{field_name}[{evidence_index}].kind is required")
        if not uri:
            errors.append(f"{field_name}[{evidence_index}].uri is required")


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
    cross_project_context = strategy_context.get("cross_project_context")
    if not isinstance(cross_project_context, Sequence) or isinstance(cross_project_context, (str, bytes, bytearray)):
        errors.append("strategy_context.cross_project_context must be an array")
        cross_project_context = []
    open_risks = strategy_context.get("open_risks")
    if not isinstance(open_risks, Sequence) or isinstance(open_risks, (str, bytes, bytearray)):
        errors.append("strategy_context.open_risks must be an array")
        open_risks = []

    assumption_ids: set[str] = set()
    unknown_ids: set[str] = set()
    risk_ids: set[str] = set()
    cross_project_context_ids: set[str] = set()
    open_risk_ids: set[str] = set()
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

        _validate_evidence_refs_array(
            evidence_refs=evidence_refs,
            field_name=f"strategy_context.risk_evidence[{index}].evidence_refs",
            errors=errors,
            evidence_ids=evidence_ids,
            require_non_empty=True,
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

    for index, row in enumerate(cross_project_context):
        if not isinstance(row, Mapping):
            errors.append(f"strategy_context.cross_project_context[{index}] must be an object")
            continue
        cross_context_id = _as_text(row.get("cross_project_context_id"))
        target_project_id = _as_text(row.get("target_project_id"))
        summary = _as_text(row.get("summary"))
        evidence_refs = row.get("evidence_refs")
        provenance = row.get("provenance")

        if not cross_context_id:
            errors.append(f"strategy_context.cross_project_context[{index}].cross_project_context_id is required")
        elif cross_context_id in cross_project_context_ids:
            errors.append(
                f"strategy_context.cross_project_context[{index}].cross_project_context_id duplicates {cross_context_id}"
            )
        else:
            cross_project_context_ids.add(cross_context_id)

        if not target_project_id:
            errors.append(f"strategy_context.cross_project_context[{index}].target_project_id is required")
        if not summary:
            errors.append(f"strategy_context.cross_project_context[{index}].summary is required")

        _validate_evidence_refs_array(
            evidence_refs=evidence_refs,
            field_name=f"strategy_context.cross_project_context[{index}].evidence_refs",
            errors=errors,
            evidence_ids=evidence_ids,
            require_non_empty=True,
        )

        if not isinstance(provenance, Mapping):
            errors.append(f"strategy_context.cross_project_context[{index}].provenance must be an object")
        else:
            if _as_text(provenance.get("research_event_id")) != _as_text(identity.get("event_id")):
                errors.append(
                    f"strategy_context.cross_project_context[{index}].provenance.research_event_id must match research_packet_identity.event_id"
                )
            source_fields = provenance.get("source_fields")
            if not isinstance(source_fields, Sequence) or isinstance(source_fields, (str, bytes, bytearray)):
                errors.append(f"strategy_context.cross_project_context[{index}].provenance.source_fields must be an array")

    for index, row in enumerate(open_risks):
        if not isinstance(row, Mapping):
            errors.append(f"strategy_context.open_risks[{index}] must be an object")
            continue
        open_risk_id = _as_text(row.get("open_risk_id"))
        reason_code = _as_text(row.get("reason_code"))
        risk_level = _as_text(row.get("risk_level"))
        risk_statement = _as_text(row.get("risk_statement"))
        evidence_refs = row.get("evidence_refs")
        provenance = row.get("provenance")

        if not open_risk_id:
            errors.append(f"strategy_context.open_risks[{index}].open_risk_id is required")
        elif open_risk_id in open_risk_ids:
            errors.append(f"strategy_context.open_risks[{index}].open_risk_id duplicates {open_risk_id}")
        else:
            open_risk_ids.add(open_risk_id)

        if risk_level not in ALLOWED_RISK_LEVELS:
            errors.append(f"strategy_context.open_risks[{index}].risk_level must be one of {sorted(ALLOWED_RISK_LEVELS)}")
        if not risk_statement:
            errors.append(f"strategy_context.open_risks[{index}].risk_statement is required")
        if row.get("reason_code") is not None and not reason_code:
            errors.append(f"strategy_context.open_risks[{index}].reason_code must be a non-empty string when set")

        _validate_evidence_refs_array(
            evidence_refs=evidence_refs,
            field_name=f"strategy_context.open_risks[{index}].evidence_refs",
            errors=errors,
            evidence_ids=evidence_ids,
        )

        if not isinstance(provenance, Mapping):
            errors.append(f"strategy_context.open_risks[{index}].provenance must be an object")
        else:
            if _as_text(provenance.get("research_event_id")) != _as_text(identity.get("event_id")):
                errors.append(
                    f"strategy_context.open_risks[{index}].provenance.research_event_id must match research_packet_identity.event_id"
                )
            source_fields = provenance.get("source_fields")
            if not isinstance(source_fields, Sequence) or isinstance(source_fields, (str, bytes, bytearray)):
                errors.append(f"strategy_context.open_risks[{index}].provenance.source_fields must be an array")

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
        linked_cross_context = row.get("linked_cross_project_context_ids")
        linked_open_risk = row.get("linked_open_risk_ids")
        recommendation_fields = row.get("recommendation_fields")
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

        for field_name, linked_value, known_ids in (
            ("linked_cross_project_context_ids", linked_cross_context, cross_project_context_ids),
            ("linked_open_risk_ids", linked_open_risk, open_risk_ids),
        ):
            if not isinstance(linked_value, Sequence) or isinstance(linked_value, (str, bytes, bytearray)):
                errors.append(f"recommendation_rationale_provenance[{index}].{field_name} must be an array")
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

        if not isinstance(recommendation_fields, Mapping):
            errors.append(f"recommendation_rationale_provenance[{index}].recommendation_fields must be an object")
        else:
            for key in ("summary", "rationale", "expected_impact"):
                if not _as_text(recommendation_fields.get(key)):
                    errors.append(f"recommendation_rationale_provenance[{index}].recommendation_fields.{key} is required")
            if _as_text(recommendation_fields.get("risk_level")) not in ALLOWED_RISK_LEVELS:
                errors.append(
                    f"recommendation_rationale_provenance[{index}].recommendation_fields.risk_level must be one of {sorted(ALLOWED_RISK_LEVELS)}"
                )

        if not isinstance(research_provenance, Mapping):
            errors.append(f"recommendation_rationale_provenance[{index}].research_provenance must be an object")
        else:
            if _as_text(research_provenance.get("research_packet_event_id")) != _as_text(identity.get("event_id")):
                errors.append(
                    f"recommendation_rationale_provenance[{index}].research_provenance.research_packet_event_id must match research_packet_identity.event_id"
                )
            if not _as_text(research_provenance.get("source_schema_version")):
                errors.append(
                    f"recommendation_rationale_provenance[{index}].research_provenance.source_schema_version is required"
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
            for field_name in ("context_mission_refs", "context_scope_refs"):
                field_value = research_provenance.get(field_name)
                if not isinstance(field_value, Sequence) or isinstance(field_value, (str, bytes, bytearray)):
                    errors.append(
                        f"recommendation_rationale_provenance[{index}].research_provenance.{field_name} must be an array"
                    )
                    continue
                for value_index, value in enumerate(field_value):
                    if not _as_text(value):
                        errors.append(
                            "recommendation_rationale_provenance"
                            f"[{index}].research_provenance.{field_name}[{value_index}] must be non-empty"
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
        context_bundle_sha256 = _as_text(source.get("context_bundle_sha256"))
        if context_bundle_sha256:
            if not re.fullmatch(r"[0-9a-f]{64}", context_bundle_sha256):
                errors.append("source.context_bundle_sha256 must be a lowercase hex sha256 digest")

    return errors


def _require_text_req_015(value: Any, *, field_name: str) -> str:
    text = _as_text(value)
    if not text:
        raise Req015Error(f"{field_name} must be a non-empty string")
    return text


def _require_mapping_req_015(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise Req015Error(f"{field_name} must be an object")
    return value


def _require_sequence_req_015(value: Any, *, field_name: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise Req015Error(f"{field_name} must be an array")
    return value


def _normalize_req_015_evidence_refs(evidence_rows: Sequence[Any], *, field_name: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_artifact_ids: set[str] = set()
    for index, row in enumerate(evidence_rows):
        evidence = _require_mapping_req_015(row, field_name=f"{field_name}[{index}]")
        artifact_id = _require_text_req_015(
            evidence.get("artifact_id"),
            field_name=f"{field_name}[{index}].artifact_id",
        )
        if artifact_id in seen_artifact_ids:
            raise Req015Error(f"{field_name}[{index}].artifact_id duplicates {artifact_id}")
        seen_artifact_ids.add(artifact_id)
        normalized_row: dict[str, Any] = {
            "artifact_id": artifact_id,
            "kind": _require_text_req_015(evidence.get("kind"), field_name=f"{field_name}[{index}].kind"),
            "uri": _require_text_req_015(evidence.get("uri"), field_name=f"{field_name}[{index}].uri"),
        }
        notes = _as_text(evidence.get("notes"))
        if notes:
            normalized_row["notes"] = notes
        if _is_stale_evidence_row(evidence):
            normalized_row["stale"] = True
        normalized.append(normalized_row)
    if not normalized:
        raise Req015Error(f"{field_name} must contain at least one evidence ref")
    return normalized


def _normalize_req_015_expected_interaction_contract(
    value: Any,
    *,
    field_name: str,
) -> dict[str, str]:
    contract = _require_mapping_req_015(value, field_name=field_name)
    return {
        "interaction_type": _require_text_req_015(
            contract.get("interaction_type"),
            field_name=f"{field_name}.interaction_type",
        ),
        "producer_component": _require_text_req_015(
            contract.get("producer_component"),
            field_name=f"{field_name}.producer_component",
        ),
        "consumer_component": _require_text_req_015(
            contract.get("consumer_component"),
            field_name=f"{field_name}.consumer_component",
        ),
        "interface": _require_text_req_015(
            contract.get("interface"),
            field_name=f"{field_name}.interface",
        ),
        "data_contract": _require_text_req_015(
            contract.get("data_contract"),
            field_name=f"{field_name}.data_contract",
        ),
    }


def _normalize_req_015_side_effect_notes(raw_value: Any, *, field_name: str) -> list[str]:
    rows = _require_sequence_req_015(raw_value, field_name=field_name)
    notes: list[str] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        note = _require_text_req_015(row, field_name=f"{field_name}[{index}]")
        if note in seen:
            continue
        seen.add(note)
        notes.append(note)
    if not notes:
        raise Req015Error(f"{field_name} must contain at least one note")
    return notes


def _default_req_015_recommendation_fields() -> dict[str, str]:
    return {
        "summary": "Not provided in input recommendation metadata.",
        "rationale": "Not provided in input recommendation metadata.",
        "expected_impact": "Not provided in input recommendation metadata.",
        "risk_level": "medium",
    }


def _normalize_req_015_recommendations(
    recommendations: Sequence[Any] | None,
) -> tuple[list[str], dict[str, dict[str, str]]]:
    if recommendations is None:
        return [], {}

    rows = _require_sequence_req_015(recommendations, field_name="recommendations")
    if not rows:
        return [], {}

    ordered_ids: list[str] = []
    fields_by_id: dict[str, dict[str, str]] = {}
    for index, raw_row in enumerate(rows):
        row = _require_mapping_req_015(raw_row, field_name=f"recommendations[{index}]")
        recommendation_id = _require_text_req_015(
            row.get("recommendation_id"),
            field_name=f"recommendations[{index}].recommendation_id",
        )
        if recommendation_id in fields_by_id:
            raise Req015Error(f"recommendations[{index}].recommendation_id duplicates {recommendation_id}")
        risk_level = _require_text_req_015(
            row.get("risk_level"),
            field_name=f"recommendations[{index}].risk_level",
        )
        if risk_level not in ALLOWED_RISK_LEVELS:
            raise Req015Error(f"recommendations[{index}].risk_level must be one of {sorted(ALLOWED_RISK_LEVELS)}")

        fields_by_id[recommendation_id] = {
            "summary": _require_text_req_015(
                row.get("summary"),
                field_name=f"recommendations[{index}].summary",
            ),
            "rationale": _require_text_req_015(
                row.get("rationale"),
                field_name=f"recommendations[{index}].rationale",
            ),
            "expected_impact": _require_text_req_015(
                row.get("expected_impact"),
                field_name=f"recommendations[{index}].expected_impact",
            ),
            "risk_level": risk_level,
        }
        ordered_ids.append(recommendation_id)
    return ordered_ids, fields_by_id


def _resolve_req_015_recommendation_links(
    *,
    value: Any,
    known_recommendation_ids: Sequence[str],
    field_name: str,
) -> list[str]:
    known = set(known_recommendation_ids)
    if value is None:
        return list(known_recommendation_ids)

    rows = _require_sequence_req_015(value, field_name=field_name)
    links: list[str] = []
    seen: set[str] = set()
    for index, raw_link in enumerate(rows):
        recommendation_id = _require_text_req_015(raw_link, field_name=f"{field_name}[{index}]")
        if recommendation_id in seen:
            continue
        if known and recommendation_id not in known:
            raise Req015Error(f"{field_name}[{index}] references unknown recommendation_id {recommendation_id}")
        seen.add(recommendation_id)
        links.append(recommendation_id)
    return links


def _resolve_req_015_artifact_id_candidates(
    raw_values: Sequence[Any],
    *,
    field_name: str,
    evidence_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    artifact_ids: list[str] = []
    seen: set[str] = set()
    for index, raw_value in enumerate(raw_values):
        artifact_id = ""
        if isinstance(raw_value, Mapping):
            artifact_id = _as_text(raw_value.get("artifact_id")) or _as_text(raw_value.get("id"))
            if not artifact_id:
                raise Req015Error(f"{field_name}[{index}].artifact_id or {field_name}[{index}].id is required")
            kind = _as_text(raw_value.get("kind"))
            uri = _as_text(raw_value.get("uri"))
            if kind or uri:
                if not kind or not uri:
                    raise Req015Error(f"{field_name}[{index}] must include both kind and uri when either is set")
                normalized_row: dict[str, Any] = {
                    "artifact_id": artifact_id,
                    "kind": kind,
                    "uri": uri,
                }
                notes = _as_text(raw_value.get("notes"))
                if notes:
                    normalized_row["notes"] = notes
                if _is_stale_evidence_row(raw_value):
                    normalized_row["stale"] = True
                evidence_by_id[artifact_id] = normalized_row
        else:
            artifact_id = _require_text_req_015(raw_value, field_name=f"{field_name}[{index}]")

        if artifact_id in seen:
            continue
        seen.add(artifact_id)
        artifact_ids.append(artifact_id)
    return artifact_ids


def _normalize_req_015_evidence_catalog(evidence_refs: Sequence[Any] | None) -> list[dict[str, Any]]:
    if evidence_refs is None:
        return []
    rows = _require_sequence_req_015(evidence_refs, field_name="evidence_refs")
    return _normalize_req_015_evidence_refs(rows, field_name="evidence_refs")


def _resolve_req_015_evidence_refs(
    *,
    artifact_ids: Sequence[str],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    field_name: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, artifact_id in enumerate(artifact_ids):
        evidence_row = evidence_by_id.get(artifact_id)
        if evidence_row is None:
            raise Req015Error(f"{field_name}[{index}] references unknown artifact_id {artifact_id}")
        rows.append(dict(evidence_row))
    return rows


def _fallback_req_015_evidence_refs(
    *,
    preferred_artifact_ids: Sequence[str],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    fallback_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()

    for artifact_id in preferred_artifact_ids:
        row = evidence_by_id.get(artifact_id)
        if row is None or artifact_id in seen:
            continue
        selected.append(dict(row))
        seen.add(artifact_id)

    if selected:
        return selected

    for row in fallback_rows:
        artifact_id = _as_text(row.get("artifact_id"))
        if not artifact_id or artifact_id in seen:
            continue
        selected.append(dict(row))
        seen.add(artifact_id)

    if not selected:
        selected.append(
            {
                "artifact_id": "artifact.req-015.synthetic-detection-observation",
                "kind": "normalization_observation",
                "uri": "strategy-context-sweep://req-015/synthetic-observation",
                "notes": "Synthetic evidence row emitted when source Earth-sweep evidence is missing.",
            }
        )
    return selected


def _resolve_req_015_optional_doc_refs(value: Any, *, field_name: str) -> list[str]:
    if value is None:
        return []
    rows = _require_sequence_req_015(value, field_name=field_name)
    refs: list[str] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        ref = _require_text_req_015(row, field_name=f"{field_name}[{index}]")
        if ref in seen:
            continue
        seen.add(ref)
        refs.append(ref)
    return refs


def _normalize_req_015_context_doc_refs(broad_sweep_context: Mapping[str, Any]) -> dict[str, list[str]] | None:
    mission_refs_raw = _mapping_value_by_alias(
        broad_sweep_context,
        ("mission_refs", "context_mission_refs"),
    )
    scope_refs_raw = _mapping_value_by_alias(
        broad_sweep_context,
        ("scope_refs", "context_scope_refs"),
    )
    if mission_refs_raw is None and scope_refs_raw is None:
        return None
    return {
        "mission_refs": _resolve_req_015_optional_doc_refs(
            mission_refs_raw,
            field_name="broad_sweep_context.mission_refs",
        ),
        "scope_refs": _resolve_req_015_optional_doc_refs(
            scope_refs_raw,
            field_name="broad_sweep_context.scope_refs",
        ),
    }


def _append_req_015_open_risk(
    *,
    open_risks: list[dict[str, Any]],
    open_risk_index: int,
    reason_code: str,
    risk_level: str,
    risk_statement: str,
    source_fields: Sequence[str],
    recommendation_ids: Sequence[str],
    evidence_rows: Sequence[Mapping[str, Any]],
    target_project_id: str = "",
    research_event_id: str = "",
) -> str:
    open_risk_id = f"open-risk.{open_risk_index:03d}.{_normalize_slug(target_project_id or reason_code)}"
    row: dict[str, Any] = {
        "open_risk_id": open_risk_id,
        "reason_code": reason_code,
        "risk_level": risk_level,
        "risk_statement": risk_statement,
        "recommendation_ids": list(recommendation_ids),
        "evidence_refs": [dict(item) for item in evidence_rows],
        "provenance": {
            "source_fields": list(source_fields),
        },
    }
    if target_project_id:
        row["target_project_id"] = target_project_id
    if _as_text(research_event_id):
        row["provenance"]["research_event_id"] = research_event_id
    open_risks.append(row)
    return open_risk_id


def _build_req_015_opportunity_row(
    *,
    opportunity_index: int,
    target_project_id: str,
    peer_project_id: str,
    opportunity_summary: str,
    recommendation_links: Sequence[str],
    recommendation_fields_by_id: Mapping[str, Mapping[str, str]],
    expected_interaction_contract: Mapping[str, str],
    dependency_side_effect_notes: Sequence[str],
    evidence_refs: Sequence[Mapping[str, Any]],
    source_fields: Sequence[str],
    research_event_id: str,
) -> dict[str, Any]:
    primary_recommendation_id = (
        recommendation_links[0]
        if recommendation_links
        else f"rec.synthetic.{_normalize_slug(peer_project_id)}"
    )
    recommendation_fields = dict(
        recommendation_fields_by_id.get(
            primary_recommendation_id,
            _default_req_015_recommendation_fields(),
        )
    )

    provenance: dict[str, Any] = {"source_fields": list(source_fields)}
    if _as_text(research_event_id):
        provenance["research_event_id"] = research_event_id

    return {
        "integration_opportunity_id": f"integration-opportunity.{opportunity_index:03d}.{_normalize_slug(peer_project_id)}",
        "target_project_id": target_project_id,
        "peer_project_id": peer_project_id,
        "opportunity_summary": opportunity_summary,
        "recommendation_id": primary_recommendation_id,
        "linked_recommendation_ids": list(recommendation_links) if recommendation_links else [primary_recommendation_id],
        "recommendation_fields": recommendation_fields,
        "expected_interaction_contract": dict(expected_interaction_contract),
        "dependency_side_effect_notes": list(dependency_side_effect_notes),
        "evidence_refs": [dict(item) for item in evidence_refs],
        "provenance": provenance,
    }


def _normalize_req_015_broad_sweep_context(
    *,
    target_project_id: str,
    broad_sweep_context: Mapping[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
    evidence_catalog_rows: Sequence[Mapping[str, Any]],
    recommendation_ids: Sequence[str],
    recommendation_fields_by_id: Mapping[str, Mapping[str, str]],
    opportunity_start_index: int,
    open_risk_start_index: int,
    research_event_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, int]:
    opportunities: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    opportunity_index = opportunity_start_index
    open_risk_index = open_risk_start_index

    global_evidence_raw = _mapping_value_by_alias(
        broad_sweep_context,
        ("earth_sweep_evidence_refs", "earth_sweep_artifact_ids", "evidence_artifact_ids", "evidence_refs"),
    )
    global_evidence_artifact_ids: list[str] = []
    if global_evidence_raw is not None:
        global_evidence_artifact_ids = _resolve_req_015_artifact_id_candidates(
            _require_sequence_req_015(
                global_evidence_raw,
                field_name="broad_sweep_context.earth_sweep_evidence_refs",
            ),
            field_name="broad_sweep_context.earth_sweep_evidence_refs",
            evidence_by_id=evidence_by_id,
        )
        _resolve_req_015_evidence_refs(
            artifact_ids=global_evidence_artifact_ids,
            evidence_by_id=evidence_by_id,
            field_name="broad_sweep_context.earth_sweep_evidence_refs",
        )

    baseline_evidence_refs = _fallback_req_015_evidence_refs(
        preferred_artifact_ids=global_evidence_artifact_ids,
        evidence_by_id=evidence_by_id,
        fallback_rows=evidence_catalog_rows,
    )
    context_doc_refs = _normalize_req_015_context_doc_refs(broad_sweep_context)
    if context_doc_refs is not None:
        missing_context_refs = _missing_context_doc_refs(context_doc_refs)
        if not context_doc_refs.get("mission_refs"):
            missing_context_refs.append("mission_refs")
        if not context_doc_refs.get("scope_refs"):
            missing_context_refs.append("scope_refs")
        for missing_ref in missing_context_refs:
            open_risk_index += 1
            _append_req_015_open_risk(
                open_risks=open_risks,
                open_risk_index=open_risk_index,
                reason_code=REASON_CODE_CONTEXT_DOC_MISSING,
                risk_level="high",
                risk_statement=f"Context doc is missing or unreadable: {missing_ref}",
                source_fields=["broad_sweep_context.mission_refs[]", "broad_sweep_context.scope_refs[]"],
                recommendation_ids=list(recommendation_ids),
                evidence_rows=baseline_evidence_refs,
                research_event_id=research_event_id,
            )

    cross_project_raw = _mapping_value_by_alias(
        broad_sweep_context,
        ("cross_project_obligations", "cross_project_context", "projects"),
    )
    if cross_project_raw is not None:
        cross_project_rows = _require_sequence_req_015(
            cross_project_raw,
            field_name="broad_sweep_context.cross_project_obligations",
        )
        for index, raw_row in enumerate(cross_project_rows):
            row = _require_mapping_req_015(
                raw_row,
                field_name=f"broad_sweep_context.cross_project_obligations[{index}]",
            )
            peer_project_id = _require_text_req_015(
                _mapping_value_by_alias(row, ("target_project_id", "peer_project_id", "project_id")),
                field_name=f"broad_sweep_context.cross_project_obligations[{index}].target_project_id",
            )
            if peer_project_id == target_project_id:
                raise Req015Error(
                    f"broad_sweep_context.cross_project_obligations[{index}].target_project_id must differ from target_project.project_id"
                )
            summary = _require_text_req_015(
                _mapping_value_by_alias(row, ("summary", "opportunity_summary", "rationale", "statement")),
                field_name=f"broad_sweep_context.cross_project_obligations[{index}].summary",
            )

            recommendation_links = _resolve_req_015_recommendation_links(
                value=_mapping_value_by_alias(row, ("recommendation_ids", "linked_recommendation_ids")),
                known_recommendation_ids=recommendation_ids,
                field_name=f"broad_sweep_context.cross_project_obligations[{index}].recommendation_ids",
            )
            if not recommendation_links:
                open_risk_index += 1
                _append_req_015_open_risk(
                    open_risks=open_risks,
                    open_risk_index=open_risk_index,
                    reason_code=REASON_CODE_REQ_015_RECOMMENDATION_CONTEXT_MISSING,
                    risk_level="high",
                    risk_statement=(
                        "Cross-project obligation omitted because recommendation context is missing: "
                        f"{summary}"
                    ),
                    source_fields=[
                        "broad_sweep_context.cross_project_obligations[].recommendation_ids[]",
                        "recommendations[]",
                    ],
                    recommendation_ids=[],
                    evidence_rows=baseline_evidence_refs,
                    target_project_id=peer_project_id,
                    research_event_id=research_event_id,
                )
                continue

            interaction_contract_raw = _mapping_value_by_alias(
                row,
                ("expected_interaction_contract", "interaction_contract"),
            )
            if interaction_contract_raw is None:
                open_risk_index += 1
                _append_req_015_open_risk(
                    open_risks=open_risks,
                    open_risk_index=open_risk_index,
                    reason_code=REASON_CODE_REQ_015_INTERACTION_CONTRACT_MISSING,
                    risk_level="high",
                    risk_statement=(
                        "Cross-project obligation omitted because expected interaction contract is missing: "
                        f"{summary}"
                    ),
                    source_fields=["broad_sweep_context.cross_project_obligations[].expected_interaction_contract"],
                    recommendation_ids=recommendation_links,
                    evidence_rows=baseline_evidence_refs,
                    target_project_id=peer_project_id,
                    research_event_id=research_event_id,
                )
                continue
            try:
                expected_interaction_contract = _normalize_req_015_expected_interaction_contract(
                    interaction_contract_raw,
                    field_name=f"broad_sweep_context.cross_project_obligations[{index}].expected_interaction_contract",
                )
            except Req015Error:
                open_risk_index += 1
                _append_req_015_open_risk(
                    open_risks=open_risks,
                    open_risk_index=open_risk_index,
                    reason_code=REASON_CODE_REQ_015_INTERACTION_CONTRACT_MISSING,
                    risk_level="high",
                    risk_statement=(
                        "Cross-project obligation omitted because expected interaction contract is incomplete: "
                        f"{summary}"
                    ),
                    source_fields=["broad_sweep_context.cross_project_obligations[].expected_interaction_contract"],
                    recommendation_ids=recommendation_links,
                    evidence_rows=baseline_evidence_refs,
                    target_project_id=peer_project_id,
                    research_event_id=research_event_id,
                )
                continue

            side_effect_notes_raw = _mapping_value_by_alias(
                row,
                ("dependency_side_effect_notes", "side_effect_notes", "dependency_notes"),
            )
            if side_effect_notes_raw is None:
                open_risk_index += 1
                _append_req_015_open_risk(
                    open_risks=open_risks,
                    open_risk_index=open_risk_index,
                    reason_code=REASON_CODE_REQ_015_SIDE_EFFECT_NOTES_MISSING,
                    risk_level="high",
                    risk_statement=(
                        "Cross-project obligation omitted because dependency side-effect notes are missing: "
                        f"{summary}"
                    ),
                    source_fields=["broad_sweep_context.cross_project_obligations[].dependency_side_effect_notes[]"],
                    recommendation_ids=recommendation_links,
                    evidence_rows=baseline_evidence_refs,
                    target_project_id=peer_project_id,
                    research_event_id=research_event_id,
                )
                continue
            try:
                dependency_side_effect_notes = _normalize_req_015_side_effect_notes(
                    side_effect_notes_raw,
                    field_name=f"broad_sweep_context.cross_project_obligations[{index}].dependency_side_effect_notes",
                )
            except Req015Error:
                open_risk_index += 1
                _append_req_015_open_risk(
                    open_risks=open_risks,
                    open_risk_index=open_risk_index,
                    reason_code=REASON_CODE_REQ_015_SIDE_EFFECT_NOTES_MISSING,
                    risk_level="high",
                    risk_statement=(
                        "Cross-project obligation omitted because dependency side-effect notes are empty: "
                        f"{summary}"
                    ),
                    source_fields=["broad_sweep_context.cross_project_obligations[].dependency_side_effect_notes[]"],
                    recommendation_ids=recommendation_links,
                    evidence_rows=baseline_evidence_refs,
                    target_project_id=peer_project_id,
                    research_event_id=research_event_id,
                )
                continue

            peer_doc_refs = _resolve_req_015_optional_doc_refs(
                _mapping_value_by_alias(
                    row,
                    ("peer_project_doc_refs", "peer_project_docs", "doc_refs", "project_doc_refs"),
                ),
                field_name=f"broad_sweep_context.cross_project_obligations[{index}].peer_project_doc_refs",
            )
            missing_peer_doc_refs = [ref for ref in peer_doc_refs if not _resolve_ref_path(ref).exists()]
            if missing_peer_doc_refs:
                open_risk_index += 1
                _append_req_015_open_risk(
                    open_risks=open_risks,
                    open_risk_index=open_risk_index,
                    reason_code=REASON_CODE_PEER_PROJECT_DOC_MISSING,
                    risk_level="high",
                    risk_statement=(
                        "Cross-project obligation blocked by missing peer-project docs "
                        f"for {peer_project_id}: {', '.join(missing_peer_doc_refs)}"
                    ),
                    source_fields=[
                        "broad_sweep_context.cross_project_obligations[].peer_project_doc_refs[]",
                        "broad_sweep_context.cross_project_obligations[]",
                    ],
                    recommendation_ids=recommendation_links,
                    evidence_rows=baseline_evidence_refs,
                    target_project_id=peer_project_id,
                    research_event_id=research_event_id,
                )
                continue

            evidence_refs_raw = _mapping_value_by_alias(
                row,
                ("earth_sweep_evidence_refs", "earth_sweep_artifact_ids", "evidence_artifact_ids", "evidence_refs"),
            )
            if evidence_refs_raw is None:
                open_risk_index += 1
                _append_req_015_open_risk(
                    open_risks=open_risks,
                    open_risk_index=open_risk_index,
                    reason_code=REASON_CODE_EARTH_SWEEP_EVIDENCE_MISSING,
                    risk_level="high",
                    risk_statement=(
                        "Cross-project obligation omitted until Earth-sweep evidence is attached: "
                        f"{summary}"
                    ),
                    source_fields=["broad_sweep_context.cross_project_obligations[].earth_sweep_evidence_refs[]"],
                    recommendation_ids=recommendation_links,
                    evidence_rows=baseline_evidence_refs,
                    target_project_id=peer_project_id,
                    research_event_id=research_event_id,
                )
                continue

            evidence_artifact_ids = _resolve_req_015_artifact_id_candidates(
                _require_sequence_req_015(
                    evidence_refs_raw,
                    field_name=f"broad_sweep_context.cross_project_obligations[{index}].earth_sweep_evidence_refs",
                ),
                field_name=f"broad_sweep_context.cross_project_obligations[{index}].earth_sweep_evidence_refs",
                evidence_by_id=evidence_by_id,
            )
            if not evidence_artifact_ids:
                open_risk_index += 1
                _append_req_015_open_risk(
                    open_risks=open_risks,
                    open_risk_index=open_risk_index,
                    reason_code=REASON_CODE_EARTH_SWEEP_EVIDENCE_MISSING,
                    risk_level="high",
                    risk_statement=(
                        "Cross-project obligation omitted until Earth-sweep evidence is attached: "
                        f"{summary}"
                    ),
                    source_fields=["broad_sweep_context.cross_project_obligations[].earth_sweep_evidence_refs[]"],
                    recommendation_ids=recommendation_links,
                    evidence_rows=baseline_evidence_refs,
                    target_project_id=peer_project_id,
                    research_event_id=research_event_id,
                )
                continue

            normalized_evidence_refs = _resolve_req_015_evidence_refs(
                artifact_ids=evidence_artifact_ids,
                evidence_by_id=evidence_by_id,
                field_name=f"broad_sweep_context.cross_project_obligations[{index}].earth_sweep_evidence_refs",
            )
            stale_evidence_refs = [dict(item) for item in normalized_evidence_refs if _to_bool(item.get("stale"))]
            if stale_evidence_refs:
                open_risk_index += 1
                _append_req_015_open_risk(
                    open_risks=open_risks,
                    open_risk_index=open_risk_index,
                    reason_code=REASON_CODE_EARTH_SWEEP_STALE_SOURCE_ARTIFACT,
                    risk_level="high",
                    risk_statement=(
                        "Cross-project obligation omitted because Earth-sweep source artifacts are stale: "
                        f"{summary}"
                    ),
                    source_fields=[
                        "broad_sweep_context.cross_project_obligations[].earth_sweep_evidence_refs[]",
                        "evidence_refs[]",
                    ],
                    recommendation_ids=recommendation_links,
                    evidence_rows=stale_evidence_refs,
                    target_project_id=peer_project_id,
                    research_event_id=research_event_id,
                )
                continue

            opportunity_index += 1
            opportunities.append(
                _build_req_015_opportunity_row(
                    opportunity_index=opportunity_index,
                    target_project_id=target_project_id,
                    peer_project_id=peer_project_id,
                    opportunity_summary=summary,
                    recommendation_links=recommendation_links,
                    recommendation_fields_by_id=recommendation_fields_by_id,
                    expected_interaction_contract=expected_interaction_contract,
                    dependency_side_effect_notes=dependency_side_effect_notes,
                    evidence_refs=normalized_evidence_refs,
                    source_fields=[
                        "broad_sweep_context.cross_project_obligations[]",
                        "broad_sweep_context.cross_project_obligations[].expected_interaction_contract",
                        "broad_sweep_context.cross_project_obligations[].dependency_side_effect_notes[]",
                        "broad_sweep_context.cross_project_obligations[].earth_sweep_evidence_refs[]",
                        "recommendations[]",
                    ],
                    research_event_id=research_event_id,
                )
            )

    unresolved_raw = _mapping_value_by_alias(
        broad_sweep_context,
        ("unresolved_ideas", "open_risks", "unresolved"),
    )
    if unresolved_raw is not None:
        unresolved_rows = _require_sequence_req_015(
            unresolved_raw,
            field_name="broad_sweep_context.unresolved_ideas",
        )
        for index, raw_row in enumerate(unresolved_rows):
            summary = ""
            risk_level = "medium"
            peer_project_id = ""
            recommendation_links: list[str] = []
            evidence_artifact_ids: list[str] = []

            if isinstance(raw_row, Mapping):
                summary = _require_text_req_015(
                    _mapping_value_by_alias(raw_row, ("summary", "idea", "risk_statement", "question", "statement")),
                    field_name=f"broad_sweep_context.unresolved_ideas[{index}].summary",
                )
                peer_project_id = _as_text(_mapping_value_by_alias(raw_row, ("target_project_id", "peer_project_id", "project_id")))
                risk_level_value = _as_text(raw_row.get("risk_level"))
                if risk_level_value:
                    if risk_level_value not in ALLOWED_RISK_LEVELS:
                        raise Req015Error(
                            f"broad_sweep_context.unresolved_ideas[{index}].risk_level must be one of {sorted(ALLOWED_RISK_LEVELS)}"
                        )
                    risk_level = risk_level_value
                recommendation_links = _resolve_req_015_recommendation_links(
                    value=_mapping_value_by_alias(raw_row, ("recommendation_ids", "linked_recommendation_ids")),
                    known_recommendation_ids=recommendation_ids,
                    field_name=f"broad_sweep_context.unresolved_ideas[{index}].recommendation_ids",
                )
                evidence_raw = _mapping_value_by_alias(
                    raw_row,
                    ("earth_sweep_evidence_refs", "earth_sweep_artifact_ids", "evidence_artifact_ids", "evidence_refs"),
                )
                if evidence_raw is not None:
                    evidence_artifact_ids = _resolve_req_015_artifact_id_candidates(
                        _require_sequence_req_015(
                            evidence_raw,
                            field_name=f"broad_sweep_context.unresolved_ideas[{index}].earth_sweep_evidence_refs",
                        ),
                        field_name=f"broad_sweep_context.unresolved_ideas[{index}].earth_sweep_evidence_refs",
                        evidence_by_id=evidence_by_id,
                    )
            else:
                summary = _require_text_req_015(
                    raw_row,
                    field_name=f"broad_sweep_context.unresolved_ideas[{index}]",
                )

            evidence_rows = _resolve_req_015_evidence_refs(
                artifact_ids=evidence_artifact_ids,
                evidence_by_id=evidence_by_id,
                field_name=f"broad_sweep_context.unresolved_ideas[{index}].earth_sweep_evidence_refs",
            ) if evidence_artifact_ids else baseline_evidence_refs

            open_risk_index += 1
            _append_req_015_open_risk(
                open_risks=open_risks,
                open_risk_index=open_risk_index,
                reason_code="unresolved_idea_open_risk",
                risk_level=risk_level,
                risk_statement=summary,
                source_fields=["broad_sweep_context.unresolved_ideas[]"],
                recommendation_ids=recommendation_links,
                evidence_rows=evidence_rows,
                target_project_id=peer_project_id,
                research_event_id=research_event_id,
            )

    return opportunities, open_risks, opportunity_index, open_risk_index


def serialize_req_015_integration_opportunity_bundle(payload: Mapping[str, Any]) -> str:
    bundle = {
        "target_project": payload.get("target_project", {}),
        "integration_opportunities": payload.get("integration_opportunities", []),
        "open_risks": payload.get("open_risks", []),
    }
    return json.dumps(bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _req_015_bundle_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(serialize_req_015_integration_opportunity_bundle(payload).encode("utf-8")).hexdigest()


def build_req_015_integration_opportunity_detection(
    *,
    target_project: Mapping[str, Any],
    integration_candidates: Sequence[Any] | None = None,
    broad_sweep_context: Mapping[str, Any] | None = None,
    evidence_refs: Sequence[Any] | None = None,
    recommendations: Sequence[Any] | None = None,
    research_event_id: str = "",
    normalized_at_utc: str | None = None,
) -> dict[str, Any]:
    """Build REQ-015 integration opportunity data-model payload."""
    normalized_target_project = {
        "project_id": _require_text_req_015(
            target_project.get("project_id"),
            field_name="target_project.project_id",
        ),
    }
    target_project_name = _as_text(target_project.get("project_name"))
    if target_project_name:
        normalized_target_project["project_name"] = target_project_name

    recommendation_ids, recommendation_fields_by_id = _normalize_req_015_recommendations(recommendations)
    evidence_catalog = _normalize_req_015_evidence_catalog(evidence_refs)
    evidence_by_id = {row["artifact_id"]: dict(row) for row in evidence_catalog}

    opportunities: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    opportunity_index = 0
    open_risk_index = 0

    if broad_sweep_context is not None:
        normalized_broad_sweep = _require_mapping_req_015(
            broad_sweep_context,
            field_name="broad_sweep_context",
        )
        (
            broad_sweep_opportunities,
            broad_sweep_open_risks,
            opportunity_index,
            open_risk_index,
        ) = _normalize_req_015_broad_sweep_context(
            target_project_id=normalized_target_project["project_id"],
            broad_sweep_context=normalized_broad_sweep,
            evidence_by_id=evidence_by_id,
            evidence_catalog_rows=evidence_catalog,
            recommendation_ids=recommendation_ids,
            recommendation_fields_by_id=recommendation_fields_by_id,
            opportunity_start_index=opportunity_index,
            open_risk_start_index=open_risk_index,
            research_event_id=_as_text(research_event_id),
        )
        opportunities.extend(broad_sweep_opportunities)
        open_risks.extend(broad_sweep_open_risks)

    normalized_candidates: Sequence[Any] = []
    if integration_candidates is not None:
        normalized_candidates = _require_sequence_req_015(
            integration_candidates,
            field_name="integration_candidates",
        )
    if not opportunities and not normalized_candidates and not open_risks:
        raise Req015Error(
            "at least one integration candidate source is required: integration_candidates[] or broad_sweep_context.cross_project_obligations[]"
        )

    for index, row in enumerate(normalized_candidates):
        candidate = _require_mapping_req_015(row, field_name=f"integration_candidates[{index}]")
        peer_project_id = _require_text_req_015(
            candidate.get("peer_project_id"),
            field_name=f"integration_candidates[{index}].peer_project_id",
        )
        if peer_project_id == normalized_target_project["project_id"]:
            raise Req015Error(
                f"integration_candidates[{index}].peer_project_id must differ from target_project.project_id"
            )

        recommendation_links = _resolve_req_015_recommendation_links(
            value=_mapping_value_by_alias(candidate, ("recommendation_ids", "linked_recommendation_ids")),
            known_recommendation_ids=recommendation_ids,
            field_name=f"integration_candidates[{index}].recommendation_ids",
        )
        if not recommendation_links and recommendation_ids:
            recommendation_links = list(recommendation_ids)

        evidence_rows = _normalize_req_015_evidence_refs(
            _require_sequence_req_015(
                candidate.get("evidence_refs"),
                field_name=f"integration_candidates[{index}].evidence_refs",
            ),
            field_name=f"integration_candidates[{index}].evidence_refs",
        )
        for evidence_row in evidence_rows:
            evidence_by_id[evidence_row["artifact_id"]] = dict(evidence_row)

        opportunity_index += 1
        opportunities.append(
            _build_req_015_opportunity_row(
                opportunity_index=opportunity_index,
                target_project_id=normalized_target_project["project_id"],
                peer_project_id=peer_project_id,
                opportunity_summary=_require_text_req_015(
                    candidate.get("opportunity_summary"),
                    field_name=f"integration_candidates[{index}].opportunity_summary",
                ),
                recommendation_links=recommendation_links,
                recommendation_fields_by_id=recommendation_fields_by_id,
                expected_interaction_contract=_normalize_req_015_expected_interaction_contract(
                    candidate.get("expected_interaction_contract"),
                    field_name=f"integration_candidates[{index}].expected_interaction_contract",
                ),
                dependency_side_effect_notes=_normalize_req_015_side_effect_notes(
                    candidate.get("dependency_side_effect_notes"),
                    field_name=f"integration_candidates[{index}].dependency_side_effect_notes",
                ),
                evidence_refs=evidence_rows,
                source_fields=[
                    "integration_candidates[].opportunity_summary",
                    "integration_candidates[].expected_interaction_contract",
                    "integration_candidates[].dependency_side_effect_notes[]",
                    "integration_candidates[].evidence_refs[]",
                    "recommendations[]",
                ],
                research_event_id=_as_text(research_event_id),
            )
        )

    output_payload = {
        "schema_version": REQ_015_SCHEMA_VERSION,
        "requirement_id": REQ_015_REQUIREMENT_ID,
        "target_project": normalized_target_project,
        "integration_opportunities": opportunities,
        "open_risks": open_risks,
        "source": {
            "normalized_at_utc": _normalize_timestamp(normalized_at_utc),
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
        },
    }
    output_payload["source"]["context_bundle_sha256"] = _req_015_bundle_sha256(output_payload)
    return output_payload


def validate_req_015_integration_opportunity_detection(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-015 integration opportunity contract shape and linkage rules."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be an object"]

    required_top_level = {
        "schema_version",
        "requirement_id",
        "target_project",
        "integration_opportunities",
        "open_risks",
        "source",
    }
    top_keys = set(payload.keys())
    missing_top = sorted(required_top_level - top_keys)
    unexpected_top = sorted(top_keys - required_top_level)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("schema_version") != REQ_015_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_015_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_015_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_015_REQUIREMENT_ID}")

    target_project = payload.get("target_project")
    if not isinstance(target_project, Mapping):
        errors.append("target_project must be an object")
        target_project = {}
    target_project_id = _as_text(target_project.get("project_id"))
    if not target_project_id:
        errors.append("target_project.project_id must be a non-empty string")

    integration_opportunities = payload.get("integration_opportunities")
    if not isinstance(integration_opportunities, Sequence) or isinstance(
        integration_opportunities, (str, bytes, bytearray)
    ):
        errors.append("integration_opportunities must be an array")
        integration_opportunities = []

    opportunity_ids: set[str] = set()
    open_risk_ids: set[str] = set()
    evidence_ids: set[str] = set()
    for index, row in enumerate(integration_opportunities):
        if not isinstance(row, Mapping):
            errors.append(f"integration_opportunities[{index}] must be an object")
            continue
        opportunity_id = _as_text(row.get("integration_opportunity_id"))
        row_target_project_id = _as_text(row.get("target_project_id"))
        peer_project_id = _as_text(row.get("peer_project_id"))
        opportunity_summary = _as_text(row.get("opportunity_summary"))
        recommendation_id = _as_text(row.get("recommendation_id"))
        linked_recommendation_ids = row.get("linked_recommendation_ids")
        recommendation_fields = row.get("recommendation_fields")
        expected_interaction_contract = row.get("expected_interaction_contract")
        dependency_side_effect_notes = row.get("dependency_side_effect_notes")
        evidence_refs = row.get("evidence_refs")
        provenance = row.get("provenance")

        if not opportunity_id:
            errors.append(f"integration_opportunities[{index}].integration_opportunity_id is required")
        elif opportunity_id in opportunity_ids:
            errors.append(f"integration_opportunities[{index}].integration_opportunity_id duplicates {opportunity_id}")
        else:
            opportunity_ids.add(opportunity_id)

        if not row_target_project_id:
            errors.append(f"integration_opportunities[{index}].target_project_id is required")
        elif target_project_id and row_target_project_id != target_project_id:
            errors.append(
                f"integration_opportunities[{index}].target_project_id must match target_project.project_id"
            )

        if not peer_project_id:
            errors.append(f"integration_opportunities[{index}].peer_project_id is required")
        elif target_project_id and peer_project_id == target_project_id:
            errors.append(
                f"integration_opportunities[{index}].peer_project_id must differ from target_project.project_id"
            )

        if not opportunity_summary:
            errors.append(f"integration_opportunities[{index}].opportunity_summary is required")

        if not recommendation_id:
            errors.append(f"integration_opportunities[{index}].recommendation_id is required")

        if not isinstance(linked_recommendation_ids, Sequence) or isinstance(
            linked_recommendation_ids,
            (str, bytes, bytearray),
        ):
            errors.append(f"integration_opportunities[{index}].linked_recommendation_ids must be an array")
        elif not linked_recommendation_ids:
            errors.append(f"integration_opportunities[{index}].linked_recommendation_ids must not be empty")
        else:
            normalized_links = []
            for link_index, raw_link in enumerate(linked_recommendation_ids):
                link = _as_text(raw_link)
                if not link:
                    errors.append(
                        f"integration_opportunities[{index}].linked_recommendation_ids[{link_index}] must be non-empty"
                    )
                    continue
                normalized_links.append(link)
            if recommendation_id and normalized_links and recommendation_id not in normalized_links:
                errors.append(
                    f"integration_opportunities[{index}].recommendation_id must appear in linked_recommendation_ids"
                )

        if not isinstance(recommendation_fields, Mapping):
            errors.append(f"integration_opportunities[{index}].recommendation_fields must be an object")
        else:
            for key in ("summary", "rationale", "expected_impact"):
                if not _as_text(recommendation_fields.get(key)):
                    errors.append(f"integration_opportunities[{index}].recommendation_fields.{key} is required")
            if _as_text(recommendation_fields.get("risk_level")) not in ALLOWED_RISK_LEVELS:
                errors.append(
                    f"integration_opportunities[{index}].recommendation_fields.risk_level must be one of {sorted(ALLOWED_RISK_LEVELS)}"
                )

        if not isinstance(expected_interaction_contract, Mapping):
            errors.append(f"integration_opportunities[{index}].expected_interaction_contract must be an object")
        else:
            for key in (
                "interaction_type",
                "producer_component",
                "consumer_component",
                "interface",
                "data_contract",
            ):
                if not _as_text(expected_interaction_contract.get(key)):
                    errors.append(
                        f"integration_opportunities[{index}].expected_interaction_contract.{key} is required"
                    )

        if not isinstance(dependency_side_effect_notes, Sequence) or isinstance(
            dependency_side_effect_notes,
            (str, bytes, bytearray),
        ):
            errors.append(f"integration_opportunities[{index}].dependency_side_effect_notes must be an array")
        elif not dependency_side_effect_notes:
            errors.append(f"integration_opportunities[{index}].dependency_side_effect_notes must not be empty")
        else:
            for note_index, note in enumerate(dependency_side_effect_notes):
                if not _as_text(note):
                    errors.append(
                        "integration_opportunities"
                        f"[{index}].dependency_side_effect_notes[{note_index}] must be non-empty"
                    )

        _validate_evidence_refs_array(
            evidence_refs=evidence_refs,
            field_name=f"integration_opportunities[{index}].evidence_refs",
            errors=errors,
            evidence_ids=evidence_ids,
            require_non_empty=True,
        )

        if not isinstance(provenance, Mapping):
            errors.append(f"integration_opportunities[{index}].provenance must be an object")
        else:
            source_fields = provenance.get("source_fields")
            if not isinstance(source_fields, Sequence) or isinstance(source_fields, (str, bytes, bytearray)):
                errors.append(f"integration_opportunities[{index}].provenance.source_fields must be an array")
            elif not source_fields:
                errors.append(f"integration_opportunities[{index}].provenance.source_fields must not be empty")
            else:
                for source_index, source_field in enumerate(source_fields):
                    if not _as_text(source_field):
                        errors.append(
                            f"integration_opportunities[{index}].provenance.source_fields[{source_index}] must be non-empty"
                        )

    open_risks = payload.get("open_risks")
    if not isinstance(open_risks, Sequence) or isinstance(open_risks, (str, bytes, bytearray)):
        errors.append("open_risks must be an array")
        open_risks = []
    elif not open_risks and not integration_opportunities:
        errors.append("integration_opportunities or open_risks must not both be empty")

    for index, row in enumerate(open_risks):
        if not isinstance(row, Mapping):
            errors.append(f"open_risks[{index}] must be an object")
            continue
        open_risk_id = _as_text(row.get("open_risk_id"))
        reason_code = _as_text(row.get("reason_code"))
        risk_level = _as_text(row.get("risk_level"))
        risk_statement = _as_text(row.get("risk_statement"))
        recommendation_ids = row.get("recommendation_ids")
        evidence_refs = row.get("evidence_refs")
        provenance = row.get("provenance")

        if not open_risk_id:
            errors.append(f"open_risks[{index}].open_risk_id is required")
        elif open_risk_id in open_risk_ids:
            errors.append(f"open_risks[{index}].open_risk_id duplicates {open_risk_id}")
        else:
            open_risk_ids.add(open_risk_id)

        if not reason_code:
            errors.append(f"open_risks[{index}].reason_code is required")
        if risk_level not in ALLOWED_RISK_LEVELS:
            errors.append(f"open_risks[{index}].risk_level must be one of {sorted(ALLOWED_RISK_LEVELS)}")
        if not risk_statement:
            errors.append(f"open_risks[{index}].risk_statement is required")

        if not isinstance(recommendation_ids, Sequence) or isinstance(recommendation_ids, (str, bytes, bytearray)):
            errors.append(f"open_risks[{index}].recommendation_ids must be an array")
        else:
            for link_index, raw_link in enumerate(recommendation_ids):
                if not _as_text(raw_link):
                    errors.append(f"open_risks[{index}].recommendation_ids[{link_index}] must be non-empty")

        _validate_evidence_refs_array(
            evidence_refs=evidence_refs,
            field_name=f"open_risks[{index}].evidence_refs",
            errors=errors,
            evidence_ids=evidence_ids,
            require_non_empty=True,
        )

        if not isinstance(provenance, Mapping):
            errors.append(f"open_risks[{index}].provenance must be an object")
        else:
            source_fields = provenance.get("source_fields")
            if not isinstance(source_fields, Sequence) or isinstance(source_fields, (str, bytes, bytearray)):
                errors.append(f"open_risks[{index}].provenance.source_fields must be an array")
            elif not source_fields:
                errors.append(f"open_risks[{index}].provenance.source_fields must not be empty")
            else:
                for source_index, source_field in enumerate(source_fields):
                    if not _as_text(source_field):
                        errors.append(f"open_risks[{index}].provenance.source_fields[{source_index}] must be non-empty")

    source = payload.get("source")
    if not isinstance(source, Mapping):
        errors.append("source must be an object")
    else:
        if _as_text(source.get("normalized_at_utc")) == "":
            errors.append("source.normalized_at_utc must be a non-empty string")
        if source.get("tool") != TOOL:
            errors.append(f"source.tool must be {TOOL}")
        if source.get("tool_version") != TOOL_VERSION:
            errors.append(f"source.tool_version must be {TOOL_VERSION}")
        context_bundle_sha256 = _as_text(source.get("context_bundle_sha256"))
        if not context_bundle_sha256:
            errors.append("source.context_bundle_sha256 must be a non-empty string")
        elif not re.fullmatch(r"[0-9a-f]{64}", context_bundle_sha256):
            errors.append("source.context_bundle_sha256 must be a lowercase hex sha256 digest")

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
            recommendation_ids=(
                _require_sequence(input_payload.get("recommendation_ids"), field_name="input.recommendation_ids")
                if input_payload.get("recommendation_ids") is not None
                else None
            ),
            recommendations=(
                _require_sequence(input_payload.get("recommendations"), field_name="input.recommendations")
                if input_payload.get("recommendations") is not None
                else None
            ),
            recommendation_topic_map=(
                _require_mapping(input_payload.get("recommendation_topic_map"), field_name="input.recommendation_topic_map")
                if input_payload.get("recommendation_topic_map") is not None
                else None
            ),
            broad_sweep_context=(
                _require_mapping(input_payload.get("broad_sweep_context"), field_name="input.broad_sweep_context")
                if input_payload.get("broad_sweep_context") is not None
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
