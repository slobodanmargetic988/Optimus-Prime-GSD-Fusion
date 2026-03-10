# Scope

This is a hardening + scale-up scope for an existing autonomous builder platform.

## Baseline reality

- `/op-initialize`, `/op-build`, `/op-simple-build`, and supporting managers are implemented,
- project has active canary evidence and known failure patterns (merge completeness, watchdog behavior, long-cycle inefficiencies),
- installer/bundling/prompt systems exist and must remain coherent with runtime behavior.

## Scope objectives for this era

- improve terminal-cycle reliability and determinism in long-running builds,
- reduce BOSS overhead by tightening manager separation and specialization,
- ensure completion flow consistently merges all intended work into run-base,
- strengthen resume/continuation semantics across restarts and watchdog stops,
- improve dispatch quality and avoid low-value redispatch loops,
- harden profile/rate-aware behavior for stable throughput,
- expand lifecycle tracking in target repos for era-level traceability,
- standardize prompt-to-runtime contract alignment and artifact freshness enforcement,
- improve operator observability via concise, timestamped, actionable terminal output.

## Manager and orchestration direction

- keep BOSS focused on planning and coordination decisions, not heavy merge finalization,
- introduce/strengthen specialized managers (for example wrapup/active-merger patterns),
- ensure each manager has deterministic inputs, outputs, and validator-enforced contracts,
- keep soft-gate vs hard-gate decisions explicit and documented.

## Planning and strategy quality direction

- improve mission/scope ingestion quality (especially file-based mission/scope inputs),
- enforce stronger decomposition for large projects and better lane/phase parallelization,
- preserve compatibility with existing project tech stacks unless override is explicit.

## Installation and packaging requirements

- bundled install must include all required prompts/skills/assets for runtime behavior,
- installed paths and repo paths must stay aligned with documented prompt references,
- install/update flows must preserve deterministic behavior across versions.

## Definition of done

- long-running canary runs complete with fewer manual interventions,
- finalization reliably lands complete work on run-base,
- artifact contracts are consistently enforced by runtime, not only by prompt guidance,
- key operator pain points have deterministic fixes and regression coverage.

## Planning decomposition requirement (hard gate)

Before build execution, planner must produce **at least 400 atomic tasks** for this era.

Task decomposition rules:

- each task fits a 5-10 minute worker execution window,
- each task includes acceptance criteria and expected evidence,
- dependencies and lanes must enable substantial parallel execution,
- phases must be explicit and ordered to support safe progression.
