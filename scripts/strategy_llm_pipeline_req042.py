#!/usr/bin/env python3
'REQ-025/REQ-028/REQ-032/REQ-033/REQ-037/REQ-042 contract/data-model surfaces for strategy pipeline artifacts.'

from __future__ import annotations

import argparse

import hashlib

import json

import sys

import time

from datetime import datetime, timezone

from pathlib import Path

from typing import Any, Mapping, Sequence

REQ_025_LLM_CALL_TRACE_SCHEMA_VERSION = 'req-025.llm-call-trace-row.v1'

REQ_042_REQUIREMENT_ID = 'REQ-042'

REQ_042_SCHEMA_VERSION = 'req-042.existing-functionality-interaction-reasoning.v1'

RUNTIME_MODE = 'llm-first'

EXECUTION_MODE = 'long-thinking'

REQ_042_STRATEGY = 'existing-functionality-interaction-reasoning'

REQ_042_REASONING_FOCUS = 'existing-functionality consume-vs-build with compatibility and integration burden'

REQ_042_TRACE_FINAL_CALL_OBJECTIVE = 'Synthesize REQ-042 consume-vs-build recommendation from candidate compatibility checks, integration burden estimates, and cross-project integration obligations.'

REQ_042_TRACE_FINAL_EXPECTED_OUTPUT = 'existing_functionality_interaction_recommendation'

LLM_CALL_TRACE_RELATIVE_PATH = 'strategy/current/llm_call_trace.jsonl'

DEFAULT_TARGET_PROJECT_ROOT = '/workspace/projects/optimus-prime'

DEFAULT_EARTH_ROOT = '/workspace/projects/Earth'

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

def _normalize_level(raw_value: Any, *, field_name: str, allowed: set[str]) -> str:
    level = _as_text(raw_value).lower()
    if level not in allowed:
        allowed_text = '|'.join(sorted(allowed))
        raise ValueError(f'{field_name} must be one of {allowed_text}')
    return level

def _normalize_burden_level(raw_value: Any, *, field_name: str) -> str:
    return _normalize_level(raw_value, field_name=field_name, allowed={'low', 'medium', 'high'})

def _normalize_req_042_capability_need(raw_value: Any) -> dict[str, Any]:
    capability_need = _require_mapping(raw_value, field_name='capability_need')
    return {'capability_id': _require_text(capability_need.get('capability_id'), field_name='capability_need.capability_id'), 'intent': _require_text(capability_need.get('intent'), field_name='capability_need.intent'), 'required_interfaces': _normalize_string_list(capability_need.get('required_interfaces'), field_name='capability_need.required_interfaces')}

def _normalize_req_042_build_new_assessment(raw_value: Any) -> dict[str, Any]:
    assessment = _require_mapping(raw_value, field_name='build_new_assessment')
    return {'summary': _require_text(assessment.get('summary'), field_name='build_new_assessment.summary'), 'estimated_burden': _normalize_burden_level(assessment.get('estimated_burden'), field_name='build_new_assessment.estimated_burden'), 'rationale': _require_text(assessment.get('rationale'), field_name='build_new_assessment.rationale'), 'evidence_refs': _normalize_string_list(assessment.get('evidence_refs'), field_name='build_new_assessment.evidence_refs', min_items=1)}

def _normalize_req_042_compatibility_checks(raw_value: Any, *, field_name: str) -> list[dict[str, str]]:
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError(f'{field_name} must be an array')
    normalized: list[dict[str, str]] = []
    seen_check_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f'{field_name}[{index}] must be an object')
        check_id = _require_text(item.get('check_id'), field_name=f'{field_name}[{index}].check_id')
        if check_id in seen_check_ids:
            raise ValueError(f'{field_name}[{index}].check_id duplicates {check_id}')
        seen_check_ids.add(check_id)
        normalized.append({'check_id': check_id, 'requirement': _require_text(item.get('requirement'), field_name=f'{field_name}[{index}].requirement'), 'status': _normalize_level(item.get('status'), field_name=f'{field_name}[{index}].status', allowed={'fail', 'pass', 'unknown'}), 'detail': _require_text(item.get('detail'), field_name=f'{field_name}[{index}].detail')})
    if not normalized:
        raise ValueError(f'{field_name} must contain at least 1 item(s)')
    normalized.sort(key=lambda row: row['check_id'])
    return normalized

def _normalize_req_042_integration_burden(raw_value: Any, *, field_name: str) -> dict[str, Any]:
    burden = _require_mapping(raw_value, field_name=field_name)
    return {'estimate_level': _normalize_burden_level(burden.get('estimate_level'), field_name=f'{field_name}.estimate_level'), 'drivers': _normalize_string_list(burden.get('drivers'), field_name=f'{field_name}.drivers', min_items=1), 'rationale': _require_text(burden.get('rationale'), field_name=f'{field_name}.rationale')}

def _normalize_req_042_existing_functionality_candidates(raw_value: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError('existing_functionality_candidates must be an array')
    normalized: list[dict[str, Any]] = []
    seen_candidate_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f'existing_functionality_candidates[{index}] must be an object')
        candidate_id = _require_text(item.get('candidate_id'), field_name=f'existing_functionality_candidates[{index}].candidate_id') if item.get('candidate_id') is not None else f'candidate-{index + 1:02d}'
        if candidate_id in seen_candidate_ids:
            raise ValueError(f'existing_functionality_candidates[{index}].candidate_id duplicates {candidate_id}')
        seen_candidate_ids.add(candidate_id)
        normalized.append({'candidate_id': candidate_id, 'source_project_id': _require_text(item.get('source_project_id'), field_name=f'existing_functionality_candidates[{index}].source_project_id'), 'capability_id': _require_text(item.get('capability_id'), field_name=f'existing_functionality_candidates[{index}].capability_id'), 'functionality_summary': _require_text(item.get('functionality_summary'), field_name=f'existing_functionality_candidates[{index}].functionality_summary'), 'provided_interfaces': _normalize_string_list(item.get('provided_interfaces'), field_name=f'existing_functionality_candidates[{index}].provided_interfaces'), 'compatibility_checks': _normalize_req_042_compatibility_checks(item.get('compatibility_checks'), field_name=f'existing_functionality_candidates[{index}].compatibility_checks'), 'integration_burden': _normalize_req_042_integration_burden(item.get('integration_burden'), field_name=f'existing_functionality_candidates[{index}].integration_burden'), 'evidence_refs': _normalize_string_list(item.get('evidence_refs'), field_name=f'existing_functionality_candidates[{index}].evidence_refs', min_items=1)})
    if not normalized:
        raise ValueError('existing_functionality_candidates must contain at least 1 item(s)')
    normalized.sort(key=lambda row: (row['candidate_id'], row['source_project_id']))
    return normalized

def _req_042_burden_rank(level: str) -> int:
    return {'low': 1, 'medium': 2, 'high': 3}[level]

def _build_req_042_reasoning_rows(*, capability_need: Mapping[str, Any], build_new_assessment: Mapping[str, Any], existing_functionality_candidates: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    build_new_burden = _require_text(build_new_assessment.get('estimated_burden'), field_name='build_new_assessment.estimated_burden')
    required_interfaces = list(_normalize_string_list(capability_need.get('required_interfaces'), field_name='capability_need.required_interfaces'))
    reasoning_rows: list[dict[str, Any]] = []
    compatible_candidates: list[dict[str, Any]] = []
    needs_followup_candidates: list[dict[str, Any]] = []
    incompatible_candidates: list[dict[str, Any]] = []
    for candidate in existing_functionality_candidates:
        provided_interfaces = list(candidate['provided_interfaces'])
        missing_interfaces = sorted(set(required_interfaces) - set(provided_interfaces))
        check_statuses = {row['status'] for row in candidate['compatibility_checks']}
        if missing_interfaces or 'fail' in check_statuses:
            compatibility_state = 'incompatible'
        elif 'unknown' in check_statuses:
            compatibility_state = 'needs_followup'
        else:
            compatibility_state = 'compatible'
        integration_burden = dict(candidate['integration_burden'])
        candidate_decision, decision_rationale = _build_req_042_candidate_decision_rationale(compatibility_state=compatibility_state, candidate_burden=integration_burden['estimate_level'], build_new_burden=build_new_burden, missing_interfaces=missing_interfaces)
        reasoning_row = {'candidate_id': candidate['candidate_id'], 'source_project_id': candidate['source_project_id'], 'capability_id': candidate['capability_id'], 'functionality_summary': candidate['functionality_summary'], 'required_interfaces': required_interfaces, 'provided_interfaces': provided_interfaces, 'missing_interfaces': missing_interfaces, 'compatibility_state': compatibility_state, 'compatibility_checks': list(candidate['compatibility_checks']), 'integration_burden': integration_burden, 'candidate_decision': candidate_decision, 'decision_rationale': decision_rationale, 'evidence_refs': list(candidate['evidence_refs'])}
        reasoning_rows.append(reasoning_row)
        if compatibility_state == 'compatible':
            compatible_candidates.append(reasoning_row)
        elif compatibility_state == 'needs_followup':
            needs_followup_candidates.append(reasoning_row)
        else:
            incompatible_candidates.append(reasoning_row)
    reasoning_rows.sort(key=lambda row: (row['candidate_id'], row['source_project_id']))
    compatible_candidates.sort(key=lambda row: (_req_042_burden_rank(row['integration_burden']['estimate_level']), row['candidate_id'], row['source_project_id']))
    needs_followup_candidates.sort(key=lambda row: (row['candidate_id'], row['source_project_id']))
    incompatible_candidates.sort(key=lambda row: (row['candidate_id'], row['source_project_id']))
    return (reasoning_rows, compatible_candidates, needs_followup_candidates, incompatible_candidates)

def _build_req_042_candidate_decision_rationale(*, compatibility_state: str, candidate_burden: str, build_new_burden: str, missing_interfaces: Sequence[str]) -> tuple[str, str]:
    if compatibility_state == 'incompatible':
        if missing_interfaces:
            return ('reject_existing_functionality', 'Reject this existing functionality because it misses required interfaces for the requested capability.')
        return ('reject_existing_functionality', 'Reject this existing functionality because at least one compatibility check failed.')
    if compatibility_state == 'needs_followup':
        return ('investigate_existing_functionality', 'Investigate this existing functionality further because compatibility checks remain unresolved.')
    if _req_042_burden_rank(candidate_burden) <= _req_042_burden_rank(build_new_burden):
        return ('consume_existing_functionality', 'Consume this existing functionality because compatibility checks passed and integration burden is not higher than building new capability.')
    return ('build_new_capability', 'Build new capability instead because the compatible integration burden is higher than the new-build estimate.')

def _build_req_042_selected_path(*, compatible_candidates: Sequence[Mapping[str, Any]], needs_followup_candidates: Sequence[Mapping[str, Any]], build_new_burden: str) -> dict[str, Any]:
    if compatible_candidates and compatible_candidates[0]['candidate_decision'] == 'consume_existing_functionality':
        selected_candidate = compatible_candidates[0]
        return {'decision': 'consume_existing_functionality', 'selected_candidate_id': selected_candidate['candidate_id'], 'rationale': f"Use {selected_candidate['candidate_id']} because it is compatible and its {selected_candidate['integration_burden']['estimate_level']} integration burden is not higher than the {build_new_burden} new-build estimate."}
    if compatible_candidates:
        selected_candidate = compatible_candidates[0]
        return {'decision': 'build_new_capability', 'selected_candidate_id': None, 'rationale': f"Build new capability because the best compatible option, {selected_candidate['candidate_id']}, still carries {selected_candidate['integration_burden']['estimate_level']} integration burden versus {build_new_burden} for new work."}
    if needs_followup_candidates:
        return {'decision': 'investigate_existing_functionality', 'selected_candidate_id': None, 'rationale': 'Investigate existing functionality first because no reviewed candidate is fully compatible and at least one candidate only has unresolved compatibility checks.'}
    return {'decision': 'build_new_capability', 'selected_candidate_id': None, 'rationale': 'Build new capability because every reviewed existing-functionality candidate failed compatibility checks or missed required interfaces.'}

def _req_042_recommendation_confidence(*, decision: str, evidence_refs: Sequence[str], open_risks: Sequence[Mapping[str, Any]]) -> str:
    if not evidence_refs:
        return 'low'
    if open_risks:
        return 'medium'
    if decision in {'consume_existing_functionality', 'build_new_capability'}:
        return 'high'
    return 'medium'

def _req_042_recommendation_rationale(*, decision: str, selected_path: Mapping[str, Any], open_risks: Sequence[Mapping[str, Any]]) -> str:
    reason_codes = {_as_text(row.get('reason_code')) for row in open_risks}
    if {'cross_call_contradiction', 'uncited_strategic_claim'}.intersection(reason_codes):
        return 'Cross-call contradictions or uncited strategic claims block promotion until citation-complete claims align across analysis and synthesis outputs.'
    if decision == 'consume_existing_functionality':
        return 'Evidence-backed compatibility and integration burden reasoning support consuming existing functionality.'
    if decision == 'build_new_capability':
        return 'Compatibility and integration burden reasoning support building new capability instead of reuse.'
    if open_risks:
        return 'Cross-project reuse remains plausible, but Earth-sweep evidence is still missing and must stay as an open risk.'
    return _require_text(selected_path.get('rationale'), field_name='selected_path.rationale')

def _build_req_042_processing_behavior(*, target_project_root: str, earth_root: str, active_project_id: str, capability_need: Mapping[str, Any], build_new_assessment: Mapping[str, Any], target_project_evidence_refs: list[str], earth_sweep_evidence_refs: list[str], cross_project_context: list[dict[str, Any]], existing_functionality_candidates: list[dict[str, Any]], reasoning_rows: list[dict[str, Any]], selected_path: Mapping[str, Any], strategic_claims: list[dict[str, Any]] | None=None) -> tuple[dict[str, Any], dict[str, Any]]:
    cross_project_refs = _collect_unique_refs(*[row['evidence_refs'] for row in cross_project_context])
    cross_project_context_by_project = {row['project_id']: row for row in cross_project_context}
    normalized_strategic_claims = list(strategic_claims or [])
    compatible_candidate_ids = [row['candidate_id'] for row in reasoning_rows if row['compatibility_state'] == 'compatible']
    needs_followup_candidate_ids = [row['candidate_id'] for row in reasoning_rows if row['compatibility_state'] == 'needs_followup']
    incompatible_candidate_ids = [row['candidate_id'] for row in reasoning_rows if row['compatibility_state'] == 'incompatible']
    reuse_candidates = [{'candidate_id': row['candidate_id'], 'source_project_id': row['source_project_id'], 'compatibility_state': row['compatibility_state'], 'candidate_decision': row['candidate_decision'], 'integration_burden': dict(row['integration_burden']), 'evidence_refs': list(row['evidence_refs'])} for row in reasoning_rows]
    recommendation_selected_path = {'decision': _require_text(selected_path.get('decision'), field_name='selected_path.decision'), 'selected_candidate_id': selected_path.get('selected_candidate_id'), 'rationale': _require_text(selected_path.get('rationale'), field_name='selected_path.rationale')}
    selected_candidate_id = _as_text(recommendation_selected_path.get('selected_candidate_id'))
    selected_candidate = next((row for row in reasoning_rows if row['candidate_id'] == selected_candidate_id), None)
    cross_project_obligations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    available_citation_refs = set(_collect_unique_refs(target_project_evidence_refs, build_new_assessment['evidence_refs'], earth_sweep_evidence_refs, cross_project_refs, *[row['evidence_refs'] for row in reasoning_rows]))
    claim_rows_by_id: dict[str, list[dict[str, Any]]] = {}
    for claim in normalized_strategic_claims:
        claim_rows_by_id.setdefault(claim['claim_id'], []).append(claim)
        citation_refs = list(claim['evidence_refs'])
        if not citation_refs or not set(citation_refs).issubset(available_citation_refs):
            open_risks.append({'risk_id': f"risk-claim-{claim['claim_id']}-citation", 'summary': claim['summary'], 'reason_code': 'uncited_strategic_claim', 'required_evidence_refs': _collect_unique_refs([claim['source_output_ref']], citation_refs)})
    for claim_id, claim_rows in claim_rows_by_id.items():
        analysis_rows = [row for row in claim_rows if row['phase'] == 'analysis']
        synthesis_rows = [row for row in claim_rows if row['phase'] == 'synthesis']
        contradiction_row: dict[str, Any] | None = None
        for analysis_row in analysis_rows:
            for synthesis_row in synthesis_rows:
                if analysis_row['position'] == synthesis_row['position']:
                    continue
                contradiction_row = {'summary': synthesis_row['summary'], 'required_evidence_refs': _collect_unique_refs([analysis_row['source_output_ref']], [synthesis_row['source_output_ref']], analysis_row['evidence_refs'], synthesis_row['evidence_refs'])}
                break
            if contradiction_row is not None:
                break
        if contradiction_row is not None:
            open_risks.append({'risk_id': f'risk-claim-{claim_id}-contradiction', 'summary': contradiction_row['summary'], 'reason_code': 'cross_call_contradiction', 'required_evidence_refs': contradiction_row['required_evidence_refs']})
    if selected_candidate is not None and selected_candidate['source_project_id'] != active_project_id:
        project_context = cross_project_context_by_project.get(selected_candidate['source_project_id'])
        candidate_earth_refs = [ref for ref in selected_candidate['evidence_refs'] if _is_earth_evidence_ref(ref)]
        project_specific_earth_refs = [ref for ref in earth_sweep_evidence_refs if selected_candidate['source_project_id'] in ref]
        available_earth_refs = _collect_unique_refs(project_specific_earth_refs, project_context['evidence_refs'] if project_context is not None else [], candidate_earth_refs)
        if available_earth_refs:
            cross_project_obligations.append({'obligation_id': f"obligation-{selected_candidate['candidate_id']}", 'project_id': selected_candidate['source_project_id'], 'candidate_id': selected_candidate['candidate_id'], 'summary': f"Coordinate reuse of {selected_candidate['candidate_id']} before promoting {capability_need['capability_id']} into execution.", 'evidence_refs': _collect_unique_refs(target_project_evidence_refs, available_earth_refs, selected_candidate['evidence_refs'])})
        else:
            recommendation_selected_path = {'decision': 'investigate_existing_functionality', 'selected_candidate_id': None, 'rationale': f"{selected_candidate['candidate_id']} is technically compatible, but cross-project reuse cannot be promoted until Earth-sweep evidence is attached for {selected_candidate['source_project_id']}."}
            open_risks.append({'risk_id': f"risk-{selected_candidate['candidate_id']}", 'summary': f"Cross-project reuse candidate {selected_candidate['candidate_id']} is missing Earth-sweep evidence needed for promotion.", 'reason_code': 'missing_earth_sweep_evidence_refs', 'project_id': selected_candidate['source_project_id'], 'candidate_id': selected_candidate['candidate_id'], 'required_evidence_refs': _collect_unique_refs(target_project_evidence_refs, selected_candidate['evidence_refs'])})
    reason_codes = {_as_text(row.get('reason_code')) for row in open_risks}
    if {'cross_call_contradiction', 'uncited_strategic_claim'}.intersection(reason_codes):
        recommendation_selected_path = {'decision': 'investigate_existing_functionality', 'selected_candidate_id': None, 'rationale': 'Strategic claim contradictions or citation gaps must be resolved before consume-vs-build promotion can proceed.'}
        cross_project_obligations = []
    cross_project_obligations.sort(key=lambda row: row['obligation_id'])
    open_risks.sort(key=lambda row: row['risk_id'])
    evidence_refs_used = _collect_unique_refs(target_project_evidence_refs, build_new_assessment['evidence_refs'], earth_sweep_evidence_refs, cross_project_refs, *[row['evidence_refs'] for row in reasoning_rows], *[row['evidence_refs'] for row in cross_project_obligations], *[row['required_evidence_refs'] for row in open_risks])
    recommendation_refs = _collect_unique_refs(target_project_evidence_refs, build_new_assessment['evidence_refs'], earth_sweep_evidence_refs, cross_project_refs, *[row['evidence_refs'] for row in reuse_candidates], *[row['evidence_refs'] for row in cross_project_obligations], *[row['required_evidence_refs'] for row in open_risks])
    recommendation_decision = _require_text(recommendation_selected_path.get('decision'), field_name='processing_behavior.recommendation.selected_path.decision')
    context_inputs: dict[str, Any] = {'target_project': {'project_root': target_project_root, 'active_project_id': active_project_id, 'capability_id': capability_need['capability_id'], 'intent': capability_need['intent'], 'evidence_refs': list(target_project_evidence_refs)}, 'build_new_assessment': dict(build_new_assessment), 'earth_sweep': {'earth_root': earth_root, 'evidence_refs': list(earth_sweep_evidence_refs)}, 'cross_project_context': [{'project_id': row['project_id'], 'project_root': row['project_root'], 'evidence_refs': list(row['evidence_refs']), 'context_note': row['context_note']} for row in cross_project_context], 'existing_functionality_candidates': [{'candidate_id': row['candidate_id'], 'source_project_id': row['source_project_id'], 'capability_id': row['capability_id'], 'functionality_summary': row['functionality_summary'], 'provided_interfaces': list(row['provided_interfaces']), 'compatibility_checks': list(row['compatibility_checks']), 'integration_burden': dict(row['integration_burden']), 'evidence_refs': list(row['evidence_refs'])} for row in existing_functionality_candidates]}
    if normalized_strategic_claims:
        context_inputs['strategic_claims'] = [{'claim_id': row['claim_id'], 'phase': row['phase'], 'summary': row['summary'], 'position': row['position'], 'source_output_ref': row['source_output_ref'], 'evidence_refs': list(row['evidence_refs'])} for row in normalized_strategic_claims]
    return ({'strategy': REQ_042_STRATEGY, 'reasoning_mode': EXECUTION_MODE, 'strict_evidence_discipline': True, 'heuristic_summarization_only': False, 'context_inputs': context_inputs, 'context_usage': {'target_project_context_used': bool(target_project_evidence_refs or build_new_assessment['evidence_refs']), 'earth_sweep_context_used': bool(earth_sweep_evidence_refs), 'cross_project_context_used': bool(cross_project_context), 'candidate_ids_considered': [row['candidate_id'] for row in reasoning_rows], 'compatible_candidate_ids': compatible_candidate_ids, 'needs_followup_candidate_ids': needs_followup_candidate_ids, 'incompatible_candidate_ids': incompatible_candidate_ids, 'cross_project_projects_considered': [row['project_id'] for row in cross_project_context], 'cross_project_refs_used': cross_project_refs, 'evidence_refs_used': evidence_refs_used}, 'existing_functionality_reasoning': {'reasoning_focus': REQ_042_REASONING_FOCUS, 'candidate_assessments': reasoning_rows, 'reviewed_candidate_count': len(reasoning_rows), 'compatible_count': len(compatible_candidate_ids), 'needs_followup_count': len(needs_followup_candidate_ids), 'incompatible_count': len(incompatible_candidate_ids), 'selected_candidate_id': recommendation_selected_path.get('selected_candidate_id')}, 'recommendation': {'decision': recommendation_decision, 'rationale': _req_042_recommendation_rationale(decision=recommendation_decision, selected_path=recommendation_selected_path, open_risks=open_risks), 'confidence': _req_042_recommendation_confidence(decision=recommendation_decision, evidence_refs=recommendation_refs, open_risks=open_risks), 'evidence_refs': recommendation_refs, 'selected_path': recommendation_selected_path, 'reuse_candidates': reuse_candidates, 'cross_project_obligations': cross_project_obligations, 'open_risks': open_risks}, 'summary': f'REQ-042 reviewed {len(reasoning_rows)} candidate(s) and selected {recommendation_decision} with {len(cross_project_obligations)} cross-project obligation(s) and {len(open_risks)} open risk(s).'}, recommendation_selected_path)

def _canonical_req_042_input(*, target_project_root: str, earth_root: str, active_project_id: str, capability_need: Mapping[str, Any], build_new_assessment: Mapping[str, Any], evaluated_at: str) -> dict[str, Any]:
    return {'runtime_mode': RUNTIME_MODE, 'execution_mode': EXECUTION_MODE, 'target_project_root': target_project_root, 'earth_root': earth_root, 'active_project_id': active_project_id, 'capability_need': {'capability_id': capability_need['capability_id'], 'intent': capability_need['intent'], 'required_interfaces': list(capability_need['required_interfaces'])}, 'build_new_assessment': {'summary': build_new_assessment['summary'], 'estimated_burden': build_new_assessment['estimated_burden'], 'rationale': build_new_assessment['rationale'], 'evidence_refs': list(build_new_assessment['evidence_refs'])}, 'evaluated_at': evaluated_at}

def _canonical_req_042_processing_input(*, target_project_evidence_refs: Sequence[str], earth_sweep_evidence_refs: Sequence[str], cross_project_context: Sequence[Mapping[str, Any]], capability_need: Mapping[str, Any], build_new_assessment: Mapping[str, Any], existing_functionality_candidates: Sequence[Mapping[str, Any]], strategic_claims: Sequence[Mapping[str, Any]] | None=None) -> dict[str, Any]:
    canonical_processing_input: dict[str, Any] = {'required_evidence_refs': _collect_unique_refs(target_project_evidence_refs, build_new_assessment['evidence_refs'], earth_sweep_evidence_refs, *[row['evidence_refs'] for row in cross_project_context], *[row['evidence_refs'] for row in existing_functionality_candidates]), 'target_project_evidence_refs': list(target_project_evidence_refs), 'earth_sweep_evidence_refs': list(earth_sweep_evidence_refs), 'cross_project_context': [{'project_id': row['project_id'], 'project_root': row['project_root'], 'evidence_refs': list(row['evidence_refs']), 'context_note': row['context_note']} for row in cross_project_context], 'capability_need': {'capability_id': capability_need['capability_id'], 'intent': capability_need['intent'], 'required_interfaces': list(capability_need['required_interfaces'])}, 'build_new_assessment': {'summary': build_new_assessment['summary'], 'estimated_burden': build_new_assessment['estimated_burden'], 'rationale': build_new_assessment['rationale'], 'evidence_refs': list(build_new_assessment['evidence_refs'])}, 'existing_functionality_candidates': [{'candidate_id': row['candidate_id'], 'source_project_id': row['source_project_id'], 'capability_id': row['capability_id'], 'functionality_summary': row['functionality_summary'], 'provided_interfaces': list(row['provided_interfaces']), 'compatibility_checks': list(row['compatibility_checks']), 'integration_burden': dict(row['integration_burden']), 'evidence_refs': list(row['evidence_refs'])} for row in existing_functionality_candidates]}
    if strategic_claims:
        canonical_processing_input['strategic_claims'] = [{'claim_id': _require_text(row.get('claim_id'), field_name='strategic_claims[].claim_id'), 'phase': _require_text(row.get('phase'), field_name='strategic_claims[].phase'), 'summary': _require_text(row.get('summary'), field_name='strategic_claims[].summary'), 'position': _require_text(row.get('position'), field_name='strategic_claims[].position'), 'source_output_ref': _require_text(row.get('source_output_ref'), field_name='strategic_claims[].source_output_ref'), 'evidence_refs': _normalize_string_list(row.get('evidence_refs'), field_name='strategic_claims[].evidence_refs')} for row in strategic_claims]
    return canonical_processing_input

def _build_req_042_trace_call_id(*, canonical_input_sha: str, processing_input_sha: str, sequence: int, call_kind: str, call_subject: str) -> str:
    material = '|'.join([canonical_input_sha, processing_input_sha, str(sequence), call_kind, call_subject])
    digest = hashlib.sha256(material.encode('utf-8')).hexdigest()[:10]
    return f'req042-call-{sequence:02d}-{digest}'

def _build_req_042_trace_expected_output(*, candidate_id: str) -> str:
    return f'candidate_interaction_assessment_{_slug_id_fragment(candidate_id)}'

def _build_req_042_llm_call_trace_rows(*, canonical_input_sha: str, processing_input_sha: str, processing_call_id: str, canonical_processing_input: Mapping[str, Any], reasoning_rows: Sequence[Mapping[str, Any]], selected_path: Mapping[str, Any], recommendation: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    plan_id = f'req042-plan-{processing_input_sha[:16]}'
    target_project_evidence_refs = _normalize_string_list(canonical_processing_input.get('target_project_evidence_refs'), field_name='canonical_processing_input.target_project_evidence_refs')
    earth_sweep_evidence_refs = _normalize_string_list(canonical_processing_input.get('earth_sweep_evidence_refs'), field_name='canonical_processing_input.earth_sweep_evidence_refs')
    cross_project_context = _normalize_cross_project_context(canonical_processing_input.get('cross_project_context'))
    build_new_assessment = _normalize_req_042_build_new_assessment(canonical_processing_input.get('build_new_assessment'))
    shared_input_refs = _collect_unique_refs(target_project_evidence_refs, build_new_assessment['evidence_refs'], earth_sweep_evidence_refs, *[row['evidence_refs'] for row in cross_project_context])
    selected_decision = _require_text(selected_path.get('decision'), field_name='selected_path.decision')
    selected_candidate_id = _as_text(selected_path.get('selected_candidate_id'))
    call_specs: list[dict[str, Any]] = []
    for sequence, row in enumerate(reasoning_rows, start=1):
        candidate_id = _require_text(row.get('candidate_id'), field_name='interaction_reasoning[].candidate_id')
        source_project_id = _require_text(row.get('source_project_id'), field_name=f'interaction_reasoning[{sequence - 1}].source_project_id')
        compatibility_state = _require_text(row.get('compatibility_state'), field_name=f'interaction_reasoning[{sequence - 1}].compatibility_state')
        integration_burden = _require_mapping(row.get('integration_burden'), field_name=f'interaction_reasoning[{sequence - 1}].integration_burden')
        burden_level = _normalize_burden_level(integration_burden.get('estimate_level'), field_name=f'interaction_reasoning[{sequence - 1}].integration_burden.estimate_level')
        candidate_evidence_refs = _normalize_string_list(row.get('evidence_refs'), field_name=f'interaction_reasoning[{sequence - 1}].evidence_refs', min_items=1)
        call_id = _build_req_042_trace_call_id(canonical_input_sha=canonical_input_sha, processing_input_sha=processing_input_sha, sequence=sequence, call_kind='candidate-assessment', call_subject=f'{candidate_id}|{source_project_id}')
        expected_output = _build_req_042_trace_expected_output(candidate_id=candidate_id)
        output_ref = _build_call_output_ref(plan_id=plan_id, call_id=call_id, expected_output=expected_output)
        call_specs.append({'sequence': sequence, 'call_id': call_id, 'candidate_id': candidate_id, 'source_project_id': source_project_id, 'compatibility_state': compatibility_state, 'burden_level': burden_level, 'expected_output': expected_output, 'output_ref': output_ref, 'evidence_refs': candidate_evidence_refs})
    final_sequence = len(call_specs) + 1
    final_call_id = _build_req_042_trace_call_id(canonical_input_sha=canonical_input_sha, processing_input_sha=processing_input_sha, sequence=final_sequence, call_kind='recommendation-synthesis', call_subject=f"{selected_decision}|{selected_candidate_id or 'none'}")
    final_output_ref = _build_call_output_ref(plan_id=plan_id, call_id=final_call_id, expected_output=REQ_042_TRACE_FINAL_EXPECTED_OUTPUT)
    trace_rows: list[dict[str, Any]] = []
    for spec in call_specs:
        input_refs = _collect_unique_refs(shared_input_refs, spec['evidence_refs'])
        trace_rows.append({'schema_version': REQ_025_LLM_CALL_TRACE_SCHEMA_VERSION, 'requirement_id': REQ_042_REQUIREMENT_ID, 'plan_id': plan_id, 'processing_call_id': processing_call_id, 'call_id': spec['call_id'], 'sequence': spec['sequence'], 'call_objective': f"Assess existing functionality candidate {spec['candidate_id']} from {spec['source_project_id']} for consume-vs-build reasoning using compatibility checks and integration burden estimates.", 'depends_on': [], 'expected_output': spec['expected_output'], 'input_refs': input_refs, 'output_refs': [spec['output_ref']], 'handoff_summary': f"Call {spec['sequence']} hands off {spec['expected_output']} via {spec['output_ref']} to {final_call_id} after assessing {spec['candidate_id']} as {spec['compatibility_state']} with {spec['burden_level']} integration burden from {len(input_refs)} input refs."})
    recommendation_refs: list[str] = []
    recommendation_open_risks: Sequence[Any] = []
    if isinstance(recommendation, Mapping):
        recommendation_refs = _normalize_string_list(recommendation.get('evidence_refs'), field_name='processing_behavior.recommendation.evidence_refs')
        recommendation_open_risks_raw = recommendation.get('open_risks')
        if isinstance(recommendation_open_risks_raw, Sequence) and (not isinstance(recommendation_open_risks_raw, (str, bytes, bytearray))):
            recommendation_open_risks = recommendation_open_risks_raw
    final_input_refs = _collect_unique_refs(shared_input_refs, recommendation_refs, *[spec['evidence_refs'] for spec in call_specs], [spec['output_ref'] for spec in call_specs])
    trace_rows.append({'schema_version': REQ_025_LLM_CALL_TRACE_SCHEMA_VERSION, 'requirement_id': REQ_042_REQUIREMENT_ID, 'plan_id': plan_id, 'processing_call_id': processing_call_id, 'call_id': final_call_id, 'sequence': final_sequence, 'call_objective': REQ_042_TRACE_FINAL_CALL_OBJECTIVE, 'depends_on': [spec['call_id'] for spec in call_specs], 'expected_output': REQ_042_TRACE_FINAL_EXPECTED_OUTPUT, 'input_refs': final_input_refs, 'output_refs': [final_output_ref], 'handoff_summary': f'Call {final_sequence} hands off {REQ_042_TRACE_FINAL_EXPECTED_OUTPUT} via {final_output_ref} as the terminal REQ-042 output with decision {selected_decision} and {len(recommendation_open_risks)} open risk(s) after consolidating {len(call_specs)} candidate assessment output(s).'})
    return trace_rows

def build_req_042_existing_functionality_interaction_reasoning(*, target_project_root: str=DEFAULT_TARGET_PROJECT_ROOT, earth_root: str=DEFAULT_EARTH_ROOT, active_project_id: Any, capability_need: Mapping[str, Any] | None, build_new_assessment: Mapping[str, Any] | None, existing_functionality_candidates: Sequence[Mapping[str, Any]] | None, target_project_evidence_refs: Sequence[Any] | None=None, earth_sweep_evidence_refs: Sequence[Any] | None=None, cross_project_context: Sequence[Mapping[str, Any]] | None=None, strategic_claims: Sequence[Mapping[str, Any]] | None=None, evaluated_at: str | None=None) -> dict[str, Any]:
    """Build the REQ-042 existing-functionality interaction reasoning surface."""
    normalized_target_root = _normalize_root(target_project_root, field_name='target_project_root')
    normalized_earth_root = _normalize_root(earth_root, field_name='earth_root')
    normalized_active_project_id = _require_text(active_project_id, field_name='active_project_id')
    normalized_capability_need = _normalize_req_042_capability_need(capability_need)
    normalized_build_new_assessment = _normalize_req_042_build_new_assessment(build_new_assessment)
    normalized_candidates = _normalize_req_042_existing_functionality_candidates(existing_functionality_candidates)
    normalized_strategic_claims = _normalize_req_028_strategic_claims(strategic_claims)
    normalized_target_project_evidence_refs = _normalize_string_list(target_project_evidence_refs, field_name='target_project_evidence_refs') if target_project_evidence_refs is not None else list(normalized_build_new_assessment['evidence_refs'])
    normalized_cross_project_context = _normalize_cross_project_context(cross_project_context)
    derived_earth_refs = _collect_unique_refs(*[row['evidence_refs'] for row in normalized_cross_project_context], *[[ref for ref in candidate['evidence_refs'] if _is_earth_evidence_ref(ref)] for candidate in normalized_candidates])
    normalized_earth_sweep_evidence_refs = _normalize_string_list(earth_sweep_evidence_refs, field_name='earth_sweep_evidence_refs') if earth_sweep_evidence_refs is not None else derived_earth_refs
    normalized_evaluated_at = _require_text(evaluated_at if evaluated_at is not None else utc_now_iso(), field_name='evaluated_at')
    canonical_input = _canonical_req_042_input(target_project_root=normalized_target_root, earth_root=normalized_earth_root, active_project_id=normalized_active_project_id, capability_need=normalized_capability_need, build_new_assessment=normalized_build_new_assessment, evaluated_at=normalized_evaluated_at)
    canonical_input_sha = _canonical_digest(canonical_input)
    canonical_processing_input = _canonical_req_042_processing_input(target_project_evidence_refs=normalized_target_project_evidence_refs, earth_sweep_evidence_refs=normalized_earth_sweep_evidence_refs, cross_project_context=normalized_cross_project_context, capability_need=normalized_capability_need, build_new_assessment=normalized_build_new_assessment, existing_functionality_candidates=normalized_candidates, strategic_claims=normalized_strategic_claims)
    processing_sha = _canonical_digest(canonical_processing_input)
    processing_call_id = f'req042-processing-{processing_sha[:16]}'
    build_new_burden = normalized_build_new_assessment['estimated_burden']
    reasoning_rows, compatible_candidates, needs_followup_candidates, incompatible_candidates = _build_req_042_reasoning_rows(capability_need=normalized_capability_need, build_new_assessment=normalized_build_new_assessment, existing_functionality_candidates=normalized_candidates)
    selected_path = _build_req_042_selected_path(compatible_candidates=compatible_candidates, needs_followup_candidates=needs_followup_candidates, build_new_burden=build_new_burden)
    processing_behavior, finalized_selected_path = _build_req_042_processing_behavior(target_project_root=normalized_target_root, earth_root=normalized_earth_root, active_project_id=normalized_active_project_id, capability_need=normalized_capability_need, build_new_assessment=normalized_build_new_assessment, target_project_evidence_refs=normalized_target_project_evidence_refs, earth_sweep_evidence_refs=normalized_earth_sweep_evidence_refs, cross_project_context=normalized_cross_project_context, existing_functionality_candidates=normalized_candidates, reasoning_rows=reasoning_rows, selected_path=selected_path, strategic_claims=normalized_strategic_claims)
    llm_call_trace_rows = _build_req_042_llm_call_trace_rows(canonical_input_sha=canonical_input_sha, processing_input_sha=processing_sha, processing_call_id=processing_call_id, canonical_processing_input=canonical_processing_input, reasoning_rows=reasoning_rows, selected_path=finalized_selected_path, recommendation=processing_behavior.get('recommendation'))
    llm_call_trace_sha = _canonical_digest(llm_call_trace_rows)
    evidence_refs = _collect_unique_refs(normalized_target_project_evidence_refs, normalized_build_new_assessment['evidence_refs'], normalized_earth_sweep_evidence_refs, *[row['evidence_refs'] for row in reasoning_rows], *[row['evidence_refs'] for row in processing_behavior['recommendation']['cross_project_obligations']], *[row['required_evidence_refs'] for row in processing_behavior['recommendation']['open_risks']])
    summary = f"Reviewed {len(reasoning_rows)} existing-functionality candidate(s) for {normalized_capability_need['capability_id']}: {len(compatible_candidates)} compatible, {len(needs_followup_candidates)} needing follow-up, {len(incompatible_candidates)} incompatible. Recommended path: {finalized_selected_path['decision']}."
    return {'requirement_id': REQ_042_REQUIREMENT_ID, 'surface': 'existing_functionality_interaction_reasoning', 'schema_version': REQ_042_SCHEMA_VERSION, 'evaluated_at': normalized_evaluated_at, 'active_project_id': normalized_active_project_id, 'capability_need': normalized_capability_need, 'build_new_assessment': normalized_build_new_assessment, 'interaction_reasoning': reasoning_rows, 'selected_path': finalized_selected_path, 'processing_behavior': processing_behavior, 'call_metadata': {'reproducibility': 'deterministic-input-fingerprint', 'canonical_input_sha256': canonical_input_sha, 'reproducible_call_id': f'req042-{canonical_input_sha[:16]}', 'canonical_input': canonical_input, 'processing_input_sha256': processing_sha, 'processing_call_id': processing_call_id, 'canonical_processing_input': canonical_processing_input, 'llm_call_trace_schema_version': REQ_025_LLM_CALL_TRACE_SCHEMA_VERSION, 'llm_call_trace_path': LLM_CALL_TRACE_RELATIVE_PATH, 'llm_call_trace_sha256': llm_call_trace_sha, 'llm_call_trace_rows': llm_call_trace_rows}, 'evidence_refs': evidence_refs, 'summary': summary}

def validate_req_042_existing_functionality_interaction_reasoning(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    required_keys = {'requirement_id', 'surface', 'schema_version', 'evaluated_at', 'active_project_id', 'capability_need', 'build_new_assessment', 'interaction_reasoning', 'selected_path', 'processing_behavior', 'call_metadata', 'evidence_refs', 'summary'}
    missing_keys = sorted(required_keys - set(payload.keys()))
    if missing_keys:
        errors.extend((f'missing required key: {key}' for key in missing_keys))
        return errors
    if payload.get('requirement_id') != REQ_042_REQUIREMENT_ID:
        errors.append(f'requirement_id must be {REQ_042_REQUIREMENT_ID}')
    if payload.get('surface') != 'existing_functionality_interaction_reasoning':
        errors.append('surface must be existing_functionality_interaction_reasoning')
    if payload.get('schema_version') != REQ_042_SCHEMA_VERSION:
        errors.append(f'schema_version must be {REQ_042_SCHEMA_VERSION}')
    if not _as_text(payload.get('evaluated_at')):
        errors.append('evaluated_at must be a non-empty string')
    if not _as_text(payload.get('active_project_id')):
        errors.append('active_project_id must be a non-empty string')
    try:
        normalized_capability_need = _normalize_req_042_capability_need(payload.get('capability_need'))
    except ValueError as exc:
        errors.append(str(exc))
        normalized_capability_need = None
    try:
        normalized_build_new = _normalize_req_042_build_new_assessment(payload.get('build_new_assessment'))
    except ValueError as exc:
        errors.append(str(exc))
        normalized_build_new = None
    interaction_reasoning = payload.get('interaction_reasoning')
    if not isinstance(interaction_reasoning, Sequence) or isinstance(interaction_reasoning, (str, bytes, bytearray)):
        errors.append('interaction_reasoning must be an array')
        interaction_reasoning = []
    elif not interaction_reasoning:
        errors.append('interaction_reasoning must contain at least 1 item(s)')
    compatible_consume_candidates: list[str] = []
    compatibility_states: set[str] = set()
    for index, item in enumerate(interaction_reasoning):
        if not isinstance(item, Mapping):
            errors.append(f'interaction_reasoning[{index}] must be an object')
            continue
        for key in ['candidate_id', 'source_project_id', 'capability_id', 'functionality_summary', 'required_interfaces', 'provided_interfaces', 'missing_interfaces', 'compatibility_state', 'compatibility_checks', 'integration_burden', 'candidate_decision', 'decision_rationale', 'evidence_refs']:
            if key not in item:
                errors.append(f'interaction_reasoning[{index}] missing {key}')
        compatibility_state = _as_text(item.get('compatibility_state'))
        if compatibility_state not in {'compatible', 'needs_followup', 'incompatible'}:
            errors.append(f'interaction_reasoning[{index}].compatibility_state must be compatible|needs_followup|incompatible')
        else:
            compatibility_states.add(compatibility_state)
        candidate_decision = _as_text(item.get('candidate_decision'))
        if candidate_decision not in {'consume_existing_functionality', 'investigate_existing_functionality', 'reject_existing_functionality', 'build_new_capability'}:
            errors.append(f'interaction_reasoning[{index}].candidate_decision must be consume_existing_functionality|investigate_existing_functionality|reject_existing_functionality|build_new_capability')
        elif candidate_decision == 'consume_existing_functionality':
            compatible_consume_candidates.append(_as_text(item.get('candidate_id')))
        try:
            _normalize_string_list(item.get('required_interfaces'), field_name=f'interaction_reasoning[{index}].required_interfaces')
            _normalize_string_list(item.get('provided_interfaces'), field_name=f'interaction_reasoning[{index}].provided_interfaces')
            _normalize_string_list(item.get('missing_interfaces'), field_name=f'interaction_reasoning[{index}].missing_interfaces')
            _normalize_req_042_compatibility_checks(item.get('compatibility_checks'), field_name=f'interaction_reasoning[{index}].compatibility_checks')
            _normalize_req_042_integration_burden(item.get('integration_burden'), field_name=f'interaction_reasoning[{index}].integration_burden')
            _normalize_string_list(item.get('evidence_refs'), field_name=f'interaction_reasoning[{index}].evidence_refs', min_items=1)
        except ValueError as exc:
            errors.append(str(exc))
    selected_path = payload.get('selected_path')
    if not isinstance(selected_path, Mapping):
        errors.append('selected_path must be an object')
    else:
        decision = _as_text(selected_path.get('decision'))
        if decision not in {'consume_existing_functionality', 'investigate_existing_functionality', 'build_new_capability'}:
            errors.append('selected_path.decision must be consume_existing_functionality|investigate_existing_functionality|build_new_capability')
        selected_candidate_id = selected_path.get('selected_candidate_id')
        if decision == 'consume_existing_functionality':
            if not _as_text(selected_candidate_id):
                errors.append('selected_path.selected_candidate_id must be set when consuming existing functionality')
            elif _as_text(selected_candidate_id) not in compatible_consume_candidates:
                errors.append('selected_path.selected_candidate_id must reference an interaction_reasoning row that recommends consume_existing_functionality')
        elif selected_candidate_id is not None:
            errors.append('selected_path.selected_candidate_id must be null unless decision consumes existing functionality')
        if not _as_text(selected_path.get('rationale')):
            errors.append('selected_path.rationale must be a non-empty string')
    try:
        evidence_refs = _normalize_string_list(payload.get('evidence_refs'), field_name='evidence_refs', min_items=1)
        if list(payload.get('evidence_refs')) != evidence_refs:
            errors.append('evidence_refs must be sorted unique strings')
    except ValueError as exc:
        errors.append(str(exc))
    if not _as_text(payload.get('summary')):
        errors.append('summary must be a non-empty string')
    if normalized_capability_need and interaction_reasoning:
        expected_required_interfaces = normalized_capability_need['required_interfaces']
        for index, item in enumerate(interaction_reasoning):
            if isinstance(item, Mapping) and item.get('required_interfaces') != expected_required_interfaces:
                errors.append(f'interaction_reasoning[{index}].required_interfaces must mirror capability_need.required_interfaces')
    if normalized_build_new and compatible_consume_candidates:
        build_new_burden = normalized_build_new['estimated_burden']
        for index, item in enumerate(interaction_reasoning):
            if not isinstance(item, Mapping):
                continue
            integration_burden = item.get('integration_burden')
            if not isinstance(integration_burden, Mapping):
                continue
            candidate_burden = _as_text(integration_burden.get('estimate_level'))
            if _as_text(item.get('candidate_decision')) == 'consume_existing_functionality' and candidate_burden in {'low', 'medium', 'high'} and (_req_042_burden_rank(candidate_burden) > _req_042_burden_rank(build_new_burden)):
                errors.append(f'interaction_reasoning[{index}] cannot recommend consume_existing_functionality when integration burden is higher than build_new_assessment')
    if compatibility_states == {'incompatible'} and isinstance(selected_path, Mapping):
        if selected_path.get('decision') != 'build_new_capability':
            errors.append('selected_path.decision must be build_new_capability when all candidates are incompatible')
    processing_behavior = payload.get('processing_behavior')
    normalized_target_root: str | None = None
    normalized_earth_root: str | None = None
    normalized_target_refs: list[str] | None = None
    normalized_earth_refs: list[str] | None = None
    normalized_cross_project_context: list[dict[str, Any]] | None = None
    normalized_context_candidates: list[dict[str, Any]] | None = None
    normalized_strategic_claims: list[dict[str, Any]] | None = None
    if not isinstance(processing_behavior, Mapping):
        errors.append('processing_behavior must be an object')
    else:
        expected_processing_keys = {'strategy', 'reasoning_mode', 'strict_evidence_discipline', 'heuristic_summarization_only', 'context_inputs', 'context_usage', 'existing_functionality_reasoning', 'recommendation', 'summary'}
        processing_keys = set(processing_behavior.keys())
        missing_processing = sorted(expected_processing_keys - processing_keys)
        if missing_processing:
            errors.append(f'processing_behavior missing keys: {missing_processing}')
        unexpected_processing = sorted(processing_keys - expected_processing_keys)
        if unexpected_processing:
            errors.append(f'processing_behavior unexpected keys: {unexpected_processing}')
        if processing_behavior.get('strategy') != REQ_042_STRATEGY:
            errors.append(f'processing_behavior.strategy must be {REQ_042_STRATEGY}')
        if processing_behavior.get('reasoning_mode') != EXECUTION_MODE:
            errors.append(f'processing_behavior.reasoning_mode must be {EXECUTION_MODE}')
        if processing_behavior.get('strict_evidence_discipline') is not True:
            errors.append('processing_behavior.strict_evidence_discipline must be true')
        if processing_behavior.get('heuristic_summarization_only') is not False:
            errors.append('processing_behavior.heuristic_summarization_only must be false')
        context_inputs = processing_behavior.get('context_inputs')
        if not isinstance(context_inputs, Mapping):
            errors.append('processing_behavior.context_inputs must be an object')
        else:
            target_project = context_inputs.get('target_project')
            if not isinstance(target_project, Mapping):
                errors.append('processing_behavior.context_inputs.target_project must be an object')
            else:
                try:
                    normalized_target_root = _normalize_root(target_project.get('project_root'), field_name='processing_behavior.context_inputs.target_project.project_root')
                    if _as_text(target_project.get('active_project_id')) != _as_text(payload.get('active_project_id')):
                        errors.append('processing_behavior.context_inputs.target_project.active_project_id must match active_project_id')
                    if normalized_capability_need is not None:
                        if _as_text(target_project.get('capability_id')) != normalized_capability_need['capability_id']:
                            errors.append('processing_behavior.context_inputs.target_project.capability_id must match capability_need.capability_id')
                        if _as_text(target_project.get('intent')) != normalized_capability_need['intent']:
                            errors.append('processing_behavior.context_inputs.target_project.intent must match capability_need.intent')
                    normalized_target_refs = _normalize_string_list(target_project.get('evidence_refs'), field_name='processing_behavior.context_inputs.target_project.evidence_refs')
                except ValueError as exc:
                    errors.append(str(exc))
            build_new_context = context_inputs.get('build_new_assessment')
            if not isinstance(build_new_context, Mapping):
                errors.append('processing_behavior.context_inputs.build_new_assessment must be an object')
            elif normalized_build_new is not None and dict(build_new_context) != normalized_build_new:
                errors.append('processing_behavior.context_inputs.build_new_assessment must match build_new_assessment')
            earth_sweep = context_inputs.get('earth_sweep')
            if not isinstance(earth_sweep, Mapping):
                errors.append('processing_behavior.context_inputs.earth_sweep must be an object')
            else:
                try:
                    normalized_earth_root = _normalize_root(earth_sweep.get('earth_root'), field_name='processing_behavior.context_inputs.earth_sweep.earth_root')
                    normalized_earth_refs = _normalize_string_list(earth_sweep.get('evidence_refs'), field_name='processing_behavior.context_inputs.earth_sweep.evidence_refs')
                except ValueError as exc:
                    errors.append(str(exc))
            try:
                normalized_cross_project_context = _normalize_cross_project_context(context_inputs.get('cross_project_context'))
            except ValueError as exc:
                errors.append(str(exc))
            try:
                normalized_context_candidates = _normalize_req_042_existing_functionality_candidates(context_inputs.get('existing_functionality_candidates'))
            except ValueError as exc:
                errors.append(str(exc))
            try:
                if 'strategic_claims' in context_inputs:
                    normalized_strategic_claims = _normalize_req_028_strategic_claims(context_inputs.get('strategic_claims'))
                else:
                    normalized_strategic_claims = []
            except ValueError as exc:
                errors.append(str(exc).replace('strategic_claims', 'processing_behavior.context_inputs.strategic_claims'))
        context_usage = processing_behavior.get('context_usage')
        if not isinstance(context_usage, Mapping):
            errors.append('processing_behavior.context_usage must be an object')
        recommendation = processing_behavior.get('recommendation')
        if not isinstance(recommendation, Mapping):
            errors.append('processing_behavior.recommendation must be an object')
        elif set(recommendation.keys()) != {'decision', 'rationale', 'confidence', 'evidence_refs', 'selected_path', 'reuse_candidates', 'cross_project_obligations', 'open_risks'}:
            errors.append('processing_behavior.recommendation must expose the complete deterministic REQ-042 fields')
    metadata = payload.get('call_metadata')
    if not isinstance(metadata, Mapping):
        errors.append('call_metadata must be an object')
    else:
        required_metadata = {'reproducibility', 'canonical_input_sha256', 'reproducible_call_id', 'canonical_input', 'processing_input_sha256', 'processing_call_id', 'canonical_processing_input', 'llm_call_trace_schema_version', 'llm_call_trace_path', 'llm_call_trace_sha256', 'llm_call_trace_rows'}
        metadata_keys = set(metadata.keys())
        missing_metadata = sorted(required_metadata - metadata_keys)
        if missing_metadata:
            errors.append(f'call_metadata missing keys: {missing_metadata}')
        unexpected_metadata = sorted(metadata_keys - required_metadata)
        if unexpected_metadata:
            errors.append(f'call_metadata unexpected keys: {unexpected_metadata}')
        if metadata.get('reproducibility') != 'deterministic-input-fingerprint':
            errors.append('call_metadata.reproducibility must be deterministic-input-fingerprint')
        if metadata.get('llm_call_trace_schema_version') != REQ_025_LLM_CALL_TRACE_SCHEMA_VERSION:
            errors.append(f'call_metadata.llm_call_trace_schema_version must be {REQ_025_LLM_CALL_TRACE_SCHEMA_VERSION}')
        if metadata.get('llm_call_trace_path') != LLM_CALL_TRACE_RELATIVE_PATH:
            errors.append(f'call_metadata.llm_call_trace_path must be {LLM_CALL_TRACE_RELATIVE_PATH}')
        trace_rows = metadata.get('llm_call_trace_rows')
        if not isinstance(trace_rows, Sequence) or isinstance(trace_rows, (str, bytes, bytearray)):
            errors.append('call_metadata.llm_call_trace_rows must be a list')
    expected_payload: dict[str, Any] | None = None
    if normalized_capability_need is not None and normalized_build_new is not None and (normalized_target_root is not None) and (normalized_earth_root is not None) and (normalized_target_refs is not None) and (normalized_earth_refs is not None) and (normalized_cross_project_context is not None) and (normalized_context_candidates is not None) and (normalized_strategic_claims is not None):
        try:
            expected_payload = build_req_042_existing_functionality_interaction_reasoning(target_project_root=normalized_target_root, earth_root=normalized_earth_root, active_project_id=_require_text(payload.get('active_project_id'), field_name='active_project_id'), capability_need=normalized_capability_need, build_new_assessment=normalized_build_new, existing_functionality_candidates=normalized_context_candidates, target_project_evidence_refs=normalized_target_refs, earth_sweep_evidence_refs=normalized_earth_refs, cross_project_context=normalized_cross_project_context, strategic_claims=normalized_strategic_claims, evaluated_at=_require_text(payload.get('evaluated_at'), field_name='evaluated_at'))
        except ValueError as exc:
            errors.append(f'REQ-042 payload could not be reconstructed: {exc}')
        else:
            if dict(payload) != expected_payload:
                errors.append('payload must match deterministic REQ-042 reasoning output')
    if isinstance(metadata, Mapping) and expected_payload is not None:
        expected_metadata = expected_payload.get('call_metadata')
        if not isinstance(expected_metadata, Mapping):
            errors.append('REQ-042 deterministic reconstruction did not yield call_metadata')
        else:
            if metadata.get('canonical_input') != expected_metadata.get('canonical_input'):
                errors.append('call_metadata.canonical_input must mirror normalized invocation anchors')
            if metadata.get('canonical_input_sha256') != expected_metadata.get('canonical_input_sha256'):
                errors.append('call_metadata.canonical_input_sha256 does not match canonical input')
            if metadata.get('reproducible_call_id') != expected_metadata.get('reproducible_call_id'):
                errors.append('call_metadata.reproducible_call_id does not match canonical digest')
            if metadata.get('canonical_processing_input') != expected_metadata.get('canonical_processing_input'):
                errors.append('call_metadata.canonical_processing_input must mirror processing inputs')
            if metadata.get('processing_input_sha256') != expected_metadata.get('processing_input_sha256'):
                errors.append('call_metadata.processing_input_sha256 does not match processing input')
            if metadata.get('processing_call_id') != expected_metadata.get('processing_call_id'):
                errors.append('call_metadata.processing_call_id does not match processing digest')
            if metadata.get('llm_call_trace_rows') != expected_metadata.get('llm_call_trace_rows'):
                errors.append('call_metadata.llm_call_trace_rows must mirror deterministic REQ-042 trace rows')
            if metadata.get('llm_call_trace_sha256') != expected_metadata.get('llm_call_trace_sha256'):
                errors.append('call_metadata.llm_call_trace_sha256 does not match llm_call_trace_rows')
    return errors

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

def _build_call_output_ref(*, plan_id: str, call_id: str, expected_output: str) -> str:
    return f'{plan_id}::call::{call_id}::output::{expected_output}'

def _slug_id_fragment(value: Any) -> str:
    text = _as_text(value).lower()
    chars = [ch if ch.isalnum() else '-' for ch in text]
    collapsed = ''.join(chars).strip('-')
    while '--' in collapsed:
        collapsed = collapsed.replace('--', '-')
    return collapsed or 'unknown'

def _normalize_req_028_strategic_claims(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError('strategic_claims must be an array when provided')
    normalized: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f'strategic_claims[{index}] must be an object')
        claim_id = _require_text(item.get('claim_id'), field_name=f'strategic_claims[{index}].claim_id')
        phase = _require_text(item.get('phase'), field_name=f'strategic_claims[{index}].phase').lower()
        if phase not in {'analysis', 'synthesis'}:
            raise ValueError(f'strategic_claims[{index}].phase must be analysis or synthesis')
        summary = _require_text(item.get('summary'), field_name=f'strategic_claims[{index}].summary')
        position = _require_text(item.get('position'), field_name=f'strategic_claims[{index}].position')
        source_output_ref = _require_text(item.get('source_output_ref'), field_name=f'strategic_claims[{index}].source_output_ref')
        claim_key = (claim_id, phase, source_output_ref)
        if claim_key in seen_keys:
            raise ValueError(f'strategic_claims[{index}] duplicates claim_id/phase/source_output_ref for {claim_id}')
        seen_keys.add(claim_key)
        evidence_refs = _normalize_string_list(item.get('evidence_refs'), field_name=f'strategic_claims[{index}].evidence_refs')
        normalized.append({'claim_id': claim_id, 'phase': phase, 'summary': summary, 'position': position, 'source_output_ref': source_output_ref, 'evidence_refs': evidence_refs})
    normalized.sort(key=lambda row: (row['claim_id'], row['phase'], row['source_output_ref'], row['position']))
    return normalized


_build_req_042_existing_functionality_interaction_reasoning_legacy = (
    build_req_042_existing_functionality_interaction_reasoning
)


def build_req_042_existing_functionality_interaction_reasoning_legacy_compat(*, target_project_root: str=DEFAULT_TARGET_PROJECT_ROOT, earth_root: str=DEFAULT_EARTH_ROOT, active_project_id: Any, capability_need: Mapping[str, Any] | None, build_new_assessment: Mapping[str, Any] | None, existing_functionality_candidates: Sequence[Mapping[str, Any]] | None, target_project_evidence_refs: Sequence[Any] | None=None, earth_sweep_evidence_refs: Sequence[Any] | None=None, cross_project_context: Sequence[Mapping[str, Any]] | None=None, strategic_claims: Sequence[Mapping[str, Any]] | None=None, evaluated_at: str | None=None) -> dict[str, Any]:
    payload = _build_req_042_existing_functionality_interaction_reasoning_legacy(
        target_project_root=target_project_root,
        earth_root=earth_root,
        active_project_id=active_project_id,
        capability_need=capability_need,
        build_new_assessment=build_new_assessment,
        existing_functionality_candidates=existing_functionality_candidates,
        target_project_evidence_refs=target_project_evidence_refs,
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        cross_project_context=cross_project_context,
        strategic_claims=strategic_claims,
        evaluated_at=evaluated_at,
    )
    payload.pop('call_metadata', None)
    return payload


def validate_req_042_existing_functionality_interaction_reasoning_legacy_compat(payload: Mapping[str, Any]) -> list[str]:
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
        expected = build_req_042_existing_functionality_interaction_reasoning(
            target_project_root=target_project.get('project_root', DEFAULT_TARGET_PROJECT_ROOT),
            earth_root=earth_sweep.get('earth_root', DEFAULT_EARTH_ROOT),
            active_project_id=payload.get('active_project_id'),
            capability_need=payload.get('capability_need'),
            build_new_assessment=payload.get('build_new_assessment'),
            existing_functionality_candidates=context_inputs.get('existing_functionality_candidates'),
            target_project_evidence_refs=target_project.get('evidence_refs'),
            earth_sweep_evidence_refs=earth_sweep.get('evidence_refs'),
            cross_project_context=context_inputs.get('cross_project_context'),
            strategic_claims=context_inputs.get('strategic_claims'),
            evaluated_at=payload.get('evaluated_at'),
        )
    except ValueError as exc:
        return [str(exc)]
    if payload != expected:
        return ['payload must mirror deterministic REQ-042 interaction reasoning output']
    return []
