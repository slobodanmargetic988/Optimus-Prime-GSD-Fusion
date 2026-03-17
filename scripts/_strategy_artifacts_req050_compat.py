#!/usr/bin/env python3
"""Compatibility layer for REQ-050 broad-sweep ecosystem link map behavior."""

from __future__ import annotations

from typing import Any, Mapping

from scripts import _strategy_artifacts_req049 as _req049
from scripts import _strategy_artifacts_req052 as _req052
from scripts import _strategy_artifacts_req048_049_processing as _compat48_49


REQ_050_SCHEMA_VERSION = "req-050.ecosystem-link-map-json-generator.v1"
REQ_050_REQUIREMENT_ID = "REQ-050"
REQ_050_ANALYSIS_TYPE = "ecosystem_link_map_json_generator"
REQ_050_CALL_ID = "ecosystem-link-map-json-generator"
REQ_050_ARTIFACT_KIND = "ECOSYSTEM_LINK_MAP.json"
REQ_050_ARTIFACT_PATH = "strategy/current/ECOSYSTEM_LINK_MAP.json"
REQ_051_SCHEMA_VERSION = "req-051.strategy-changelog-md-generator.v1"
REQ_051_REQUIREMENT_ID = "REQ-051"
REQ_051_ANALYSIS_TYPE = "strategy_changelog_md_generator"
REQ_051_CALL_ID = "strategy-changelog-md-generator"
REQ_051_ARTIFACT_KIND = "STRATEGY_CHANGELOG.md"
REQ_051_ARTIFACT_PATH = "strategy/current/STRATEGY_CHANGELOG.md"
_REQ_050_PROPOSED_LINK_REQUIRED_FIELDS = (
    "link_id",
    "summary",
    "rationale",
    "peer_project_id",
    "lane",
    "source_recommendation_id",
    "confidence",
    "obligation_status",
    "evidence_refs",
)
_REQ_051_ENTRY_REQUIRED_FIELDS = (
    "recommendation_id",
    "summary",
    "delta_type",
    "change_ids",
    "strategic_direction",
    "evidence_refs",
)


def _use_req_050_compat(payload: Mapping[str, Any]) -> bool:
    return bool(payload.get("broad_sweep_context"))


def _build_req_050_proposed_links(
    *,
    target_project_id: str,
    synthesis: Mapping[str, Any],
    context_usage: Mapping[str, Any],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, list[str]],
]:
    packet_inputs = {str(row["packet_input_id"]): row for row in synthesis["strategy_packet_inputs"]}
    earth_refs_considered = list(context_usage["earth_sweep_evidence_refs_considered"])
    proposed_links: list[dict[str, Any]] = []
    cross_project_obligations: list[dict[str, Any]] = []
    missing_links: list[dict[str, Any]] = []
    missing_evidence_open_risks: list[dict[str, Any]] = []
    recommendation_refs: dict[str, list[str]] = {}
    for row in synthesis["final_recommendations"]:
        if row["packet_kind"] != "cross-project":
            continue
        packet_input = packet_inputs.get(str(row["strategy_packet_input_id"]))
        packet_refs = list(packet_input["evidence_refs"]) if packet_input is not None else []
        combined_refs = _req049._collect_unique_refs(list(row["evidence_refs"]), packet_refs)
        recommendation_id = str(row["recommendation_id"])
        recommendation_refs[recommendation_id] = list(combined_refs)
        earth_backed = _compat48_49._recommendation_has_earth_sweep_evidence(
            evidence_refs=combined_refs,
            earth_sweep_evidence_refs=earth_refs_considered,
        )
        confidence = "low"
        if earth_backed and int(row["supporting_call_count"]) >= 2:
            confidence = "high"
        elif earth_backed:
            confidence = "medium"
        link_id = f"link.{target_project_id}.{row['peer_project_id']}.{recommendation_id}"
        proposed_row = {
            "link_id": link_id,
            "target_project_id": target_project_id,
            "peer_project_id": row["peer_project_id"],
            "lane": row["lane"],
            "summary": row["summary"],
            "rationale": row["rationale"],
            "source_recommendation_id": recommendation_id,
            "strategy_packet_input_id": row["strategy_packet_input_id"],
            "sequence_hint": int(row["sequence_hint"]),
            "confidence": confidence,
            "obligation_status": "active" if earth_backed else "withheld",
            "evidence_refs": combined_refs,
            "obligation_metadata": {
                "earth_sweep_evidence_backed": earth_backed,
                "required_earth_sweep_evidence_refs": list(earth_refs_considered),
                "supporting_call_count": int(row["supporting_call_count"]),
                "contributing_call_ids": list(row["contributing_call_ids"]),
            },
        }
        proposed_links.append(proposed_row)
        if earth_backed:
            cross_project_obligations.append(
                {
                    "project_id": row["peer_project_id"],
                    "lane": row["lane"],
                    "recommendation_id": recommendation_id,
                    "link_id": link_id,
                    "status": "active",
                    "confidence": confidence,
                    "evidence_refs": combined_refs,
                    "obligation_metadata": dict(proposed_row["obligation_metadata"]),
                }
            )
            continue
        missing_links.append(
            {
                "link_id": link_id,
                "target_project_id": target_project_id,
                "peer_project_id": row["peer_project_id"],
                "lane": row["lane"],
                "source_recommendation_id": recommendation_id,
                "reason_code": "missing_earth_sweep_evidence_refs",
                "summary": "Cross-project link remains missing because Earth-sweep evidence refs were not provided.",
                "confidence": "low",
                "required_evidence_refs": list(earth_refs_considered),
                "evidence_refs": combined_refs,
                "obligation_metadata": {
                    "status": "withheld",
                    "required_earth_sweep_evidence_refs": list(earth_refs_considered),
                },
            }
        )
        missing_evidence_open_risks.append(
            {
                "open_risk_id": f"open-risk.missing-earth-evidence.{recommendation_id}",
                "project_id": row["peer_project_id"],
                "recommendation_id": recommendation_id,
                "reason_code": "missing_earth_sweep_evidence_refs",
                "summary": "Cross-project link cannot be activated without Earth-sweep evidence refs.",
                "required_evidence_refs": list(earth_refs_considered),
                "evidence_refs": combined_refs,
                "linked_recommendation_ids": [recommendation_id],
            }
        )

    proposed_links.sort(
        key=lambda row: (
            row["peer_project_id"],
            row["lane"],
            row["sequence_hint"],
            row["source_recommendation_id"],
        )
    )
    cross_project_obligations.sort(key=lambda row: (row["project_id"], row["lane"], row["recommendation_id"]))
    missing_links.sort(key=lambda row: (row["peer_project_id"], row["lane"], row["source_recommendation_id"]))
    missing_evidence_open_risks.sort(key=lambda row: row["open_risk_id"])
    return (
        proposed_links,
        cross_project_obligations,
        missing_links,
        missing_evidence_open_risks,
        recommendation_refs,
    )


def _build_req_050_current_links_from_broad_sweep(
    *,
    target_project_id: str,
    broad_sweep_context: Any,
    proposed_links: list[Mapping[str, Any]],
    context_usage: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if broad_sweep_context is None:
        return []
    broad_sweep = _req052._require_mapping(broad_sweep_context, field_name="broad_sweep_context")
    earth_sweep_raw = broad_sweep.get("earth_sweep")
    if earth_sweep_raw is None:
        return []

    earth_sweep = _req052._require_mapping(earth_sweep_raw, field_name="broad_sweep_context.earth_sweep")
    earth_projects = _compat48_49._mapping_sequence(
        earth_sweep.get("projects"),
        field_name="broad_sweep_context.earth_sweep.projects",
    )
    proposed_by_recommendation_id = {str(row["source_recommendation_id"]): row for row in proposed_links}
    current_rows: dict[str, dict[str, Any]] = {}
    earth_refs_considered = list(context_usage["earth_sweep_evidence_refs_considered"])
    for project_index, project in enumerate(earth_projects):
        project_id = _req052._require_nonempty_text(
            project.get("project_id"),
            field_name=f"broad_sweep_context.earth_sweep.projects[{project_index}].project_id",
        )
        obligations = _compat48_49._mapping_sequence(
            project.get("obligations"),
            field_name=f"broad_sweep_context.earth_sweep.projects[{project_index}].obligations",
        )
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
            summary_raw = obligation.get("summary")
            obligation_summary = (
                "Earth-sweep obligation confirms this ecosystem link."
                if summary_raw is None
                else _req052._require_nonempty_text(
                    summary_raw,
                    field_name=(
                        "broad_sweep_context.earth_sweep.projects"
                        f"[{project_index}].obligations[{obligation_index}].summary"
                    ),
                )
            )
            for recommendation_id in recommendation_ids:
                proposed = proposed_by_recommendation_id.get(recommendation_id)
                if proposed is None or str(proposed["obligation_status"]) != "active":
                    continue
                link_id = str(proposed["link_id"])
                combined_refs = _req049._collect_unique_refs(list(proposed["evidence_refs"]), obligation_refs)
                current_rows[link_id] = {
                    "link_id": link_id,
                    "target_project_id": target_project_id,
                    "peer_project_id": project_id,
                    "lane": proposed["lane"],
                    "source_recommendation_id": recommendation_id,
                    "summary": proposed["summary"],
                    "confidence": proposed["confidence"],
                    "status": "current",
                    "evidence_refs": combined_refs,
                    "obligation_metadata": {
                        "obligation_summary": obligation_summary,
                        "earth_sweep_evidence_refs_considered": list(earth_refs_considered),
                        "obligation_evidence_refs": obligation_refs,
                    },
                }
    return sorted(
        current_rows.values(),
        key=lambda row: (row["peer_project_id"], row["lane"], row["source_recommendation_id"]),
    )


def _build_req_050_unresolved_idea_rows(
    *,
    target_project_id: str,
    broad_sweep_context: Any,
    context_usage: Mapping[str, Any],
    recommendation_refs: Mapping[str, list[str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if broad_sweep_context is None:
        return [], []
    broad_sweep = _req052._require_mapping(broad_sweep_context, field_name="broad_sweep_context")
    earth_sweep_raw = broad_sweep.get("earth_sweep")
    if earth_sweep_raw is None:
        return [], []
    earth_sweep = _req052._require_mapping(earth_sweep_raw, field_name="broad_sweep_context.earth_sweep")
    earth_projects = _compat48_49._mapping_sequence(
        earth_sweep.get("projects"),
        field_name="broad_sweep_context.earth_sweep.projects",
    )
    earth_refs_considered = list(context_usage["earth_sweep_evidence_refs_considered"])
    missing_links: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    for project_index, project in enumerate(earth_projects):
        project_id = _req052._require_nonempty_text(
            project.get("project_id"),
            field_name=f"broad_sweep_context.earth_sweep.projects[{project_index}].project_id",
        )
        unresolved_ideas = _compat48_49._mapping_sequence(
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
            idea_raw = unresolved.get("idea")
            summary = (
                "Unresolved cross-project idea remains open and must stay in the risk ledger."
                if idea_raw is None
                else _req052._require_nonempty_text(
                    idea_raw,
                    field_name=(
                        "broad_sweep_context.earth_sweep.projects"
                        f"[{project_index}].unresolved_ideas[{unresolved_index}].idea"
                    ),
                )
            )
            linked_refs = [
                list(recommendation_refs[recommendation_id])
                for recommendation_id in recommendation_ids
                if recommendation_id in recommendation_refs
            ]
            combined_refs = _req049._collect_unique_refs(unresolved_refs, *linked_refs)
            recommendation_anchor = recommendation_ids[0] if recommendation_ids else f"idea.{project_id}.{unresolved_index + 1:03d}"
            open_risk_id = f"open-risk.unresolved-idea.{project_id}.{unresolved_index + 1:03d}"
            open_risks.append(
                {
                    "open_risk_id": open_risk_id,
                    "project_id": project_id,
                    "recommendation_id": recommendation_anchor,
                    "reason_code": "unresolved_idea_open_risk",
                    "summary": summary,
                    "required_evidence_refs": list(earth_refs_considered),
                    "evidence_refs": combined_refs,
                    "linked_recommendation_ids": list(recommendation_ids),
                }
            )
            missing_links.append(
                {
                    "link_id": f"link-missing.{target_project_id}.{project_id}.idea.{unresolved_index + 1:03d}",
                    "target_project_id": target_project_id,
                    "peer_project_id": project_id,
                    "lane": "discovery",
                    "source_recommendation_id": recommendation_anchor,
                    "reason_code": "unresolved_idea_open_risk",
                    "summary": summary,
                    "confidence": "low",
                    "required_evidence_refs": list(earth_refs_considered),
                    "evidence_refs": combined_refs,
                    "obligation_metadata": {
                        "status": "open-risk",
                        "linked_recommendation_ids": list(recommendation_ids),
                    },
                }
            )
    missing_links.sort(key=lambda row: (row["peer_project_id"], row["link_id"]))
    open_risks.sort(key=lambda row: row["open_risk_id"])
    return missing_links, open_risks


def _build_req_050_synthesis_open_risks(synthesis: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in synthesis["open_risks"]:
        rows.append(
            {
                "open_risk_id": row["open_risk_id"],
                "project_id": row["project_id"],
                "recommendation_id": row["recommendation_id"],
                "reason_code": row["reason_code"],
                "summary": row["summary"],
                "required_evidence_refs": list(row["required_evidence_refs"]),
                "evidence_refs": list(row["evidence_refs"]),
                "linked_recommendation_ids": list(row["linked_recommendation_ids"]),
            }
        )
    return sorted(rows, key=lambda row: row["open_risk_id"])


def _merge_req_050_open_risks(*groups: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for group in groups:
        for row in group:
            rows[str(row["open_risk_id"])] = dict(row)
    return sorted(rows.values(), key=lambda row: row["open_risk_id"])


def _build_req_050_recommended_actions(
    proposed_links: list[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    actions: list[dict[str, Any]] = []
    completeness_rows: list[dict[str, Any]] = []
    for row in proposed_links:
        missing_fields: list[str] = []
        for field_name in _REQ_050_PROPOSED_LINK_REQUIRED_FIELDS:
            value = row.get(field_name)
            if field_name == "evidence_refs":
                if not isinstance(value, list) or not value:
                    missing_fields.append(field_name)
                continue
            if not isinstance(value, str) or not value.strip():
                missing_fields.append(field_name)
        fields_complete = not missing_fields
        actions.append(
            {
                "link_id": row["link_id"],
                "summary": row["summary"],
                "rationale": row["rationale"],
                "peer_project_id": row["peer_project_id"],
                "lane": row["lane"],
                "source_recommendation_id": row["source_recommendation_id"],
                "confidence": row["confidence"],
                "obligation_status": row["obligation_status"],
                "evidence_refs": list(row["evidence_refs"]),
                "fields_complete": fields_complete,
                "missing_fields": missing_fields,
            }
        )
        completeness_rows.append(
            {
                "link_id": row["link_id"],
                "source_recommendation_id": row["source_recommendation_id"],
                "fields_complete": fields_complete,
                "missing_fields": missing_fields,
            }
        )
    actions.sort(key=lambda row: (row["peer_project_id"], row["lane"], row["source_recommendation_id"]))
    completeness_rows.sort(key=lambda row: row["link_id"])
    return actions, completeness_rows


def _collect_req_050_processing_evidence_refs(
    *,
    context_usage: Mapping[str, Any],
    current_links: list[Mapping[str, Any]],
    missing_links: list[Mapping[str, Any]],
    proposed_links: list[Mapping[str, Any]],
    open_risks: list[Mapping[str, Any]],
) -> list[str]:
    refs: set[str] = set(context_usage["earth_sweep_evidence_refs_considered"])
    for row in current_links:
        refs.update(str(ref) for ref in row["evidence_refs"])
    for row in missing_links:
        refs.update(str(ref) for ref in row["required_evidence_refs"])
        refs.update(str(ref) for ref in row["evidence_refs"])
    for row in proposed_links:
        refs.update(str(ref) for ref in row["evidence_refs"])
    for row in open_risks:
        refs.update(str(ref) for ref in row["required_evidence_refs"])
        refs.update(str(ref) for ref in row["evidence_refs"])
    return sorted(ref for ref in refs if ref)


def _determine_req_050_processing_decision(
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
            "Cross-project link obligations were withheld until Earth-sweep evidence refs are attached.",
        )
    if open_risks:
        return (
            "proceed-with-open-risks",
            "medium",
            "Ecosystem link map generation is valid, but unresolved ideas remain as open risks.",
        )
    if context_usage["cross_project_context_used"] and not cross_project_obligations:
        return (
            "proceed",
            "high",
            "Cross-project context was consumed and did not produce active obligations.",
        )
    return ("proceed", "high", "Ecosystem link map generation is complete and context-grounded.")


def _compute_req_050_ecosystem_link_map(payload: Mapping[str, Any]) -> dict[str, Any]:
    raw = _req052._require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_050_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_050_ANALYSIS_TYPE}")

    generated_at_utc = _req052._require_nonempty_text(raw.get("now_utc"), field_name="now_utc")
    target_project = _req052._normalize_target_project(raw.get("target_project"))
    synthesis = _req052._normalize_final_strategy_synthesis(raw.get("final_strategy_synthesis"))
    explicit_context_usage = dict(synthesis["cross_project_context_usage"])
    derived_context_usage = _compat48_49._derive_cross_project_context_usage_from_broad_sweep_context(
        raw.get("broad_sweep_context")
    )
    context_usage = _compat48_49._merge_cross_project_context_usage(explicit_context_usage, derived_context_usage)

    (
        proposed_links,
        cross_project_obligations,
        missing_links_from_recommendations,
        missing_evidence_open_risks,
        recommendation_refs,
    ) = _build_req_050_proposed_links(
        target_project_id=target_project["project_id"],
        synthesis=synthesis,
        context_usage=context_usage,
    )
    current_links = _build_req_050_current_links_from_broad_sweep(
        target_project_id=target_project["project_id"],
        broad_sweep_context=raw.get("broad_sweep_context"),
        proposed_links=proposed_links,
        context_usage=context_usage,
    )
    missing_links_from_unresolved_ideas, unresolved_idea_open_risks = _build_req_050_unresolved_idea_rows(
        target_project_id=target_project["project_id"],
        broad_sweep_context=raw.get("broad_sweep_context"),
        context_usage=context_usage,
        recommendation_refs=recommendation_refs,
    )
    missing_links = sorted(
        [*missing_links_from_recommendations, *missing_links_from_unresolved_ideas],
        key=lambda row: (row["peer_project_id"], row["lane"], row["source_recommendation_id"], row["reason_code"]),
    )
    synthesis_open_risks = _build_req_050_synthesis_open_risks(synthesis)
    open_risks = _merge_req_050_open_risks(
        synthesis_open_risks,
        missing_evidence_open_risks,
        unresolved_idea_open_risks,
    )
    recommended_actions, completeness_rows = _build_req_050_recommended_actions(proposed_links)
    evidence_refs = _collect_req_050_processing_evidence_refs(
        context_usage=context_usage,
        current_links=current_links,
        missing_links=missing_links,
        proposed_links=proposed_links,
        open_risks=open_risks,
    )
    decision, confidence, rationale = _determine_req_050_processing_decision(
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
        "generated_at_utc": generated_at_utc,
        "target_project": target_project,
        "context_usage": context_usage,
        "recommended_actions": recommended_actions,
        "recommendation_field_completeness": completeness_summary,
        "current_links": current_links,
        "missing_links": missing_links,
        "proposed_links": proposed_links,
        "cross_project_obligations": cross_project_obligations,
        "open_risks": open_risks,
        "decision": decision,
        "confidence": confidence,
        "rationale": rationale,
        "evidence_refs": evidence_refs,
        "totals": {
            "final_recommendations": len(synthesis["final_recommendations"]),
            "cross_project_recommendations": sum(
                1 for row in synthesis["final_recommendations"] if row["packet_kind"] == "cross-project"
            ),
            "current_links": len(current_links),
            "missing_links": len(missing_links),
            "proposed_links": len(proposed_links),
            "cross_project_obligations": len(cross_project_obligations),
            "open_risks": len(open_risks),
            "processing_evidence_refs": len(evidence_refs),
        },
    }


def process_req_050_ecosystem_link_map_json_generator(payload: Mapping[str, Any]) -> dict[str, Any]:
    computed = _compute_req_050_ecosystem_link_map(payload)
    return {
        "ok": True,
        "schema_version": REQ_050_SCHEMA_VERSION,
        "requirement_id": REQ_050_REQUIREMENT_ID,
        "analysis_type": REQ_050_ANALYSIS_TYPE,
        "call_id": REQ_050_CALL_ID,
        "artifact_kind": REQ_050_ARTIFACT_KIND,
        "generated_at_utc": computed["generated_at_utc"],
        "target_project": computed["target_project"],
        "processing_behavior": {
            "context_usage": computed["context_usage"],
            "recommendation": {
                "decision": computed["decision"],
                "rationale": computed["rationale"],
                "confidence": computed["confidence"],
                "evidence_refs": computed["evidence_refs"],
                "recommended_actions": computed["recommended_actions"],
                "recommendation_field_completeness": computed["recommendation_field_completeness"],
                "current_links": computed["current_links"],
                "missing_links": computed["missing_links"],
                "proposed_links": computed["proposed_links"],
                "cross_project_obligations": computed["cross_project_obligations"],
                "open_risks": computed["open_risks"],
            },
        },
        "totals": dict(computed["totals"]),
    }


def build_req_050_ecosystem_link_map_json_generator(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not _use_req_050_compat(payload):
        return _req052.build_req_050_ecosystem_link_map_json_generator(payload)
    computed = _compute_req_050_ecosystem_link_map(payload)
    missing_obligation_count = sum(
        1 for row in computed["missing_links"] if row["reason_code"] == "missing_earth_sweep_evidence_refs"
    )
    return {
        "ok": True,
        "schema_version": REQ_050_SCHEMA_VERSION,
        "requirement_id": REQ_050_REQUIREMENT_ID,
        "analysis_type": REQ_050_ANALYSIS_TYPE,
        "call_id": REQ_050_CALL_ID,
        "artifact_kind": REQ_050_ARTIFACT_KIND,
        "generated_at_utc": computed["generated_at_utc"],
        "target_project": computed["target_project"],
        "ecosystem_link_map": {
            "artifact_path": REQ_050_ARTIFACT_PATH,
            "current_links": computed["current_links"],
            "missing_links": computed["missing_links"],
            "proposed_links": computed["proposed_links"],
            "confidence": {
                "overall": computed["confidence"],
                "rationale": computed["rationale"],
            },
            "obligation_metadata": {
                "cross_project_obligations": len(computed["cross_project_obligations"]),
                "withheld_obligations": missing_obligation_count,
                "projects_considered": list(computed["context_usage"]["projects_considered"]),
                "earth_sweep_evidence_refs_considered": list(
                    computed["context_usage"]["earth_sweep_evidence_refs_considered"]
                ),
            },
            "open_risks": computed["open_risks"],
            "evidence_refs": computed["evidence_refs"],
        },
        "totals": {
            "current_links": len(computed["current_links"]),
            "missing_links": len(computed["missing_links"]),
            "proposed_links": len(computed["proposed_links"]),
            "cross_project_obligations": len(computed["cross_project_obligations"]),
            "open_risks": len(computed["open_risks"]),
            "evidence_refs": len(computed["evidence_refs"]),
        },
    }


def validate_req_050_ecosystem_link_map_json_generator(payload: Mapping[str, Any]) -> list[str]:
    if payload.get("artifact_kind") != REQ_050_ARTIFACT_KIND:
        return _req052.validate_req_050_ecosystem_link_map_json_generator(payload)
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]
    errors: list[str] = []
    link_map = payload.get("ecosystem_link_map")
    totals = payload.get("totals")
    if payload.get("analysis_type") != REQ_050_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_050_ANALYSIS_TYPE}")
    if not isinstance(link_map, Mapping):
        errors.append("ecosystem_link_map must be an object")
        return errors
    expected_map_keys = {
        "artifact_path",
        "current_links",
        "missing_links",
        "proposed_links",
        "confidence",
        "obligation_metadata",
        "open_risks",
        "evidence_refs",
    }
    missing_map = sorted(expected_map_keys - set(link_map.keys()))
    if missing_map:
        errors.append(f"ecosystem_link_map missing keys: {missing_map}")
    if link_map.get("artifact_path") != REQ_050_ARTIFACT_PATH:
        errors.append(f"ecosystem_link_map.artifact_path must be {REQ_050_ARTIFACT_PATH}")
    for key in ("current_links", "missing_links", "proposed_links", "open_risks", "evidence_refs"):
        if not isinstance(link_map.get(key), list):
            errors.append(f"ecosystem_link_map.{key} must be a list")
    if not isinstance(link_map.get("confidence"), Mapping):
        errors.append("ecosystem_link_map.confidence must be an object")
    if not isinstance(link_map.get("obligation_metadata"), Mapping):
        errors.append("ecosystem_link_map.obligation_metadata must be an object")
    if isinstance(totals, Mapping):
        expected = {
            "current_links": len(link_map.get("current_links", [])) if isinstance(link_map.get("current_links"), list) else None,
            "missing_links": len(link_map.get("missing_links", [])) if isinstance(link_map.get("missing_links"), list) else None,
            "proposed_links": len(link_map.get("proposed_links", [])) if isinstance(link_map.get("proposed_links"), list) else None,
            "open_risks": len(link_map.get("open_risks", [])) if isinstance(link_map.get("open_risks"), list) else None,
            "evidence_refs": len(link_map.get("evidence_refs", [])) if isinstance(link_map.get("evidence_refs"), list) else None,
        }
        for key, expected_value in expected.items():
            if expected_value is None:
                continue
            if totals.get(key) != expected_value:
                errors.append(f"totals.{key} must match ecosystem_link_map.{key} length")
    else:
        errors.append("totals must be an object")
    return errors


def _stable_req_051_id(prefix: str, *parts: str) -> str:
    raw = _req050_compat_json([prefix, *parts])
    return f"{prefix}.{_req052.hashlib.sha256(raw.encode('utf-8')).hexdigest()[:12]}"


def _req050_compat_json(value: Any) -> str:
    return _req052.json.dumps(value, sort_keys=False, separators=(",", ":"), ensure_ascii=False)


def _normalize_req_051_revision_pair(value: Any) -> dict[str, str]:
    row = _req052._require_mapping(value, field_name="revision_pair")
    expected = {"previous_revision_id", "current_revision_id"}
    unexpected = sorted(set(row.keys()) - expected)
    if unexpected:
        raise ValueError(f"revision_pair has unexpected keys: {unexpected}")
    return {
        "previous_revision_id": _req052._require_nonempty_text(
            row.get("previous_revision_id"),
            field_name="revision_pair.previous_revision_id",
        ),
        "current_revision_id": _req052._require_nonempty_text(
            row.get("current_revision_id"),
            field_name="revision_pair.current_revision_id",
        ),
    }


def _normalize_req_051_change_summary(value: Any) -> dict[str, Any]:
    row = _req052._require_mapping(value, field_name="change_summary")
    expected = {"total_change_count", "changed_sections", "change_ids"}
    unexpected = sorted(set(row.keys()) - expected)
    if unexpected:
        raise ValueError(f"change_summary has unexpected keys: {unexpected}")
    change_ids = _req052._normalize_optional_str_list(row.get("change_ids"), field_name="change_summary.change_ids")
    total_change_count = _req052._normalize_non_negative_int(
        row.get("total_change_count"),
        field_name="change_summary.total_change_count",
    )
    if total_change_count != len(change_ids):
        raise ValueError("change_summary.total_change_count must equal len(change_summary.change_ids)")
    return {
        "total_change_count": total_change_count,
        "changed_sections": _req052._normalize_optional_str_list(
            row.get("changed_sections"),
            field_name="change_summary.changed_sections",
        ),
        "change_ids": change_ids,
    }


def _normalize_req_051_recommendation_delta(value: Any, *, field_name: str) -> dict[str, Any]:
    row = _req052._require_mapping(value, field_name=field_name)
    expected = {
        "recommendation_id",
        "summary",
        "anchors",
        "change_ids",
        "delta_type",
        "evidence_refs",
        "linked_context_project_ids",
    }
    unexpected = sorted(set(row.keys()) - expected)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {unexpected}")
    return {
        "recommendation_id": _req052._require_nonempty_text(
            row.get("recommendation_id"),
            field_name=f"{field_name}.recommendation_id",
        ),
        "summary": _req052._require_nonempty_text(row.get("summary"), field_name=f"{field_name}.summary"),
        "anchors": _req052._normalize_nonempty_str_list(row.get("anchors"), field_name=f"{field_name}.anchors"),
        "change_ids": _req052._normalize_nonempty_str_list(row.get("change_ids"), field_name=f"{field_name}.change_ids"),
        "delta_type": _req052._require_nonempty_text(row.get("delta_type"), field_name=f"{field_name}.delta_type"),
        "evidence_refs": _req052._normalize_nonempty_str_list(
            row.get("evidence_refs"),
            field_name=f"{field_name}.evidence_refs",
        ),
        "linked_context_project_ids": _req052._normalize_optional_str_list(
            row.get("linked_context_project_ids"),
            field_name=f"{field_name}.linked_context_project_ids",
        ),
    }


def _normalize_req_051_recommendation_deltas(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError("recommendation_deltas must be a non-empty list")
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(value):
        normalized = _normalize_req_051_recommendation_delta(row, field_name=f"recommendation_deltas[{index}]")
        recommendation_id = normalized["recommendation_id"]
        if recommendation_id in seen_ids:
            raise ValueError("recommendation_deltas[].recommendation_id must be unique")
        seen_ids.add(recommendation_id)
        rows.append(normalized)
    return sorted(rows, key=lambda row: (row["recommendation_id"], row["delta_type"]))


def _summarize_req_051_direction(
    *,
    final_recommendation: Mapping[str, Any] | None,
    deferred_recommendation: Mapping[str, Any] | None,
    linked_open_risks: list[Mapping[str, Any]],
    proposed_link: Mapping[str, Any] | None,
) -> tuple[str, str, str, str, str, str, str]:
    if final_recommendation is not None:
        packet_kind = str(final_recommendation["packet_kind"])
        peer_project_id = str(final_recommendation["peer_project_id"])
        lane = str(final_recommendation["lane"])
        strategy_packet_input_id = str(final_recommendation["strategy_packet_input_id"])
        if packet_kind == "cross-project":
            obligation_status = (
                str(proposed_link["obligation_status"])
                if proposed_link is not None
                else (
                    "withheld"
                    if any(row["reason_code"] == "missing_earth_sweep_evidence_refs" for row in linked_open_risks)
                    else "active"
                )
            )
            direction = f"Coordinate `{peer_project_id}` through the `{lane}` lane."
            return ("final", obligation_status, direction, packet_kind, peer_project_id, lane, strategy_packet_input_id)
        return (
            "final",
            "active",
            f"Advance the target-project `{lane}` lane.",
            packet_kind,
            peer_project_id,
            lane,
            strategy_packet_input_id,
        )
    if deferred_recommendation is not None:
        peer_candidates = list(deferred_recommendation["peer_project_candidates"])
        packet_candidates = list(deferred_recommendation["packet_kind_candidates"])
        packet_kind = packet_candidates[0] if packet_candidates else ""
        peer_project_id = peer_candidates[0] if peer_candidates else ""
        return (
            "deferred",
            "deferred",
            "Hold this direction until routing and evidence constraints are resolved.",
            packet_kind,
            peer_project_id,
            "",
            "",
        )
    if linked_open_risks:
        return (
            "risk-only",
            "open-risk",
            "Keep this delta open as a tracked risk until evidence-backed direction is available.",
            "",
            "",
            "",
            "",
        )
    return (
        "delta-only",
        "observed",
        "Record the revision delta without promoting a new strategic direction yet.",
        "",
        "",
        "",
        "",
    )


def _build_req_051_changelog_entries(
    *,
    revision_pair: Mapping[str, str],
    synthesis: Mapping[str, Any],
    recommendation_deltas: list[Mapping[str, Any]],
    proposed_links: list[Mapping[str, Any]],
    open_risks: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    final_by_id = {str(row["recommendation_id"]): row for row in synthesis["final_recommendations"]}
    deferred_by_id = {str(row["recommendation_id"]): row for row in synthesis["deferred_recommendations"]}
    packet_by_id = {str(row["packet_input_id"]): row for row in synthesis["strategy_packet_inputs"]}
    proposed_link_by_recommendation_id = {str(row["source_recommendation_id"]): row for row in proposed_links}
    open_risks_by_recommendation_id: dict[str, list[Mapping[str, Any]]] = {}
    for row in open_risks:
        recommendation_ids = {str(row["recommendation_id"])}
        recommendation_ids.update(str(rec_id) for rec_id in row["linked_recommendation_ids"])
        for recommendation_id in recommendation_ids:
            open_risks_by_recommendation_id.setdefault(recommendation_id, []).append(row)

    changelog_entries: list[dict[str, Any]] = []
    for delta in recommendation_deltas:
        recommendation_id = str(delta["recommendation_id"])
        final_recommendation = final_by_id.get(recommendation_id)
        deferred_recommendation = deferred_by_id.get(recommendation_id)
        linked_open_risks = sorted(
            open_risks_by_recommendation_id.get(recommendation_id, []),
            key=lambda row: str(row["open_risk_id"]),
        )
        proposed_link = proposed_link_by_recommendation_id.get(recommendation_id)
        (
            recommendation_status,
            direction_status,
            strategic_direction,
            packet_kind,
            peer_project_id,
            lane,
            strategy_packet_input_id,
        ) = _summarize_req_051_direction(
            final_recommendation=final_recommendation,
            deferred_recommendation=deferred_recommendation,
            linked_open_risks=linked_open_risks,
            proposed_link=proposed_link,
        )
        packet_evidence_refs: list[str] = []
        if strategy_packet_input_id:
            packet = packet_by_id.get(strategy_packet_input_id)
            if packet is not None:
                packet_evidence_refs = list(packet["evidence_refs"])

        final_evidence_refs = list(final_recommendation["evidence_refs"]) if final_recommendation is not None else []
        deferred_evidence_refs = list(deferred_recommendation["evidence_refs"]) if deferred_recommendation is not None else []
        risk_refs = [list(row["evidence_refs"]) for row in linked_open_risks]
        risk_required_refs = [list(row["required_evidence_refs"]) for row in linked_open_risks]
        linked_context_project_ids = set(str(project_id) for project_id in delta["linked_context_project_ids"])
        if peer_project_id:
            linked_context_project_ids.add(peer_project_id)
        for row in linked_open_risks:
            project_id = str(row["project_id"])
            if project_id:
                linked_context_project_ids.add(project_id)

        entry_id = _stable_req_051_id("chglog", revision_pair["current_revision_id"], recommendation_id)
        summary = (
            str(final_recommendation["summary"])
            if final_recommendation is not None
            else (
                str(deferred_recommendation["summary"])
                if deferred_recommendation is not None
                else str(delta["summary"])
            )
        )
        changelog_entries.append(
            {
                "entry_id": entry_id,
                "recommendation_id": recommendation_id,
                "summary": summary,
                "delta_type": str(delta["delta_type"]),
                "change_ids": list(delta["change_ids"]),
                "anchors": list(delta["anchors"]),
                "recommendation_status": recommendation_status,
                "strategic_direction": strategic_direction,
                "direction_status": direction_status,
                "packet_kind": packet_kind,
                "peer_project_id": peer_project_id,
                "lane": lane,
                "strategy_packet_input_id": strategy_packet_input_id,
                "linked_context_project_ids": sorted(linked_context_project_ids),
                "linked_open_risk_ids": sorted(str(row["open_risk_id"]) for row in linked_open_risks),
                "evidence_refs": _req049._collect_unique_refs(
                    list(delta["evidence_refs"]),
                    final_evidence_refs,
                    deferred_evidence_refs,
                    packet_evidence_refs,
                    *risk_refs,
                    *risk_required_refs,
                ),
            }
        )

    changelog_entries.sort(
        key=lambda row: (
            row["packet_kind"] != "cross-project",
            row["peer_project_id"],
            row["recommendation_status"],
            row["recommendation_id"],
        )
    )
    return changelog_entries


def _build_req_051_strategic_direction_changes(
    changelog_entries: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in changelog_entries:
        direction_change_id = _stable_req_051_id(
            "direction",
            str(entry["entry_id"]),
            str(entry["direction_status"]),
        )
        rows.append(
            {
                "direction_change_id": direction_change_id,
                "linked_entry_id": str(entry["entry_id"]),
                "recommendation_id": str(entry["recommendation_id"]),
                "direction_status": str(entry["direction_status"]),
                "strategic_direction": str(entry["strategic_direction"]),
                "packet_kind": str(entry["packet_kind"]),
                "peer_project_id": str(entry["peer_project_id"]),
                "lane": str(entry["lane"]),
                "change_ids": list(entry["change_ids"]),
                "linked_context_project_ids": list(entry["linked_context_project_ids"]),
                "evidence_refs": list(entry["evidence_refs"]),
            }
        )
    rows.sort(key=lambda row: (row["direction_status"], row["peer_project_id"], row["recommendation_id"]))
    return rows


def _build_req_051_recommended_actions(
    changelog_entries: list[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    actions: list[dict[str, Any]] = []
    completeness_rows: list[dict[str, Any]] = []
    for row in changelog_entries:
        missing_fields: list[str] = []
        for field_name in _REQ_051_ENTRY_REQUIRED_FIELDS:
            value = row.get(field_name)
            if field_name in {"recommendation_id", "summary", "delta_type", "strategic_direction"}:
                if not isinstance(value, str) or not value.strip():
                    missing_fields.append(field_name)
                continue
            if not isinstance(value, list) or not value:
                missing_fields.append(field_name)
        fields_complete = not missing_fields
        actions.append(
            {
                "entry_id": row["entry_id"],
                "recommendation_id": row["recommendation_id"],
                "summary": row["summary"],
                "delta_type": row["delta_type"],
                "recommendation_status": row["recommendation_status"],
                "direction_status": row["direction_status"],
                "strategic_direction": row["strategic_direction"],
                "linked_context_project_ids": list(row["linked_context_project_ids"]),
                "evidence_refs": list(row["evidence_refs"]),
                "fields_complete": fields_complete,
                "missing_fields": missing_fields,
            }
        )
        completeness_rows.append(
            {
                "recommendation_id": row["recommendation_id"],
                "entry_id": row["entry_id"],
                "fields_complete": fields_complete,
                "missing_fields": missing_fields,
            }
        )
    actions.sort(key=lambda row: (row["recommendation_id"], row["entry_id"]))
    completeness_rows.sort(key=lambda row: (row["recommendation_id"], row["entry_id"]))
    return actions, completeness_rows


def _build_req_051_recommendation_refs(
    *,
    synthesis: Mapping[str, Any],
    recommendation_deltas: list[Mapping[str, Any]],
    proposed_recommendation_refs: Mapping[str, list[str]],
) -> dict[str, list[str]]:
    packet_by_id = {str(row["packet_input_id"]): row for row in synthesis["strategy_packet_inputs"]}
    refs_by_recommendation_id: dict[str, list[str]] = {
        str(recommendation_id): list(refs)
        for recommendation_id, refs in proposed_recommendation_refs.items()
    }

    def add_refs(recommendation_id: str, *groups: list[str]) -> None:
        refs_by_recommendation_id[recommendation_id] = _req049._collect_unique_refs(
            refs_by_recommendation_id.get(recommendation_id, []),
            *groups,
        )

    for row in synthesis["final_recommendations"]:
        recommendation_id = str(row["recommendation_id"])
        packet_input = packet_by_id.get(str(row["strategy_packet_input_id"]))
        packet_refs = list(packet_input["evidence_refs"]) if packet_input is not None else []
        add_refs(recommendation_id, list(row["evidence_refs"]), packet_refs)

    for row in synthesis["deferred_recommendations"]:
        add_refs(str(row["recommendation_id"]), list(row["evidence_refs"]))

    for row in synthesis["open_risks"]:
        risk_refs = _req049._collect_unique_refs(list(row["required_evidence_refs"]), list(row["evidence_refs"]))
        add_refs(str(row["recommendation_id"]), risk_refs)
        for recommendation_id in row["linked_recommendation_ids"]:
            add_refs(str(recommendation_id), risk_refs)

    for row in recommendation_deltas:
        add_refs(str(row["recommendation_id"]), list(row["evidence_refs"]))

    return {recommendation_id: list(refs) for recommendation_id, refs in sorted(refs_by_recommendation_id.items())}


def _collect_req_051_processing_evidence_refs(
    *,
    context_usage: Mapping[str, Any],
    changelog_entries: list[Mapping[str, Any]],
    strategic_direction_changes: list[Mapping[str, Any]],
    open_risks: list[Mapping[str, Any]],
) -> list[str]:
    refs: set[str] = set(context_usage["earth_sweep_evidence_refs_considered"])
    for row in changelog_entries:
        refs.update(str(ref) for ref in row["evidence_refs"])
    for row in strategic_direction_changes:
        refs.update(str(ref) for ref in row["evidence_refs"])
    for row in open_risks:
        refs.update(str(ref) for ref in row["required_evidence_refs"])
        refs.update(str(ref) for ref in row["evidence_refs"])
    return sorted(ref for ref in refs if ref)


def _determine_req_051_processing_decision(
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
            "Cross-project direction changes were withheld until Earth-sweep evidence refs are attached.",
        )
    if open_risks:
        return (
            "proceed-with-open-risks",
            "medium",
            "Strategy changelog is complete, but unresolved risks remain visible in the output.",
        )
    if context_usage["cross_project_context_used"] and not cross_project_obligations:
        return (
            "proceed",
            "high",
            "Broad-sweep context was evaluated and no additional cross-project obligations were required.",
        )
    return ("proceed", "high", "Strategy changelog is complete and evidence-linked.")


def _render_req_051_strategy_changelog_markdown(
    *,
    checked_at_utc: str,
    target_project: Mapping[str, str],
    revision_pair: Mapping[str, str],
    change_summary: Mapping[str, Any],
    changelog_entries: list[Mapping[str, Any]],
    strategic_direction_changes: list[Mapping[str, Any]],
    context_usage: Mapping[str, Any],
    open_risks: list[Mapping[str, Any]],
) -> str:
    lines: list[str] = []
    lines.append("# STRATEGY_CHANGELOG")
    lines.append("")
    lines.append(f"Generated at `{checked_at_utc}` for project `{target_project['project_id']}`.")
    lines.append(f"Compares `{revision_pair['previous_revision_id']}` to `{revision_pair['current_revision_id']}`.")
    lines.append("")
    lines.append("## Revision Summary")
    lines.append(f"- Previous revision: `{revision_pair['previous_revision_id']}`")
    lines.append(f"- Current revision: `{revision_pair['current_revision_id']}`")
    lines.append(f"- Changed sections: {_req052._quote_join(list(change_summary['changed_sections']))}")
    lines.append(f"- Change ids: {_req052._quote_join(list(change_summary['change_ids']))}")
    lines.append(f"- Total change count: `{change_summary['total_change_count']}`")
    lines.append("")
    lines.append("## Changed Recommendations")
    if not changelog_entries:
        lines.append("No changed recommendations were emitted.")
    for row in changelog_entries:
        lines.append("")
        lines.append(f"### {row['recommendation_id']}")
        lines.append(f"- Entry id: `{row['entry_id']}`")
        lines.append(f"- Summary: {row['summary']}")
        lines.append(f"- Delta type: `{row['delta_type']}`")
        lines.append(f"- Recommendation status: `{row['recommendation_status']}`")
        lines.append(f"- Direction status: `{row['direction_status']}`")
        lines.append(f"- Strategic direction: {row['strategic_direction']}")
        lines.append(f"- Packet kind: `{row['packet_kind'] or 'none'}`")
        lines.append(f"- Peer project id: `{row['peer_project_id'] or 'none'}`")
        lines.append(f"- Lane: `{row['lane'] or 'none'}`")
        lines.append(f"- Strategy packet input: `{row['strategy_packet_input_id'] or 'none'}`")
        lines.append(f"- Change ids: {_req052._quote_join(list(row['change_ids']))}")
        lines.append(f"- Anchors: {_req052._quote_join(list(row['anchors']))}")
        lines.append(f"- Linked context projects: {_req052._quote_join(list(row['linked_context_project_ids']))}")
        lines.append(f"- Linked open risks: {_req052._quote_join(list(row['linked_open_risk_ids']))}")
        lines.append("- Evidence refs:")
        for ref in row["evidence_refs"]:
            lines.append(f"  - `{ref}`")

    lines.append("")
    lines.append("## Strategic Direction Changes")
    if not strategic_direction_changes:
        lines.append("No strategic direction changes were emitted.")
    for row in strategic_direction_changes:
        lines.append("")
        lines.append(f"### {row['direction_change_id']}")
        lines.append(f"- Linked entry id: `{row['linked_entry_id']}`")
        lines.append(f"- Recommendation id: `{row['recommendation_id']}`")
        lines.append(f"- Direction status: `{row['direction_status']}`")
        lines.append(f"- Strategic direction: {row['strategic_direction']}")
        lines.append(f"- Packet kind: `{row['packet_kind'] or 'none'}`")
        lines.append(f"- Peer project id: `{row['peer_project_id'] or 'none'}`")
        lines.append(f"- Lane: `{row['lane'] or 'none'}`")
        lines.append(f"- Change ids: {_req052._quote_join(list(row['change_ids']))}")
        lines.append(f"- Linked context projects: {_req052._quote_join(list(row['linked_context_project_ids']))}")
        lines.append("- Evidence refs:")
        for ref in row["evidence_refs"]:
            lines.append(f"  - `{ref}`")

    lines.append("")
    lines.append("## Open Risks")
    if not open_risks:
        lines.append("No open risks were emitted.")
    for row in open_risks:
        lines.append("")
        lines.append(f"### {row['open_risk_id']}")
        lines.append(f"- Recommendation id: `{row['recommendation_id']}`")
        lines.append(f"- Project id: `{row['project_id']}`")
        lines.append(f"- Reason code: `{row['reason_code']}`")
        lines.append(f"- Summary: {row['summary']}")
        lines.append(f"- Linked recommendation ids: {_req052._quote_join(list(row['linked_recommendation_ids']))}")
        lines.append("- Required evidence refs:")
        for ref in row["required_evidence_refs"]:
            lines.append(f"  - `{ref}`")
        lines.append("- Evidence refs:")
        for ref in row["evidence_refs"]:
            lines.append(f"  - `{ref}`")

    lines.append("")
    lines.append("## Cross-Project Context Usage")
    lines.append(f"- Context provided: `{str(context_usage['cross_project_context_provided']).lower()}`")
    lines.append(f"- Context used: `{str(context_usage['cross_project_context_used']).lower()}`")
    lines.append(f"- Projects considered: {_req052._quote_join(list(context_usage['projects_considered']))}")
    lines.append(
        "- Earth sweep evidence refs considered: "
        f"{_req052._quote_join(list(context_usage['earth_sweep_evidence_refs_considered']))}"
    )
    lines.append(f"- Cross-project obligation count: `{context_usage['cross_project_obligation_count']}`")
    lines.append(f"- Unresolved idea count: `{context_usage['unresolved_idea_count']}`")
    lines.append(
        "- Recommendation ids with context: "
        f"{_req052._quote_join(list(context_usage['recommendation_ids_with_context']))}"
    )

    lines.append("")
    lines.append("## Totals")
    lines.append(f"- Changed recommendations: `{len(changelog_entries)}`")
    lines.append(f"- Strategic direction changes: `{len(strategic_direction_changes)}`")
    lines.append(f"- Open risks: `{len(open_risks)}`")
    return "\n".join(lines).rstrip() + "\n"


def _compute_req_051_strategy_changelog(payload: Mapping[str, Any]) -> dict[str, Any]:
    raw = _req052._require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_051_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_051_ANALYSIS_TYPE}")

    generated_at_utc = _req052._require_nonempty_text(raw.get("now_utc"), field_name="now_utc")
    target_project = _req052._normalize_target_project(raw.get("target_project"))
    synthesis = _req052._normalize_final_strategy_synthesis(raw.get("final_strategy_synthesis"))
    revision_pair = _normalize_req_051_revision_pair(raw.get("revision_pair"))
    change_summary = _normalize_req_051_change_summary(raw.get("change_summary"))
    recommendation_deltas = _normalize_req_051_recommendation_deltas(raw.get("recommendation_deltas"))

    known_change_ids = set(change_summary["change_ids"])
    referenced_change_ids = {change_id for row in recommendation_deltas for change_id in row["change_ids"]}
    unknown_change_ids = sorted(referenced_change_ids - known_change_ids)
    if unknown_change_ids:
        raise ValueError(f"recommendation_deltas reference unknown change ids: {unknown_change_ids}")
    missing_change_ids = sorted(known_change_ids - referenced_change_ids)
    if missing_change_ids:
        raise ValueError(f"change_summary.change_ids must be fully covered by recommendation_deltas: {missing_change_ids}")

    explicit_context_usage = _compat48_49._normalize_cross_project_context_usage(
        raw.get("cross_project_context_usage"),
        field_name="cross_project_context_usage",
    )
    derived_context_usage = _compat48_49._derive_cross_project_context_usage_from_broad_sweep_context(
        raw.get("broad_sweep_context")
    )
    context_usage = _compat48_49._merge_cross_project_context_usage(explicit_context_usage, derived_context_usage)

    (
        proposed_links,
        cross_project_obligations,
        _missing_links,
        missing_evidence_open_risks,
        proposed_recommendation_refs,
    ) = _build_req_050_proposed_links(
        target_project_id=target_project["project_id"],
        synthesis=synthesis,
        context_usage=context_usage,
    )
    recommendation_refs = _build_req_051_recommendation_refs(
        synthesis=synthesis,
        recommendation_deltas=recommendation_deltas,
        proposed_recommendation_refs=proposed_recommendation_refs,
    )
    _, unresolved_idea_open_risks = _build_req_050_unresolved_idea_rows(
        target_project_id=target_project["project_id"],
        broad_sweep_context=raw.get("broad_sweep_context"),
        context_usage=context_usage,
        recommendation_refs=recommendation_refs,
    )
    synthesis_open_risks = _build_req_050_synthesis_open_risks(synthesis)
    open_risks = _merge_req_050_open_risks(
        synthesis_open_risks,
        missing_evidence_open_risks,
        unresolved_idea_open_risks,
    )
    changelog_entries = _build_req_051_changelog_entries(
        revision_pair=revision_pair,
        synthesis=synthesis,
        recommendation_deltas=recommendation_deltas,
        proposed_links=proposed_links,
        open_risks=open_risks,
    )
    strategic_direction_changes = _build_req_051_strategic_direction_changes(changelog_entries)
    recommended_actions, completeness_rows = _build_req_051_recommended_actions(changelog_entries)
    evidence_refs = _collect_req_051_processing_evidence_refs(
        context_usage=context_usage,
        changelog_entries=changelog_entries,
        strategic_direction_changes=strategic_direction_changes,
        open_risks=open_risks,
    )
    decision, confidence, rationale = _determine_req_051_processing_decision(
        context_usage=context_usage,
        cross_project_obligations=cross_project_obligations,
        open_risks=open_risks,
    )
    completeness_summary = {
        "complete_count": sum(1 for row in completeness_rows if row["fields_complete"]),
        "incomplete_count": sum(1 for row in completeness_rows if not row["fields_complete"]),
        "rows": completeness_rows,
    }
    markdown = _render_req_051_strategy_changelog_markdown(
        checked_at_utc=generated_at_utc,
        target_project=target_project,
        revision_pair=revision_pair,
        change_summary=change_summary,
        changelog_entries=changelog_entries,
        strategic_direction_changes=strategic_direction_changes,
        context_usage=context_usage,
        open_risks=open_risks,
    )
    sections = [
        "Revision Summary",
        "Changed Recommendations",
        "Strategic Direction Changes",
        "Open Risks",
        "Cross-Project Context Usage",
        "Totals",
    ]
    return {
        "generated_at_utc": generated_at_utc,
        "target_project": target_project,
        "revision_pair": revision_pair,
        "change_summary": change_summary,
        "context_usage": context_usage,
        "changelog_entries": changelog_entries,
        "recommended_actions": recommended_actions,
        "recommendation_field_completeness": completeness_summary,
        "strategic_direction_changes": strategic_direction_changes,
        "cross_project_obligations": cross_project_obligations,
        "open_risks": open_risks,
        "decision": decision,
        "confidence": confidence,
        "rationale": rationale,
        "evidence_refs": evidence_refs,
        "markdown": markdown,
        "sections": sections,
        "line_count": len(markdown.splitlines()),
        "totals": {
            "recommendation_deltas": len(recommendation_deltas),
            "changelog_entries": len(changelog_entries),
            "strategic_direction_changes": len(strategic_direction_changes),
            "cross_project_obligations": len(cross_project_obligations),
            "open_risks": len(open_risks),
            "processing_evidence_refs": len(evidence_refs),
        },
    }


def process_req_051_strategy_changelog_md_generator(payload: Mapping[str, Any]) -> dict[str, Any]:
    computed = _compute_req_051_strategy_changelog(payload)
    return {
        "ok": True,
        "schema_version": REQ_051_SCHEMA_VERSION,
        "requirement_id": REQ_051_REQUIREMENT_ID,
        "analysis_type": REQ_051_ANALYSIS_TYPE,
        "call_id": REQ_051_CALL_ID,
        "artifact_kind": REQ_051_ARTIFACT_KIND,
        "generated_at_utc": computed["generated_at_utc"],
        "target_project": computed["target_project"],
        "processing_behavior": {
            "context_usage": computed["context_usage"],
            "recommendation": {
                "decision": computed["decision"],
                "rationale": computed["rationale"],
                "confidence": computed["confidence"],
                "evidence_refs": computed["evidence_refs"],
                "recommended_actions": computed["recommended_actions"],
                "recommendation_field_completeness": computed["recommendation_field_completeness"],
                "changelog_entries": computed["changelog_entries"],
                "strategic_direction_changes": computed["strategic_direction_changes"],
                "cross_project_obligations": computed["cross_project_obligations"],
                "open_risks": computed["open_risks"],
            },
        },
        "totals": dict(computed["totals"]),
    }


def build_req_051_strategy_changelog_md_generator(payload: Mapping[str, Any]) -> dict[str, Any]:
    computed = _compute_req_051_strategy_changelog(payload)
    alignment = {
        "entry_ids": [str(row["entry_id"]) for row in computed["changelog_entries"]],
        "recommendation_ids": [str(row["recommendation_id"]) for row in computed["changelog_entries"]],
        "strategic_direction_change_ids": [
            str(row["direction_change_id"]) for row in computed["strategic_direction_changes"]
        ],
        "open_risk_ids": [str(row["open_risk_id"]) for row in computed["open_risks"]],
        "projects_considered": list(computed["context_usage"]["projects_considered"]),
    }
    return {
        "ok": True,
        "schema_version": REQ_051_SCHEMA_VERSION,
        "requirement_id": REQ_051_REQUIREMENT_ID,
        "analysis_type": REQ_051_ANALYSIS_TYPE,
        "call_id": REQ_051_CALL_ID,
        "artifact_kind": REQ_051_ARTIFACT_KIND,
        "generated_at_utc": computed["generated_at_utc"],
        "target_project": computed["target_project"],
        "strategy_changelog_md": {
            "artifact_path": REQ_051_ARTIFACT_PATH,
            "revision_pair": computed["revision_pair"],
            "change_summary": computed["change_summary"],
            "entries": computed["changelog_entries"],
            "strategic_direction_changes": computed["strategic_direction_changes"],
            "cross_project_context_usage": computed["context_usage"],
            "open_risks": computed["open_risks"],
            "evidence_refs": computed["evidence_refs"],
            "markdown": computed["markdown"],
            "sections": list(computed["sections"]),
            "line_count": computed["line_count"],
            "alignment": alignment,
        },
        "totals": {
            "changelog_entries": len(computed["changelog_entries"]),
            "strategic_direction_changes": len(computed["strategic_direction_changes"]),
            "open_risks": len(computed["open_risks"]),
            "evidence_refs": len(computed["evidence_refs"]),
            "markdown_sections": len(computed["sections"]),
            "markdown_lines": computed["line_count"],
        },
    }


def validate_req_051_strategy_changelog_md_generator(payload: Mapping[str, Any]) -> list[str]:
    if payload.get("artifact_kind") != REQ_051_ARTIFACT_KIND:
        return _req052.validate_req_051_strategy_changelog_md_generator(payload)
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]
    errors: list[str] = []
    changelog = payload.get("strategy_changelog_md")
    totals = payload.get("totals")
    if payload.get("analysis_type") != REQ_051_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_051_ANALYSIS_TYPE}")
    if not isinstance(changelog, Mapping):
        errors.append("strategy_changelog_md must be an object")
        return errors
    expected_changelog_keys = {
        "artifact_path",
        "revision_pair",
        "change_summary",
        "entries",
        "strategic_direction_changes",
        "cross_project_context_usage",
        "open_risks",
        "evidence_refs",
        "markdown",
        "sections",
        "line_count",
        "alignment",
    }
    missing = sorted(expected_changelog_keys - set(changelog.keys()))
    if missing:
        errors.append(f"strategy_changelog_md missing keys: {missing}")
    if changelog.get("artifact_path") != REQ_051_ARTIFACT_PATH:
        errors.append(f"strategy_changelog_md.artifact_path must be {REQ_051_ARTIFACT_PATH}")
    for key in ("entries", "strategic_direction_changes", "open_risks", "evidence_refs", "sections"):
        if not isinstance(changelog.get(key), list):
            errors.append(f"strategy_changelog_md.{key} must be a list")
    if not isinstance(changelog.get("revision_pair"), Mapping):
        errors.append("strategy_changelog_md.revision_pair must be an object")
    if not isinstance(changelog.get("change_summary"), Mapping):
        errors.append("strategy_changelog_md.change_summary must be an object")
    if not isinstance(changelog.get("cross_project_context_usage"), Mapping):
        errors.append("strategy_changelog_md.cross_project_context_usage must be an object")
    if not isinstance(changelog.get("alignment"), Mapping):
        errors.append("strategy_changelog_md.alignment must be an object")
    if not isinstance(changelog.get("markdown"), str) or not changelog.get("markdown", "").strip():
        errors.append("strategy_changelog_md.markdown must be a non-empty string")
    if not isinstance(changelog.get("line_count"), int) or changelog.get("line_count", 0) <= 0:
        errors.append("strategy_changelog_md.line_count must be a positive integer")
    if isinstance(totals, Mapping):
        expected = {
            "changelog_entries": len(changelog.get("entries", [])) if isinstance(changelog.get("entries"), list) else None,
            "strategic_direction_changes": len(changelog.get("strategic_direction_changes", [])) if isinstance(changelog.get("strategic_direction_changes"), list) else None,
            "open_risks": len(changelog.get("open_risks", [])) if isinstance(changelog.get("open_risks"), list) else None,
            "evidence_refs": len(changelog.get("evidence_refs", [])) if isinstance(changelog.get("evidence_refs"), list) else None,
        }
        for key, expected_value in expected.items():
            if expected_value is None:
                continue
            if totals.get(key) != expected_value:
                errors.append(f"totals.{key} must match strategy_changelog_md.{key} length")
    else:
        errors.append("totals must be an object")
    return errors
