# Scope: Active Debugger

## Core scope
- Subscribe to issue queues and runtime signals from OP artifacts/logs.
- Auto-triage candidates that fit bounded-fix criteria.
- Generate minimal patch plans with explicit scope constraints.
- Execute bounded patch and targeted verification loops with strict retry caps.
- Publish structured evidence, diff summary, and confidence-based handoff outcome.

## Bounded-fix criteria
- Limited file and logic surface area.
- Clear local verification command path.
- No broad architectural redesign required.
- Low-to-medium risk change class.

## Quality and safety requirements
- Every change must include before/after defect statement.
- Verification output must be captured and attached.
- Failed verification triggers rollback or escalation decision.
- All decisions must be logged with reason codes.

## Autonomy model
- Use low-cost model by default for narrow, high-confidence fixes.
- Escalate to stronger model or operator for ambiguous/high-risk cases.
- Never perform broad refactors or multi-domain redesign without explicit assignment.

## Integration scope
- Can be invoked by orchestrator, BOSS, or standalone trigger queue.
- Must emit artifacts that other managers can consume deterministically.
- Should reduce repetitive manual triage burden in active runs.

## Non-goals
- Taking over full feature implementation.
- Silent code changes without evidence artifacts.
- Modifying governance rules or branch policy.
