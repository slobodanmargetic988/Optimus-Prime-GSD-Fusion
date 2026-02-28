# Lane D: Autonomous Reliability and Chaos Hardening Plan (Future)

## Summary
Lane D is a future hardening lane focused on rare but high-impact operational failures during long autonomous runs. It does not add product features; it stress-proves stop/resume, worker lifecycle, lock safety, and artifact integrity under real process and filesystem faults.

## Scope
1. Real process chaos drills for worker halt behavior.
2. Filesystem fault injection for stop/build artifact paths.
3. Repeated stop/resume convergence soak runs.
4. Concurrency and lock-contention stress.
5. Forensics integrity checks for stop/build/runtime artifacts.
6. Deterministic reliability gate for release readiness.

## Non-Goals
1. Lane C packaging/distribution changes.
2. New user-facing command surface.
3. Legacy/backward-compatibility paths.

## Workstreams (Ordered)

### D1: Process Lifecycle Chaos
1. Add integration chaos tests with real subprocess workers.
2. Cover SIGTERM ignored, SIGKILL fallback, exit races, and stale-registry/live-PID cases.

Acceptance:
1. No orphan workers after stop flow.
2. Deterministic per-worker stop results on every run.

### D2: Artifact and Filesystem Fault Injection
1. Add fault harness for write/archive/backup/replace failure paths.
2. Cover permission errors, partial writes, atomic rename failures, and corrupt JSON reads.

Acceptance:
1. No uncaught exceptions in operator-facing commands.
2. Lock release is guaranteed on all failure paths.
3. Correct blocked vs stopped semantics are preserved.

### D3: Stop/Resume Convergence Soak
1. Add long-run randomized interruption suites.
2. Stop at varying cycle points (pre-dispatch, post-dispatch, artifact refresh, reconciliation window).

Acceptance:
1. No infinite in-progress stalls.
2. No false completion under drift.
3. Deterministic reconcile outcomes over repeated resumes.

### D4: Concurrency and Lock Safety
1. Stress parallel `/op-build` and `/op-resume` invocations.
2. Validate stale-lock cleanup and lock owner correctness under process termination.

Acceptance:
1. Single-flight behavior holds.
2. No split-brain loop execution.
3. No persistent false `lock_conflict` after failures.

### D5: Ledger and Forensics Integrity
1. Add validators for `OPERATOR_STOP_STATE.json`, `BUILD_STATE.json`, `WORKER_REGISTRY.json`, and event/handoff parity.
2. Validate consistency after interrupted writes and retries.

Acceptance:
1. Artifacts remain internally consistent.
2. Postmortem reconstruction is always possible from ledgers.

### D6: Reliability Gate and CI
1. Add deterministic gate script and CI job for required hardening scenarios.
2. Produce machine-readable gate artifact at each run.

Acceptance:
1. Gate blocks on any required scenario failure.
2. Gate artifact is deterministic and release-auditable.

## Public Interfaces and Artifacts

### 1) Reliability Gate Artifact
Path: `reports/optimus-prime/planning/LANE_D_RELIABILITY_GATE.json`

Required fields:
1. `schema_version`
2. `generated_at`
3. `ok`
4. `required_scenarios`
5. `failed_scenarios`
6. `status` (`passed|blocked`)
7. `next_action`

### 2) Optional Build Diagnostics Extension
Potential `BUILD_STATE.json` extension:
1. `reliability_counters.stop_apply_failures`
2. `reliability_counters.reconcile_failures`
3. `reliability_counters.lock_conflicts_resolved`
4. `reliability_counters.orphan_kill_attempts`

## Test Matrix (Lane D)
1. Process chaos suite on macOS and Linux.
2. Filesystem fault-injection suite for stop/archive/build artifact paths.
3. Stop/resume soak suite (high-cycle randomized runs).
4. Concurrency stress suite for locking and race conditions.
5. Existing Lane B matrix as regression baseline after each D batch.

## Definition of Done
1. No known crash-class failures remain in autonomous control paths.
2. No orphan worker leakage in process chaos suites.
3. Deterministic blocked/stopped semantics under injected failures.
4. CI-enforced reliability gate is green on target platforms.
5. Lane D status docs are reconciled with evidence links.

## Assumptions and Defaults
1. New-only model remains strict with no legacy compatibility branches.
2. Deterministic safety behavior is prioritized over throughput.
3. Lane D executes after current higher-priority roadmap work is complete.
