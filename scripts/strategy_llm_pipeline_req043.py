#!/usr/bin/env python3
'REQ-025, REQ-026, REQ-029, REQ-030, REQ-031, REQ-034, and REQ-043 contract/data-model surface for strategy LLM pipeline flows.'

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

REQ_043_REQUIREMENT_ID = 'REQ-043'

REQ_043_SCHEMA_VERSION = 'req-043.project-obligation-reasoning.v1'

REQ_043_LLM_CALL_TRACE_SCHEMA_VERSION = 'req-043.llm-call-trace-row.v1'

REQ_043_ANALYSIS_TYPE = 'project_obligation_reasoning'

REQ_043_PROCESSING_STRATEGY = 'project-obligation-reasoning'

REQ_043_REASONING_MODE = 'deterministic-contract-surface-mapping'

RUNTIME_MODE = 'llm-first'

EXECUTION_MODE = 'long-thinking'

LLM_CALL_TRACE_RELATIVE_PATH = 'strategy/current/llm_call_trace.jsonl'

REQ_043_OBLIGATION_ID_RE = re.compile('^obl\\.[a-z0-9]+(?:-[a-z0-9]+)*$')

REQ_043_ALLOWED_DIRECTIONS = {'consume', 'expose'}

REQ_043_ALLOWED_TRANSPORTS = {'event', 'file', 'http', 'json', 'queue'}

REQ_043_ALLOWED_PROJECT_ROLES = {'consumer', 'producer'}

REQ_043_ALLOWED_CLAIM_PHASES = {'analysis', 'synthesis'}

class Req043Error(ValueError):
    """Raised when REQ-043 input is malformed."""

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

def _req_043_contract_output_ref(*, call_id: str) -> str:
    return f'{REQ_043_REQUIREMENT_ID}::call::{call_id}::output::project_obligation_reasoning'

def _req_043_candidate_call_id(*, parent_call_id: str, obligation_id: str) -> str:
    return f'{parent_call_id}::candidate::{obligation_id}'

def _req_043_candidate_output_ref(*, call_id: str, obligation_id: str) -> str:
    return f'{REQ_043_REQUIREMENT_ID}::call::{call_id}::output::obligation_assessment::{obligation_id}'

def _req_043_normalize_target_project_profile(value: Any, *, field_name: str='target_project_profile') -> dict[str, str]:
    row = _require_mapping(value, field_name=field_name)
    return {'project_id': _require_text(row.get('project_id'), field_name=f'{field_name}.project_id'), 'owner_team': _require_text(row.get('owner_team'), field_name=f'{field_name}.owner_team')}

def _req_043_normalize_cross_project_context(value: Any, *, field_name: str='cross_project_context') -> list[dict[str, Any]]:
    if value is None:
        rows: Sequence[Any] = []
    else:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            raise Req043Error(f'{field_name} must be an array')
        rows = value
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_row in enumerate(rows):
        row = _require_mapping(raw_row, field_name=f'{field_name}[{index}]')
        project_id = _require_text(row.get('project_id'), field_name=f'{field_name}[{index}].project_id')
        if project_id in seen_ids:
            raise Req043Error(f'{field_name}[{index}].project_id must be unique')
        seen_ids.add(project_id)
        normalized.append({'project_id': project_id, 'project_root': _normalize_root(row.get('project_root'), field_name=f'{field_name}[{index}].project_root'), 'owner_team': _require_text(row.get('owner_team'), field_name=f'{field_name}[{index}].owner_team'), 'evidence_refs': _normalize_string_list(row.get('evidence_refs'), field_name=f'{field_name}[{index}].evidence_refs', min_items=1), 'context_note': _require_text(row.get('context_note'), field_name=f'{field_name}[{index}].context_note')})
    normalized.sort(key=lambda row: (row['project_id'], row['project_root'], row['owner_team']))
    return normalized

def _req_043_normalize_contract_expectations(value: Any, *, field_name: str) -> dict[str, Any]:
    row = _require_mapping(value, field_name=field_name)
    transport = _require_text(row.get('transport'), field_name=f'{field_name}.transport').lower()
    if transport not in REQ_043_ALLOWED_TRANSPORTS:
        raise Req043Error(f'{field_name}.transport must be one of {sorted(REQ_043_ALLOWED_TRANSPORTS)}')
    return {'summary': _require_text(row.get('summary'), field_name=f'{field_name}.summary'), 'version': _require_text(row.get('version'), field_name=f'{field_name}.version'), 'transport': transport, 'required_fields': _normalize_string_list(row.get('required_fields'), field_name=f'{field_name}.required_fields', min_items=1)}

def _req_043_normalize_ownership_boundary(value: Any, *, direction: str, field_name: str) -> dict[str, str]:
    row = _require_mapping(value, field_name=field_name)
    current_project_role = _require_text(row.get('current_project_role'), field_name=f'{field_name}.current_project_role').lower()
    counterparty_role = _require_text(row.get('counterparty_role'), field_name=f'{field_name}.counterparty_role').lower()
    if current_project_role not in REQ_043_ALLOWED_PROJECT_ROLES:
        raise Req043Error(f'{field_name}.current_project_role must be one of {sorted(REQ_043_ALLOWED_PROJECT_ROLES)}')
    if counterparty_role not in REQ_043_ALLOWED_PROJECT_ROLES:
        raise Req043Error(f'{field_name}.counterparty_role must be one of {sorted(REQ_043_ALLOWED_PROJECT_ROLES)}')
    expected_current_role = 'producer' if direction == 'expose' else 'consumer'
    expected_counterparty_role = 'consumer' if direction == 'expose' else 'producer'
    if current_project_role != expected_current_role:
        raise Req043Error(f'{field_name}.current_project_role must be {expected_current_role} when direction is {direction}')
    if counterparty_role != expected_counterparty_role:
        raise Req043Error(f'{field_name}.counterparty_role must be {expected_counterparty_role} when direction is {direction}')
    return {'current_project_role': current_project_role, 'counterparty_role': counterparty_role, 'boundary_rule': _require_text(row.get('boundary_rule'), field_name=f'{field_name}.boundary_rule')}

def _req_043_normalize_project_obligation_candidates(value: Any, *, target_project_id: str, field_name: str='project_obligation_candidates') -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise Req043Error(f'{field_name} must be an array')
    if not value:
        raise Req043Error(f'{field_name} must contain at least 1 item')
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_row in enumerate(value):
        row = _require_mapping(raw_row, field_name=f'{field_name}[{index}]')
        obligation_id = _require_text(row.get('obligation_id'), field_name=f'{field_name}[{index}].obligation_id')
        if not REQ_043_OBLIGATION_ID_RE.match(obligation_id):
            raise Req043Error(f'{field_name}[{index}].obligation_id must match {REQ_043_OBLIGATION_ID_RE.pattern}')
        if obligation_id in seen_ids:
            raise Req043Error(f'{field_name}[{index}].obligation_id must be unique')
        seen_ids.add(obligation_id)
        direction = _require_text(row.get('direction'), field_name=f'{field_name}[{index}].direction').lower()
        if direction not in REQ_043_ALLOWED_DIRECTIONS:
            raise Req043Error(f'{field_name}[{index}].direction must be one of {sorted(REQ_043_ALLOWED_DIRECTIONS)}')
        counterparty_project_id = _require_text(row.get('counterparty_project_id'), field_name=f'{field_name}[{index}].counterparty_project_id')
        if counterparty_project_id == target_project_id:
            raise Req043Error(f'{field_name}[{index}].counterparty_project_id must differ from target_project_profile.project_id')
        requires_earth_evidence = row.get('requires_earth_evidence', True)
        if not isinstance(requires_earth_evidence, bool):
            raise Req043Error(f'{field_name}[{index}].requires_earth_evidence must be a boolean')
        normalized.append({'obligation_id': obligation_id, 'direction': direction, 'summary': _require_text(row.get('summary'), field_name=f'{field_name}[{index}].summary'), 'counterparty_project_id': counterparty_project_id, 'interface_id': _require_text(row.get('interface_id'), field_name=f'{field_name}[{index}].interface_id'), 'contract_expectations': _req_043_normalize_contract_expectations(row.get('contract_expectations'), field_name=f'{field_name}[{index}].contract_expectations'), 'ownership_boundary': _req_043_normalize_ownership_boundary(row.get('ownership_boundary'), direction=direction, field_name=f'{field_name}[{index}].ownership_boundary'), 'rationale': _require_text(row.get('rationale'), field_name=f'{field_name}[{index}].rationale'), 'requires_earth_evidence': requires_earth_evidence, 'evidence_refs': _normalize_string_list(row.get('evidence_refs'), field_name=f'{field_name}[{index}].evidence_refs', min_items=1), 'next_step': _require_text(row.get('next_step'), field_name=f'{field_name}[{index}].next_step')})
    normalized.sort(key=lambda row: (row['obligation_id'], row['interface_id'], row['counterparty_project_id']))
    return normalized

def _req_043_normalize_call_chain(value: Any, *, field_name: str='call_chain') -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise Req043Error(f'{field_name} must be an array')
    normalized: list[dict[str, Any]] = []
    seen_sequences: set[int] = set()
    seen_call_ids: set[str] = set()
    for index, raw_row in enumerate(value):
        row = _require_mapping(raw_row, field_name=f'{field_name}[{index}]')
        sequence = row.get('sequence')
        if isinstance(sequence, bool) or not isinstance(sequence, int):
            raise Req043Error(f'{field_name}[{index}].sequence must be an integer')
        if sequence < 1:
            raise Req043Error(f'{field_name}[{index}].sequence must be >= 1')
        if sequence in seen_sequences:
            raise Req043Error(f'{field_name}[{index}].sequence must be unique')
        seen_sequences.add(sequence)
        call_id = _require_text(row.get('call_id'), field_name=f'{field_name}[{index}].call_id')
        if call_id in seen_call_ids:
            raise Req043Error(f'{field_name}[{index}].call_id must be unique')
        seen_call_ids.add(call_id)
        normalized.append({'sequence': sequence, 'call_id': call_id, 'phase': _require_text(row.get('phase'), field_name=f'{field_name}[{index}].phase').lower(), 'output_ref': _require_text(row.get('output_ref'), field_name=f'{field_name}[{index}].output_ref')})
    normalized.sort(key=lambda row: row['sequence'])
    expected_sequences = list(range(1, len(normalized) + 1))
    actual_sequences = [row['sequence'] for row in normalized]
    if actual_sequences != expected_sequences:
        raise Req043Error(f'{field_name}.sequence must be contiguous starting at 1')
    if len(normalized) < 2:
        raise Req043Error(f'{field_name} must include at least 2 calls for contradiction checks')
    return normalized

def _req_043_normalize_strategic_claims(value: Any, *, call_depth: int, call_chain_supplied: bool, field_name: str='strategic_claims') -> list[dict[str, Any]]:
    if value is None:
        rows: Sequence[Any] = []
    else:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            raise Req043Error(f'{field_name} must be an array')
        rows = value
    if rows and (not call_chain_supplied):
        raise Req043Error('call_chain must be provided when strategic_claims are supplied')
    normalized: list[dict[str, Any]] = []
    for index, raw_row in enumerate(rows):
        row = _require_mapping(raw_row, field_name=f'{field_name}[{index}]')
        source_call_sequence = row.get('source_call_sequence')
        if isinstance(source_call_sequence, bool) or not isinstance(source_call_sequence, int):
            raise Req043Error(f'{field_name}[{index}].source_call_sequence must be an integer')
        if source_call_sequence < 1 or source_call_sequence > call_depth:
            raise Req043Error(f'{field_name}[{index}].source_call_sequence must be between 1 and {call_depth}')
        phase = _require_text(row.get('phase'), field_name=f'{field_name}[{index}].phase').lower()
        if phase not in REQ_043_ALLOWED_CLAIM_PHASES:
            raise Req043Error(f'{field_name}[{index}].phase must be one of {sorted(REQ_043_ALLOWED_CLAIM_PHASES)}')
        normalized.append({'claim_id': _require_text(row.get('claim_id'), field_name=f'{field_name}[{index}].claim_id'), 'obligation_id': _as_text(row.get('obligation_id')), 'phase': phase, 'summary': _require_text(row.get('summary'), field_name=f'{field_name}[{index}].summary'), 'position': _require_text(row.get('position'), field_name=f'{field_name}[{index}].position'), 'source_call_sequence': source_call_sequence, 'evidence_refs': _normalize_string_list(row.get('evidence_refs'), field_name=f'{field_name}[{index}].evidence_refs')})
    normalized.sort(key=lambda row: (row['claim_id'], row['obligation_id'], row['phase'], row['source_call_sequence'], row['position'], row['summary']))
    return normalized

def _req_043_canonical_input(*, target_project_root: str, earth_root: str, output_root: str, revision_identity: str, strategy_goal: str, target_project_profile: Mapping[str, Any], call_id: str, checked_at_utc: str) -> dict[str, Any]:
    return {'runtime_mode': RUNTIME_MODE, 'execution_mode': EXECUTION_MODE, 'target_project_root': target_project_root, 'earth_root': earth_root, 'output_root': output_root, 'revision_identity': revision_identity, 'strategy_goal': strategy_goal, 'analysis_type': REQ_043_ANALYSIS_TYPE, 'target_project_profile': dict(target_project_profile), 'call_id': call_id, 'checked_at_utc': checked_at_utc}

def _req_043_canonical_processing_input(*, target_project_evidence_refs: Sequence[str], earth_sweep_evidence_refs: Sequence[str], cross_project_context: Sequence[Mapping[str, Any]], project_obligation_candidates: Sequence[Mapping[str, Any]], call_chain: Sequence[Mapping[str, Any]] | None=None, strategic_claims: Sequence[Mapping[str, Any]] | None=None) -> dict[str, Any]:
    canonical: dict[str, Any] = {'target_project_evidence_refs': list(target_project_evidence_refs), 'earth_sweep_evidence_refs': list(earth_sweep_evidence_refs), 'cross_project_context': [dict(row) for row in cross_project_context], 'project_obligation_candidates': [dict(row) for row in project_obligation_candidates]}
    if call_chain is not None:
        canonical['call_chain'] = [dict(row) for row in call_chain]
    if strategic_claims is not None:
        canonical['strategic_claims'] = [dict(row) for row in strategic_claims]
    return canonical

def _req_043_build_trace_rows(*, processing_call_id: str, call_id: str, target_project_evidence_refs: Sequence[str], earth_sweep_evidence_refs: Sequence[str], cross_project_context: Sequence[Mapping[str, Any]], project_obligation_candidates: Sequence[Mapping[str, Any]], obligation_count: int, open_risk_count: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    base_input_refs = _dedupe_preserving_order(list(target_project_evidence_refs) + list(earth_sweep_evidence_refs))
    context_refs_by_project = {_as_text(row.get('project_id')): list(row.get('evidence_refs', [])) for row in cross_project_context}
    prior_output_refs: list[str] = []
    candidate_ids = [_as_text(row.get('obligation_id')) for row in project_obligation_candidates]
    for sequence, row in enumerate(project_obligation_candidates, start=1):
        obligation_id = _as_text(row.get('obligation_id'))
        direction = _as_text(row.get('direction'))
        interface_id = _as_text(row.get('interface_id'))
        candidate_call_id = _req_043_candidate_call_id(parent_call_id=call_id, obligation_id=obligation_id)
        output_ref = _req_043_candidate_output_ref(call_id=candidate_call_id, obligation_id=obligation_id)
        counterparty_project_id = _as_text(row.get('counterparty_project_id'))
        input_refs = _dedupe_preserving_order(base_input_refs + list(row.get('evidence_refs', [])) + context_refs_by_project.get(counterparty_project_id, []) + prior_output_refs)
        next_call_id = _req_043_candidate_call_id(parent_call_id=call_id, obligation_id=candidate_ids[sequence]) if sequence < len(candidate_ids) else call_id
        rows.append({'schema_version': REQ_043_LLM_CALL_TRACE_SCHEMA_VERSION, 'requirement_id': REQ_043_REQUIREMENT_ID, 'processing_call_id': processing_call_id, 'call_id': candidate_call_id, 'sequence': sequence, 'call_objective': f'Assess obligation {obligation_id} ({direction}) for interface {interface_id} with contract expectations and ownership boundaries.', 'input_refs': input_refs, 'output_refs': [output_ref], 'handoff_summary': f'Call {sequence} evaluates {obligation_id} and hands off obligation assessment via {output_ref} to {next_call_id}.'})
        prior_output_refs.append(output_ref)
    final_sequence = len(project_obligation_candidates) + 1
    final_output_ref = _req_043_contract_output_ref(call_id=call_id)
    final_input_refs = _dedupe_preserving_order(base_input_refs + [ref for row in cross_project_context for ref in row['evidence_refs']] + [ref for row in project_obligation_candidates for ref in row['evidence_refs']] + prior_output_refs)
    rows.append({'schema_version': REQ_043_LLM_CALL_TRACE_SCHEMA_VERSION, 'requirement_id': REQ_043_REQUIREMENT_ID, 'processing_call_id': processing_call_id, 'call_id': call_id, 'sequence': final_sequence, 'call_objective': REQ_043_ANALYSIS_TYPE, 'input_refs': final_input_refs, 'output_refs': [final_output_ref], 'handoff_summary': f'Call {final_sequence} emits project obligation reasoning with {obligation_count} obligation(s) and {open_risk_count} open risk(s).'})
    return rows

def build_req_043_project_obligation_reasoning(*, target_project_root: str, earth_root: str, output_root: str, revision_identity: str, strategy_goal: str, target_project_profile: Mapping[str, Any], project_obligation_candidates: Sequence[Mapping[str, Any]], call_chain: Sequence[Mapping[str, Any]] | None=None, strategic_claims: Sequence[Mapping[str, Any]] | None=None, cross_project_context: Sequence[Mapping[str, Any]] | None=None, target_project_evidence_refs: Sequence[Any] | None=None, earth_sweep_evidence_refs: Sequence[Any] | None=None, call_id: str='call-project-obligations', checked_at_utc: str | None=None) -> dict[str, Any]:
    normalized_target_root = _normalize_root(target_project_root, field_name='target_project_root')
    normalized_earth_root = _normalize_root(earth_root, field_name='earth_root')
    normalized_output_root = _normalize_root(output_root, field_name='output_root')
    normalized_revision_identity = _require_text(revision_identity, field_name='revision_identity')
    normalized_strategy_goal = _require_text(strategy_goal, field_name='strategy_goal')
    normalized_target_project_profile = _req_043_normalize_target_project_profile(target_project_profile)
    normalized_call_id = _require_text(call_id, field_name='call_id')
    normalized_checked_at_utc = _require_text(checked_at_utc or utc_now_iso(), field_name='checked_at_utc')
    normalized_target_refs = _normalize_string_list(target_project_evidence_refs, field_name='target_project_evidence_refs')
    normalized_earth_refs = _normalize_string_list(earth_sweep_evidence_refs, field_name='earth_sweep_evidence_refs')
    normalized_cross_project_context = _req_043_normalize_cross_project_context(cross_project_context)
    normalized_candidates = _req_043_normalize_project_obligation_candidates(project_obligation_candidates, target_project_id=normalized_target_project_profile['project_id'])
    normalized_call_chain: list[dict[str, Any]] = []
    call_chain_supplied = call_chain is not None
    if call_chain_supplied:
        normalized_call_chain = _req_043_normalize_call_chain(call_chain)
    normalized_strategic_claims = _req_043_normalize_strategic_claims(strategic_claims, call_depth=len(normalized_call_chain), call_chain_supplied=call_chain_supplied)
    context_by_project = {row['project_id']: row for row in normalized_cross_project_context}
    cross_project_refs = _collect_unique_refs(*[row['evidence_refs'] for row in normalized_cross_project_context])
    call_output_refs = [row['output_ref'] for row in normalized_call_chain]
    output_ref_by_sequence = {int(row['sequence']): str(row['output_ref']) for row in normalized_call_chain}
    base_available_refs = set(_collect_unique_refs(normalized_target_refs, normalized_earth_refs, cross_project_refs, call_output_refs))
    project_obligations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    blocked_by_contradiction: set[str] = set()
    blocked_by_uncited_claim: set[str] = set()
    blocked_claim_refs_by_obligation: dict[str, list[str]] = {}
    claim_rows_by_id: dict[str, list[dict[str, Any]]] = {}
    for claim in normalized_strategic_claims:
        claim_id = str(claim['claim_id'])
        claim_rows_by_id.setdefault(claim_id, []).append(claim)
        source_output_ref = output_ref_by_sequence.get(int(claim['source_call_sequence']), '')
        citation_refs = list(claim['evidence_refs'])
        uncited_claim_refs = sorted(set(citation_refs) - base_available_refs)
        if not citation_refs or uncited_claim_refs:
            obligation_id = str(claim['obligation_id'])
            required_refs = _collect_unique_refs([source_output_ref], uncited_claim_refs if uncited_claim_refs else citation_refs)
            open_risks.append({'risk_id': f'risk-claim-{claim_id}-citation', 'reason_code': 'uncited_strategic_claim', 'summary': str(claim['summary']), 'required_evidence_refs': required_refs})
            if obligation_id:
                blocked_by_uncited_claim.add(obligation_id)
                blocked_claim_refs_by_obligation[obligation_id] = _collect_unique_refs(blocked_claim_refs_by_obligation.get(obligation_id, []), required_refs)
    for claim_id, claim_rows in claim_rows_by_id.items():
        analysis_rows = [row for row in claim_rows if row['phase'] == 'analysis']
        synthesis_rows = [row for row in claim_rows if row['phase'] == 'synthesis']
        contradiction_found = False
        for analysis_row in analysis_rows:
            for synthesis_row in synthesis_rows:
                if analysis_row['position'] == synthesis_row['position']:
                    continue
                required_refs = _collect_unique_refs([output_ref_by_sequence.get(int(analysis_row['source_call_sequence']), '')], [output_ref_by_sequence.get(int(synthesis_row['source_call_sequence']), '')], analysis_row['evidence_refs'], synthesis_row['evidence_refs'])
                open_risks.append({'risk_id': f'risk-claim-{claim_id}-contradiction', 'reason_code': 'cross_call_contradiction', 'summary': str(synthesis_row['summary']), 'required_evidence_refs': required_refs})
                for claim_row in (analysis_row, synthesis_row):
                    obligation_id = str(claim_row['obligation_id'])
                    if not obligation_id:
                        continue
                    blocked_by_contradiction.add(obligation_id)
                    blocked_claim_refs_by_obligation[obligation_id] = _collect_unique_refs(blocked_claim_refs_by_obligation.get(obligation_id, []), required_refs)
                contradiction_found = True
                break
            if contradiction_found:
                break
    for row in normalized_candidates:
        counterparty_context = context_by_project.get(row['counterparty_project_id'])
        counterparty_refs = counterparty_context['evidence_refs'] if counterparty_context else []
        candidate_earth_refs = _collect_unique_refs([ref for ref in row['evidence_refs'] if _is_earth_evidence_ref(ref)], [ref for ref in counterparty_refs if _is_earth_evidence_ref(ref)])
        uncited_refs = sorted(set(row['evidence_refs']) - base_available_refs)
        blocked_claim_refs = blocked_claim_refs_by_obligation.get(row['obligation_id'], [])
        blocked_reason_code = ''
        if row['obligation_id'] in blocked_by_contradiction:
            blocked_reason_code = 'cross_call_contradiction'
        elif row['obligation_id'] in blocked_by_uncited_claim:
            blocked_reason_code = 'uncited_strategic_claim'
        elif uncited_refs:
            blocked_reason_code = 'uncited_strategic_claim'
        elif counterparty_context is None:
            blocked_reason_code = 'missing_cross_project_context'
        elif row['requires_earth_evidence'] and (not candidate_earth_refs):
            blocked_reason_code = 'missing_earth_sweep_evidence_refs'
        if blocked_reason_code:
            required_refs = _collect_unique_refs(row['evidence_refs'], counterparty_refs, normalized_earth_refs, blocked_claim_refs)
            if uncited_refs:
                required_refs = _collect_unique_refs(blocked_claim_refs, uncited_refs)
            open_risks.append({'risk_id': f"risk-{row['obligation_id']}", 'reason_code': blocked_reason_code, 'summary': row['summary'], 'required_evidence_refs': required_refs})
            continue
        project_obligations.append({'obligation_id': row['obligation_id'], 'direction': row['direction'], 'summary': row['summary'], 'counterparty_project_id': row['counterparty_project_id'], 'interface_id': row['interface_id'], 'contract_expectations': dict(row['contract_expectations']), 'ownership_boundary': {'current_project_role': row['ownership_boundary']['current_project_role'], 'current_project_owner': normalized_target_project_profile['owner_team'], 'counterparty_role': row['ownership_boundary']['counterparty_role'], 'counterparty_owner': counterparty_context['owner_team'], 'boundary_rule': row['ownership_boundary']['boundary_rule']}, 'rationale': row['rationale'], 'next_step': row['next_step'], 'evidence_refs': _collect_unique_refs(row['evidence_refs'], counterparty_refs, candidate_earth_refs)})
    project_obligations.sort(key=lambda row: row['obligation_id'])
    open_risks.sort(key=lambda row: row['risk_id'])
    expose_obligation_ids = [row['obligation_id'] for row in project_obligations if row['direction'] == 'expose']
    consume_obligation_ids = [row['obligation_id'] for row in project_obligations if row['direction'] == 'consume']
    recommendation_refs = _collect_unique_refs(normalized_target_refs, normalized_earth_refs, cross_project_refs, *[row['evidence_refs'] for row in project_obligations], *[row['required_evidence_refs'] for row in open_risks])
    decision = _recommendation_decision(recommended_actions=project_obligations, open_risks=open_risks)
    rationale = f'obligations={len(project_obligations)} expose={len(expose_obligation_ids)} consume={len(consume_obligation_ids)} open_risks={len(open_risks)}'
    confidence = _recommendation_confidence(evidence_refs=recommendation_refs, open_risks=open_risks)
    canonical_input = _req_043_canonical_input(target_project_root=normalized_target_root, earth_root=normalized_earth_root, output_root=normalized_output_root, revision_identity=normalized_revision_identity, strategy_goal=normalized_strategy_goal, target_project_profile=normalized_target_project_profile, call_id=normalized_call_id, checked_at_utc=normalized_checked_at_utc)
    canonical_processing_input = _req_043_canonical_processing_input(target_project_evidence_refs=normalized_target_refs, earth_sweep_evidence_refs=normalized_earth_refs, cross_project_context=normalized_cross_project_context, project_obligation_candidates=normalized_candidates, call_chain=normalized_call_chain if call_chain_supplied else None, strategic_claims=normalized_strategic_claims if strategic_claims is not None else None)
    processing_sha = _canonical_digest(canonical_processing_input)
    processing_call_id = f'req043-processing-{processing_sha[:16]}'
    llm_call_trace_rows = _req_043_build_trace_rows(processing_call_id=processing_call_id, call_id=normalized_call_id, target_project_evidence_refs=normalized_target_refs, earth_sweep_evidence_refs=normalized_earth_refs, cross_project_context=normalized_cross_project_context, project_obligation_candidates=normalized_candidates, obligation_count=len(project_obligations), open_risk_count=len(open_risks))
    context_inputs: dict[str, Any] = {'target_project': {'project_root': normalized_target_root, 'project_id': normalized_target_project_profile['project_id'], 'owner_team': normalized_target_project_profile['owner_team'], 'evidence_refs': list(normalized_target_refs)}, 'earth_sweep': {'earth_root': normalized_earth_root, 'evidence_refs': list(normalized_earth_refs)}, 'cross_project_context': [dict(row) for row in normalized_cross_project_context], 'project_obligation_candidates': [dict(row) for row in normalized_candidates]}
    if call_chain_supplied:
        context_inputs['call_chain'] = [dict(row) for row in normalized_call_chain]
    if strategic_claims is not None:
        context_inputs['strategic_claims'] = [dict(row) for row in normalized_strategic_claims]
    context_usage: dict[str, Any] = {'bounded_context_used': True, 'earth_sweep_context_used': bool(normalized_earth_refs), 'cross_project_context_used': bool(normalized_cross_project_context), 'counterparty_projects_considered': sorted(context_by_project), 'obligation_ids_considered': [row['obligation_id'] for row in normalized_candidates], 'interface_ids_emitted': sorted({row['interface_id'] for row in project_obligations}), 'expose_obligation_ids_emitted': expose_obligation_ids, 'consume_obligation_ids_emitted': consume_obligation_ids, 'open_risk_ids_emitted': [row['risk_id'] for row in open_risks], 'evidence_refs_used': list(recommendation_refs)}
    if call_chain_supplied:
        context_usage['call_chain_depth'] = len(normalized_call_chain)
    if strategic_claims is not None:
        context_usage['strategic_claim_ids_considered'] = [row['claim_id'] for row in normalized_strategic_claims]
    if blocked_by_contradiction or blocked_by_uncited_claim:
        context_usage['blocked_obligation_ids'] = sorted(blocked_by_contradiction | blocked_by_uncited_claim)
    return {'schema_version': REQ_043_SCHEMA_VERSION, 'requirement_id': REQ_043_REQUIREMENT_ID, 'analysis_type': REQ_043_ANALYSIS_TYPE, 'call_id': normalized_call_id, 'checked_at_utc': normalized_checked_at_utc, 'processing_behavior': {'strategy': REQ_043_PROCESSING_STRATEGY, 'reasoning_mode': REQ_043_REASONING_MODE, 'bounded_context': True, 'context_inputs': context_inputs, 'context_usage': context_usage, 'recommendation': {'decision': decision, 'rationale': rationale, 'confidence': confidence, 'evidence_refs': list(recommendation_refs), 'project_obligations': project_obligations, 'open_risks': open_risks}}, 'call_metadata': {'reproducibility': 'deterministic-input-fingerprint', 'canonical_input': canonical_input, 'canonical_input_sha256': _canonical_digest(canonical_input), 'reproducible_call_id': f'req043-{_canonical_digest(canonical_input)[:16]}', 'canonical_processing_input': canonical_processing_input, 'processing_input_sha256': processing_sha, 'processing_call_id': processing_call_id, 'llm_call_trace_schema_version': REQ_043_LLM_CALL_TRACE_SCHEMA_VERSION, 'llm_call_trace_path': LLM_CALL_TRACE_RELATIVE_PATH, 'llm_call_trace_sha256': _canonical_digest(llm_call_trace_rows), 'llm_call_trace_rows': llm_call_trace_rows}}

def validate_req_043_project_obligation_reasoning(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ['payload must be a JSON object']
    if payload.get('schema_version') != REQ_043_SCHEMA_VERSION:
        errors.append(f'schema_version must be {REQ_043_SCHEMA_VERSION}')
    if payload.get('requirement_id') != REQ_043_REQUIREMENT_ID:
        errors.append(f'requirement_id must be {REQ_043_REQUIREMENT_ID}')
    if payload.get('analysis_type') != REQ_043_ANALYSIS_TYPE:
        errors.append(f'analysis_type must be {REQ_043_ANALYSIS_TYPE}')
    if not _as_text(payload.get('call_id')):
        errors.append('call_id is required')
    if not _as_text(payload.get('checked_at_utc')):
        errors.append('checked_at_utc is required')
    processing_behavior = payload.get('processing_behavior')
    if not isinstance(processing_behavior, Mapping):
        return errors + ['processing_behavior must be an object']
    if processing_behavior.get('strategy') != REQ_043_PROCESSING_STRATEGY:
        errors.append(f'processing_behavior.strategy must be {REQ_043_PROCESSING_STRATEGY}')
    if processing_behavior.get('reasoning_mode') != REQ_043_REASONING_MODE:
        errors.append(f'processing_behavior.reasoning_mode must be {REQ_043_REASONING_MODE}')
    if processing_behavior.get('bounded_context') is not True:
        errors.append('processing_behavior.bounded_context must be true')
    context_inputs = processing_behavior.get('context_inputs')
    normalized_target_profile: dict[str, str] = {}
    normalized_target_refs: list[str] = []
    normalized_earth_refs: list[str] = []
    normalized_cross_project_context: list[dict[str, Any]] = []
    normalized_candidates: list[dict[str, Any]] = []
    normalized_call_chain: list[dict[str, Any]] = []
    normalized_strategic_claims: list[dict[str, Any]] = []
    call_chain_supplied = False
    strategic_claims_supplied = False
    if not isinstance(context_inputs, Mapping):
        return errors + ['processing_behavior.context_inputs must be an object']
    target_project = context_inputs.get('target_project')
    if not isinstance(target_project, Mapping):
        errors.append('processing_behavior.context_inputs.target_project must be an object')
    else:
        try:
            normalized_target_profile = _req_043_normalize_target_project_profile({'project_id': target_project.get('project_id'), 'owner_team': target_project.get('owner_team')})
        except Req043Error as exc:
            errors.append(str(exc))
        normalized_target_refs = _normalize_string_list(target_project.get('evidence_refs'), field_name='processing_behavior.context_inputs.target_project.evidence_refs')
    earth_sweep = context_inputs.get('earth_sweep')
    if not isinstance(earth_sweep, Mapping):
        errors.append('processing_behavior.context_inputs.earth_sweep must be an object')
    else:
        normalized_earth_refs = _normalize_string_list(earth_sweep.get('evidence_refs'), field_name='processing_behavior.context_inputs.earth_sweep.evidence_refs')
    try:
        normalized_cross_project_context = _req_043_normalize_cross_project_context(context_inputs.get('cross_project_context'))
    except Req043Error as exc:
        errors.append(str(exc))
    try:
        normalized_candidates = _req_043_normalize_project_obligation_candidates(context_inputs.get('project_obligation_candidates'), target_project_id=normalized_target_profile.get('project_id', ''))
    except Req043Error as exc:
        errors.append(str(exc))
    call_chain_supplied = 'call_chain' in context_inputs
    if call_chain_supplied:
        try:
            normalized_call_chain = _req_043_normalize_call_chain(context_inputs.get('call_chain'))
        except Req043Error as exc:
            errors.append(str(exc))
    strategic_claims_supplied = 'strategic_claims' in context_inputs
    if strategic_claims_supplied:
        try:
            normalized_strategic_claims = _req_043_normalize_strategic_claims(context_inputs.get('strategic_claims'), call_depth=len(normalized_call_chain), call_chain_supplied=call_chain_supplied)
        except Req043Error as exc:
            errors.append(str(exc))
    context_usage = processing_behavior.get('context_usage')
    if not isinstance(context_usage, Mapping):
        errors.append('processing_behavior.context_usage must be an object')
    else:
        if not isinstance(context_usage.get('bounded_context_used'), bool):
            errors.append('processing_behavior.context_usage.bounded_context_used must be a boolean')
        if not isinstance(context_usage.get('earth_sweep_context_used'), bool):
            errors.append('processing_behavior.context_usage.earth_sweep_context_used must be a boolean')
        if not isinstance(context_usage.get('cross_project_context_used'), bool):
            errors.append('processing_behavior.context_usage.cross_project_context_used must be a boolean')
        for key in ('counterparty_projects_considered', 'obligation_ids_considered', 'interface_ids_emitted', 'expose_obligation_ids_emitted', 'consume_obligation_ids_emitted', 'open_risk_ids_emitted', 'evidence_refs_used'):
            value = context_usage.get(key)
            if not isinstance(value, list) or any((not _as_text(item) for item in value)):
                errors.append(f'processing_behavior.context_usage.{key} must be a string array')
    recommendation = processing_behavior.get('recommendation')
    if not isinstance(recommendation, Mapping):
        return errors + ['processing_behavior.recommendation must be an object']
    for key in ('decision', 'rationale', 'confidence'):
        if not _as_text(recommendation.get(key)):
            errors.append(f'processing_behavior.recommendation.{key} is required')
    if not isinstance(recommendation.get('evidence_refs'), list) or not recommendation.get('evidence_refs'):
        errors.append('processing_behavior.recommendation.evidence_refs must be a non-empty list')
    if not isinstance(recommendation.get('project_obligations'), list):
        errors.append('processing_behavior.recommendation.project_obligations must be a list')
    if not isinstance(recommendation.get('open_risks'), list):
        errors.append('processing_behavior.recommendation.open_risks must be a list')
    else:
        for index, risk in enumerate(recommendation.get('open_risks', [])):
            if not isinstance(risk, Mapping):
                errors.append(f'processing_behavior.recommendation.open_risks[{index}] must be an object')
                continue
            if not _as_text(risk.get('risk_id')):
                errors.append(f'processing_behavior.recommendation.open_risks[{index}].risk_id is required')
            if not _as_text(risk.get('reason_code')):
                errors.append(f'processing_behavior.recommendation.open_risks[{index}].reason_code is required')
            refs = risk.get('required_evidence_refs')
            if not isinstance(refs, list) or any((not _as_text(item) for item in refs)):
                errors.append(f'processing_behavior.recommendation.open_risks[{index}].required_evidence_refs must be a string array')
    for index, obligation in enumerate(recommendation.get('project_obligations', [])):
        if not isinstance(obligation, Mapping):
            errors.append(f'processing_behavior.recommendation.project_obligations[{index}] must be an object')
            continue
        obligation_id = _as_text(obligation.get('obligation_id'))
        if not REQ_043_OBLIGATION_ID_RE.match(obligation_id):
            errors.append(f'processing_behavior.recommendation.project_obligations[{index}].obligation_id must match {REQ_043_OBLIGATION_ID_RE.pattern}')
        direction = _as_text(obligation.get('direction')).lower()
        if direction not in REQ_043_ALLOWED_DIRECTIONS:
            errors.append(f'processing_behavior.recommendation.project_obligations[{index}].direction must be one of {sorted(REQ_043_ALLOWED_DIRECTIONS)}')
        if not _as_text(obligation.get('counterparty_project_id')):
            errors.append(f'processing_behavior.recommendation.project_obligations[{index}].counterparty_project_id is required')
        if not _as_text(obligation.get('interface_id')):
            errors.append(f'processing_behavior.recommendation.project_obligations[{index}].interface_id is required')
        contract_expectations = obligation.get('contract_expectations')
        if not isinstance(contract_expectations, Mapping):
            errors.append(f'processing_behavior.recommendation.project_obligations[{index}].contract_expectations must be an object')
        else:
            required_fields = contract_expectations.get('required_fields')
            if not isinstance(required_fields, list) or any((not _as_text(item) for item in required_fields)):
                errors.append(f'processing_behavior.recommendation.project_obligations[{index}].contract_expectations.required_fields must be a string array')
        ownership_boundary = obligation.get('ownership_boundary')
        if not isinstance(ownership_boundary, Mapping):
            errors.append(f'processing_behavior.recommendation.project_obligations[{index}].ownership_boundary must be an object')
        else:
            for key in ('current_project_role', 'current_project_owner', 'counterparty_role', 'counterparty_owner', 'boundary_rule'):
                if not _as_text(ownership_boundary.get(key)):
                    errors.append(f'processing_behavior.recommendation.project_obligations[{index}].ownership_boundary.{key} is required')
        evidence_refs = obligation.get('evidence_refs')
        if not isinstance(evidence_refs, list) or any((not _as_text(item) for item in evidence_refs)):
            errors.append(f'processing_behavior.recommendation.project_obligations[{index}].evidence_refs must be a string array')
    metadata = payload.get('call_metadata')
    if not isinstance(metadata, Mapping):
        return errors + ['call_metadata must be an object']
    if metadata.get('reproducibility') != 'deterministic-input-fingerprint':
        errors.append('call_metadata.reproducibility must be deterministic-input-fingerprint')
    canonical_input = metadata.get('canonical_input')
    if not isinstance(canonical_input, Mapping):
        errors.append('call_metadata.canonical_input must be an object')
    else:
        expected_canonical_input = _req_043_canonical_input(target_project_root=_as_text(target_project.get('project_root')) if isinstance(target_project, Mapping) else '', earth_root=_as_text(earth_sweep.get('earth_root')) if isinstance(earth_sweep, Mapping) else '', output_root=_as_text(canonical_input.get('output_root')), revision_identity=_as_text(canonical_input.get('revision_identity')), strategy_goal=_as_text(canonical_input.get('strategy_goal')), target_project_profile=normalized_target_profile, call_id=_as_text(payload.get('call_id')), checked_at_utc=_as_text(payload.get('checked_at_utc')))
        if dict(canonical_input) != expected_canonical_input:
            errors.append('call_metadata.canonical_input must mirror normalized invocation anchors')
        expected_input_sha = _canonical_digest(expected_canonical_input)
        if metadata.get('canonical_input_sha256') != expected_input_sha:
            errors.append('call_metadata.canonical_input_sha256 does not match canonical input')
        if metadata.get('reproducible_call_id') != f'req043-{expected_input_sha[:16]}':
            errors.append('call_metadata.reproducible_call_id does not match canonical digest')
    canonical_processing_input = metadata.get('canonical_processing_input')
    if not isinstance(canonical_processing_input, Mapping):
        errors.append('call_metadata.canonical_processing_input must be an object')
    else:
        expected_processing_input = _req_043_canonical_processing_input(target_project_evidence_refs=normalized_target_refs, earth_sweep_evidence_refs=normalized_earth_refs, cross_project_context=normalized_cross_project_context, project_obligation_candidates=normalized_candidates, call_chain=normalized_call_chain if call_chain_supplied else None, strategic_claims=normalized_strategic_claims if strategic_claims_supplied else None)
        if dict(canonical_processing_input) != expected_processing_input:
            errors.append('call_metadata.canonical_processing_input must mirror normalized obligation inputs')
        expected_processing_sha = _canonical_digest(expected_processing_input)
        if metadata.get('processing_input_sha256') != expected_processing_sha:
            errors.append('call_metadata.processing_input_sha256 does not match processing input')
        if metadata.get('processing_call_id') != f'req043-processing-{expected_processing_sha[:16]}':
            errors.append('call_metadata.processing_call_id does not match processing digest')
    if metadata.get('llm_call_trace_schema_version') != REQ_043_LLM_CALL_TRACE_SCHEMA_VERSION:
        errors.append(f'call_metadata.llm_call_trace_schema_version must be {REQ_043_LLM_CALL_TRACE_SCHEMA_VERSION}')
    if metadata.get('llm_call_trace_path') != LLM_CALL_TRACE_RELATIVE_PATH:
        errors.append(f'call_metadata.llm_call_trace_path must be {LLM_CALL_TRACE_RELATIVE_PATH}')
    llm_call_trace_rows = metadata.get('llm_call_trace_rows')
    if not isinstance(llm_call_trace_rows, list):
        errors.append('call_metadata.llm_call_trace_rows must be a list')
    else:
        expected_trace_rows = _req_043_build_trace_rows(processing_call_id=_as_text(metadata.get('processing_call_id')), call_id=_as_text(payload.get('call_id')), target_project_evidence_refs=normalized_target_refs, earth_sweep_evidence_refs=normalized_earth_refs, cross_project_context=normalized_cross_project_context, project_obligation_candidates=normalized_candidates, obligation_count=len(recommendation.get('project_obligations', [])) if isinstance(recommendation.get('project_obligations'), list) else 0, open_risk_count=len(recommendation.get('open_risks', [])) if isinstance(recommendation.get('open_risks'), list) else 0)
        if llm_call_trace_rows != expected_trace_rows:
            errors.append('call_metadata.llm_call_trace_rows must mirror deterministic trace rows')
        if metadata.get('llm_call_trace_sha256') != _canonical_digest(expected_trace_rows):
            errors.append('call_metadata.llm_call_trace_sha256 does not match llm_call_trace_rows')
    return errors


_build_req_043_project_obligation_reasoning_legacy = build_req_043_project_obligation_reasoning


def _req_043_contract_trace_rows(*, processing_call_id: str, call_id: str, target_project_evidence_refs: Sequence[str], earth_sweep_evidence_refs: Sequence[str], obligation_count: int, open_risk_count: int) -> list[dict[str, Any]]:
    input_refs = list(target_project_evidence_refs)
    for ref in earth_sweep_evidence_refs:
        if ref not in input_refs:
            input_refs.append(ref)
    return [
        {
            'schema_version': REQ_043_LLM_CALL_TRACE_SCHEMA_VERSION,
            'requirement_id': REQ_043_REQUIREMENT_ID,
            'processing_call_id': processing_call_id,
            'call_id': call_id,
            'sequence': 1,
            'call_objective': REQ_043_ANALYSIS_TYPE,
            'input_refs': input_refs,
            'output_refs': [f'{REQ_043_REQUIREMENT_ID}::call::{call_id}::output::{REQ_043_ANALYSIS_TYPE}'],
            'handoff_summary': (
                f'Call 1 emits project obligation reasoning with {obligation_count} obligation(s) '
                f'and {open_risk_count} open risk(s).'
            ),
        }
    ]


def build_req_043_project_obligation_reasoning(*, target_project_root: str, earth_root: str, output_root: str, revision_identity: str, strategy_goal: str, target_project_profile: Mapping[str, Any], project_obligation_candidates: Sequence[Mapping[str, Any]], call_chain: Sequence[Mapping[str, Any]] | None=None, strategic_claims: Sequence[Mapping[str, Any]] | None=None, cross_project_context: Sequence[Mapping[str, Any]] | None=None, target_project_evidence_refs: Sequence[Any] | None=None, earth_sweep_evidence_refs: Sequence[Any] | None=None, call_id: str | None=None, checked_at_utc: str | None=None) -> dict[str, Any]:
    payload = _build_req_043_project_obligation_reasoning_legacy(
        target_project_root=target_project_root,
        earth_root=earth_root,
        output_root=output_root,
        revision_identity=revision_identity,
        strategy_goal=strategy_goal,
        target_project_profile=target_project_profile,
        project_obligation_candidates=project_obligation_candidates,
        call_chain=call_chain,
        strategic_claims=strategic_claims,
        cross_project_context=cross_project_context,
        target_project_evidence_refs=target_project_evidence_refs,
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        call_id=call_id,
        checked_at_utc=checked_at_utc,
    )
    metadata = dict(payload['call_metadata'])
    recommendation = _require_mapping(payload['processing_behavior']['recommendation'], field_name='processing_behavior.recommendation')
    trace_rows = _req_043_contract_trace_rows(
        processing_call_id=_as_text(metadata.get('processing_call_id')),
        call_id=_as_text(payload.get('call_id')),
        target_project_evidence_refs=_normalize_string_list(target_project_evidence_refs, field_name='target_project_evidence_refs'),
        earth_sweep_evidence_refs=_normalize_string_list(earth_sweep_evidence_refs, field_name='earth_sweep_evidence_refs'),
        obligation_count=len(recommendation.get('project_obligations', [])),
        open_risk_count=len(recommendation.get('open_risks', [])),
    )
    metadata['llm_call_trace_rows'] = trace_rows
    metadata['llm_call_trace_sha256'] = _canonical_digest(trace_rows)
    payload['call_metadata'] = metadata
    return payload


def validate_req_043_project_obligation_reasoning(payload: Mapping[str, Any]) -> list[str]:
    if not isinstance(payload, Mapping):
        return ['payload must be a JSON object']
    try:
        processing_behavior = _require_mapping(payload.get('processing_behavior'), field_name='processing_behavior')
        context_inputs = _require_mapping(
            processing_behavior.get('context_inputs'),
            field_name='processing_behavior.context_inputs',
        )
        target_project = _require_mapping(
            context_inputs.get('target_project'),
            field_name='processing_behavior.context_inputs.target_project',
        )
        earth_sweep = _require_mapping(
            context_inputs.get('earth_sweep'),
            field_name='processing_behavior.context_inputs.earth_sweep',
        )
        metadata = _require_mapping(payload.get('call_metadata'), field_name='call_metadata')
        canonical_input = _require_mapping(metadata.get('canonical_input'), field_name='call_metadata.canonical_input')
        expected = build_req_043_project_obligation_reasoning(
            target_project_root=target_project.get('project_root'),
            earth_root=earth_sweep.get('earth_root'),
            output_root=canonical_input.get('output_root'),
            revision_identity=canonical_input.get('revision_identity'),
            strategy_goal=canonical_input.get('strategy_goal'),
            target_project_profile={
                'project_id': target_project.get('project_id'),
                'owner_team': target_project.get('owner_team'),
            },
            project_obligation_candidates=context_inputs.get('project_obligation_candidates'),
            call_chain=context_inputs.get('call_chain'),
            strategic_claims=context_inputs.get('strategic_claims'),
            cross_project_context=context_inputs.get('cross_project_context'),
            target_project_evidence_refs=target_project.get('evidence_refs'),
            earth_sweep_evidence_refs=earth_sweep.get('evidence_refs'),
            call_id=payload.get('call_id'),
            checked_at_utc=payload.get('checked_at_utc'),
        )
    except ValueError as exc:
        return [str(exc)]
    comparable_payload = dict(payload)
    payload_metadata = comparable_payload.get('call_metadata')
    if isinstance(payload_metadata, Mapping) and 'llm_call_trace_artifact' in payload_metadata:
        comparable_metadata = dict(payload_metadata)
        comparable_metadata.pop('llm_call_trace_artifact', None)
        comparable_payload['call_metadata'] = comparable_metadata
    if comparable_payload != expected:
        return ['payload must mirror deterministic REQ-043 project-obligation reasoning output']
    return []
