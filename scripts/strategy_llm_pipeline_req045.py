#!/usr/bin/env python3
'REQ-045 contract/data-model surface for alternative strategic scenario generation.'

from __future__ import annotations

import argparse

import hashlib

import json

import re

import sys

from datetime import datetime, timezone

from pathlib import Path

from typing import Any, Mapping, Sequence

RUNTIME_MODE = 'llm-first'

EXECUTION_MODE = 'long-thinking'

REQ_045_REQUIREMENT_ID = 'REQ-045'

REQ_045_SCHEMA_VERSION = 'req-045.alternative-strategic-scenario-generator.v1'

REQ_045_ANALYSIS_TYPE = 'alternative_strategic_scenario_generator'

REQ_045_PROCESSING_STRATEGY = 'alternative-strategic-scenario-generation'

REQ_045_REASONING_MODE = 'deterministic-branch-comparison'

REQ_045_CALL_TRACE_SCHEMA_VERSION = 'req-045.llm-call-trace.v1'

REQ_045_TRIGGER_THRESHOLD = 0.7

REQ_045_ALLOWED_DECISIONS = {'generate-alternatives', 'single-path-sufficient'}

REQ_045_ALLOWED_CONFIDENCE = {'high', 'medium', 'low'}

REQ_045_ALLOWED_TRADEOFF_POSITIONS = {'advantaged', 'balanced', 'constrained'}

REQ_045_ALLOWED_TRIGGER_OPERATORS = {'gte', 'lte', 'eq', 'present'}

REQ_045_BRANCH_KEY_RE = re.compile('^[a-z0-9]+(?:-[a-z0-9]+)*$')

REQ_045_CONDITION_ID_RE = re.compile('^cond\\.[a-z0-9]+(?:-[a-z0-9]+)*$')

REQ_045_REASON_CODE_ANALYSIS_SYNTHESIS_CONTRADICTION = 'analysis_synthesis_contradiction'

REQ_045_REASON_CODE_UNCITED_STRATEGIC_CLAIM_BLOCKED = 'uncited_strategic_claim_blocked'

REQ_045_CROSS_PROJECT_HINTS = ('cross-project', 'cross project', 'shared dependency', 'multi-project')

REQ_045_DEFAULT_CALL_TRACE_PATH = Path('strategy/current/llm_call_trace.jsonl')

class Req045Error(ValueError):
    """Raised when REQ-045 input is malformed."""

def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ''
    return str(value).strip()

def _require_text(value: Any, *, field_name: str) -> str:
    text = _as_text(value)
    if not text:
        raise Req045Error(f'{field_name} must be a non-empty string')
    return text

def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise Req045Error(f'{field_name} must be an object')
    return value

def _normalize_root(value: Any, *, field_name: str) -> str:
    normalized = str(Path(_require_text(value, field_name=field_name)).expanduser().resolve())
    if not normalized.startswith('/'):
        raise Req045Error(f'{field_name} must normalize to an absolute path')
    return normalized

def _normalize_utc(value: Any, *, field_name: str) -> str:
    text = _require_text(value, field_name=field_name)
    try:
        parsed = datetime.strptime(text, '%Y-%m-%dT%H:%M:%SZ')
    except ValueError as exc:
        raise Req045Error(f'{field_name} must be ISO-8601 UTC like 2026-03-16T12:00:00Z') from exc
    return parsed.replace(tzinfo=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def _normalize_string_list(raw_value: Any, *, field_name: str, min_items: int=0) -> list[str]:
    if raw_value is None:
        raw_items: Sequence[Any] = []
    else:
        if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
            raise Req045Error(f'{field_name} must be an array of non-empty strings')
        raw_items = raw_value
    normalized: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_items):
        text = _require_text(item, field_name=f'{field_name}[{index}]')
        if text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    if len(normalized) < min_items:
        raise Req045Error(f'{field_name} must contain at least {min_items} item(s)')
    return sorted(normalized)

def _normalize_score(value: Any, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Req045Error(f'{field_name} must be a number between 0.0 and 1.0')
    score = round(float(value), 3)
    if score < 0.0 or score > 1.0:
        raise Req045Error(f'{field_name} must be between 0.0 and 1.0')
    return score

def _normalize_tradeoff_rows(raw_value: Any, *, field_name: str) -> list[dict[str, str]]:
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise Req045Error(f'{field_name} must be an array')
    normalized: list[dict[str, str]] = []
    seen_dimensions: set[str] = set()
    for index, item in enumerate(raw_value):
        row = _require_mapping(item, field_name=f'{field_name}[{index}]')
        dimension = _require_text(row.get('dimension'), field_name=f'{field_name}[{index}].dimension')
        if dimension in seen_dimensions:
            raise Req045Error(f'{field_name}[{index}].dimension must be unique per scenario')
        seen_dimensions.add(dimension)
        position = _require_text(row.get('position'), field_name=f'{field_name}[{index}].position').lower()
        if position not in REQ_045_ALLOWED_TRADEOFF_POSITIONS:
            allowed = sorted(REQ_045_ALLOWED_TRADEOFF_POSITIONS)
            raise Req045Error(f'{field_name}[{index}].position must be one of: {allowed}')
        summary = _require_text(row.get('summary'), field_name=f'{field_name}[{index}].summary')
        normalized.append({'dimension': dimension, 'position': position, 'summary': summary})
    if not normalized:
        raise Req045Error(f'{field_name} must contain at least 1 item(s)')
    normalized.sort(key=lambda row: (row['dimension'], row['position'], row['summary']))
    return normalized

def _normalize_trigger_condition_value(value: Any, *, field_name: str) -> str | float | int | bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and (not isinstance(value, bool)):
        return value
    if isinstance(value, float):
        return round(value, 3)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise Req045Error(f'{field_name} must be non-empty when provided')
        return text
    raise Req045Error(f'{field_name} must be null, boolean, number, or string')

def _normalize_trigger_condition_rows(raw_value: Any, *, field_name: str) -> list[dict[str, Any]]:
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise Req045Error(f'{field_name} must be an array')
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        row = _require_mapping(item, field_name=f'{field_name}[{index}]')
        condition_id = _require_text(row.get('condition_id'), field_name=f'{field_name}[{index}].condition_id')
        if not REQ_045_CONDITION_ID_RE.match(condition_id):
            raise Req045Error(f'{field_name}[{index}].condition_id must match {REQ_045_CONDITION_ID_RE.pattern}')
        if condition_id in seen_ids:
            raise Req045Error(f'{field_name}[{index}].condition_id must be unique per scenario')
        seen_ids.add(condition_id)
        signal = _require_text(row.get('signal'), field_name=f'{field_name}[{index}].signal')
        operator = _require_text(row.get('operator'), field_name=f'{field_name}[{index}].operator').lower()
        if operator not in REQ_045_ALLOWED_TRIGGER_OPERATORS:
            allowed = sorted(REQ_045_ALLOWED_TRIGGER_OPERATORS)
            raise Req045Error(f'{field_name}[{index}].operator must be one of: {allowed}')
        value = _normalize_trigger_condition_value(row.get('value'), field_name=f'{field_name}[{index}].value')
        if operator == 'present' and value is not None:
            raise Req045Error(f'{field_name}[{index}].value must be null when operator is present')
        if operator != 'present' and value is None:
            raise Req045Error(f'{field_name}[{index}].value must be set when operator is not present')
        summary = _require_text(row.get('summary'), field_name=f'{field_name}[{index}].summary')
        normalized.append({'condition_id': condition_id, 'signal': signal, 'operator': operator, 'value': value, 'summary': summary})
    if not normalized:
        raise Req045Error(f'{field_name} must contain at least 1 item(s)')
    normalized.sort(key=lambda row: (row['condition_id'], row['signal']))
    return normalized

def _normalize_scenario_candidates(raw_value: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise Req045Error('scenario_candidates must be an array')
    normalized: list[dict[str, Any]] = []
    seen_branch_keys: set[str] = set()
    for index, item in enumerate(raw_value):
        row = _require_mapping(item, field_name=f'scenario_candidates[{index}]')
        branch_key = _require_text(row.get('branch_key'), field_name=f'scenario_candidates[{index}].branch_key').lower()
        if not REQ_045_BRANCH_KEY_RE.match(branch_key):
            raise Req045Error(f'scenario_candidates[{index}].branch_key must match {REQ_045_BRANCH_KEY_RE.pattern}')
        if branch_key in seen_branch_keys:
            raise Req045Error(f'scenario_candidates[{index}].branch_key must be unique')
        seen_branch_keys.add(branch_key)
        label = _require_text(row.get('label'), field_name=f'scenario_candidates[{index}].label')
        summary = _require_text(row.get('summary'), field_name=f'scenario_candidates[{index}].summary')
        comparative_tradeoffs = _normalize_tradeoff_rows(row.get('comparative_tradeoffs'), field_name=f'scenario_candidates[{index}].comparative_tradeoffs')
        trigger_conditions = _normalize_trigger_condition_rows(row.get('trigger_conditions'), field_name=f'scenario_candidates[{index}].trigger_conditions')
        evidence_refs = _normalize_string_list(row.get('evidence_refs'), field_name=f'scenario_candidates[{index}].evidence_refs', min_items=1)
        normalized.append({'branch_key': branch_key, 'label': label, 'summary': summary, 'comparative_tradeoffs': comparative_tradeoffs, 'trigger_conditions': trigger_conditions, 'evidence_refs': evidence_refs})
    if len(normalized) < 2:
        raise Req045Error('scenario_candidates must contain at least 2 item(s)')
    normalized.sort(key=lambda row: (row['branch_key'], row['label']))
    return normalized

def _tradeoff_advantage_score(tradeoffs: Sequence[Mapping[str, Any]]) -> int:
    score = 0
    for row in tradeoffs:
        position = _as_text(row.get('position')).lower()
        if position == 'advantaged':
            score += 1
        elif position == 'constrained':
            score -= 1
    return score

def _collect_unique_refs(*ref_groups: Sequence[Any]) -> list[str]:
    seen: set[str] = set()
    for refs in ref_groups:
        for raw_ref in refs:
            ref = _as_text(raw_ref)
            if ref:
                seen.add(ref)
    return sorted(seen)

def _validation_error_with_reason_code(*, message: str, reason_code: str, evidence_refs: Sequence[Any]) -> str:
    refs = _collect_unique_refs(evidence_refs)
    rendered_refs = ', '.join(refs) if refs else 'none'
    return f'{message} [reason_code={reason_code}; evidence_refs={rendered_refs}]'

def _scenario_is_cross_project(row: Mapping[str, Any]) -> bool:
    haystack = ' '.join((_as_text(row.get('branch_key')).lower(), _as_text(row.get('label')).lower(), _as_text(row.get('summary')).lower()))
    return any((hint in haystack for hint in REQ_045_CROSS_PROJECT_HINTS))

def _build_cross_project_recommendation_rows(*, triggered: bool, scenario_rows: Sequence[Mapping[str, Any]], earth_sweep_evidence_refs: Sequence[str]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    earth_ref_set = set(earth_sweep_evidence_refs)
    scenario_ids_with_earth_evidence: list[str] = []
    cross_project_scenario_ids: list[str] = []
    obligations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    for row in scenario_rows:
        scenario_id = _require_text(row.get('scenario_id'), field_name='scenarios[].scenario_id')
        branch_key = _require_text(row.get('branch_key'), field_name='scenarios[].branch_key')
        branch_refs = _normalize_string_list(row.get('evidence_refs'), field_name=f'{scenario_id}.evidence_refs')
        earth_refs_for_branch = sorted((ref for ref in branch_refs if ref in earth_ref_set))
        is_cross_project = _scenario_is_cross_project(row)
        if is_cross_project:
            cross_project_scenario_ids.append(scenario_id)
        if earth_refs_for_branch:
            scenario_ids_with_earth_evidence.append(scenario_id)
        if triggered and is_cross_project and earth_refs_for_branch:
            obligations.append({'obligation_id': f'obl.{branch_key}', 'scenario_id': scenario_id, 'summary': f'Use {branch_key} only while its trigger conditions remain satisfied.', 'trigger_condition_ids': sorted((_require_text(condition.get('condition_id'), field_name=f'{scenario_id}.trigger_conditions[].condition_id') for condition in row.get('trigger_conditions', []) if isinstance(condition, Mapping))), 'evidence_refs': earth_refs_for_branch})
        elif triggered and is_cross_project and (not earth_sweep_evidence_refs):
            open_risks.append({'risk_id': f'risk.{branch_key}.earth-sweep-evidence-missing', 'reason_code': 'earth_sweep_evidence_missing', 'scenario_id': scenario_id, 'summary': f'Cross-project branch {branch_key} is not promoted to an obligation because Earth-sweep evidence refs are missing.', 'evidence_refs': branch_refs})
    context = {'cross_project': bool(earth_sweep_evidence_refs), 'earth_sweep_evidence_refs': list(earth_sweep_evidence_refs), 'cross_project_scenario_ids': sorted(cross_project_scenario_ids), 'scenario_ids_with_earth_sweep_evidence': sorted(scenario_ids_with_earth_evidence)}
    obligations.sort(key=lambda row: (row['scenario_id'], row['obligation_id']))
    open_risks.sort(key=lambda row: row['risk_id'])
    return (context, obligations, open_risks)

def _canonical_call_input(*, target_project_root: str, earth_root: str, output_root: str, revision_identity: str, strategy_goal: str) -> dict[str, Any]:
    return {'runtime_mode': RUNTIME_MODE, 'execution_mode': EXECUTION_MODE, 'target_project_root': target_project_root, 'earth_root': earth_root, 'output_root': output_root, 'revision_identity': revision_identity, 'strategy_goal': strategy_goal}

def _canonical_processing_input(*, generated_at_utc: str, uncertainty_score: float, conflict_score: float, uncertainty_signals: list[str], conflict_signals: list[str], target_project_evidence_refs: list[str], earth_sweep_evidence_refs: list[str], scenario_candidates: list[dict[str, Any]]) -> dict[str, Any]:
    earth_ref_set = set(earth_sweep_evidence_refs)
    return {'generated_at_utc': generated_at_utc, 'uncertainty_score': uncertainty_score, 'conflict_score': conflict_score, 'uncertainty_signals': list(uncertainty_signals), 'conflict_signals': list(conflict_signals), 'target_project_evidence_refs': list(target_project_evidence_refs), 'earth_sweep_evidence_refs': list(earth_sweep_evidence_refs), 'scenario_candidates': [{'branch_key': row['branch_key'], 'label': row['label'], 'summary': row['summary'], 'comparative_tradeoffs': [{'dimension': tradeoff['dimension'], 'position': tradeoff['position'], 'summary': tradeoff['summary']} for tradeoff in row['comparative_tradeoffs']], 'trigger_conditions': [{'condition_id': condition['condition_id'], 'signal': condition['signal'], 'operator': condition['operator'], 'value': condition['value'], 'summary': condition['summary']} for condition in row['trigger_conditions']], 'evidence_refs': list(row['evidence_refs'])} for row in scenario_candidates], 'broad_sweep_context': {'earth_sweep_evidence_refs': list(earth_sweep_evidence_refs), 'scenario_branch_keys_with_earth_sweep_evidence': sorted((row['branch_key'] for row in scenario_candidates if any((ref in earth_ref_set for ref in row['evidence_refs']))))}}

def _canonical_digest(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()

def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)

def _trace_ref_list(*ref_groups: Sequence[str]) -> list[str]:
    return _collect_unique_refs(*ref_groups)

def _normalize_output_ref(output_payload_ref: str) -> str:
    return _require_text(output_payload_ref, field_name='output_payload_ref')

def build_req_045_llm_call_trace_rows(payload: Mapping[str, Any], *, output_payload_ref: str='stdout:REQ-045') -> list[dict[str, Any]]:
    """Build replay-stable REQ-045 call-trace rows."""
    errors = validate_req_045_alternative_strategic_scenario_generator(payload)
    if errors:
        raise Req045Error('; '.join(errors))
    contract = _require_mapping(payload.get('alternative_strategic_scenario_generator'), field_name='alternative_strategic_scenario_generator')
    processing = _require_mapping(payload.get('processing_behavior'), field_name='processing_behavior')
    recommendation = _require_mapping(processing.get('recommendation'), field_name='processing_behavior.recommendation')
    context_usage = _require_mapping(processing.get('context_usage'), field_name='processing_behavior.context_usage')
    call_metadata = _require_mapping(payload.get('call_metadata'), field_name='call_metadata')
    scenario_trigger = _require_mapping(contract.get('scenario_trigger'), field_name='scenario_trigger')
    evidence_refs = _require_mapping(contract.get('evidence_refs'), field_name='evidence_refs')
    target_refs = _normalize_string_list(evidence_refs.get('target_project'), field_name='target_project_evidence_refs', min_items=1)
    earth_refs = _normalize_string_list(evidence_refs.get('earth_sweep'), field_name='earth_sweep_evidence_refs')
    scenario_ids = _normalize_string_list(context_usage.get('scenario_ids_considered'), field_name='scenario_ids_considered', min_items=2)
    trigger_condition_ids = _normalize_string_list(context_usage.get('trigger_condition_ids_used'), field_name='trigger_condition_ids_used', min_items=1)
    preferred_branch = _as_text(recommendation.get('preferred_branch'))
    fallback_branch = _as_text(recommendation.get('fallback_branch'))
    decision = _require_text(recommendation.get('decision'), field_name='decision')
    confidence = _require_text(recommendation.get('confidence'), field_name='confidence')
    output_ref = _normalize_output_ref(output_payload_ref)
    scenario_generation_input_refs = _trace_ref_list([f"digest:canonical_input:{_require_text(call_metadata.get('canonical_input_sha256'), field_name='canonical_input_sha256')}"], [f"digest:processing_input:{_require_text(call_metadata.get('processing_input_sha256'), field_name='processing_input_sha256')}"], [f"trigger:uncertainty_score:{scenario_trigger.get('uncertainty_score'):.3f}"], [f"trigger:conflict_score:{scenario_trigger.get('conflict_score'):.3f}"], [f"decision:triggered:{bool(scenario_trigger.get('triggered'))}"], target_refs, earth_refs)
    scenario_generation_output_refs = _trace_ref_list([f"scenario:{scenario_id}" for scenario_id in scenario_ids], [f"call_id:{_require_text(call_metadata.get('processing_call_id'), field_name='processing_call_id')}"], [f"output:{output_ref}"])
    recommendation_input_refs = _trace_ref_list(scenario_generation_output_refs, [f"trigger_condition:{condition_id}" for condition_id in trigger_condition_ids], _normalize_string_list(recommendation.get('evidence_refs'), field_name='recommendation.evidence_refs', min_items=1))
    recommendation_output_refs = _trace_ref_list([f"decision:{decision}"], [f"confidence:{confidence}"], ([f"branch:preferred:{preferred_branch}"] if preferred_branch else []), ([f"branch:fallback:{fallback_branch}"] if fallback_branch else []), [f"call_id:{_require_text(call_metadata.get('reproducible_call_id'), field_name='reproducible_call_id')}"], [f"output:{output_ref}"])
    raw_rows = [{'call_index': 1, 'call_objective': 'Generate alternative strategic scenarios when uncertainty/conflict thresholds indicate branching risk.', 'input_refs': scenario_generation_input_refs, 'output_refs': scenario_generation_output_refs, 'handoff_summary': f'Generated {len(scenario_ids)} strategic scenario branches; handoff includes comparative tradeoffs and trigger conditions for recommendation synthesis.'}, {'call_index': 2, 'call_objective': 'Compare branch tradeoffs and trigger conditions to produce a bounded recommendation handoff.', 'input_refs': recommendation_input_refs, 'output_refs': recommendation_output_refs, 'handoff_summary': f'Produced recommendation decision={decision} confidence={confidence}; handoff packages preferred/fallback branch selection for downstream execution.'}]
    rows: list[dict[str, Any]] = []
    for row in raw_rows:
        normalized_row = {'trace_schema_version': REQ_045_CALL_TRACE_SCHEMA_VERSION, 'requirement_id': REQ_045_REQUIREMENT_ID, 'processing_strategy': REQ_045_PROCESSING_STRATEGY, 'call_index': row['call_index'], 'call_objective': row['call_objective'], 'input_refs': row['input_refs'], 'output_refs': row['output_refs'], 'handoff_summary': row['handoff_summary']}
        input_sha256 = hashlib.sha256(_canonical_json(normalized_row['input_refs']).encode('utf-8')).hexdigest()
        output_sha256 = hashlib.sha256(_canonical_json(normalized_row['output_refs']).encode('utf-8')).hexdigest()
        call_key = {'call_index': normalized_row['call_index'], 'call_objective': normalized_row['call_objective'], 'input_sha256': input_sha256, 'output_sha256': output_sha256, 'handoff_summary': normalized_row['handoff_summary']}
        call_sha256 = hashlib.sha256(_canonical_json(call_key).encode('utf-8')).hexdigest()
        normalized_row['input_sha256'] = input_sha256
        normalized_row['output_sha256'] = output_sha256
        normalized_row['llm_call_id'] = f'req045-llm-call-{call_sha256[:16]}'
        normalized_row['replay_stable'] = True
        rows.append(normalized_row)
    return rows

def _scenario_generation_reasons(*, uncertainty_score: float, conflict_score: float, uncertainty_signals: Sequence[str], conflict_signals: Sequence[str]) -> list[str]:
    reasons: list[str] = []
    if uncertainty_score >= REQ_045_TRIGGER_THRESHOLD:
        reasons.append(f'uncertainty_score={uncertainty_score:.3f} meets or exceeds {REQ_045_TRIGGER_THRESHOLD:.1f}')
    if conflict_score >= REQ_045_TRIGGER_THRESHOLD:
        reasons.append(f'conflict_score={conflict_score:.3f} meets or exceeds {REQ_045_TRIGGER_THRESHOLD:.1f}')
    if uncertainty_signals:
        reasons.append(f'uncertainty_signals={len(uncertainty_signals)} captured for branch comparison')
    if conflict_signals:
        reasons.append(f'conflict_signals={len(conflict_signals)} captured for branch comparison')
    if not reasons:
        reasons.append('uncertainty and conflict remain below the high-threshold trigger')
    return reasons

def _recommendation_confidence(*, triggered: bool, earth_sweep_evidence_refs: Sequence[str]) -> str:
    if not triggered:
        return 'low'
    if earth_sweep_evidence_refs:
        return 'high'
    return 'medium'

def build_req_045_alternative_strategic_scenario_generator(*, generated_at_utc: str, target_project_root: str, earth_root: str, output_root: str, revision_identity: str, strategy_goal: str, uncertainty_score: float, conflict_score: float, scenario_candidates: list[Mapping[str, Any]] | None, uncertainty_signals: list[str] | None=None, conflict_signals: list[str] | None=None, target_project_evidence_refs: list[str] | None=None, earth_sweep_evidence_refs: list[str] | None=None) -> dict[str, Any]:
    """Build the REQ-045 alternative strategic scenario generator payload."""
    normalized_generated_at = _normalize_utc(generated_at_utc, field_name='generated_at_utc')
    normalized_target_project_root = _normalize_root(target_project_root, field_name='target_project_root')
    normalized_earth_root = _normalize_root(earth_root, field_name='earth_root')
    normalized_output_root = _normalize_root(output_root, field_name='output_root')
    normalized_revision_identity = _require_text(revision_identity, field_name='revision_identity')
    normalized_strategy_goal = _require_text(strategy_goal, field_name='strategy_goal')
    normalized_uncertainty_score = _normalize_score(uncertainty_score, field_name='uncertainty_score')
    normalized_conflict_score = _normalize_score(conflict_score, field_name='conflict_score')
    normalized_uncertainty_signals = _normalize_string_list(uncertainty_signals, field_name='uncertainty_signals')
    normalized_conflict_signals = _normalize_string_list(conflict_signals, field_name='conflict_signals')
    normalized_target_refs = _normalize_string_list(target_project_evidence_refs, field_name='target_project_evidence_refs')
    normalized_earth_refs = _normalize_string_list(earth_sweep_evidence_refs, field_name='earth_sweep_evidence_refs')
    normalized_candidates = _normalize_scenario_candidates(scenario_candidates)
    triggered = normalized_uncertainty_score >= REQ_045_TRIGGER_THRESHOLD or normalized_conflict_score >= REQ_045_TRIGGER_THRESHOLD
    trigger_reasons = _scenario_generation_reasons(uncertainty_score=normalized_uncertainty_score, conflict_score=normalized_conflict_score, uncertainty_signals=normalized_uncertainty_signals, conflict_signals=normalized_conflict_signals)
    scenario_rows: list[dict[str, Any]] = []
    dimension_set: set[str] = set()
    trigger_condition_ids: list[str] = []
    for row in normalized_candidates:
        scenario_id = f"scenario.{row['branch_key']}"
        dimension_set.update((tradeoff['dimension'] for tradeoff in row['comparative_tradeoffs']))
        trigger_condition_ids.extend((condition['condition_id'] for condition in row['trigger_conditions']))
        scenario_rows.append({'scenario_id': scenario_id, 'branch_key': row['branch_key'], 'label': row['label'], 'summary': row['summary'], 'comparative_tradeoffs': [{'dimension': tradeoff['dimension'], 'position': tradeoff['position'], 'summary': tradeoff['summary']} for tradeoff in row['comparative_tradeoffs']], 'trigger_conditions': [{'condition_id': condition['condition_id'], 'signal': condition['signal'], 'operator': condition['operator'], 'value': condition['value'], 'summary': condition['summary']} for condition in row['trigger_conditions']], 'evidence_refs': list(row['evidence_refs'])})
    ranked_scenarios = sorted(scenario_rows, key=lambda row: (-_tradeoff_advantage_score(row['comparative_tradeoffs']), row['branch_key'], row['scenario_id']))
    preferred_branch = ranked_scenarios[0]['branch_key'] if triggered and ranked_scenarios else ''
    fallback_branch = ranked_scenarios[1]['branch_key'] if triggered and len(ranked_scenarios) > 1 else ''
    recommendation_decision = 'generate-alternatives' if triggered else 'single-path-sufficient'
    recommendation_rationale = 'High uncertainty or conflict requires multiple bounded strategic branches with explicit selection triggers.' if triggered else 'Current uncertainty and conflict do not require alternative scenario branching.'
    recommendation_confidence = _recommendation_confidence(triggered=triggered, earth_sweep_evidence_refs=normalized_earth_refs)
    recommendation_cross_project_context, recommendation_obligations, recommendation_open_risks = _build_cross_project_recommendation_rows(triggered=triggered, scenario_rows=scenario_rows, earth_sweep_evidence_refs=normalized_earth_refs)
    canonical_input = _canonical_call_input(target_project_root=normalized_target_project_root, earth_root=normalized_earth_root, output_root=normalized_output_root, revision_identity=normalized_revision_identity, strategy_goal=normalized_strategy_goal)
    canonical_processing_input = _canonical_processing_input(generated_at_utc=normalized_generated_at, uncertainty_score=normalized_uncertainty_score, conflict_score=normalized_conflict_score, uncertainty_signals=normalized_uncertainty_signals, conflict_signals=normalized_conflict_signals, target_project_evidence_refs=normalized_target_refs, earth_sweep_evidence_refs=normalized_earth_refs, scenario_candidates=normalized_candidates)
    input_digest = _canonical_digest(canonical_input)
    processing_digest = _canonical_digest(canonical_processing_input)
    evidence_refs = _collect_unique_refs(normalized_target_refs, normalized_earth_refs, *[row['evidence_refs'] for row in scenario_rows])
    return {'schema_version': REQ_045_SCHEMA_VERSION, 'requirement_id': REQ_045_REQUIREMENT_ID, 'analysis_type': REQ_045_ANALYSIS_TYPE, 'alternative_strategic_scenario_generator': {'runtime_mode': RUNTIME_MODE, 'execution_mode': EXECUTION_MODE, 'generated_at_utc': normalized_generated_at, 'target_project_root': normalized_target_project_root, 'earth_root': normalized_earth_root, 'output_root': normalized_output_root, 'revision_identity': normalized_revision_identity, 'strategy_goal': normalized_strategy_goal, 'scenario_trigger': {'uncertainty_score': normalized_uncertainty_score, 'conflict_score': normalized_conflict_score, 'triggered': triggered, 'trigger_threshold': REQ_045_TRIGGER_THRESHOLD, 'reasons': trigger_reasons}, 'evidence_refs': {'target_project': normalized_target_refs, 'earth_sweep': normalized_earth_refs}, 'scenarios': scenario_rows, 'comparative_summary': {'scenario_count': len(scenario_rows), 'branch_keys': [row['branch_key'] for row in scenario_rows], 'dimensions_covered': sorted(dimension_set), 'trigger_condition_count': len(trigger_condition_ids), 'requires_alternative_generation': triggered}}, 'processing_behavior': {'strategy': REQ_045_PROCESSING_STRATEGY, 'reasoning_mode': REQ_045_REASONING_MODE, 'heuristic_summarization_only': False, 'context_inputs': canonical_processing_input, 'context_usage': {'triggered': triggered, 'scenario_ids_considered': [row['scenario_id'] for row in scenario_rows], 'tradeoff_dimensions_used': sorted(dimension_set), 'trigger_condition_ids_used': sorted(trigger_condition_ids), 'evidence_refs_used': evidence_refs, 'cross_project_context_used': bool(recommendation_cross_project_context['cross_project_scenario_ids']), 'cross_project_scenario_ids_used': recommendation_cross_project_context['cross_project_scenario_ids'], 'cross_project_obligation_ids_used': [row['obligation_id'] for row in recommendation_obligations], 'cross_project_open_risk_ids': [row['risk_id'] for row in recommendation_open_risks]}, 'recommendation': {'decision': recommendation_decision, 'rationale': recommendation_rationale, 'confidence': recommendation_confidence, 'preferred_branch': preferred_branch, 'fallback_branch': fallback_branch, 'evidence_refs': evidence_refs, 'cross_project_context': recommendation_cross_project_context, 'obligations': recommendation_obligations, 'open_risks': recommendation_open_risks}}, 'call_metadata': {'reproducibility': 'deterministic-input-fingerprint', 'canonical_input_sha256': input_digest, 'reproducible_call_id': f'req045-{input_digest[:16]}', 'canonical_input': canonical_input, 'processing_input_sha256': processing_digest, 'processing_call_id': f'req045-processing-{processing_digest[:16]}', 'canonical_processing_input': canonical_processing_input}}

def validate_req_045_alternative_strategic_scenario_generator(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-045 payload shape and deterministic metadata."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ['payload must be a JSON object']
    required_top = {'schema_version', 'requirement_id', 'analysis_type', 'alternative_strategic_scenario_generator', 'processing_behavior', 'call_metadata'}
    top_keys = set(payload.keys())
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f'missing top-level keys: {missing_top}')
    unexpected_top = sorted(top_keys - required_top)
    if unexpected_top:
        errors.append(f'unexpected top-level keys: {unexpected_top}')
    if payload.get('schema_version') != REQ_045_SCHEMA_VERSION:
        errors.append(f'schema_version must be {REQ_045_SCHEMA_VERSION}')
    if payload.get('requirement_id') != REQ_045_REQUIREMENT_ID:
        errors.append(f'requirement_id must be {REQ_045_REQUIREMENT_ID}')
    if payload.get('analysis_type') != REQ_045_ANALYSIS_TYPE:
        errors.append(f'analysis_type must be {REQ_045_ANALYSIS_TYPE}')
    contract = payload.get('alternative_strategic_scenario_generator')
    if not isinstance(contract, Mapping):
        errors.append('alternative_strategic_scenario_generator must be an object')
        return errors
    for required_field in ('runtime_mode', 'execution_mode', 'generated_at_utc', 'target_project_root', 'earth_root', 'output_root', 'revision_identity', 'strategy_goal', 'scenario_trigger', 'evidence_refs', 'scenarios', 'comparative_summary'):
        if required_field not in contract:
            errors.append(f'alternative_strategic_scenario_generator missing {required_field}')
    if contract.get('runtime_mode') != RUNTIME_MODE:
        errors.append(f'alternative_strategic_scenario_generator.runtime_mode must be {RUNTIME_MODE}')
    if contract.get('execution_mode') != EXECUTION_MODE:
        errors.append(f'alternative_strategic_scenario_generator.execution_mode must be {EXECUTION_MODE}')
    generated_at_utc = contract.get('generated_at_utc')
    if isinstance(generated_at_utc, str):
        try:
            _normalize_utc(generated_at_utc, field_name='alternative_strategic_scenario_generator.generated_at_utc')
        except Req045Error as exc:
            errors.append(str(exc))
    else:
        errors.append('alternative_strategic_scenario_generator.generated_at_utc must be a string')
    for root_field in ('target_project_root', 'earth_root', 'output_root'):
        value = contract.get(root_field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f'alternative_strategic_scenario_generator.{root_field} must be a non-empty string')
        elif not value.startswith('/'):
            errors.append(f'alternative_strategic_scenario_generator.{root_field} must be absolute')
    if not isinstance(contract.get('revision_identity'), str) or not str(contract.get('revision_identity')).strip():
        errors.append('alternative_strategic_scenario_generator.revision_identity must be a non-empty string')
    if not isinstance(contract.get('strategy_goal'), str) or not str(contract.get('strategy_goal')).strip():
        errors.append('alternative_strategic_scenario_generator.strategy_goal must be a non-empty string')
    scenario_trigger = contract.get('scenario_trigger')
    if not isinstance(scenario_trigger, Mapping):
        errors.append('alternative_strategic_scenario_generator.scenario_trigger must be an object')
    else:
        for field_name in ('uncertainty_score', 'conflict_score', 'triggered', 'trigger_threshold', 'reasons'):
            if field_name not in scenario_trigger:
                errors.append(f'alternative_strategic_scenario_generator.scenario_trigger missing {field_name}')
    evidence_refs = contract.get('evidence_refs')
    if not isinstance(evidence_refs, Mapping):
        errors.append('alternative_strategic_scenario_generator.evidence_refs must be an object')
    else:
        for field_name in ('target_project', 'earth_sweep'):
            if not isinstance(evidence_refs.get(field_name), list):
                errors.append(f'alternative_strategic_scenario_generator.evidence_refs.{field_name} must be a list')
    scenarios = contract.get('scenarios')
    if not isinstance(scenarios, list):
        errors.append('alternative_strategic_scenario_generator.scenarios must be a list')
        scenarios = []
    elif len(scenarios) < 2:
        errors.append('alternative_strategic_scenario_generator.scenarios must contain at least 2 items')
    scenario_ids: list[str] = []
    dimension_set: set[str] = set()
    trigger_condition_ids: list[str] = []
    for index, row in enumerate(scenarios):
        if not isinstance(row, Mapping):
            errors.append(f'alternative_strategic_scenario_generator.scenarios[{index}] must be an object')
            continue
        for required_field in ('scenario_id', 'branch_key', 'label', 'summary', 'comparative_tradeoffs', 'trigger_conditions', 'evidence_refs'):
            if required_field not in row:
                errors.append(f'alternative_strategic_scenario_generator.scenarios[{index}] missing {required_field}')
        branch_key = row.get('branch_key')
        if not isinstance(branch_key, str) or not REQ_045_BRANCH_KEY_RE.match(branch_key):
            errors.append(f'alternative_strategic_scenario_generator.scenarios[{index}].branch_key must match {REQ_045_BRANCH_KEY_RE.pattern}')
        scenario_id = row.get('scenario_id')
        if not isinstance(scenario_id, str) or not scenario_id.startswith('scenario.'):
            errors.append(f'alternative_strategic_scenario_generator.scenarios[{index}].scenario_id must start with scenario.')
        elif isinstance(branch_key, str) and scenario_id != f'scenario.{branch_key}':
            errors.append(f'alternative_strategic_scenario_generator.scenarios[{index}].scenario_id must mirror branch_key')
        else:
            scenario_ids.append(scenario_id)
        tradeoffs = row.get('comparative_tradeoffs')
        if not isinstance(tradeoffs, list) or not tradeoffs:
            errors.append(f'alternative_strategic_scenario_generator.scenarios[{index}].comparative_tradeoffs must be a non-empty list')
        else:
            for tradeoff_index, tradeoff in enumerate(tradeoffs):
                if not isinstance(tradeoff, Mapping):
                    errors.append(f'alternative_strategic_scenario_generator.scenarios[{index}].comparative_tradeoffs[{tradeoff_index}] must be an object')
                    continue
                position = tradeoff.get('position')
                if not isinstance(position, str) or position not in REQ_045_ALLOWED_TRADEOFF_POSITIONS:
                    allowed = sorted(REQ_045_ALLOWED_TRADEOFF_POSITIONS)
                    errors.append(f'alternative_strategic_scenario_generator.scenarios[{index}].comparative_tradeoffs[{tradeoff_index}].position must be one of: {allowed}')
                dimension = tradeoff.get('dimension')
                if isinstance(dimension, str) and dimension.strip():
                    dimension_set.add(dimension)
                else:
                    errors.append(f'alternative_strategic_scenario_generator.scenarios[{index}].comparative_tradeoffs[{tradeoff_index}].dimension must be a non-empty string')
        conditions = row.get('trigger_conditions')
        if not isinstance(conditions, list) or not conditions:
            errors.append(f'alternative_strategic_scenario_generator.scenarios[{index}].trigger_conditions must be a non-empty list')
        else:
            for condition_index, condition in enumerate(conditions):
                if not isinstance(condition, Mapping):
                    errors.append(f'alternative_strategic_scenario_generator.scenarios[{index}].trigger_conditions[{condition_index}] must be an object')
                    continue
                condition_id = condition.get('condition_id')
                if not isinstance(condition_id, str) or not REQ_045_CONDITION_ID_RE.match(condition_id):
                    errors.append(f'alternative_strategic_scenario_generator.scenarios[{index}].trigger_conditions[{condition_index}].condition_id must match {REQ_045_CONDITION_ID_RE.pattern}')
                else:
                    trigger_condition_ids.append(condition_id)
                operator = condition.get('operator')
                if not isinstance(operator, str) or operator not in REQ_045_ALLOWED_TRIGGER_OPERATORS:
                    allowed = sorted(REQ_045_ALLOWED_TRIGGER_OPERATORS)
                    errors.append(f'alternative_strategic_scenario_generator.scenarios[{index}].trigger_conditions[{condition_index}].operator must be one of: {allowed}')
        if not isinstance(row.get('evidence_refs'), list) or not row['evidence_refs']:
            errors.append(f'alternative_strategic_scenario_generator.scenarios[{index}].evidence_refs must be a non-empty list')
    comparative_summary = contract.get('comparative_summary')
    if not isinstance(comparative_summary, Mapping):
        errors.append('alternative_strategic_scenario_generator.comparative_summary must be an object')
    else:
        if comparative_summary.get('scenario_count') != len(scenarios):
            errors.append('alternative_strategic_scenario_generator.comparative_summary.scenario_count must equal scenario length')
        if comparative_summary.get('branch_keys') != [row.get('branch_key') for row in scenarios if isinstance(row, Mapping)]:
            errors.append('alternative_strategic_scenario_generator.comparative_summary.branch_keys must mirror scenarios order')
        if comparative_summary.get('dimensions_covered') != sorted(dimension_set):
            errors.append('alternative_strategic_scenario_generator.comparative_summary.dimensions_covered must mirror scenario tradeoffs')
        if comparative_summary.get('trigger_condition_count') != len(trigger_condition_ids):
            errors.append('alternative_strategic_scenario_generator.comparative_summary.trigger_condition_count must mirror scenario trigger conditions')
    processing_behavior = payload.get('processing_behavior')
    if not isinstance(processing_behavior, Mapping):
        errors.append('processing_behavior must be an object')
        return errors
    required_processing = {'strategy', 'reasoning_mode', 'heuristic_summarization_only', 'context_inputs', 'context_usage', 'recommendation'}
    processing_keys = set(processing_behavior.keys())
    missing_processing = sorted(required_processing - processing_keys)
    if missing_processing:
        errors.append(f'processing_behavior missing keys: {missing_processing}')
    unexpected_processing = sorted(processing_keys - required_processing)
    if unexpected_processing:
        errors.append(f'processing_behavior has unexpected keys: {unexpected_processing}')
    if processing_behavior.get('strategy') != REQ_045_PROCESSING_STRATEGY:
        errors.append(f'processing_behavior.strategy must be {REQ_045_PROCESSING_STRATEGY}')
    if processing_behavior.get('reasoning_mode') != REQ_045_REASONING_MODE:
        errors.append(f'processing_behavior.reasoning_mode must be {REQ_045_REASONING_MODE}')
    if processing_behavior.get('heuristic_summarization_only') is not False:
        errors.append('processing_behavior.heuristic_summarization_only must be false')
    metadata_for_diagnostics = payload.get('call_metadata')
    metadata_refs_for_diagnostics: list[str] = []
    if isinstance(metadata_for_diagnostics, Mapping):
        metadata_refs_for_diagnostics = _collect_unique_refs([f"call_id:{_as_text(metadata_for_diagnostics.get('reproducible_call_id'))}"], [f"call_id:{_as_text(metadata_for_diagnostics.get('processing_call_id'))}"])
    context_usage = processing_behavior.get('context_usage')
    if not isinstance(context_usage, Mapping):
        errors.append('processing_behavior.context_usage must be an object')
    else:
        if context_usage.get('scenario_ids_considered') != scenario_ids:
            errors.append('processing_behavior.context_usage.scenario_ids_considered must mirror scenario ids')
        if context_usage.get('tradeoff_dimensions_used') != sorted(dimension_set):
            errors.append('processing_behavior.context_usage.tradeoff_dimensions_used must mirror tradeoff dimensions')
        if context_usage.get('trigger_condition_ids_used') != sorted(trigger_condition_ids):
            errors.append('processing_behavior.context_usage.trigger_condition_ids_used must mirror trigger condition ids')
        expected_cross_project_ids = sorted((row.get('scenario_id') for row in scenarios if isinstance(row, Mapping) and _scenario_is_cross_project(row) and isinstance(row.get('scenario_id'), str)))
        if context_usage.get('cross_project_context_used') != bool(expected_cross_project_ids):
            errors.append('processing_behavior.context_usage.cross_project_context_used must reflect detected cross-project scenarios')
        if context_usage.get('cross_project_scenario_ids_used') != expected_cross_project_ids:
            errors.append('processing_behavior.context_usage.cross_project_scenario_ids_used must mirror cross-project scenario ids')
    recommendation = processing_behavior.get('recommendation')
    if not isinstance(recommendation, Mapping):
        errors.append('processing_behavior.recommendation must be an object')
    else:
        for field_name in ('decision', 'rationale', 'confidence', 'preferred_branch', 'fallback_branch', 'evidence_refs', 'cross_project_context', 'obligations', 'open_risks'):
            if field_name not in recommendation:
                errors.append(f'processing_behavior.recommendation missing {field_name}')
        decision = recommendation.get('decision')
        if not isinstance(decision, str) or decision not in REQ_045_ALLOWED_DECISIONS:
            errors.append(f'processing_behavior.recommendation.decision must be one of: {sorted(REQ_045_ALLOWED_DECISIONS)}')
        confidence = recommendation.get('confidence')
        if not isinstance(confidence, str) or confidence not in REQ_045_ALLOWED_CONFIDENCE:
            errors.append(f'processing_behavior.recommendation.confidence must be one of: {sorted(REQ_045_ALLOWED_CONFIDENCE)}')
        recommendation_evidence_refs = recommendation.get('evidence_refs')
        recommendation_evidence_set: set[str] = set()
        if not isinstance(recommendation_evidence_refs, list):
            errors.append('processing_behavior.recommendation.evidence_refs must be a list')
        else:
            recommendation_evidence_set = {_as_text(ref) for ref in recommendation_evidence_refs if isinstance(ref, str) and _as_text(ref)}
            if not recommendation_evidence_set:
                errors.append('processing_behavior.recommendation.evidence_refs must contain at least one citation ref')
        earth_sweep_refs = contract.get('evidence_refs', {}).get('earth_sweep', []) if isinstance(contract.get('evidence_refs'), Mapping) else []
        earth_sweep_ref_set = set(earth_sweep_refs if isinstance(earth_sweep_refs, list) else [])
        scenario_trigger = contract.get('scenario_trigger')
        triggered = bool(scenario_trigger.get('triggered')) if isinstance(scenario_trigger, Mapping) else False
        expected_decision = 'generate-alternatives' if triggered else 'single-path-sufficient'
        preferred_branch = _as_text(recommendation.get('preferred_branch'))
        fallback_branch = _as_text(recommendation.get('fallback_branch'))
        scenario_branch_keys = sorted((row.get('branch_key') for row in scenarios if isinstance(row, Mapping) and isinstance(row.get('branch_key'), str)))
        scenario_branch_key_set = set(scenario_branch_keys)
        expected_cross_project_ids = sorted((row.get('scenario_id') for row in scenarios if isinstance(row, Mapping) and _scenario_is_cross_project(row) and isinstance(row.get('scenario_id'), str)))
        expected_scenario_ids_with_earth_refs = sorted((row.get('scenario_id') for row in scenarios if isinstance(row, Mapping) and isinstance(row.get('scenario_id'), str) and isinstance(row.get('evidence_refs'), list) and any((isinstance(ref, str) and ref in earth_sweep_ref_set for ref in row['evidence_refs']))))
        cross_project_context = recommendation.get('cross_project_context')
        if not isinstance(cross_project_context, Mapping):
            errors.append('processing_behavior.recommendation.cross_project_context must be an object')
        else:
            if cross_project_context.get('cross_project') != bool(earth_sweep_refs):
                errors.append('processing_behavior.recommendation.cross_project_context.cross_project must reflect earth_sweep evidence refs')
            if cross_project_context.get('earth_sweep_evidence_refs') != list(earth_sweep_refs):
                errors.append('processing_behavior.recommendation.cross_project_context.earth_sweep_evidence_refs must mirror contract earth_sweep refs')
            if cross_project_context.get('cross_project_scenario_ids') != expected_cross_project_ids:
                errors.append('processing_behavior.recommendation.cross_project_context.cross_project_scenario_ids must mirror scenario classification')
            if cross_project_context.get('scenario_ids_with_earth_sweep_evidence') != expected_scenario_ids_with_earth_refs:
                errors.append('processing_behavior.recommendation.cross_project_context.scenario_ids_with_earth_sweep_evidence must mirror scenario evidence usage')
        if isinstance(decision, str):
            if decision != expected_decision:
                errors.append(_validation_error_with_reason_code(message='processing_behavior.recommendation.decision contradicts alternative_strategic_scenario_generator.scenario_trigger.triggered', reason_code=REQ_045_REASON_CODE_ANALYSIS_SYNTHESIS_CONTRADICTION, evidence_refs=metadata_refs_for_diagnostics + [f'decision:{decision}', f'triggered:{triggered}']))
            if decision == 'generate-alternatives':
                if not preferred_branch or preferred_branch not in scenario_branch_key_set:
                    errors.append(_validation_error_with_reason_code(message='processing_behavior.recommendation.preferred_branch must reference a known scenario branch when decision=generate-alternatives', reason_code=REQ_045_REASON_CODE_ANALYSIS_SYNTHESIS_CONTRADICTION, evidence_refs=metadata_refs_for_diagnostics + [f"preferred_branch:{preferred_branch or 'missing'}"]))
                if len(scenario_branch_keys) >= 2:
                    if not fallback_branch or fallback_branch not in scenario_branch_key_set:
                        errors.append(_validation_error_with_reason_code(message='processing_behavior.recommendation.fallback_branch must reference a known scenario branch when decision=generate-alternatives', reason_code=REQ_045_REASON_CODE_ANALYSIS_SYNTHESIS_CONTRADICTION, evidence_refs=metadata_refs_for_diagnostics + [f"fallback_branch:{fallback_branch or 'missing'}"]))
                    elif fallback_branch == preferred_branch:
                        errors.append(_validation_error_with_reason_code(message='processing_behavior.recommendation.fallback_branch must differ from preferred_branch when decision=generate-alternatives', reason_code=REQ_045_REASON_CODE_ANALYSIS_SYNTHESIS_CONTRADICTION, evidence_refs=metadata_refs_for_diagnostics + [f'preferred_branch:{preferred_branch}', f'fallback_branch:{fallback_branch}']))
            if decision == 'single-path-sufficient' and (preferred_branch or fallback_branch):
                errors.append(_validation_error_with_reason_code(message='processing_behavior.recommendation.preferred_branch/fallback_branch must be empty when decision=single-path-sufficient', reason_code=REQ_045_REASON_CODE_ANALYSIS_SYNTHESIS_CONTRADICTION, evidence_refs=metadata_refs_for_diagnostics + [f"preferred_branch:{preferred_branch or 'none'}", f"fallback_branch:{fallback_branch or 'none'}"]))
        if isinstance(recommendation_evidence_refs, list):
            for row in scenarios:
                if not isinstance(row, Mapping):
                    continue
                scenario_id = _as_text(row.get('scenario_id'))
                scenario_evidence_refs = _collect_unique_refs(row.get('evidence_refs', []) if isinstance(row.get('evidence_refs'), list) else [])
                missing_scenario_citations = [ref for ref in scenario_evidence_refs if ref not in recommendation_evidence_set]
                if missing_scenario_citations:
                    errors.append(_validation_error_with_reason_code(message='processing_behavior.recommendation.evidence_refs must cite every strategic claim carried by alternative_strategic_scenario_generator.scenarios[].evidence_refs', reason_code=REQ_045_REASON_CODE_UNCITED_STRATEGIC_CLAIM_BLOCKED, evidence_refs=metadata_refs_for_diagnostics + [f'scenario:{scenario_id}'] + missing_scenario_citations))
        obligations = recommendation.get('obligations')
        obligation_ids: list[str] = []
        if not isinstance(obligations, list):
            errors.append('processing_behavior.recommendation.obligations must be a list')
            obligations = []
        for index, row in enumerate(obligations):
            if not isinstance(row, Mapping):
                errors.append(f'processing_behavior.recommendation.obligations[{index}] must be an object')
                continue
            obligation_id = row.get('obligation_id')
            scenario_id = row.get('scenario_id')
            summary = row.get('summary')
            trigger_ids = row.get('trigger_condition_ids')
            refs = row.get('evidence_refs')
            if not isinstance(obligation_id, str) or not obligation_id.strip():
                errors.append(f'processing_behavior.recommendation.obligations[{index}].obligation_id is required')
            else:
                obligation_ids.append(obligation_id)
            if not isinstance(scenario_id, str) or scenario_id not in scenario_ids:
                errors.append(f'processing_behavior.recommendation.obligations[{index}].scenario_id must reference a known scenario_id')
            if not isinstance(summary, str) or not summary.strip():
                errors.append(f'processing_behavior.recommendation.obligations[{index}].summary is required')
            if not isinstance(trigger_ids, list):
                errors.append(f'processing_behavior.recommendation.obligations[{index}].trigger_condition_ids must be a list')
            if not isinstance(refs, list) or not refs:
                errors.append(f'processing_behavior.recommendation.obligations[{index}].evidence_refs must be non-empty list')
            elif any((not isinstance(ref, str) or ref not in earth_sweep_ref_set for ref in refs)):
                errors.append(f'processing_behavior.recommendation.obligations[{index}].evidence_refs must be earth_sweep refs')
        if not earth_sweep_refs and obligations:
            errors.append('processing_behavior.recommendation.obligations must be empty when earth_sweep refs are missing')
        open_risks = recommendation.get('open_risks')
        open_risk_ids: list[str] = []
        if not isinstance(open_risks, list):
            errors.append('processing_behavior.recommendation.open_risks must be a list')
            open_risks = []
        for index, row in enumerate(open_risks):
            if not isinstance(row, Mapping):
                errors.append(f'processing_behavior.recommendation.open_risks[{index}] must be an object')
                continue
            risk_id = row.get('risk_id')
            scenario_id = row.get('scenario_id')
            reason_code = row.get('reason_code')
            summary = row.get('summary')
            refs = row.get('evidence_refs')
            if not isinstance(risk_id, str) or not risk_id.strip():
                errors.append(f'processing_behavior.recommendation.open_risks[{index}].risk_id is required')
            else:
                open_risk_ids.append(risk_id)
            if not isinstance(scenario_id, str) or scenario_id not in scenario_ids:
                errors.append(f'processing_behavior.recommendation.open_risks[{index}].scenario_id must reference a known scenario_id')
            if not isinstance(reason_code, str) or not reason_code.strip():
                errors.append(f'processing_behavior.recommendation.open_risks[{index}].reason_code is required')
            if not isinstance(summary, str) or not summary.strip():
                errors.append(f'processing_behavior.recommendation.open_risks[{index}].summary is required')
            if not isinstance(refs, list):
                errors.append(f'processing_behavior.recommendation.open_risks[{index}].evidence_refs must be a list')
        if not earth_sweep_refs:
            triggered = bool(contract.get('scenario_trigger', {}).get('triggered')) if isinstance(contract.get('scenario_trigger'), Mapping) else False
            if triggered and expected_cross_project_ids and (not open_risks):
                errors.append('processing_behavior.recommendation.open_risks must capture unresolved cross-project scenarios when earth_sweep refs are missing')
        if isinstance(context_usage, Mapping):
            if context_usage.get('cross_project_obligation_ids_used') != sorted(obligation_ids):
                errors.append('processing_behavior.context_usage.cross_project_obligation_ids_used must mirror recommendation obligations')
            if context_usage.get('cross_project_open_risk_ids') != sorted(open_risk_ids):
                errors.append('processing_behavior.context_usage.cross_project_open_risk_ids must mirror recommendation open_risks')
    metadata = payload.get('call_metadata')
    if not isinstance(metadata, Mapping):
        errors.append('call_metadata must be an object')
        return errors
    canonical_input = metadata.get('canonical_input')
    if not isinstance(canonical_input, Mapping):
        errors.append('call_metadata.canonical_input must be an object')
        return errors
    expected_canonical_input = _canonical_call_input(target_project_root=str(contract.get('target_project_root') or ''), earth_root=str(contract.get('earth_root') or ''), output_root=str(contract.get('output_root') or ''), revision_identity=str(contract.get('revision_identity') or ''), strategy_goal=str(contract.get('strategy_goal') or ''))
    if dict(canonical_input) != expected_canonical_input:
        errors.append('call_metadata.canonical_input must mirror normalized invocation anchors')
    expected_input_digest = _canonical_digest(expected_canonical_input)
    if metadata.get('canonical_input_sha256') != expected_input_digest:
        errors.append('call_metadata.canonical_input_sha256 does not match canonical input')
    if metadata.get('reproducible_call_id') != f'req045-{expected_input_digest[:16]}':
        errors.append('call_metadata.reproducible_call_id does not match canonical input digest')
    expected_processing_input = _canonical_processing_input(generated_at_utc=str(contract.get('generated_at_utc') or ''), uncertainty_score=float(contract.get('scenario_trigger', {}).get('uncertainty_score', 0.0)) if isinstance(contract.get('scenario_trigger'), Mapping) else 0.0, conflict_score=float(contract.get('scenario_trigger', {}).get('conflict_score', 0.0)) if isinstance(contract.get('scenario_trigger'), Mapping) else 0.0, uncertainty_signals=list(processing_behavior.get('context_inputs', {}).get('uncertainty_signals', []) if isinstance(processing_behavior.get('context_inputs'), Mapping) else []), conflict_signals=list(processing_behavior.get('context_inputs', {}).get('conflict_signals', []) if isinstance(processing_behavior.get('context_inputs'), Mapping) else []), target_project_evidence_refs=list(contract.get('evidence_refs', {}).get('target_project', []) if isinstance(contract.get('evidence_refs'), Mapping) else []), earth_sweep_evidence_refs=list(contract.get('evidence_refs', {}).get('earth_sweep', []) if isinstance(contract.get('evidence_refs'), Mapping) else []), scenario_candidates=[{'branch_key': str(row.get('branch_key') or ''), 'label': str(row.get('label') or ''), 'summary': str(row.get('summary') or ''), 'comparative_tradeoffs': list(row.get('comparative_tradeoffs', []) if isinstance(row, Mapping) else []), 'trigger_conditions': list(row.get('trigger_conditions', []) if isinstance(row, Mapping) else []), 'evidence_refs': list(row.get('evidence_refs', []) if isinstance(row, Mapping) else [])} for row in scenarios if isinstance(row, Mapping)])
    canonical_processing_input = metadata.get('canonical_processing_input')
    if not isinstance(canonical_processing_input, Mapping):
        errors.append('call_metadata.canonical_processing_input must be an object')
        return errors
    if dict(canonical_processing_input) != expected_processing_input:
        errors.append('call_metadata.canonical_processing_input must mirror normalized processing input')
    expected_processing_digest = _canonical_digest(expected_processing_input)
    if metadata.get('processing_input_sha256') != expected_processing_digest:
        errors.append('call_metadata.processing_input_sha256 does not match canonical processing input')
    if metadata.get('processing_call_id') != f'req045-processing-{expected_processing_digest[:16]}':
        errors.append('call_metadata.processing_call_id does not match canonical processing digest')
    return errors


_build_req_045_alternative_strategic_scenario_generator_rich = (
    build_req_045_alternative_strategic_scenario_generator
)


def build_req_045_alternative_strategic_scenario_generator_legacy_compat(*, generated_at_utc: str, target_project_root: str, earth_root: str, output_root: str, revision_identity: str, strategy_goal: str, uncertainty_score: Any, conflict_score: Any, scenario_candidates: Any, uncertainty_signals: Any, conflict_signals: Any, target_project_evidence_refs: Any, earth_sweep_evidence_refs: Any) -> dict[str, Any]:
    payload = _build_req_045_alternative_strategic_scenario_generator_rich(
        generated_at_utc=generated_at_utc,
        target_project_root=target_project_root,
        earth_root=earth_root,
        output_root=output_root,
        revision_identity=revision_identity,
        strategy_goal=strategy_goal,
        uncertainty_score=uncertainty_score,
        conflict_score=conflict_score,
        scenario_candidates=scenario_candidates,
        uncertainty_signals=uncertainty_signals,
        conflict_signals=conflict_signals,
        target_project_evidence_refs=target_project_evidence_refs,
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
    )
    metadata = dict(payload['call_metadata'])
    canonical_processing_input = dict(metadata['canonical_processing_input'])
    canonical_processing_input.pop('broad_sweep_context', None)
    processing_digest = _canonical_digest(canonical_processing_input)
    processing_behavior = dict(payload['processing_behavior'])
    context_usage = _require_mapping(processing_behavior.get('context_usage'), field_name='processing_behavior.context_usage')
    recommendation = _require_mapping(processing_behavior.get('recommendation'), field_name='processing_behavior.recommendation')
    processing_behavior['context_inputs'] = canonical_processing_input
    processing_behavior['context_usage'] = {
        'triggered': context_usage.get('triggered'),
        'scenario_ids_considered': context_usage.get('scenario_ids_considered'),
        'tradeoff_dimensions_used': context_usage.get('tradeoff_dimensions_used'),
        'trigger_condition_ids_used': context_usage.get('trigger_condition_ids_used'),
        'evidence_refs_used': context_usage.get('evidence_refs_used'),
    }
    processing_behavior['recommendation'] = {
        'decision': recommendation.get('decision'),
        'rationale': recommendation.get('rationale'),
        'confidence': recommendation.get('confidence'),
        'preferred_branch': recommendation.get('preferred_branch'),
        'fallback_branch': recommendation.get('fallback_branch'),
        'evidence_refs': recommendation.get('evidence_refs'),
    }
    metadata = {
        'reproducibility': metadata.get('reproducibility'),
        'canonical_input_sha256': metadata.get('canonical_input_sha256'),
        'reproducible_call_id': metadata.get('reproducible_call_id'),
        'canonical_input': metadata.get('canonical_input'),
        'processing_input_sha256': processing_digest,
        'processing_call_id': f'req045-processing-{processing_digest[:16]}',
        'canonical_processing_input': canonical_processing_input,
    }
    payload['processing_behavior'] = processing_behavior
    payload['call_metadata'] = metadata
    return payload


def validate_req_045_alternative_strategic_scenario_generator_legacy_compat(payload: Mapping[str, Any]) -> list[str]:
    if not isinstance(payload, Mapping):
        return ['payload must be a JSON object']
    try:
        metadata = _require_mapping(payload.get('call_metadata'), field_name='call_metadata')
        canonical_input = _require_mapping(metadata.get('canonical_input'), field_name='call_metadata.canonical_input')
        processing_behavior = _require_mapping(payload.get('processing_behavior'), field_name='processing_behavior')
        context_inputs = _require_mapping(
            processing_behavior.get('context_inputs'),
            field_name='processing_behavior.context_inputs',
        )
        expected = build_req_045_alternative_strategic_scenario_generator_legacy_compat(
            generated_at_utc=context_inputs.get('generated_at_utc'),
            target_project_root=canonical_input.get('target_project_root'),
            earth_root=canonical_input.get('earth_root'),
            output_root=canonical_input.get('output_root'),
            revision_identity=canonical_input.get('revision_identity'),
            strategy_goal=canonical_input.get('strategy_goal'),
            uncertainty_score=context_inputs.get('uncertainty_score'),
            conflict_score=context_inputs.get('conflict_score'),
            scenario_candidates=context_inputs.get('scenario_candidates'),
            uncertainty_signals=context_inputs.get('uncertainty_signals'),
            conflict_signals=context_inputs.get('conflict_signals'),
            target_project_evidence_refs=context_inputs.get('target_project_evidence_refs'),
            earth_sweep_evidence_refs=context_inputs.get('earth_sweep_evidence_refs'),
        )
    except ValueError as exc:
        return [str(exc)]
    if payload != expected:
        return ['payload must mirror deterministic REQ-045 alternative-strategic-scenario output']
    return []
