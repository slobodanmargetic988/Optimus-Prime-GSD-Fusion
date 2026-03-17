#!/usr/bin/env python3
'Contract/data-model surfaces for strategy LLM pipeline calls.\n\nImplemented requirement surfaces:\n- REQ-027 Call-2 ecosystem linkage reasoning.\n- REQ-030 Call-5 sequencing and lane design reasoning.\n- REQ-035 Evidence citation discipline in reasoning calls.\n- REQ-039 Recommendation rationale quality scoring.\n- REQ-047 LLM call trace and decision ledger.\n'

from __future__ import annotations

import argparse

import hashlib

import json

import os

import sys

import time

from datetime import datetime, timezone

from pathlib import Path

from typing import Any, Callable, Mapping

REQ_039_SCHEMA_VERSION = 'req-039.recommendation-rationale-quality-scoring.v1'

REQ_039_PROCESSING_SCHEMA_VERSION = 'req-039.recommendation-rationale-quality-scoring-processing.v1'

REQ_039_REQUIREMENT_ID = 'REQ-039'

REQ_039_ANALYSIS_TYPE = 'recommendation_rationale_quality_scoring'

REQ_039_CALL_ID = 'rationale-quality-scoring'

REQ_047_SCHEMA_VERSION = 'req-047.llm-call-trace-and-decision-ledger.v1'

REQ_047_PROCESSING_SCHEMA_VERSION = 'req-047.llm-call-trace-and-decision-ledger-processing.v1'

REQ_047_REQUIREMENT_ID = 'REQ-047'

REQ_047_ANALYSIS_TYPE = 'llm_call_trace_and_decision_ledger'

REQ_047_CALL_ID = 'trace-and-decision-ledger'

_REQ_039_QUALITY_STATUSES = ('accepted', 'rejected')

_REQ_039_REJECTION_REASON_CODES = ('insufficient_evidence_refs', 'missing_explicit_tradeoffs')

_REQ_047_DECISION_TYPES = ('emit', 'hold', 'revise', 'reject')

_LLM_CALL_TRACE_SCHEMA_VERSION = 'optimus-prime.llm-call-trace.v1'

_LLM_CALL_TRACE_RELATIVE_PATH = 'strategy/current/llm_call_trace.jsonl'

_LLM_CALL_TRACE_ARTIFACTS_RELATIVE_DIR = 'strategy/current/llm_call_trace_artifacts'

_REQ_039_CALL_OBJECTIVE = 'Score recommendation rationale quality before packet emission; reject low-substance recommendations that do not meet minimum evidence and tradeoff thresholds; gate cross-project obligations on Earth-sweep evidence refs and record unresolved ideas as open risks.'

_REQ_047_CALL_OBJECTIVE = 'Record machine-readable call-level trace metadata and decision-ledger links to final output artifacts; preserve auditability across emitted and deferred strategy decisions; keep replay analysis reproducible without adding new packet sections or orchestration gates.'

def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f'{field_name} must be an object')
    return value

def _require_nonempty_text(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f'{field_name} must be a string')
    text = value.strip()
    if not text:
        raise ValueError(f'{field_name} must be a non-empty string')
    return text

def _normalize_string_list(raw_value: Any, *, field_name: str) -> list[str]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError(f'{field_name} must be a list of strings')
    normalized: set[str] = set()
    for index, item in enumerate(raw_value):
        normalized.add(_require_nonempty_text(item, field_name=f'{field_name}[{index}]'))
    return sorted(normalized)

def _is_lower_hex(value: str, *, length: int) -> bool:
    return len(value) == length and all((char in '0123456789abcdef' for char in value))

def _require_sha256_hex(value: Any, *, field_name: str) -> str:
    digest = _require_nonempty_text(value, field_name=field_name)
    if not _is_lower_hex(digest, length=64):
        raise ValueError(f'{field_name} must be a lowercase 64-character sha256 hex digest')
    return digest

def _req_047_call_ref(*, requirement_id: str, call_id: str) -> str:
    return f'{requirement_id}::call::{call_id}'

def _normalize_req_047_totals(raw_value: Any, *, field_name: str) -> dict[str, int]:
    totals = _require_mapping(raw_value, field_name=field_name)
    normalized: dict[str, int] = {}
    for key in sorted(totals.keys()):
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f'{field_name} keys must be non-empty strings')
        count = totals[key]
        if not isinstance(count, int) or count < 0:
            raise ValueError(f'{field_name}.{key} must be a non-negative integer')
        normalized[key] = count
    return normalized

def _normalize_req_047_artifacts(raw_value: Any, *, field_name: str) -> list[dict[str, str]]:
    if not isinstance(raw_value, list) or not raw_value:
        raise ValueError(f'{field_name} must be a non-empty list')
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for index, item in enumerate(raw_value):
        artifact = _require_mapping(item, field_name=f'{field_name}[{index}]')
        kind = _require_nonempty_text(artifact.get('kind'), field_name=f'{field_name}[{index}].kind')
        path = _require_nonempty_text(artifact.get('path'), field_name=f'{field_name}[{index}].path')
        sha256 = _require_sha256_hex(artifact.get('sha256'), field_name=f'{field_name}[{index}].sha256')
        normalized_row = {'kind': kind, 'path': path, 'sha256': sha256}
        extra = sorted(set(artifact.keys()) - set(normalized_row.keys()))
        if extra:
            raise ValueError(f'{field_name}[{index}] has unexpected keys: {extra}')
        key = (kind, path, sha256)
        if key in seen:
            raise ValueError(f'{field_name}[{index}] must be unique (duplicate artifact: {path})')
        seen.add(key)
        normalized.append(normalized_row)
    normalized.sort(key=lambda row: (row['kind'], row['path'], row['sha256']))
    return normalized

def _normalize_req_047_trace_rows(raw_value: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_value, list) or not raw_value:
        raise ValueError('llm_call_trace_rows must be a non-empty list')
    normalized: list[dict[str, Any]] = []
    seen_call_refs: set[str] = set()
    for index, item in enumerate(raw_value):
        row = _require_mapping(item, field_name=f'llm_call_trace_rows[{index}]')
        schema_version = row.get('schema_version')
        if schema_version is not None and schema_version != _LLM_CALL_TRACE_SCHEMA_VERSION:
            raise ValueError(f'llm_call_trace_rows[{index}].schema_version must be {_LLM_CALL_TRACE_SCHEMA_VERSION}')
        checked_at_utc = _require_nonempty_text(row.get('checked_at_utc'), field_name=f'llm_call_trace_rows[{index}].checked_at_utc')
        requirement_id = _require_nonempty_text(row.get('requirement_id'), field_name=f'llm_call_trace_rows[{index}].requirement_id')
        analysis_type = _require_nonempty_text(row.get('analysis_type'), field_name=f'llm_call_trace_rows[{index}].analysis_type')
        call_id = _require_nonempty_text(row.get('call_id'), field_name=f'llm_call_trace_rows[{index}].call_id')
        call_objective = _require_nonempty_text(row.get('call_objective'), field_name=f'llm_call_trace_rows[{index}].call_objective')
        raw_target_project_id = row.get('target_project_id')
        if raw_target_project_id is None:
            target_project_id = ''
        elif not isinstance(raw_target_project_id, str):
            raise ValueError(f'llm_call_trace_rows[{index}].target_project_id must be a string')
        else:
            target_project_id = raw_target_project_id.strip()
        peer_project_ids = _normalize_string_list(row.get('peer_project_ids'), field_name=f'llm_call_trace_rows[{index}].peer_project_ids')
        input_refs = _normalize_string_list(row.get('input_refs'), field_name=f'llm_call_trace_rows[{index}].input_refs')
        if not input_refs:
            raise ValueError(f'llm_call_trace_rows[{index}].input_refs must contain at least one ref')
        output_refs = _normalize_string_list(row.get('output_refs'), field_name=f'llm_call_trace_rows[{index}].output_refs')
        if not output_refs:
            raise ValueError(f'llm_call_trace_rows[{index}].output_refs must contain at least one ref')
        artifacts = _normalize_req_047_artifacts(row.get('artifacts'), field_name=f'llm_call_trace_rows[{index}].artifacts')
        handoff_summary = _require_nonempty_text(row.get('handoff_summary'), field_name=f'llm_call_trace_rows[{index}].handoff_summary')
        totals = _normalize_req_047_totals(row.get('totals'), field_name=f'llm_call_trace_rows[{index}].totals')
        normalized_row = {'schema_version': _LLM_CALL_TRACE_SCHEMA_VERSION, 'checked_at_utc': checked_at_utc, 'requirement_id': requirement_id, 'analysis_type': analysis_type, 'call_id': call_id, 'call_ref': _req_047_call_ref(requirement_id=requirement_id, call_id=call_id), 'call_objective': call_objective, 'target_project_id': target_project_id, 'peer_project_ids': peer_project_ids, 'input_refs': input_refs, 'output_refs': output_refs, 'artifacts': artifacts, 'handoff_summary': handoff_summary, 'totals': totals}
        raw_call_ref = row.get('call_ref')
        if raw_call_ref is not None and raw_call_ref != normalized_row['call_ref']:
            raise ValueError(f"llm_call_trace_rows[{index}].call_ref must equal {normalized_row['call_ref']}")
        extra = sorted(set(row.keys()) - {'schema_version', 'checked_at_utc', 'requirement_id', 'analysis_type', 'call_id', 'call_ref', 'call_objective', 'target_project_id', 'peer_project_ids', 'input_refs', 'output_refs', 'artifacts', 'handoff_summary', 'totals', 'linked_final_output_artifact_refs'})
        if extra:
            raise ValueError(f'llm_call_trace_rows[{index}] has unexpected keys: {extra}')
        call_ref = normalized_row['call_ref']
        if call_ref in seen_call_refs:
            raise ValueError(f'llm_call_trace_rows[{index}] must be unique by requirement_id + call_id (duplicate: {call_ref})')
        seen_call_refs.add(call_ref)
        normalized.append(normalized_row)
    normalized.sort(key=lambda row: (row['requirement_id'], row['call_id'], row['analysis_type']))
    return normalized

def _normalize_req_047_final_output_artifacts(raw_value: Any) -> list[dict[str, str]]:
    if not isinstance(raw_value, list) or not raw_value:
        raise ValueError('final_output_artifacts must be a non-empty list')
    normalized: list[dict[str, str]] = []
    seen_refs: set[str] = set()
    for index, item in enumerate(raw_value):
        artifact = _require_mapping(item, field_name=f'final_output_artifacts[{index}]')
        artifact_ref = _require_nonempty_text(artifact.get('artifact_ref'), field_name=f'final_output_artifacts[{index}].artifact_ref')
        artifact_role = _require_nonempty_text(artifact.get('artifact_role'), field_name=f'final_output_artifacts[{index}].artifact_role')
        sha256 = _require_sha256_hex(artifact.get('sha256'), field_name=f'final_output_artifacts[{index}].sha256')
        normalized_row = {'artifact_ref': artifact_ref, 'artifact_role': artifact_role, 'sha256': sha256}
        extra = sorted(set(artifact.keys()) - set(normalized_row.keys()))
        if extra:
            raise ValueError(f'final_output_artifacts[{index}] has unexpected keys: {extra}')
        if artifact_ref in seen_refs:
            raise ValueError(f'final_output_artifacts[{index}].artifact_ref must be unique (duplicate: {artifact_ref})')
        seen_refs.add(artifact_ref)
        normalized.append(normalized_row)
    normalized.sort(key=lambda row: (row['artifact_role'], row['artifact_ref']))
    return normalized

def _normalize_req_047_decision_ledger(raw_value: Any, *, known_call_refs: set[str], known_artifact_refs: set[str]) -> list[dict[str, Any]]:
    if not isinstance(raw_value, list) or not raw_value:
        raise ValueError('decision_ledger must be a non-empty list')
    normalized: list[dict[str, Any]] = []
    seen_decision_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        decision = _require_mapping(item, field_name=f'decision_ledger[{index}]')
        decision_id = _require_nonempty_text(decision.get('decision_id'), field_name=f'decision_ledger[{index}].decision_id')
        if decision_id in seen_decision_ids:
            raise ValueError(f'decision_ledger[{index}].decision_id must be unique (duplicate: {decision_id})')
        seen_decision_ids.add(decision_id)
        decision_type = _require_nonempty_text(decision.get('decision_type'), field_name=f'decision_ledger[{index}].decision_type').lower()
        if decision_type not in _REQ_047_DECISION_TYPES:
            raise ValueError(f'decision_ledger[{index}].decision_type must be one of: {list(_REQ_047_DECISION_TYPES)}')
        summary = _require_nonempty_text(decision.get('summary'), field_name=f'decision_ledger[{index}].summary')
        rationale = _require_nonempty_text(decision.get('rationale'), field_name=f'decision_ledger[{index}].rationale')
        source_call_refs = _normalize_string_list(decision.get('source_call_refs'), field_name=f'decision_ledger[{index}].source_call_refs')
        if not source_call_refs:
            raise ValueError(f'decision_ledger[{index}].source_call_refs must contain at least one ref')
        unknown_call_refs = sorted(set(source_call_refs) - known_call_refs)
        if unknown_call_refs:
            raise ValueError(f'decision_ledger[{index}].source_call_refs must reference llm_call_trace_rows.call_ref values: {unknown_call_refs}')
        final_output_artifact_refs = _normalize_string_list(decision.get('final_output_artifact_refs'), field_name=f'decision_ledger[{index}].final_output_artifact_refs')
        if not final_output_artifact_refs:
            raise ValueError(f'decision_ledger[{index}].final_output_artifact_refs must contain at least one ref')
        unknown_artifact_refs = sorted(set(final_output_artifact_refs) - known_artifact_refs)
        if unknown_artifact_refs:
            raise ValueError(f'decision_ledger[{index}].final_output_artifact_refs must reference final_output_artifacts.artifact_ref values: {unknown_artifact_refs}')
        evidence_refs = _normalize_string_list(decision.get('evidence_refs'), field_name=f'decision_ledger[{index}].evidence_refs')
        if not evidence_refs:
            raise ValueError(f'decision_ledger[{index}].evidence_refs must contain at least one ref')
        normalized_row = {'decision_id': decision_id, 'decision_type': decision_type, 'summary': summary, 'rationale': rationale, 'source_call_refs': source_call_refs, 'final_output_artifact_refs': final_output_artifact_refs, 'evidence_refs': evidence_refs}
        extra = sorted(set(decision.keys()) - set(normalized_row.keys()))
        if extra:
            raise ValueError(f'decision_ledger[{index}] has unexpected keys: {extra}')
        normalized.append(normalized_row)
    normalized.sort(key=lambda row: row['decision_id'])
    return normalized

def _req_047_linked_artifact_refs_by_call(*, call_refs: list[str], decision_ledger: list[dict[str, Any]]) -> dict[str, list[str]]:
    linked: dict[str, set[str]] = {call_ref: set() for call_ref in call_refs}
    for decision in decision_ledger:
        decision_call_refs = decision.get('source_call_refs')
        decision_call_refs = decision_call_refs if isinstance(decision_call_refs, list) else []
        artifact_refs = decision.get('final_output_artifact_refs')
        artifact_refs = artifact_refs if isinstance(artifact_refs, list) else []
        for call_ref in decision_call_refs:
            if call_ref in linked:
                linked[call_ref].update((str(ref) for ref in artifact_refs if str(ref).strip()))
    return {call_ref: sorted(refs) for call_ref, refs in linked.items()}

def _req_047_traceability_index(*, final_output_artifacts: list[dict[str, str]], decision_ledger: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decision_ids_by_artifact: dict[str, set[str]] = {}
    source_call_refs_by_artifact: dict[str, set[str]] = {}
    for decision in decision_ledger:
        decision_id = str(decision.get('decision_id') or '').strip()
        source_call_refs = decision.get('source_call_refs')
        source_call_refs = source_call_refs if isinstance(source_call_refs, list) else []
        artifact_refs = decision.get('final_output_artifact_refs')
        artifact_refs = artifact_refs if isinstance(artifact_refs, list) else []
        for artifact_ref in artifact_refs:
            decision_ids_by_artifact.setdefault(artifact_ref, set()).add(decision_id)
            source_call_refs_by_artifact.setdefault(artifact_ref, set()).update((str(ref) for ref in source_call_refs if str(ref).strip()))
    rows: list[dict[str, Any]] = []
    for artifact in final_output_artifacts:
        artifact_ref = artifact['artifact_ref']
        rows.append({'final_output_artifact_ref': artifact_ref, 'artifact_role': artifact['artifact_role'], 'decision_ids': sorted(decision_ids_by_artifact.get(artifact_ref, set())), 'source_call_refs': sorted(source_call_refs_by_artifact.get(artifact_ref, set()))})
    rows.sort(key=lambda row: (row['artifact_role'], row['final_output_artifact_ref']))
    return rows

def _normalize_req_039_quality_policy(raw_value: Any) -> dict[str, int]:
    policy = _require_mapping(raw_value, field_name='quality_policy')
    minimum_evidence_ref_count = policy.get('minimum_evidence_ref_count')
    if not isinstance(minimum_evidence_ref_count, int) or minimum_evidence_ref_count <= 0:
        raise ValueError('quality_policy.minimum_evidence_ref_count must be a positive integer')
    minimum_tradeoff_count = policy.get('minimum_tradeoff_count')
    if not isinstance(minimum_tradeoff_count, int) or minimum_tradeoff_count <= 0:
        raise ValueError('quality_policy.minimum_tradeoff_count must be a positive integer')
    passing_score = policy.get('passing_score')
    if not isinstance(passing_score, int) or passing_score <= 0 or passing_score > 4:
        raise ValueError('quality_policy.passing_score must be an integer between 1 and 4')
    normalized = {'minimum_evidence_ref_count': minimum_evidence_ref_count, 'minimum_tradeoff_count': minimum_tradeoff_count, 'passing_score': passing_score}
    extra = sorted(set(policy.keys()) - set(normalized.keys()))
    if extra:
        raise ValueError(f'quality_policy has unexpected keys: {extra}')
    return normalized

def _normalize_req_039_recommendations(raw_value: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_value, list) or not raw_value:
        raise ValueError('recommendations must be a non-empty list')
    normalized: list[dict[str, Any]] = []
    seen_recommendation_ids: set[str] = set()
    for idx, item in enumerate(raw_value):
        recommendation = _require_mapping(item, field_name=f'recommendations[{idx}]')
        recommendation_id = _require_nonempty_text(recommendation.get('recommendation_id'), field_name=f'recommendations[{idx}].recommendation_id')
        if recommendation_id in seen_recommendation_ids:
            raise ValueError(f'recommendations[{idx}].recommendation_id must be unique (duplicate: {recommendation_id})')
        seen_recommendation_ids.add(recommendation_id)
        summary = _require_nonempty_text(recommendation.get('summary'), field_name=f'recommendations[{idx}].summary')
        rationale = _require_nonempty_text(recommendation.get('rationale'), field_name=f'recommendations[{idx}].rationale')
        evidence_refs = _normalize_string_list(recommendation.get('evidence_refs'), field_name=f'recommendations[{idx}].evidence_refs')
        tradeoffs = _normalize_string_list(recommendation.get('tradeoffs'), field_name=f'recommendations[{idx}].tradeoffs')
        normalized_row = {'recommendation_id': recommendation_id, 'summary': summary, 'rationale': rationale, 'evidence_refs': evidence_refs, 'tradeoffs': tradeoffs}
        extra = sorted(set(recommendation.keys()) - set(normalized_row.keys()))
        if extra:
            raise ValueError(f'recommendations[{idx}] has unexpected keys: {extra}')
        normalized.append(normalized_row)
    normalized.sort(key=lambda row: row['recommendation_id'])
    return normalized

def _req_039_quality_breakdown(*, evidence_ref_count: int, tradeoff_count: int, quality_policy: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
    minimum_evidence_ref_count = int(quality_policy['minimum_evidence_ref_count'])
    minimum_tradeoff_count = int(quality_policy['minimum_tradeoff_count'])
    evidence_requirement_met = evidence_ref_count >= minimum_evidence_ref_count
    tradeoff_requirement_met = tradeoff_count >= minimum_tradeoff_count
    evidence_score = 2 if evidence_requirement_met else 1 if evidence_ref_count > 0 else 0
    tradeoff_score = 2 if tradeoff_requirement_met else 0
    quality_score = evidence_score + tradeoff_score
    return (quality_score, {'evidence_ref_count': evidence_ref_count, 'evidence_requirement_met': evidence_requirement_met, 'tradeoff_count': tradeoff_count, 'tradeoff_requirement_met': tradeoff_requirement_met})

def build_req_039_recommendation_rationale_quality_scoring(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build normalized REQ-039 payload for recommendation rationale quality scoring."""
    raw = _require_mapping(payload, field_name='payload')
    analysis_type = str(raw.get('analysis_type') or '').strip()
    if analysis_type and analysis_type != REQ_039_ANALYSIS_TYPE:
        raise ValueError(f'analysis_type must be {REQ_039_ANALYSIS_TYPE}')
    checked_at_utc = _require_nonempty_text(raw.get('now_utc'), field_name='now_utc')
    quality_policy = _normalize_req_039_quality_policy(raw.get('quality_policy'))
    recommendations = _normalize_req_039_recommendations(raw.get('recommendations'))
    extra = sorted(set(raw.keys()) - {'analysis_type', 'now_utc', 'quality_policy', 'recommendations'})
    if extra:
        raise ValueError(f'payload has unexpected keys: {extra}')
    scored_recommendations: list[dict[str, Any]] = []
    accepted_recommendations: list[dict[str, Any]] = []
    rejected_recommendations: list[dict[str, Any]] = []
    recommendations_meeting_evidence_minimum = 0
    recommendations_meeting_tradeoff_minimum = 0
    for recommendation in recommendations:
        evidence_refs = list(recommendation['evidence_refs'])
        tradeoffs = list(recommendation['tradeoffs'])
        quality_score, score_breakdown = _req_039_quality_breakdown(evidence_ref_count=len(evidence_refs), tradeoff_count=len(tradeoffs), quality_policy=quality_policy)
        if score_breakdown['evidence_requirement_met']:
            recommendations_meeting_evidence_minimum += 1
        if score_breakdown['tradeoff_requirement_met']:
            recommendations_meeting_tradeoff_minimum += 1
        rejection_reason_codes: list[str] = []
        if not score_breakdown['evidence_requirement_met']:
            rejection_reason_codes.append('insufficient_evidence_refs')
        if not score_breakdown['tradeoff_requirement_met']:
            rejection_reason_codes.append('missing_explicit_tradeoffs')
        quality_status = 'accepted'
        if rejection_reason_codes or quality_score < quality_policy['passing_score']:
            quality_status = 'rejected'
        row = {'recommendation_id': recommendation['recommendation_id'], 'summary': recommendation['summary'], 'rationale': recommendation['rationale'], 'evidence_refs': evidence_refs, 'tradeoffs': tradeoffs, 'quality_score': quality_score, 'quality_status': quality_status, 'score_breakdown': score_breakdown, 'rejection_reason_codes': rejection_reason_codes}
        scored_recommendations.append(row)
        if quality_status == 'accepted':
            accepted_recommendations.append(row)
        else:
            rejected_recommendations.append(row)
    totals = {'recommendations': len(recommendations), 'accepted_recommendations': len(accepted_recommendations), 'rejected_recommendations': len(rejected_recommendations), 'recommendations_meeting_evidence_minimum': recommendations_meeting_evidence_minimum, 'recommendations_meeting_tradeoff_minimum': recommendations_meeting_tradeoff_minimum}
    output_payload = {'ok': True, 'schema_version': REQ_039_SCHEMA_VERSION, 'requirement_id': REQ_039_REQUIREMENT_ID, 'analysis_type': REQ_039_ANALYSIS_TYPE, 'call_id': REQ_039_CALL_ID, 'checked_at_utc': checked_at_utc, 'quality_policy': quality_policy, 'recommendations': recommendations, 'recommendation_rationale_quality_scoring': {'scored_recommendations': scored_recommendations, 'accepted_recommendations': accepted_recommendations, 'rejected_recommendations': rejected_recommendations}, 'totals': totals}
    errors = validate_req_039_recommendation_rationale_quality_scoring(output_payload)
    if errors:
        raise ValueError(f'built REQ-039 payload failed validation: {errors}')
    return output_payload

def validate_req_039_recommendation_rationale_quality_scoring(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-039 recommendation rationale quality scoring payload shape."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ['payload must be a JSON object']
    required_top = {'ok', 'schema_version', 'requirement_id', 'analysis_type', 'call_id', 'checked_at_utc', 'quality_policy', 'recommendations', 'recommendation_rationale_quality_scoring', 'totals'}
    top_keys = set(payload.keys())
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f'missing top-level keys: {missing_top}')
    unexpected_top = sorted(top_keys - required_top)
    if unexpected_top:
        errors.append(f'unexpected top-level keys: {unexpected_top}')
    if payload.get('ok') is not True:
        errors.append('ok must be true')
    if payload.get('schema_version') != REQ_039_SCHEMA_VERSION:
        errors.append(f'schema_version must be {REQ_039_SCHEMA_VERSION}')
    if payload.get('requirement_id') != REQ_039_REQUIREMENT_ID:
        errors.append(f'requirement_id must be {REQ_039_REQUIREMENT_ID}')
    if payload.get('analysis_type') != REQ_039_ANALYSIS_TYPE:
        errors.append(f'analysis_type must be {REQ_039_ANALYSIS_TYPE}')
    if payload.get('call_id') != REQ_039_CALL_ID:
        errors.append(f'call_id must be {REQ_039_CALL_ID}')
    if not isinstance(payload.get('checked_at_utc'), str) or not str(payload.get('checked_at_utc')).strip():
        errors.append('checked_at_utc must be a non-empty string')
    quality_policy = payload.get('quality_policy')
    minimum_evidence_ref_count = 0
    minimum_tradeoff_count = 0
    passing_score = 0
    if not isinstance(quality_policy, Mapping):
        errors.append('quality_policy must be an object')
    else:
        expected_policy_keys = {'minimum_evidence_ref_count', 'minimum_tradeoff_count', 'passing_score'}
        policy_keys = set(quality_policy.keys())
        missing_policy = sorted(expected_policy_keys - policy_keys)
        if missing_policy:
            errors.append(f'quality_policy missing keys: {missing_policy}')
        unexpected_policy = sorted(policy_keys - expected_policy_keys)
        if unexpected_policy:
            errors.append(f'quality_policy has unexpected keys: {unexpected_policy}')
        minimum_evidence_ref_count = quality_policy.get('minimum_evidence_ref_count', 0)
        if not isinstance(minimum_evidence_ref_count, int) or minimum_evidence_ref_count <= 0:
            errors.append('quality_policy.minimum_evidence_ref_count must be a positive integer')
            minimum_evidence_ref_count = 0
        minimum_tradeoff_count = quality_policy.get('minimum_tradeoff_count', 0)
        if not isinstance(minimum_tradeoff_count, int) or minimum_tradeoff_count <= 0:
            errors.append('quality_policy.minimum_tradeoff_count must be a positive integer')
            minimum_tradeoff_count = 0
        passing_score = quality_policy.get('passing_score', 0)
        if not isinstance(passing_score, int) or passing_score <= 0 or passing_score > 4:
            errors.append('quality_policy.passing_score must be an integer between 1 and 4')
            passing_score = 0
    recommendations = payload.get('recommendations')
    recommendation_ids: set[str] = set()
    if not isinstance(recommendations, list) or not recommendations:
        errors.append('recommendations must be a non-empty list')
        recommendations = []
    else:
        for idx, recommendation in enumerate(recommendations):
            if not isinstance(recommendation, Mapping):
                errors.append(f'recommendations[{idx}] must be an object')
                continue
            expected_keys = {'recommendation_id', 'summary', 'rationale', 'evidence_refs', 'tradeoffs'}
            recommendation_keys = set(recommendation.keys())
            missing_recommendation = sorted(expected_keys - recommendation_keys)
            if missing_recommendation:
                errors.append(f'recommendations[{idx}] missing keys: {missing_recommendation}')
            unexpected_recommendation = sorted(recommendation_keys - expected_keys)
            if unexpected_recommendation:
                errors.append(f'recommendations[{idx}] has unexpected keys: {unexpected_recommendation}')
            recommendation_id = recommendation.get('recommendation_id')
            if not isinstance(recommendation_id, str) or not recommendation_id.strip():
                errors.append(f'recommendations[{idx}].recommendation_id must be a non-empty string')
                recommendation_id = ''
            elif recommendation_id in recommendation_ids:
                errors.append(f'recommendations[{idx}].recommendation_id must be unique (duplicate: {recommendation_id})')
            else:
                recommendation_ids.add(recommendation_id)
            for key in ('summary', 'rationale'):
                value = recommendation.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f'recommendations[{idx}].{key} must be a non-empty string')
            for key in ('evidence_refs', 'tradeoffs'):
                values = recommendation.get(key)
                if not isinstance(values, list):
                    errors.append(f'recommendations[{idx}].{key} must be a list of strings')
                    continue
                for value_index, value in enumerate(values):
                    if not isinstance(value, str) or not value.strip():
                        errors.append(f'recommendations[{idx}].{key}[{value_index}] must be a non-empty string')
    scoring = payload.get('recommendation_rationale_quality_scoring')
    scored_ids: set[str] = set()
    accepted_ids: set[str] = set()
    rejected_ids: set[str] = set()
    recommendations_meeting_evidence_minimum = 0
    recommendations_meeting_tradeoff_minimum = 0
    if not isinstance(scoring, Mapping):
        errors.append('recommendation_rationale_quality_scoring must be an object')
    else:
        expected_scoring_keys = {'scored_recommendations', 'accepted_recommendations', 'rejected_recommendations'}
        scoring_keys = set(scoring.keys())
        missing_scoring = sorted(expected_scoring_keys - scoring_keys)
        if missing_scoring:
            errors.append(f'recommendation_rationale_quality_scoring missing keys: {missing_scoring}')
        unexpected_scoring = sorted(scoring_keys - expected_scoring_keys)
        if unexpected_scoring:
            errors.append(f'recommendation_rationale_quality_scoring has unexpected keys: {unexpected_scoring}')
        for bucket_name, id_sink in (('scored_recommendations', scored_ids), ('accepted_recommendations', accepted_ids), ('rejected_recommendations', rejected_ids)):
            rows = scoring.get(bucket_name)
            if not isinstance(rows, list):
                errors.append(f'recommendation_rationale_quality_scoring.{bucket_name} must be a list')
                continue
            for idx, row in enumerate(rows):
                if not isinstance(row, Mapping):
                    errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}] must be an object')
                    continue
                expected_row_keys = {'recommendation_id', 'summary', 'rationale', 'evidence_refs', 'tradeoffs', 'quality_score', 'quality_status', 'score_breakdown', 'rejection_reason_codes'}
                row_keys = set(row.keys())
                missing_row = sorted(expected_row_keys - row_keys)
                if missing_row:
                    errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}] missing keys: {missing_row}')
                unexpected_row = sorted(row_keys - expected_row_keys)
                if unexpected_row:
                    errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}] has unexpected keys: {unexpected_row}')
                recommendation_id = row.get('recommendation_id')
                if not isinstance(recommendation_id, str) or not recommendation_id.strip():
                    errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].recommendation_id must be a non-empty string')
                    recommendation_id = ''
                elif recommendation_ids and recommendation_id not in recommendation_ids:
                    errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].recommendation_id must exist in recommendations')
                elif recommendation_id in id_sink:
                    errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].recommendation_id must be unique within {bucket_name} (duplicate: {recommendation_id})')
                else:
                    id_sink.add(recommendation_id)
                for key in ('summary', 'rationale'):
                    value = row.get(key)
                    if not isinstance(value, str) or not value.strip():
                        errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].{key} must be a non-empty string')
                evidence_refs = row.get('evidence_refs')
                evidence_ref_count = 0
                if not isinstance(evidence_refs, list):
                    errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].evidence_refs must be a list of strings')
                else:
                    evidence_ref_count = len(evidence_refs)
                    for value_index, value in enumerate(evidence_refs):
                        if not isinstance(value, str) or not value.strip():
                            errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].evidence_refs[{value_index}] must be a non-empty string')
                tradeoffs = row.get('tradeoffs')
                tradeoff_count = 0
                if not isinstance(tradeoffs, list):
                    errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].tradeoffs must be a list of strings')
                else:
                    tradeoff_count = len(tradeoffs)
                    for value_index, value in enumerate(tradeoffs):
                        if not isinstance(value, str) or not value.strip():
                            errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].tradeoffs[{value_index}] must be a non-empty string')
                score_breakdown = row.get('score_breakdown')
                evidence_requirement_met = False
                tradeoff_requirement_met = False
                if not isinstance(score_breakdown, Mapping):
                    errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].score_breakdown must be an object')
                else:
                    expected_breakdown_keys = {'evidence_ref_count', 'evidence_requirement_met', 'tradeoff_count', 'tradeoff_requirement_met'}
                    breakdown_keys = set(score_breakdown.keys())
                    missing_breakdown = sorted(expected_breakdown_keys - breakdown_keys)
                    if missing_breakdown:
                        errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].score_breakdown missing keys: {missing_breakdown}')
                    unexpected_breakdown = sorted(breakdown_keys - expected_breakdown_keys)
                    if unexpected_breakdown:
                        errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].score_breakdown has unexpected keys: {unexpected_breakdown}')
                    breakdown_evidence_ref_count = score_breakdown.get('evidence_ref_count')
                    if not isinstance(breakdown_evidence_ref_count, int) or breakdown_evidence_ref_count < 0:
                        errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].score_breakdown.evidence_ref_count must be a non-negative integer')
                    elif isinstance(evidence_refs, list) and breakdown_evidence_ref_count != evidence_ref_count:
                        errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].score_breakdown.evidence_ref_count must equal len(evidence_refs)')
                    evidence_requirement_met = score_breakdown.get('evidence_requirement_met') is True
                    if not isinstance(score_breakdown.get('evidence_requirement_met'), bool):
                        errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].score_breakdown.evidence_requirement_met must be a boolean')
                    elif minimum_evidence_ref_count and evidence_requirement_met != (evidence_ref_count >= minimum_evidence_ref_count):
                        errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].score_breakdown.evidence_requirement_met must reflect quality_policy.minimum_evidence_ref_count')
                    breakdown_tradeoff_count = score_breakdown.get('tradeoff_count')
                    if not isinstance(breakdown_tradeoff_count, int) or breakdown_tradeoff_count < 0:
                        errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].score_breakdown.tradeoff_count must be a non-negative integer')
                    elif isinstance(tradeoffs, list) and breakdown_tradeoff_count != tradeoff_count:
                        errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].score_breakdown.tradeoff_count must equal len(tradeoffs)')
                    tradeoff_requirement_met = score_breakdown.get('tradeoff_requirement_met') is True
                    if not isinstance(score_breakdown.get('tradeoff_requirement_met'), bool):
                        errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].score_breakdown.tradeoff_requirement_met must be a boolean')
                    elif minimum_tradeoff_count and tradeoff_requirement_met != (tradeoff_count >= minimum_tradeoff_count):
                        errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].score_breakdown.tradeoff_requirement_met must reflect quality_policy.minimum_tradeoff_count')
                quality_score = row.get('quality_score')
                if not isinstance(quality_score, int) or quality_score < 0 or quality_score > 4:
                    errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].quality_score must be an integer between 0 and 4')
                else:
                    expected_quality_score = (2 if evidence_requirement_met else 1 if evidence_ref_count > 0 else 0) + (2 if tradeoff_requirement_met else 0)
                    if quality_score != expected_quality_score:
                        errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].quality_score must equal deterministic evidence/tradeoff score')
                quality_status = row.get('quality_status')
                if quality_status not in _REQ_039_QUALITY_STATUSES:
                    errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].quality_status must be one of: {list(_REQ_039_QUALITY_STATUSES)}')
                expected_rejection_reason_codes: list[str] = []
                if minimum_evidence_ref_count and evidence_ref_count < minimum_evidence_ref_count:
                    expected_rejection_reason_codes.append('insufficient_evidence_refs')
                if minimum_tradeoff_count and tradeoff_count < minimum_tradeoff_count:
                    expected_rejection_reason_codes.append('missing_explicit_tradeoffs')
                rejection_reason_codes = row.get('rejection_reason_codes')
                if not isinstance(rejection_reason_codes, list):
                    errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].rejection_reason_codes must be a list of strings')
                    rejection_reason_codes = []
                else:
                    for value_index, value in enumerate(rejection_reason_codes):
                        if not isinstance(value, str) or not value.strip():
                            errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].rejection_reason_codes[{value_index}] must be a non-empty string')
                        elif value not in _REQ_039_REJECTION_REASON_CODES:
                            errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].rejection_reason_codes[{value_index}] must be one of: {list(_REQ_039_REJECTION_REASON_CODES)}')
                if sorted(rejection_reason_codes) != expected_rejection_reason_codes:
                    errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].rejection_reason_codes must match deterministic threshold failures')
                expected_status = 'accepted' if not expected_rejection_reason_codes and isinstance(quality_score, int) and (quality_score >= passing_score) else 'rejected'
                if quality_status in _REQ_039_QUALITY_STATUSES and quality_status != expected_status:
                    errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}].quality_status must match threshold outcomes')
                if bucket_name == 'accepted_recommendations' and quality_status == 'rejected':
                    errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}] must not contain rejected recommendations')
                if bucket_name == 'rejected_recommendations' and quality_status == 'accepted':
                    errors.append(f'recommendation_rationale_quality_scoring.{bucket_name}[{idx}] must not contain accepted recommendations')
                if bucket_name == 'scored_recommendations':
                    if evidence_requirement_met:
                        recommendations_meeting_evidence_minimum += 1
                    if tradeoff_requirement_met:
                        recommendations_meeting_tradeoff_minimum += 1
    if scored_ids and recommendation_ids and (scored_ids != recommendation_ids):
        errors.append('recommendation_rationale_quality_scoring.scored_recommendations must cover all recommendations')
    if accepted_ids and rejected_ids and accepted_ids & rejected_ids:
        errors.append('accepted_recommendations and rejected_recommendations must be disjoint')
    if scored_ids:
        if accepted_ids | rejected_ids != scored_ids:
            errors.append('accepted_recommendations and rejected_recommendations must partition scored_recommendations')
    totals = payload.get('totals')
    if not isinstance(totals, Mapping):
        errors.append('totals must be an object')
    else:
        expected_totals = {'recommendations', 'accepted_recommendations', 'rejected_recommendations', 'recommendations_meeting_evidence_minimum', 'recommendations_meeting_tradeoff_minimum'}
        total_keys = set(totals.keys())
        missing_totals = sorted(expected_totals - total_keys)
        if missing_totals:
            errors.append(f'totals missing keys: {missing_totals}')
        unexpected_totals = sorted(total_keys - expected_totals)
        if unexpected_totals:
            errors.append(f'totals has unexpected keys: {unexpected_totals}')
        for key in expected_totals:
            value = totals.get(key)
            if not isinstance(value, int) or value < 0:
                errors.append(f'totals.{key} must be a non-negative integer')
        if isinstance(totals.get('recommendations'), int) and recommendation_ids:
            if totals['recommendations'] != len(recommendation_ids):
                errors.append('totals.recommendations must equal len(recommendations)')
        if isinstance(totals.get('accepted_recommendations'), int) and accepted_ids:
            if totals['accepted_recommendations'] != len(accepted_ids):
                errors.append('totals.accepted_recommendations must equal len(accepted_recommendations)')
        if isinstance(totals.get('rejected_recommendations'), int) and rejected_ids:
            if totals['rejected_recommendations'] != len(rejected_ids):
                errors.append('totals.rejected_recommendations must equal len(rejected_recommendations)')
        if isinstance(totals.get('recommendations_meeting_evidence_minimum'), int) and scored_ids:
            if totals['recommendations_meeting_evidence_minimum'] != recommendations_meeting_evidence_minimum:
                errors.append('totals.recommendations_meeting_evidence_minimum must equal scored recommendations meeting the evidence minimum')
        if isinstance(totals.get('recommendations_meeting_tradeoff_minimum'), int) and scored_ids:
            if totals['recommendations_meeting_tradeoff_minimum'] != recommendations_meeting_tradeoff_minimum:
                errors.append('totals.recommendations_meeting_tradeoff_minimum must equal scored recommendations meeting the tradeoff minimum')
    return errors

def build_req_047_llm_call_trace_and_decision_ledger(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build normalized REQ-047 payload for trace + decision-ledger auditability."""
    raw = _require_mapping(payload, field_name='payload')
    analysis_type = str(raw.get('analysis_type') or '').strip()
    if analysis_type and analysis_type != REQ_047_ANALYSIS_TYPE:
        raise ValueError(f'analysis_type must be {REQ_047_ANALYSIS_TYPE}')
    allowed_top = {'analysis_type', 'now_utc', 'llm_call_trace_rows', 'final_output_artifacts', 'decision_ledger'}
    extra_top = sorted(set(raw.keys()) - allowed_top)
    if extra_top:
        raise ValueError(f'payload has unexpected keys: {extra_top}')
    checked_at_utc = _require_nonempty_text(raw.get('now_utc'), field_name='now_utc')
    llm_call_trace_rows = _normalize_req_047_trace_rows(raw.get('llm_call_trace_rows'))
    final_output_artifacts = _normalize_req_047_final_output_artifacts(raw.get('final_output_artifacts'))
    call_refs = [row['call_ref'] for row in llm_call_trace_rows]
    decision_ledger = _normalize_req_047_decision_ledger(raw.get('decision_ledger'), known_call_refs=set(call_refs), known_artifact_refs={row['artifact_ref'] for row in final_output_artifacts})
    linked_refs_by_call = _req_047_linked_artifact_refs_by_call(call_refs=call_refs, decision_ledger=decision_ledger)
    normalized_trace_rows = [{**row, 'linked_final_output_artifact_refs': linked_refs_by_call[row['call_ref']]} for row in llm_call_trace_rows]
    for row in normalized_trace_rows:
        if not row['linked_final_output_artifact_refs']:
            raise ValueError(f"llm_call_trace_rows.call_ref={row['call_ref']} must be linked to at least one final_output_artifact_ref")
    traceability_index = _req_047_traceability_index(final_output_artifacts=final_output_artifacts, decision_ledger=decision_ledger)
    for row in traceability_index:
        if not row['decision_ids']:
            raise ValueError(f"final_output_artifacts.artifact_ref={row['final_output_artifact_ref']} must be referenced by at least one decision_ledger entry")
    output_payload = {'ok': True, 'schema_version': REQ_047_SCHEMA_VERSION, 'requirement_id': REQ_047_REQUIREMENT_ID, 'analysis_type': REQ_047_ANALYSIS_TYPE, 'call_id': REQ_047_CALL_ID, 'checked_at_utc': checked_at_utc, 'llm_call_trace_rows': normalized_trace_rows, 'final_output_artifacts': final_output_artifacts, 'llm_call_trace_and_decision_ledger': {'call_objective': _REQ_047_CALL_OBJECTIVE, 'decision_ledger': decision_ledger, 'traceability_index': traceability_index}, 'totals': {'llm_call_trace_rows': len(normalized_trace_rows), 'final_output_artifacts': len(final_output_artifacts), 'decision_ledger_entries': len(decision_ledger), 'linked_llm_call_trace_rows': sum((1 for row in normalized_trace_rows if row['linked_final_output_artifact_refs'])), 'linked_final_output_artifacts': sum((1 for row in traceability_index if row['decision_ids']))}}
    errors = validate_req_047_llm_call_trace_and_decision_ledger(output_payload)
    if errors:
        raise ValueError(f'built REQ-047 payload failed validation: {errors}')
    return output_payload

def validate_req_047_llm_call_trace_and_decision_ledger(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-047 trace/decision-ledger payload shape."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ['payload must be a JSON object']
    required_top = {'ok', 'schema_version', 'requirement_id', 'analysis_type', 'call_id', 'checked_at_utc', 'llm_call_trace_rows', 'final_output_artifacts', 'llm_call_trace_and_decision_ledger', 'totals'}
    top_keys = set(payload.keys())
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f'missing top-level keys: {missing_top}')
    unexpected_top = sorted(top_keys - required_top)
    if unexpected_top:
        errors.append(f'unexpected top-level keys: {unexpected_top}')
    if payload.get('ok') is not True:
        errors.append('ok must be true')
    if payload.get('schema_version') != REQ_047_SCHEMA_VERSION:
        errors.append(f'schema_version must be {REQ_047_SCHEMA_VERSION}')
    if payload.get('requirement_id') != REQ_047_REQUIREMENT_ID:
        errors.append(f'requirement_id must be {REQ_047_REQUIREMENT_ID}')
    if payload.get('analysis_type') != REQ_047_ANALYSIS_TYPE:
        errors.append(f'analysis_type must be {REQ_047_ANALYSIS_TYPE}')
    if payload.get('call_id') != REQ_047_CALL_ID:
        errors.append(f'call_id must be {REQ_047_CALL_ID}')
    if not isinstance(payload.get('checked_at_utc'), str) or not str(payload.get('checked_at_utc')).strip():
        errors.append('checked_at_utc must be a non-empty string')
    final_output_artifacts = payload.get('final_output_artifacts')
    normalized_final_output_artifacts: list[dict[str, str]] = []
    artifact_refs: set[str] = set()
    artifact_roles_by_ref: dict[str, str] = {}
    if not isinstance(final_output_artifacts, list) or not final_output_artifacts:
        errors.append('final_output_artifacts must be a non-empty list')
        final_output_artifacts = []
    else:
        for index, item in enumerate(final_output_artifacts):
            if not isinstance(item, Mapping):
                errors.append(f'final_output_artifacts[{index}] must be an object')
                continue
            expected_keys = {'artifact_ref', 'artifact_role', 'sha256'}
            keys = set(item.keys())
            missing = sorted(expected_keys - keys)
            if missing:
                errors.append(f'final_output_artifacts[{index}] missing keys: {missing}')
            extra = sorted(keys - expected_keys)
            if extra:
                errors.append(f'final_output_artifacts[{index}] has unexpected keys: {extra}')
            artifact_ref = item.get('artifact_ref')
            if not isinstance(artifact_ref, str) or not artifact_ref.strip():
                errors.append(f'final_output_artifacts[{index}].artifact_ref must be a non-empty string')
                continue
            artifact_role = item.get('artifact_role')
            if not isinstance(artifact_role, str) or not artifact_role.strip():
                errors.append(f'final_output_artifacts[{index}].artifact_role must be a non-empty string')
                continue
            sha256 = item.get('sha256')
            if not isinstance(sha256, str) or not _is_lower_hex(sha256, length=64):
                errors.append(f'final_output_artifacts[{index}].sha256 must be a lowercase 64-character sha256 hex digest')
                continue
            if artifact_ref in artifact_refs:
                errors.append(f'final_output_artifacts[{index}].artifact_ref must be unique (duplicate: {artifact_ref})')
            artifact_refs.add(artifact_ref)
            artifact_roles_by_ref[artifact_ref] = artifact_role
            normalized_final_output_artifacts.append({'artifact_ref': artifact_ref, 'artifact_role': artifact_role, 'sha256': sha256})
        if normalized_final_output_artifacts != sorted(normalized_final_output_artifacts, key=lambda row: (row['artifact_role'], row['artifact_ref'])):
            errors.append('final_output_artifacts must be sorted by artifact_role, artifact_ref')
    llm_call_trace_rows = payload.get('llm_call_trace_rows')
    call_refs: set[str] = set()
    linked_refs_by_call: dict[str, list[str]] = {}
    if not isinstance(llm_call_trace_rows, list) or not llm_call_trace_rows:
        errors.append('llm_call_trace_rows must be a non-empty list')
        llm_call_trace_rows = []
    else:
        for index, item in enumerate(llm_call_trace_rows):
            if not isinstance(item, Mapping):
                errors.append(f'llm_call_trace_rows[{index}] must be an object')
                continue
            expected_keys = {'schema_version', 'checked_at_utc', 'requirement_id', 'analysis_type', 'call_id', 'call_ref', 'call_objective', 'target_project_id', 'peer_project_ids', 'input_refs', 'output_refs', 'artifacts', 'handoff_summary', 'totals', 'linked_final_output_artifact_refs'}
            keys = set(item.keys())
            missing = sorted(expected_keys - keys)
            if missing:
                errors.append(f'llm_call_trace_rows[{index}] missing keys: {missing}')
            extra = sorted(keys - expected_keys)
            if extra:
                errors.append(f'llm_call_trace_rows[{index}] has unexpected keys: {extra}')
            if item.get('schema_version') != _LLM_CALL_TRACE_SCHEMA_VERSION:
                errors.append(f'llm_call_trace_rows[{index}].schema_version must be {_LLM_CALL_TRACE_SCHEMA_VERSION}')
            requirement_id = item.get('requirement_id')
            analysis_type = item.get('analysis_type')
            call_id = item.get('call_id')
            if not isinstance(requirement_id, str) or not requirement_id.strip():
                errors.append(f'llm_call_trace_rows[{index}].requirement_id must be a non-empty string')
                requirement_id = ''
            if not isinstance(analysis_type, str) or not analysis_type.strip():
                errors.append(f'llm_call_trace_rows[{index}].analysis_type must be a non-empty string')
            if not isinstance(call_id, str) or not call_id.strip():
                errors.append(f'llm_call_trace_rows[{index}].call_id must be a non-empty string')
                call_id = ''
            call_ref = item.get('call_ref')
            expected_call_ref = _req_047_call_ref(requirement_id=str(requirement_id), call_id=str(call_id))
            if call_ref != expected_call_ref:
                errors.append(f'llm_call_trace_rows[{index}].call_ref must equal {expected_call_ref}')
                call_ref = expected_call_ref
            if call_ref in call_refs:
                errors.append(f'llm_call_trace_rows[{index}].call_ref must be unique (duplicate: {call_ref})')
            call_refs.add(str(call_ref))
            for key in ('checked_at_utc', 'call_objective', 'target_project_id', 'handoff_summary'):
                value = item.get(key)
                if key == 'target_project_id':
                    if not isinstance(value, str):
                        errors.append(f'llm_call_trace_rows[{index}].{key} must be a string')
                    continue
                if not isinstance(value, str) or not value.strip():
                    errors.append(f'llm_call_trace_rows[{index}].{key} must be a non-empty string')
            for key in ('peer_project_ids', 'input_refs', 'output_refs', 'linked_final_output_artifact_refs'):
                values = item.get(key)
                if not isinstance(values, list):
                    errors.append(f'llm_call_trace_rows[{index}].{key} must be a list')
                    continue
                if key in {'input_refs', 'output_refs', 'linked_final_output_artifact_refs'} and (not values):
                    errors.append(f'llm_call_trace_rows[{index}].{key} must be a non-empty list')
                    continue
                for value_index, value in enumerate(values):
                    if not isinstance(value, str) or not value.strip():
                        errors.append(f'llm_call_trace_rows[{index}].{key}[{value_index}] must be a non-empty string')
                    elif key == 'linked_final_output_artifact_refs' and value not in artifact_refs:
                        errors.append(f'llm_call_trace_rows[{index}].{key}[{value_index}] must reference final_output_artifacts.artifact_ref')
                if values != sorted(set(values)):
                    errors.append(f'llm_call_trace_rows[{index}].{key} must be sorted unique strings')
                if key == 'linked_final_output_artifact_refs':
                    linked_refs_by_call[str(call_ref)] = [str(value) for value in values if isinstance(value, str) and value.strip()]
            artifacts = item.get('artifacts')
            if not isinstance(artifacts, list) or not artifacts:
                errors.append(f'llm_call_trace_rows[{index}].artifacts must be a non-empty list')
            else:
                normalized_artifacts: list[dict[str, str]] = []
                for artifact_index, artifact in enumerate(artifacts):
                    if not isinstance(artifact, Mapping):
                        errors.append(f'llm_call_trace_rows[{index}].artifacts[{artifact_index}] must be an object')
                        continue
                    expected_artifact_keys = {'kind', 'path', 'sha256'}
                    artifact_keys = set(artifact.keys())
                    missing_artifact = sorted(expected_artifact_keys - artifact_keys)
                    if missing_artifact:
                        errors.append(f'llm_call_trace_rows[{index}].artifacts[{artifact_index}] missing keys: {missing_artifact}')
                    extra_artifact = sorted(artifact_keys - expected_artifact_keys)
                    if extra_artifact:
                        errors.append(f'llm_call_trace_rows[{index}].artifacts[{artifact_index}] has unexpected keys: {extra_artifact}')
                    kind = artifact.get('kind')
                    path = artifact.get('path')
                    sha256 = artifact.get('sha256')
                    if not isinstance(kind, str) or not kind.strip():
                        errors.append(f'llm_call_trace_rows[{index}].artifacts[{artifact_index}].kind must be a non-empty string')
                        continue
                    if not isinstance(path, str) or not path.strip():
                        errors.append(f'llm_call_trace_rows[{index}].artifacts[{artifact_index}].path must be a non-empty string')
                        continue
                    if not isinstance(sha256, str) or not _is_lower_hex(sha256, length=64):
                        errors.append(f'llm_call_trace_rows[{index}].artifacts[{artifact_index}].sha256 must be a lowercase 64-character sha256 hex digest')
                        continue
                    normalized_artifacts.append({'kind': kind, 'path': path, 'sha256': sha256})
                if normalized_artifacts != sorted(normalized_artifacts, key=lambda row: (row['kind'], row['path'], row['sha256'])):
                    errors.append(f'llm_call_trace_rows[{index}].artifacts must be sorted by kind, path, sha256')
            totals = item.get('totals')
            if not isinstance(totals, Mapping) or not totals:
                errors.append(f'llm_call_trace_rows[{index}].totals must be a non-empty object')
            else:
                for total_key in totals.keys():
                    if not isinstance(total_key, str) or not total_key.strip():
                        errors.append(f'llm_call_trace_rows[{index}].totals keys must be non-empty strings')
                        continue
                    count = totals[total_key]
                    if not isinstance(count, int) or count < 0:
                        errors.append(f'llm_call_trace_rows[{index}].totals.{total_key} must be a non-negative integer')
        normalized_call_refs = [str(row.get('call_ref') or '') for row in llm_call_trace_rows if isinstance(row, Mapping)]
        if normalized_call_refs != sorted(normalized_call_refs):
            errors.append('llm_call_trace_rows must be sorted by call_ref')
    ledger = payload.get('llm_call_trace_and_decision_ledger')
    decision_ledger: list[dict[str, Any]] = []
    traceability_index: list[dict[str, Any]] = []
    if not isinstance(ledger, Mapping):
        errors.append('llm_call_trace_and_decision_ledger must be an object')
    else:
        expected_ledger_keys = {'call_objective', 'decision_ledger', 'traceability_index'}
        ledger_keys = set(ledger.keys())
        missing_ledger = sorted(expected_ledger_keys - ledger_keys)
        if missing_ledger:
            errors.append(f'llm_call_trace_and_decision_ledger missing keys: {missing_ledger}')
        unexpected_ledger = sorted(ledger_keys - expected_ledger_keys)
        if unexpected_ledger:
            errors.append(f'llm_call_trace_and_decision_ledger has unexpected keys: {unexpected_ledger}')
        if ledger.get('call_objective') != _REQ_047_CALL_OBJECTIVE:
            errors.append('llm_call_trace_and_decision_ledger.call_objective must match the REQ-047 contract objective')
        raw_decision_ledger = ledger.get('decision_ledger')
        if not isinstance(raw_decision_ledger, list) or not raw_decision_ledger:
            errors.append('llm_call_trace_and_decision_ledger.decision_ledger must be a non-empty list')
            raw_decision_ledger = []
        else:
            for index, item in enumerate(raw_decision_ledger):
                if not isinstance(item, Mapping):
                    errors.append(f'llm_call_trace_and_decision_ledger.decision_ledger[{index}] must be an object')
                    continue
                expected_keys = {'decision_id', 'decision_type', 'summary', 'rationale', 'source_call_refs', 'final_output_artifact_refs', 'evidence_refs'}
                keys = set(item.keys())
                missing = sorted(expected_keys - keys)
                if missing:
                    errors.append(f'llm_call_trace_and_decision_ledger.decision_ledger[{index}] missing keys: {missing}')
                extra = sorted(keys - expected_keys)
                if extra:
                    errors.append(f'llm_call_trace_and_decision_ledger.decision_ledger[{index}] has unexpected keys: {extra}')
                decision_id = item.get('decision_id')
                decision_type = item.get('decision_type')
                if not isinstance(decision_id, str) or not decision_id.strip():
                    errors.append(f'llm_call_trace_and_decision_ledger.decision_ledger[{index}].decision_id must be a non-empty string')
                    continue
                if not isinstance(decision_type, str) or decision_type not in _REQ_047_DECISION_TYPES:
                    errors.append(f'llm_call_trace_and_decision_ledger.decision_ledger[{index}].decision_type must be one of: {list(_REQ_047_DECISION_TYPES)}')
                    continue
                for key in ('summary', 'rationale'):
                    value = item.get(key)
                    if not isinstance(value, str) or not value.strip():
                        errors.append(f'llm_call_trace_and_decision_ledger.decision_ledger[{index}].{key} must be a non-empty string')
                for key in ('source_call_refs', 'final_output_artifact_refs', 'evidence_refs'):
                    values = item.get(key)
                    if not isinstance(values, list) or not values:
                        errors.append(f'llm_call_trace_and_decision_ledger.decision_ledger[{index}].{key} must be a non-empty list')
                        continue
                    for value_index, value in enumerate(values):
                        if not isinstance(value, str) or not value.strip():
                            errors.append(f'llm_call_trace_and_decision_ledger.decision_ledger[{index}].{key}[{value_index}] must be a non-empty string')
                        elif key == 'source_call_refs' and value not in call_refs:
                            errors.append(f'llm_call_trace_and_decision_ledger.decision_ledger[{index}].{key}[{value_index}] must reference llm_call_trace_rows.call_ref')
                        elif key == 'final_output_artifact_refs' and value not in artifact_refs:
                            errors.append(f'llm_call_trace_and_decision_ledger.decision_ledger[{index}].{key}[{value_index}] must reference final_output_artifacts.artifact_ref')
                    if values != sorted(set(values)):
                        errors.append(f'llm_call_trace_and_decision_ledger.decision_ledger[{index}].{key} must be sorted unique strings')
                decision_ledger.append({'decision_id': decision_id, 'decision_type': decision_type, 'summary': str(item.get('summary') or ''), 'rationale': str(item.get('rationale') or ''), 'source_call_refs': [str(value) for value in item.get('source_call_refs', []) if isinstance(value, str) and value.strip()], 'final_output_artifact_refs': [str(value) for value in item.get('final_output_artifact_refs', []) if isinstance(value, str) and value.strip()], 'evidence_refs': [str(value) for value in item.get('evidence_refs', []) if isinstance(value, str) and value.strip()]})
            if decision_ledger != sorted(decision_ledger, key=lambda row: row['decision_id']):
                errors.append('llm_call_trace_and_decision_ledger.decision_ledger must be sorted by decision_id')
        raw_traceability_index = ledger.get('traceability_index')
        if not isinstance(raw_traceability_index, list) or not raw_traceability_index:
            errors.append('llm_call_trace_and_decision_ledger.traceability_index must be a non-empty list')
            raw_traceability_index = []
        else:
            for index, item in enumerate(raw_traceability_index):
                if not isinstance(item, Mapping):
                    errors.append(f'llm_call_trace_and_decision_ledger.traceability_index[{index}] must be an object')
                    continue
                expected_keys = {'final_output_artifact_ref', 'artifact_role', 'decision_ids', 'source_call_refs'}
                keys = set(item.keys())
                missing = sorted(expected_keys - keys)
                if missing:
                    errors.append(f'llm_call_trace_and_decision_ledger.traceability_index[{index}] missing keys: {missing}')
                extra = sorted(keys - expected_keys)
                if extra:
                    errors.append(f'llm_call_trace_and_decision_ledger.traceability_index[{index}] has unexpected keys: {extra}')
                artifact_ref = item.get('final_output_artifact_ref')
                artifact_role = item.get('artifact_role')
                decision_ids = item.get('decision_ids')
                source_call_refs = item.get('source_call_refs')
                if not isinstance(artifact_ref, str) or artifact_ref not in artifact_refs:
                    errors.append(f'llm_call_trace_and_decision_ledger.traceability_index[{index}].final_output_artifact_ref must reference final_output_artifacts.artifact_ref')
                if not isinstance(artifact_role, str) or artifact_role != artifact_roles_by_ref.get(str(artifact_ref)):
                    errors.append(f'llm_call_trace_and_decision_ledger.traceability_index[{index}].artifact_role must match final_output_artifacts for final_output_artifact_ref')
                if not isinstance(decision_ids, list) or not decision_ids:
                    errors.append(f'llm_call_trace_and_decision_ledger.traceability_index[{index}].decision_ids must be a non-empty list')
                elif decision_ids != sorted(set(decision_ids)):
                    errors.append(f'llm_call_trace_and_decision_ledger.traceability_index[{index}].decision_ids must be sorted unique strings')
                if not isinstance(source_call_refs, list) or not source_call_refs:
                    errors.append(f'llm_call_trace_and_decision_ledger.traceability_index[{index}].source_call_refs must be a non-empty list')
                else:
                    for value_index, value in enumerate(source_call_refs):
                        if not isinstance(value, str) or value not in call_refs:
                            errors.append(f'llm_call_trace_and_decision_ledger.traceability_index[{index}].source_call_refs[{value_index}] must reference llm_call_trace_rows.call_ref')
                    if source_call_refs != sorted(set(source_call_refs)):
                        errors.append(f'llm_call_trace_and_decision_ledger.traceability_index[{index}].source_call_refs must be sorted unique strings')
                traceability_index.append({'final_output_artifact_ref': str(artifact_ref or ''), 'artifact_role': str(artifact_role or ''), 'decision_ids': [str(value) for value in decision_ids or [] if isinstance(value, str) and value.strip()], 'source_call_refs': [str(value) for value in source_call_refs or [] if isinstance(value, str) and value.strip()]})
            if traceability_index != sorted(traceability_index, key=lambda row: (row['artifact_role'], row['final_output_artifact_ref'])):
                errors.append('llm_call_trace_and_decision_ledger.traceability_index must be sorted by artifact_role, final_output_artifact_ref')
    if decision_ledger:
        expected_linked_refs_by_call = _req_047_linked_artifact_refs_by_call(call_refs=sorted(call_refs), decision_ledger=decision_ledger)
        for index, item in enumerate(llm_call_trace_rows):
            if not isinstance(item, Mapping):
                continue
            call_ref = str(item.get('call_ref') or '')
            if linked_refs_by_call.get(call_ref, []) != expected_linked_refs_by_call.get(call_ref, []):
                errors.append(f'llm_call_trace_rows[{index}].linked_final_output_artifact_refs must equal decision-ledger artifact union for {call_ref}')
        expected_traceability_index = _req_047_traceability_index(final_output_artifacts=normalized_final_output_artifacts, decision_ledger=decision_ledger)
        if traceability_index != expected_traceability_index:
            errors.append('llm_call_trace_and_decision_ledger.traceability_index must equal the deterministic artifact linkage index')
    totals = payload.get('totals')
    if not isinstance(totals, Mapping):
        errors.append('totals must be an object')
    else:
        expected_totals = {'llm_call_trace_rows', 'final_output_artifacts', 'decision_ledger_entries', 'linked_llm_call_trace_rows', 'linked_final_output_artifacts'}
        total_keys = set(totals.keys())
        missing_totals = sorted(expected_totals - total_keys)
        if missing_totals:
            errors.append(f'totals missing keys: {missing_totals}')
        unexpected_totals = sorted(total_keys - expected_totals)
        if unexpected_totals:
            errors.append(f'totals has unexpected keys: {unexpected_totals}')
        for key in expected_totals:
            value = totals.get(key)
            if not isinstance(value, int) or value < 0:
                errors.append(f'totals.{key} must be a non-negative integer')
        if isinstance(totals.get('llm_call_trace_rows'), int) and totals.get('llm_call_trace_rows') != len(llm_call_trace_rows):
            errors.append('totals.llm_call_trace_rows must equal len(llm_call_trace_rows)')
        if isinstance(totals.get('final_output_artifacts'), int) and totals.get('final_output_artifacts') != len(final_output_artifacts):
            errors.append('totals.final_output_artifacts must equal len(final_output_artifacts)')
        if isinstance(totals.get('decision_ledger_entries'), int) and totals.get('decision_ledger_entries') != len(decision_ledger):
            errors.append('totals.decision_ledger_entries must equal len(llm_call_trace_and_decision_ledger.decision_ledger)')
        linked_rows = sum((1 for refs in linked_refs_by_call.values() if refs))
        if isinstance(totals.get('linked_llm_call_trace_rows'), int) and totals.get('linked_llm_call_trace_rows') != linked_rows:
            errors.append('totals.linked_llm_call_trace_rows must equal the number of llm_call_trace_rows with linked_final_output_artifact_refs')
        linked_artifacts = sum((1 for row in traceability_index if row['decision_ids']))
        if isinstance(totals.get('linked_final_output_artifacts'), int) and totals.get('linked_final_output_artifacts') != linked_artifacts:
            errors.append('totals.linked_final_output_artifacts must equal the number of traceability_index rows with decision_ids')
    return errors


def _stable_id_fragment(*parts: str) -> str:
    raw = '|'.join(parts)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:12]


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _format_ts_line(message: str, *, now_utc: str | None = None) -> str:
    stamp = now_utc.strip() if isinstance(now_utc, str) and now_utc.strip() else _utc_timestamp()
    return f'[{stamp}] {message}'


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_llm_call_trace_path() -> Path:
    return _repo_root() / _LLM_CALL_TRACE_RELATIVE_PATH


def _default_llm_call_trace_artifacts_dir() -> Path:
    return _repo_root() / _LLM_CALL_TRACE_ARTIFACTS_RELATIVE_DIR


def _repo_relative_path(path: Path) -> str:
    return path.resolve().relative_to(_repo_root()).as_posix()


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def _sha256_hex(payload: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _canonicalize(payload: Any) -> Any:
    return json.loads(_canonical_json_bytes(payload).decode('utf-8'))


def _write_json_artifact(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + '\n',
        encoding='utf-8',
    )


def _append_jsonl_row(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n')


def _best_effort_extract_string_refs(raw_value: Any) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, str):
        ref = raw_value.strip()
        return [ref] if ref else []
    if isinstance(raw_value, list):
        out: list[str] = []
        for item in raw_value:
            if item is None:
                continue
            ref = str(item).strip()
            if ref:
                out.append(ref)
        return out
    return []


def _trace_input_refs(
    *,
    earth_sweep_evidence_refs: list[str],
    cross_project_context: list[dict[str, Any]],
    earth_sweep_projects: list[dict[str, Any]],
) -> list[str]:
    refs: set[str] = set()
    refs.update(earth_sweep_evidence_refs)
    for row in cross_project_context:
        refs.update(_best_effort_extract_string_refs(row.get('evidence_refs')))
    for project in earth_sweep_projects:
        for obligation in project.get('obligations') or []:
            if not isinstance(obligation, Mapping):
                continue
            refs.update(_best_effort_extract_string_refs(obligation.get('earth_sweep_evidence_refs')))
            refs.update(_best_effort_extract_string_refs(obligation.get('evidence_refs')))
        for idea in project.get('unresolved_ideas') or []:
            if not isinstance(idea, Mapping):
                continue
            refs.update(_best_effort_extract_string_refs(idea.get('evidence_refs')))
    return sorted(refs)


def _collect_unique_refs(*lists: list[str]) -> list[str]:
    out: set[str] = set()
    for items in lists:
        out.update([str(item) for item in items if str(item).strip()])
    return sorted(out)


def _normalize_cross_project_context(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError('cross_project_context must be a list')
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_value):
        row = _require_mapping(item, field_name=f'cross_project_context[{index}]')
        project_id = _require_nonempty_text(row.get('project_id'), field_name=f'cross_project_context[{index}].project_id')
        project_root = _require_nonempty_text(row.get('project_root'), field_name=f'cross_project_context[{index}].project_root')
        evidence_refs = _normalize_string_list(row.get('evidence_refs'), field_name=f'cross_project_context[{index}].evidence_refs')
        context_note = str(row.get('context_note') or '').strip()
        extra = sorted(set(row.keys()) - {'project_id', 'project_root', 'evidence_refs', 'context_note'})
        if extra:
            raise ValueError(f'cross_project_context[{index}] has unexpected keys: {extra}')
        normalized.append(
            {
                'project_id': project_id,
                'project_root': project_root,
                'evidence_refs': evidence_refs,
                'context_note': context_note,
            }
        )
    normalized.sort(key=lambda row: (row['project_id'], row['project_root']))
    return normalized


def _normalize_req_039_analysis_synthesis_citation_status(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError('analysis_synthesis_citation_status must be a list')
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_value):
        row = _require_mapping(item, field_name=f'analysis_synthesis_citation_status[{index}]')
        strategic_claim_id = _require_nonempty_text(
            row.get('strategic_claim_id'),
            field_name=f'analysis_synthesis_citation_status[{index}].strategic_claim_id',
        )
        call_id = _require_nonempty_text(
            row.get('call_id'),
            field_name=f'analysis_synthesis_citation_status[{index}].call_id',
        )
        recommendation_id = _require_nonempty_text(
            row.get('recommendation_id'),
            field_name=f'analysis_synthesis_citation_status[{index}].recommendation_id',
        )
        citation_status = _require_nonempty_text(
            row.get('citation_status'),
            field_name=f'analysis_synthesis_citation_status[{index}].citation_status',
        ).lower()
        if citation_status not in {'cited', 'uncited'}:
            raise ValueError(
                f"analysis_synthesis_citation_status[{index}].citation_status must be one of: ['cited', 'uncited']"
            )
        summary = str(row.get('summary') or '').strip()
        evidence_refs = _normalize_string_list(
            row.get('evidence_refs'),
            field_name=f'analysis_synthesis_citation_status[{index}].evidence_refs',
        )
        normalized_row = {
            'strategic_claim_id': strategic_claim_id,
            'call_id': call_id,
            'recommendation_id': recommendation_id,
            'citation_status': citation_status,
            'summary': summary,
            'evidence_refs': evidence_refs,
        }
        extra = sorted(set(row.keys()) - set(normalized_row.keys()))
        if extra:
            raise ValueError(f'analysis_synthesis_citation_status[{index}] has unexpected keys: {extra}')
        normalized.append(normalized_row)
    normalized.sort(key=lambda row: (row['strategic_claim_id'], row['call_id'], row['recommendation_id']))
    return normalized


def _extract_earth_sweep_inputs(raw_value: Any) -> tuple[list[str], list[dict[str, Any]]]:
    if raw_value is None:
        return ([], [])
    broad = _require_mapping(raw_value, field_name='broad_sweep_context')
    evidence_refs: list[str] = []
    earth_sweep_projects: list[dict[str, Any]] = []
    if broad.get('earth_sweep_evidence_refs') is not None:
        evidence_refs = _normalize_string_list(
            broad.get('earth_sweep_evidence_refs'),
            field_name='broad_sweep_context.earth_sweep_evidence_refs',
        )
    earth_sweep = broad.get('earth_sweep')
    if earth_sweep is None:
        return (evidence_refs, earth_sweep_projects)
    sweep = _require_mapping(earth_sweep, field_name='broad_sweep_context.earth_sweep')
    if sweep.get('evidence_refs') is not None and not evidence_refs:
        evidence_refs = _normalize_string_list(
            sweep.get('evidence_refs'),
            field_name='broad_sweep_context.earth_sweep.evidence_refs',
        )
    raw_projects = sweep.get('projects')
    if raw_projects is None:
        return (evidence_refs, earth_sweep_projects)
    if not isinstance(raw_projects, list):
        raise ValueError('broad_sweep_context.earth_sweep.projects must be a list')
    for index, item in enumerate(raw_projects):
        project = _require_mapping(item, field_name=f'broad_sweep_context.earth_sweep.projects[{index}]')
        project_id = _require_nonempty_text(
            project.get('project_id'),
            field_name=f'broad_sweep_context.earth_sweep.projects[{index}].project_id',
        )
        obligations = project.get('obligations') or []
        unresolved = project.get('unresolved_ideas') or []
        if not isinstance(obligations, list):
            raise ValueError(f'broad_sweep_context.earth_sweep.projects[{index}].obligations must be a list')
        if not isinstance(unresolved, list):
            raise ValueError(f'broad_sweep_context.earth_sweep.projects[{index}].unresolved_ideas must be a list')
        earth_sweep_projects.append(
            {
                'project_id': project_id,
                'obligations': obligations,
                'unresolved_ideas': unresolved,
            }
        )
    earth_sweep_projects.sort(key=lambda row: row['project_id'])
    return (evidence_refs, earth_sweep_projects)


def _resolve_local_json_ref_path(ref: str) -> Path | None:
    text = str(ref).strip()
    if not text:
        return None
    candidate = Path(text).expanduser()
    candidates = [candidate] if candidate.is_absolute() else [_repo_root() / candidate]
    for path in candidates:
        if path.suffix.lower() != '.json':
            continue
        if path.exists() and path.is_file():
            return path.resolve()
    return None


def _reason_codes_from_raw_row(raw_value: Mapping[str, Any]) -> list[str]:
    reason_codes: set[str] = set()
    single_reason_code = str(raw_value.get('reason_code') or '').strip()
    if single_reason_code:
        reason_codes.update(code.strip() for code in single_reason_code.split(',') if code.strip())
    for field_name in ('flag_reason_codes', 'rejection_reason_codes'):
        values = raw_value.get(field_name)
        if not isinstance(values, list):
            continue
        for value in values:
            text = str(value).strip()
            if text:
                reason_codes.add(text)
    return sorted(reason_codes)


def _req_047_collect_document_recommendation_entries(
    raw_value: Any,
    *,
    document_ref: str,
    entries: list[dict[str, Any]],
) -> None:
    if isinstance(raw_value, Mapping):
        recommendation_ids: set[str] = set()
        recommendation_id = str(raw_value.get('recommendation_id') or '').strip()
        if recommendation_id:
            recommendation_ids.add(recommendation_id)
        recommendation_ids_raw = raw_value.get('recommendation_ids')
        if isinstance(recommendation_ids_raw, list):
            for value in recommendation_ids_raw:
                text = str(value).strip()
                if text:
                    recommendation_ids.add(text)
        reason_codes = _reason_codes_from_raw_row(raw_value)
        evidence_refs = _collect_unique_refs(
            _best_effort_extract_string_refs(raw_value.get('evidence_refs')),
            _best_effort_extract_string_refs(raw_value.get('evidence_ids')),
            [document_ref],
        )
        state_labels: list[str] = []
        for field_name in ('position', 'recommendation_scope', 'decision', 'decision_type', 'status'):
            text = str(raw_value.get(field_name) or '').strip().lower()
            if text:
                state_labels.append(f'{field_name}:{text}')
        if raw_value.get('excluded_from_final_recommendations') is True:
            state_labels.append('status:excluded_from_final_recommendations')
        for rec_id in sorted(recommendation_ids):
            entries.append(
                {
                    'recommendation_id': rec_id,
                    'reason_codes': reason_codes,
                    'state_labels': sorted(set(state_labels)),
                    'evidence_refs': evidence_refs,
                    'document_ref': document_ref,
                }
            )
        for value in raw_value.values():
            _req_047_collect_document_recommendation_entries(value, document_ref=document_ref, entries=entries)
        return
    if isinstance(raw_value, list):
        for item in raw_value:
            _req_047_collect_document_recommendation_entries(item, document_ref=document_ref, entries=entries)


def _req_047_recommendation_entries_for_refs(
    refs: list[str],
    *,
    cache: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for ref in refs:
        text = str(ref).strip()
        if not text:
            continue
        if text not in cache:
            cache[text] = []
            path = _resolve_local_json_ref_path(text)
            if path is not None:
                try:
                    payload = json.loads(path.read_text(encoding='utf-8'))
                except (OSError, ValueError):
                    payload = None
                if payload is not None:
                    extracted: list[dict[str, Any]] = []
                    _req_047_collect_document_recommendation_entries(payload, document_ref=text, entries=extracted)
                    deduped: dict[tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...]], dict[str, Any]] = {}
                    for entry in extracted:
                        key = (
                            str(entry.get('recommendation_id') or ''),
                            tuple(str(value) for value in entry.get('reason_codes') or []),
                            tuple(str(value) for value in entry.get('state_labels') or []),
                            tuple(str(value) for value in entry.get('evidence_refs') or []),
                        )
                        deduped[key] = entry
                    cache[text] = sorted(
                        deduped.values(),
                        key=lambda row: (
                            str(row.get('recommendation_id') or ''),
                            ','.join(row.get('reason_codes') or []),
                            ','.join(row.get('state_labels') or []),
                            ','.join(row.get('evidence_refs') or []),
                        ),
                    )
        entries.extend(dict(entry) for entry in cache[text])
    return entries


def _req_047_diagnostic_insights(
    *,
    llm_call_trace_rows: list[dict[str, Any]],
    decision_ledger: list[dict[str, Any]],
) -> dict[str, Any]:
    cache: dict[str, list[dict[str, Any]]] = {}
    recommendation_ids_by_call_ref: dict[str, list[str]] = {}
    blocked_reason_codes_by_recommendation: dict[str, set[str]] = {}
    required_refs_by_recommendation: dict[str, set[str]] = {}
    state_entries_by_recommendation: dict[str, list[dict[str, Any]]] = {}
    recommendation_ids_seen: set[str] = set()
    for row in llm_call_trace_rows:
        call_ref = str(row.get('call_ref') or '').strip()
        refs = _collect_unique_refs(
            list(row.get('input_refs') or []),
            list(row.get('output_refs') or []),
            [
                str(artifact.get('path') or '').strip()
                for artifact in row.get('artifacts') or []
                if isinstance(artifact, Mapping)
            ],
        )
        entries = _req_047_recommendation_entries_for_refs(refs, cache=cache)
        recommendation_ids_by_call_ref[call_ref] = sorted(
            {
                str(entry.get('recommendation_id') or '').strip()
                for entry in entries
                if str(entry.get('recommendation_id') or '').strip()
            }
        )
        for entry in entries:
            recommendation_id = str(entry.get('recommendation_id') or '').strip()
            if not recommendation_id:
                continue
            recommendation_ids_seen.add(recommendation_id)
            required_refs = required_refs_by_recommendation.setdefault(recommendation_id, set())
            required_refs.update(str(ref).strip() for ref in entry.get('evidence_refs') or [] if str(ref).strip())
            for reason_code in entry.get('reason_codes') or []:
                text = str(reason_code).strip()
                if text:
                    blocked_reason_codes_by_recommendation.setdefault(recommendation_id, set()).add(text)
            for state_label in entry.get('state_labels') or []:
                text = str(state_label).strip()
                if not text:
                    continue
                state_entries_by_recommendation.setdefault(recommendation_id, []).append(
                    {
                        'call_ref': call_ref,
                        'state_label': text,
                        'required_evidence_refs': sorted(required_refs),
                    }
                )
    recommendation_ids_by_decision_id: dict[str, list[str]] = {}
    blocked_recommendation_ids_by_decision_id: dict[str, list[str]] = {}
    required_refs_by_decision_id: dict[str, list[str]] = {}
    for decision in decision_ledger:
        decision_id = str(decision.get('decision_id') or '').strip()
        source_call_refs = [str(value).strip() for value in decision.get('source_call_refs') or [] if str(value).strip()]
        refs = _collect_unique_refs(list(decision.get('evidence_refs') or []))
        entries = _req_047_recommendation_entries_for_refs(refs, cache=cache)
        decision_recommendation_ids = {
            recommendation_id
            for call_ref in source_call_refs
            for recommendation_id in recommendation_ids_by_call_ref.get(call_ref, [])
        }
        decision_recommendation_ids.update(
            {
                str(entry.get('recommendation_id') or '').strip()
                for entry in entries
                if str(entry.get('recommendation_id') or '').strip()
            }
        )
        recommendation_ids_by_decision_id[decision_id] = sorted(decision_recommendation_ids)
        blocked_recommendation_ids_by_decision_id[decision_id] = sorted(
            recommendation_id
            for recommendation_id in decision_recommendation_ids
            if 'uncited_strategic_claim' in blocked_reason_codes_by_recommendation.get(recommendation_id, set())
        )
        required_refs_by_decision: set[str] = {str(value).strip() for value in refs if str(value).strip()}
        for recommendation_id in decision_recommendation_ids:
            required_refs_by_decision.update(required_refs_by_recommendation.get(recommendation_id, set()))
        required_refs_by_decision_id[decision_id] = sorted(required_refs_by_decision)
    contradiction_risks: list[dict[str, Any]] = []
    contradiction_recommendation_ids: list[str] = []
    for recommendation_id in sorted(state_entries_by_recommendation):
        rows = state_entries_by_recommendation[recommendation_id]
        state_labels = sorted(
            {
                str(row.get('state_label') or '').strip()
                for row in rows
                if str(row.get('state_label') or '').strip()
            }
        )
        call_refs = sorted({str(row.get('call_ref') or '').strip() for row in rows if str(row.get('call_ref') or '').strip()})
        if len(state_labels) < 2 or len(call_refs) < 2:
            continue
        contradiction_recommendation_ids.append(recommendation_id)
        contradiction_risks.append(
            {
                'risk_id': f"risk.{_stable_id_fragment('req-047', recommendation_id, 'cross-call-contradiction', ','.join(state_labels), ','.join(call_refs))}",
                'summary': (
                    f"Recommendation '{recommendation_id}' carries contradictory analysis/synthesis positions across "
                    f"{','.join(call_refs)} and cannot be replayed deterministically."
                ),
                'reason_code': 'cross_call_contradiction',
                'recommendation_ids': [recommendation_id],
                'source_call_refs': call_refs,
                'required_evidence_refs': _collect_unique_refs(
                    *[list(row.get('required_evidence_refs') or []) for row in rows]
                ),
            }
        )
    blocked_recommendation_ids = sorted(
        recommendation_id
        for recommendation_id, reason_codes in blocked_reason_codes_by_recommendation.items()
        if 'uncited_strategic_claim' in reason_codes
    )
    emitted_recommendation_ids = sorted(recommendation_ids_seen - set(blocked_recommendation_ids))
    return {
        'recommendation_ids_by_decision_id': recommendation_ids_by_decision_id,
        'blocked_recommendation_ids_by_decision_id': blocked_recommendation_ids_by_decision_id,
        'required_refs_by_decision_id': required_refs_by_decision_id,
        'blocked_recommendation_ids': blocked_recommendation_ids,
        'emitted_recommendation_ids': emitted_recommendation_ids,
        'recommendation_ids_considered': sorted(recommendation_ids_seen),
        'contradiction_risks': contradiction_risks,
        'contradiction_recommendation_ids': contradiction_recommendation_ids,
    }


def _recommendation_confidence(*, evidence_refs: list[str], open_risks: list[dict[str, Any]]) -> str:
    if not evidence_refs:
        return 'low'
    if open_risks:
        return 'medium'
    return 'high'


def _req_039_infer_cross_project_targets(
    *,
    recommendation: Mapping[str, Any],
    peer_project_ids: set[str],
) -> list[str]:
    text = '\n'.join(
        [
            str(recommendation.get('summary') or ''),
            str(recommendation.get('rationale') or ''),
            *[str(item) for item in (recommendation.get('tradeoffs') or [])],
        ]
    ).lower()
    matched = [project_id for project_id in sorted(peer_project_ids) if project_id.lower() in text]
    if matched:
        return matched
    cross_tokens = ('cross-project', 'cross project', 'coordinate', 'coordination', 'sync', 'align', 'peer project')
    if any(token in text for token in cross_tokens):
        return ['<unspecified>']
    return []


def _req_039_recommendation_decision(*, recommended_actions: list[dict[str, Any]], open_risks: list[dict[str, Any]]) -> str:
    if recommended_actions and open_risks:
        return 'proceed-with-open-risks'
    if recommended_actions:
        return 'proceed'
    if open_risks:
        if all(str(row.get('reason_code')) == 'missing_earth_sweep_evidence_refs' for row in open_risks):
            return 'collect-earth-evidence'
        low_substance_codes = {'insufficient_evidence_refs', 'missing_explicit_tradeoffs'}
        open_reason_codes = {
            reason_code.strip()
            for row in open_risks
            for reason_code in str(row.get('reason_code') or '').split(',')
            if reason_code.strip()
        }
        if open_reason_codes and open_reason_codes.issubset(low_substance_codes):
            return 'improve-rationale-quality'
        return 'resolve-context-gaps'
    return 'insufficient-context'


def _req_039_cross_call_contradiction_risks(
    *,
    analysis_synthesis_citation_status: list[dict[str, Any]],
    fallback_evidence_refs: list[str],
) -> list[dict[str, Any]]:
    grouped_by_claim: dict[str, list[dict[str, Any]]] = {}
    for row in analysis_synthesis_citation_status:
        claim_id = str(row.get('strategic_claim_id') or '').strip()
        if not claim_id:
            continue
        grouped_by_claim.setdefault(claim_id, []).append(row)
    contradiction_risks: list[dict[str, Any]] = []
    for claim_id in sorted(grouped_by_claim):
        rows = grouped_by_claim[claim_id]
        statuses = sorted(
            {
                str(row.get('citation_status') or '').strip()
                for row in rows
                if str(row.get('citation_status') or '').strip()
            }
        )
        if len(statuses) < 2:
            continue
        call_ids = sorted({str(row.get('call_id') or '').strip() for row in rows if str(row.get('call_id') or '').strip()})
        recommendation_ids = sorted(
            {
                str(row.get('recommendation_id') or '').strip()
                for row in rows
                if str(row.get('recommendation_id') or '').strip()
            }
        )
        claim_refs = _collect_unique_refs(*[list(row.get('evidence_refs') or []) for row in rows])
        contradiction_risks.append(
            {
                'risk_id': f"risk.{_stable_id_fragment('req-039', claim_id, 'analysis-synthesis-contradiction', ','.join(statuses), ','.join(call_ids), ','.join(recommendation_ids))}",
                'summary': (
                    f"Strategic claim '{claim_id}' has contradictory citation outcomes across analysis/synthesis calls "
                    f"({','.join(call_ids)}) and cannot be promoted deterministically."
                ),
                'reason_code': 'analysis_synthesis_contradiction_cross_call_citation_status',
                'required_evidence_refs': claim_refs or list(fallback_evidence_refs),
            }
        )
    return contradiction_risks


def _req_039_trace_call_id(recommendation_id: str) -> str:
    normalized = ''.join(char.lower() if char.isalnum() else '-' for char in recommendation_id).strip('-')
    normalized = '-'.join(segment for segment in normalized.split('-') if segment)
    if not normalized:
        normalized = 'recommendation'
    return f"score-{normalized[:48]}-{_stable_id_fragment('req-039-call', recommendation_id)}"


def _req_039_trace_open_risks_for_recommendation(
    *,
    scored_recommendation: Mapping[str, Any],
    open_risks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    summary = str(scored_recommendation.get('summary') or '').strip()
    evidence_refs = {
        ref for ref in _best_effort_extract_string_refs(scored_recommendation.get('evidence_refs')) if ref.strip()
    }
    low_substance_reason_codes = {'insufficient_evidence_refs', 'missing_explicit_tradeoffs'}
    matched: dict[str, dict[str, Any]] = {}
    for risk in open_risks:
        risk_id = str(risk.get('risk_id') or '').strip()
        if not risk_id:
            continue
        risk_summary = str(risk.get('summary') or '').strip()
        if summary and risk_summary == summary:
            matched[risk_id] = dict(risk)
            continue
        reason_codes = {token.strip() for token in str(risk.get('reason_code') or '').split(',') if token.strip()}
        if not (reason_codes & low_substance_reason_codes):
            continue
        required_refs = {
            ref for ref in _best_effort_extract_string_refs(risk.get('required_evidence_refs')) if ref.strip()
        }
        if evidence_refs and evidence_refs.issubset(required_refs):
            matched[risk_id] = dict(risk)
    return sorted(matched.values(), key=lambda row: (str(row.get('reason_code') or ''), str(row.get('risk_id') or '')))


def _handoff_summary_for_req_039_call(
    *,
    call_id: str,
    scored_recommendation: Mapping[str, Any],
    recommended_actions: list[dict[str, Any]],
    cross_project_obligations: list[dict[str, Any]],
    open_risks: list[dict[str, Any]],
) -> str:
    recommendation_id = str(scored_recommendation.get('recommendation_id') or '').strip() or 'unknown'
    quality_status = str(scored_recommendation.get('quality_status') or '').strip() or 'unknown'
    quality_score = int(scored_recommendation.get('quality_score') or 0)
    rejection_reason_codes = sorted(
        {
            reason_code.strip()
            for reason_code in (scored_recommendation.get('rejection_reason_codes') or [])
            if isinstance(reason_code, str) and reason_code.strip()
        }
    )
    return (
        f'{REQ_039_REQUIREMENT_ID} {call_id} handoff: '
        f'recommendation_id={recommendation_id} quality_status={quality_status} quality_score={quality_score} '
        f"rejection_reason_codes={','.join(rejection_reason_codes) if rejection_reason_codes else 'none'} "
        f'actions={len(recommended_actions)} obligations={len(cross_project_obligations)} open_risks={len(open_risks)}'
    )


def _req_039_canonical_input(
    *,
    checked_at_utc: str,
    quality_policy: Mapping[str, Any],
    recommendations: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        'analysis_type': REQ_039_ANALYSIS_TYPE,
        'call_id': REQ_039_CALL_ID,
        'checked_at_utc': checked_at_utc,
        'quality_policy': _canonicalize(quality_policy),
        'recommendations': _canonicalize(recommendations),
    }


def _req_039_canonical_processing_input(
    *,
    earth_sweep_evidence_refs: list[str],
    earth_sweep_projects: list[dict[str, Any]],
    cross_project_context: list[dict[str, Any]],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        'earth_sweep_evidence_refs': _canonicalize(earth_sweep_evidence_refs),
        'earth_sweep_projects': _canonicalize(earth_sweep_projects),
        'cross_project_context': _canonicalize(cross_project_context),
        'recommendation_rationale_quality_scoring': _canonicalize(result.get('recommendation_rationale_quality_scoring') or {}),
        'totals': _canonicalize(result.get('totals') or {}),
        'processing_behavior': _canonicalize(result.get('processing_behavior') or {}),
    }


def _record_req_039_llm_call_trace(
    *,
    checked_at_utc: str,
    quality_policy: Mapping[str, Any],
    recommendations: list[dict[str, Any]],
    earth_sweep_evidence_refs: list[str],
    earth_sweep_projects: list[dict[str, Any]],
    cross_project_context: list[dict[str, Any]],
    result: Mapping[str, Any],
    trace_path: Path | None = None,
    artifacts_dir: Path | None = None,
) -> list[dict[str, Any]]:
    trace_file = trace_path or _default_llm_call_trace_path()
    artifacts_root = artifacts_dir or _default_llm_call_trace_artifacts_dir()
    trace_input_refs = _trace_input_refs(
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        cross_project_context=cross_project_context,
        earth_sweep_projects=earth_sweep_projects,
    )
    behavior = result.get('processing_behavior')
    recommendation = behavior.get('recommendation') if isinstance(behavior, Mapping) else {}
    recommended_actions = recommendation.get('recommended_actions') if isinstance(recommendation, Mapping) else []
    cross_project_obligations = recommendation.get('cross_project_obligations') if isinstance(recommendation, Mapping) else []
    open_risks = recommendation.get('open_risks') if isinstance(recommendation, Mapping) else []
    recommended_actions = [dict(row) for row in (recommended_actions if isinstance(recommended_actions, list) else [])]
    cross_project_obligations = [dict(row) for row in (cross_project_obligations if isinstance(cross_project_obligations, list) else [])]
    open_risks = [dict(row) for row in (open_risks if isinstance(open_risks, list) else [])]
    actions_by_recommendation: dict[str, list[dict[str, Any]]] = {}
    for row in recommended_actions:
        recommendation_id = str(row.get('recommendation_id') or '').strip()
        if recommendation_id:
            actions_by_recommendation.setdefault(recommendation_id, []).append(row)
    obligations_by_recommendation: dict[str, list[dict[str, Any]]] = {}
    for row in cross_project_obligations:
        recommendation_id = str(row.get('recommendation_id') or '').strip()
        if recommendation_id:
            obligations_by_recommendation.setdefault(recommendation_id, []).append(row)
    scoring = result.get('recommendation_rationale_quality_scoring')
    scored_recommendations = (
        scoring.get('scored_recommendations')
        if isinstance(scoring, Mapping) and isinstance(scoring.get('scored_recommendations'), list)
        else []
    )
    scored_rows = [dict(row) for row in scored_recommendations if isinstance(row, Mapping)]
    scored_rows.sort(key=lambda row: str(row.get('recommendation_id') or ''))
    rows: list[dict[str, Any]] = []
    for scored_row in scored_rows:
        recommendation_id = str(scored_row.get('recommendation_id') or '').strip()
        if not recommendation_id:
            continue
        call_id = _req_039_trace_call_id(recommendation_id)
        call_actions = sorted(
            actions_by_recommendation.get(recommendation_id, []),
            key=lambda row: (str(row.get('action_id') or ''), str(row.get('recommendation_id') or '')),
        )
        call_obligations = sorted(
            obligations_by_recommendation.get(recommendation_id, []),
            key=lambda row: (str(row.get('obligation_id') or ''), str(row.get('project_id') or '')),
        )
        call_open_risks = _req_039_trace_open_risks_for_recommendation(
            scored_recommendation=scored_row,
            open_risks=open_risks,
        )
        input_snapshot = {
            'schema_version': 'optimus-prime.req-039.recommendation-call-input-snapshot.v1',
            'checked_at_utc': checked_at_utc,
            'requirement_id': REQ_039_REQUIREMENT_ID,
            'analysis_type': REQ_039_ANALYSIS_TYPE,
            'call_id': call_id,
            'quality_policy': dict(quality_policy),
            'recommendation': dict(scored_row),
            'broad_sweep_context': {
                'earth_sweep_evidence_refs': list(earth_sweep_evidence_refs),
                'earth_sweep_projects': earth_sweep_projects,
                'cross_project_context': cross_project_context,
            },
        }
        output_snapshot = {
            'schema_version': 'optimus-prime.req-039.recommendation-call-output-snapshot.v1',
            'checked_at_utc': checked_at_utc,
            'requirement_id': REQ_039_REQUIREMENT_ID,
            'analysis_type': REQ_039_ANALYSIS_TYPE,
            'call_id': call_id,
            'result': {
                'scored_recommendation': dict(scored_row),
                'recommended_actions': call_actions,
                'cross_project_obligations': call_obligations,
                'open_risks': call_open_risks,
                'totals': dict(result.get('totals') or {}) if isinstance(result.get('totals'), Mapping) else {},
            },
        }
        input_digest = _sha256_hex(input_snapshot)
        output_digest = _sha256_hex(output_snapshot)
        bundle_dir = artifacts_root / 'req-039' / call_id / input_digest[:16]
        input_path = bundle_dir / 'input.normalized.json'
        output_path = bundle_dir / 'output.normalized.json'
        _write_json_artifact(input_path, input_snapshot)
        _write_json_artifact(output_path, output_snapshot)
        input_refs = _collect_unique_refs(trace_input_refs, list(scored_row.get('evidence_refs') or []))
        output_refs = [
            f'{REQ_039_REQUIREMENT_ID}::call::{call_id}::output::scored_recommendation',
            _repo_relative_path(output_path),
        ]
        if call_actions:
            output_refs.append(f'{REQ_039_REQUIREMENT_ID}::call::{call_id}::output::recommended_actions')
        if call_obligations:
            output_refs.append(f'{REQ_039_REQUIREMENT_ID}::call::{call_id}::output::cross_project_obligations')
        if call_open_risks:
            output_refs.append(f'{REQ_039_REQUIREMENT_ID}::call::{call_id}::output::open_risks')
        quality_status = str(scored_row.get('quality_status') or '').strip().lower()
        row = {
            'schema_version': _LLM_CALL_TRACE_SCHEMA_VERSION,
            'checked_at_utc': checked_at_utc,
            'requirement_id': REQ_039_REQUIREMENT_ID,
            'analysis_type': REQ_039_ANALYSIS_TYPE,
            'call_id': call_id,
            'call_objective': _REQ_039_CALL_OBJECTIVE,
            'target_project_id': '',
            'peer_project_ids': sorted(
                {str(item.get('project_id') or '').strip() for item in cross_project_context if item.get('project_id')}
            ),
            'input_refs': input_refs,
            'output_refs': sorted(set(output_refs)),
            'artifacts': [
                {'kind': 'input_snapshot', 'path': _repo_relative_path(input_path), 'sha256': input_digest},
                {'kind': 'output_snapshot', 'path': _repo_relative_path(output_path), 'sha256': output_digest},
            ],
            'handoff_summary': _handoff_summary_for_req_039_call(
                call_id=call_id,
                scored_recommendation=scored_row,
                recommended_actions=call_actions,
                cross_project_obligations=call_obligations,
                open_risks=call_open_risks,
            ),
            'totals': {
                'scored_recommendations': 1,
                'accepted_recommendations': 1 if quality_status == 'accepted' else 0,
                'rejected_recommendations': 1 if quality_status == 'rejected' else 0,
                'recommended_actions': len(call_actions),
                'cross_project_obligations': len(call_obligations),
                'open_risks': len(call_open_risks),
            },
        }
        _append_jsonl_row(trace_file, row)
        rows.append(row)
    return rows


def _req_047_trace_dir_segment(*, call_id: str, call_ref: str) -> str:
    normalized = ''.join(char.lower() if char.isalnum() else '-' for char in call_id).strip('-')
    normalized = '-'.join(segment for segment in normalized.split('-') if segment)
    if not normalized:
        normalized = 'call'
    return f"{normalized[:48]}-{_stable_id_fragment('req-047-trace', call_ref)}"


def _handoff_summary_for_req_047_trace_call(
    *,
    call_ref: str,
    source_handoff_summary: str,
    decision_rows: list[dict[str, Any]],
    linked_final_output_artifact_refs: list[str],
) -> str:
    decision_types = sorted(
        {
            str(row.get('decision_type') or '').strip()
            for row in decision_rows
            if str(row.get('decision_type') or '').strip()
        }
    )
    type_counts = {
        decision_type: sum(1 for row in decision_rows if str(row.get('decision_type') or '').strip() == decision_type)
        for decision_type in decision_types
    }
    counts_fragment = ' '.join(f'{decision_type}={count}' for decision_type, count in type_counts.items()) or 'none'
    return (
        f'{REQ_047_REQUIREMENT_ID} {call_ref} handoff: '
        f'decisions={len(decision_rows)} '
        f'linked_final_output_artifacts={len(linked_final_output_artifact_refs)} '
        f"decision_types={','.join(decision_types) if decision_types else 'none'} "
        f'type_counts={counts_fragment} '
        f"source_summary={source_handoff_summary or 'none'}"
    )


def _req_047_infer_cross_project_targets(
    *,
    decision: Mapping[str, Any],
    source_trace_rows_by_call_ref: Mapping[str, Mapping[str, Any]],
    peer_project_ids: set[str],
) -> list[str]:
    matched: set[str] = set()
    source_call_refs = decision.get('source_call_refs')
    source_call_refs = source_call_refs if isinstance(source_call_refs, list) else []
    for call_ref in source_call_refs:
        trace_row = source_trace_rows_by_call_ref.get(str(call_ref))
        if not isinstance(trace_row, Mapping):
            continue
        for raw_project_id in (trace_row.get('peer_project_ids') or []):
            project_id = str(raw_project_id).strip()
            if project_id:
                matched.add(project_id)
    text = '\n'.join(
        [
            str(decision.get('summary') or ''),
            str(decision.get('rationale') or ''),
            *[str(item) for item in source_call_refs],
            *[str(item) for item in (decision.get('final_output_artifact_refs') or [])],
        ]
    ).lower()
    for project_id in sorted(peer_project_ids):
        if project_id.lower() in text:
            matched.add(project_id)
    if matched:
        return sorted(matched)
    cross_tokens = ('cross-project', 'cross project', 'coordination', 'coordinate', 'sync', 'align', 'peer project')
    if any(token in text for token in cross_tokens):
        return ['<unspecified>']
    return []


def _req_047_recommendation_decision(*, recommended_actions: list[dict[str, Any]], open_risks: list[dict[str, Any]]) -> str:
    if recommended_actions and open_risks:
        return 'proceed-with-open-risks'
    if recommended_actions:
        return 'proceed'
    if open_risks:
        if any(str(row.get('reason_code')) == 'missing_earth_sweep_evidence_refs' for row in open_risks):
            return 'collect-earth-evidence'
        if any('uncited_strategic_claim' in str(row.get('reason_code') or '') for row in open_risks):
            return 'resolve-citation-gaps'
        return 'resolve-context-gaps'
    return 'insufficient-context'


def _req_047_canonical_input(
    *,
    checked_at_utc: str,
    llm_call_trace_rows: list[dict[str, Any]],
    final_output_artifacts: list[dict[str, str]],
    decision_ledger: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        'analysis_type': REQ_047_ANALYSIS_TYPE,
        'call_id': REQ_047_CALL_ID,
        'checked_at_utc': checked_at_utc,
        'llm_call_trace_rows': _canonicalize(llm_call_trace_rows),
        'final_output_artifacts': _canonicalize(final_output_artifacts),
        'decision_ledger': _canonicalize(decision_ledger),
    }


def _req_047_canonical_processing_input(
    *,
    earth_sweep_evidence_refs: list[str],
    earth_sweep_projects: list[dict[str, Any]],
    cross_project_context: list[dict[str, Any]],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        'earth_sweep_evidence_refs': _canonicalize(earth_sweep_evidence_refs),
        'earth_sweep_projects': _canonicalize(earth_sweep_projects),
        'cross_project_context': _canonicalize(cross_project_context),
        'llm_call_trace_and_decision_ledger': _canonicalize(result.get('llm_call_trace_and_decision_ledger') or {}),
        'totals': _canonicalize(result.get('totals') or {}),
        'processing_behavior': _canonicalize(result.get('processing_behavior') or {}),
    }


def _record_req_047_llm_call_trace(
    *,
    checked_at_utc: str,
    llm_call_trace_rows: list[dict[str, Any]],
    final_output_artifacts: list[dict[str, str]],
    decision_ledger: list[dict[str, Any]],
    earth_sweep_evidence_refs: list[str],
    earth_sweep_projects: list[dict[str, Any]],
    cross_project_context: list[dict[str, Any]],
    trace_path: Path | None = None,
    artifacts_dir: Path | None = None,
) -> list[dict[str, Any]]:
    trace_file = trace_path or _default_llm_call_trace_path()
    artifacts_root = artifacts_dir or _default_llm_call_trace_artifacts_dir()
    trace_input_refs = _trace_input_refs(
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        cross_project_context=cross_project_context,
        earth_sweep_projects=earth_sweep_projects,
    )
    traceability_index = _req_047_traceability_index(
        final_output_artifacts=final_output_artifacts,
        decision_ledger=decision_ledger,
    )
    final_output_artifact_by_ref = {
        str(row.get('artifact_ref') or '').strip(): row
        for row in final_output_artifacts
        if str(row.get('artifact_ref') or '').strip()
    }
    decision_rows_by_call_ref: dict[str, list[dict[str, Any]]] = {}
    for row in decision_ledger:
        source_call_refs = row.get('source_call_refs')
        source_call_refs = source_call_refs if isinstance(source_call_refs, list) else []
        for call_ref in source_call_refs:
            normalized_call_ref = str(call_ref).strip()
            if not normalized_call_ref:
                continue
            decision_rows_by_call_ref.setdefault(normalized_call_ref, []).append(dict(row))
    for call_ref in decision_rows_by_call_ref:
        decision_rows_by_call_ref[call_ref].sort(key=lambda item: str(item.get('decision_id') or ''))
    rows: list[dict[str, Any]] = []
    for source_row in llm_call_trace_rows:
        call_id = str(source_row.get('call_id') or '').strip()
        requirement_id = str(source_row.get('requirement_id') or '').strip()
        analysis_type = str(source_row.get('analysis_type') or '').strip()
        call_ref = str(source_row.get('call_ref') or _req_047_call_ref(requirement_id=requirement_id, call_id=call_id)).strip()
        if not call_ref:
            continue
        linked_final_output_artifact_refs = _collect_unique_refs(list(source_row.get('linked_final_output_artifact_refs') or []))
        linked_final_output_artifact_rows = [
            final_output_artifact_by_ref[ref]
            for ref in linked_final_output_artifact_refs
            if ref in final_output_artifact_by_ref
        ]
        call_decisions = list(decision_rows_by_call_ref.get(call_ref, []))
        decision_ids = _collect_unique_refs([str(item.get('decision_id') or '').strip() for item in call_decisions])
        decision_evidence_refs = _collect_unique_refs(*[list(item.get('evidence_refs') or []) for item in call_decisions])
        decision_output_refs = _collect_unique_refs(*[list(item.get('final_output_artifact_refs') or []) for item in call_decisions])
        traceability_rows_for_call = [
            row
            for row in traceability_index
            if str(row.get('final_output_artifact_ref') or '').strip() in set(linked_final_output_artifact_refs)
        ]
        traceability_rows_for_call.sort(
            key=lambda row: (str(row.get('artifact_role') or ''), str(row.get('final_output_artifact_ref') or ''))
        )
        input_snapshot = {
            'schema_version': 'optimus-prime.req-047.trace-call-input-snapshot.v1',
            'checked_at_utc': checked_at_utc,
            'requirement_id': REQ_047_REQUIREMENT_ID,
            'analysis_type': REQ_047_ANALYSIS_TYPE,
            'call_id': call_id,
            'call_ref': call_ref,
            'source_trace_row': _canonicalize(dict(source_row)),
            'decision_ledger_entries': _canonicalize(call_decisions),
            'linked_final_output_artifacts': _canonicalize(linked_final_output_artifact_rows),
            'broad_sweep_context': {
                'earth_sweep_evidence_refs': _canonicalize(earth_sweep_evidence_refs),
                'earth_sweep_projects': _canonicalize(earth_sweep_projects),
                'cross_project_context': _canonicalize(cross_project_context),
            },
        }
        output_snapshot = {
            'schema_version': 'optimus-prime.req-047.trace-call-output-snapshot.v1',
            'checked_at_utc': checked_at_utc,
            'requirement_id': REQ_047_REQUIREMENT_ID,
            'analysis_type': REQ_047_ANALYSIS_TYPE,
            'call_id': call_id,
            'call_ref': call_ref,
            'result': {
                'decision_ids': decision_ids,
                'linked_final_output_artifact_refs': linked_final_output_artifact_refs,
                'traceability_index_rows': _canonicalize(traceability_rows_for_call),
                'totals': {
                    'decision_ledger_entries': len(call_decisions),
                    'linked_final_output_artifacts': len(linked_final_output_artifact_refs),
                },
            },
        }
        input_digest = _sha256_hex(input_snapshot)
        output_digest = _sha256_hex(output_snapshot)
        bundle_dir = artifacts_root / 'req-047' / _req_047_trace_dir_segment(call_id=call_id, call_ref=call_ref) / input_digest[:16]
        input_path = bundle_dir / 'input.normalized.json'
        output_path = bundle_dir / 'output.normalized.json'
        _write_json_artifact(input_path, input_snapshot)
        _write_json_artifact(output_path, output_snapshot)
        input_refs = _collect_unique_refs(
            list(source_row.get('input_refs') or []),
            trace_input_refs,
            decision_evidence_refs,
            [row['artifact_ref'] for row in linked_final_output_artifact_rows],
        )
        output_refs = _collect_unique_refs(
            list(source_row.get('output_refs') or []),
            linked_final_output_artifact_refs,
            decision_output_refs,
            [
                f'{REQ_047_REQUIREMENT_ID}::call::{call_id}::output::decision_ledger_links',
                f'{REQ_047_REQUIREMENT_ID}::call::{call_id}::output::traceability_index_links',
                _repo_relative_path(output_path),
            ],
        )
        totals = dict(source_row.get('totals') or {}) if isinstance(source_row.get('totals'), Mapping) else {}
        totals['decision_ledger_entries'] = len(call_decisions)
        totals['linked_final_output_artifacts'] = len(linked_final_output_artifact_refs)
        totals = {
            str(key): int(value)
            for key, value in totals.items()
            if isinstance(key, str) and key.strip() and isinstance(value, int) and value >= 0
        }
        if not totals:
            totals = {
                'decision_ledger_entries': len(call_decisions),
                'linked_final_output_artifacts': len(linked_final_output_artifact_refs),
            }
        row = {
            'schema_version': _LLM_CALL_TRACE_SCHEMA_VERSION,
            'checked_at_utc': str(source_row.get('checked_at_utc') or checked_at_utc).strip(),
            'requirement_id': requirement_id,
            'analysis_type': analysis_type,
            'call_id': call_id,
            'call_ref': call_ref,
            'call_objective': str(source_row.get('call_objective') or _REQ_047_CALL_OBJECTIVE).strip(),
            'target_project_id': str(source_row.get('target_project_id') or '').strip(),
            'peer_project_ids': _collect_unique_refs(list(source_row.get('peer_project_ids') or [])),
            'input_refs': input_refs,
            'output_refs': output_refs,
            'artifacts': [
                {'kind': 'input_snapshot', 'path': _repo_relative_path(input_path), 'sha256': input_digest},
                {'kind': 'output_snapshot', 'path': _repo_relative_path(output_path), 'sha256': output_digest},
            ],
            'handoff_summary': _handoff_summary_for_req_047_trace_call(
                call_ref=call_ref,
                source_handoff_summary=str(source_row.get('handoff_summary') or '').strip(),
                decision_rows=call_decisions,
                linked_final_output_artifact_refs=linked_final_output_artifact_refs,
            ),
            'totals': totals,
            'linked_final_output_artifact_refs': linked_final_output_artifact_refs,
        }
        _append_jsonl_row(trace_file, row)
        rows.append(row)
    return rows


def process_req_047_llm_call_trace_and_decision_ledger(
    payload: Mapping[str, Any],
    *,
    emit: Callable[[str], None] | None = None,
    trace_path: str | Path | None = None,
    trace_artifacts_dir: str | Path | None = None,
) -> dict[str, Any]:
    raw = _require_mapping(payload, field_name='payload')
    analysis_type = str(raw.get('analysis_type') or '').strip()
    if analysis_type and analysis_type != REQ_047_ANALYSIS_TYPE:
        raise ValueError(f'analysis_type must be {REQ_047_ANALYSIS_TYPE}')
    checked_at_utc = _require_nonempty_text(raw.get('now_utc'), field_name='now_utc')
    earth_sweep_evidence_refs, earth_sweep_projects = _extract_earth_sweep_inputs(raw.get('broad_sweep_context'))
    broad = raw.get('broad_sweep_context')
    cross_project_context: list[dict[str, Any]] = []
    if broad is not None:
        broad_map = _require_mapping(broad, field_name='broad_sweep_context')
        cross_project_context = _normalize_cross_project_context(broad_map.get('cross_project_context'))
    extra = sorted(
        set(raw.keys())
        - {
            'analysis_type',
            'now_utc',
            'llm_call_trace_rows',
            'final_output_artifacts',
            'decision_ledger',
            'broad_sweep_context',
        }
    )
    if extra:
        raise ValueError(f'payload has unexpected keys: {extra}')
    if emit is not None:
        emit(_format_ts_line('REQ-047 processing start', now_utc=checked_at_utc))
    contract_payload = build_req_047_llm_call_trace_and_decision_ledger(
        {
            'analysis_type': REQ_047_ANALYSIS_TYPE,
            'now_utc': checked_at_utc,
            'llm_call_trace_rows': raw.get('llm_call_trace_rows'),
            'final_output_artifacts': raw.get('final_output_artifacts'),
            'decision_ledger': raw.get('decision_ledger'),
        }
    )
    contract_trace_rows = [dict(row) for row in contract_payload['llm_call_trace_rows']]
    final_output_artifacts = [dict(row) for row in contract_payload['final_output_artifacts']]
    decision_ledger = [dict(row) for row in contract_payload['llm_call_trace_and_decision_ledger']['decision_ledger']]
    source_trace_rows_by_call_ref = {
        str(row.get('call_ref') or ''): row for row in contract_trace_rows if str(row.get('call_ref') or '').strip()
    }
    context_refs_by_project: dict[str, set[str]] = {}
    for context_row in cross_project_context:
        project_id = str(context_row.get('project_id') or '').strip()
        if not project_id:
            continue
        refs = context_refs_by_project.setdefault(project_id, set())
        refs.update(str(ref).strip() for ref in (context_row.get('evidence_refs') or []) if str(ref).strip())
    sorted_context_refs_by_project = {
        project_id: sorted(refs) for project_id, refs in sorted(context_refs_by_project.items())
    }
    peer_project_ids = {
        project_id
        for row in contract_trace_rows
        for project_id in (row.get('peer_project_ids') or [])
        if isinstance(project_id, str) and project_id.strip()
    }
    peer_project_ids.update(sorted_context_refs_by_project.keys())
    trace_input_refs = _collect_unique_refs(*[list(row.get('input_refs') or []) for row in contract_trace_rows])
    trace_output_refs = _collect_unique_refs(*[list(row.get('output_refs') or []) for row in contract_trace_rows])
    cross_project_refs = _collect_unique_refs(*list(sorted_context_refs_by_project.values()))
    ledger_evidence_refs = _collect_unique_refs(*[list(row.get('evidence_refs') or []) for row in decision_ledger])
    diagnostic_insights = _req_047_diagnostic_insights(
        llm_call_trace_rows=contract_trace_rows,
        decision_ledger=decision_ledger,
    )
    recommended_actions: list[dict[str, Any]] = []
    cross_project_obligations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = list(diagnostic_insights['contradiction_risks'])
    for decision in decision_ledger:
        decision_id = str(decision.get('decision_id') or '').strip()
        summary = str(decision.get('summary') or '').strip()
        rationale = str(decision.get('rationale') or '').strip()
        decision_type = str(decision.get('decision_type') or '').strip()
        source_call_refs = [str(value) for value in decision.get('source_call_refs') or [] if str(value).strip()]
        final_output_artifact_refs = [
            str(value) for value in decision.get('final_output_artifact_refs') or [] if str(value).strip()
        ]
        decision_evidence_refs = [str(value) for value in decision.get('evidence_refs') or [] if str(value).strip()]
        decision_recommendation_ids = list(diagnostic_insights['recommendation_ids_by_decision_id'].get(decision_id, []))
        blocked_recommendation_ids = list(
            diagnostic_insights['blocked_recommendation_ids_by_decision_id'].get(decision_id, [])
        )
        emitted_recommendation_ids_for_decision = [
            recommendation_id
            for recommendation_id in decision_recommendation_ids
            if recommendation_id not in set(blocked_recommendation_ids)
        ]
        diagnostic_required_refs = list(diagnostic_insights['required_refs_by_decision_id'].get(decision_id, []))
        if blocked_recommendation_ids:
            open_risks.append(
                {
                    'risk_id': f"risk.{_stable_id_fragment('req-047', decision_id, 'uncited-strategic-claim', ','.join(blocked_recommendation_ids))}",
                    'summary': summary or f'Decision {decision_id} is blocked by citation discipline.',
                    'reason_code': 'uncited_strategic_claim',
                    'recommendation_ids': blocked_recommendation_ids,
                    'source_call_refs': source_call_refs,
                    'required_evidence_refs': _collect_unique_refs(diagnostic_required_refs, decision_evidence_refs),
                }
            )
            if not emitted_recommendation_ids_for_decision:
                continue
        targets = _req_047_infer_cross_project_targets(
            decision=decision,
            source_trace_rows_by_call_ref=source_trace_rows_by_call_ref,
            peer_project_ids=set(peer_project_ids),
        )
        if not targets:
            recommended_actions.append(
                {
                    'action_id': f"action.{_stable_id_fragment('req-047', decision_id, 'local')}",
                    'decision_id': decision_id,
                    'decision_type': decision_type,
                    'summary': summary,
                    'rationale': rationale,
                    'source_call_refs': source_call_refs,
                    'recommendation_ids': emitted_recommendation_ids_for_decision,
                    'final_output_artifact_refs': final_output_artifact_refs,
                    'evidence_refs': _collect_unique_refs(diagnostic_required_refs, decision_evidence_refs),
                    'coordination_required': False,
                    'coordination_projects': [],
                }
            )
            continue
        if not earth_sweep_evidence_refs:
            open_risks.append(
                {
                    'risk_id': f"risk.{_stable_id_fragment('req-047', decision_id, 'missing-earth-sweep-evidence-refs')}",
                    'summary': summary or f'Decision {decision_id} requires Earth-sweep evidence refs.',
                    'reason_code': 'missing_earth_sweep_evidence_refs',
                    'recommendation_ids': emitted_recommendation_ids_for_decision,
                    'source_call_refs': source_call_refs,
                    'required_evidence_refs': _collect_unique_refs(diagnostic_required_refs, decision_evidence_refs),
                }
            )
            continue
        if targets == ['<unspecified>']:
            open_risks.append(
                {
                    'risk_id': f"risk.{_stable_id_fragment('req-047', decision_id, 'missing-cross-project-context')}",
                    'summary': summary or f'Decision {decision_id} references cross-project coordination without targets.',
                    'reason_code': 'missing_cross_project_context',
                    'recommendation_ids': emitted_recommendation_ids_for_decision,
                    'source_call_refs': source_call_refs,
                    'required_evidence_refs': _collect_unique_refs(
                        earth_sweep_evidence_refs,
                        diagnostic_required_refs,
                        decision_evidence_refs,
                    ),
                }
            )
            continue
        missing_reason_codes: list[str] = []
        required_refs = list(earth_sweep_evidence_refs)
        required_refs.extend(diagnostic_required_refs)
        required_refs.extend(decision_evidence_refs)
        coordination_projects: list[str] = []
        obligation_rows: list[dict[str, Any]] = []
        for project_id in sorted(set(targets)):
            context_refs = sorted_context_refs_by_project.get(project_id)
            if context_refs is None:
                missing_reason_codes.append('missing_cross_project_context')
                continue
            if not context_refs:
                missing_reason_codes.append('missing_cross_project_context_evidence_refs')
                continue
            coordination_projects.append(project_id)
            required_refs.extend(context_refs)
            obligation_rows.append(
                {
                    'obligation_id': f"obl.{_stable_id_fragment('req-047', decision_id, project_id)}",
                    'project_id': project_id,
                    'decision_id': decision_id,
                    'recommendation_ids': emitted_recommendation_ids_for_decision,
                    'summary': summary,
                    'evidence_refs': _collect_unique_refs(
                        earth_sweep_evidence_refs,
                        diagnostic_required_refs,
                        decision_evidence_refs,
                        context_refs,
                    ),
                }
            )
        if missing_reason_codes:
            open_risks.append(
                {
                    'risk_id': f"risk.{_stable_id_fragment('req-047', decision_id, ','.join(sorted(set(missing_reason_codes))))}",
                    'summary': summary or f'Decision {decision_id} cannot be promoted due to missing context.',
                    'reason_code': ','.join(sorted(set(missing_reason_codes))),
                    'recommendation_ids': emitted_recommendation_ids_for_decision,
                    'source_call_refs': source_call_refs,
                    'required_evidence_refs': _collect_unique_refs(required_refs),
                }
            )
            continue
        recommended_actions.append(
            {
                'action_id': f"action.{_stable_id_fragment('req-047', decision_id, ','.join(coordination_projects))}",
                'decision_id': decision_id,
                'decision_type': decision_type,
                'summary': summary,
                'rationale': rationale,
                'source_call_refs': source_call_refs,
                'recommendation_ids': emitted_recommendation_ids_for_decision,
                'final_output_artifact_refs': final_output_artifact_refs,
                'evidence_refs': _collect_unique_refs(
                    earth_sweep_evidence_refs,
                    diagnostic_required_refs,
                    decision_evidence_refs,
                    *[sorted_context_refs_by_project[project_id] for project_id in coordination_projects],
                ),
                'coordination_required': True,
                'coordination_projects': sorted(set(coordination_projects)),
            }
        )
        cross_project_obligations.extend(obligation_rows)
    for project in earth_sweep_projects:
        project_id = str(project.get('project_id') or '').strip()
        if not project_id:
            continue
        for index, idea_row in enumerate(project.get('unresolved_ideas') or []):
            if not isinstance(idea_row, Mapping):
                continue
            summary = str(idea_row.get('idea') or idea_row.get('summary') or '').strip()
            if not summary:
                continue
            idea_refs = _normalize_string_list(
                idea_row.get('earth_sweep_evidence_refs') or idea_row.get('evidence_refs'),
                field_name=f'broad_sweep_context.earth_sweep.projects[project_id={project_id}].unresolved_ideas[{index}].evidence_refs',
            )
            open_risks.append(
                {
                    'risk_id': f"risk.{_stable_id_fragment('req-047', project_id, 'unresolved-idea', summary)}",
                    'summary': summary,
                    'reason_code': 'unresolved_cross_project_idea',
                    'required_evidence_refs': _collect_unique_refs(idea_refs),
                }
            )
    deduped_open_risks: dict[str, dict[str, Any]] = {}
    for row in open_risks:
        deduped_open_risks[row['risk_id']] = row
    open_risks = sorted(
        deduped_open_risks.values(),
        key=lambda row: (str(row.get('reason_code') or ''), str(row.get('risk_id') or '')),
    )
    recommended_actions.sort(key=lambda row: (str(row.get('decision_id') or ''), str(row.get('action_id') or '')))
    cross_project_obligations.sort(
        key=lambda row: (
            str(row.get('project_id') or ''),
            str(row.get('decision_id') or ''),
            str(row.get('obligation_id') or ''),
        )
    )
    emitted_recommendation_ids = _collect_unique_refs(
        *[list(row.get('recommendation_ids') or []) for row in recommended_actions]
    )
    evidence_refs_used = _collect_unique_refs(
        earth_sweep_evidence_refs,
        cross_project_refs,
        trace_input_refs,
        trace_output_refs,
        ledger_evidence_refs,
        *[list(row.get('evidence_refs') or []) for row in recommended_actions],
        *[list(row.get('evidence_refs') or []) for row in cross_project_obligations],
        *[list(row.get('required_evidence_refs') or []) for row in open_risks],
    )
    decision = _req_047_recommendation_decision(recommended_actions=recommended_actions, open_risks=open_risks)
    confidence = _recommendation_confidence(evidence_refs=evidence_refs_used, open_risks=open_risks)
    processing_behavior = {
        'strategy': 'llm-first-broad-sweep',
        'reasoning_mode': 'long-thinking',
        'heuristic_summarization_only': False,
        'strict_evidence_discipline': True,
        'context_inputs': {
            'llm_call_trace_rows': contract_trace_rows,
            'final_output_artifacts': final_output_artifacts,
            'decision_ledger': decision_ledger,
            'broad_sweep_context': {
                'earth_sweep_evidence_refs': earth_sweep_evidence_refs,
                'earth_sweep_projects': earth_sweep_projects,
                'cross_project_context': cross_project_context,
            },
        },
        'context_usage': {
            'earth_sweep_context_used': bool(earth_sweep_evidence_refs or earth_sweep_projects),
            'cross_project_context_used': bool(cross_project_context),
            'cross_project_projects_considered': sorted(sorted_context_refs_by_project.keys()),
            'earth_sweep_refs_used': earth_sweep_evidence_refs,
            'cross_project_refs_used': cross_project_refs,
            'trace_input_refs_used': trace_input_refs,
            'trace_output_refs_used': trace_output_refs,
            'ledger_evidence_refs_used': ledger_evidence_refs,
            'call_refs_considered': [str(row.get('call_ref') or '') for row in contract_trace_rows],
            'decision_ids_considered': [str(row.get('decision_id') or '') for row in decision_ledger],
            'recommendation_ids_considered': list(diagnostic_insights['recommendation_ids_considered']),
            'emitted_recommendation_ids': emitted_recommendation_ids,
            'blocked_recommendation_ids': list(diagnostic_insights['blocked_recommendation_ids']),
            'contradiction_recommendation_ids': list(diagnostic_insights['contradiction_recommendation_ids']),
            'evidence_refs_used': evidence_refs_used,
        },
        'recommendation': {
            'decision': decision,
            'rationale': (
                f"trace_rows={contract_payload['totals']['llm_call_trace_rows']} "
                f"decision_ledger_entries={contract_payload['totals']['decision_ledger_entries']} "
                f"recommended_actions={len(recommended_actions)} "
                f"open_risks={len(open_risks)}"
            ),
            'confidence': confidence,
            'evidence_refs': evidence_refs_used,
            'recommended_actions': recommended_actions,
            'cross_project_obligations': cross_project_obligations,
            'open_risks': open_risks,
        },
    }
    if emit is not None:
        emit(_format_ts_line(f'REQ-047 processing decision={decision}', now_utc=checked_at_utc))
    trace_rows = _record_req_047_llm_call_trace(
        checked_at_utc=checked_at_utc,
        llm_call_trace_rows=contract_trace_rows,
        final_output_artifacts=final_output_artifacts,
        decision_ledger=decision_ledger,
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        earth_sweep_projects=earth_sweep_projects,
        cross_project_context=cross_project_context,
        trace_path=Path(trace_path) if trace_path is not None else None,
        artifacts_dir=Path(trace_artifacts_dir) if trace_artifacts_dir is not None else None,
    )
    result = {
        'ok': True,
        'schema_version': REQ_047_PROCESSING_SCHEMA_VERSION,
        'requirement_id': REQ_047_REQUIREMENT_ID,
        'analysis_type': REQ_047_ANALYSIS_TYPE,
        'call_id': REQ_047_CALL_ID,
        'checked_at_utc': contract_payload['checked_at_utc'],
        'llm_call_trace_rows': trace_rows,
        'final_output_artifacts': contract_payload['final_output_artifacts'],
        'llm_call_trace_and_decision_ledger': contract_payload['llm_call_trace_and_decision_ledger'],
        'totals': contract_payload['totals'],
        'processing_behavior': processing_behavior,
    }
    canonical_input = _req_047_canonical_input(
        checked_at_utc=checked_at_utc,
        llm_call_trace_rows=contract_trace_rows,
        final_output_artifacts=final_output_artifacts,
        decision_ledger=decision_ledger,
    )
    canonical_processing_input = _req_047_canonical_processing_input(
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        earth_sweep_projects=earth_sweep_projects,
        cross_project_context=cross_project_context,
        result=result,
    )
    canonical_input_sha = _sha256_hex(canonical_input)
    canonical_processing_input_sha = _sha256_hex(canonical_processing_input)
    result['call_metadata'] = {
        'reproducibility': 'deterministic-input-fingerprint',
        'canonical_input': canonical_input,
        'canonical_input_sha256': canonical_input_sha,
        'reproducible_call_id': f'req047-{canonical_input_sha[:16]}',
        'canonical_processing_input': canonical_processing_input,
        'canonical_processing_input_sha256': canonical_processing_input_sha,
        'processing_call_id': f'req047-processing-{canonical_processing_input_sha[:16]}',
        'llm_call_trace_schema_version': _LLM_CALL_TRACE_SCHEMA_VERSION,
        'llm_call_trace_path': _repo_relative_path(
            Path(trace_path) if trace_path is not None else _default_llm_call_trace_path()
        ),
        'llm_call_trace_sha256': _sha256_hex(trace_rows),
        'llm_call_trace_rows': trace_rows,
        'decision_ledger_entries': len(decision_ledger),
    }
    return result


def process_req_039_recommendation_rationale_quality_scoring(
    payload: Mapping[str, Any],
    *,
    emit: Callable[[str], None] | None = None,
    trace_path: str | Path | None = None,
    trace_artifacts_dir: str | Path | None = None,
) -> dict[str, Any]:
    raw = _require_mapping(payload, field_name='payload')
    analysis_type = str(raw.get('analysis_type') or '').strip()
    if analysis_type and analysis_type != REQ_039_ANALYSIS_TYPE:
        raise ValueError(f'analysis_type must be {REQ_039_ANALYSIS_TYPE}')
    checked_at_utc = _require_nonempty_text(raw.get('now_utc'), field_name='now_utc')
    quality_policy = _normalize_req_039_quality_policy(raw.get('quality_policy'))
    recommendations = _normalize_req_039_recommendations(raw.get('recommendations'))
    earth_sweep_evidence_refs, earth_sweep_projects = _extract_earth_sweep_inputs(raw.get('broad_sweep_context'))
    broad = raw.get('broad_sweep_context')
    cross_project_context: list[dict[str, Any]] = []
    analysis_synthesis_citation_status: list[dict[str, Any]] = []
    if broad is not None:
        broad_map = _require_mapping(broad, field_name='broad_sweep_context')
        cross_project_context = _normalize_cross_project_context(broad_map.get('cross_project_context'))
        analysis_synthesis_citation_status = _normalize_req_039_analysis_synthesis_citation_status(
            broad_map.get('analysis_synthesis_citation_status')
        )
    extra = sorted(
        set(raw.keys()) - {'analysis_type', 'now_utc', 'quality_policy', 'recommendations', 'broad_sweep_context'}
    )
    if extra:
        raise ValueError(f'payload has unexpected keys: {extra}')
    if emit is not None:
        emit(_format_ts_line(f'REQ-039 processing start recommendations={len(recommendations)}', now_utc=checked_at_utc))
    contract_payload = build_req_039_recommendation_rationale_quality_scoring(
        {
            'analysis_type': REQ_039_ANALYSIS_TYPE,
            'now_utc': checked_at_utc,
            'quality_policy': quality_policy,
            'recommendations': recommendations,
        }
    )
    scoring = contract_payload['recommendation_rationale_quality_scoring']
    scored_recommendations = list(scoring['scored_recommendations'])
    accepted_recommendations = list(scoring['accepted_recommendations'])
    accepted_ids = {row['recommendation_id'] for row in accepted_recommendations}
    context_by_project = {row['project_id']: row for row in cross_project_context if row.get('project_id')}
    peer_project_ids = set(context_by_project.keys())
    earth_projects_by_id = {str(row.get('project_id') or '').strip(): row for row in earth_sweep_projects}
    cross_project_refs = _collect_unique_refs(*[list(row['evidence_refs']) for row in cross_project_context])
    citation_reason_codes_by_recommendation: dict[str, set[str]] = {}
    citation_required_refs_by_recommendation: dict[str, set[str]] = {}
    for row in analysis_synthesis_citation_status:
        recommendation_id = str(row.get('recommendation_id') or '').strip()
        if not recommendation_id:
            continue
        if str(row.get('citation_status') or '').strip().lower() == 'cited':
            continue
        citation_reason_codes_by_recommendation.setdefault(recommendation_id, set()).add('uncited_strategic_claim')
        refs = citation_required_refs_by_recommendation.setdefault(recommendation_id, set())
        refs.update(_best_effort_extract_string_refs(row.get('evidence_refs')))
    recommended_actions: list[dict[str, Any]] = []
    cross_project_obligations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = _req_039_cross_call_contradiction_risks(
        analysis_synthesis_citation_status=analysis_synthesis_citation_status,
        fallback_evidence_refs=earth_sweep_evidence_refs,
    )
    for row in scored_recommendations:
        recommendation_id = row['recommendation_id']
        summary = row['summary']
        rationale = row['rationale']
        evidence_refs = list(row['evidence_refs'])
        tradeoffs = list(row['tradeoffs'])
        if recommendation_id not in accepted_ids:
            reason_codes = sorted(
                {
                    reason_code.strip()
                    for reason_code in row.get('rejection_reason_codes') or []
                    if isinstance(reason_code, str) and reason_code.strip()
                }
            )
            open_risks.append(
                {
                    'risk_id': f"risk.{_stable_id_fragment('req-039', recommendation_id, ','.join(reason_codes))}",
                    'summary': summary,
                    'reason_code': ','.join(reason_codes) if reason_codes else 'rejected_low_substance_recommendation',
                    'required_evidence_refs': evidence_refs,
                }
            )
            continue
        citation_reason_codes = sorted(citation_reason_codes_by_recommendation.get(recommendation_id, set()))
        if citation_reason_codes:
            citation_required_refs = sorted(citation_required_refs_by_recommendation.get(recommendation_id, set()))
            open_risks.append(
                {
                    'risk_id': f"risk.{_stable_id_fragment('req-039', recommendation_id, ','.join(citation_reason_codes))}",
                    'summary': summary,
                    'reason_code': ','.join(citation_reason_codes),
                    'required_evidence_refs': _collect_unique_refs(citation_required_refs, evidence_refs),
                }
            )
            continue
        targets = _req_039_infer_cross_project_targets(recommendation=row, peer_project_ids=peer_project_ids)
        if not targets:
            recommended_actions.append(
                {
                    'action_id': f"action.{_stable_id_fragment('req-039', recommendation_id, 'local')}",
                    'recommendation_id': recommendation_id,
                    'summary': summary,
                    'rationale': rationale,
                    'quality_score': row['quality_score'],
                    'tradeoffs': tradeoffs,
                    'evidence_refs': evidence_refs,
                    'coordination_required': False,
                    'coordination_projects': [],
                }
            )
            continue
        if not earth_sweep_evidence_refs:
            open_risks.append(
                {
                    'risk_id': f"risk.{_stable_id_fragment('req-039', recommendation_id, 'missing-earth-sweep-evidence-refs')}",
                    'summary': summary,
                    'reason_code': 'missing_earth_sweep_evidence_refs',
                    'required_evidence_refs': _collect_unique_refs(evidence_refs),
                }
            )
            continue
        if targets == ['<unspecified>']:
            open_risks.append(
                {
                    'risk_id': f"risk.{_stable_id_fragment('req-039', recommendation_id, 'missing-cross-project-context')}",
                    'summary': summary,
                    'reason_code': 'missing_cross_project_context',
                    'required_evidence_refs': _collect_unique_refs(earth_sweep_evidence_refs, evidence_refs),
                }
            )
            continue
        missing_reason_codes: list[str] = []
        required_refs: list[str] = list(earth_sweep_evidence_refs)
        coordination_projects: list[str] = []
        obligation_rows: list[dict[str, Any]] = []
        for project_id in sorted(set(targets)):
            context_row = context_by_project.get(project_id)
            if context_row is None:
                missing_reason_codes.append('missing_cross_project_context')
                continue
            context_refs = list(context_row.get('evidence_refs') or [])
            if not context_refs:
                missing_reason_codes.append('missing_cross_project_context_evidence_refs')
                continue
            coordination_projects.append(project_id)
            required_refs.extend(context_refs)
            obligation_rows.append(
                {
                    'obligation_id': f"obl.{_stable_id_fragment('req-039', recommendation_id, project_id)}",
                    'project_id': project_id,
                    'recommendation_id': recommendation_id,
                    'summary': summary,
                    'evidence_refs': _collect_unique_refs(earth_sweep_evidence_refs, context_refs, evidence_refs),
                }
            )
        if missing_reason_codes:
            open_risks.append(
                {
                    'risk_id': f"risk.{_stable_id_fragment('req-039', recommendation_id, ','.join(sorted(set(missing_reason_codes))))}",
                    'summary': summary,
                    'reason_code': ','.join(sorted(set(missing_reason_codes))),
                    'required_evidence_refs': _collect_unique_refs(required_refs, evidence_refs),
                }
            )
            continue
        cross_project_obligations.extend(obligation_rows)
        recommended_actions.append(
            {
                'action_id': f"action.{_stable_id_fragment('req-039', recommendation_id, ','.join(coordination_projects))}",
                'recommendation_id': recommendation_id,
                'summary': summary,
                'rationale': rationale,
                'quality_score': row['quality_score'],
                'tradeoffs': tradeoffs,
                'evidence_refs': _collect_unique_refs(
                    earth_sweep_evidence_refs,
                    evidence_refs,
                    *[
                        list(context_by_project.get(project_id, {}).get('evidence_refs') or [])
                        for project_id in coordination_projects
                    ],
                ),
                'coordination_required': True,
                'coordination_projects': sorted(set(coordination_projects)),
            }
        )
    for project_id, project in sorted(earth_projects_by_id.items()):
        for idx, idea_row in enumerate(project.get('unresolved_ideas') or []):
            if not isinstance(idea_row, Mapping):
                continue
            idea_summary = str(idea_row.get('idea') or idea_row.get('summary') or '').strip()
            if not idea_summary:
                continue
            idea_refs = _normalize_string_list(
                idea_row.get('earth_sweep_evidence_refs') or idea_row.get('evidence_refs'),
                field_name=f'broad_sweep_context.earth_sweep.projects[project_id={project_id}].unresolved_ideas[{idx}].evidence_refs',
            )
            open_risks.append(
                {
                    'risk_id': f"risk.{_stable_id_fragment('req-039', project_id, 'unresolved-idea', idea_summary)}",
                    'summary': idea_summary,
                    'reason_code': 'unresolved_cross_project_idea',
                    'required_evidence_refs': _collect_unique_refs(idea_refs),
                }
            )
    deduped_open_risks: dict[str, dict[str, Any]] = {}
    for risk in open_risks:
        deduped_open_risks[risk['risk_id']] = risk
    open_risks = sorted(
        deduped_open_risks.values(),
        key=lambda row: (str(row.get('reason_code') or ''), str(row.get('risk_id') or '')),
    )
    recommended_actions.sort(key=lambda row: (row['recommendation_id'], row['action_id']))
    cross_project_obligations.sort(
        key=lambda row: (row['project_id'], row['recommendation_id'], row['obligation_id'])
    )
    evidence_refs_used = _collect_unique_refs(
        earth_sweep_evidence_refs,
        cross_project_refs,
        *[list(row.get('evidence_refs') or []) for row in scored_recommendations],
        *[list(row.get('evidence_refs') or []) for row in recommended_actions],
        *[list(row.get('evidence_refs') or []) for row in cross_project_obligations],
        *[list(row.get('required_evidence_refs') or []) for row in open_risks],
    )
    decision = _req_039_recommendation_decision(recommended_actions=recommended_actions, open_risks=open_risks)
    confidence = _recommendation_confidence(evidence_refs=evidence_refs_used, open_risks=open_risks)
    processing_behavior = {
        'strategy': 'llm-first-broad-sweep',
        'reasoning_mode': 'long-thinking',
        'heuristic_summarization_only': False,
        'strict_evidence_discipline': True,
        'context_inputs': {
            'quality_policy': dict(quality_policy),
            'recommendations': recommendations,
            'broad_sweep_context': {
                'earth_sweep_evidence_refs': earth_sweep_evidence_refs,
                'earth_sweep_projects': earth_sweep_projects,
                'cross_project_context': cross_project_context,
                'analysis_synthesis_citation_status': analysis_synthesis_citation_status,
            },
        },
        'context_usage': {
            'earth_sweep_context_used': bool(earth_sweep_evidence_refs or earth_sweep_projects),
            'cross_project_context_used': bool(cross_project_context),
            'analysis_synthesis_citation_status_used': bool(analysis_synthesis_citation_status),
            'cross_project_projects_considered': sorted({row['project_id'] for row in cross_project_context}),
            'citation_status_reasoning_calls': sorted(
                {str(row.get('call_id') or '').strip() for row in analysis_synthesis_citation_status if row.get('call_id')}
            ),
            'earth_sweep_refs_used': earth_sweep_evidence_refs,
            'cross_project_refs_used': cross_project_refs,
            'evidence_refs_used': evidence_refs_used,
            'recommendations_considered': [row['recommendation_id'] for row in scored_recommendations],
            'accepted_recommendation_ids': [row['recommendation_id'] for row in accepted_recommendations],
            'rejected_recommendation_ids': [row['recommendation_id'] for row in scoring['rejected_recommendations']],
        },
        'recommendation': {
            'decision': decision,
            'rationale': (
                f"accepted={len(accepted_recommendations)} "
                f"rejected={len(scoring['rejected_recommendations'])} "
                f"emission_ready={len(recommended_actions)} "
                f"open_risks={len(open_risks)}"
            ),
            'confidence': confidence,
            'evidence_refs': evidence_refs_used,
            'recommended_actions': recommended_actions,
            'cross_project_obligations': cross_project_obligations,
            'open_risks': open_risks,
        },
    }
    if emit is not None:
        emit(_format_ts_line(f'REQ-039 processing decision={decision}', now_utc=checked_at_utc))
    result = {
        'ok': True,
        'schema_version': REQ_039_PROCESSING_SCHEMA_VERSION,
        'requirement_id': REQ_039_REQUIREMENT_ID,
        'analysis_type': REQ_039_ANALYSIS_TYPE,
        'call_id': REQ_039_CALL_ID,
        'checked_at_utc': contract_payload['checked_at_utc'],
        'quality_policy': contract_payload['quality_policy'],
        'recommendations': contract_payload['recommendations'],
        'recommendation_rationale_quality_scoring': contract_payload['recommendation_rationale_quality_scoring'],
        'totals': contract_payload['totals'],
        'processing_behavior': processing_behavior,
    }
    trace_rows = _record_req_039_llm_call_trace(
        checked_at_utc=checked_at_utc,
        quality_policy=quality_policy,
        recommendations=recommendations,
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        earth_sweep_projects=earth_sweep_projects,
        cross_project_context=cross_project_context,
        result=result,
        trace_path=Path(trace_path) if trace_path is not None else None,
        artifacts_dir=Path(trace_artifacts_dir) if trace_artifacts_dir is not None else None,
    )
    canonical_input = _req_039_canonical_input(
        checked_at_utc=checked_at_utc,
        quality_policy=quality_policy,
        recommendations=recommendations,
    )
    canonical_processing_input = _req_039_canonical_processing_input(
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        earth_sweep_projects=earth_sweep_projects,
        cross_project_context=cross_project_context,
        result=result,
    )
    canonical_input_sha = _sha256_hex(canonical_input)
    processing_input_sha = _sha256_hex(canonical_processing_input)
    result['call_metadata'] = {
        'reproducibility': 'deterministic-input-fingerprint',
        'canonical_input': canonical_input,
        'canonical_input_sha256': canonical_input_sha,
        'reproducible_call_id': f'req039-{canonical_input_sha[:16]}',
        'canonical_processing_input': canonical_processing_input,
        'canonical_processing_input_sha256': processing_input_sha,
        'processing_call_id': f'req039-processing-{processing_input_sha[:16]}',
        'llm_call_trace_schema_version': _LLM_CALL_TRACE_SCHEMA_VERSION,
        'llm_call_trace_path': _repo_relative_path(
            Path(trace_path) if trace_path is not None else _default_llm_call_trace_path()
        ),
        'llm_call_trace_sha256': _sha256_hex(trace_rows),
        'llm_call_trace_rows': trace_rows,
    }
    return result
