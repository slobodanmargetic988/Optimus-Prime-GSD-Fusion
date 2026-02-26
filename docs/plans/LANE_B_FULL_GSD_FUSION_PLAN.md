# Lane B — Full GSD Fusion Plan (Orchestration + Planning + Quality Gates)

## Summary
Lane B upgrades Optimus from a strong runtime orchestrator into a full-system product with GSD-grade planning rigor, test-first contracts, verification loops, and reliability operations.

Lane A provides deterministic cycle control. Lane B adds the product workflow layer that GSD currently does better.

---

## Objectives
1. Add a complete planning lifecycle (project -> requirements -> roadmap -> phase plans -> execution -> verification).
2. Enforce test-first planning gates and developer readiness gates before tester handoff.
3. Add structured UAT and gap-closure loops.
4. Add health/repair, continuity, and deterministic state management.
5. Keep Optimus strengths: worker orchestration, rate gating, branch lineage, strict handoff ownership.

---

## Target Architecture

## Core lanes
- **Planning lane**: product scope + phased plan generation + plan quality checks.
- **Execution lane**: Optimus cycle controller + worker dispatch + deterministic state.
- **Verification lane**: tester/reviewer + UAT + gap generation + closure planning.

## New control artifacts
- `reports/optimus-prime/planning/PROJECT.md`
- `reports/optimus-prime/planning/REQUIREMENTS.md`
- `reports/optimus-prime/planning/ROADMAP.md`
- `reports/optimus-prime/planning/STATE.md`
- `reports/optimus-prime/planning/TEST_CONTRACT.md`
- `reports/optimus-prime/planning/PLAYWRIGHT_UAT_MATRIX.md`

---

## B1 — Planning Lifecycle (GSD-style)

### Scope
Create commands/workflows to build deterministic planning artifacts:
- initialize project definition
- build requirements with phase traceability
- produce execution roadmap
- phase-specific discuss/research/plan steps

### Required outputs
- every phase has a machine-parseable plan packet set
- every plan maps to requirement IDs
- every requirement maps to at least one plan

### Acceptance criteria
- no phase execution allowed without valid requirements mapping
- no plan accepted with missing requirement coverage

---

## B2 — Plan-Quality Gates (Pre-Execution)

### Scope
Introduce `plan-check` enforcement similar to GSD:
- requirement coverage gate
- task completeness gate
- dependency/wave correctness gate
- key-link/wiring gate
- scope-size sanity gate
- context compliance gate (locked decisions vs deferred ideas)

### Acceptance criteria
- failed plan gate blocks dispatch
- gate output is machine-readable and persisted

---

## B3 — Test-First Contract + Dev Ready Gate

### Scope
For each story/packet, enforce test contract before coding:
- automated checks per acceptance criterion
- Playwright/browser scenarios when UI flows are in scope
- explicit evidence format for developer handoff

### Required artifacts
- `TEST_CONTRACT.md` per phase
- `DEV_READY_EVIDENCE.json` per task

### Gate policy
- tester dispatch blocked if `DEV_READY_EVIDENCE.json` missing or failing
- reviewer decision blocked if test-contract traceability is incomplete

---

## B4 — UAT + Gap Closure Loop

### Scope
Add user-facing verification workflow:
- derive testable outcomes from summaries
- conversational pass/fail collection
- create structured gaps file
- generate gap-closure plans automatically

### Required artifacts
- `UAT.md` per phase
- `VERIFICATION.md` per phase
- `GAPS.md` or equivalent structured gap payload

### Acceptance criteria
- unresolved gaps automatically become new planning inputs
- phase cannot be marked fully complete if blocking gaps remain

---

## B5 — Reliability & Continuity Layer

### Scope
Add maintenance and recovery commands:
- health check for planning/orchestration state
- auto-repair for deterministic fixable issues
- pause/resume continuity files for interrupted cycles
- status/progress snapshot command

### Acceptance criteria
- deterministic health report with pass/fail codes
- resume restores last known working state and pending actions

---

## B6 — Runtime Integration with Lane A Controller

### Scope
Bind planning/verifier outputs into controller-aware orchestration:
- controller events trigger Optimus decisions from validated planning state
- directive schemas include requirement/story/test references
- terminal stop still restricted to Lane A rules

### Acceptance criteria
- Optimus cannot claim mission complete without:
  - controller terminal final state, and
  - requirement + verification completion evidence

---

## Public Interfaces / Types

## 1) Plan packet schema
Fields: `phase`, `plan_id`, `requirements[]`, `tasks[]`, `depends_on[]`, `must_haves`, `verify_commands[]`.

## 2) Test contract schema
Fields: `requirement_id`, `story_id`, `acceptance_criteria`, `automated_verify[]`, `playwright_verify[]`, `evidence_expectations`.

## 3) Dev ready evidence schema
Fields: `task_identifier`, `checks[]`, `results`, `artifacts[]`, `decision`, `blockers[]`, `generated_at`.

## 4) Verification/UAT schema
Fields: `test_case`, `expected`, `result`, `severity`, `gap_id`, `needs_replan`.

---

## Test Cases (Lane B)
1. Plan with missing requirement IDs is rejected.
2. Plan with invalid dependency graph is rejected.
3. Plan with missing automated verify commands is rejected.
4. Task without `DEV_READY_EVIDENCE.json` cannot enter tester stage.
5. UI task without Playwright matrix entries is flagged/rejected.
6. UAT failure creates a structured gap entry.
7. Gap entry is convertible into a valid closure plan packet.
8. Health command detects missing/corrupt planning state files.
9. Resume command reconstructs active context and pending actions.

---

## Definition of Done (Lane B)
- Full planning lifecycle exists with deterministic artifacts.
- Pre-execution plan gates are enforced and blocking.
- Test-first contract and dev-ready gate are enforced.
- UAT and gap-closure loop is operational.
- Health + resume reliability layer is operational.
- Lane A controller remains authoritative for loop continuity and terminal stops.

---

## Explicit Assumptions
- No backward compatibility requirement with Agents repo implementation details.
- Lane B focuses on capability completion, not packaging/distribution UX.
- Lane C will package and polish installation/runtime UX.
