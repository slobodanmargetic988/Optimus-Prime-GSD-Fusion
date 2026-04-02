#!/usr/bin/env python3
'REQ-036 and REQ-040 contract/data-model surfaces for strategy LLM pipeline.'

from __future__ import annotations

import hashlib

import json

from pathlib import Path

from typing import Any, Mapping, Sequence

REQ_040_REQUIREMENT_ID = 'REQ-040'

REQ_040_SCHEMA_VERSION = 'req-040.recommendation-feasibility-scoring.v1'

REQ_040_STRATEGY = 'resource-dependency-maturity-feasibility-scoring'

REQ_040_CONTEXT_BUNDLE_SCHEMA_VERSION = 'req-040.recommendation-feasibility-context-bundle.v1'

REQ_040_LLM_CALL_TRACE_SCHEMA_VERSION = 'req-040.llm-call-trace.v1'

REQ_040_LLM_CALL_TRACE_ROW_SCHEMA_VERSION = 'req-040.llm-call-trace-row.v1'

REQ_040_DEFAULT_LLM_CALL_TRACE_PATH = 'strategy/current/llm_call_trace.jsonl'

REQ_040_REASON_CODE_CROSS_CALL_CONTRADICTION = 'cross_call_analysis_synthesis_contradiction'

REQ_040_REASON_CODE_CITATION_DISCIPLINE = 'uncited_strategic_claim_blocked'

RUNTIME_MODE = 'llm-first'

EXECUTION_MODE = 'long-thinking'

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

def _normalize_root(value: Any, *, field_name: str) -> str:
    normalized = str(Path(_require_text(value, field_name=field_name)).expanduser().resolve())
    if not normalized.startswith('/'):
        raise ValueError(f'{field_name} must normalize to an absolute path')
    return normalized

def _normalize_string_list(raw_value: Any, *, field_name: str, min_items: int=0) -> list[str]:
    if raw_value is None:
        raw_items: Sequence[Any] = []
    else:
        if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
            raise ValueError(f'{field_name} must be an array of non-empty strings')
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

def _canonical_input_digest(canonical_input: Mapping[str, Any]) -> str:
    raw = json.dumps(canonical_input, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]

def _normalize_trace_artifact_path(value: Any) -> str:
    text = _require_text(value, field_name='llm_call_trace_path')
    return str(Path(text).as_posix())

def _resolve_trace_artifact_path(path_text: str) -> Path:
    candidate = Path(path_text).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (_repo_root() / candidate).resolve()

def _write_jsonl_rows(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    rendered = '\n'.join((json.dumps(dict(row), sort_keys=True, separators=(',', ':'), ensure_ascii=True) for row in rows))
    if rendered:
        rendered += '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + '.tmp')
    tmp_path.write_text(rendered, encoding='utf-8')
    tmp_path.replace(path)

def _canonical_call_input(*, target_project_root: str, earth_root: str, output_root: str, revision_identity: str) -> dict[str, str]:
    return {'earth_root': earth_root, 'execution_mode': EXECUTION_MODE, 'output_root': output_root, 'revision_identity': revision_identity, 'runtime_mode': RUNTIME_MODE, 'target_project_root': target_project_root}

_REQ_040_COST_TIER_ORDER = {'low': 1, 'medium': 2, 'high': 3}

_REQ_040_DEPENDENCY_STATUS_SCORES = {'ready': 1.0, 'partial': 0.6, 'blocked': 0.2}

_REQ_040_MATURITY_LEVEL_SCORES = {'bootstrap': 0.35, 'developing': 0.65, 'stable': 0.9}

_REQ_040_SCORE_WEIGHTS = {'resource_constraints': 0.4, 'dependency_readiness': 0.35, 'repo_maturity': 0.25}

def _require_integer(value: Any, *, field_name: str, minimum: int=0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f'{field_name} must be an integer')
    if value < minimum:
        raise ValueError(f'{field_name} must be >= {minimum}')
    return value

def _require_fraction(value: Any, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{field_name} must be a number between 0 and 1')
    numeric = float(value)
    if numeric < 0 or numeric > 1:
        raise ValueError(f'{field_name} must be between 0 and 1')
    return round(numeric, 3)

def _normalize_req_040_cost_tier(value: Any, *, field_name: str) -> str:
    tier = _as_text(value).lower()
    if tier not in _REQ_040_COST_TIER_ORDER:
        raise ValueError(f'{field_name} must be one of: low, medium, high')
    return tier

def _normalize_req_040_resource_constraints(raw_value: Any) -> dict[str, Any]:
    if not isinstance(raw_value, Mapping):
        raise ValueError('resource_constraints must be an object')
    return {'available_parallel_slots': _require_integer(raw_value.get('available_parallel_slots'), field_name='resource_constraints.available_parallel_slots', minimum=1), 'available_daily_tokens': _require_integer(raw_value.get('available_daily_tokens'), field_name='resource_constraints.available_daily_tokens', minimum=0), 'max_recommendation_cost_tier': _normalize_req_040_cost_tier(raw_value.get('max_recommendation_cost_tier'), field_name='resource_constraints.max_recommendation_cost_tier'), 'constrained_resources': _normalize_string_list(raw_value.get('constrained_resources'), field_name='resource_constraints.constrained_resources'), 'evidence_refs': _normalize_string_list(raw_value.get('evidence_refs'), field_name='resource_constraints.evidence_refs', min_items=1)}

def _normalize_req_040_dependency_readiness(raw_value: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError('dependency_readiness must be an array')
    normalized: list[dict[str, Any]] = []
    seen_dependency_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f'dependency_readiness[{index}] must be an object')
        dependency_id = _require_text(item.get('dependency_id'), field_name=f'dependency_readiness[{index}].dependency_id')
        if dependency_id in seen_dependency_ids:
            raise ValueError(f'dependency_readiness[{index}].dependency_id must be unique')
        seen_dependency_ids.add(dependency_id)
        readiness_status = _as_text(item.get('readiness_status')).lower()
        if readiness_status not in _REQ_040_DEPENDENCY_STATUS_SCORES:
            raise ValueError(f'dependency_readiness[{index}].readiness_status must be one of: ready, partial, blocked')
        blocker_count = _require_integer(item.get('blocker_count'), field_name=f'dependency_readiness[{index}].blocker_count', minimum=0)
        normalized.append({'dependency_id': dependency_id, 'readiness_status': readiness_status, 'blocker_count': blocker_count, 'evidence_refs': _normalize_string_list(item.get('evidence_refs'), field_name=f'dependency_readiness[{index}].evidence_refs', min_items=1)})
    if not normalized:
        raise ValueError('dependency_readiness must contain at least 1 row')
    normalized.sort(key=lambda row: row['dependency_id'])
    return normalized

def _normalize_req_040_repo_maturity(raw_value: Any) -> dict[str, Any]:
    if not isinstance(raw_value, Mapping):
        raise ValueError('repo_maturity must be an object')
    maturity_level = _as_text(raw_value.get('maturity_level')).lower()
    if maturity_level not in _REQ_040_MATURITY_LEVEL_SCORES:
        raise ValueError('repo_maturity.maturity_level must be one of: bootstrap, developing, stable')
    return {'maturity_level': maturity_level, 'test_pass_rate': _require_fraction(raw_value.get('test_pass_rate'), field_name='repo_maturity.test_pass_rate'), 'open_defect_count': _require_integer(raw_value.get('open_defect_count'), field_name='repo_maturity.open_defect_count', minimum=0), 'evidence_refs': _normalize_string_list(raw_value.get('evidence_refs'), field_name='repo_maturity.evidence_refs', min_items=1)}

def _normalize_req_040_candidate_recommendations(raw_value: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes, bytearray)):
        raise ValueError('candidate_recommendations must be an array')
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f'candidate_recommendations[{index}] must be an object')
        recommendation_id = _require_text(item.get('recommendation_id'), field_name=f'candidate_recommendations[{index}].recommendation_id')
        if recommendation_id in seen_ids:
            raise ValueError(f'candidate_recommendations[{index}].recommendation_id must be unique')
        seen_ids.add(recommendation_id)
        normalized.append({'recommendation_id': recommendation_id, 'summary': _require_text(item.get('summary'), field_name=f'candidate_recommendations[{index}].summary'), 'required_dependency_ids': _normalize_string_list(item.get('required_dependency_ids'), field_name=f'candidate_recommendations[{index}].required_dependency_ids'), 'required_cost_tier': _normalize_req_040_cost_tier(item.get('required_cost_tier'), field_name=f'candidate_recommendations[{index}].required_cost_tier'), 'evidence_refs': _normalize_string_list(item.get('evidence_refs'), field_name=f'candidate_recommendations[{index}].evidence_refs', min_items=1)})
    if not normalized:
        raise ValueError('candidate_recommendations must contain at least 1 row')
    normalized.sort(key=lambda row: row['recommendation_id'])
    return normalized

def _req_040_average(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 3)

def _req_040_dependency_row_score(*, readiness_status: str, blocker_count: int) -> float:
    base_score = _REQ_040_DEPENDENCY_STATUS_SCORES[readiness_status]
    penalty = min(0.5, blocker_count * 0.1)
    return round(max(0.0, base_score - penalty), 3)

def _req_040_summary_mentions_source(summary: str, source: str) -> bool:
    return source in summary.lower()

def _req_040_summary_indicates_analysis_synthesis_contradiction(summary: str) -> bool:
    summary_lower = summary.lower()
    if 'analysis' not in summary_lower or 'synthesis' not in summary_lower:
        return False
    contradiction_markers = ('contradict', 'conflict', 'inconsistent', 'disagree')
    return any((marker in summary_lower for marker in contradiction_markers))

def _req_040_uncited_strategic_claim_detected(*, summary: str, recommendation_evidence_refs: Sequence[str], dependency_evidence_refs: Sequence[str]) -> bool:
    mentioned_sources = [source for source in ('analysis', 'synthesis') if _req_040_summary_mentions_source(summary, source)]
    if not mentioned_sources:
        return False
    all_evidence_refs = [*recommendation_evidence_refs, *dependency_evidence_refs]
    evidence_text = ' '.join((ref.lower() for ref in all_evidence_refs))
    return any((source not in evidence_text for source in mentioned_sources))

def _build_req_040_processing_behavior(*, broad_sweep_context: Mapping[str, str], resource_constraints: Mapping[str, Any], dependency_readiness: Sequence[Mapping[str, Any]], repo_maturity: Mapping[str, Any], candidate_recommendations: Sequence[Mapping[str, Any]], feasibility_assessment: Mapping[str, Any], sequencing_policy: Mapping[str, Any], risk_policy: Mapping[str, Any]) -> dict[str, Any]:
    recommendations = feasibility_assessment.get('recommendations', [])
    recommendation_rows = [row for row in recommendations if isinstance(row, Mapping) and _as_text(row.get('recommendation_id'))]
    recommendation_lookup = {_as_text(row['recommendation_id']): row for row in recommendation_rows}
    ordered_recommendation_ids = [recommendation_id for recommendation_id in sequencing_policy.get('ordered_recommendation_ids', []) if isinstance(recommendation_id, str) and recommendation_id in recommendation_lookup]
    recommended_actions: list[dict[str, Any]] = []
    for recommendation_id in ordered_recommendation_ids:
        row = recommendation_lookup[recommendation_id]
        reason_codes = row.get('reason_codes', [])
        rationale = f"Feasibility score {row['feasibility_score']} ({row['feasibility_label']}) with policy '{row['risk_policy']}'."
        if reason_codes:
            rationale = f"{rationale} Reason codes: {', '.join(reason_codes)}."
        sequencing_bucket = row.get('sequencing_bucket')
        if sequencing_bucket == 'immediate':
            next_step = 'Sequence this recommendation in the current execution wave.'
        elif sequencing_bucket == 'next-iteration':
            next_step = 'Sequence this recommendation in the next iteration with guardrails.'
        else:
            next_step = 'Defer sequencing until controls or readiness gaps are resolved.'
        recommended_actions.append({'action_id': f'sequence-{recommendation_id}', 'summary': _as_text(row.get('summary')), 'rationale': rationale, 'next_step': next_step, 'evidence_refs': list(row.get('evidence_refs', []))})
    recommendation_evidence_refs = list(feasibility_assessment.get('evidence_refs', []))
    open_risks = list(risk_policy.get('open_risks', []))
    global_policy = _as_text(risk_policy.get('global_policy'))
    overall_feasibility_score = float(feasibility_assessment.get('overall_feasibility_score', 0.0))
    if global_policy == 'defer-high-risk-work':
        decision = 'defer-high-risk-recommendations'
    elif global_policy == 'guarded-execution':
        decision = 'execute-with-guardrails'
    else:
        decision = 'ready-for-standard-execution'
    if overall_feasibility_score >= 0.75 and (not open_risks):
        confidence = 'high'
    elif overall_feasibility_score >= 0.55:
        confidence = 'medium'
    else:
        confidence = 'low'
    rationale = f"Scored {len(recommendation_rows)} recommendations from resource constraints, dependency readiness, and repo maturity; resulting global policy is '{global_policy}'."
    return {'strategy': REQ_040_STRATEGY, 'reasoning_mode': EXECUTION_MODE, 'heuristic_summarization_only': False, 'context_inputs': {'broad_sweep_context': dict(broad_sweep_context), 'resource_constraints': dict(resource_constraints), 'dependency_readiness': [dict(row) for row in dependency_readiness], 'repo_maturity': dict(repo_maturity), 'candidate_recommendations': [dict(row) for row in candidate_recommendations]}, 'context_usage': {'recommendation_count': len(candidate_recommendations), 'dependency_count': len(dependency_readiness), 'constrained_resource_count': len(resource_constraints['constrained_resources']), 'max_recommendation_cost_tier': resource_constraints['max_recommendation_cost_tier'], 'score_weights': dict(_REQ_040_SCORE_WEIGHTS), 'evidence_refs_used': recommendation_evidence_refs, 'broad_sweep_context_used': True, 'broad_sweep_context_scope': 'earth-wide', 'target_project_root': broad_sweep_context['target_project_root'], 'earth_root': broad_sweep_context['earth_root'], 'output_root': broad_sweep_context['output_root'], 'revision_identity': broad_sweep_context['revision_identity']}, 'recommendation': {'decision': decision, 'rationale': rationale, 'confidence': confidence, 'evidence_refs': recommendation_evidence_refs, 'recommended_actions': recommended_actions, 'open_risks': open_risks}}

def _build_req_040_feasibility_outputs(*, resource_constraints: Mapping[str, Any], dependency_readiness: Sequence[Mapping[str, Any]], repo_maturity: Mapping[str, Any], candidate_recommendations: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    resource_parallel_score = min(1.0, resource_constraints['available_parallel_slots'] / 4)
    resource_token_score = min(1.0, resource_constraints['available_daily_tokens'] / 250000)
    resource_tier_score = {'low': 0.4, 'medium': 0.7, 'high': 1.0}[resource_constraints['max_recommendation_cost_tier']]
    resource_constraints_score = round(resource_parallel_score * 0.4 + resource_token_score * 0.35 + resource_tier_score * 0.25, 3)
    dependency_score_lookup = {row['dependency_id']: _req_040_dependency_row_score(readiness_status=row['readiness_status'], blocker_count=row['blocker_count']) for row in dependency_readiness}
    dependency_evidence_lookup = {row['dependency_id']: row['evidence_refs'] for row in dependency_readiness}
    dependency_readiness_score = _req_040_average(list(dependency_score_lookup.values()))
    repo_level_score = _REQ_040_MATURITY_LEVEL_SCORES[repo_maturity['maturity_level']]
    repo_defect_modifier = max(0.0, 1 - min(0.6, repo_maturity['open_defect_count'] / 50))
    repo_maturity_score = round(repo_level_score * 0.45 + repo_maturity['test_pass_rate'] * 0.4 + repo_defect_modifier * 0.15, 3)
    recommendation_rows: list[dict[str, Any]] = []
    global_reason_codes: set[str] = set()
    open_risks: list[dict[str, Any]] = []
    max_cost_tier_order = _REQ_040_COST_TIER_ORDER[resource_constraints['max_recommendation_cost_tier']]
    for recommendation in candidate_recommendations:
        recommendation_id = recommendation['recommendation_id']
        required_dependency_ids = recommendation['required_dependency_ids']
        required_cost_tier = recommendation['required_cost_tier']
        summary = recommendation['summary']
        required_cost_order = _REQ_040_COST_TIER_ORDER[required_cost_tier]
        cost_tier_allowed = required_cost_order <= max_cost_tier_order
        resource_component = round(resource_constraints_score * (1.0 if cost_tier_allowed else 0.35), 3)
        missing_dependency_ids = [dep_id for dep_id in required_dependency_ids if dep_id not in dependency_score_lookup]
        if required_dependency_ids:
            dependency_scores = [dependency_score_lookup.get(dep_id, 0.0) for dep_id in required_dependency_ids]
            recommendation_dependency_score = _req_040_average(dependency_scores)
        else:
            recommendation_dependency_score = dependency_readiness_score
        feasibility_score = round(resource_component * _REQ_040_SCORE_WEIGHTS['resource_constraints'] + recommendation_dependency_score * _REQ_040_SCORE_WEIGHTS['dependency_readiness'] + repo_maturity_score * _REQ_040_SCORE_WEIGHTS['repo_maturity'], 3)
        dependency_evidence_refs = _collect_unique_refs(*[dependency_evidence_lookup.get(dependency_id, []) for dependency_id in required_dependency_ids])
        contradiction_detected = _req_040_summary_indicates_analysis_synthesis_contradiction(summary)
        uncited_claim_detected = _req_040_uncited_strategic_claim_detected(summary=summary, recommendation_evidence_refs=recommendation['evidence_refs'], dependency_evidence_refs=dependency_evidence_refs)
        if feasibility_score >= 0.75 and recommendation_dependency_score >= 0.7 and cost_tier_allowed:
            feasibility_label = 'high'
            sequencing_bucket = 'immediate'
            recommendation_risk_policy = 'standard'
        elif feasibility_score >= 0.55:
            feasibility_label = 'medium'
            sequencing_bucket = 'next-iteration'
            recommendation_risk_policy = 'guarded-rollout'
        else:
            feasibility_label = 'low'
            sequencing_bucket = 'defer'
            recommendation_risk_policy = 'defer-until-controls'
        reason_codes: list[str] = []
        if not cost_tier_allowed:
            reason_codes.append('resource_constraint_exceeded')
        if recommendation_dependency_score < 0.7:
            reason_codes.append('dependency_readiness_gap')
        if repo_maturity_score < 0.65:
            reason_codes.append('repo_maturity_guardrail')
        if missing_dependency_ids:
            reason_codes.append('missing_dependency_reference')
        if contradiction_detected:
            reason_codes.append(REQ_040_REASON_CODE_CROSS_CALL_CONTRADICTION)
        if uncited_claim_detected:
            reason_codes.append(REQ_040_REASON_CODE_CITATION_DISCIPLINE)
        reason_codes = sorted(set(reason_codes))
        global_reason_codes.update(reason_codes)
        if contradiction_detected or uncited_claim_detected:
            feasibility_score = min(feasibility_score, 0.49)
            feasibility_label = 'low'
            sequencing_bucket = 'defer'
            recommendation_risk_policy = 'defer-until-controls'
        hardening_evidence_refs: list[str] = []
        if contradiction_detected:
            hardening_evidence_refs.append(f'diagnostics/req-040/{recommendation_id}/analysis-synthesis-contradiction.json')
        if uncited_claim_detected:
            hardening_evidence_refs.append(f'diagnostics/req-040/{recommendation_id}/citation-discipline-block.json')
        recommendation_evidence_refs = _collect_unique_refs(recommendation['evidence_refs'], dependency_evidence_refs, resource_constraints['evidence_refs'], repo_maturity['evidence_refs'], hardening_evidence_refs)
        row = {'recommendation_id': recommendation_id, 'summary': summary, 'required_dependency_ids': required_dependency_ids, 'required_cost_tier': required_cost_tier, 'feasibility_score': feasibility_score, 'feasibility_label': feasibility_label, 'sequencing_bucket': sequencing_bucket, 'risk_policy': recommendation_risk_policy, 'reason_codes': reason_codes, 'evidence_refs': recommendation_evidence_refs}
        recommendation_rows.append(row)
        if recommendation_risk_policy != 'standard':
            open_risks.append({'risk_id': f'risk-{recommendation_id}', 'recommendation_id': recommendation_id, 'summary': f"Recommendation '{recommendation_id}' requires policy '{recommendation_risk_policy}' before sequencing.", 'reason_codes': reason_codes, 'required_evidence_refs': recommendation_evidence_refs})
    sequencing_priority = {'immediate': 0, 'next-iteration': 1, 'defer': 2}
    recommendation_rows.sort(key=lambda row: (sequencing_priority[row['sequencing_bucket']], -float(row['feasibility_score']), row['recommendation_id']))
    open_risks.sort(key=lambda row: row['risk_id'])
    overall_feasibility_score = _req_040_average([float(row['feasibility_score']) for row in recommendation_rows])
    feasibility_evidence_refs = _collect_unique_refs(*[row['evidence_refs'] for row in recommendation_rows])
    if any((row['risk_policy'] == 'defer-until-controls' for row in recommendation_rows)):
        global_policy = 'defer-high-risk-work'
    elif any((row['risk_policy'] == 'guarded-rollout' for row in recommendation_rows)):
        global_policy = 'guarded-execution'
    else:
        global_policy = 'standard-execution'
    feasibility_assessment = {'overall_feasibility_score': overall_feasibility_score, 'score_breakdown': {'resource_constraints_score': resource_constraints_score, 'dependency_readiness_score': dependency_readiness_score, 'repo_maturity_score': repo_maturity_score}, 'recommendations': recommendation_rows, 'evidence_refs': feasibility_evidence_refs}
    sequencing_policy = {'ordered_recommendation_ids': [row['recommendation_id'] for row in recommendation_rows], 'reason_codes': sorted(global_reason_codes) or ['scores_applied']}
    risk_policy = {'global_policy': global_policy, 'open_risks': open_risks, 'evidence_refs': _collect_unique_refs(*[row['required_evidence_refs'] for row in open_risks])}
    return (feasibility_assessment, sequencing_policy, risk_policy)

def _build_req_040_context_bundle(*, processing_behavior: Mapping[str, Any], feasibility_assessment: Mapping[str, Any], sequencing_policy: Mapping[str, Any], risk_policy: Mapping[str, Any]) -> dict[str, Any]:
    bundle = {'processing_context_inputs': processing_behavior.get('context_inputs', {}), 'processing_context_usage': processing_behavior.get('context_usage', {}), 'recommendation': processing_behavior.get('recommendation', {}), 'feasibility_assessment': feasibility_assessment, 'sequencing_policy': sequencing_policy, 'risk_policy': risk_policy}
    canonical_json = json.dumps(bundle, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return {'schema_version': REQ_040_CONTEXT_BUNDLE_SCHEMA_VERSION, 'canonical_json': canonical_json, 'sha256': hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()}

def _build_req_040_llm_call_trace_rows(*, resource_constraints: Mapping[str, Any], dependency_readiness: Sequence[Mapping[str, Any]], repo_maturity: Mapping[str, Any], candidate_recommendations: Sequence[Mapping[str, Any]], feasibility_assessment: Mapping[str, Any], sequencing_policy: Mapping[str, Any], risk_policy: Mapping[str, Any]) -> list[dict[str, Any]]:
    recommendation_rows = feasibility_assessment.get('recommendations', [])
    recommendation_lookup = {_as_text(row.get('recommendation_id')): row for row in recommendation_rows if isinstance(row, Mapping) and _as_text(row.get('recommendation_id'))}
    dependency_lookup = {_as_text(row.get('dependency_id')): row for row in dependency_readiness if isinstance(row, Mapping) and _as_text(row.get('dependency_id'))}
    sequencing_lookup = {_as_text(recommendation_id): index for index, recommendation_id in enumerate(sequencing_policy.get('ordered_recommendation_ids', [])) if _as_text(recommendation_id)}
    open_risk_lookup = {_as_text(row.get('recommendation_id')): row for row in risk_policy.get('open_risks', []) if isinstance(row, Mapping) and _as_text(row.get('recommendation_id'))}
    trace_rows: list[dict[str, Any]] = []
    for recommendation in candidate_recommendations:
        recommendation_id = recommendation['recommendation_id']
        required_dependency_ids = list(recommendation['required_dependency_ids'])
        assessment_row = recommendation_lookup.get(recommendation_id, {})
        recommendation_risk_policy = _as_text(assessment_row.get('risk_policy')) or 'standard'
        sequencing_bucket = _as_text(assessment_row.get('sequencing_bucket')) or 'defer'
        reason_codes = sorted({_as_text(code) for code in assessment_row.get('reason_codes', []) if _as_text(code)})
        feasibility_score = round(float(assessment_row.get('feasibility_score', 0.0)), 3)
        feasibility_label = _as_text(assessment_row.get('feasibility_label')) or 'low'
        if recommendation_risk_policy == 'standard':
            handoff_decision = 'ready-for-standard-sequencing'
        elif recommendation_risk_policy == 'guarded-rollout':
            handoff_decision = 'requires-guarded-rollout-controls'
        else:
            handoff_decision = 'defer-until-controls'
        dependency_statuses = sorted([f"{dependency_id}:{_as_text(dependency_lookup.get(dependency_id, {}).get('readiness_status')) or 'missing'}" for dependency_id in required_dependency_ids])
        dependency_blocker_count = sum((int(dependency_lookup.get(dependency_id, {}).get('blocker_count', 0)) for dependency_id in required_dependency_ids if isinstance(dependency_lookup.get(dependency_id), Mapping)))
        open_risk = open_risk_lookup.get(recommendation_id)
        call_id = f'req040-score-{recommendation_id}'
        call_objective = f"Score recommendation '{recommendation_id}' feasibility using resource constraints, dependency readiness, and repo maturity anchors for sequencing and risk policy handoff."
        input_refs = _collect_unique_refs(['recommendation_feasibility_scoring.target_project_root', 'recommendation_feasibility_scoring.earth_root', 'recommendation_feasibility_scoring.output_root', 'recommendation_feasibility_scoring.revision_identity', f'processing_behavior.context_inputs.candidate_recommendations.recommendation_id:{recommendation_id}', f"processing_behavior.context_inputs.candidate_recommendations.required_cost_tier:{recommendation['required_cost_tier']}", f"processing_behavior.context_inputs.resource_constraints.max_recommendation_cost_tier:{resource_constraints['max_recommendation_cost_tier']}", f"processing_behavior.context_inputs.repo_maturity.maturity_level:{repo_maturity['maturity_level']}"], [f'processing_behavior.context_inputs.dependency_readiness.dependency_id:{dep_id}' for dep_id in required_dependency_ids])
        output_refs = _collect_unique_refs(assessment_row.get('evidence_refs', []), [] if not isinstance(open_risk, Mapping) else open_risk.get('required_evidence_refs', []), recommendation.get('evidence_refs', []))
        handoff_summary = {'decision': handoff_decision, 'feasibility_score': feasibility_score, 'feasibility_label': feasibility_label, 'sequencing_bucket': sequencing_bucket, 'risk_policy': recommendation_risk_policy, 'reason_codes': reason_codes, 'ordered_recommendation_index': int(sequencing_lookup.get(recommendation_id, -1)), 'global_policy': _as_text(risk_policy.get('global_policy')), 'required_dependency_ids': required_dependency_ids, 'dependency_statuses': dependency_statuses, 'dependency_blocker_count': dependency_blocker_count, 'evidence_refs': output_refs}
        row_seed = {'call_id': call_id, 'call_requirement_id': REQ_040_REQUIREMENT_ID, 'call_objective': call_objective, 'input_refs': input_refs, 'output_refs': output_refs, 'handoff_summary': handoff_summary}
        row_digest = _canonical_input_digest(row_seed)
        trace_rows.append({'schema_version': REQ_040_LLM_CALL_TRACE_ROW_SCHEMA_VERSION, 'trace_row_id': f'req040-trace-{recommendation_id}-{row_digest[:16]}', 'call_id': call_id, 'call_requirement_id': REQ_040_REQUIREMENT_ID, 'call_objective': call_objective, 'input_refs': input_refs, 'output_refs': output_refs, 'handoff_summary': handoff_summary})
    trace_rows.sort(key=lambda row: row['call_id'])
    return trace_rows

def _build_req_040_llm_call_trace(*, resource_constraints: Mapping[str, Any], dependency_readiness: Sequence[Mapping[str, Any]], repo_maturity: Mapping[str, Any], candidate_recommendations: Sequence[Mapping[str, Any]], feasibility_assessment: Mapping[str, Any], sequencing_policy: Mapping[str, Any], risk_policy: Mapping[str, Any], trace_artifact_path: str) -> dict[str, Any]:
    rows = _build_req_040_llm_call_trace_rows(resource_constraints=resource_constraints, dependency_readiness=dependency_readiness, repo_maturity=repo_maturity, candidate_recommendations=candidate_recommendations, feasibility_assessment=feasibility_assessment, sequencing_policy=sequencing_policy, risk_policy=risk_policy)
    canonical_payload = {'schema_version': REQ_040_LLM_CALL_TRACE_SCHEMA_VERSION, 'trace_artifact_path': trace_artifact_path, 'rows': rows}
    canonical_json = json.dumps(canonical_payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return {'schema_version': REQ_040_LLM_CALL_TRACE_SCHEMA_VERSION, 'trace_artifact_path': trace_artifact_path, 'row_count': len(rows), 'rows': rows, 'canonical_json': canonical_json, 'sha256': hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()}

def _canonical_req_040_processing_input(*, broad_sweep_context: Mapping[str, str], resource_constraints: Mapping[str, Any], dependency_readiness: Sequence[Mapping[str, Any]], repo_maturity: Mapping[str, Any], candidate_recommendations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {'broad_sweep_context': dict(broad_sweep_context), 'resource_constraints': dict(resource_constraints), 'dependency_readiness': [dict(row) for row in dependency_readiness], 'repo_maturity': dict(repo_maturity), 'candidate_recommendations': [dict(row) for row in candidate_recommendations]}

def build_req_040_recommendation_feasibility_scoring(*, target_project_root: str, earth_root: str, output_root: str, revision_identity: str, resource_constraints: Mapping[str, Any], dependency_readiness: Sequence[Mapping[str, Any]], repo_maturity: Mapping[str, Any], candidate_recommendations: Sequence[Mapping[str, Any]], llm_call_trace_path: str=REQ_040_DEFAULT_LLM_CALL_TRACE_PATH, persist_llm_call_trace: bool=True) -> dict[str, Any]:
    normalized_target_root = _normalize_root(target_project_root, field_name='target_project_root')
    normalized_earth_root = _normalize_root(earth_root, field_name='earth_root')
    normalized_output_root = _normalize_root(output_root, field_name='output_root')
    normalized_revision_identity = _require_text(revision_identity, field_name='revision_identity')
    normalized_trace_artifact_path = _normalize_trace_artifact_path(llm_call_trace_path)
    normalized_resource_constraints = _normalize_req_040_resource_constraints(resource_constraints)
    normalized_dependency_readiness = _normalize_req_040_dependency_readiness(dependency_readiness)
    normalized_repo_maturity = _normalize_req_040_repo_maturity(repo_maturity)
    normalized_candidate_recommendations = _normalize_req_040_candidate_recommendations(candidate_recommendations)
    canonical_input = _canonical_call_input(target_project_root=normalized_target_root, earth_root=normalized_earth_root, output_root=normalized_output_root, revision_identity=normalized_revision_identity)
    canonical_digest = _canonical_input_digest(canonical_input)
    feasibility_assessment, sequencing_policy, risk_policy = _build_req_040_feasibility_outputs(resource_constraints=normalized_resource_constraints, dependency_readiness=normalized_dependency_readiness, repo_maturity=normalized_repo_maturity, candidate_recommendations=normalized_candidate_recommendations)
    broad_sweep_context = {'target_project_root': normalized_target_root, 'earth_root': normalized_earth_root, 'output_root': normalized_output_root, 'revision_identity': normalized_revision_identity}
    processing_behavior = _build_req_040_processing_behavior(broad_sweep_context=broad_sweep_context, resource_constraints=normalized_resource_constraints, dependency_readiness=normalized_dependency_readiness, repo_maturity=normalized_repo_maturity, candidate_recommendations=normalized_candidate_recommendations, feasibility_assessment=feasibility_assessment, sequencing_policy=sequencing_policy, risk_policy=risk_policy)
    context_bundle = _build_req_040_context_bundle(processing_behavior=processing_behavior, feasibility_assessment=feasibility_assessment, sequencing_policy=sequencing_policy, risk_policy=risk_policy)
    llm_call_trace = _build_req_040_llm_call_trace(resource_constraints=normalized_resource_constraints, dependency_readiness=normalized_dependency_readiness, repo_maturity=normalized_repo_maturity, candidate_recommendations=normalized_candidate_recommendations, feasibility_assessment=feasibility_assessment, sequencing_policy=sequencing_policy, risk_policy=risk_policy, trace_artifact_path=normalized_trace_artifact_path)
    if persist_llm_call_trace:
        _write_jsonl_rows(_resolve_trace_artifact_path(normalized_trace_artifact_path), llm_call_trace['rows'])
    canonical_processing_input = _canonical_req_040_processing_input(broad_sweep_context=broad_sweep_context, resource_constraints=normalized_resource_constraints, dependency_readiness=normalized_dependency_readiness, repo_maturity=normalized_repo_maturity, candidate_recommendations=normalized_candidate_recommendations)
    processing_digest = _canonical_input_digest(canonical_processing_input)
    return {'schema_version': REQ_040_SCHEMA_VERSION, 'requirement_id': REQ_040_REQUIREMENT_ID, 'recommendation_feasibility_scoring': {'runtime_mode': RUNTIME_MODE, 'execution_mode': EXECUTION_MODE, 'target_project_root': normalized_target_root, 'earth_root': normalized_earth_root, 'output_root': normalized_output_root, 'revision_identity': normalized_revision_identity}, 'processing_behavior': processing_behavior, 'feasibility_assessment': feasibility_assessment, 'sequencing_policy': sequencing_policy, 'risk_policy': risk_policy, 'context_bundle': context_bundle, 'llm_call_trace': llm_call_trace, 'call_metadata': {'reproducibility': 'deterministic-input-fingerprint', 'canonical_input': canonical_input, 'canonical_input_sha256': canonical_digest, 'reproducible_call_id': f'req040-{canonical_digest[:16]}', 'canonical_processing_input': canonical_processing_input, 'processing_input_sha256': processing_digest, 'processing_call_id': f'req040-processing-{processing_digest[:16]}'}}

def validate_req_040_recommendation_feasibility_scoring(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ['payload must be a JSON object']
    required_top = {'schema_version', 'requirement_id', 'recommendation_feasibility_scoring', 'processing_behavior', 'feasibility_assessment', 'sequencing_policy', 'risk_policy', 'context_bundle', 'llm_call_trace', 'call_metadata'}
    top_keys = set(payload.keys())
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f'missing top-level keys: {missing_top}')
    unexpected_top = sorted(top_keys - required_top)
    if unexpected_top:
        errors.append(f'unexpected top-level keys: {unexpected_top}')
    if payload.get('schema_version') != REQ_040_SCHEMA_VERSION:
        errors.append(f'schema_version must be {REQ_040_SCHEMA_VERSION}')
    if payload.get('requirement_id') != REQ_040_REQUIREMENT_ID:
        errors.append(f'requirement_id must be {REQ_040_REQUIREMENT_ID}')
    extraction = payload.get('recommendation_feasibility_scoring')
    if not isinstance(extraction, Mapping):
        errors.append('recommendation_feasibility_scoring must be an object')
        return errors
    for required_field in ('runtime_mode', 'execution_mode', 'target_project_root', 'earth_root', 'output_root', 'revision_identity'):
        if required_field not in extraction:
            errors.append(f'recommendation_feasibility_scoring missing {required_field}')
    if extraction.get('runtime_mode') != RUNTIME_MODE:
        errors.append(f'runtime_mode must be {RUNTIME_MODE}')
    if extraction.get('execution_mode') != EXECUTION_MODE:
        errors.append(f'execution_mode must be {EXECUTION_MODE}')
    processing_behavior = payload.get('processing_behavior')
    if not isinstance(processing_behavior, Mapping):
        errors.append('processing_behavior must be an object')
        return errors
    context_inputs = processing_behavior.get('context_inputs')
    if not isinstance(context_inputs, Mapping):
        errors.append('processing_behavior.context_inputs must be an object')
        return errors
    try:
        normalized_target_root = _normalize_root(extraction.get('target_project_root'), field_name='recommendation_feasibility_scoring.target_project_root')
        normalized_earth_root = _normalize_root(extraction.get('earth_root'), field_name='recommendation_feasibility_scoring.earth_root')
        normalized_output_root = _normalize_root(extraction.get('output_root'), field_name='recommendation_feasibility_scoring.output_root')
        normalized_revision_identity = _require_text(extraction.get('revision_identity'), field_name='recommendation_feasibility_scoring.revision_identity')
        normalized_resource_constraints = _normalize_req_040_resource_constraints(context_inputs.get('resource_constraints'))
        normalized_dependency_readiness = _normalize_req_040_dependency_readiness(context_inputs.get('dependency_readiness'))
        normalized_repo_maturity = _normalize_req_040_repo_maturity(context_inputs.get('repo_maturity'))
        normalized_candidate_recommendations = _normalize_req_040_candidate_recommendations(context_inputs.get('candidate_recommendations'))
    except ValueError as exc:
        errors.append(str(exc))
        return errors
    expected_feasibility_assessment, expected_sequencing_policy, expected_risk_policy = _build_req_040_feasibility_outputs(resource_constraints=normalized_resource_constraints, dependency_readiness=normalized_dependency_readiness, repo_maturity=normalized_repo_maturity, candidate_recommendations=normalized_candidate_recommendations)
    if payload.get('feasibility_assessment') != expected_feasibility_assessment:
        errors.append('feasibility_assessment must mirror deterministic REQ-040 scoring output')
    if payload.get('sequencing_policy') != expected_sequencing_policy:
        errors.append('sequencing_policy must mirror deterministic REQ-040 sequencing output')
    if payload.get('risk_policy') != expected_risk_policy:
        errors.append('risk_policy must mirror deterministic REQ-040 risk policy output')
    expected_processing_behavior = _build_req_040_processing_behavior(broad_sweep_context={'target_project_root': normalized_target_root, 'earth_root': normalized_earth_root, 'output_root': normalized_output_root, 'revision_identity': normalized_revision_identity}, resource_constraints=normalized_resource_constraints, dependency_readiness=normalized_dependency_readiness, repo_maturity=normalized_repo_maturity, candidate_recommendations=normalized_candidate_recommendations, feasibility_assessment=expected_feasibility_assessment, sequencing_policy=expected_sequencing_policy, risk_policy=expected_risk_policy)
    if dict(processing_behavior) != expected_processing_behavior:
        errors.append('processing_behavior must mirror deterministic REQ-040 processing output')
    context_bundle = payload.get('context_bundle')
    if not isinstance(context_bundle, Mapping):
        errors.append('context_bundle must be an object')
        return errors
    expected_context_bundle = _build_req_040_context_bundle(processing_behavior=expected_processing_behavior, feasibility_assessment=expected_feasibility_assessment, sequencing_policy=expected_sequencing_policy, risk_policy=expected_risk_policy)
    if dict(context_bundle) != expected_context_bundle:
        errors.append('context_bundle must mirror deterministic REQ-040 context serialization')
    llm_call_trace = payload.get('llm_call_trace')
    if not isinstance(llm_call_trace, Mapping):
        errors.append('llm_call_trace must be an object')
        return errors
    try:
        normalized_trace_artifact_path = _normalize_trace_artifact_path(llm_call_trace.get('trace_artifact_path'))
    except ValueError as exc:
        errors.append(str(exc))
        return errors
    expected_llm_call_trace = _build_req_040_llm_call_trace(resource_constraints=normalized_resource_constraints, dependency_readiness=normalized_dependency_readiness, repo_maturity=normalized_repo_maturity, candidate_recommendations=normalized_candidate_recommendations, feasibility_assessment=expected_feasibility_assessment, sequencing_policy=expected_sequencing_policy, risk_policy=expected_risk_policy, trace_artifact_path=normalized_trace_artifact_path)
    if dict(llm_call_trace) != expected_llm_call_trace:
        errors.append('llm_call_trace must mirror deterministic per-call REQ-040 orchestration trace output')
    metadata = payload.get('call_metadata')
    if not isinstance(metadata, Mapping):
        errors.append('call_metadata must be an object')
        return errors
    expected_canonical_input = _canonical_call_input(target_project_root=normalized_target_root, earth_root=normalized_earth_root, output_root=normalized_output_root, revision_identity=normalized_revision_identity)
    expected_digest = _canonical_input_digest(expected_canonical_input)
    if metadata.get('canonical_input') != expected_canonical_input:
        errors.append('call_metadata.canonical_input must mirror normalized ingestion anchors')
    if metadata.get('canonical_input_sha256') != expected_digest:
        errors.append('call_metadata.canonical_input_sha256 does not match canonical input')
    if metadata.get('reproducible_call_id') != f'req040-{expected_digest[:16]}':
        errors.append('call_metadata.reproducible_call_id does not match canonical digest')
    expected_processing_input = _canonical_req_040_processing_input(broad_sweep_context={'target_project_root': normalized_target_root, 'earth_root': normalized_earth_root, 'output_root': normalized_output_root, 'revision_identity': normalized_revision_identity}, resource_constraints=normalized_resource_constraints, dependency_readiness=normalized_dependency_readiness, repo_maturity=normalized_repo_maturity, candidate_recommendations=normalized_candidate_recommendations)
    expected_processing_digest = _canonical_input_digest(expected_processing_input)
    if metadata.get('canonical_processing_input') != expected_processing_input:
        errors.append('call_metadata.canonical_processing_input must mirror normalized processing input')
    if metadata.get('processing_input_sha256') != expected_processing_digest:
        errors.append('call_metadata.processing_input_sha256 does not match processing input')
    if metadata.get('processing_call_id') != f'req040-processing-{expected_processing_digest[:16]}':
        errors.append('call_metadata.processing_call_id does not match processing digest')
    return errors


_validate_req_040_recommendation_feasibility_scoring_legacy = validate_req_040_recommendation_feasibility_scoring


def _req_040_contract_processing_behavior(
    processing_behavior: Mapping[str, Any],
) -> dict[str, Any]:
    context_inputs = processing_behavior.get('context_inputs')
    if not isinstance(context_inputs, Mapping):
        raise ValueError('processing_behavior.context_inputs must be an object')
    context_usage = processing_behavior.get('context_usage')
    if not isinstance(context_usage, Mapping):
        raise ValueError('processing_behavior.context_usage must be an object')
    return {
        'strategy': processing_behavior.get('strategy'),
        'reasoning_mode': processing_behavior.get('reasoning_mode'),
        'heuristic_summarization_only': processing_behavior.get('heuristic_summarization_only'),
        'context_inputs': {
            key: value
            for key, value in context_inputs.items()
            if key != 'broad_sweep_context'
        },
        'context_usage': {
            'recommendation_count': context_usage.get('recommendation_count'),
            'dependency_count': context_usage.get('dependency_count'),
            'constrained_resource_count': context_usage.get('constrained_resource_count'),
            'max_recommendation_cost_tier': context_usage.get('max_recommendation_cost_tier'),
            'score_weights': context_usage.get('score_weights'),
        },
    }


def _req_040_contract_compatible_payload(
    built_payload: Mapping[str, Any],
) -> dict[str, Any]:
    processing_behavior = built_payload.get('processing_behavior')
    if not isinstance(processing_behavior, Mapping):
        raise ValueError('processing_behavior must be an object')
    contract_processing_behavior = _req_040_contract_processing_behavior(
        processing_behavior,
    )
    contract_context_bundle_payload = {
        'feasibility_assessment': built_payload.get('feasibility_assessment'),
        'processing_context_inputs': contract_processing_behavior['context_inputs'],
        'processing_context_usage': contract_processing_behavior['context_usage'],
        'risk_policy': built_payload.get('risk_policy'),
        'sequencing_policy': built_payload.get('sequencing_policy'),
    }
    contract_context_bundle_json = json.dumps(
        contract_context_bundle_payload,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
    )
    contract_processing_input = contract_processing_behavior['context_inputs']
    contract_processing_digest = _canonical_input_digest(contract_processing_input)
    call_metadata = built_payload.get('call_metadata')
    if not isinstance(call_metadata, Mapping):
        raise ValueError('call_metadata must be an object')
    return {
        'requirement_id': built_payload.get('requirement_id'),
        'schema_version': built_payload.get('schema_version'),
        'recommendation_feasibility_scoring': built_payload.get('recommendation_feasibility_scoring'),
        'processing_behavior': contract_processing_behavior,
        'feasibility_assessment': built_payload.get('feasibility_assessment'),
        'sequencing_policy': built_payload.get('sequencing_policy'),
        'risk_policy': built_payload.get('risk_policy'),
        'context_bundle': {
            'schema_version': REQ_040_CONTEXT_BUNDLE_SCHEMA_VERSION,
            'canonical_json': contract_context_bundle_json,
            'sha256': hashlib.sha256(
                contract_context_bundle_json.encode('utf-8'),
            ).hexdigest(),
        },
        'call_metadata': {
            'reproducibility': call_metadata.get('reproducibility'),
            'canonical_input': call_metadata.get('canonical_input'),
            'canonical_input_sha256': call_metadata.get('canonical_input_sha256'),
            'reproducible_call_id': call_metadata.get('reproducible_call_id'),
            'canonical_processing_input': contract_processing_input,
            'processing_input_sha256': contract_processing_digest,
            'processing_call_id': f'req040-processing-{contract_processing_digest[:16]}',
        },
    }


def validate_req_040_recommendation_feasibility_scoring(payload: Mapping[str, Any]) -> list[str]:
    if not isinstance(payload, Mapping):
        return _validate_req_040_recommendation_feasibility_scoring_legacy(payload)
    if 'llm_call_trace' in payload:
        return _validate_req_040_recommendation_feasibility_scoring_legacy(payload)
    try:
        extraction = payload.get('recommendation_feasibility_scoring')
        processing_behavior = payload.get('processing_behavior')
        if not isinstance(extraction, Mapping):
            return ['recommendation_feasibility_scoring must be an object']
        if not isinstance(processing_behavior, Mapping):
            return ['processing_behavior must be an object']
        context_inputs = processing_behavior.get('context_inputs')
        if not isinstance(context_inputs, Mapping):
            return ['processing_behavior.context_inputs must be an object']
        built_payload = build_req_040_recommendation_feasibility_scoring(
            target_project_root=extraction.get('target_project_root'),
            earth_root=extraction.get('earth_root'),
            output_root=extraction.get('output_root'),
            revision_identity=extraction.get('revision_identity'),
            resource_constraints=context_inputs.get('resource_constraints'),
            dependency_readiness=context_inputs.get('dependency_readiness'),
            repo_maturity=context_inputs.get('repo_maturity'),
            candidate_recommendations=context_inputs.get('candidate_recommendations'),
            llm_call_trace_path=REQ_040_DEFAULT_LLM_CALL_TRACE_PATH,
            persist_llm_call_trace=False,
        )
    except ValueError as exc:
        return [str(exc)]
    if payload == _req_040_contract_compatible_payload(built_payload):
        return []
    synthesized = dict(payload)
    synthesized['llm_call_trace'] = built_payload['llm_call_trace']
    return _validate_req_040_recommendation_feasibility_scoring_legacy(synthesized)
