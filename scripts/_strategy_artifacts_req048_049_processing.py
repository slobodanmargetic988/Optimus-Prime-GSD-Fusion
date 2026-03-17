#!/usr/bin/env python3
"""Compatibility processing layer for REQ-048/049 handoff workflows."""

from __future__ import annotations

from typing import Any, Mapping

from scripts import _strategy_artifacts_req049 as _req049
from scripts import _strategy_artifacts_req052 as _req052


REQ_048_SCHEMA_VERSION = _req052.REQ_048_SCHEMA_VERSION
REQ_048_REQUIREMENT_ID = _req052.REQ_048_REQUIREMENT_ID
REQ_048_ANALYSIS_TYPE = _req052.REQ_048_ANALYSIS_TYPE
REQ_048_CALL_ID = _req052.REQ_048_CALL_ID
REQ_049_SCHEMA_VERSION = _req049.REQ_049_SCHEMA_VERSION
REQ_049_REQUIREMENT_ID = _req049.REQ_049_REQUIREMENT_ID
REQ_049_ANALYSIS_TYPE = _req049.REQ_049_ANALYSIS_TYPE
REQ_049_CALL_ID = _req049.REQ_049_CALL_ID
REQ_049_ARTIFACT_KIND = _req049.REQ_049_ARTIFACT_KIND

_REQ_048_RECOMMENDATION_REQUIRED_FIELDS = (
    "summary",
    "rationale",
    "packet_kind",
    "lane",
    "priority",
    "strategy_packet_input_id",
)
_REQ_049_RECOMMENDATION_REQUIRED_FIELDS = (
    "recommendation_id",
    "rationale",
    "impacts",
    "risk_ids",
    "evidence_refs",
)


def _default_cross_project_context_usage() -> dict[str, Any]:
    return {
        "cross_project_context_provided": False,
        "cross_project_context_used": False,
        "projects_considered": [],
        "earth_sweep_evidence_refs_considered": [],
        "cross_project_obligation_count": 0,
        "unresolved_idea_count": 0,
        "recommendation_ids_with_context": [],
    }


def _normalize_cross_project_context_usage(value: Any, *, field_name: str) -> dict[str, Any]:
    if value is None:
        return _default_cross_project_context_usage()

    row = _req052._require_mapping(value, field_name=field_name)
    expected = {
        "cross_project_context_provided",
        "cross_project_context_used",
        "projects_considered",
        "earth_sweep_evidence_refs_considered",
        "cross_project_obligation_count",
        "unresolved_idea_count",
        "recommendation_ids_with_context",
    }
    unexpected = sorted(set(row.keys()) - expected)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {unexpected}")

    provided = row.get("cross_project_context_provided")
    used = row.get("cross_project_context_used")
    if not isinstance(provided, bool):
        raise ValueError(f"{field_name}.cross_project_context_provided must be a boolean")
    if not isinstance(used, bool):
        raise ValueError(f"{field_name}.cross_project_context_used must be a boolean")

    return {
        "cross_project_context_provided": provided,
        "cross_project_context_used": used,
        "projects_considered": _req052._normalize_optional_str_list(
            row.get("projects_considered"),
            field_name=f"{field_name}.projects_considered",
        ),
        "earth_sweep_evidence_refs_considered": _req052._normalize_optional_str_list(
            row.get("earth_sweep_evidence_refs_considered"),
            field_name=f"{field_name}.earth_sweep_evidence_refs_considered",
        ),
        "cross_project_obligation_count": _req052._normalize_non_negative_int(
            row.get("cross_project_obligation_count"),
            field_name=f"{field_name}.cross_project_obligation_count",
        ),
        "unresolved_idea_count": _req052._normalize_non_negative_int(
            row.get("unresolved_idea_count"),
            field_name=f"{field_name}.unresolved_idea_count",
        ),
        "recommendation_ids_with_context": _req052._normalize_optional_str_list(
            row.get("recommendation_ids_with_context"),
            field_name=f"{field_name}.recommendation_ids_with_context",
        ),
    }


def _mapping_sequence(value: Any, *, field_name: str) -> list[Mapping[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    rows: list[Mapping[str, Any]] = []
    for index, row in enumerate(value):
        rows.append(_req052._require_mapping(row, field_name=f"{field_name}[{index}]"))
    return rows


def _derive_cross_project_context_usage_from_broad_sweep_context(value: Any) -> dict[str, Any]:
    if value is None:
        return _default_cross_project_context_usage()

    broad_sweep = _req052._require_mapping(value, field_name="broad_sweep_context")
    expected = {"earth_sweep_evidence_refs", "cross_project_context", "earth_sweep"}
    unexpected = sorted(set(broad_sweep.keys()) - expected)
    if unexpected:
        raise ValueError(f"broad_sweep_context has unexpected keys: {unexpected}")

    earth_refs = _req052._normalize_optional_str_list(
        broad_sweep.get("earth_sweep_evidence_refs"),
        field_name="broad_sweep_context.earth_sweep_evidence_refs",
    )
    projects_considered: set[str] = set()
    recommendation_ids_with_context: set[str] = set()
    cross_project_obligation_count = 0
    unresolved_idea_count = 0

    cross_project_rows = _mapping_sequence(
        broad_sweep.get("cross_project_context"),
        field_name="broad_sweep_context.cross_project_context",
    )
    for index, row in enumerate(cross_project_rows):
        project_id = _req052._require_nonempty_text(
            row.get("project_id"),
            field_name=f"broad_sweep_context.cross_project_context[{index}].project_id",
        )
        projects_considered.add(project_id)
        _req052._normalize_optional_str_list(
            row.get("evidence_refs"),
            field_name=f"broad_sweep_context.cross_project_context[{index}].evidence_refs",
        )

    earth_sweep_raw = broad_sweep.get("earth_sweep")
    if earth_sweep_raw is None:
        earth_projects: list[Mapping[str, Any]] = []
    else:
        earth_sweep = _req052._require_mapping(earth_sweep_raw, field_name="broad_sweep_context.earth_sweep")
        expected_earth_sweep = {"projects"}
        unexpected_earth_sweep = sorted(set(earth_sweep.keys()) - expected_earth_sweep)
        if unexpected_earth_sweep:
            raise ValueError(f"broad_sweep_context.earth_sweep has unexpected keys: {unexpected_earth_sweep}")
        earth_projects = _mapping_sequence(
            earth_sweep.get("projects"),
            field_name="broad_sweep_context.earth_sweep.projects",
        )

    for project_index, project in enumerate(earth_projects):
        project_id = _req052._require_nonempty_text(
            project.get("project_id"),
            field_name=f"broad_sweep_context.earth_sweep.projects[{project_index}].project_id",
        )
        projects_considered.add(project_id)
        obligations = _mapping_sequence(
            project.get("obligations"),
            field_name=f"broad_sweep_context.earth_sweep.projects[{project_index}].obligations",
        )
        unresolved_ideas = _mapping_sequence(
            project.get("unresolved_ideas"),
            field_name=f"broad_sweep_context.earth_sweep.projects[{project_index}].unresolved_ideas",
        )
        cross_project_obligation_count += len(obligations)
        unresolved_idea_count += len(unresolved_ideas)

        for obligation_index, obligation in enumerate(obligations):
            recommendation_ids = _req052._normalize_optional_str_list(
                obligation.get("recommendation_ids"),
                field_name=(
                    "broad_sweep_context.earth_sweep.projects"
                    f"[{project_index}].obligations[{obligation_index}].recommendation_ids"
                ),
            )
            recommendation_ids_with_context.update(recommendation_ids)
        for unresolved_index, unresolved in enumerate(unresolved_ideas):
            recommendation_ids = _req052._normalize_optional_str_list(
                unresolved.get("recommendation_ids"),
                field_name=(
                    "broad_sweep_context.earth_sweep.projects"
                    f"[{project_index}].unresolved_ideas[{unresolved_index}].recommendation_ids"
                ),
            )
            recommendation_ids_with_context.update(recommendation_ids)

    provided = bool(projects_considered or earth_refs)
    used = provided and bool(cross_project_obligation_count or unresolved_idea_count or earth_refs)
    return {
        "cross_project_context_provided": provided,
        "cross_project_context_used": used,
        "projects_considered": sorted(projects_considered),
        "earth_sweep_evidence_refs_considered": earth_refs,
        "cross_project_obligation_count": cross_project_obligation_count,
        "unresolved_idea_count": unresolved_idea_count,
        "recommendation_ids_with_context": sorted(recommendation_ids_with_context),
    }


def _merge_cross_project_context_usage(
    explicit: Mapping[str, Any],
    derived: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "cross_project_context_provided": bool(
            explicit["cross_project_context_provided"] or derived["cross_project_context_provided"]
        ),
        "cross_project_context_used": bool(
            explicit["cross_project_context_used"] or derived["cross_project_context_used"]
        ),
        "projects_considered": sorted(set(explicit["projects_considered"]) | set(derived["projects_considered"])),
        "earth_sweep_evidence_refs_considered": sorted(
            set(explicit["earth_sweep_evidence_refs_considered"]) | set(derived["earth_sweep_evidence_refs_considered"])
        ),
        "cross_project_obligation_count": max(
            int(explicit["cross_project_obligation_count"]),
            int(derived["cross_project_obligation_count"]),
        ),
        "unresolved_idea_count": max(
            int(explicit["unresolved_idea_count"]),
            int(derived["unresolved_idea_count"]),
        ),
        "recommendation_ids_with_context": sorted(
            set(explicit["recommendation_ids_with_context"]) | set(derived["recommendation_ids_with_context"])
        ),
    }


def _recommendation_has_earth_sweep_evidence(*, evidence_refs: list[str], earth_sweep_evidence_refs: list[str]) -> bool:
    evidence_ref_set = set(evidence_refs)
    if evidence_ref_set.intersection(set(earth_sweep_evidence_refs)):
        return True
    return any(ref.startswith("reports/earth/sweeps/") for ref in evidence_ref_set)


def _build_req_048_recommended_actions(synthesis: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    actions: list[dict[str, Any]] = []
    completeness_rows: list[dict[str, Any]] = []
    for row in synthesis["final_recommendations"]:
        missing_fields = [
            field_name
            for field_name in _REQ_048_RECOMMENDATION_REQUIRED_FIELDS
            if not isinstance(row.get(field_name), str) or not str(row.get(field_name)).strip()
        ]
        fields_complete = not missing_fields
        action_row = {
            "recommendation_id": row["recommendation_id"],
            "summary": row["summary"],
            "rationale": row["rationale"],
            "packet_kind": row["packet_kind"],
            "peer_project_id": row["peer_project_id"],
            "lane": row["lane"],
            "priority": row["priority"],
            "sequence_hint": row["sequence_hint"],
            "strategy_packet_input_id": row["strategy_packet_input_id"],
            "supporting_call_count": row["supporting_call_count"],
            "evidence_refs": list(row["evidence_refs"]),
            "fields_complete": fields_complete,
            "missing_fields": missing_fields,
        }
        actions.append(action_row)
        completeness_rows.append(
            {
                "recommendation_id": row["recommendation_id"],
                "fields_complete": fields_complete,
                "missing_fields": missing_fields,
            }
        )
    actions.sort(key=lambda row: (row["sequence_hint"], row["priority"], row["recommendation_id"]))
    completeness_rows.sort(key=lambda row: row["recommendation_id"])
    return actions, completeness_rows


def _build_req_048_cross_project_obligations(
    *,
    synthesis: Mapping[str, Any],
    context_usage: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    packet_inputs = {row["packet_input_id"]: row for row in synthesis["strategy_packet_inputs"]}
    obligations: list[dict[str, Any]] = []
    gap_open_risks: list[dict[str, Any]] = []
    earth_refs_considered = list(context_usage["earth_sweep_evidence_refs_considered"])
    for row in synthesis["final_recommendations"]:
        if row["packet_kind"] != "cross-project":
            continue
        packet_input = packet_inputs.get(row["strategy_packet_input_id"])
        packet_evidence_refs = list(packet_input["evidence_refs"]) if packet_input is not None else []
        combined_evidence_refs = sorted(set(row["evidence_refs"]) | set(packet_evidence_refs))
        earth_backed = _recommendation_has_earth_sweep_evidence(
            evidence_refs=combined_evidence_refs,
            earth_sweep_evidence_refs=earth_refs_considered,
        )
        if earth_backed:
            obligations.append(
                {
                    "project_id": row["peer_project_id"],
                    "lane": row["lane"],
                    "recommendation_id": row["recommendation_id"],
                    "strategy_packet_input_id": row["strategy_packet_input_id"],
                    "evidence_refs": combined_evidence_refs,
                }
            )
            continue
        gap_open_risks.append(
            {
                "open_risk_id": f"open-risk.missing-earth-evidence.{row['recommendation_id']}",
                "project_id": row["peer_project_id"] or "unknown-peer-project",
                "recommendation_id": row["recommendation_id"],
                "reason_code": "missing_earth_sweep_evidence_refs",
                "summary": (
                    "Cross-project recommendation cannot be promoted because Earth-sweep evidence refs are missing."
                ),
                "required_evidence_refs": list(earth_refs_considered),
                "evidence_refs": combined_evidence_refs,
            }
        )
    obligations.sort(key=lambda row: (row["project_id"], row["lane"], row["recommendation_id"]))
    gap_open_risks.sort(key=lambda row: row["open_risk_id"])
    return obligations, gap_open_risks


def _build_req_048_open_risks(
    *,
    target_project_id: str,
    synthesis: Mapping[str, Any],
    context_usage: Mapping[str, Any],
    derived_gap_open_risks: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in synthesis["open_risks"]:
        rows[row["open_risk_id"]] = {
            "open_risk_id": row["open_risk_id"],
            "project_id": row["project_id"],
            "recommendation_id": row["recommendation_id"],
            "reason_code": row["reason_code"],
            "summary": row["summary"],
            "linked_recommendation_ids": list(row["linked_recommendation_ids"]),
            "required_evidence_refs": list(row["required_evidence_refs"]),
            "evidence_refs": list(row["evidence_refs"]),
        }
    for row in derived_gap_open_risks:
        normalized_row = dict(row)
        normalized_row["linked_recommendation_ids"] = list(row.get("linked_recommendation_ids", []))
        rows[str(row["open_risk_id"])] = normalized_row

    unresolved_idea_count = int(context_usage["unresolved_idea_count"])
    if unresolved_idea_count > 0 and not rows:
        earth_refs_considered = list(context_usage["earth_sweep_evidence_refs_considered"])
        rows["open-risk.unresolved-cross-project-ideas"] = {
            "open_risk_id": "open-risk.unresolved-cross-project-ideas",
            "project_id": target_project_id,
            "recommendation_id": "context.unresolved-cross-project-ideas",
            "reason_code": "unresolved_cross_project_ideas",
            "summary": "Broad-sweep context reported unresolved ideas; they must remain open risks.",
            "linked_recommendation_ids": [],
            "required_evidence_refs": list(earth_refs_considered),
            "evidence_refs": list(earth_refs_considered),
        }
    return sorted(rows.values(), key=lambda row: row["open_risk_id"])


def _collect_req_048_evidence_refs(
    *,
    context_usage: Mapping[str, Any],
    recommended_actions: list[Mapping[str, Any]],
    cross_project_obligations: list[Mapping[str, Any]],
    open_risks: list[Mapping[str, Any]],
    multi_call_trace: list[Mapping[str, Any]],
) -> list[str]:
    evidence_refs: set[str] = set(context_usage["earth_sweep_evidence_refs_considered"])
    for row in recommended_actions:
        evidence_refs.update(str(value) for value in row["evidence_refs"])
    for row in cross_project_obligations:
        evidence_refs.update(str(value) for value in row["evidence_refs"])
    for row in open_risks:
        evidence_refs.update(str(value) for value in row["required_evidence_refs"])
        evidence_refs.update(str(value) for value in row["evidence_refs"])
    for row in multi_call_trace:
        evidence_refs.update(str(value) for value in row["input_refs"])
    return sorted(ref for ref in evidence_refs if ref)


def _determine_req_048_processing_decision(
    *,
    context_usage: Mapping[str, Any],
    cross_project_obligations: list[Mapping[str, Any]],
    open_risks: list[Mapping[str, Any]],
) -> tuple[str, str, str]:
    reason_codes = {str(row["reason_code"]) for row in open_risks}
    if "missing_earth_sweep_evidence_refs" in reason_codes:
        return (
            "collect-earth-evidence",
            "medium",
            "Cross-project obligations were withheld until Earth-sweep evidence refs are available.",
        )
    if open_risks:
        return (
            "proceed-with-open-risks",
            "medium",
            "Narrative generation is valid, but unresolved risks remain in the recommendation payload.",
        )
    if context_usage["cross_project_context_used"] and not cross_project_obligations:
        return (
            "proceed",
            "high",
            "No cross-project obligations were required after applying broad-sweep context constraints.",
        )
    return ("proceed", "high", "Recommendation output is complete and context-grounded.")


def _build_req_048_planner_hook(
    *,
    synthesis: Mapping[str, Any],
    recommended_actions: list[Mapping[str, Any]],
    open_risks: list[Mapping[str, Any]],
) -> dict[str, Any]:
    packet_inputs = {str(row["packet_input_id"]): row for row in synthesis["strategy_packet_inputs"]}
    open_risks_by_recommendation: dict[str, set[str]] = {}
    for row in open_risks:
        open_risk_id = str(row["open_risk_id"])
        linked_ids = {
            str(item).strip()
            for item in row.get("linked_recommendation_ids", [])
            if isinstance(item, str) and item.strip()
        }
        recommendation_id = str(row.get("recommendation_id") or "").strip()
        if recommendation_id:
            linked_ids.add(recommendation_id)
        for linked_recommendation_id in linked_ids:
            open_risks_by_recommendation.setdefault(linked_recommendation_id, set()).add(open_risk_id)

    mapping_rows: list[dict[str, Any]] = []
    seen_recommendation_ids: set[str] = set()

    for row in recommended_actions:
        recommendation_id = str(row["recommendation_id"])
        seen_recommendation_ids.add(recommendation_id)
        packet_input_id = str(row["strategy_packet_input_id"])
        packet_input = packet_inputs.get(packet_input_id)
        packet_recommendation_ids = (
            list(packet_input["recommendation_ids"]) if isinstance(packet_input, Mapping) else [recommendation_id]
        )
        mapping_rows.append(
            {
                "recommendation_id": recommendation_id,
                "source": "final_recommendation",
                "strategy_packet_input_id": packet_input_id,
                "packet_kind": row["packet_kind"],
                "lane": row["lane"],
                "peer_project_id": row["peer_project_id"],
                "packet_recommendation_ids": sorted(set(packet_recommendation_ids)),
                "linked_open_risk_ids": sorted(open_risks_by_recommendation.get(recommendation_id, set())),
            }
        )

    for row in synthesis["deferred_recommendations"]:
        recommendation_id = str(row["recommendation_id"])
        seen_recommendation_ids.add(recommendation_id)
        mapping_rows.append(
            {
                "recommendation_id": recommendation_id,
                "source": "deferred_recommendation",
                "strategy_packet_input_id": None,
                "packet_kind": ",".join(sorted(set(row["packet_kind_candidates"]))),
                "lane": "deferred",
                "peer_project_id": ",".join(sorted(set(row["peer_project_candidates"]))),
                "packet_recommendation_ids": [],
                "linked_open_risk_ids": sorted(open_risks_by_recommendation.get(recommendation_id, set())),
            }
        )

    for recommendation_id in sorted(open_risks_by_recommendation):
        if recommendation_id in seen_recommendation_ids:
            continue
        mapping_rows.append(
            {
                "recommendation_id": recommendation_id,
                "source": "open_risk_only",
                "strategy_packet_input_id": None,
                "packet_kind": "open-risk-only",
                "lane": "risk-follow-up",
                "peer_project_id": "",
                "packet_recommendation_ids": [],
                "linked_open_risk_ids": sorted(open_risks_by_recommendation.get(recommendation_id, set())),
            }
        )

    mapping_rows.sort(
        key=lambda row: (
            str(row["recommendation_id"]),
            str(row["source"]),
            str(row["strategy_packet_input_id"] or ""),
        )
    )
    return {
        "recommendation_ids": [str(row["recommendation_id"]) for row in mapping_rows],
        "strategy_packet_input_ids": sorted(packet_inputs),
        "recommendation_mapping_set": mapping_rows,
    }


def _build_req_048_acceptance_packet(
    *,
    decision: str,
    confidence: str,
    rationale: str,
    recommended_actions: list[Mapping[str, Any]],
    cross_project_obligations: list[Mapping[str, Any]],
    open_risks: list[Mapping[str, Any]],
    evidence_refs: list[str],
) -> dict[str, Any]:
    required_evidence_refs: set[str] = set(evidence_refs)
    for row in recommended_actions:
        required_evidence_refs.update(str(value) for value in row["evidence_refs"])
    for row in cross_project_obligations:
        required_evidence_refs.update(str(value) for value in row["evidence_refs"])
    for row in open_risks:
        required_evidence_refs.update(str(value) for value in row["required_evidence_refs"])
        required_evidence_refs.update(str(value) for value in row["evidence_refs"])

    open_risk_ids = sorted(str(row["open_risk_id"]) for row in open_risks)
    open_risk_reason_codes = sorted({str(row["reason_code"]) for row in open_risks})
    return {
        "decision": decision,
        "confidence": confidence,
        "rationale": rationale,
        "recommendation_ids": sorted({str(row["recommendation_id"]) for row in recommended_actions}),
        "cross_project_recommendation_ids": sorted(
            {str(row["recommendation_id"]) for row in cross_project_obligations}
        ),
        "required_evidence_refs": sorted(ref for ref in required_evidence_refs if ref),
        "open_risk_handling": {
            "status": "open_risks_present" if open_risks else "no_open_risks",
            "open_risk_ids": open_risk_ids,
            "reason_codes": open_risk_reason_codes,
            "requires_operator_review": bool(open_risks),
        },
    }


def process_req_048_strategy_md_generator(payload: Mapping[str, Any]) -> dict[str, Any]:
    raw = _req052._require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_048_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_048_ANALYSIS_TYPE}")

    checked_at_utc = _req052._require_nonempty_text(raw.get("now_utc"), field_name="now_utc")
    target_project = _req052._normalize_target_project(raw.get("target_project"))
    synthesis = _req052._normalize_final_strategy_synthesis(raw.get("final_strategy_synthesis"))
    multi_call_trace = _req052._normalize_multi_call_trace(raw.get("multi_call_orchestration_trace"))
    explicit_context_usage = dict(synthesis["cross_project_context_usage"])
    derived_context_usage = _derive_cross_project_context_usage_from_broad_sweep_context(
        raw.get("broad_sweep_context")
    )
    context_usage = _merge_cross_project_context_usage(explicit_context_usage, derived_context_usage)

    recommended_actions, completeness_rows = _build_req_048_recommended_actions(synthesis)
    cross_project_obligations, derived_gap_open_risks = _build_req_048_cross_project_obligations(
        synthesis=synthesis,
        context_usage=context_usage,
    )
    open_risks = _build_req_048_open_risks(
        target_project_id=target_project["project_id"],
        synthesis=synthesis,
        context_usage=context_usage,
        derived_gap_open_risks=derived_gap_open_risks,
    )
    evidence_refs = _collect_req_048_evidence_refs(
        context_usage=context_usage,
        recommended_actions=recommended_actions,
        cross_project_obligations=cross_project_obligations,
        open_risks=open_risks,
        multi_call_trace=multi_call_trace,
    )
    decision, confidence, rationale = _determine_req_048_processing_decision(
        context_usage=context_usage,
        cross_project_obligations=cross_project_obligations,
        open_risks=open_risks,
    )
    planner_hook = _build_req_048_planner_hook(
        synthesis=synthesis,
        recommended_actions=recommended_actions,
        open_risks=open_risks,
    )
    acceptance_packet = _build_req_048_acceptance_packet(
        decision=decision,
        confidence=confidence,
        rationale=rationale,
        recommended_actions=recommended_actions,
        cross_project_obligations=cross_project_obligations,
        open_risks=open_risks,
        evidence_refs=evidence_refs,
    )
    completeness_summary = {
        "complete_count": sum(1 for row in completeness_rows if row["fields_complete"]),
        "incomplete_count": sum(1 for row in completeness_rows if not row["fields_complete"]),
        "rows": completeness_rows,
    }

    return {
        "ok": True,
        "schema_version": REQ_048_SCHEMA_VERSION,
        "requirement_id": REQ_048_REQUIREMENT_ID,
        "analysis_type": REQ_048_ANALYSIS_TYPE,
        "call_id": REQ_048_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "target_project": target_project,
        "processing_behavior": {
            "context_usage": context_usage,
            "planner_hook": planner_hook,
            "acceptance_packet": acceptance_packet,
            "recommendation": {
                "decision": decision,
                "rationale": rationale,
                "confidence": confidence,
                "evidence_refs": evidence_refs,
                "recommended_actions": recommended_actions,
                "recommendation_field_completeness": completeness_summary,
                "cross_project_obligations": cross_project_obligations,
                "open_risks": open_risks,
            },
        },
        "totals": {
            "final_recommendations": len(synthesis["final_recommendations"]),
            "recommended_actions": len(recommended_actions),
            "cross_project_recommendations": sum(
                1 for row in synthesis["final_recommendations"] if row["packet_kind"] == "cross-project"
            ),
            "cross_project_obligations": len(cross_project_obligations),
            "open_risks": len(open_risks),
            "processing_evidence_refs": len(evidence_refs),
        },
    }


def _build_req_049_recommended_actions(
    recommendations: list[Mapping[str, Any]],
    risks_by_id: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    actions: list[dict[str, Any]] = []
    completeness_rows: list[dict[str, Any]] = []
    for row in recommendations:
        missing_fields: list[str] = []
        for field_name in _REQ_049_RECOMMENDATION_REQUIRED_FIELDS:
            value = row.get(field_name)
            if field_name in {"recommendation_id", "rationale"}:
                if not isinstance(value, str) or not value.strip():
                    missing_fields.append(field_name)
                continue
            if not isinstance(value, list) or not value:
                missing_fields.append(field_name)
        fields_complete = not missing_fields
        action_row = {
            "recommendation_id": row["recommendation_id"],
            "rationale": row["rationale"],
            "impacts": list(row["impacts"]),
            "risk_ids": list(row["risk_ids"]),
            "risk_summaries": [
                str(risks_by_id[risk_id]["summary"])
                for risk_id in row["risk_ids"]
                if risk_id in risks_by_id
            ],
            "evidence_refs": list(row["evidence_refs"]),
            "fields_complete": fields_complete,
            "missing_fields": missing_fields,
        }
        actions.append(action_row)
        completeness_rows.append(
            {
                "recommendation_id": row["recommendation_id"],
                "fields_complete": fields_complete,
                "missing_fields": missing_fields,
            }
        )
    actions.sort(key=lambda row: row["recommendation_id"])
    completeness_rows.sort(key=lambda row: row["recommendation_id"])
    return actions, completeness_rows


def _derive_req_049_project_context_evidence_refs(value: Any) -> dict[str, list[str]]:
    if value is None:
        return {}
    broad_sweep = _req052._require_mapping(value, field_name="broad_sweep_context")
    expected = {"earth_sweep_evidence_refs", "cross_project_context", "earth_sweep"}
    unexpected = sorted(set(broad_sweep.keys()) - expected)
    if unexpected:
        raise ValueError(f"broad_sweep_context has unexpected keys: {unexpected}")

    refs_by_project: dict[str, set[str]] = {}
    cross_project_rows = _mapping_sequence(
        broad_sweep.get("cross_project_context"),
        field_name="broad_sweep_context.cross_project_context",
    )
    for index, row in enumerate(cross_project_rows):
        project_id = _req052._require_nonempty_text(
            row.get("project_id"),
            field_name=f"broad_sweep_context.cross_project_context[{index}].project_id",
        )
        refs = _req052._normalize_optional_str_list(
            row.get("evidence_refs"),
            field_name=f"broad_sweep_context.cross_project_context[{index}].evidence_refs",
        )
        refs_by_project.setdefault(project_id, set()).update(refs)
    return {project_id: sorted(refs) for project_id, refs in refs_by_project.items()}


def _build_req_049_cross_project_obligations(
    *,
    recommendations: list[Mapping[str, Any]],
    context_usage: Mapping[str, Any],
    broad_sweep_context: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if broad_sweep_context is None:
        return [], []

    recommendations_by_id = {str(row["recommendation_id"]): row for row in recommendations}
    project_context_refs = _derive_req_049_project_context_evidence_refs(broad_sweep_context)
    broad_sweep = _req052._require_mapping(broad_sweep_context, field_name="broad_sweep_context")

    earth_sweep_raw = broad_sweep.get("earth_sweep")
    if earth_sweep_raw is None:
        earth_projects: list[Mapping[str, Any]] = []
    else:
        earth_sweep = _req052._require_mapping(earth_sweep_raw, field_name="broad_sweep_context.earth_sweep")
        expected_earth = {"projects"}
        unexpected_earth = sorted(set(earth_sweep.keys()) - expected_earth)
        if unexpected_earth:
            raise ValueError(f"broad_sweep_context.earth_sweep has unexpected keys: {unexpected_earth}")
        earth_projects = _mapping_sequence(
            earth_sweep.get("projects"),
            field_name="broad_sweep_context.earth_sweep.projects",
        )

    earth_refs_considered = list(context_usage["earth_sweep_evidence_refs_considered"])
    obligation_rows: dict[tuple[str, str], dict[str, Any]] = {}
    gap_open_risks: dict[str, dict[str, Any]] = {}

    for project_index, project in enumerate(earth_projects):
        project_id = _req052._require_nonempty_text(
            project.get("project_id"),
            field_name=f"broad_sweep_context.earth_sweep.projects[{project_index}].project_id",
        )
        obligations = _mapping_sequence(
            project.get("obligations"),
            field_name=f"broad_sweep_context.earth_sweep.projects[{project_index}].obligations",
        )
        project_refs = list(project_context_refs.get(project_id, []))
        for obligation_index, obligation in enumerate(obligations):
            recommendation_ids = _req052._normalize_optional_str_list(
                obligation.get("recommendation_ids"),
                field_name=(
                    "broad_sweep_context.earth_sweep.projects"
                    f"[{project_index}].obligations[{obligation_index}].recommendation_ids"
                ),
            )
            obligation_refs = _req052._normalize_optional_str_list(
                obligation.get("evidence_refs"),
                field_name=(
                    "broad_sweep_context.earth_sweep.projects"
                    f"[{project_index}].obligations[{obligation_index}].evidence_refs"
                ),
            )
            for recommendation_id in recommendation_ids:
                recommendation = recommendations_by_id.get(recommendation_id)
                if recommendation is None:
                    continue
                combined_refs = _req049._collect_unique_refs(
                    list(recommendation["evidence_refs"]),
                    project_refs,
                    obligation_refs,
                )
                earth_backed = _recommendation_has_earth_sweep_evidence(
                    evidence_refs=combined_refs,
                    earth_sweep_evidence_refs=earth_refs_considered,
                )
                if earth_backed:
                    obligation_rows[(project_id, recommendation_id)] = {
                        "project_id": project_id,
                        "recommendation_id": recommendation_id,
                        "status": "active",
                        "rationale": recommendation["rationale"],
                        "impacts": list(recommendation["impacts"]),
                        "risk_ids": list(recommendation["risk_ids"]),
                        "evidence_refs": combined_refs,
                    }
                    continue

                risk_id = f"open-risk.missing-earth-evidence.{project_id}.{recommendation_id}"
                gap_open_risks[risk_id] = {
                    "open_risk_id": risk_id,
                    "project_id": project_id,
                    "recommendation_id": recommendation_id,
                    "reason_code": "missing_earth_sweep_evidence_refs",
                    "summary": (
                        "Cross-project obligation could not be promoted because Earth-sweep evidence refs are missing."
                    ),
                    "required_evidence_refs": list(earth_refs_considered),
                    "evidence_refs": combined_refs,
                    "linked_recommendation_ids": [recommendation_id],
                }

    obligations = sorted(
        obligation_rows.values(),
        key=lambda row: (row["project_id"], row["recommendation_id"]),
    )
    return obligations, sorted(gap_open_risks.values(), key=lambda row: row["open_risk_id"])


def _build_req_049_open_risks(
    *,
    target_project_id: str,
    recommendations: list[Mapping[str, Any]],
    broad_sweep_context: Any,
    context_usage: Mapping[str, Any],
    derived_gap_open_risks: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    recommendations_by_id = {str(row["recommendation_id"]): row for row in recommendations}
    rows: dict[str, dict[str, Any]] = {}
    for row in derived_gap_open_risks:
        rows[str(row["open_risk_id"])] = dict(row)

    if broad_sweep_context is not None:
        broad_sweep = _req052._require_mapping(broad_sweep_context, field_name="broad_sweep_context")
        earth_sweep_raw = broad_sweep.get("earth_sweep")
        if earth_sweep_raw is not None:
            earth_sweep = _req052._require_mapping(earth_sweep_raw, field_name="broad_sweep_context.earth_sweep")
            projects = _mapping_sequence(
                earth_sweep.get("projects"),
                field_name="broad_sweep_context.earth_sweep.projects",
            )
            for project_index, project in enumerate(projects):
                project_id = _req052._require_nonempty_text(
                    project.get("project_id"),
                    field_name=f"broad_sweep_context.earth_sweep.projects[{project_index}].project_id",
                )
                unresolved_ideas = _mapping_sequence(
                    project.get("unresolved_ideas"),
                    field_name=f"broad_sweep_context.earth_sweep.projects[{project_index}].unresolved_ideas",
                )
                for unresolved_index, unresolved in enumerate(unresolved_ideas):
                    recommendation_ids = _req052._normalize_optional_str_list(
                        unresolved.get("recommendation_ids"),
                        field_name=(
                            "broad_sweep_context.earth_sweep.projects"
                            f"[{project_index}].unresolved_ideas[{unresolved_index}].recommendation_ids"
                        ),
                    )
                    unresolved_refs = _req052._normalize_optional_str_list(
                        unresolved.get("evidence_refs"),
                        field_name=(
                            "broad_sweep_context.earth_sweep.projects"
                            f"[{project_index}].unresolved_ideas[{unresolved_index}].evidence_refs"
                        ),
                    )
                    linked_recommendation_ids = sorted(set(recommendation_ids))
                    linked_recommendation_refs: list[list[str]] = [
                        list(recommendations_by_id[recommendation_id]["evidence_refs"])
                        for recommendation_id in linked_recommendation_ids
                        if recommendation_id in recommendations_by_id
                    ]
                    idea_value = unresolved.get("idea")
                    if idea_value is None:
                        summary = (
                            "Unresolved broad-sweep idea remains an open risk until Earth-sweep evidence is attached."
                        )
                    else:
                        summary = _req052._require_nonempty_text(
                            idea_value,
                            field_name=(
                                "broad_sweep_context.earth_sweep.projects"
                                f"[{project_index}].unresolved_ideas[{unresolved_index}].idea"
                            ),
                        )
                    recommendation_anchor = (
                        linked_recommendation_ids[0]
                        if linked_recommendation_ids
                        else f"idea.{project_id}.{unresolved_index + 1:03d}"
                    )
                    open_risk_id = f"open-risk.unresolved-idea.{project_id}.{unresolved_index + 1:03d}"
                    rows[open_risk_id] = {
                        "open_risk_id": open_risk_id,
                        "project_id": project_id,
                        "recommendation_id": recommendation_anchor,
                        "reason_code": "unresolved_idea_open_risk",
                        "summary": summary,
                        "required_evidence_refs": list(context_usage["earth_sweep_evidence_refs_considered"]),
                        "evidence_refs": _req049._collect_unique_refs(unresolved_refs, *linked_recommendation_refs),
                        "linked_recommendation_ids": linked_recommendation_ids,
                    }

    unresolved_idea_count = int(context_usage["unresolved_idea_count"])
    if unresolved_idea_count > 0 and not any(
        row["reason_code"] == "unresolved_idea_open_risk" for row in rows.values()
    ):
        rows["open-risk.unresolved-cross-project-ideas"] = {
            "open_risk_id": "open-risk.unresolved-cross-project-ideas",
            "project_id": target_project_id,
            "recommendation_id": "context.unresolved-cross-project-ideas",
            "reason_code": "unresolved_idea_open_risk",
            "summary": "Broad-sweep context reported unresolved ideas; they remain open risks.",
            "required_evidence_refs": list(context_usage["earth_sweep_evidence_refs_considered"]),
            "evidence_refs": list(context_usage["earth_sweep_evidence_refs_considered"]),
            "linked_recommendation_ids": [],
        }

    return sorted(rows.values(), key=lambda row: row["open_risk_id"])


def _collect_req_049_processing_evidence_refs(
    *,
    strategy_revision: Mapping[str, Any],
    recommendations: list[Mapping[str, Any]],
    risks: list[Mapping[str, Any]],
    context_usage: Mapping[str, Any],
    cross_project_obligations: list[Mapping[str, Any]],
    open_risks: list[Mapping[str, Any]],
) -> list[str]:
    refs: set[str] = set(context_usage["earth_sweep_evidence_refs_considered"])
    refs.update(str(ref) for ref in strategy_revision["evidence_refs"])
    for row in recommendations:
        refs.update(str(ref) for ref in row["evidence_refs"])
    for row in risks:
        refs.update(str(ref) for ref in row["evidence_refs"])
    for row in cross_project_obligations:
        refs.update(str(ref) for ref in row["evidence_refs"])
    for row in open_risks:
        refs.update(str(ref) for ref in row["required_evidence_refs"])
        refs.update(str(ref) for ref in row["evidence_refs"])
    return sorted(ref for ref in refs if ref)


def _determine_req_049_processing_decision(
    *,
    context_usage: Mapping[str, Any],
    cross_project_obligations: list[Mapping[str, Any]],
    open_risks: list[Mapping[str, Any]],
) -> tuple[str, str, str]:
    reason_codes = {str(row["reason_code"]) for row in open_risks}
    if "missing_earth_sweep_evidence_refs" in reason_codes:
        return (
            "collect-earth-evidence",
            "medium",
            "Cross-project obligations were withheld until Earth-sweep evidence refs are attached.",
        )
    if open_risks:
        return (
            "proceed-with-open-risks",
            "medium",
            "Strategy JSON output is valid, but unresolved risks remain from broad-sweep context.",
        )
    if context_usage["cross_project_context_used"] and not cross_project_obligations:
        return (
            "proceed",
            "high",
            "Cross-project context was evaluated and did not require new obligations.",
        )
    return ("proceed", "high", "Strategy JSON output is complete and context-grounded.")


def process_req_049_strategy_json_generator(payload: Mapping[str, Any]) -> dict[str, Any]:
    raw = _req049._require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_049_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_049_ANALYSIS_TYPE}")

    expected_top_keys = {
        "analysis_type",
        "now_utc",
        "target_project",
        "strategy_revision",
        "recommendations",
        "risks",
        "broad_sweep_context",
    }
    unexpected_top = sorted(set(raw.keys()) - expected_top_keys)
    if unexpected_top:
        raise ValueError(f"payload has unexpected keys: {unexpected_top}")

    generated_at_utc = _req049._require_nonempty_text(raw.get("now_utc"), field_name="now_utc")
    target_project = _req049._normalize_target_project(raw.get("target_project"))
    strategy_revision = _req049._normalize_strategy_revision(raw.get("strategy_revision"))
    recommendations = _req049._normalize_recommendations(raw.get("recommendations"))
    risks = _req049._normalize_risks(raw.get("risks"))

    known_risk_ids = {row["risk_id"] for row in risks}
    for recommendation in recommendations:
        unknown_risk_ids = sorted(set(recommendation["risk_ids"]) - known_risk_ids)
        if unknown_risk_ids:
            raise ValueError(
                "recommendations[].risk_ids must reference defined risks; "
                f"unknown ids for {recommendation['recommendation_id']}: {unknown_risk_ids}"
            )

    explicit_context_usage = _default_cross_project_context_usage()
    derived_context_usage = _derive_cross_project_context_usage_from_broad_sweep_context(
        raw.get("broad_sweep_context")
    )
    context_usage = _merge_cross_project_context_usage(explicit_context_usage, derived_context_usage)

    risks_by_id = {row["risk_id"]: row for row in risks}
    recommended_actions, completeness_rows = _build_req_049_recommended_actions(recommendations, risks_by_id)
    cross_project_obligations, derived_gap_open_risks = _build_req_049_cross_project_obligations(
        recommendations=recommendations,
        context_usage=context_usage,
        broad_sweep_context=raw.get("broad_sweep_context"),
    )
    open_risks = _build_req_049_open_risks(
        target_project_id=target_project["project_id"],
        recommendations=recommendations,
        broad_sweep_context=raw.get("broad_sweep_context"),
        context_usage=context_usage,
        derived_gap_open_risks=derived_gap_open_risks,
    )
    evidence_refs = _collect_req_049_processing_evidence_refs(
        strategy_revision=strategy_revision,
        recommendations=recommendations,
        risks=risks,
        context_usage=context_usage,
        cross_project_obligations=cross_project_obligations,
        open_risks=open_risks,
    )
    decision, confidence, rationale = _determine_req_049_processing_decision(
        context_usage=context_usage,
        cross_project_obligations=cross_project_obligations,
        open_risks=open_risks,
    )
    completeness_summary = {
        "complete_count": sum(1 for row in completeness_rows if row["fields_complete"]),
        "incomplete_count": sum(1 for row in completeness_rows if not row["fields_complete"]),
        "rows": completeness_rows,
    }

    return {
        "ok": True,
        "schema_version": REQ_049_SCHEMA_VERSION,
        "requirement_id": REQ_049_REQUIREMENT_ID,
        "analysis_type": REQ_049_ANALYSIS_TYPE,
        "call_id": REQ_049_CALL_ID,
        "artifact_kind": REQ_049_ARTIFACT_KIND,
        "generated_at_utc": generated_at_utc,
        "target_project": target_project,
        "processing_behavior": {
            "context_usage": context_usage,
            "recommendation": {
                "decision": decision,
                "rationale": rationale,
                "confidence": confidence,
                "evidence_refs": evidence_refs,
                "recommended_actions": recommended_actions,
                "recommendation_field_completeness": completeness_summary,
                "cross_project_obligations": cross_project_obligations,
                "open_risks": open_risks,
            },
        },
        "totals": {
            "recommendations": len(recommendations),
            "risks": len(risks),
            "impacts": sum(len(row["impacts"]) for row in recommendations),
            "cross_project_obligations": len(cross_project_obligations),
            "open_risks": len(open_risks),
            "processing_evidence_refs": len(evidence_refs),
        },
    }
