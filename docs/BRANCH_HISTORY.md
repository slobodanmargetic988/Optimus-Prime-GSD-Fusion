# Branch history and release posture

Last audited: 2026-08-27.

This file records why notable long-lived or memorable branches exist, and whether
they should be used as a base for future work. It is intentionally operator-facing:
use commit history for exact diffs, and use this file for orientation.

## Recommended checkout points

### `main` / `github/main`

- Status: preferred stable code snapshot on the GitHub remote.
- Current audited commit: `e686d9c` (`2026-04-02`) - `Revert "TASK-028 add merge evidence checker [DONE][lane:phase-3/lane-a][task:TASK-028]"`.
- Use when: another person wants to inspect or try the integrated project code from git.
- Notes: includes the large OP Simple canary integration from March 2026, then reverts the merge-evidence checker task that was not kept.

### `origin/main`

- Status: preferred stable code snapshot on the Gitea remote.
- Current audited commit: `bb833fc` (`2026-08-06`) - `docs: license project under Apache 2.0`.
- Use when: another person is cloning from the Gitea `origin` remote.
- Notes: functionally appears to be `github/main` plus licensing files (`LICENSE`, `NOTICE`).

### `v0.3.0-rc.2`

- Status: best installable prerelease snapshot found during the audit.
- Date: `2026-02-27`.
- Use when: someone wants to test the private release/install pipeline rather than a working branch.
- Notes: the GitHub release exists, release readiness validation passes, and the Lane C release bundle builds locally.

## Branches to understand, not necessarily use

### `codex/simple-op`

- Status: historical feature/stabilization branch; already merged into `main`.
- Current audited commit: `fb973b7` (`2026-03-12`) - `Restore missing op-simple watchdog/state helper functions`.
- Original purpose: stabilize the OP Simple runtime path, especially recovery, watchdog/state helpers, quiet-cycle behavior, resume behavior, and Blackbox executor lane/worker routing.
- Use when: you need to understand the development history behind OP Simple runtime recovery or Blackbox executor integration.
- Do not use as: the default branch for new work, because its intended value has been integrated into `main`.

### `op-simple-canary-20260314T214654Z-ac48393d`

- Status: historical canary/run-base branch; already merged into `main`.
- Current audited commit: `bbb8ff1` (`2026-04-02`) - `op-plan: add repo-local planner prompt template override`.
- Original purpose: a larger OP Simple canary run that integrated many task branches and runtime hardening changes.
- Use when: investigating the March 2026 canary run or the exact integration sequence before it entered `main`.
- Notes: per repo policy, do not edit prompt templates; if this branch suggests useful prompt wording, carry it forward as narrative guidance only.

### `langstack` / `github/langstack`

- Status: experiment branch; not merged into `main`.
- Current audited commit: `af9ac0a` (`2026-06-21`) - `Trace OP manager runtime with live LangSmith spans`.
- Original purpose: experiment with LangSmith tracing for OP manager/runtime visibility.
- Use when: there is a serious need to revive LangSmith tracing work or compare OP wall-clock behavior in LangSmith.
- Do not use as: a stable product branch or default base for normal OP development.
- Notes: the repo contains `docs/langsmith-tracing-experiment.md` with the experiment details.

### `codex/main-major-sync-20260402`

- Status: integration support branch aligned with `main`.
- Current audited commit: `e686d9c` (`2026-04-02`), same as audited `main`.
- Original purpose: mainline sync/integration point around the large OP Simple canary merge and the later revert of `TASK-028`.
- Use when: reconstructing why the April 2026 mainline ended at the current `main` state.

### `codex/apache-2-license-main`

- Status: docs/licensing branch aligned with `origin/main`.
- Current audited commit: `bb833fc` (`2026-08-06`) - `docs: license project under Apache 2.0`.
- Original purpose: add Apache 2.0 project licensing files.
- Use when: checking the licensing update before syncing `github/main` and `origin/main`.

## Branch families

### `op-simple-canary-*`

- Status: run-base, canary, or worker branches.
- Meaning: these names usually represent autonomous OP Simple test/build runs.
- Use when: investigating a specific run's evidence, task integration sequence, or failure mode.
- Do not use as: stable branches for outside users unless a branch has been explicitly promoted in this file.

### `*-wNN`, `*-taskNNN`, and `*-taskNNN-dev`

- Status: worker/task branches.
- Meaning: these are narrow implementation or reconciliation slices from OP runs.
- Use when: tracing a specific task or cherry-picking a known fix.
- Do not use as: user-facing or stable branches.

### `lane-base/*`

- Status: lane aggregation or review base branches.
- Meaning: these represent intermediate lane-level integration points.
- Use when: reviewing lane history or reconstructing merge decisions.
- Do not use as: a default development base unless current planning explicitly says so.

## Audit notes

- The local checkout during this audit was `langstack`.
- The local worktree already had unrelated modifications in `.claude/skills/*`, `AGENTS.md`, and `CLAUDE.md`; this audit did not interpret or revert those changes.
- A temporary worktree at `origin/main` was used for checks and then removed.
- `python3 -m scripts.release.validate_release_readiness --repo-root /tmp/opgsd-origin-main --version 0.3.0-rc.2` passed.
- `python3 -m scripts.release.build_lane_c_bundle --repo-root /tmp/opgsd-origin-main --out-dir /tmp/opgsd-origin-main/dist-check --version 0.3.0-rc.2 --json-pretty` passed.
- A focused pytest run on `origin/main` reached `285 passed` before being interrupted after roughly four minutes while it was still running. No test failure had appeared before the interruption.
- A full `python3 -m pytest` without additional setup failed during collection because import paths allowed `op-tools/strategy/scripts` to shadow the top-level `scripts` package. Treat that as a test invocation/setup caveat, not as a direct stability verdict.
