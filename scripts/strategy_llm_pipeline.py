#!/usr/bin/env python3
"""REQ-036 contract/data-model surface for cross-call contradiction detection."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

REQ_036_REQUIREMENT_ID = "REQ-036"
REQ_036_SCHEMA_VERSION = "req-036.cross-call-contradiction-detection.v1"
REQ_036_DETECTION_STRATEGY = "cross-call-claim-stance-comparison"
REQ_036_REASON_CODE = "cross_call_contradiction"
REQ_036_HANDLING_POLICY = "explicit-resolution-or-unresolved-risk"
RUNTIME_MODE = "llm-first"
EXECUTION_MODE = "long-thinking"


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


def _require_text(value: Any, *, field_name: str) -> str:
    text = _as_text(value)
    if not text:
        raise ValueError(f"{field_name} must be a non-empty string")
    return text


def _normalize_root(value: Any, *, field_name: str) -> str:
    normalized = str(Path(_require_text(value, field_name=field_name)).expanduser().resolve())
    if not normalized.startswith("/"):
        raise ValueError(f"{field_name} must normalize to an absolute path")
    return normalized


def _normalize_string_list(raw_value: Any, *, field_name: str, min_items: int = 0) -> list[str]:
    if raw_value is None:
        raw_items: Sequence[Any] = []
    else:
        if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
            raise ValueError(f"{field_name} must be an array of non-empty strings")
        raw_items = raw_value

    normalized: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_items):
        text = _require_text(item, field_name=f"{field_name}[{index}]")
        if text in seen:
            continue
        seen.add(text)
        normalized.append(text)

    if len(normalized) < min_items:
        raise ValueError(f"{field_name} must contain at least {min_items} item(s)")
    return sorted(normalized)


def _collect_unique_refs(*ref_groups: Sequence[Any]) -> list[str]:
    seen: set[str] = set()
    for refs in ref_groups:
        for raw_ref in refs:
            ref = _as_text(raw_ref)
            if ref:
                seen.add(ref)
    return sorted(seen)


def _canonical_input_digest(canonical_input: Mapping[str, Any]) -> str:
    raw = json.dumps(canonical_input, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_claim_stance(value: Any, *, field_name: str) -> str:
    stance = _as_text(value).lower()
    if stance not in {"support", "contradict"}:
        raise ValueError(f"{field_name} must be either 'support' or 'contradict'")
    return stance


def _normalize_call_output_claims(raw_value: Any, *, field_name: str) -> list[dict[str, Any]]:
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be an array")

    normalized: list[dict[str, Any]] = []
    seen_claim_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"{field_name}[{index}] must be an object")

        claim_id = _require_text(item.get("claim_id"), field_name=f"{field_name}[{index}].claim_id")
        if claim_id in seen_claim_ids:
            raise ValueError(f"{field_name}[{index}].claim_id must be unique within each call output")
        seen_claim_ids.add(claim_id)

        claim_text = _require_text(item.get("claim_text"), field_name=f"{field_name}[{index}].claim_text")
        stance = _normalize_claim_stance(item.get("stance"), field_name=f"{field_name}[{index}].stance")
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            field_name=f"{field_name}[{index}].evidence_refs",
            min_items=1,
        )

        normalized.append(
            {
                "claim_id": claim_id,
                "claim_text": claim_text,
                "stance": stance,
                "evidence_refs": evidence_refs,
            }
        )

    normalized.sort(key=lambda row: (row["claim_id"], row["stance"], row["claim_text"]))
    return normalized


def _normalize_call_outputs(raw_value: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError("call_outputs must be an array")

    normalized: list[dict[str, Any]] = []
    seen_call_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"call_outputs[{index}] must be an object")

        call_id = _require_text(item.get("call_id"), field_name=f"call_outputs[{index}].call_id")
        if call_id in seen_call_ids:
            raise ValueError(f"call_outputs[{index}].call_id must be unique")
        seen_call_ids.add(call_id)

        call_requirement_id = _as_text(item.get("call_requirement_id"))
        emitted_claims = _normalize_call_output_claims(
            item.get("emitted_claims"),
            field_name=f"call_outputs[{index}].emitted_claims",
        )
        if not emitted_claims:
            raise ValueError(f"call_outputs[{index}].emitted_claims must contain at least 1 claim")

        normalized.append(
            {
                "call_id": call_id,
                "call_requirement_id": call_requirement_id,
                "emitted_claims": emitted_claims,
            }
        )

    if not normalized:
        raise ValueError("call_outputs must contain at least 1 call output")

    normalized.sort(key=lambda row: row["call_id"])
    return normalized


def _normalize_resolution_status(value: Any, *, field_name: str) -> str:
    status = _as_text(value).lower()
    if status not in {"resolved", "unresolved"}:
        raise ValueError(f"{field_name} must be either 'resolved' or 'unresolved'")
    return status


def _normalize_contradiction_resolutions(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError("contradiction_resolutions must be an array when provided")

    normalized: list[dict[str, Any]] = []
    seen_claim_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"contradiction_resolutions[{index}] must be an object")

        claim_id = _require_text(item.get("claim_id"), field_name=f"contradiction_resolutions[{index}].claim_id")
        if claim_id in seen_claim_ids:
            raise ValueError(f"contradiction_resolutions[{index}].claim_id must be unique")
        seen_claim_ids.add(claim_id)

        resolution_status = _normalize_resolution_status(
            item.get("resolution_status"),
            field_name=f"contradiction_resolutions[{index}].resolution_status",
        )
        resolution_summary = _require_text(
            item.get("resolution_summary"),
            field_name=f"contradiction_resolutions[{index}].resolution_summary",
        )
        resolved_by_call_id = _as_text(item.get("resolved_by_call_id"))
        if resolution_status == "resolved" and not resolved_by_call_id:
            raise ValueError(
                f"contradiction_resolutions[{index}].resolved_by_call_id is required when resolution_status is 'resolved'"
            )
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            field_name=f"contradiction_resolutions[{index}].evidence_refs",
            min_items=1,
        )

        normalized.append(
            {
                "claim_id": claim_id,
                "resolution_status": resolution_status,
                "resolution_summary": resolution_summary,
                "resolved_by_call_id": resolved_by_call_id,
                "evidence_refs": evidence_refs,
            }
        )

    normalized.sort(key=lambda row: row["claim_id"])
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


def _canonical_req_036_processing_input(
    *,
    call_outputs: list[dict[str, Any]],
    contradiction_resolutions: list[dict[str, Any]],
    broad_sweep_context: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "call_outputs": call_outputs,
        "contradiction_resolutions": contradiction_resolutions,
        "broad_sweep_context": dict(broad_sweep_context),
    }


def _build_req_036_contradiction_report(
    *,
    call_outputs: list[dict[str, Any]],
    contradiction_resolutions: list[dict[str, Any]],
) -> dict[str, Any]:
    resolution_lookup = {row["claim_id"]: row for row in contradiction_resolutions}

    observations_by_claim: dict[str, list[dict[str, Any]]] = {}
    for call in call_outputs:
        call_id = call["call_id"]
        call_requirement_id = call["call_requirement_id"]
        for claim in call["emitted_claims"]:
            observations_by_claim.setdefault(claim["claim_id"], []).append(
                {
                    "call_id": call_id,
                    "call_requirement_id": call_requirement_id,
                    "claim_text": claim["claim_text"],
                    "stance": claim["stance"],
                    "evidence_refs": list(claim["evidence_refs"]),
                }
            )

    contradictions: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []

    for claim_id in sorted(observations_by_claim):
        observations = observations_by_claim[claim_id]
        observations.sort(key=lambda row: (row["call_id"], row["stance"], row["claim_text"]))
        stances = {row["stance"] for row in observations}
        if stances != {"support", "contradict"}:
            continue

        required_evidence_refs = _collect_unique_refs(*[row["evidence_refs"] for row in observations])
        summary = f"Claim '{claim_id}' has contradictory stances across call outputs."

        resolution_row = resolution_lookup.get(claim_id)
        resolution_status = "unresolved"
        resolution_payload: dict[str, Any] | None = None
        unresolved_risk: dict[str, Any] | None = None

        if resolution_row is not None and resolution_row["resolution_status"] == "resolved":
            resolution_status = "resolved"
            resolution_payload = {
                "resolution_status": "resolved",
                "resolution_summary": resolution_row["resolution_summary"],
                "resolved_by_call_id": resolution_row["resolved_by_call_id"],
                "evidence_refs": list(resolution_row["evidence_refs"]),
            }
        else:
            if resolution_row is not None:
                resolution_payload = {
                    "resolution_status": "unresolved",
                    "resolution_summary": resolution_row["resolution_summary"],
                    "resolved_by_call_id": "",
                    "evidence_refs": list(resolution_row["evidence_refs"]),
                }
            unresolved_risk = {
                "risk_id": f"risk-claim-{claim_id}-contradiction",
                "summary": summary,
                "reason_code": REQ_036_REASON_CODE,
                "required_evidence_refs": _collect_unique_refs(
                    required_evidence_refs,
                    [] if resolution_row is None else resolution_row["evidence_refs"],
                ),
            }
            open_risks.append(unresolved_risk)

        contradictions.append(
            {
                "claim_id": claim_id,
                "summary": summary,
                "contradictory_calls": observations,
                "resolution_status": resolution_status,
                "resolution": resolution_payload,
                "unresolved_risk": unresolved_risk,
                "required_evidence_refs": required_evidence_refs,
            }
        )

    contradictions.sort(key=lambda row: row["claim_id"])
    open_risks.sort(key=lambda row: row["risk_id"])

    return {
        "detection_strategy": REQ_036_DETECTION_STRATEGY,
        "contradiction_count": len(contradictions),
        "resolved_contradictions": sum(1 for row in contradictions if row["resolution_status"] == "resolved"),
        "unresolved_contradictions": sum(1 for row in contradictions if row["resolution_status"] == "unresolved"),
        "contradictions": contradictions,
        "open_risks": open_risks,
        "evidence_refs": _collect_unique_refs(
            *[row["required_evidence_refs"] for row in contradictions],
            *[row["required_evidence_refs"] for row in open_risks],
        ),
    }


def _build_req_036_processing_behavior(
    *,
    broad_sweep_context: Mapping[str, str],
    call_outputs: list[dict[str, Any]],
    contradiction_resolutions: list[dict[str, Any]],
    contradiction_report: Mapping[str, Any],
) -> dict[str, Any]:
    unresolved_count = int(contradiction_report.get("unresolved_contradictions", 0))
    contradiction_claim_ids = [
        _as_text(row.get("claim_id"))
        for row in contradiction_report.get("contradictions", [])
        if isinstance(row, Mapping) and _as_text(row.get("claim_id"))
    ]
    recommendation_evidence_refs = list(contradiction_report.get("evidence_refs", []))

    if unresolved_count > 0:
        decision = "requires-resolution-before-final-synthesis"
        rationale = "At least one cross-call contradiction remains unresolved and is now explicitly risk-marked."
        confidence = "low"
        recommended_actions = [
            {
                "action_id": "resolve-cross-call-contradictions",
                "summary": "Resolve contradiction claims or accept unresolved risk before final synthesis.",
                "rationale": "REQ-036 requires explicit resolution or unresolved-risk marking for contradictions.",
                "next_step": "Address contradiction_report.open_risks or acknowledge each unresolved risk in synthesis output.",
                "evidence_refs": recommendation_evidence_refs,
            }
        ]
    else:
        decision = "ready-for-final-synthesis"
        rationale = "Cross-call contradictions are either absent or explicitly resolved with evidence refs."
        confidence = "high"
        recommended_actions = [
            {
                "action_id": "proceed-to-final-synthesis",
                "summary": "Proceed with final synthesis using resolved contradiction context.",
                "rationale": "No unresolved cross-call contradiction remains in the contradiction report.",
                "next_step": "Use contradiction_report.contradictions as rationale support in synthesis output.",
                "evidence_refs": recommendation_evidence_refs,
            }
        ]

    return {
        "strategy": "cross-call-contradiction-detection",
        "reasoning_mode": EXECUTION_MODE,
        "heuristic_summarization_only": False,
        "contradiction_handling_policy": REQ_036_HANDLING_POLICY,
        "context_inputs": {
            "broad_sweep_context": dict(broad_sweep_context),
            "call_outputs": call_outputs,
            "contradiction_resolutions": contradiction_resolutions,
        },
        "context_usage": {
            "call_count": len(call_outputs),
            "call_ids_considered": [row["call_id"] for row in call_outputs],
            "contradiction_claim_ids": sorted(contradiction_claim_ids),
            "contradiction_count": int(contradiction_report.get("contradiction_count", 0)),
            "resolved_contradictions": int(contradiction_report.get("resolved_contradictions", 0)),
            "unresolved_contradictions": unresolved_count,
            "evidence_refs_used": recommendation_evidence_refs,
            "broad_sweep_context_used": True,
            "broad_sweep_context_scope": "earth-wide",
            "target_project_root": broad_sweep_context["target_project_root"],
            "earth_root": broad_sweep_context["earth_root"],
            "output_root": broad_sweep_context["output_root"],
            "revision_identity": broad_sweep_context["revision_identity"],
        },
        "recommendation": {
            "decision": decision,
            "rationale": rationale,
            "confidence": confidence,
            "evidence_refs": recommendation_evidence_refs,
            "recommended_actions": recommended_actions,
            "open_risks": list(contradiction_report.get("open_risks", [])),
        },
    }


def _build_req_036_context_bundle(
    *,
    processing_behavior: Mapping[str, Any],
    contradiction_report: Mapping[str, Any],
) -> dict[str, Any]:
    bundle = {
        "processing_context_inputs": processing_behavior.get("context_inputs", {}),
        "processing_context_usage": processing_behavior.get("context_usage", {}),
        "recommendation": processing_behavior.get("recommendation", {}),
        "contradiction_report": contradiction_report,
    }
    canonical_json = json.dumps(bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return {
        "schema_version": "req-036.cross-call-contradiction-context-bundle.v1",
        "canonical_json": canonical_json,
        "sha256": hashlib.sha256(canonical_json.encode("utf-8")).hexdigest(),
    }


def build_req_036_cross_call_contradiction_detection(
    *,
    target_project_root: str,
    earth_root: str,
    output_root: str,
    revision_identity: str,
    call_outputs: Sequence[Mapping[str, Any]],
    contradiction_resolutions: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_target_root = _normalize_root(target_project_root, field_name="target_project_root")
    normalized_earth_root = _normalize_root(earth_root, field_name="earth_root")
    normalized_output_root = _normalize_root(output_root, field_name="output_root")
    normalized_revision_identity = _require_text(revision_identity, field_name="revision_identity")
    normalized_call_outputs = _normalize_call_outputs(call_outputs)
    normalized_resolutions = _normalize_contradiction_resolutions(contradiction_resolutions)

    canonical_input = _canonical_call_input(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        output_root=normalized_output_root,
        revision_identity=normalized_revision_identity,
    )
    canonical_digest = _canonical_input_digest(canonical_input)

    contradiction_report = _build_req_036_contradiction_report(
        call_outputs=normalized_call_outputs,
        contradiction_resolutions=normalized_resolutions,
    )
    normalized_broad_sweep_context = {
        "target_project_root": normalized_target_root,
        "earth_root": normalized_earth_root,
        "output_root": normalized_output_root,
        "revision_identity": normalized_revision_identity,
    }
    processing_behavior = _build_req_036_processing_behavior(
        broad_sweep_context=normalized_broad_sweep_context,
        call_outputs=normalized_call_outputs,
        contradiction_resolutions=normalized_resolutions,
        contradiction_report=contradiction_report,
    )
    context_bundle = _build_req_036_context_bundle(
        processing_behavior=processing_behavior,
        contradiction_report=contradiction_report,
    )

    canonical_processing_input = _canonical_req_036_processing_input(
        call_outputs=normalized_call_outputs,
        contradiction_resolutions=normalized_resolutions,
        broad_sweep_context=normalized_broad_sweep_context,
    )
    processing_digest = _canonical_input_digest(canonical_processing_input)

    return {
        "schema_version": REQ_036_SCHEMA_VERSION,
        "requirement_id": REQ_036_REQUIREMENT_ID,
        "cross_call_contradiction_detection": {
            "runtime_mode": RUNTIME_MODE,
            "execution_mode": EXECUTION_MODE,
            "target_project_root": normalized_target_root,
            "earth_root": normalized_earth_root,
            "output_root": normalized_output_root,
            "revision_identity": normalized_revision_identity,
        },
        "processing_behavior": processing_behavior,
        "contradiction_report": contradiction_report,
        "context_bundle": context_bundle,
        "call_metadata": {
            "reproducibility": "deterministic-input-fingerprint",
            "canonical_input": canonical_input,
            "canonical_input_sha256": canonical_digest,
            "reproducible_call_id": f"req036-{canonical_digest[:16]}",
            "canonical_processing_input": canonical_processing_input,
            "processing_input_sha256": processing_digest,
            "processing_call_id": f"req036-processing-{processing_digest[:16]}",
        },
    }


def validate_req_036_cross_call_contradiction_detection(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    required_top = {
        "schema_version",
        "requirement_id",
        "cross_call_contradiction_detection",
        "processing_behavior",
        "contradiction_report",
        "context_bundle",
        "call_metadata",
    }
    top_keys = set(payload.keys())
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - required_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("schema_version") != REQ_036_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_036_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_036_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_036_REQUIREMENT_ID}")

    extraction = payload.get("cross_call_contradiction_detection")
    if not isinstance(extraction, Mapping):
        errors.append("cross_call_contradiction_detection must be an object")
        return errors

    for required_field in (
        "runtime_mode",
        "execution_mode",
        "target_project_root",
        "earth_root",
        "output_root",
        "revision_identity",
    ):
        if required_field not in extraction:
            errors.append(f"cross_call_contradiction_detection missing {required_field}")

    if extraction.get("runtime_mode") != RUNTIME_MODE:
        errors.append(f"runtime_mode must be {RUNTIME_MODE}")
    if extraction.get("execution_mode") != EXECUTION_MODE:
        errors.append(f"execution_mode must be {EXECUTION_MODE}")

    processing_behavior = payload.get("processing_behavior")
    if not isinstance(processing_behavior, Mapping):
        errors.append("processing_behavior must be an object")
        return errors

    context_inputs = processing_behavior.get("context_inputs")
    if not isinstance(context_inputs, Mapping):
        errors.append("processing_behavior.context_inputs must be an object")
        return errors

    try:
        normalized_target_root = _normalize_root(
            extraction.get("target_project_root"),
            field_name="cross_call_contradiction_detection.target_project_root",
        )
        normalized_earth_root = _normalize_root(
            extraction.get("earth_root"),
            field_name="cross_call_contradiction_detection.earth_root",
        )
        normalized_output_root = _normalize_root(
            extraction.get("output_root"),
            field_name="cross_call_contradiction_detection.output_root",
        )
        normalized_revision_identity = _require_text(
            extraction.get("revision_identity"),
            field_name="cross_call_contradiction_detection.revision_identity",
        )
        normalized_call_outputs = _normalize_call_outputs(context_inputs.get("call_outputs"))
        normalized_resolutions = _normalize_contradiction_resolutions(context_inputs.get("contradiction_resolutions"))
    except ValueError as exc:
        errors.append(str(exc))
        return errors

    expected_contradiction_report = _build_req_036_contradiction_report(
        call_outputs=normalized_call_outputs,
        contradiction_resolutions=normalized_resolutions,
    )
    if payload.get("contradiction_report") != expected_contradiction_report:
        errors.append("contradiction_report must mirror deterministic contradiction detection output")

    expected_processing_behavior = _build_req_036_processing_behavior(
        broad_sweep_context={
            "target_project_root": normalized_target_root,
            "earth_root": normalized_earth_root,
            "output_root": normalized_output_root,
            "revision_identity": normalized_revision_identity,
        },
        call_outputs=normalized_call_outputs,
        contradiction_resolutions=normalized_resolutions,
        contradiction_report=expected_contradiction_report,
    )
    if dict(processing_behavior) != expected_processing_behavior:
        errors.append("processing_behavior must mirror deterministic contradiction handling output")

    context_bundle = payload.get("context_bundle")
    if not isinstance(context_bundle, Mapping):
        errors.append("context_bundle must be an object")
        return errors
    expected_context_bundle = _build_req_036_context_bundle(
        processing_behavior=expected_processing_behavior,
        contradiction_report=expected_contradiction_report,
    )
    if dict(context_bundle) != expected_context_bundle:
        errors.append("context_bundle must mirror deterministic contradiction context serialization")

    metadata = payload.get("call_metadata")
    if not isinstance(metadata, Mapping):
        errors.append("call_metadata must be an object")
        return errors

    expected_canonical_input = _canonical_call_input(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        output_root=normalized_output_root,
        revision_identity=normalized_revision_identity,
    )
    expected_digest = _canonical_input_digest(expected_canonical_input)
    if metadata.get("canonical_input") != expected_canonical_input:
        errors.append("call_metadata.canonical_input must mirror normalized ingestion anchors")
    if metadata.get("canonical_input_sha256") != expected_digest:
        errors.append("call_metadata.canonical_input_sha256 does not match canonical input")
    if metadata.get("reproducible_call_id") != f"req036-{expected_digest[:16]}":
        errors.append("call_metadata.reproducible_call_id does not match canonical digest")

    expected_processing_input = _canonical_req_036_processing_input(
        call_outputs=normalized_call_outputs,
        contradiction_resolutions=normalized_resolutions,
        broad_sweep_context={
            "target_project_root": normalized_target_root,
            "earth_root": normalized_earth_root,
            "output_root": normalized_output_root,
            "revision_identity": normalized_revision_identity,
        },
    )
    expected_processing_digest = _canonical_input_digest(expected_processing_input)
    if metadata.get("canonical_processing_input") != expected_processing_input:
        errors.append("call_metadata.canonical_processing_input must mirror normalized processing input")
    if metadata.get("processing_input_sha256") != expected_processing_digest:
        errors.append("call_metadata.processing_input_sha256 does not match processing input")
    if metadata.get("processing_call_id") != f"req036-processing-{expected_processing_digest[:16]}":
        errors.append("call_metadata.processing_call_id does not match processing digest")

    return errors
