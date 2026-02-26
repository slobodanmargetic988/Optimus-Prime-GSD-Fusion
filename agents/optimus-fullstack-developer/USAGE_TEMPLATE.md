# Usage Template

## Blank Template
```text
Agent: optimus-fullstack-developer
Goal: Execute one Optimus packet in automated-handoff mode with concise machine summary.
Inputs: task_identifier:
Inputs: goal:
Inputs: repo_root:
Inputs: worktree_root:
Inputs: branch_name:
Inputs: start_from_branch:
Inputs: start_from_commit:
Inputs: acceptance_criteria:
Inputs: tracking_mode: automated-handoff
Inputs: packet_version:
Inputs: default_branch: main
Inputs: complexity_hint: medium
Inputs: changed_files_hint:
Inputs: test_focus:
Inputs: constraints:
Inputs: fallback_branch_suffix: -dev
Inputs: db_seed_profile: minimal
Inputs: developer_tooling_policy: tool-first
Constraints: No Linear updates. No orchestration file writes. Minimum checks required for acceptance criteria only. Summary must be concise and emoji-free. Developer should prefer built-in dev tools when task scope matches (`dev-ephemeral-db-runner`, `dev-benchmark-runner`, `dev-openapi-client-sync`, `dev-check-bundle`, `dev-handoff-summary-builder`), using manual commands only when tool is unavailable or packet explicitly requires manual path (and then report skipped tool + reason). If DB-facing behavior changes, developer must keep `reset -> migrate -> seed` runnable on a task-scoped temporary DB and update seed/reset scripts as needed (explicit DB URL targeting required).
Output: Code changes + task commit(s) + strict concise summary for Optimus
```

## Filled Example
```text
Agent: optimus-fullstack-developer
Goal: Implement MYO-23 menu navbar behavior fix in assigned workstation with minimal token chatter.
Inputs: task_identifier: MYO-23
Inputs: goal: Fix mobile menu navbar toggle behavior and preserve desktop layout behavior.
Inputs: repo_root: ../Ouroboros
Inputs: worktree_root: ../workstation-2
Inputs: branch_name: MYO-23-make-menu-navbar
Inputs: start_from_branch: MYO-22-menu-shell
Inputs: start_from_commit: 9f3a1c2
Inputs: acceptance_criteria: Mobile toggle works on first click, close behavior works, desktop nav remains unchanged, no console errors.
Inputs: tracking_mode: automated-handoff
Inputs: packet_version: 4
Inputs: default_branch: main
Inputs: complexity_hint: medium
Inputs: changed_files_hint: src/components/navbar, src/styles/navbar.css
Inputs: test_focus: component tests for navbar interactions + production build
Inputs: constraints: Keep patch scoped to navbar only.
Inputs: fallback_branch_suffix: -dev
Inputs: db_seed_profile: minimal
Inputs: developer_tooling_policy: tool-first
Constraints: No Linear updates. No orchestration file writes. Minimum checks required for acceptance criteria only. Summary must be concise and emoji-free. Developer should prefer built-in dev tools when task scope matches (`dev-ephemeral-db-runner`, `dev-benchmark-runner`, `dev-openapi-client-sync`, `dev-check-bundle`, `dev-handoff-summary-builder`), using manual commands only when tool is unavailable or packet explicitly requires manual path (and then report skipped tool + reason). If DB-facing behavior changes, developer must keep `reset -> migrate -> seed` runnable on a task-scoped temporary DB and update seed/reset scripts as needed (explicit DB URL targeting required).
Output: Code changes + task commit(s) + strict concise summary for Optimus
```
