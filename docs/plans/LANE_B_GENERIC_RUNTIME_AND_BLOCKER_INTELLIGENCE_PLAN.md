# Lane B — Generic Runtime Orchestration + Blocker Intelligence Plan

Updated: 2026-02-26

## Objective

Make Optimus project-agnostic for browser/runtime tasks and systematically learn from recurring blockers.

## Outcomes

1. Runtime handling is strategy-driven (`none|external_url|shared_runtime|isolated_runtime`), not framework hardcoded.
2. Playwright user-flow testing defaults to shared runtime consumption.
3. Parallel tester runtime startup collisions are eliminated by policy.
4. All blocking states are persisted to a canonical blocker event stream.
5. Recurring blockers are aggregated into adaptation candidates.

## Scope

- Add runtime strategy contracts and state registries.
- Add runtime coordination skill/script.
- Add blocker event and blocker index generation.
- Integrate runtime payload into worker packet generation.
- Extend orchestration snapshot visibility for runtime/blockers.

## Non-goals

- Hardcoding Nuxt/Next/Vite behaviors in orchestration logic.
- Forcing tester-owned frontend startup for standard browser flow verification.
- Replacing project-specific runtime commands with universal defaults.

## Delivery Order

### Step 1 — Contracts + Files
- Create contracts:
  - `docs/contracts/RUNTIME_PROFILES_CONTRACT.md`
  - `docs/contracts/BLOCKER_EVENT_CONTRACT.md`
- Add default config/state files:
  - `reports/optimus-prime/config/RUNTIME_PROFILES.json`
  - `reports/optimus-prime/RUNTIME_REGISTRY.json`
  - `reports/optimus-prime/TEST_RUNTIME_LEASES.json`
  - `reports/optimus-prime/BLOCKERS.jsonl`
  - `reports/optimus-prime/BLOCKER_INDEX.json`

### Step 2 — Runtime Strategy Resolver
- Implement `runtime-coordinator` skill.
- Resolve per-task runtime strategy with override support.
- Determine shared/external/isolated behavior from profile + task metadata.

### Step 3 — Runtime Registry + Lease Control
- Maintain runtime instance registry.
- Maintain tester lease state for mutating flow policies:
  - `serialized`
  - `account_pool`
  - `isolated`

### Step 4 — Packet Integration
- Extend dispatch packet with runtime fields:
  - `runtime_strategy`
  - `runtime_id`
  - `base_url`
  - `lease_id`
  - `tester_must_not_start_runtime`

### Step 5 — Tester Startup Guard
- Enforce no self-start runtime policy for shared/external runtime tasks.
- Keep isolated startup only when strategy explicitly requires it.

### Step 6 — Blocker Event Logging
- Ensure blocking outcomes append structured events to `BLOCKERS.jsonl`.
- Include stage, code, category, fingerprint, evidence paths.

### Step 7 — Recurring Blocker Aggregation
- Build/refresh `BLOCKER_INDEX.json` from `BLOCKERS.jsonl`.
- Generate adaptation candidate report:
  - `reports/optimus-prime/BLOCKER_ADAPTATION_CANDIDATES.md`

### Step 8 — Snapshot + Controller Visibility
- Extend `orchestrator-status-snapshot` with runtime and blocker summaries.
- Emit controller directives for runtime and blocker workflows when needed.

### Step 9 — Documentation + Acceptance Validation
- Update Optimus docs and usage templates with runtime/blocker policies.
- Validate with automated tests and dry-run command examples.

## Acceptance Criteria

1. Browser flow tasks can run in parallel without each tester starting frontend.
2. Runtime strategy is config-driven and project-agnostic.
3. Every blocker is written to `BLOCKERS.jsonl`.
4. Recurring blocker fingerprints are aggregated with counts and remediation hints.
5. Optimus can read runtime/blocker state from snapshot outputs deterministically.

## Risks + Mitigations

- Risk: shared runtime data collisions.
  - Mitigation: lease policies + mutating-flow serialization.
- Risk: over-blocking due to strict runtime checks.
  - Mitigation: explicit strategy overrides and staged rollout flags.
- Risk: blocker noise.
  - Mitigation: stable fingerprinting + dedup aggregation.
