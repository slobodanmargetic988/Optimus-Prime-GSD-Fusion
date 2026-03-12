# Scope: Active Merger

## Core scope
- Run as long-lived independent service with configurable poll interval (default 30 seconds).
- Support dynamic monitor targets: thread IDs, thread files, artifact roots, and repo refs.
- Discover new commit SHAs from logs/artifacts/git sources.
- Run LLM decision pass for each unseen commit.
- Apply deterministic merge policy gate before any merge operation.
- Execute merges into configured target branches when policy passes.
- Expose control API for adding/removing targets, pause/resume, and forced re-evaluation.

## Mandatory quality and safety gates
- Every commit decision must include decision code, reason code, and human explanation.
- Every merge action must be idempotent and auditable.
- Required checks and branch protections must be respected.
- Conflicted/unsafe commits must enter hold queue with clear operator action guidance.

## Autonomy model
- Use cost-optimized model for routine high-confidence decisions.
- Escalate uncertain, high-risk, or policy-sensitive commits to stronger model or operator review.
- Maintain strict evidence logs for discovery, decision, and merge outcomes.

## Integration scope
- BOSS can emit merge intents/context but should not carry routine merge execution burden.
- Runtime should read Active Merger status artifacts for cycle decisions and progress reporting.
- Tool should support multi-project monitoring with explicit project boundary mapping.

## Non-goals
- Owning planning strategy decisions.
- Bypassing branch protections, required checks, or governance policy.
- Performing broad refactor decisions unrelated to commit merge relevance.
