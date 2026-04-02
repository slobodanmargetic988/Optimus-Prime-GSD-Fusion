#!/usr/bin/env python3
'REQ-038 and REQ-041 contract/data-model surfaces for strategy recommendation processing.'

from __future__ import annotations

import argparse

import hashlib

import json

import sys

import time

from datetime import datetime, timezone

from pathlib import Path

from typing import Any, Callable, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]

REQ_038_REQUIREMENT_ID = 'REQ-038'

REQ_038_SURFACE = 'recommendation_priority_calibration'

REQ_038_SCHEMA_VERSION = 'req-038.recommendation-priority-calibration.v1'

REQ_041_REQUIREMENT_ID = 'REQ-041'

REQ_041_SURFACE = 'recommendation_dependency_effect_modeling'

REQ_041_SCHEMA_VERSION = 'req-041.recommendation-dependency-effect-modeling.v1'

RUNTIME_MODE = 'llm-first'

EXECUTION_MODE = 'long-thinking'

DEFAULT_TARGET_PROJECT_ROOT = '/workspace/projects/optimus-prime'

DEFAULT_EARTH_ROOT = '/workspace/projects/Earth'

DEFAULT_OUTPUT_ROOT = '/workspace/projects/optimus-prime/strategy/out'

DEFAULT_REQ_038_REVISION_ID = 'rev-req038-fixture-r1'

DEFAULT_REQ_041_REVISION_ID = 'rev-req041-fixture-r1'

PRIORITY_SIGNALS = ('ecosystem_impact', 'feasibility', 'urgency')

SCORE_FIELD_BY_SIGNAL = {'ecosystem_impact': 'ecosystem_impact_score', 'feasibility': 'feasibility_score', 'urgency': 'urgency_score'}

DEFAULT_PRIORITY_WEIGHTS = {'ecosystem_impact': 0.5, 'feasibility': 0.3, 'urgency': 0.2}

LLM_CALL_TRACE_SCHEMA_VERSION = 'req-038.recommendation-priority-calibration.trace-row.v1'

REQ_041_LLM_CALL_TRACE_SCHEMA_VERSION = 'req-041.recommendation-dependency-effect-modeling.trace-row.v1'

LLM_CALL_TRACE_RELATIVE_PATH = 'strategy/current/llm_call_trace.jsonl'

LLM_CALL_TRACE_SERIALIZATION = 'jsonl-per-call-row.v1'

REASON_CODE_CROSS_CALL_ANALYSIS_SYNTHESIS_CONTRADICTION = 'cross_call_analysis_synthesis_contradiction'

REASON_CODE_CITATION_DISCIPLINE_UNCITED_STRATEGIC_CLAIM = 'citation_discipline_uncited_strategic_claim'

BLOCKER_SEVERITY_ORDER = ('critical', 'high', 'medium', 'low')

LOG_ROOT = Path('/Users/slobodan/projects/LOGS')

LOG_PATH = LOG_ROOT / 'strategy_llm_pipeline.log'

LOG_BUDGET_CHECK_STAMP = LOG_ROOT / '.log_budget_check.strategy_llm_pipeline'

LOG_BUDGET_CHECK_INTERVAL_SECONDS = 15 * 60

LOG_BUDGET_MAX_BYTES = 3 * 1024 * 1024 * 1024

EmitFn = Callable[[str], None]

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

def _normalize_number(value: Any, *, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f'{field_name} must be a number')
    if not isinstance(value, (int, float)):
        raise ValueError(f'{field_name} must be a number')
    out = float(value)
    if out < 0:
        raise ValueError(f'{field_name} must be non-negative')
    return out

def _normalize_score(value: Any, *, field_name: str) -> float:
    out = _normalize_number(value, field_name=field_name)
    if out > 10:
        raise ValueError(f'{field_name} must be between 0 and 10')
    return round(out, 4)

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

def _collect_unique_refs(*groups: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    for group in groups:
        for value in group:
            text = _as_text(value)
            if text:
                seen.add(text)
    return sorted(seen)

def _req_041_depends_on_call_ids(*, affected_project_ids: Sequence[str], latest_call_id_by_project_id: Mapping[str, str]) -> list[str]:
    seen: set[str] = set()
    for project_id in affected_project_ids:
        call_id = _as_text(latest_call_id_by_project_id.get(project_id))
        if call_id:
            seen.add(call_id)
    return sorted(seen)

def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()

def _serialize_llm_call_trace_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    ordered_rows = sorted(rows, key=lambda row: (int(row.get('sequence', 0)) if isinstance(row.get('sequence'), int) else 0, _as_text(row.get('call_id'))))
    lines = [json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=False) for row in ordered_rows]
    if not lines:
        return ''
    return '\n'.join(lines) + '\n'

def _write_llm_call_trace(serialized_rows: str, *, trace_root: str | Path | None=None, emit: EmitFn | None=None) -> dict[str, Any]:
    root_path = REPO_ROOT if trace_root is None else Path(trace_root).expanduser().resolve()
    trace_path = root_path / LLM_CALL_TRACE_RELATIVE_PATH
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(serialized_rows, encoding='utf-8')
    row_count = len([line for line in serialized_rows.splitlines() if line.strip()])
    trace_sha256 = hashlib.sha256(serialized_rows.encode('utf-8')).hexdigest()
    _emit_event(emit, level='INFO', message=f'Persisted llm_call_trace artifact rows={row_count} path={trace_path} sha256={trace_sha256}.')
    return {'relative_path': LLM_CALL_TRACE_RELATIVE_PATH, 'absolute_path': str(trace_path), 'row_count': row_count, 'sha256': trace_sha256}

def _priority_band(priority_score: float) -> str:
    if priority_score >= 8:
        return 'high'
    if priority_score >= 6:
        return 'medium'
    return 'low'

def _normalize_priority_weights(raw_value: Any) -> dict[str, float]:
    source = DEFAULT_PRIORITY_WEIGHTS if raw_value is None else _require_mapping(raw_value, field_name='priority_weights')
    extra_keys = sorted(set(source.keys()) - set(PRIORITY_SIGNALS))
    if extra_keys:
        raise ValueError(f"priority_weights contains unsupported signals: {', '.join(extra_keys)}")
    parsed: dict[str, float] = {}
    for signal in PRIORITY_SIGNALS:
        parsed[signal] = _normalize_number(source.get(signal), field_name=f'priority_weights.{signal}')
    total_weight = sum(parsed.values())
    if total_weight <= 0:
        raise ValueError('priority_weights must have a total weight greater than zero')
    return {signal: round(parsed[signal] / total_weight, 6) for signal in PRIORITY_SIGNALS}

def _normalize_recommendations(raw_value: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError('recommendations must be an array')
    if not raw_value:
        raise ValueError('recommendations must contain at least one row')
    normalized: list[dict[str, Any]] = []
    seen_recommendation_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        row = _require_mapping(item, field_name=f'recommendations[{index}]')
        recommendation_id = _require_text(row.get('recommendation_id'), field_name=f'recommendations[{index}].recommendation_id')
        if recommendation_id in seen_recommendation_ids:
            raise ValueError(f"recommendations[{index}].recommendation_id duplicates '{recommendation_id}'")
        seen_recommendation_ids.add(recommendation_id)
        summary = _require_text(row.get('summary'), field_name=f'recommendations[{index}].summary')
        rationale = _require_text(row.get('rationale') if row.get('rationale') is not None else 'No rationale supplied.', field_name=f'recommendations[{index}].rationale')
        ecosystem_impact_score = _normalize_score(row.get('ecosystem_impact_score'), field_name=f'recommendations[{index}].ecosystem_impact_score')
        feasibility_score = _normalize_score(row.get('feasibility_score'), field_name=f'recommendations[{index}].feasibility_score')
        urgency_score = _normalize_score(row.get('urgency_score'), field_name=f'recommendations[{index}].urgency_score')
        evidence_refs = _normalize_string_list(row.get('evidence_refs'), field_name=f'recommendations[{index}].evidence_refs', min_items=1)
        normalized.append({'recommendation_id': recommendation_id, 'summary': summary, 'rationale': rationale, 'ecosystem_impact_score': ecosystem_impact_score, 'feasibility_score': feasibility_score, 'urgency_score': urgency_score, 'evidence_refs': evidence_refs})
    normalized.sort(key=lambda row: row['recommendation_id'])
    return normalized

def _normalize_blocker_severity(value: Any, *, field_name: str) -> str:
    severity = _require_text(value, field_name=field_name).lower()
    if severity not in BLOCKER_SEVERITY_ORDER:
        raise ValueError(f"{field_name} must be one of: {', '.join(BLOCKER_SEVERITY_ORDER)}")
    return severity

def _highest_blocker_severity(blockers: Sequence[Mapping[str, Any]]) -> str:
    seen = {_as_text(row.get('severity')).lower() for row in blockers if isinstance(row, Mapping) and _as_text(row.get('severity'))}
    for severity in BLOCKER_SEVERITY_ORDER:
        if severity in seen:
            return severity
    return 'none'

def _normalize_dependency_effect_blockers(raw_value: Any, *, field_name: str) -> list[dict[str, Any]]:
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError(f'{field_name} must be an array')
    if not raw_value:
        raise ValueError(f'{field_name} must contain at least one row')
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        row = _require_mapping(item, field_name=f'{field_name}[{index}]')
        blocker_id = _require_text(row.get('blocker_id'), field_name=f'{field_name}[{index}].blocker_id')
        if blocker_id in seen_ids:
            raise ValueError(f"{field_name}[{index}].blocker_id duplicates '{blocker_id}'")
        seen_ids.add(blocker_id)
        normalized.append({'blocker_id': blocker_id, 'summary': _require_text(row.get('summary'), field_name=f'{field_name}[{index}].summary'), 'severity': _normalize_blocker_severity(row.get('severity'), field_name=f'{field_name}[{index}].severity'), 'evidence_refs': _normalize_string_list(row.get('evidence_refs'), field_name=f'{field_name}[{index}].evidence_refs', min_items=1)})
    normalized.sort(key=lambda row: row['blocker_id'])
    return normalized

def _normalize_mitigation_hooks(raw_value: Any, *, field_name: str) -> list[dict[str, Any]]:
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError(f'{field_name} must be an array')
    if not raw_value:
        raise ValueError(f'{field_name} must contain at least one row')
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        row = _require_mapping(item, field_name=f'{field_name}[{index}]')
        hook_id = _require_text(row.get('hook_id'), field_name=f'{field_name}[{index}].hook_id')
        if hook_id in seen_ids:
            raise ValueError(f"{field_name}[{index}].hook_id duplicates '{hook_id}'")
        seen_ids.add(hook_id)
        normalized.append({'hook_id': hook_id, 'summary': _require_text(row.get('summary'), field_name=f'{field_name}[{index}].summary'), 'hook_type': _require_text(row.get('hook_type'), field_name=f'{field_name}[{index}].hook_type'), 'evidence_refs': _normalize_string_list(row.get('evidence_refs'), field_name=f'{field_name}[{index}].evidence_refs', min_items=1)})
    normalized.sort(key=lambda row: row['hook_id'])
    return normalized

def _normalize_affected_project_effects(raw_value: Any, *, field_name: str) -> list[dict[str, Any]]:
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError(f'{field_name} must be an array')
    if not raw_value:
        raise ValueError(f'{field_name} must contain at least one row')
    normalized: list[dict[str, Any]] = []
    seen_project_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        row = _require_mapping(item, field_name=f'{field_name}[{index}]')
        project_id = _require_text(row.get('project_id') if row.get('project_id') is not None else row.get('affected_project_id'), field_name=f'{field_name}[{index}].project_id')
        if project_id in seen_project_ids:
            raise ValueError(f"{field_name}[{index}].project_id duplicates '{project_id}'")
        seen_project_ids.add(project_id)
        blockers = _normalize_dependency_effect_blockers(row.get('likely_blockers'), field_name=f'{field_name}[{index}].likely_blockers')
        mitigation_hooks = _normalize_mitigation_hooks(row.get('mitigation_hooks'), field_name=f'{field_name}[{index}].mitigation_hooks')
        evidence_refs = _collect_unique_refs(_normalize_string_list(row.get('evidence_refs'), field_name=f'{field_name}[{index}].evidence_refs', min_items=1), *(blocker['evidence_refs'] for blocker in blockers), *(hook['evidence_refs'] for hook in mitigation_hooks))
        normalized.append({'project_id': project_id, 'effect_type': _require_text(row.get('effect_type'), field_name=f'{field_name}[{index}].effect_type'), 'dependency_effect_summary': _require_text(row.get('dependency_effect_summary'), field_name=f'{field_name}[{index}].dependency_effect_summary'), 'blocker_count': len(blockers), 'mitigation_hook_count': len(mitigation_hooks), 'likely_blockers': blockers, 'mitigation_hooks': mitigation_hooks, 'highest_blocker_severity': _highest_blocker_severity(blockers), 'evidence_refs': evidence_refs})
    normalized.sort(key=lambda row: row['project_id'])
    return normalized

def _normalize_dependency_effect_recommendations(raw_value: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError('recommendations must be an array')
    if not raw_value:
        raise ValueError('recommendations must contain at least one row')
    normalized: list[dict[str, Any]] = []
    seen_recommendation_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        row = _require_mapping(item, field_name=f'recommendations[{index}]')
        recommendation_id = _require_text(row.get('recommendation_id'), field_name=f'recommendations[{index}].recommendation_id')
        if recommendation_id in seen_recommendation_ids:
            raise ValueError(f"recommendations[{index}].recommendation_id duplicates '{recommendation_id}'")
        seen_recommendation_ids.add(recommendation_id)
        affected_project_effects = _normalize_affected_project_effects(row.get('affected_project_effects'), field_name=f'recommendations[{index}].affected_project_effects')
        evidence_refs = _collect_unique_refs(_normalize_string_list(row.get('evidence_refs'), field_name=f'recommendations[{index}].evidence_refs', min_items=1), *(project_effect['evidence_refs'] for project_effect in affected_project_effects))
        blocker_count = sum((int(project_effect['blocker_count']) for project_effect in affected_project_effects))
        mitigation_hook_count = sum((int(project_effect['mitigation_hook_count']) for project_effect in affected_project_effects))
        normalized.append({'recommendation_id': recommendation_id, 'summary': _require_text(row.get('summary'), field_name=f'recommendations[{index}].summary'), 'rationale': _require_text(row.get('rationale') if row.get('rationale') is not None else 'No rationale supplied.', field_name=f'recommendations[{index}].rationale'), 'affected_project_count': len(affected_project_effects), 'affected_project_ids': [project_effect['project_id'] for project_effect in affected_project_effects], 'blocker_count': blocker_count, 'mitigation_hook_count': mitigation_hook_count, 'highest_blocker_severity': _highest_blocker_severity([blocker for project_effect in affected_project_effects for blocker in project_effect['likely_blockers']]), 'affected_project_effects': affected_project_effects, 'evidence_refs': evidence_refs})
    normalized.sort(key=lambda row: row['recommendation_id'])
    return normalized

def _normalize_context_project_ids(raw_value: Any, *, field_name: str) -> list[str]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError(f'{field_name} must be an array')
    project_ids: list[str] = []
    for index, item in enumerate(raw_value):
        if isinstance(item, Mapping):
            project_id = _require_text(item.get('project_id'), field_name=f'{field_name}[{index}].project_id')
        else:
            project_id = _require_text(item, field_name=f'{field_name}[{index}]')
        project_ids.append(project_id)
    return _normalize_string_list(project_ids, field_name=field_name)

def _normalize_cross_project_obligations(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError('broad_sweep_context.proposed_cross_project_obligations must be an array')
    obligations: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        row = _require_mapping(item, field_name=f'broad_sweep_context.proposed_cross_project_obligations[{index}]')
        obligation_id = _require_text(row.get('obligation_id'), field_name=f'broad_sweep_context.proposed_cross_project_obligations[{index}].obligation_id')
        if obligation_id in seen_ids:
            raise ValueError(f"broad_sweep_context.proposed_cross_project_obligations[{index}].obligation_id duplicates '{obligation_id}'")
        seen_ids.add(obligation_id)
        summary = _require_text(row.get('summary') if row.get('summary') is not None else row.get('title'), field_name=f'broad_sweep_context.proposed_cross_project_obligations[{index}].summary')
        project_ids = _normalize_string_list(row.get('project_ids'), field_name=f'broad_sweep_context.proposed_cross_project_obligations[{index}].project_ids', min_items=1)
        evidence_refs_raw = row.get('earth_sweep_evidence_refs')
        if evidence_refs_raw is None:
            evidence_refs_raw = row.get('evidence_refs')
        evidence_refs = _normalize_string_list(evidence_refs_raw, field_name=f'broad_sweep_context.proposed_cross_project_obligations[{index}].evidence_refs')
        obligations.append({'obligation_id': obligation_id, 'summary': summary, 'project_ids': project_ids, 'evidence_refs': evidence_refs})
    obligations.sort(key=lambda row: row['obligation_id'])
    return obligations

def _normalize_unresolved_ideas(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError('broad_sweep_context.unresolved_ideas must be an array')
    unresolved: list[dict[str, Any]] = []
    seen_risk_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        row = _require_mapping(item, field_name=f'broad_sweep_context.unresolved_ideas[{index}]')
        summary = _require_text(row.get('summary') if row.get('summary') is not None else row.get('idea'), field_name=f'broad_sweep_context.unresolved_ideas[{index}].summary')
        project_ids = _normalize_string_list(row.get('project_ids'), field_name=f'broad_sweep_context.unresolved_ideas[{index}].project_ids')
        evidence_refs_raw = row.get('earth_sweep_evidence_refs')
        if evidence_refs_raw is None:
            evidence_refs_raw = row.get('evidence_refs')
        evidence_refs = _normalize_string_list(evidence_refs_raw, field_name=f'broad_sweep_context.unresolved_ideas[{index}].evidence_refs')
        risk_id_seed = _as_text(row.get('open_risk_id') or row.get('risk_id') or row.get('idea_id'))
        if risk_id_seed:
            risk_id = risk_id_seed
        else:
            risk_id = 'risk.req038.unresolved.' + hashlib.sha256(f"{summary}|{','.join(project_ids)}".encode('utf-8')).hexdigest()[:10]
        if risk_id in seen_risk_ids:
            raise ValueError(f"broad_sweep_context.unresolved_ideas[{index}] risk_id duplicates '{risk_id}'")
        seen_risk_ids.add(risk_id)
        unresolved.append({'risk_id': risk_id, 'summary': summary, 'project_ids': project_ids, 'evidence_refs': evidence_refs})
    unresolved.sort(key=lambda row: row['risk_id'])
    return unresolved

def _normalize_cross_call_reconciliations(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError('broad_sweep_context.cross_call_reconciliations must be an array')
    reconciliations: list[dict[str, Any]] = []
    seen_call_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        row = _require_mapping(item, field_name=f'broad_sweep_context.cross_call_reconciliations[{index}]')
        call_id = _require_text(row.get('call_id'), field_name=f'broad_sweep_context.cross_call_reconciliations[{index}].call_id')
        if call_id in seen_call_ids:
            raise ValueError(f"broad_sweep_context.cross_call_reconciliations[{index}].call_id duplicates '{call_id}'")
        seen_call_ids.add(call_id)
        analysis_output = _require_text(row.get('analysis_output'), field_name=f'broad_sweep_context.cross_call_reconciliations[{index}].analysis_output')
        synthesis_output = _require_text(row.get('synthesis_output'), field_name=f'broad_sweep_context.cross_call_reconciliations[{index}].synthesis_output')
        project_ids = _normalize_string_list(row.get('project_ids'), field_name=f'broad_sweep_context.cross_call_reconciliations[{index}].project_ids')
        evidence_refs = _collect_unique_refs(_normalize_string_list(row.get('evidence_refs'), field_name=f'broad_sweep_context.cross_call_reconciliations[{index}].evidence_refs'), _normalize_string_list(row.get('analysis_evidence_refs'), field_name=f'broad_sweep_context.cross_call_reconciliations[{index}].analysis_evidence_refs'), _normalize_string_list(row.get('synthesis_evidence_refs'), field_name=f'broad_sweep_context.cross_call_reconciliations[{index}].synthesis_evidence_refs'))
        if not evidence_refs:
            raise ValueError(f'broad_sweep_context.cross_call_reconciliations[{index}] must include at least one evidence ref')
        reconciliations.append({'call_id': call_id, 'analysis_output': analysis_output, 'synthesis_output': synthesis_output, 'project_ids': project_ids, 'evidence_refs': evidence_refs})
    reconciliations.sort(key=lambda row: row['call_id'])
    return reconciliations

def _normalize_strategic_claims(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError('broad_sweep_context.strategic_claims must be an array')
    claims: list[dict[str, Any]] = []
    seen_claim_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        row = _require_mapping(item, field_name=f'broad_sweep_context.strategic_claims[{index}]')
        claim_id = _require_text(row.get('claim_id'), field_name=f'broad_sweep_context.strategic_claims[{index}].claim_id')
        if claim_id in seen_claim_ids:
            raise ValueError(f"broad_sweep_context.strategic_claims[{index}].claim_id duplicates '{claim_id}'")
        seen_claim_ids.add(claim_id)
        summary = _require_text(row.get('summary') if row.get('summary') is not None else row.get('claim'), field_name=f'broad_sweep_context.strategic_claims[{index}].summary')
        project_ids = _normalize_string_list(row.get('project_ids'), field_name=f'broad_sweep_context.strategic_claims[{index}].project_ids')
        citations_raw = row.get('citation_refs')
        if citations_raw is None:
            citations_raw = row.get('citations')
        citation_refs = _normalize_string_list(citations_raw, field_name=f'broad_sweep_context.strategic_claims[{index}].citation_refs')
        evidence_refs_raw = row.get('evidence_refs')
        if evidence_refs_raw is None:
            evidence_refs_raw = row.get('claim_evidence_refs')
        evidence_refs = _normalize_string_list(evidence_refs_raw, field_name=f'broad_sweep_context.strategic_claims[{index}].evidence_refs', min_items=1)
        claims.append({'claim_id': claim_id, 'summary': summary, 'project_ids': project_ids, 'citation_refs': citation_refs, 'evidence_refs': evidence_refs})
    claims.sort(key=lambda row: row['claim_id'])
    return claims

def _normalize_broad_sweep_context(raw_value: Any) -> dict[str, Any]:
    if raw_value is None:
        raw: Mapping[str, Any] = {}
    else:
        raw = _require_mapping(raw_value, field_name='broad_sweep_context')
    projects_considered = _normalize_context_project_ids(raw.get('projects_considered'), field_name='broad_sweep_context.projects_considered')
    cross_project_context_projects = _normalize_context_project_ids(raw.get('cross_project_context'), field_name='broad_sweep_context.cross_project_context')
    earth_sweep_evidence_refs_raw = raw.get('earth_sweep_evidence_refs')
    if earth_sweep_evidence_refs_raw is None:
        earth_sweep_evidence_refs_raw = raw.get('evidence_refs')
    earth_sweep_evidence_refs = _normalize_string_list(earth_sweep_evidence_refs_raw, field_name='broad_sweep_context.earth_sweep_evidence_refs')
    obligations_raw = raw.get('proposed_cross_project_obligations')
    if obligations_raw is None:
        obligations_raw = raw.get('cross_project_obligations')
    proposed_obligations = _normalize_cross_project_obligations(obligations_raw)
    unresolved_raw = raw.get('unresolved_ideas')
    if unresolved_raw is None:
        unresolved_raw = raw.get('open_risks')
    unresolved_ideas = _normalize_unresolved_ideas(unresolved_raw)
    cross_call_reconciliations_raw = raw.get('cross_call_reconciliations')
    if cross_call_reconciliations_raw is None:
        cross_call_reconciliations_raw = raw.get('analysis_synthesis_reconciliations')
    cross_call_reconciliations = _normalize_cross_call_reconciliations(cross_call_reconciliations_raw)
    strategic_claims_raw = raw.get('strategic_claims')
    if strategic_claims_raw is None:
        strategic_claims_raw = raw.get('claims')
    strategic_claims = _normalize_strategic_claims(strategic_claims_raw)
    context_project_ids = _collect_unique_refs(projects_considered, cross_project_context_projects, *(row['project_ids'] for row in proposed_obligations), *(row['project_ids'] for row in unresolved_ideas), *(row['project_ids'] for row in cross_call_reconciliations), *(row['project_ids'] for row in strategic_claims))
    normalized = {'projects_considered': projects_considered, 'cross_project_context_project_ids': cross_project_context_projects, 'context_project_ids': context_project_ids, 'earth_sweep_evidence_refs': earth_sweep_evidence_refs, 'proposed_cross_project_obligations': proposed_obligations, 'unresolved_ideas': unresolved_ideas}
    if cross_call_reconciliations:
        normalized['cross_call_reconciliations'] = cross_call_reconciliations
    if strategic_claims:
        normalized['strategic_claims'] = strategic_claims
    return normalized

def _build_cross_project_recommendation(*, broad_sweep_context: Mapping[str, Any], baseline_evidence_refs: Sequence[str]) -> dict[str, Any]:
    earth_sweep_evidence_refs = _normalize_string_list(broad_sweep_context.get('earth_sweep_evidence_refs'), field_name='broad_sweep_context.earth_sweep_evidence_refs')
    earth_sweep_ref_set = set(earth_sweep_evidence_refs)
    context_project_ids = _normalize_string_list(broad_sweep_context.get('context_project_ids'), field_name='broad_sweep_context.context_project_ids')
    proposed_obligations = _normalize_cross_project_obligations(broad_sweep_context.get('proposed_cross_project_obligations'))
    unresolved_ideas = _normalize_unresolved_ideas(broad_sweep_context.get('unresolved_ideas'))
    cross_call_reconciliations = _normalize_cross_call_reconciliations(broad_sweep_context.get('cross_call_reconciliations'))
    strategic_claims = _normalize_strategic_claims(broad_sweep_context.get('strategic_claims'))
    approved_obligations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    for row in proposed_obligations:
        has_refs = bool(row['evidence_refs'])
        refs_are_earth_sweep = all((ref in earth_sweep_ref_set for ref in row['evidence_refs'])) if has_refs else False
        if has_refs and refs_are_earth_sweep:
            approved_obligations.append({'obligation_id': row['obligation_id'], 'summary': row['summary'], 'project_ids': row['project_ids'], 'evidence_refs': row['evidence_refs']})
            continue
        reason_parts: list[str] = []
        if not has_refs:
            reason_parts.append('missing_earth_sweep_evidence_refs')
        if has_refs and (not refs_are_earth_sweep):
            reason_parts.append('non_earth_sweep_evidence_refs')
        open_risks.append({'risk_id': f"risk.req038.cross_project_obligation.{row['obligation_id']}", 'summary': row['summary'], 'reason_code': ','.join(reason_parts), 'required_evidence_refs': row['evidence_refs'], 'context_project_ids': row['project_ids'], 'evidence_refs': sorted((ref for ref in row['evidence_refs'] if ref in earth_sweep_ref_set))})
    for row in unresolved_ideas:
        open_risks.append({'risk_id': row['risk_id'], 'summary': row['summary'], 'reason_code': 'unresolved_cross_project_idea', 'required_evidence_refs': row['evidence_refs'], 'context_project_ids': row['project_ids'], 'evidence_refs': sorted((ref for ref in row['evidence_refs'] if ref in earth_sweep_ref_set))})
    cross_call_contradiction_count = 0
    for row in cross_call_reconciliations:
        if row['analysis_output'] == row['synthesis_output']:
            continue
        cross_call_contradiction_count += 1
        open_risks.append({'risk_id': f"risk.req038.cross_call_contradiction.{row['call_id']}", 'summary': f"Cross-call contradiction detected for {row['call_id']}: analysis and synthesis outputs disagree.", 'reason_code': REASON_CODE_CROSS_CALL_ANALYSIS_SYNTHESIS_CONTRADICTION, 'required_evidence_refs': row['evidence_refs'], 'context_project_ids': row['project_ids'], 'evidence_refs': row['evidence_refs']})
    uncited_claim_count = 0
    for row in strategic_claims:
        if row['citation_refs']:
            continue
        uncited_claim_count += 1
        open_risks.append({'risk_id': f"risk.req038.citation_discipline.{row['claim_id']}", 'summary': f"Citation discipline blocked uncited strategic claim: {row['summary']}", 'reason_code': REASON_CODE_CITATION_DISCIPLINE_UNCITED_STRATEGIC_CLAIM, 'required_evidence_refs': row['evidence_refs'], 'context_project_ids': row['project_ids'], 'evidence_refs': row['evidence_refs']})
    approved_obligations.sort(key=lambda row: row['obligation_id'])
    open_risks.sort(key=lambda row: row['risk_id'])
    recommendation_evidence_refs = _collect_unique_refs(baseline_evidence_refs, earth_sweep_evidence_refs, *(row['evidence_refs'] for row in approved_obligations), *(row['evidence_refs'] for row in open_risks))
    cross_project_context_used = bool(context_project_ids or proposed_obligations or unresolved_ideas or cross_call_reconciliations or strategic_claims)
    decision = 'prioritize_with_open_risks' if open_risks else 'prioritize_with_cross_project_obligations' if approved_obligations else 'prioritize_local'
    rationale = f'context_projects={len(context_project_ids)} approved_obligations={len(approved_obligations)} open_risks={len(open_risks)} earth_refs={len(earth_sweep_evidence_refs)}'
    if cross_call_contradiction_count or uncited_claim_count:
        rationale = f'{rationale} cross_call_contradictions={cross_call_contradiction_count} uncited_claims={uncited_claim_count}'
    context_usage = {'cross_project_context_used': cross_project_context_used, 'context_project_ids': context_project_ids, 'earth_sweep_evidence_refs_used': earth_sweep_evidence_refs, 'approved_cross_project_obligation_ids': [row['obligation_id'] for row in approved_obligations], 'open_risk_ids': [row['risk_id'] for row in open_risks], 'evidence_refs_used': recommendation_evidence_refs}
    recommendation = {'decision': decision, 'rationale': rationale, 'evidence_refs': recommendation_evidence_refs, 'context_project_ids': context_project_ids, 'approved_cross_project_obligations': approved_obligations, 'open_risks': open_risks}
    return {'context_usage': context_usage, 'recommendation': recommendation}

def _build_req_041_processing_recommendation(*, broad_sweep_context: Mapping[str, Any], baseline_evidence_refs: Sequence[str], modeled_project_ids: Sequence[str]) -> dict[str, Any]:
    earth_sweep_evidence_refs = _normalize_string_list(broad_sweep_context.get('earth_sweep_evidence_refs'), field_name='broad_sweep_context.earth_sweep_evidence_refs')
    earth_sweep_ref_set = set(earth_sweep_evidence_refs)
    context_project_ids = _collect_unique_refs(_normalize_string_list(broad_sweep_context.get('context_project_ids'), field_name='broad_sweep_context.context_project_ids'), modeled_project_ids)
    proposed_obligations = _normalize_cross_project_obligations(broad_sweep_context.get('proposed_cross_project_obligations'))
    unresolved_ideas = _normalize_unresolved_ideas(broad_sweep_context.get('unresolved_ideas'))
    cross_call_reconciliations = _normalize_cross_call_reconciliations(broad_sweep_context.get('cross_call_reconciliations'))
    strategic_claims = _normalize_strategic_claims(broad_sweep_context.get('strategic_claims'))
    approved_obligations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    for row in proposed_obligations:
        has_refs = bool(row['evidence_refs'])
        refs_are_earth_sweep = all((ref in earth_sweep_ref_set for ref in row['evidence_refs'])) if has_refs else False
        if has_refs and refs_are_earth_sweep:
            approved_obligations.append({'obligation_id': row['obligation_id'], 'summary': row['summary'], 'project_ids': row['project_ids'], 'evidence_refs': row['evidence_refs']})
            continue
        reason_parts: list[str] = []
        if not has_refs:
            reason_parts.append('missing_earth_sweep_evidence_refs')
        if has_refs and (not refs_are_earth_sweep):
            reason_parts.append('non_earth_sweep_evidence_refs')
        open_risks.append({'risk_id': f"risk.req041.cross_project_obligation.{row['obligation_id']}", 'summary': row['summary'], 'reason_code': ','.join(reason_parts), 'required_evidence_refs': row['evidence_refs'], 'context_project_ids': row['project_ids'], 'evidence_refs': sorted((ref for ref in row['evidence_refs'] if ref in earth_sweep_ref_set))})
    for row in unresolved_ideas:
        open_risks.append({'risk_id': row['risk_id'], 'summary': row['summary'], 'reason_code': 'unresolved_cross_project_idea', 'required_evidence_refs': row['evidence_refs'], 'context_project_ids': row['project_ids'], 'evidence_refs': sorted((ref for ref in row['evidence_refs'] if ref in earth_sweep_ref_set))})
    cross_call_contradiction_count = 0
    for row in cross_call_reconciliations:
        if row['analysis_output'] == row['synthesis_output']:
            continue
        cross_call_contradiction_count += 1
        open_risks.append({'risk_id': f"risk.req041.cross_call_contradiction.{row['call_id']}", 'summary': f"Cross-call contradiction detected for {row['call_id']}: analysis and synthesis outputs disagree.", 'reason_code': REASON_CODE_CROSS_CALL_ANALYSIS_SYNTHESIS_CONTRADICTION, 'required_evidence_refs': row['evidence_refs'], 'context_project_ids': row['project_ids'], 'evidence_refs': row['evidence_refs']})
    uncited_claim_count = 0
    for row in strategic_claims:
        if row['citation_refs']:
            continue
        uncited_claim_count += 1
        open_risks.append({'risk_id': f"risk.req041.citation_discipline.{row['claim_id']}", 'summary': f"Citation discipline blocked uncited strategic claim: {row['summary']}", 'reason_code': REASON_CODE_CITATION_DISCIPLINE_UNCITED_STRATEGIC_CLAIM, 'required_evidence_refs': row['evidence_refs'], 'context_project_ids': row['project_ids'], 'evidence_refs': row['evidence_refs']})
    approved_obligations.sort(key=lambda row: row['obligation_id'])
    open_risks.sort(key=lambda row: row['risk_id'])
    normalized_modeled_project_ids = _normalize_string_list(modeled_project_ids, field_name='modeled_project_ids')
    recommendation_evidence_refs = _collect_unique_refs(baseline_evidence_refs, earth_sweep_evidence_refs, *(row['evidence_refs'] for row in approved_obligations), *(row['evidence_refs'] for row in open_risks))
    cross_project_context_used = bool(normalized_modeled_project_ids or _normalize_string_list(broad_sweep_context.get('cross_project_context_project_ids'), field_name='broad_sweep_context.cross_project_context_project_ids') or proposed_obligations or unresolved_ideas or cross_call_reconciliations or strategic_claims)
    decision = 'model_with_open_risks' if open_risks else 'model_with_cross_project_obligations' if approved_obligations else 'model_dependency_effects_only'
    rationale = f'modeled_projects={len(normalized_modeled_project_ids)} context_projects={len(context_project_ids)} approved_obligations={len(approved_obligations)} open_risks={len(open_risks)} earth_refs={len(earth_sweep_evidence_refs)}'
    if cross_call_contradiction_count or uncited_claim_count:
        rationale = f'{rationale} cross_call_contradictions={cross_call_contradiction_count} uncited_claims={uncited_claim_count}'
    context_usage = {'cross_project_context_used': cross_project_context_used, 'modeled_project_ids': normalized_modeled_project_ids, 'context_project_ids': context_project_ids, 'earth_sweep_evidence_refs_used': earth_sweep_evidence_refs, 'approved_cross_project_obligation_ids': [row['obligation_id'] for row in approved_obligations], 'open_risk_ids': [row['risk_id'] for row in open_risks], 'evidence_refs_used': recommendation_evidence_refs}
    recommendation = {'decision': decision, 'rationale': rationale, 'evidence_refs': recommendation_evidence_refs, 'context_project_ids': context_project_ids, 'approved_cross_project_obligations': approved_obligations, 'open_risks': open_risks}
    return {'context_usage': context_usage, 'recommendation': recommendation}

def _maybe_enforce_log_budget() -> None:
    try:
        LOG_ROOT.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    now_ts = time.time()
    try:
        last_checked = LOG_BUDGET_CHECK_STAMP.stat().st_mtime
        if now_ts - last_checked < LOG_BUDGET_CHECK_INTERVAL_SECONDS:
            return
    except FileNotFoundError:
        pass
    except OSError:
        return
    tracked_files: list[tuple[Path, int, float]] = []
    total_size = 0
    for candidate in LOG_ROOT.rglob('*'):
        if not candidate.is_file() or candidate == LOG_BUDGET_CHECK_STAMP:
            continue
        try:
            stat = candidate.stat()
        except OSError:
            continue
        tracked_files.append((candidate, stat.st_size, stat.st_mtime))
        total_size += stat.st_size
    if total_size > LOG_BUDGET_MAX_BYTES:
        tracked_files.sort(key=lambda row: row[2])
        remaining_size = total_size
        for path, size_bytes, _mtime in tracked_files:
            if remaining_size <= LOG_BUDGET_MAX_BYTES:
                break
            try:
                path.write_bytes(b'')
            except OSError:
                continue
            remaining_size -= size_bytes
    try:
        LOG_BUDGET_CHECK_STAMP.touch()
    except OSError:
        return

def _default_emit(line: str) -> None:
    _maybe_enforce_log_budget()
    sys.stderr.write(f'{line}\n')
    sys.stderr.flush()
    try:
        LOG_ROOT.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open('a', encoding='utf-8') as handle:
            handle.write(f'{line}\n')
    except OSError:
        return

def _emit_event(emit: EmitFn | None, *, level: str, message: str) -> None:
    line = f'[{utc_now_iso()}] [{level}] {message}'
    if emit is None:
        _default_emit(line)
    else:
        emit(line)

def build_req_038_recommendation_priority_calibration(*, target_project_root: str=DEFAULT_TARGET_PROJECT_ROOT, earth_root: str=DEFAULT_EARTH_ROOT, output_root: str=DEFAULT_OUTPUT_ROOT, revision_identity: str=DEFAULT_REQ_038_REVISION_ID, recommendations: Sequence[Mapping[str, Any]], priority_weights: Mapping[str, Any] | None=None, broad_sweep_context: Mapping[str, Any] | None=None, calibrated_at: str | None=None, persist_llm_call_trace: bool=False, trace_root: str | Path | None=None, emit: EmitFn | None=None) -> dict[str, Any]:
    """Build the REQ-038 recommendation-priority calibration payload."""
    _emit_event(emit, level='INFO', message='Starting REQ-038 recommendation priority calibration build with deterministic weighted scoring.')
    normalized_target_project_root = _normalize_root(target_project_root, field_name='target_project_root')
    normalized_earth_root = _normalize_root(earth_root, field_name='earth_root')
    normalized_output_root = _normalize_root(output_root, field_name='output_root')
    normalized_revision_identity = _require_text(revision_identity, field_name='revision_identity')
    normalized_calibrated_at = _require_text(calibrated_at, field_name='calibrated_at') if calibrated_at else utc_now_iso()
    normalized_weights = _normalize_priority_weights(priority_weights)
    normalized_recommendations = _normalize_recommendations(recommendations)
    normalized_broad_sweep_context = _normalize_broad_sweep_context(broad_sweep_context)
    _emit_event(emit, level='INFO', message=f"REQ-038 input normalized: recommendations={len(normalized_recommendations)}, weights={normalized_weights}, context_projects={len(normalized_broad_sweep_context['context_project_ids'])}.")
    canonical_input = {'runtime_mode': RUNTIME_MODE, 'execution_mode': EXECUTION_MODE, 'target_project_root': normalized_target_project_root, 'earth_root': normalized_earth_root, 'output_root': normalized_output_root, 'revision_identity': normalized_revision_identity, 'calibrated_at': normalized_calibrated_at}
    canonical_input_sha256 = _canonical_sha256(canonical_input)
    canonical_processing_input = {'priority_weights': normalized_weights, 'recommendations': normalized_recommendations, 'broad_sweep_context': normalized_broad_sweep_context}
    processing_input_sha256 = _canonical_sha256(canonical_processing_input)
    call_plan_id = f'req038-plan-{processing_input_sha256[:16]}'
    processing_call_id = f'req038-processing-{processing_input_sha256[:16]}'
    priority_calibrations: list[dict[str, Any]] = []
    for row in normalized_recommendations:
        contributors: dict[str, dict[str, float]] = {}
        priority_score = 0.0
        for signal in PRIORITY_SIGNALS:
            score_field = SCORE_FIELD_BY_SIGNAL[signal]
            score_value = float(row[score_field])
            weight_value = float(normalized_weights[signal])
            weighted_contribution = round(score_value * weight_value, 4)
            contributors[signal] = {'weight': weight_value, 'score': score_value, 'weighted_contribution': weighted_contribution}
            priority_score += weighted_contribution
        rounded_priority_score = round(priority_score, 4)
        priority_calibrations.append({'recommendation_id': row['recommendation_id'], 'summary': row['summary'], 'rationale': row['rationale'], 'ecosystem_impact_score': row['ecosystem_impact_score'], 'feasibility_score': row['feasibility_score'], 'urgency_score': row['urgency_score'], 'priority_score': rounded_priority_score, 'priority_band': _priority_band(rounded_priority_score), 'scoring_contributors': contributors, 'evidence_refs': row['evidence_refs']})
    priority_calibrations.sort(key=lambda row: (-float(row['priority_score']), -float(row['ecosystem_impact_score']), -float(row['urgency_score']), -float(row['feasibility_score']), row['recommendation_id']))
    llm_call_trace_rows: list[dict[str, Any]] = []
    for index, row in enumerate(priority_calibrations, start=1):
        row['rank'] = index
        call_id = f"req038-call-{index:02d}-{hashlib.sha256(row['recommendation_id'].encode('utf-8')).hexdigest()[:10]}"
        depends_on = [] if index == 1 else [llm_call_trace_rows[-1]['call_id']]
        llm_call_trace_rows.append({'schema_version': LLM_CALL_TRACE_SCHEMA_VERSION, 'requirement_id': REQ_038_REQUIREMENT_ID, 'plan_id': call_plan_id, 'processing_call_id': processing_call_id, 'call_id': call_id, 'sequence': index, 'call_objective': f"Calibrate recommendation priority score using ecosystem impact, feasibility, and urgency for {row['recommendation_id']}.", 'depends_on': depends_on, 'expected_output': f"priority_calibration_{index:02d}_{row['recommendation_id'].replace('.', '-')}", 'input_refs': row['evidence_refs'], 'output_refs': [f'{call_plan_id}::call::{call_id}::output::priority_calibration_{index:02d}', f'{LLM_CALL_TRACE_RELATIVE_PATH}#L{index}'], 'handoff_summary': f"Call {index} calibrated recommendation {row['recommendation_id']} to priority score {row['priority_score']}."})
    llm_call_trace_jsonl = _serialize_llm_call_trace_rows(llm_call_trace_rows)
    llm_call_trace_jsonl_sha256 = hashlib.sha256(llm_call_trace_jsonl.encode('utf-8')).hexdigest()
    calibration_evidence_refs = _collect_unique_refs(*(row['evidence_refs'] for row in priority_calibrations))
    cross_project_output = _build_cross_project_recommendation(broad_sweep_context=normalized_broad_sweep_context, baseline_evidence_refs=calibration_evidence_refs)
    context_usage = cross_project_output['context_usage']
    recommendation = cross_project_output['recommendation']
    evidence_refs = _collect_unique_refs(calibration_evidence_refs, recommendation['evidence_refs'])
    top_recommendation = priority_calibrations[0]
    bottom_recommendation = priority_calibrations[-1]
    payload = {'requirement_id': REQ_038_REQUIREMENT_ID, 'surface': REQ_038_SURFACE, 'schema_version': REQ_038_SCHEMA_VERSION, 'recommendation_priority_calibration_entrypoint': {'runtime_mode': RUNTIME_MODE, 'execution_mode': EXECUTION_MODE, 'target_project_root': normalized_target_project_root, 'earth_root': normalized_earth_root, 'output_root': normalized_output_root, 'revision_identity': normalized_revision_identity, 'calibrated_at': normalized_calibrated_at}, 'processing_behavior': {'calibration_method': 'weighted-signal-linear-model', 'signal_order': list(PRIORITY_SIGNALS), 'auditability': 'Each recommendation reports transparent per-signal scoring contributors.', 'ranking_rule': 'Sort by priority_score desc, ecosystem_impact_score desc, urgency_score desc, feasibility_score desc, recommendation_id asc.', 'context_inputs': {'broad_sweep_context': normalized_broad_sweep_context}, 'context_usage': context_usage, 'recommendation': recommendation}, 'call_metadata': {'reproducibility': 'deterministic-input-fingerprint', 'canonical_input_sha256': canonical_input_sha256, 'reproducible_call_id': f'req038-{canonical_input_sha256[:16]}', 'canonical_input': canonical_input, 'processing_input_sha256': processing_input_sha256, 'processing_call_id': processing_call_id, 'canonical_processing_input': canonical_processing_input, 'llm_call_trace_schema_version': LLM_CALL_TRACE_SCHEMA_VERSION, 'llm_call_trace_serialization': LLM_CALL_TRACE_SERIALIZATION, 'llm_call_trace_path': LLM_CALL_TRACE_RELATIVE_PATH, 'llm_call_trace_row_count': len(llm_call_trace_rows), 'llm_call_trace_jsonl_sha256': llm_call_trace_jsonl_sha256, 'llm_call_trace_sha256': _canonical_sha256({'rows': llm_call_trace_rows}), 'llm_call_trace_rows': llm_call_trace_rows}, 'calibrated_at': normalized_calibrated_at, 'priority_weights': normalized_weights, 'priority_calibrations': priority_calibrations, 'evidence_refs': evidence_refs, 'summary': {'recommendation_count': len(priority_calibrations), 'top_recommendation_id': top_recommendation['recommendation_id'], 'top_priority_score': top_recommendation['priority_score'], 'bottom_recommendation_id': bottom_recommendation['recommendation_id'], 'bottom_priority_score': bottom_recommendation['priority_score'], 'score_spread': round(float(top_recommendation['priority_score']) - float(bottom_recommendation['priority_score']), 4)}}
    if persist_llm_call_trace:
        payload['call_metadata']['llm_call_trace_artifact'] = _write_llm_call_trace(llm_call_trace_jsonl, trace_root=trace_root, emit=emit)
    _emit_event(emit, level='INFO', message=f"REQ-038 build complete: top_recommendation={payload['summary']['top_recommendation_id']}, score={payload['summary']['top_priority_score']}.")
    return payload

def validate_req_038_recommendation_priority_calibration(payload: Mapping[str, Any], *, emit: EmitFn | None=None) -> list[str]:
    """Validate a REQ-038 recommendation-priority calibration payload."""
    _emit_event(emit, level='INFO', message='Validating REQ-038 recommendation priority calibration payload.')
    errors: list[str] = []
    required_top_level = {'requirement_id', 'surface', 'schema_version', 'recommendation_priority_calibration_entrypoint', 'processing_behavior', 'call_metadata', 'calibrated_at', 'priority_weights', 'priority_calibrations', 'evidence_refs', 'summary'}
    missing = sorted(required_top_level - set(payload.keys()))
    if missing:
        errors.append(f"missing top-level key(s): {', '.join(missing)}")
    if payload.get('requirement_id') != REQ_038_REQUIREMENT_ID:
        errors.append('requirement_id must be REQ-038')
    if payload.get('surface') != REQ_038_SURFACE:
        errors.append('surface must be recommendation_priority_calibration')
    if payload.get('schema_version') != REQ_038_SCHEMA_VERSION:
        errors.append('schema_version mismatch for REQ-038')
    weights = payload.get('priority_weights')
    if not isinstance(weights, Mapping):
        errors.append('priority_weights must be an object')
        weights = {}
    weight_total = 0.0
    for signal in PRIORITY_SIGNALS:
        value = weights.get(signal)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f'priority_weights.{signal} must be numeric')
            continue
        numeric = float(value)
        if numeric < 0 or numeric > 1:
            errors.append(f'priority_weights.{signal} must be between 0 and 1')
        weight_total += numeric
    if abs(weight_total - 1.0) > 1e-06:
        errors.append('priority_weights must sum to 1')
    rows = payload.get('priority_calibrations')
    if not isinstance(rows, list) or not rows:
        errors.append('priority_calibrations must be a non-empty array')
        rows = []
    expected_rank = 1
    previous_priority_score = float('inf')
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            errors.append(f'priority_calibrations[{index}] must be an object')
            continue
        if row.get('rank') != expected_rank:
            errors.append(f'priority_calibrations[{index}].rank must be {expected_rank}')
        expected_rank += 1
        for score_field in SCORE_FIELD_BY_SIGNAL.values():
            value = row.get(score_field)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(f'priority_calibrations[{index}].{score_field} must be numeric')
                continue
            numeric = float(value)
            if numeric < 0 or numeric > 10:
                errors.append(f'priority_calibrations[{index}].{score_field} must be between 0 and 10')
        contributors = row.get('scoring_contributors')
        if not isinstance(contributors, Mapping):
            errors.append(f'priority_calibrations[{index}].scoring_contributors must be an object')
            continue
        calculated_priority = 0.0
        for signal in PRIORITY_SIGNALS:
            detail = contributors.get(signal)
            if not isinstance(detail, Mapping):
                errors.append(f'priority_calibrations[{index}].scoring_contributors.{signal} must be an object')
                continue
            weight = detail.get('weight')
            score = detail.get('score')
            contribution = detail.get('weighted_contribution')
            if any((isinstance(value, bool) or not isinstance(value, (int, float)) for value in (weight, score, contribution))):
                errors.append(f'priority_calibrations[{index}].scoring_contributors.{signal} fields must be numeric')
                continue
            expected_contribution = round(float(weight) * float(score), 4)
            if abs(float(contribution) - expected_contribution) > 1e-06:
                errors.append(f'priority_calibrations[{index}].scoring_contributors.{signal}.weighted_contribution mismatch')
            calculated_priority += float(contribution)
        priority_score = row.get('priority_score')
        if isinstance(priority_score, bool) or not isinstance(priority_score, (int, float)):
            errors.append(f'priority_calibrations[{index}].priority_score must be numeric')
            continue
        priority_score_float = float(priority_score)
        if abs(priority_score_float - round(calculated_priority, 4)) > 1e-06:
            errors.append(f'priority_calibrations[{index}].priority_score must equal contributor sum')
        if priority_score_float > previous_priority_score + 1e-09:
            errors.append('priority_calibrations must be sorted by descending priority_score')
        previous_priority_score = priority_score_float
        evidence_refs = row.get('evidence_refs')
        if not isinstance(evidence_refs, list) or not evidence_refs:
            errors.append(f'priority_calibrations[{index}].evidence_refs must be a non-empty array')
    processing_behavior = payload.get('processing_behavior')
    if not isinstance(processing_behavior, Mapping):
        errors.append('processing_behavior must be an object')
        processing_behavior = {}
    context_inputs = processing_behavior.get('context_inputs')
    if not isinstance(context_inputs, Mapping):
        errors.append('processing_behavior.context_inputs must be an object')
        context_inputs = {}
    else:
        broad_sweep_context = context_inputs.get('broad_sweep_context')
        if not isinstance(broad_sweep_context, Mapping):
            errors.append('processing_behavior.context_inputs.broad_sweep_context must be an object')
    context_usage = processing_behavior.get('context_usage')
    if not isinstance(context_usage, Mapping):
        errors.append('processing_behavior.context_usage must be an object')
        context_usage = {}
    else:
        if not isinstance(context_usage.get('cross_project_context_used'), bool):
            errors.append('processing_behavior.context_usage.cross_project_context_used must be boolean')
        for field_name in ('context_project_ids', 'earth_sweep_evidence_refs_used', 'approved_cross_project_obligation_ids', 'open_risk_ids', 'evidence_refs_used'):
            value = context_usage.get(field_name)
            if not isinstance(value, list):
                errors.append(f'processing_behavior.context_usage.{field_name} must be an array')
    recommendation = processing_behavior.get('recommendation')
    if not isinstance(recommendation, Mapping):
        errors.append('processing_behavior.recommendation must be an object')
        recommendation = {}
    else:
        required_recommendation_fields = {'decision', 'rationale', 'evidence_refs', 'context_project_ids', 'approved_cross_project_obligations', 'open_risks'}
        missing_recommendation_fields = sorted(required_recommendation_fields - set(recommendation.keys()))
        if missing_recommendation_fields:
            errors.append('processing_behavior.recommendation missing field(s): ' + ', '.join(missing_recommendation_fields))
        recommendation_refs = recommendation.get('evidence_refs')
        if not isinstance(recommendation_refs, list) or not recommendation_refs:
            errors.append('processing_behavior.recommendation.evidence_refs must be a non-empty array')
        obligations = recommendation.get('approved_cross_project_obligations')
        if not isinstance(obligations, list):
            errors.append('processing_behavior.recommendation.approved_cross_project_obligations must be an array')
            obligations = []
        for index, row in enumerate(obligations):
            if not isinstance(row, Mapping):
                errors.append(f'processing_behavior.recommendation.approved_cross_project_obligations[{index}] must be an object')
                continue
            for field_name in ('obligation_id', 'summary'):
                text_value = _as_text(row.get(field_name))
                if not text_value:
                    errors.append(f'processing_behavior.recommendation.approved_cross_project_obligations[{index}].{field_name} is required')
            evidence_refs = row.get('evidence_refs')
            if not isinstance(evidence_refs, list) or not evidence_refs:
                errors.append(f'processing_behavior.recommendation.approved_cross_project_obligations[{index}].evidence_refs must be a non-empty array')
        open_risks = recommendation.get('open_risks')
        if not isinstance(open_risks, list):
            errors.append('processing_behavior.recommendation.open_risks must be an array')
            open_risks = []
        for index, row in enumerate(open_risks):
            if not isinstance(row, Mapping):
                errors.append(f'processing_behavior.recommendation.open_risks[{index}] must be an object')
                continue
            for field_name in ('risk_id', 'summary', 'reason_code'):
                text_value = _as_text(row.get(field_name))
                if not text_value:
                    errors.append(f'processing_behavior.recommendation.open_risks[{index}].{field_name} is required')
            for field_name in ('required_evidence_refs', 'context_project_ids', 'evidence_refs'):
                value = row.get(field_name)
                if not isinstance(value, list):
                    errors.append(f'processing_behavior.recommendation.open_risks[{index}].{field_name} must be an array')
    call_metadata = payload.get('call_metadata')
    if not isinstance(call_metadata, Mapping):
        errors.append('call_metadata must be an object')
        call_metadata = {}
    trace_rows = call_metadata.get('llm_call_trace_rows')
    if not isinstance(trace_rows, list) or not trace_rows:
        errors.append('call_metadata.llm_call_trace_rows must be a non-empty array')
        trace_rows = []
    elif len(trace_rows) != len(rows):
        errors.append('call_metadata.llm_call_trace_rows must have one row per priority calibration')
    expected_sequence = 1
    for index, trace_row in enumerate(trace_rows):
        if not isinstance(trace_row, Mapping):
            errors.append(f'call_metadata.llm_call_trace_rows[{index}] must be an object')
            continue
        if trace_row.get('sequence') != expected_sequence:
            errors.append(f'call_metadata.llm_call_trace_rows[{index}].sequence must be {expected_sequence}')
        expected_sequence += 1
        for text_field in ('call_objective', 'handoff_summary', 'call_id', 'plan_id', 'processing_call_id'):
            if not _as_text(trace_row.get(text_field)):
                errors.append(f'call_metadata.llm_call_trace_rows[{index}].{text_field} must be a non-empty string')
        for list_field in ('input_refs', 'output_refs', 'depends_on'):
            value = trace_row.get(list_field)
            if not isinstance(value, list):
                errors.append(f'call_metadata.llm_call_trace_rows[{index}].{list_field} must be an array')
    _emit_event(emit, level='INFO', message=f'REQ-038 validation finished with {len(errors)} issue(s).')
    return errors

def build_req_041_recommendation_dependency_effect_modeling(*, target_project_root: str=DEFAULT_TARGET_PROJECT_ROOT, earth_root: str=DEFAULT_EARTH_ROOT, output_root: str=DEFAULT_OUTPUT_ROOT, revision_identity: str=DEFAULT_REQ_041_REVISION_ID, recommendations: Sequence[Mapping[str, Any]], broad_sweep_context: Mapping[str, Any] | None=None, modeled_at: str | None=None, persist_llm_call_trace: bool=False, trace_root: str | Path | None=None, emit: EmitFn | None=None) -> dict[str, Any]:
    """Build the REQ-041 recommendation dependency-effect modeling payload."""
    _emit_event(emit, level='INFO', message='Starting REQ-041 recommendation dependency-effect modeling build.')
    normalized_target_project_root = _normalize_root(target_project_root, field_name='target_project_root')
    normalized_earth_root = _normalize_root(earth_root, field_name='earth_root')
    normalized_output_root = _normalize_root(output_root, field_name='output_root')
    normalized_revision_identity = _require_text(revision_identity, field_name='revision_identity')
    normalized_modeled_at = _require_text(modeled_at, field_name='modeled_at') if modeled_at else utc_now_iso()
    normalized_recommendations = _normalize_dependency_effect_recommendations(recommendations)
    normalized_broad_sweep_context = _normalize_broad_sweep_context(broad_sweep_context)
    _emit_event(emit, level='INFO', message=f"REQ-041 input normalized: recommendations={len(normalized_recommendations)}, context_projects={len(normalized_broad_sweep_context['context_project_ids'])}.")
    canonical_input = {'runtime_mode': RUNTIME_MODE, 'execution_mode': EXECUTION_MODE, 'target_project_root': normalized_target_project_root, 'earth_root': normalized_earth_root, 'output_root': normalized_output_root, 'revision_identity': normalized_revision_identity, 'modeled_at': normalized_modeled_at}
    canonical_input_sha256 = _canonical_sha256(canonical_input)
    canonical_processing_input = {'recommendations': normalized_recommendations, 'broad_sweep_context': normalized_broad_sweep_context}
    processing_input_sha256 = _canonical_sha256(canonical_processing_input)
    call_plan_id = f'req041-plan-{processing_input_sha256[:16]}'
    processing_call_id = f'req041-processing-{processing_input_sha256[:16]}'
    modeled_project_ids = _collect_unique_refs(*(row['affected_project_ids'] for row in normalized_recommendations))
    context_input_refs = _collect_unique_refs(normalized_broad_sweep_context['earth_sweep_evidence_refs'], *(row['evidence_refs'] for row in normalized_broad_sweep_context['proposed_cross_project_obligations']), *(row['evidence_refs'] for row in normalized_broad_sweep_context['unresolved_ideas']))
    llm_call_trace_rows: list[dict[str, Any]] = []
    latest_call_id_by_project_id: dict[str, str] = {}
    call_output_ref_by_call_id: dict[str, str] = {}
    for index, row in enumerate(normalized_recommendations, start=1):
        call_id = f"req041-call-{index:02d}-{hashlib.sha256(row['recommendation_id'].encode('utf-8')).hexdigest()[:10]}"
        depends_on = _req_041_depends_on_call_ids(affected_project_ids=row['affected_project_ids'], latest_call_id_by_project_id=latest_call_id_by_project_id)
        dependency_output_refs = [call_output_ref_by_call_id[dependency_call_id] for dependency_call_id in depends_on if dependency_call_id in call_output_ref_by_call_id]
        dependency_effect_output_ref = f'{call_plan_id}::call::{call_id}::output::dependency_effect_model_{index:02d}'
        llm_call_trace_rows.append({'schema_version': REQ_041_LLM_CALL_TRACE_SCHEMA_VERSION, 'requirement_id': REQ_041_REQUIREMENT_ID, 'plan_id': call_plan_id, 'processing_call_id': processing_call_id, 'call_id': call_id, 'sequence': index, 'call_objective': f"Model dependency effects for {row['recommendation_id']} across {row['affected_project_count']} affected project(s).", 'depends_on': depends_on, 'expected_output': f"dependency_effect_model_{index:02d}_{row['recommendation_id'].replace('.', '-')}", 'input_refs': _collect_unique_refs(row['evidence_refs'], context_input_refs, dependency_output_refs), 'output_refs': [dependency_effect_output_ref, f'{LLM_CALL_TRACE_RELATIVE_PATH}#L{index}', f"{REQ_041_SURFACE}::recommendation::{row['recommendation_id']}"], 'handoff_summary': f"Call {index} modeled {row['blocker_count']} likely blocker(s) and {row['mitigation_hook_count']} mitigation hook(s) for {row['recommendation_id']}."})
        call_output_ref_by_call_id[call_id] = dependency_effect_output_ref
        for affected_project_id in row['affected_project_ids']:
            latest_call_id_by_project_id[affected_project_id] = call_id
    llm_call_trace_jsonl = _serialize_llm_call_trace_rows(llm_call_trace_rows)
    llm_call_trace_jsonl_sha256 = hashlib.sha256(llm_call_trace_jsonl.encode('utf-8')).hexdigest()
    evidence_refs = _collect_unique_refs(*(row['evidence_refs'] for row in normalized_recommendations))
    all_project_effects = [project_effect for row in normalized_recommendations for project_effect in row['affected_project_effects']]
    all_blockers = [blocker for project_effect in all_project_effects for blocker in project_effect['likely_blockers']]
    processing_recommendation = _build_req_041_processing_recommendation(broad_sweep_context=normalized_broad_sweep_context, baseline_evidence_refs=evidence_refs, modeled_project_ids=modeled_project_ids)
    context_usage = processing_recommendation['context_usage']
    recommendation = processing_recommendation['recommendation']
    evidence_refs = _collect_unique_refs(evidence_refs, recommendation['evidence_refs'])
    payload = {'requirement_id': REQ_041_REQUIREMENT_ID, 'surface': REQ_041_SURFACE, 'schema_version': REQ_041_SCHEMA_VERSION, 'recommendation_dependency_effect_modeling_entrypoint': {'runtime_mode': RUNTIME_MODE, 'execution_mode': EXECUTION_MODE, 'target_project_root': normalized_target_project_root, 'earth_root': normalized_earth_root, 'output_root': normalized_output_root, 'revision_identity': normalized_revision_identity, 'modeled_at': normalized_modeled_at}, 'processing_behavior': {'modeling_method': 'per-recommendation-affected-project-rollup', 'auditability': 'Each recommendation records affected-project dependency effects with likely blockers and mitigation hooks.', 'sort_rule': 'Sort recommendation models by recommendation_id asc, affected_project_effects by project_id asc, likely_blockers by blocker_id asc, mitigation_hooks by hook_id asc.', 'context_inputs': {'broad_sweep_context': normalized_broad_sweep_context}, 'context_usage': context_usage, 'recommendation': recommendation}, 'call_metadata': {'reproducibility': 'deterministic-input-fingerprint', 'canonical_input_sha256': canonical_input_sha256, 'reproducible_call_id': f'req041-{canonical_input_sha256[:16]}', 'canonical_input': canonical_input, 'processing_input_sha256': processing_input_sha256, 'processing_call_id': processing_call_id, 'canonical_processing_input': canonical_processing_input, 'llm_call_trace_schema_version': REQ_041_LLM_CALL_TRACE_SCHEMA_VERSION, 'llm_call_trace_serialization': LLM_CALL_TRACE_SERIALIZATION, 'llm_call_trace_path': LLM_CALL_TRACE_RELATIVE_PATH, 'llm_call_trace_row_count': len(llm_call_trace_rows), 'llm_call_trace_jsonl_sha256': llm_call_trace_jsonl_sha256, 'llm_call_trace_sha256': _canonical_sha256({'rows': llm_call_trace_rows}), 'llm_call_trace_rows': llm_call_trace_rows}, 'modeled_at': normalized_modeled_at, 'dependency_effect_models': normalized_recommendations, 'evidence_refs': evidence_refs, 'summary': {'recommendation_count': len(normalized_recommendations), 'affected_project_count': len(all_project_effects), 'likely_blocker_count': len(all_blockers), 'mitigation_hook_count': sum((int(project_effect['mitigation_hook_count']) for project_effect in all_project_effects)), 'highest_blocker_severity': _highest_blocker_severity(all_blockers)}}
    if persist_llm_call_trace:
        payload['call_metadata']['llm_call_trace_artifact'] = _write_llm_call_trace(llm_call_trace_jsonl, trace_root=trace_root, emit=emit)
    _emit_event(emit, level='INFO', message=f"REQ-041 build complete: recommendations={payload['summary']['recommendation_count']}, affected_projects={payload['summary']['affected_project_count']}.")
    return payload

def validate_req_041_recommendation_dependency_effect_modeling(payload: Mapping[str, Any], *, emit: EmitFn | None=None) -> list[str]:
    """Validate a REQ-041 recommendation dependency-effect modeling payload."""
    _emit_event(emit, level='INFO', message='Validating REQ-041 recommendation dependency-effect modeling payload.')
    errors: list[str] = []
    required_top_level = {'requirement_id', 'surface', 'schema_version', 'recommendation_dependency_effect_modeling_entrypoint', 'processing_behavior', 'call_metadata', 'modeled_at', 'dependency_effect_models', 'evidence_refs', 'summary'}
    missing = sorted(required_top_level - set(payload.keys()))
    if missing:
        errors.append(f"missing top-level key(s): {', '.join(missing)}")
    if payload.get('requirement_id') != REQ_041_REQUIREMENT_ID:
        errors.append('requirement_id must be REQ-041')
    if payload.get('surface') != REQ_041_SURFACE:
        errors.append('surface must be recommendation_dependency_effect_modeling')
    if payload.get('schema_version') != REQ_041_SCHEMA_VERSION:
        errors.append('schema_version mismatch for REQ-041')
    processing_behavior = payload.get('processing_behavior')
    if not isinstance(processing_behavior, Mapping):
        errors.append('processing_behavior must be an object')
        processing_behavior = {}
    context_inputs = processing_behavior.get('context_inputs')
    if not isinstance(context_inputs, Mapping):
        errors.append('processing_behavior.context_inputs must be an object')
        context_inputs = {}
    else:
        broad_sweep_context = context_inputs.get('broad_sweep_context')
        if not isinstance(broad_sweep_context, Mapping):
            errors.append('processing_behavior.context_inputs.broad_sweep_context must be an object')
    context_usage = processing_behavior.get('context_usage')
    if not isinstance(context_usage, Mapping):
        errors.append('processing_behavior.context_usage must be an object')
        context_usage = {}
    else:
        if not isinstance(context_usage.get('cross_project_context_used'), bool):
            errors.append('processing_behavior.context_usage.cross_project_context_used must be boolean')
        for field_name in ('modeled_project_ids', 'context_project_ids', 'earth_sweep_evidence_refs_used', 'approved_cross_project_obligation_ids', 'open_risk_ids', 'evidence_refs_used'):
            value = context_usage.get(field_name)
            if not isinstance(value, list):
                errors.append(f'processing_behavior.context_usage.{field_name} must be an array')
    recommendation = processing_behavior.get('recommendation')
    if not isinstance(recommendation, Mapping):
        errors.append('processing_behavior.recommendation must be an object')
        recommendation = {}
    else:
        required_recommendation_fields = {'decision', 'rationale', 'evidence_refs', 'context_project_ids', 'approved_cross_project_obligations', 'open_risks'}
        missing_recommendation_fields = sorted(required_recommendation_fields - set(recommendation.keys()))
        if missing_recommendation_fields:
            errors.append('processing_behavior.recommendation missing field(s): ' + ', '.join(missing_recommendation_fields))
        recommendation_refs = recommendation.get('evidence_refs')
        if not isinstance(recommendation_refs, list) or not recommendation_refs:
            errors.append('processing_behavior.recommendation.evidence_refs must be a non-empty array')
        obligations = recommendation.get('approved_cross_project_obligations')
        if not isinstance(obligations, list):
            errors.append('processing_behavior.recommendation.approved_cross_project_obligations must be an array')
            obligations = []
        for index, row in enumerate(obligations):
            if not isinstance(row, Mapping):
                errors.append(f'processing_behavior.recommendation.approved_cross_project_obligations[{index}] must be an object')
                continue
            for field_name in ('obligation_id', 'summary'):
                text_value = _as_text(row.get(field_name))
                if not text_value:
                    errors.append(f'processing_behavior.recommendation.approved_cross_project_obligations[{index}].{field_name} is required')
            evidence_refs = row.get('evidence_refs')
            if not isinstance(evidence_refs, list) or not evidence_refs:
                errors.append(f'processing_behavior.recommendation.approved_cross_project_obligations[{index}].evidence_refs must be a non-empty array')
        open_risks = recommendation.get('open_risks')
        if not isinstance(open_risks, list):
            errors.append('processing_behavior.recommendation.open_risks must be an array')
            open_risks = []
        for index, row in enumerate(open_risks):
            if not isinstance(row, Mapping):
                errors.append(f'processing_behavior.recommendation.open_risks[{index}] must be an object')
                continue
            for field_name in ('risk_id', 'summary', 'reason_code'):
                text_value = _as_text(row.get(field_name))
                if not text_value:
                    errors.append(f'processing_behavior.recommendation.open_risks[{index}].{field_name} is required')
            for field_name in ('required_evidence_refs', 'context_project_ids', 'evidence_refs'):
                value = row.get(field_name)
                if not isinstance(value, list):
                    errors.append(f'processing_behavior.recommendation.open_risks[{index}].{field_name} must be an array')
    models = payload.get('dependency_effect_models')
    if not isinstance(models, list) or not models:
        errors.append('dependency_effect_models must be a non-empty array')
        models = []
    previous_recommendation_id = ''
    total_project_count = 0
    total_blocker_count = 0
    total_hook_count = 0
    collected_blockers: list[Mapping[str, Any]] = []
    for model_index, model in enumerate(models):
        if not isinstance(model, Mapping):
            errors.append(f'dependency_effect_models[{model_index}] must be an object')
            continue
        recommendation_id = _as_text(model.get('recommendation_id'))
        if not recommendation_id:
            errors.append(f'dependency_effect_models[{model_index}].recommendation_id must be a non-empty string')
        elif previous_recommendation_id and recommendation_id < previous_recommendation_id:
            errors.append('dependency_effect_models must be sorted by recommendation_id')
        previous_recommendation_id = recommendation_id or previous_recommendation_id
        for text_field in ('summary', 'rationale', 'highest_blocker_severity'):
            if not _as_text(model.get(text_field)):
                errors.append(f'dependency_effect_models[{model_index}].{text_field} must be a non-empty string')
        affected_project_ids = model.get('affected_project_ids')
        if not isinstance(affected_project_ids, list) or not affected_project_ids:
            errors.append(f'dependency_effect_models[{model_index}].affected_project_ids must be a non-empty array')
            affected_project_ids = []
        project_effects = model.get('affected_project_effects')
        if not isinstance(project_effects, list) or not project_effects:
            errors.append(f'dependency_effect_models[{model_index}].affected_project_effects must be a non-empty array')
            project_effects = []
        counted_blockers = 0
        counted_hooks = 0
        expected_project_ids: list[str] = []
        model_blockers: list[Mapping[str, Any]] = []
        previous_project_id = ''
        for effect_index, project_effect in enumerate(project_effects):
            if not isinstance(project_effect, Mapping):
                errors.append(f'dependency_effect_models[{model_index}].affected_project_effects[{effect_index}] must be an object')
                continue
            project_id = _as_text(project_effect.get('project_id'))
            if not project_id:
                errors.append(f'dependency_effect_models[{model_index}].affected_project_effects[{effect_index}].project_id must be a non-empty string')
            elif previous_project_id and project_id < previous_project_id:
                errors.append('affected_project_effects must be sorted by project_id')
            previous_project_id = project_id or previous_project_id
            expected_project_ids.append(project_id)
            for text_field in ('effect_type', 'dependency_effect_summary', 'highest_blocker_severity'):
                if not _as_text(project_effect.get(text_field)):
                    errors.append(f'dependency_effect_models[{model_index}].affected_project_effects[{effect_index}].{text_field} must be a non-empty string')
            blockers = project_effect.get('likely_blockers')
            if not isinstance(blockers, list) or not blockers:
                errors.append(f'dependency_effect_models[{model_index}].affected_project_effects[{effect_index}].likely_blockers must be a non-empty array')
                blockers = []
            hooks = project_effect.get('mitigation_hooks')
            if not isinstance(hooks, list) or not hooks:
                errors.append(f'dependency_effect_models[{model_index}].affected_project_effects[{effect_index}].mitigation_hooks must be a non-empty array')
                hooks = []
            if project_effect.get('blocker_count') != len(blockers):
                errors.append(f'dependency_effect_models[{model_index}].affected_project_effects[{effect_index}].blocker_count mismatch')
            if project_effect.get('mitigation_hook_count') != len(hooks):
                errors.append(f'dependency_effect_models[{model_index}].affected_project_effects[{effect_index}].mitigation_hook_count mismatch')
            previous_blocker_id = ''
            for blocker_index, blocker in enumerate(blockers):
                if not isinstance(blocker, Mapping):
                    errors.append(f'dependency_effect_models[{model_index}].affected_project_effects[{effect_index}].likely_blockers[{blocker_index}] must be an object')
                    continue
                blocker_id = _as_text(blocker.get('blocker_id'))
                if not blocker_id:
                    errors.append(f'dependency_effect_models[{model_index}].affected_project_effects[{effect_index}].likely_blockers[{blocker_index}].blocker_id must be a non-empty string')
                elif previous_blocker_id and blocker_id < previous_blocker_id:
                    errors.append('likely_blockers must be sorted by blocker_id')
                previous_blocker_id = blocker_id or previous_blocker_id
                if not _as_text(blocker.get('summary')):
                    errors.append(f'dependency_effect_models[{model_index}].affected_project_effects[{effect_index}].likely_blockers[{blocker_index}].summary must be a non-empty string')
                severity = _as_text(blocker.get('severity')).lower()
                if severity not in BLOCKER_SEVERITY_ORDER:
                    errors.append(f"dependency_effect_models[{model_index}].affected_project_effects[{effect_index}].likely_blockers[{blocker_index}].severity must be one of: {', '.join(BLOCKER_SEVERITY_ORDER)}")
                evidence_refs = blocker.get('evidence_refs')
                if not isinstance(evidence_refs, list) or not evidence_refs:
                    errors.append(f'dependency_effect_models[{model_index}].affected_project_effects[{effect_index}].likely_blockers[{blocker_index}].evidence_refs must be a non-empty array')
                collected_blockers.append(blocker)
                model_blockers.append(blocker)
            previous_hook_id = ''
            for hook_index, hook in enumerate(hooks):
                if not isinstance(hook, Mapping):
                    errors.append(f'dependency_effect_models[{model_index}].affected_project_effects[{effect_index}].mitigation_hooks[{hook_index}] must be an object')
                    continue
                hook_id = _as_text(hook.get('hook_id'))
                if not hook_id:
                    errors.append(f'dependency_effect_models[{model_index}].affected_project_effects[{effect_index}].mitigation_hooks[{hook_index}].hook_id must be a non-empty string')
                elif previous_hook_id and hook_id < previous_hook_id:
                    errors.append('mitigation_hooks must be sorted by hook_id')
                previous_hook_id = hook_id or previous_hook_id
                for text_field in ('summary', 'hook_type'):
                    if not _as_text(hook.get(text_field)):
                        errors.append(f'dependency_effect_models[{model_index}].affected_project_effects[{effect_index}].mitigation_hooks[{hook_index}].{text_field} must be a non-empty string')
                evidence_refs = hook.get('evidence_refs')
                if not isinstance(evidence_refs, list) or not evidence_refs:
                    errors.append(f'dependency_effect_models[{model_index}].affected_project_effects[{effect_index}].mitigation_hooks[{hook_index}].evidence_refs must be a non-empty array')
            if project_effect.get('highest_blocker_severity') != _highest_blocker_severity(blockers):
                errors.append(f'dependency_effect_models[{model_index}].affected_project_effects[{effect_index}].highest_blocker_severity mismatch')
            evidence_refs = project_effect.get('evidence_refs')
            if not isinstance(evidence_refs, list) or not evidence_refs:
                errors.append(f'dependency_effect_models[{model_index}].affected_project_effects[{effect_index}].evidence_refs must be a non-empty array')
            counted_blockers += len(blockers)
            counted_hooks += len(hooks)
        if model.get('affected_project_count') != len(project_effects):
            errors.append(f'dependency_effect_models[{model_index}].affected_project_count mismatch')
        if model.get('blocker_count') != counted_blockers:
            errors.append(f'dependency_effect_models[{model_index}].blocker_count mismatch')
        if model.get('mitigation_hook_count') != counted_hooks:
            errors.append(f'dependency_effect_models[{model_index}].mitigation_hook_count mismatch')
        if affected_project_ids != expected_project_ids:
            errors.append(f'dependency_effect_models[{model_index}].affected_project_ids must match project effect order')
        if model.get('highest_blocker_severity') != _highest_blocker_severity(model_blockers):
            errors.append(f'dependency_effect_models[{model_index}].highest_blocker_severity mismatch')
        evidence_refs = model.get('evidence_refs')
        if not isinstance(evidence_refs, list) or not evidence_refs:
            errors.append(f'dependency_effect_models[{model_index}].evidence_refs must be a non-empty array')
        total_project_count += len(project_effects)
        total_blocker_count += counted_blockers
        total_hook_count += counted_hooks
    summary = payload.get('summary')
    if not isinstance(summary, Mapping):
        errors.append('summary must be an object')
        summary = {}
    else:
        if summary.get('recommendation_count') != len(models):
            errors.append('summary.recommendation_count mismatch')
        if summary.get('affected_project_count') != total_project_count:
            errors.append('summary.affected_project_count mismatch')
        if summary.get('likely_blocker_count') != total_blocker_count:
            errors.append('summary.likely_blocker_count mismatch')
        if summary.get('mitigation_hook_count') != total_hook_count:
            errors.append('summary.mitigation_hook_count mismatch')
        if summary.get('highest_blocker_severity') != _highest_blocker_severity(collected_blockers):
            errors.append('summary.highest_blocker_severity mismatch')
    call_metadata = payload.get('call_metadata')
    if not isinstance(call_metadata, Mapping):
        errors.append('call_metadata must be an object')
        call_metadata = {}
    trace_rows = call_metadata.get('llm_call_trace_rows')
    if not isinstance(trace_rows, list) or not trace_rows:
        errors.append('call_metadata.llm_call_trace_rows must be a non-empty array')
        trace_rows = []
    elif len(trace_rows) != len(models):
        errors.append('call_metadata.llm_call_trace_rows must have one row per dependency effect model')
    if isinstance(call_metadata.get('llm_call_trace_row_count'), int):
        if call_metadata.get('llm_call_trace_row_count') != len(trace_rows):
            errors.append('call_metadata.llm_call_trace_row_count mismatch')
    expected_sequence = 1
    seen_call_ids: set[str] = set()
    for index, trace_row in enumerate(trace_rows):
        if not isinstance(trace_row, Mapping):
            errors.append(f'call_metadata.llm_call_trace_rows[{index}] must be an object')
            continue
        if trace_row.get('sequence') != expected_sequence:
            errors.append(f'call_metadata.llm_call_trace_rows[{index}].sequence must be {expected_sequence}')
        expected_sequence += 1
        call_id = _as_text(trace_row.get('call_id'))
        if call_id in seen_call_ids:
            errors.append(f'call_metadata.llm_call_trace_rows[{index}].call_id must be unique')
        elif call_id:
            seen_call_ids.add(call_id)
        for text_field in ('call_objective', 'handoff_summary', 'call_id', 'plan_id', 'processing_call_id'):
            if not _as_text(trace_row.get(text_field)):
                errors.append(f'call_metadata.llm_call_trace_rows[{index}].{text_field} must be a non-empty string')
        for list_field in ('input_refs', 'output_refs', 'depends_on'):
            value = trace_row.get(list_field)
            if not isinstance(value, list):
                errors.append(f'call_metadata.llm_call_trace_rows[{index}].{list_field} must be an array')
                continue
            if list_field in {'input_refs', 'output_refs'} and (not value):
                errors.append(f'call_metadata.llm_call_trace_rows[{index}].{list_field} must be a non-empty array')
            for value_index, item in enumerate(value):
                if not _as_text(item):
                    errors.append(f'call_metadata.llm_call_trace_rows[{index}].{list_field}[{value_index}] must be a non-empty string')
        depends_on = trace_row.get('depends_on')
        if isinstance(depends_on, list):
            seen_depends_on: set[str] = set()
            for dependency_index, dependency_call_id in enumerate(depends_on):
                dependency_call_id_text = _as_text(dependency_call_id)
                if not dependency_call_id_text:
                    continue
                if dependency_call_id_text in seen_depends_on:
                    errors.append(f"call_metadata.llm_call_trace_rows[{index}].depends_on[{dependency_index}] duplicates '{dependency_call_id_text}'")
                    continue
                seen_depends_on.add(dependency_call_id_text)
                if dependency_call_id_text == call_id:
                    errors.append(f'call_metadata.llm_call_trace_rows[{index}].depends_on[{dependency_index}] must not reference call_id')
                if dependency_call_id_text not in seen_call_ids:
                    errors.append(f'call_metadata.llm_call_trace_rows[{index}].depends_on[{dependency_index}] must reference a prior call_id')
    _emit_event(emit, level='INFO', message=f'REQ-041 validation finished with {len(errors)} issue(s).')
    return errors


_build_req_041_recommendation_dependency_effect_modeling_rich = (
    build_req_041_recommendation_dependency_effect_modeling
)


def build_req_041_recommendation_dependency_effect_modeling_legacy_compat(*, target_project_root: str=DEFAULT_TARGET_PROJECT_ROOT, earth_root: str=DEFAULT_EARTH_ROOT, output_root: str=DEFAULT_OUTPUT_ROOT, revision_identity: str=DEFAULT_REQ_041_REVISION_ID, recommendations: Sequence[Mapping[str, Any]], broad_sweep_context: Mapping[str, Any] | None=None, modeled_at: str | None=None, persist_llm_call_trace: bool=False, trace_root: str | Path | None=None, emit: EmitFn | None=None) -> dict[str, Any]:
    payload = _build_req_041_recommendation_dependency_effect_modeling_rich(
        target_project_root=target_project_root,
        earth_root=earth_root,
        output_root=output_root,
        revision_identity=revision_identity,
        recommendations=recommendations,
        broad_sweep_context=broad_sweep_context,
        modeled_at=modeled_at,
        persist_llm_call_trace=False,
        trace_root=None,
        emit=emit,
    )
    payload['processing_behavior'] = {
        'auditability': payload['processing_behavior']['auditability'],
        'modeling_method': payload['processing_behavior']['modeling_method'],
        'sort_rule': payload['processing_behavior']['sort_rule'],
    }
    metadata = dict(payload['call_metadata'])
    canonical_processing_input = {'recommendations': [dict(row) for row in payload['dependency_effect_models']]}
    processing_input_sha256 = _canonical_sha256(canonical_processing_input)
    processing_call_id = f'req041-processing-{processing_input_sha256[:16]}'
    plan_id = f'req041-plan-{processing_input_sha256[:16]}'
    llm_call_trace_rows = metadata.get('llm_call_trace_rows', [])
    transformed_trace_rows: list[dict[str, Any]] = []
    previous_call_id = ''
    for row in llm_call_trace_rows:
        if not isinstance(row, Mapping):
            continue
        call_id = _as_text(row.get('call_id'))
        sequence = row.get('sequence')
        if isinstance(sequence, int) and sequence > 0:
            output_ref = f'{plan_id}::call::{call_id}::output::dependency_effect_model_{sequence:02d}'
        else:
            output_ref = row.get('output_refs', [None])[0]
        depends_on: list[str] = []
        if previous_call_id:
            depends_on = [previous_call_id]
        transformed_trace_rows.append(
            {
                'schema_version': row.get('schema_version'),
                'requirement_id': row.get('requirement_id'),
                'plan_id': plan_id,
                'processing_call_id': processing_call_id,
                'call_id': call_id,
                'sequence': sequence,
                'call_objective': row.get('call_objective'),
                'depends_on': depends_on,
                'expected_output': row.get('expected_output'),
                'input_refs': row.get('input_refs'),
                'output_refs': [output_ref, f'{LLM_CALL_TRACE_RELATIVE_PATH}#L{sequence}'],
                'handoff_summary': row.get('handoff_summary'),
            }
        )
        previous_call_id = call_id
    llm_call_trace_jsonl = _serialize_llm_call_trace_rows(transformed_trace_rows)
    llm_call_trace_artifact: dict[str, Any] | None = None
    if persist_llm_call_trace:
        llm_call_trace_artifact = _write_llm_call_trace(
            llm_call_trace_jsonl,
            trace_root=trace_root,
            emit=emit,
        )
    call_metadata: dict[str, Any] = {
        'reproducibility': metadata.get('reproducibility'),
        'canonical_input_sha256': metadata.get('canonical_input_sha256'),
        'reproducible_call_id': metadata.get('reproducible_call_id'),
        'canonical_input': metadata.get('canonical_input'),
        'processing_input_sha256': processing_input_sha256,
        'processing_call_id': processing_call_id,
        'canonical_processing_input': canonical_processing_input,
        'llm_call_trace_schema_version': metadata.get('llm_call_trace_schema_version'),
        'llm_call_trace_serialization': LLM_CALL_TRACE_SERIALIZATION,
        'llm_call_trace_path': metadata.get('llm_call_trace_path'),
        'llm_call_trace_row_count': len(transformed_trace_rows),
        'llm_call_trace_jsonl_sha256': hashlib.sha256(llm_call_trace_jsonl.encode('utf-8')).hexdigest(),
        'llm_call_trace_sha256': _canonical_sha256({'rows': transformed_trace_rows}),
        'llm_call_trace_rows': transformed_trace_rows,
    }
    if llm_call_trace_artifact is not None:
        call_metadata['llm_call_trace_artifact'] = llm_call_trace_artifact
    payload['call_metadata'] = call_metadata
    return payload


def validate_req_041_recommendation_dependency_effect_modeling_legacy_compat(payload: Mapping[str, Any], *, emit: EmitFn | None=None) -> list[str]:
    if not isinstance(payload, Mapping):
        return ['payload must be a JSON object']
    errors: list[str] = []
    models = payload.get('dependency_effect_models')
    if isinstance(models, list):
        for model_index, model in enumerate(models):
            if not isinstance(model, Mapping):
                continue
            project_effects = model.get('affected_project_effects')
            if not isinstance(project_effects, list):
                continue
            for effect_index, project_effect in enumerate(project_effects):
                if not isinstance(project_effect, Mapping):
                    continue
                mitigation_hooks = project_effect.get('mitigation_hooks')
                if not isinstance(mitigation_hooks, list) or not mitigation_hooks:
                    errors.append(
                        f'dependency_effect_models[{model_index}].affected_project_effects[{effect_index}].mitigation_hooks must be a non-empty array'
                    )
    if errors:
        return errors
    try:
        entrypoint = _require_mapping(
            payload.get('recommendation_dependency_effect_modeling_entrypoint'),
            field_name='recommendation_dependency_effect_modeling_entrypoint',
        )
        expected = build_req_041_recommendation_dependency_effect_modeling_legacy_compat(
            target_project_root=entrypoint.get('target_project_root', DEFAULT_TARGET_PROJECT_ROOT),
            earth_root=entrypoint.get('earth_root', DEFAULT_EARTH_ROOT),
            output_root=entrypoint.get('output_root', DEFAULT_OUTPUT_ROOT),
            revision_identity=entrypoint.get('revision_identity', DEFAULT_REQ_041_REVISION_ID),
            recommendations=payload.get('dependency_effect_models'),
            modeled_at=payload.get('modeled_at'),
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
        return ['payload must mirror deterministic REQ-041 dependency-effect modeling output']
    return []
