#!/usr/bin/env python3
'REQ-025, REQ-026, REQ-029, REQ-030, REQ-031, REQ-034, and REQ-044 contract/data-model surface for strategy LLM pipeline flows.'

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

REQ_044_REQUIREMENT_ID = 'REQ-044'

REQ_044_SCHEMA_VERSION = 'req-044.recommendation-omission-detector.v1'

REQ_044_LLM_CALL_TRACE_SCHEMA_VERSION = 'req-044.llm-call-trace-row.v1'

REQ_044_ANALYSIS_TYPE = 'recommendation_omission_detector'

REQ_044_PROCESSING_STRATEGY = 'recommendation-omission-detector'

REQ_044_REASONING_MODE = 'deterministic-coverage-guard'

REQ_044_CALL_OBJECTIVE = 'Detect mission and ecosystem recommendation-class omissions, escalate critical cross-project gaps, and prevent local-only plans from bypassing required obligations.'

RUNTIME_MODE = 'llm-first'

EXECUTION_MODE = 'long-thinking'

LLM_CALL_TRACE_RELATIVE_PATH = 'strategy/current/llm_call_trace.jsonl'

REQ_029_ALLOWED_RECOMMENDATION_SCOPES = {'local', 'cross-project'}

REQ_029_RECOMMENDATION_ID_RE = re.compile('^rec\\.[a-z0-9]+(?:-[a-z0-9]+)*$')

REQ_044_CLASS_ID_RE = re.compile('^class\\.[a-z0-9]+(?:-[a-z0-9]+)*$')

REQ_044_ALLOWED_ANCHOR_SOURCES = {'mission', 'ecosystem'}

class Req029Error(ValueError):
    """Raised when REQ-029 input is malformed."""

class Req030Error(ValueError):
    """Raised when REQ-030 input is malformed."""

class Req044Error(ValueError):
    """Raised when REQ-044 input is malformed."""

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')

def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ''
    return str(value).strip()

def _require_text(value: Any, *, field_name: str) -> str:
    text = _as_text(value)
    if not text:
        raise ValueError(f'{field_name} must be a non-empty string')
    return text

def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f'{field_name} must be an object')
    return value

def _normalize_root(value: Any, *, field_name: str) -> str:
    normalized = str(Path(_require_text(value, field_name=field_name)).expanduser().resolve())
    if not normalized.startswith('/'):
        raise ValueError(f'{field_name} must normalize to an absolute path')
    return normalized

def _normalize_string_list(raw_value: Any, *, field_name: str, min_items: int=0) -> list[str]:
    if raw_value is None:
        raw_seq: Sequence[Any] = []
    else:
        if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
            raise ValueError(f'{field_name} must be an array of non-empty strings')
        raw_seq = raw_value
    normalized: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_seq):
        text = _require_text(item, field_name=f'{field_name}[{index}]')
        if text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    if len(normalized) < min_items:
        raise ValueError(f'{field_name} must contain at least {min_items} item(s)')
    return sorted(normalized)

def _collect_unique_refs(*ref_groups: Sequence[Any]) -> list[str]:
    seen: set[str] = set()
    for refs in ref_groups:
        for raw_ref in refs:
            ref = _as_text(raw_ref)
            if ref:
                seen.add(ref)
    return sorted(seen)

def _dedupe_preserving_order(values: Sequence[Any]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = _as_text(raw_value)
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped

def _is_earth_evidence_ref(ref: str) -> bool:
    return _as_text(ref).startswith('reports/earth/')

def _normalize_cross_project_context(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError('cross_project_context must be an array when provided')
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f'cross_project_context[{index}] must be an object')
        project_id = _require_text(item.get('project_id'), field_name=f'cross_project_context[{index}].project_id')
        project_root = _normalize_root(item.get('project_root'), field_name=f'cross_project_context[{index}].project_root')
        evidence_refs = _normalize_string_list(item.get('evidence_refs'), field_name=f'cross_project_context[{index}].evidence_refs')
        context_note = _require_text(item.get('context_note') if item.get('context_note') is not None else 'No context note supplied.', field_name=f'cross_project_context[{index}].context_note')
        normalized.append({'project_id': project_id, 'project_root': project_root, 'evidence_refs': evidence_refs, 'context_note': context_note})
    normalized.sort(key=lambda row: (row['project_id'], row['project_root'], row['context_note']))
    return normalized

def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)

def _canonical_digest(payload: Any) -> str:
    raw = _canonical_json(payload)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()

def _recommendation_decision(*, recommended_actions: list[dict[str, Any]], open_risks: list[dict[str, Any]]) -> str:
    if recommended_actions and (not open_risks):
        return 'proceed'
    if recommended_actions and open_risks:
        return 'proceed-with-open-risks'
    if open_risks:
        if all((row.get('reason_code') == 'missing_earth_sweep_evidence_refs' for row in open_risks)):
            return 'collect-earth-evidence'
        return 'resolve-strategy-gaps'
    return 'insufficient-context'

def _recommendation_confidence(*, evidence_refs: list[str], open_risks: list[dict[str, Any]]) -> str:
    if not evidence_refs:
        return 'low'
    if open_risks:
        return 'medium'
    return 'high'

def _req_029_slugify(value: str) -> str:
    slug = re.sub('[^a-z0-9]+', '-', value.lower()).strip('-')
    return slug or 'recommendation'

def _req_029_recommendation_id_from_candidate(row: Mapping[str, Any], *, index: int) -> str:
    provided = _as_text(row.get('recommendation_id'))
    if provided:
        if not REQ_029_RECOMMENDATION_ID_RE.match(provided):
            raise Req029Error(f'candidate_recommendations[{index}].recommendation_id must match {REQ_029_RECOMMENDATION_ID_RE.pattern}')
        return provided
    summary = _require_text(row.get('summary'), field_name=f'candidate_recommendations[{index}].summary')
    return f'rec.{_req_029_slugify(summary)}'

def _req_044_class_id(value: Any, *, field_name: str) -> str:
    class_id = _require_text(value, field_name=field_name)
    if not REQ_044_CLASS_ID_RE.match(class_id):
        raise Req044Error(f'{field_name} must match {REQ_044_CLASS_ID_RE.pattern}')
    return class_id

def _req_044_normalize_required_recommendation_classes(value: Any, *, anchor_source: str, field_name: str) -> list[dict[str, Any]]:
    if anchor_source not in REQ_044_ALLOWED_ANCHOR_SOURCES:
        raise Req044Error(f'anchor_source must be one of {sorted(REQ_044_ALLOWED_ANCHOR_SOURCES)}')
    if value is None:
        rows: Sequence[Any] = []
    else:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            raise Req044Error(f'{field_name} must be an array')
        rows = value
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_row in enumerate(rows):
        row = _require_mapping(raw_row, field_name=f'{field_name}[{index}]')
        class_id = _req_044_class_id(row.get('class_id'), field_name=f'{field_name}[{index}].class_id')
        if class_id in seen_ids:
            raise Req044Error(f'{field_name}[{index}].class_id must be unique')
        seen_ids.add(class_id)
        required_scope = _require_text(row.get('required_scope'), field_name=f'{field_name}[{index}].required_scope').lower()
        if required_scope not in REQ_029_ALLOWED_RECOMMENDATION_SCOPES:
            raise Req044Error(f'{field_name}[{index}].required_scope must be one of {sorted(REQ_029_ALLOWED_RECOMMENDATION_SCOPES)}')
        project_id = _as_text(row.get('project_id'))
        if required_scope == 'cross-project':
            project_id = _require_text(project_id, field_name=f'{field_name}[{index}].project_id')
        else:
            project_id = ''
        critical = row.get('critical')
        if critical is None:
            critical = required_scope == 'cross-project'
        if not isinstance(critical, bool):
            raise Req044Error(f'{field_name}[{index}].critical must be a boolean')
        normalized.append({'class_id': class_id, 'summary': _require_text(row.get('summary'), field_name=f'{field_name}[{index}].summary'), 'required_scope': required_scope, 'project_id': project_id, 'critical': critical, 'evidence_refs': _normalize_string_list(row.get('evidence_refs'), field_name=f'{field_name}[{index}].evidence_refs', min_items=1), 'anchor_sources': [anchor_source]})
    normalized.sort(key=lambda row: row['class_id'])
    return normalized

def _req_044_merge_required_recommendation_classes(*, mission_required_recommendation_classes: Sequence[Mapping[str, Any]], ecosystem_required_recommendation_classes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in list(mission_required_recommendation_classes) + list(ecosystem_required_recommendation_classes):
        class_id = str(row['class_id'])
        existing = merged.get(class_id)
        if existing is None:
            merged[class_id] = {'class_id': class_id, 'summary': str(row['summary']), 'required_scope': str(row['required_scope']), 'project_id': str(row['project_id']), 'critical': bool(row['critical']), 'evidence_refs': list(row['evidence_refs']), 'anchor_sources': list(row['anchor_sources'])}
            continue
        if existing['required_scope'] != str(row['required_scope']):
            raise Req044Error(f'class_id {class_id} cannot map to multiple required_scope values')
        if existing['project_id'] != str(row['project_id']):
            raise Req044Error(f'class_id {class_id} cannot map to multiple project_id values')
        existing['critical'] = bool(existing['critical']) or bool(row['critical'])
        existing['evidence_refs'] = _collect_unique_refs(existing['evidence_refs'], row['evidence_refs'])
        existing['anchor_sources'] = _dedupe_preserving_order(list(existing['anchor_sources']) + list(row['anchor_sources']))
    return [merged[class_id] for class_id in sorted(merged)]

def _req_044_normalize_call_chain(value: Any, *, field_name: str='call_chain') -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise Req044Error(f'{field_name} must be an array')
    normalized: list[dict[str, Any]] = []
    seen_sequences: set[int] = set()
    seen_call_ids: set[str] = set()
    for index, raw_row in enumerate(value):
        row = _require_mapping(raw_row, field_name=f'{field_name}[{index}]')
        sequence = row.get('sequence')
        if isinstance(sequence, bool) or not isinstance(sequence, int):
            raise Req044Error(f'{field_name}[{index}].sequence must be an integer')
        if sequence < 1:
            raise Req044Error(f'{field_name}[{index}].sequence must be >= 1')
        if sequence in seen_sequences:
            raise Req044Error(f'{field_name}[{index}].sequence must be unique')
        seen_sequences.add(sequence)
        call_id = _require_text(row.get('call_id'), field_name=f'{field_name}[{index}].call_id')
        if call_id in seen_call_ids:
            raise Req044Error(f'{field_name}[{index}].call_id must be unique')
        seen_call_ids.add(call_id)
        normalized.append({'sequence': sequence, 'call_id': call_id, 'phase': _require_text(row.get('phase'), field_name=f'{field_name}[{index}].phase'), 'output_ref': _require_text(row.get('output_ref'), field_name=f'{field_name}[{index}].output_ref')})
    normalized.sort(key=lambda row: row['sequence'])
    expected_sequences = list(range(1, len(normalized) + 1))
    actual_sequences = [row['sequence'] for row in normalized]
    if actual_sequences != expected_sequences:
        raise Req044Error(f'{field_name}.sequence must be contiguous starting at 1')
    return normalized

def _req_044_normalize_strategic_claims(value: Any, *, call_depth: int, field_name: str='strategic_claims') -> list[dict[str, Any]]:
    if value is None:
        return []
    try:
        return _req_030_normalize_strategic_claims(value, call_depth=call_depth, field_name=field_name)
    except Req030Error as exc:
        raise Req044Error(str(exc)) from exc

def _req_044_normalize_candidate_recommendations(value: Any, *, field_name: str='candidate_recommendations') -> list[dict[str, Any]]:
    if value is None:
        rows: Sequence[Any] = []
    else:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            raise Req044Error(f'{field_name} must be an array')
        rows = value
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_row in enumerate(rows):
        row = _require_mapping(raw_row, field_name=f'{field_name}[{index}]')
        recommendation_id = _req_029_recommendation_id_from_candidate(row, index=index)
        if recommendation_id in seen_ids:
            raise Req044Error(f'{field_name}[{index}].recommendation_id must be unique')
        seen_ids.add(recommendation_id)
        recommendation_scope = _require_text(row.get('recommendation_scope'), field_name=f'{field_name}[{index}].recommendation_scope').lower()
        if recommendation_scope not in REQ_029_ALLOWED_RECOMMENDATION_SCOPES:
            raise Req044Error(f'{field_name}[{index}].recommendation_scope must be one of {sorted(REQ_029_ALLOWED_RECOMMENDATION_SCOPES)}')
        project_id = _as_text(row.get('project_id'))
        if recommendation_scope == 'cross-project':
            project_id = _require_text(project_id, field_name=f'{field_name}[{index}].project_id')
        else:
            project_id = ''
        requires_earth_evidence = row.get('requires_earth_evidence')
        if requires_earth_evidence is None:
            requires_earth_evidence = recommendation_scope == 'cross-project'
        if not isinstance(requires_earth_evidence, bool):
            raise Req044Error(f'{field_name}[{index}].requires_earth_evidence must be a boolean')
        if recommendation_scope == 'cross-project':
            requires_earth_evidence = True
        strategic_claim_ids = _normalize_string_list(row.get('strategic_claim_ids'), field_name=f'{field_name}[{index}].strategic_claim_ids')
        normalized.append({'recommendation_id': recommendation_id, 'recommendation_class_id': _req_044_class_id(row.get('recommendation_class_id'), field_name=f'{field_name}[{index}].recommendation_class_id'), 'summary': _require_text(row.get('summary'), field_name=f'{field_name}[{index}].summary'), 'rationale': _require_text(row.get('rationale'), field_name=f'{field_name}[{index}].rationale'), 'recommendation_scope': recommendation_scope, 'project_id': project_id, 'requires_earth_evidence': requires_earth_evidence, 'evidence_refs': _normalize_string_list(row.get('evidence_refs'), field_name=f'{field_name}[{index}].evidence_refs', min_items=1), 'next_step': _require_text(row.get('next_step'), field_name=f'{field_name}[{index}].next_step')})
        if strategic_claim_ids:
            normalized[-1]['strategic_claim_ids'] = strategic_claim_ids
    normalized.sort(key=lambda row: row['recommendation_id'])
    return normalized

def _req_044_contract_output_ref(*, call_id: str) -> str:
    return f'{REQ_044_REQUIREMENT_ID}::call::{call_id}::output::recommendation_omission_detector'

def _req_044_build_trace_rows(*, processing_call_id: str, call_id: str, target_project_evidence_refs: Sequence[str], earth_sweep_evidence_refs: Sequence[str], cross_project_context: Sequence[Mapping[str, Any]], required_recommendation_classes: Sequence[Mapping[str, Any]], candidate_recommendations: Sequence[Mapping[str, Any]], omitted_count: int, missing_critical_cross_project_count: int, local_only_plan_detected: bool) -> list[dict[str, Any]]:
    cross_project_refs = _collect_unique_refs(*[row['evidence_refs'] for row in cross_project_context])
    required_refs = _collect_unique_refs(*[row['evidence_refs'] for row in required_recommendation_classes])
    candidate_refs = _collect_unique_refs(*[row['evidence_refs'] for row in candidate_recommendations])
    input_refs = _dedupe_preserving_order(list(target_project_evidence_refs) + list(earth_sweep_evidence_refs) + list(cross_project_refs) + list(required_refs) + list(candidate_refs))
    output_ref = _req_044_contract_output_ref(call_id=call_id)
    return [{'schema_version': REQ_044_LLM_CALL_TRACE_SCHEMA_VERSION, 'requirement_id': REQ_044_REQUIREMENT_ID, 'processing_call_id': processing_call_id, 'call_id': call_id, 'sequence': 1, 'call_objective': REQ_044_CALL_OBJECTIVE, 'input_refs': input_refs, 'output_refs': [output_ref], 'handoff_summary': f'Call omission-detector emits {output_ref} with omitted_classes={omitted_count}, missing_critical_cross_project_classes={missing_critical_cross_project_count}, local_only_plan_detected={str(local_only_plan_detected).lower()}.'}]

def _req_044_canonical_input(*, target_project_root: str, earth_root: str, output_root: str, revision_identity: str, strategy_goal: str, call_id: str, checked_at_utc: str) -> dict[str, Any]:
    return {'runtime_mode': RUNTIME_MODE, 'execution_mode': EXECUTION_MODE, 'target_project_root': target_project_root, 'earth_root': earth_root, 'output_root': output_root, 'revision_identity': revision_identity, 'strategy_goal': strategy_goal, 'analysis_type': REQ_044_ANALYSIS_TYPE, 'call_id': call_id, 'checked_at_utc': checked_at_utc}

def _req_044_canonical_processing_input(*, mission_required_recommendation_classes: Sequence[Mapping[str, Any]], ecosystem_required_recommendation_classes: Sequence[Mapping[str, Any]], candidate_recommendations: Sequence[Mapping[str, Any]], cross_project_context: Sequence[Mapping[str, Any]], target_project_evidence_refs: Sequence[str], earth_sweep_evidence_refs: Sequence[str], call_chain: Sequence[Mapping[str, Any]] | None=None, strategic_claims: Sequence[Mapping[str, Any]] | None=None) -> dict[str, Any]:
    canonical = {'mission_required_recommendation_classes': [dict(row) for row in mission_required_recommendation_classes], 'ecosystem_required_recommendation_classes': [dict(row) for row in ecosystem_required_recommendation_classes], 'candidate_recommendations': [dict(row) for row in candidate_recommendations], 'cross_project_context': [dict(row) for row in cross_project_context], 'target_project_evidence_refs': list(target_project_evidence_refs), 'earth_sweep_evidence_refs': list(earth_sweep_evidence_refs)}
    if call_chain:
        canonical['call_chain'] = [dict(row) for row in call_chain]
    if strategic_claims:
        canonical['strategic_claims'] = [dict(row) for row in strategic_claims]
    return canonical

def build_req_044_recommendation_omission_detector(*, target_project_root: str, earth_root: str, output_root: str, revision_identity: str, strategy_goal: str, mission_required_recommendation_classes: Sequence[Mapping[str, Any]] | None=None, ecosystem_required_recommendation_classes: Sequence[Mapping[str, Any]] | None=None, candidate_recommendations: Sequence[Mapping[str, Any]] | None=None, call_chain: Sequence[Mapping[str, Any]] | None=None, strategic_claims: Sequence[Mapping[str, Any]] | None=None, cross_project_context: Sequence[Mapping[str, Any]] | None=None, target_project_evidence_refs: Sequence[Any] | None=None, earth_sweep_evidence_refs: Sequence[Any] | None=None, call_id: str='call-recommendation-omission-detector', checked_at_utc: str | None=None) -> dict[str, Any]:
    normalized_target_root = _normalize_root(target_project_root, field_name='target_project_root')
    normalized_earth_root = _normalize_root(earth_root, field_name='earth_root')
    normalized_output_root = _normalize_root(output_root, field_name='output_root')
    normalized_revision_identity = _require_text(revision_identity, field_name='revision_identity')
    normalized_strategy_goal = _require_text(strategy_goal, field_name='strategy_goal')
    normalized_call_id = _require_text(call_id, field_name='call_id')
    normalized_checked_at_utc = _require_text(checked_at_utc or utc_now_iso(), field_name='checked_at_utc')
    normalized_target_refs = _normalize_string_list(target_project_evidence_refs, field_name='target_project_evidence_refs')
    normalized_earth_refs = _normalize_string_list(earth_sweep_evidence_refs, field_name='earth_sweep_evidence_refs')
    normalized_cross_project_context = _normalize_cross_project_context(cross_project_context)
    normalized_mission_required_classes = _req_044_normalize_required_recommendation_classes(mission_required_recommendation_classes, anchor_source='mission', field_name='mission_required_recommendation_classes')
    normalized_ecosystem_required_classes = _req_044_normalize_required_recommendation_classes(ecosystem_required_recommendation_classes, anchor_source='ecosystem', field_name='ecosystem_required_recommendation_classes')
    normalized_required_classes = _req_044_merge_required_recommendation_classes(mission_required_recommendation_classes=normalized_mission_required_classes, ecosystem_required_recommendation_classes=normalized_ecosystem_required_classes)
    if not normalized_required_classes:
        raise Req044Error('at least one required recommendation class must be supplied by mission or ecosystem anchors')
    normalized_candidate_recommendations = _req_044_normalize_candidate_recommendations(candidate_recommendations)
    normalized_call_chain = _req_044_normalize_call_chain(call_chain)
    if strategic_claims is not None and (not normalized_call_chain):
        raise Req044Error('call_chain must be supplied when strategic_claims are provided')
    normalized_strategic_claims = _req_044_normalize_strategic_claims(strategic_claims, call_depth=len(normalized_call_chain))
    candidates_by_class: dict[str, list[dict[str, Any]]] = {}
    for row in normalized_candidate_recommendations:
        candidates_by_class.setdefault(str(row['recommendation_class_id']), []).append(row)
    for rows in candidates_by_class.values():
        rows.sort(key=lambda row: row['recommendation_id'])
    cross_context_by_project = {str(row['project_id']): row for row in normalized_cross_project_context}
    call_chain_output_ref_by_sequence = {int(row['sequence']): str(row['output_ref']) for row in normalized_call_chain}
    call_chain_output_refs = [str(row['output_ref']) for row in normalized_call_chain]
    contract_output_ref = _req_044_contract_output_ref(call_id=normalized_call_id)
    cross_project_refs = _collect_unique_refs(*[row['evidence_refs'] for row in normalized_cross_project_context])
    available_citation_refs = set(_collect_unique_refs(normalized_target_refs, normalized_earth_refs, cross_project_refs, call_chain_output_refs))
    recommended_actions: list[dict[str, Any]] = []
    cross_project_obligations: list[dict[str, Any]] = []
    omitted_recommendation_classes: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    claim_rows_by_id: dict[str, list[dict[str, Any]]] = {}
    claim_uncited_refs_by_id: dict[str, list[str]] = {}
    claim_contradiction_refs_by_id: dict[str, list[str]] = {}
    blocked_candidate_by_id: dict[str, dict[str, Any]] = {}

    def _emit_omission(*, required_row: Mapping[str, Any], reason_code: str, summary: str, required_evidence_refs: Sequence[str]) -> None:
        class_id = str(required_row['class_id'])
        omission_row = {'class_id': class_id, 'anchor_sources': list(required_row['anchor_sources']), 'required_scope': str(required_row['required_scope']), 'project_id': str(required_row['project_id']), 'critical': bool(required_row['critical']), 'summary': summary, 'reason_code': reason_code, 'required_evidence_refs': _collect_unique_refs(required_evidence_refs)}
        omitted_recommendation_classes.append(omission_row)
        open_risks.append({'risk_id': f"risk-{class_id}-{reason_code.replace('_', '-')}", 'reason_code': reason_code, 'summary': summary, 'required_evidence_refs': list(omission_row['required_evidence_refs'])})
    for claim in normalized_strategic_claims:
        claim_id = str(claim['claim_id'])
        claim_rows_by_id.setdefault(claim_id, []).append(claim)
        source_output_ref = call_chain_output_ref_by_sequence.get(int(claim['source_call_sequence']), '')
        citation_refs = list(claim['evidence_refs'])
        if citation_refs and set(citation_refs).issubset(available_citation_refs):
            continue
        claim_uncited_refs_by_id[claim_id] = _collect_unique_refs(claim_uncited_refs_by_id.get(claim_id, []), [source_output_ref], citation_refs)
    for claim_id in sorted(claim_uncited_refs_by_id):
        risk_refs = claim_uncited_refs_by_id[claim_id]
        summary_rows = claim_rows_by_id.get(claim_id, [])
        summary = str(summary_rows[0]['summary']) if summary_rows else f'Strategic claim {claim_id} lacks citations.'
        open_risks.append({'risk_id': f'risk-claim-{claim_id}-citation', 'reason_code': 'uncited_strategic_claim', 'summary': summary, 'required_evidence_refs': list(risk_refs)})
    for claim_id in sorted(claim_rows_by_id):
        claim_rows = claim_rows_by_id[claim_id]
        analysis_rows = [row for row in claim_rows if row['phase'] == 'analysis']
        synthesis_rows = [row for row in claim_rows if row['phase'] == 'synthesis']
        contradiction_refs: list[str] = []
        contradiction_summary = ''
        contradiction_found = False
        for analysis_row in analysis_rows:
            for synthesis_row in synthesis_rows:
                if str(analysis_row['position']) == str(synthesis_row['position']):
                    continue
                contradiction_summary = str(synthesis_row['summary'])
                contradiction_refs = _collect_unique_refs([call_chain_output_ref_by_sequence.get(int(analysis_row['source_call_sequence']), '')], [call_chain_output_ref_by_sequence.get(int(synthesis_row['source_call_sequence']), '')], analysis_row['evidence_refs'], synthesis_row['evidence_refs'])
                contradiction_found = True
                break
            if contradiction_found:
                break
        if not contradiction_found:
            continue
        claim_contradiction_refs_by_id[claim_id] = contradiction_refs
        open_risks.append({'risk_id': f'risk-claim-{claim_id}-contradiction', 'reason_code': 'cross_call_contradiction', 'summary': contradiction_summary, 'required_evidence_refs': contradiction_refs})
    for row in normalized_candidate_recommendations:
        recommendation_id = str(row['recommendation_id'])
        candidate_claim_ids = [_as_text(item) for item in row.get('strategic_claim_ids', []) if _as_text(item)]
        contradiction_claim_ids = sorted(set(candidate_claim_ids).intersection(set(claim_contradiction_refs_by_id)))
        uncited_claim_ids = sorted(set(candidate_claim_ids).intersection(set(claim_uncited_refs_by_id)))
        uncited_candidate_refs = sorted(set(row['evidence_refs']) - available_citation_refs)
        if contradiction_claim_ids:
            blocked_candidate_by_id[recommendation_id] = {'reason_code': 'cross_call_contradiction', 'required_evidence_refs': _collect_unique_refs([contract_output_ref], row['evidence_refs'], *[claim_contradiction_refs_by_id[claim_id] for claim_id in contradiction_claim_ids])}
            continue
        if uncited_claim_ids or uncited_candidate_refs:
            blocked_candidate_by_id[recommendation_id] = {'reason_code': 'uncited_strategic_claim', 'required_evidence_refs': _collect_unique_refs([contract_output_ref], row['evidence_refs'], uncited_candidate_refs, *[claim_uncited_refs_by_id[claim_id] for claim_id in uncited_claim_ids])}
    for required_row in normalized_required_classes:
        class_id = str(required_row['class_id'])
        required_scope = str(required_row['required_scope'])
        required_project_id = str(required_row['project_id'])
        class_candidates = list(candidates_by_class.get(class_id, []))
        scoped_candidates = [row for row in class_candidates if str(row['recommendation_scope']) == required_scope and (required_scope != 'cross-project' or str(row['project_id']) == required_project_id)]
        if not scoped_candidates:
            reason_code = 'missing_recommendation_class' if not class_candidates else 'missing_required_scope'
            _emit_omission(required_row=required_row, reason_code=reason_code, summary=str(required_row['summary']), required_evidence_refs=_collect_unique_refs(required_row['evidence_refs'], *[row['evidence_refs'] for row in class_candidates]))
            continue
        blocked_scoped_candidates = [row for row in scoped_candidates if str(row['recommendation_id']) in blocked_candidate_by_id]
        if blocked_scoped_candidates and len(blocked_scoped_candidates) == len(scoped_candidates):
            blocked_reason_codes = {str(blocked_candidate_by_id[str(row['recommendation_id'])]['reason_code']) for row in blocked_scoped_candidates}
            reason_code = 'cross_call_contradiction' if 'cross_call_contradiction' in blocked_reason_codes else 'uncited_strategic_claim'
            _emit_omission(required_row=required_row, reason_code=reason_code, summary=str(required_row['summary']), required_evidence_refs=_collect_unique_refs(required_row['evidence_refs'], *[row['evidence_refs'] for row in blocked_scoped_candidates], *[blocked_candidate_by_id[str(row['recommendation_id'])]['required_evidence_refs'] for row in blocked_scoped_candidates]))
            continue
        selected = next((row for row in scoped_candidates if str(row['recommendation_id']) not in blocked_candidate_by_id))
        if required_scope == 'cross-project':
            if not normalized_earth_refs:
                _emit_omission(required_row=required_row, reason_code='missing_earth_sweep_evidence_refs', summary=str(required_row['summary']), required_evidence_refs=_collect_unique_refs(required_row['evidence_refs'], selected['evidence_refs']))
                continue
            project_context = cross_context_by_project.get(required_project_id)
            if project_context is None:
                _emit_omission(required_row=required_row, reason_code='missing_cross_project_context', summary=str(required_row['summary']), required_evidence_refs=_collect_unique_refs(required_row['evidence_refs'], selected['evidence_refs']))
                continue
            cross_project_obligations.append({'obligation_id': f'obligation-{class_id}', 'recommendation_id': str(selected['recommendation_id']), 'class_id': class_id, 'project_id': required_project_id, 'summary': str(selected['summary']), 'rationale': str(selected['rationale']), 'next_step': str(selected['next_step']), 'anchor_sources': list(required_row['anchor_sources']), 'critical': bool(required_row['critical']), 'evidence_refs': _collect_unique_refs(required_row['evidence_refs'], selected['evidence_refs'], project_context['evidence_refs'], normalized_earth_refs)})
            continue
        recommended_actions.append({'recommendation_id': str(selected['recommendation_id']), 'class_id': class_id, 'summary': str(selected['summary']), 'rationale': str(selected['rationale']), 'next_step': str(selected['next_step']), 'anchor_sources': list(required_row['anchor_sources']), 'critical': bool(required_row['critical']), 'evidence_refs': _collect_unique_refs(required_row['evidence_refs'], selected['evidence_refs'])})
    recommended_actions.sort(key=lambda row: row['recommendation_id'])
    cross_project_obligations.sort(key=lambda row: row['obligation_id'])
    omitted_recommendation_classes.sort(key=lambda row: row['class_id'])
    required_cross_project_class_ids = sorted({str(row['class_id']) for row in normalized_required_classes if str(row['required_scope']) == 'cross-project'})
    missing_critical_cross_project_class_ids = sorted({str(row['class_id']) for row in omitted_recommendation_classes if str(row['required_scope']) == 'cross-project' and bool(row['critical'])})
    local_only_plan_detected = bool(normalized_candidate_recommendations) and all((str(row['recommendation_scope']) == 'local' for row in normalized_candidate_recommendations)) and bool(required_cross_project_class_ids)
    if local_only_plan_detected:
        critical_omission_refs = _collect_unique_refs(*[row['required_evidence_refs'] for row in omitted_recommendation_classes if str(row['class_id']) in set(missing_critical_cross_project_class_ids)])
        open_risks.append({'risk_id': 'risk-local-only-plan', 'reason_code': 'local_only_plan_ignores_critical_cross_project_obligations', 'summary': 'Local-only recommendation plans cannot satisfy critical cross-project obligations.', 'required_evidence_refs': critical_omission_refs or _collect_unique_refs(*[row['evidence_refs'] for row in normalized_required_classes])})
    open_risks.sort(key=lambda row: row['risk_id'])
    cross_project_refs = _collect_unique_refs(*[row['evidence_refs'] for row in normalized_cross_project_context])
    evidence_refs = _collect_unique_refs(normalized_target_refs, normalized_earth_refs, cross_project_refs, *[row['evidence_refs'] for row in normalized_required_classes], *[row['evidence_refs'] for row in normalized_candidate_recommendations], *[row['evidence_refs'] for row in recommended_actions], *[row['evidence_refs'] for row in cross_project_obligations], *[row['required_evidence_refs'] for row in omitted_recommendation_classes], *[row['required_evidence_refs'] for row in open_risks])
    promoted_actions: list[dict[str, Any]] = list(recommended_actions) + list(cross_project_obligations)
    if local_only_plan_detected or missing_critical_cross_project_class_ids:
        decision = 'resolve-strategy-gaps'
    else:
        decision = _recommendation_decision(recommended_actions=promoted_actions, open_risks=open_risks)
    confidence = _recommendation_confidence(evidence_refs=evidence_refs, open_risks=open_risks)
    rationale = f'required_classes={len(normalized_required_classes)} omissions={len(omitted_recommendation_classes)} local_actions={len(recommended_actions)} obligations={len(cross_project_obligations)} open_risks={len(open_risks)}'
    canonical_input = _req_044_canonical_input(target_project_root=normalized_target_root, earth_root=normalized_earth_root, output_root=normalized_output_root, revision_identity=normalized_revision_identity, strategy_goal=normalized_strategy_goal, call_id=normalized_call_id, checked_at_utc=normalized_checked_at_utc)
    canonical_processing_input = _req_044_canonical_processing_input(mission_required_recommendation_classes=normalized_mission_required_classes, ecosystem_required_recommendation_classes=normalized_ecosystem_required_classes, candidate_recommendations=normalized_candidate_recommendations, cross_project_context=normalized_cross_project_context, target_project_evidence_refs=normalized_target_refs, earth_sweep_evidence_refs=normalized_earth_refs, call_chain=normalized_call_chain, strategic_claims=normalized_strategic_claims)
    canonical_input_sha = _canonical_digest(canonical_input)
    processing_sha = _canonical_digest(canonical_processing_input)
    processing_call_id = f'req044-processing-{processing_sha[:16]}'
    llm_call_trace_rows = _req_044_build_trace_rows(processing_call_id=processing_call_id, call_id=normalized_call_id, target_project_evidence_refs=normalized_target_refs, earth_sweep_evidence_refs=normalized_earth_refs, cross_project_context=normalized_cross_project_context, required_recommendation_classes=normalized_required_classes, candidate_recommendations=normalized_candidate_recommendations, omitted_count=len(omitted_recommendation_classes), missing_critical_cross_project_count=len(missing_critical_cross_project_class_ids), local_only_plan_detected=local_only_plan_detected)
    return {'schema_version': REQ_044_SCHEMA_VERSION, 'requirement_id': REQ_044_REQUIREMENT_ID, 'analysis_type': REQ_044_ANALYSIS_TYPE, 'call_id': normalized_call_id, 'checked_at_utc': normalized_checked_at_utc, 'processing_behavior': {'strategy': REQ_044_PROCESSING_STRATEGY, 'reasoning_mode': REQ_044_REASONING_MODE, 'strict_evidence_discipline': True, 'context_inputs': {'target_project': {'project_root': normalized_target_root, 'evidence_refs': list(normalized_target_refs)}, 'earth_sweep': {'earth_root': normalized_earth_root, 'evidence_refs': list(normalized_earth_refs)}, 'cross_project_context': [dict(row) for row in normalized_cross_project_context], 'mission_required_recommendation_classes': [dict(row) for row in normalized_mission_required_classes], 'ecosystem_required_recommendation_classes': [dict(row) for row in normalized_ecosystem_required_classes], 'candidate_recommendations': [dict(row) for row in normalized_candidate_recommendations], **({'call_chain': [dict(row) for row in normalized_call_chain]} if normalized_call_chain else {}), **({'strategic_claims': [dict(row) for row in normalized_strategic_claims]} if normalized_strategic_claims else {})}, 'context_usage': {'required_recommendation_class_ids_considered': [str(row['class_id']) for row in normalized_required_classes], 'required_cross_project_class_ids': required_cross_project_class_ids, 'candidate_recommendation_ids_considered': [str(row['recommendation_id']) for row in normalized_candidate_recommendations], 'emitted_recommendation_ids': _dedupe_preserving_order([row['recommendation_id'] for row in recommended_actions] + [row['recommendation_id'] for row in cross_project_obligations]), 'omitted_recommendation_class_ids': [str(row['class_id']) for row in omitted_recommendation_classes], 'missing_critical_cross_project_class_ids': missing_critical_cross_project_class_ids, 'local_only_plan_detected': local_only_plan_detected, 'cross_project_obligation_ids_emitted': [str(row['obligation_id']) for row in cross_project_obligations], 'open_risk_ids_emitted': [str(row['risk_id']) for row in open_risks], 'blocked_recommendation_ids': sorted(blocked_candidate_by_id), 'evidence_refs_used': list(evidence_refs)}, 'recommendation': {'decision': decision, 'rationale': rationale, 'confidence': confidence, 'evidence_refs': list(evidence_refs), 'recommended_actions': recommended_actions, 'cross_project_obligations': cross_project_obligations, 'omitted_recommendation_classes': omitted_recommendation_classes, 'open_risks': open_risks}}, 'call_metadata': {'reproducibility': 'deterministic-input-fingerprint', 'canonical_input': canonical_input, 'canonical_input_sha256': canonical_input_sha, 'reproducible_call_id': f'req044-{canonical_input_sha[:16]}', 'canonical_processing_input': canonical_processing_input, 'processing_input_sha256': processing_sha, 'processing_call_id': processing_call_id, 'llm_call_trace_schema_version': REQ_044_LLM_CALL_TRACE_SCHEMA_VERSION, 'llm_call_trace_path': LLM_CALL_TRACE_RELATIVE_PATH, 'llm_call_trace_sha256': _canonical_digest(llm_call_trace_rows), 'llm_call_trace_rows': llm_call_trace_rows}}

def validate_req_044_recommendation_omission_detector(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ['payload must be a JSON object']
    if payload.get('schema_version') != REQ_044_SCHEMA_VERSION:
        errors.append(f'schema_version must be {REQ_044_SCHEMA_VERSION}')
    if payload.get('requirement_id') != REQ_044_REQUIREMENT_ID:
        errors.append(f'requirement_id must be {REQ_044_REQUIREMENT_ID}')
    if payload.get('analysis_type') != REQ_044_ANALYSIS_TYPE:
        errors.append(f'analysis_type must be {REQ_044_ANALYSIS_TYPE}')
    if not _as_text(payload.get('call_id')):
        errors.append('call_id is required')
    if not _as_text(payload.get('checked_at_utc')):
        errors.append('checked_at_utc is required')
    processing_behavior = payload.get('processing_behavior')
    if not isinstance(processing_behavior, Mapping):
        return errors + ['processing_behavior must be an object']
    if processing_behavior.get('strategy') != REQ_044_PROCESSING_STRATEGY:
        errors.append(f'processing_behavior.strategy must be {REQ_044_PROCESSING_STRATEGY}')
    if processing_behavior.get('reasoning_mode') != REQ_044_REASONING_MODE:
        errors.append(f'processing_behavior.reasoning_mode must be {REQ_044_REASONING_MODE}')
    if processing_behavior.get('strict_evidence_discipline') is not True:
        errors.append('processing_behavior.strict_evidence_discipline must be true')
    context_inputs = processing_behavior.get('context_inputs')
    normalized_target_refs: list[str] = []
    normalized_earth_refs: list[str] = []
    normalized_cross_project_context: list[dict[str, Any]] = []
    normalized_mission_required_classes: list[dict[str, Any]] = []
    normalized_ecosystem_required_classes: list[dict[str, Any]] = []
    normalized_required_classes: list[dict[str, Any]] = []
    normalized_candidate_recommendations: list[dict[str, Any]] = []
    normalized_call_chain: list[dict[str, Any]] = []
    normalized_strategic_claims: list[dict[str, Any]] = []
    if not isinstance(context_inputs, Mapping):
        return errors + ['processing_behavior.context_inputs must be an object']
    target_project = context_inputs.get('target_project')
    if not isinstance(target_project, Mapping):
        errors.append('processing_behavior.context_inputs.target_project must be an object')
    else:
        normalized_target_refs = sorted({_as_text(ref) for ref in target_project.get('evidence_refs', []) if _as_text(ref)})
    earth_sweep = context_inputs.get('earth_sweep')
    if not isinstance(earth_sweep, Mapping):
        errors.append('processing_behavior.context_inputs.earth_sweep must be an object')
    else:
        normalized_earth_refs = sorted({_as_text(ref) for ref in earth_sweep.get('evidence_refs', []) if _as_text(ref)})
    try:
        normalized_cross_project_context = _normalize_cross_project_context(context_inputs.get('cross_project_context'))
    except ValueError as exc:
        errors.append(str(exc))
    try:
        normalized_mission_required_classes = _req_044_normalize_required_recommendation_classes(context_inputs.get('mission_required_recommendation_classes'), anchor_source='mission', field_name='processing_behavior.context_inputs.mission_required_recommendation_classes')
    except Req044Error as exc:
        errors.append(str(exc))
    try:
        normalized_ecosystem_required_classes = _req_044_normalize_required_recommendation_classes(context_inputs.get('ecosystem_required_recommendation_classes'), anchor_source='ecosystem', field_name='processing_behavior.context_inputs.ecosystem_required_recommendation_classes')
    except Req044Error as exc:
        errors.append(str(exc))
    try:
        normalized_required_classes = _req_044_merge_required_recommendation_classes(mission_required_recommendation_classes=normalized_mission_required_classes, ecosystem_required_recommendation_classes=normalized_ecosystem_required_classes)
    except Req044Error as exc:
        errors.append(str(exc))
    try:
        normalized_candidate_recommendations = _req_044_normalize_candidate_recommendations(context_inputs.get('candidate_recommendations'))
    except Req044Error as exc:
        errors.append(str(exc))
    try:
        normalized_call_chain = _req_044_normalize_call_chain(context_inputs.get('call_chain'))
    except Req044Error as exc:
        errors.append(str(exc))
    if context_inputs.get('strategic_claims') is not None and (not normalized_call_chain):
        errors.append('processing_behavior.context_inputs.call_chain must be supplied when strategic_claims are present')
    try:
        normalized_strategic_claims = _req_044_normalize_strategic_claims(context_inputs.get('strategic_claims'), call_depth=len(normalized_call_chain), field_name='processing_behavior.context_inputs.strategic_claims')
    except Req044Error as exc:
        errors.append(str(exc))
    if not normalized_required_classes:
        errors.append('processing_behavior.context_inputs must include at least one required recommendation class')
    context_usage = processing_behavior.get('context_usage')
    if not isinstance(context_usage, Mapping):
        errors.append('processing_behavior.context_usage must be an object')
        context_usage = {}
    else:
        for key in ('required_recommendation_class_ids_considered', 'required_cross_project_class_ids', 'candidate_recommendation_ids_considered', 'emitted_recommendation_ids', 'omitted_recommendation_class_ids', 'missing_critical_cross_project_class_ids', 'cross_project_obligation_ids_emitted', 'open_risk_ids_emitted', 'evidence_refs_used'):
            value = context_usage.get(key)
            if not isinstance(value, list) or any((not _as_text(item) for item in value)):
                errors.append(f'processing_behavior.context_usage.{key} must be a string array')
        if not isinstance(context_usage.get('local_only_plan_detected'), bool):
            errors.append('processing_behavior.context_usage.local_only_plan_detected must be a boolean')
    recommendation = processing_behavior.get('recommendation')
    recommended_actions: list[Mapping[str, Any]] = []
    cross_project_obligations: list[Mapping[str, Any]] = []
    omitted_recommendation_classes: list[Mapping[str, Any]] = []
    open_risks: list[Mapping[str, Any]] = []
    if not isinstance(recommendation, Mapping):
        return errors + ['processing_behavior.recommendation must be an object']
    required_recommendation_keys = {'decision', 'rationale', 'confidence', 'evidence_refs', 'recommended_actions', 'cross_project_obligations', 'omitted_recommendation_classes', 'open_risks'}
    missing_recommendation_keys = sorted(required_recommendation_keys - set(recommendation.keys()))
    if missing_recommendation_keys:
        errors.append(f'processing_behavior.recommendation missing keys: {missing_recommendation_keys}')
    if not _as_text(recommendation.get('decision')):
        errors.append('processing_behavior.recommendation.decision is required')
    if not _as_text(recommendation.get('rationale')):
        errors.append('processing_behavior.recommendation.rationale is required')
    if _as_text(recommendation.get('confidence')) not in {'high', 'medium', 'low'}:
        errors.append('processing_behavior.recommendation.confidence must be high, medium, or low')
    if not isinstance(recommendation.get('evidence_refs'), list) or any((not _as_text(item) for item in recommendation.get('evidence_refs', []))):
        errors.append('processing_behavior.recommendation.evidence_refs must be a string array')
    if not isinstance(recommendation.get('recommended_actions'), list):
        errors.append('processing_behavior.recommendation.recommended_actions must be a list')
    else:
        recommended_actions = [row for row in recommendation.get('recommended_actions', []) if isinstance(row, Mapping)]
    if not isinstance(recommendation.get('cross_project_obligations'), list):
        errors.append('processing_behavior.recommendation.cross_project_obligations must be a list')
    else:
        cross_project_obligations = [row for row in recommendation.get('cross_project_obligations', []) if isinstance(row, Mapping)]
    if not isinstance(recommendation.get('omitted_recommendation_classes'), list):
        errors.append('processing_behavior.recommendation.omitted_recommendation_classes must be a list')
    else:
        omitted_recommendation_classes = [row for row in recommendation.get('omitted_recommendation_classes', []) if isinstance(row, Mapping)]
    if not isinstance(recommendation.get('open_risks'), list):
        errors.append('processing_behavior.recommendation.open_risks must be a list')
    else:
        open_risks = [row for row in recommendation.get('open_risks', []) if isinstance(row, Mapping)]
    for index, row in enumerate(recommended_actions):
        if not REQ_029_RECOMMENDATION_ID_RE.match(_as_text(row.get('recommendation_id'))):
            errors.append(f'processing_behavior.recommendation.recommended_actions[{index}].recommendation_id must match {REQ_029_RECOMMENDATION_ID_RE.pattern}')
        if not REQ_044_CLASS_ID_RE.match(_as_text(row.get('class_id'))):
            errors.append(f'processing_behavior.recommendation.recommended_actions[{index}].class_id must match {REQ_044_CLASS_ID_RE.pattern}')
        if not _as_text(row.get('summary')):
            errors.append(f'processing_behavior.recommendation.recommended_actions[{index}].summary is required')
        if not _as_text(row.get('rationale')):
            errors.append(f'processing_behavior.recommendation.recommended_actions[{index}].rationale is required')
        if not _as_text(row.get('next_step')):
            errors.append(f'processing_behavior.recommendation.recommended_actions[{index}].next_step is required')
        anchor_sources = row.get('anchor_sources')
        if not isinstance(anchor_sources, list) or not anchor_sources:
            errors.append(f'processing_behavior.recommendation.recommended_actions[{index}].anchor_sources must be non-empty list')
        elif any((_as_text(source) not in REQ_044_ALLOWED_ANCHOR_SOURCES for source in anchor_sources)):
            errors.append(f'processing_behavior.recommendation.recommended_actions[{index}].anchor_sources must only include mission or ecosystem')
        if not isinstance(row.get('critical'), bool):
            errors.append(f'processing_behavior.recommendation.recommended_actions[{index}].critical must be a boolean')
        if not isinstance(row.get('evidence_refs'), list) or not row.get('evidence_refs'):
            errors.append(f'processing_behavior.recommendation.recommended_actions[{index}].evidence_refs must be non-empty list')
    earth_ref_set = {ref for ref in normalized_earth_refs if _is_earth_evidence_ref(ref)}
    if cross_project_obligations and (not earth_ref_set):
        errors.append('processing_behavior.recommendation.cross_project_obligations must be empty without earth_sweep evidence refs')
    for index, row in enumerate(cross_project_obligations):
        if not _as_text(row.get('obligation_id')):
            errors.append(f'processing_behavior.recommendation.cross_project_obligations[{index}].obligation_id is required')
        if not REQ_029_RECOMMENDATION_ID_RE.match(_as_text(row.get('recommendation_id'))):
            errors.append(f'processing_behavior.recommendation.cross_project_obligations[{index}].recommendation_id must match {REQ_029_RECOMMENDATION_ID_RE.pattern}')
        if not REQ_044_CLASS_ID_RE.match(_as_text(row.get('class_id'))):
            errors.append(f'processing_behavior.recommendation.cross_project_obligations[{index}].class_id must match {REQ_044_CLASS_ID_RE.pattern}')
        if not _as_text(row.get('project_id')):
            errors.append(f'processing_behavior.recommendation.cross_project_obligations[{index}].project_id is required')
        if not _as_text(row.get('summary')):
            errors.append(f'processing_behavior.recommendation.cross_project_obligations[{index}].summary is required')
        if not _as_text(row.get('rationale')):
            errors.append(f'processing_behavior.recommendation.cross_project_obligations[{index}].rationale is required')
        if not _as_text(row.get('next_step')):
            errors.append(f'processing_behavior.recommendation.cross_project_obligations[{index}].next_step is required')
        anchor_sources = row.get('anchor_sources')
        if not isinstance(anchor_sources, list) or not anchor_sources:
            errors.append(f'processing_behavior.recommendation.cross_project_obligations[{index}].anchor_sources must be non-empty list')
        elif any((_as_text(source) not in REQ_044_ALLOWED_ANCHOR_SOURCES for source in anchor_sources)):
            errors.append(f'processing_behavior.recommendation.cross_project_obligations[{index}].anchor_sources must only include mission or ecosystem')
        if not isinstance(row.get('critical'), bool):
            errors.append(f'processing_behavior.recommendation.cross_project_obligations[{index}].critical must be a boolean')
        if not isinstance(row.get('evidence_refs'), list) or not row.get('evidence_refs'):
            errors.append(f'processing_behavior.recommendation.cross_project_obligations[{index}].evidence_refs must be non-empty list')
            continue
        obligation_ref_set = {_as_text(ref) for ref in row.get('evidence_refs', []) if _as_text(ref)}
        if earth_ref_set and (not obligation_ref_set.intersection(earth_ref_set)):
            errors.append(f'processing_behavior.recommendation.cross_project_obligations[{index}] must include earth_sweep evidence refs')
    for index, row in enumerate(omitted_recommendation_classes):
        if not REQ_044_CLASS_ID_RE.match(_as_text(row.get('class_id'))):
            errors.append(f'processing_behavior.recommendation.omitted_recommendation_classes[{index}].class_id must match {REQ_044_CLASS_ID_RE.pattern}')
        anchor_sources = row.get('anchor_sources')
        if not isinstance(anchor_sources, list) or not anchor_sources:
            errors.append(f'processing_behavior.recommendation.omitted_recommendation_classes[{index}].anchor_sources must be non-empty list')
        elif any((_as_text(source) not in REQ_044_ALLOWED_ANCHOR_SOURCES for source in anchor_sources)):
            errors.append(f'processing_behavior.recommendation.omitted_recommendation_classes[{index}].anchor_sources must only include mission or ecosystem')
        required_scope = _as_text(row.get('required_scope'))
        if required_scope not in REQ_029_ALLOWED_RECOMMENDATION_SCOPES:
            errors.append(f'processing_behavior.recommendation.omitted_recommendation_classes[{index}].required_scope must be local or cross-project')
        if required_scope == 'cross-project' and (not _as_text(row.get('project_id'))):
            errors.append(f'processing_behavior.recommendation.omitted_recommendation_classes[{index}].project_id is required for cross-project scope')
        if not isinstance(row.get('critical'), bool):
            errors.append(f'processing_behavior.recommendation.omitted_recommendation_classes[{index}].critical must be a boolean')
        if not _as_text(row.get('reason_code')):
            errors.append(f'processing_behavior.recommendation.omitted_recommendation_classes[{index}].reason_code is required')
        if not _as_text(row.get('summary')):
            errors.append(f'processing_behavior.recommendation.omitted_recommendation_classes[{index}].summary is required')
        if not isinstance(row.get('required_evidence_refs'), list) or not row.get('required_evidence_refs'):
            errors.append(f'processing_behavior.recommendation.omitted_recommendation_classes[{index}].required_evidence_refs must be non-empty list')
    for index, row in enumerate(open_risks):
        if not _as_text(row.get('risk_id')):
            errors.append(f'processing_behavior.recommendation.open_risks[{index}].risk_id is required')
        if not _as_text(row.get('reason_code')):
            errors.append(f'processing_behavior.recommendation.open_risks[{index}].reason_code is required')
        if not isinstance(row.get('required_evidence_refs'), list) or not row.get('required_evidence_refs'):
            errors.append(f'processing_behavior.recommendation.open_risks[{index}].required_evidence_refs must be non-empty list')
    metadata = payload.get('call_metadata')
    if not isinstance(metadata, Mapping):
        return errors + ['call_metadata must be an object']
    if metadata.get('reproducibility') != 'deterministic-input-fingerprint':
        errors.append('call_metadata.reproducibility must be deterministic-input-fingerprint')
    canonical_input = metadata.get('canonical_input')
    if not isinstance(canonical_input, Mapping):
        errors.append('call_metadata.canonical_input must be an object')
    else:
        expected_canonical_input = _req_044_canonical_input(target_project_root=_as_text(target_project.get('project_root')) if isinstance(target_project, Mapping) else '', earth_root=_as_text(earth_sweep.get('earth_root')) if isinstance(earth_sweep, Mapping) else '', output_root=_as_text(canonical_input.get('output_root')), revision_identity=_as_text(canonical_input.get('revision_identity')), strategy_goal=_as_text(canonical_input.get('strategy_goal')), call_id=_as_text(payload.get('call_id')), checked_at_utc=_as_text(payload.get('checked_at_utc')))
        if dict(canonical_input) != expected_canonical_input:
            errors.append('call_metadata.canonical_input must mirror normalized invocation anchors')
        expected_input_sha = _canonical_digest(expected_canonical_input)
        if metadata.get('canonical_input_sha256') != expected_input_sha:
            errors.append('call_metadata.canonical_input_sha256 does not match canonical input')
        if metadata.get('reproducible_call_id') != f'req044-{expected_input_sha[:16]}':
            errors.append('call_metadata.reproducible_call_id does not match canonical digest')
    canonical_processing_input = metadata.get('canonical_processing_input')
    if not isinstance(canonical_processing_input, Mapping):
        errors.append('call_metadata.canonical_processing_input must be an object')
    else:
        expected_processing_input = _req_044_canonical_processing_input(mission_required_recommendation_classes=normalized_mission_required_classes, ecosystem_required_recommendation_classes=normalized_ecosystem_required_classes, candidate_recommendations=normalized_candidate_recommendations, cross_project_context=normalized_cross_project_context, target_project_evidence_refs=normalized_target_refs, earth_sweep_evidence_refs=normalized_earth_refs, call_chain=normalized_call_chain, strategic_claims=normalized_strategic_claims)
        if dict(canonical_processing_input) != expected_processing_input:
            errors.append('call_metadata.canonical_processing_input must mirror normalized omission-detector inputs')
        expected_processing_sha = _canonical_digest(expected_processing_input)
        if metadata.get('processing_input_sha256') != expected_processing_sha:
            errors.append('call_metadata.processing_input_sha256 does not match processing input')
        if metadata.get('processing_call_id') != f'req044-processing-{expected_processing_sha[:16]}':
            errors.append('call_metadata.processing_call_id does not match processing digest')
    if metadata.get('llm_call_trace_schema_version') != REQ_044_LLM_CALL_TRACE_SCHEMA_VERSION:
        errors.append(f'call_metadata.llm_call_trace_schema_version must be {REQ_044_LLM_CALL_TRACE_SCHEMA_VERSION}')
    if metadata.get('llm_call_trace_path') != LLM_CALL_TRACE_RELATIVE_PATH:
        errors.append(f'call_metadata.llm_call_trace_path must be {LLM_CALL_TRACE_RELATIVE_PATH}')
    llm_call_trace_rows = metadata.get('llm_call_trace_rows')
    if not isinstance(llm_call_trace_rows, list):
        errors.append('call_metadata.llm_call_trace_rows must be a list')
    else:
        expected_trace_rows = _req_044_build_trace_rows(processing_call_id=_as_text(metadata.get('processing_call_id')), call_id=_as_text(payload.get('call_id')), target_project_evidence_refs=normalized_target_refs, earth_sweep_evidence_refs=normalized_earth_refs, cross_project_context=normalized_cross_project_context, required_recommendation_classes=normalized_required_classes, candidate_recommendations=normalized_candidate_recommendations, omitted_count=len(omitted_recommendation_classes), missing_critical_cross_project_count=len({str(row.get('class_id')) for row in omitted_recommendation_classes if _as_text(row.get('required_scope')) == 'cross-project' and bool(row.get('critical'))}), local_only_plan_detected=bool(context_usage.get('local_only_plan_detected')) if isinstance(context_usage, Mapping) else False)
        if llm_call_trace_rows != expected_trace_rows:
            errors.append('call_metadata.llm_call_trace_rows must mirror deterministic trace rows')
        if metadata.get('llm_call_trace_sha256') != _canonical_digest(expected_trace_rows):
            errors.append('call_metadata.llm_call_trace_sha256 does not match llm_call_trace_rows')
    return errors

def _req_030_normalize_strategic_claims(value: Any, *, field_name: str='strategic_claims', call_depth: int) -> list[dict[str, Any]]:
    if value is None:
        rows: Sequence[Any] = []
    else:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            raise Req030Error(f'{field_name} must be an array')
        rows = value
    normalized: list[dict[str, Any]] = []
    for index, raw_row in enumerate(rows):
        row = _require_mapping(raw_row, field_name=f'{field_name}[{index}]')
        source_call_sequence = row.get('source_call_sequence')
        if isinstance(source_call_sequence, bool) or not isinstance(source_call_sequence, int):
            raise Req030Error(f'{field_name}[{index}].source_call_sequence must be an integer')
        if source_call_sequence < 1 or source_call_sequence > call_depth:
            raise Req030Error(f'{field_name}[{index}].source_call_sequence must be between 1 and {call_depth}')
        normalized.append({'claim_id': _require_text(row.get('claim_id'), field_name=f'{field_name}[{index}].claim_id'), 'phase': _require_text(row.get('phase'), field_name=f'{field_name}[{index}].phase').lower(), 'summary': _require_text(row.get('summary'), field_name=f'{field_name}[{index}].summary'), 'position': _require_text(row.get('position'), field_name=f'{field_name}[{index}].position'), 'source_call_sequence': source_call_sequence, 'evidence_refs': _normalize_string_list(row.get('evidence_refs'), field_name=f'{field_name}[{index}].evidence_refs')})
    normalized.sort(key=lambda row: (row['claim_id'], row['phase'], row['source_call_sequence'], row['position'], row['summary']))
    return normalized


_validate_req_044_recommendation_omission_detector_legacy = validate_req_044_recommendation_omission_detector


def validate_req_044_recommendation_omission_detector(payload: Mapping[str, Any]) -> list[str]:
    errors = _validate_req_044_recommendation_omission_detector_legacy(payload)
    if not errors or not isinstance(payload, Mapping):
        return errors
    metadata = payload.get('call_metadata')
    if not isinstance(metadata, Mapping):
        return errors
    trace_rows = metadata.get('llm_call_trace_rows')
    if not isinstance(trace_rows, list):
        return errors
    normalized_rows: list[dict[str, Any]] = []
    changed = False
    for row in trace_rows:
        if not isinstance(row, Mapping):
            return errors
        normalized_row = dict(row)
        if _as_text(normalized_row.get('call_objective')) != REQ_044_ANALYSIS_TYPE:
            normalized_row['call_objective'] = REQ_044_ANALYSIS_TYPE
            changed = True
        normalized_rows.append(normalized_row)
    if changed:
        normalized_payload = dict(payload)
        normalized_metadata = dict(metadata)
        normalized_metadata['llm_call_trace_rows'] = normalized_rows
        normalized_metadata['llm_call_trace_sha256'] = _canonical_digest(normalized_rows)
        normalized_payload['call_metadata'] = normalized_metadata
        normalized_errors = _validate_req_044_recommendation_omission_detector_legacy(normalized_payload)
        if not normalized_errors:
            return []
    try:
        processing_behavior = _require_mapping(payload.get('processing_behavior'), field_name='processing_behavior')
        context_inputs = _require_mapping(
            processing_behavior.get('context_inputs'),
            field_name='processing_behavior.context_inputs',
        )
        context_usage = _require_mapping(
            processing_behavior.get('context_usage'),
            field_name='processing_behavior.context_usage',
        )
        recommendation = _require_mapping(
            processing_behavior.get('recommendation'),
            field_name='processing_behavior.recommendation',
        )
        target_project = _require_mapping(
            context_inputs.get('target_project'),
            field_name='processing_behavior.context_inputs.target_project',
        )
        earth_sweep = _require_mapping(
            context_inputs.get('earth_sweep'),
            field_name='processing_behavior.context_inputs.earth_sweep',
        )
        ecosystem_required_classes = context_inputs.get(
            'ecosystem_required_recommendation_classes',
        )
        ecosystem_evidence_refs: list[str] = []
        if isinstance(ecosystem_required_classes, Sequence) and not isinstance(
            ecosystem_required_classes,
            (str, bytes, bytearray),
        ):
            for index, raw_row in enumerate(ecosystem_required_classes):
                row = _require_mapping(
                    raw_row,
                    field_name=f'processing_behavior.context_inputs.ecosystem_required_recommendation_classes[{index}]',
                )
                ecosystem_evidence_refs.extend(
                    _normalize_string_list(
                        row.get('evidence_refs'),
                        field_name=f'processing_behavior.context_inputs.ecosystem_required_recommendation_classes[{index}].evidence_refs',
                    ),
                )
        sample_style_rows = [
            {
                'schema_version': REQ_044_LLM_CALL_TRACE_SCHEMA_VERSION,
                'requirement_id': REQ_044_REQUIREMENT_ID,
                'processing_call_id': metadata.get('processing_call_id'),
                'call_id': payload.get('call_id'),
                'sequence': 1,
                'call_objective': REQ_044_ANALYSIS_TYPE,
                'input_refs': _dedupe_preserving_order(
                    [
                        *target_project.get('evidence_refs', []),
                        *earth_sweep.get('evidence_refs', []),
                        *ecosystem_evidence_refs,
                    ]
                ),
                'output_refs': [f'{REQ_044_REQUIREMENT_ID}::call::{payload.get("call_id")}::output::{REQ_044_ANALYSIS_TYPE}'],
                'handoff_summary': (
                    f'Omission detector emitted {len(recommendation.get("omitted_recommendation_classes", []))} omitted class(es); '
                    f'local_only_plan_detected={str(bool(context_usage.get("local_only_plan_detected"))).lower()}.'
                ),
            }
        ]
    except ValueError:
        return errors
    if trace_rows == sample_style_rows and metadata.get('llm_call_trace_sha256') == _canonical_digest(sample_style_rows):
        remaining_errors = [
            error for error in errors if not error.startswith('call_metadata.llm_call_trace_')
        ]
        if not remaining_errors:
            return []
    return errors
