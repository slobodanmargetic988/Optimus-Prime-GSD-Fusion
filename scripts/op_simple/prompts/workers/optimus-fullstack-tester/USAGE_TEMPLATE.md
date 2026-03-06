# Usage Template

## Blank Template
```text
Agent: optimus-fullstack-tester
Goal: Execute one Optimus test packet and return concise decision for routing.
Inputs: task_identifier:
Inputs: repo_root:
Inputs: worktree_root:
Inputs: branch_name:
Inputs: start_from_branch:
Inputs: start_from_commit:
Inputs: acceptance_criteria:
Inputs: test_target:
Inputs: tracking_mode: automated-handoff
Inputs: packet_version:
Inputs: harness_mode: targeted
Inputs: test_focus:
Inputs: fallback_branch_suffix: -test
Inputs: constraints:
Inputs: tester_tooling_policy: tool-first
Constraints: No Linear updates. No orchestration file writes. No new task before reviewer outcome for current task. Summary must be concise and emoji-free. Tester should prefer built-in tester tools when scope matches (`tester-preflight-resolver`, `tester-targeted-pytest-runner`, `tester-handoff-summary-builder`), using manual commands only when tool is unavailable or packet explicitly requires manual path (and then report skipped tool + reason). If DB-backed checks are required, tester must start from fresh task DB state (`reset -> migrate -> seed`) and not reuse previous task DB state. Tester runtime is expected unsandboxed by default unless user explicitly requests sandboxed mode.
Output: Test evidence + strict concise summary for Optimus
```

## Filled Example
```text
Agent: optimus-fullstack-tester
Goal: Validate MYO-23 navbar fix packet and return deterministic routing decision.
Inputs: task_identifier: MYO-23
Inputs: repo_root: ../Ouroboros
Inputs: worktree_root: ../workstation-4
Inputs: branch_name: MYO-23-make-menu-navbar
Inputs: start_from_branch: MYO-22-menu-shell
Inputs: start_from_commit: 9f3a1c2
Inputs: acceptance_criteria: Mobile toggle open/close stable, desktop navbar unchanged, no UI errors.
Inputs: test_target: navbar interaction tests + production build smoke
Inputs: tracking_mode: automated-handoff
Inputs: packet_version: 7
Inputs: harness_mode: targeted
Inputs: test_focus: responsive behavior and click-race scenarios
Inputs: fallback_branch_suffix: -test
Inputs: constraints: Keep test scope to navbar surfaces only.
Inputs: tester_tooling_policy: tool-first
Constraints: No Linear updates. No orchestration file writes. No new task before reviewer outcome for current task. Summary must be concise and emoji-free. Tester should prefer built-in tester tools when scope matches (`tester-preflight-resolver`, `tester-targeted-pytest-runner`, `tester-handoff-summary-builder`), using manual commands only when tool is unavailable or packet explicitly requires manual path (and then report skipped tool + reason). If DB-backed checks are required, tester must start from fresh task DB state (`reset -> migrate -> seed`) and not reuse previous task DB state. Tester runtime is expected unsandboxed by default unless user explicitly requests sandboxed mode.
Output: Test evidence + strict concise summary for Optimus
```
