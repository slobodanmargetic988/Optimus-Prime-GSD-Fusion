# Usage Template

## Blank Template
```text
Agent: optimus-reviewer
Goal: Review one tested unit and return final routing decision.
Inputs: task_identifier:
Inputs: repo_root:
Inputs: worktree_root:
Inputs: branch_name:
Inputs: start_from_branch:
Inputs: start_from_commit:
Inputs: acceptance_criteria:
Inputs: dev_summary:
Inputs: test_summary:
Inputs: tracking_mode: automated-handoff
Inputs: packet_version:
Inputs: review_focus:
Inputs: risk_focus:
Inputs: fallback_branch_suffix: -review
Inputs: constraints:
Constraints: No Linear updates. No orchestration file writes. Summary must be concise and emoji-free.
Output: Final review decision summary for Optimus
```

## Filled Example
```text
Agent: optimus-reviewer
Goal: Final review MYO-23 after developer fix and tester pass.
Inputs: task_identifier: MYO-23
Inputs: repo_root: ../Ouroboros
Inputs: worktree_root: ../workstation-7
Inputs: branch_name: MYO-23-make-menu-navbar-test
Inputs: start_from_branch: MYO-22-menu-shell
Inputs: start_from_commit: 9f3a1c2
Inputs: acceptance_criteria: Navbar toggle stable on mobile, desktop unchanged, no regressions in navigation behavior.
Inputs: dev_summary: Developer implemented debounce fix and state guard for toggle race.
Inputs: test_summary: Targeted navbar tests and build pass; no failures.
Inputs: tracking_mode: automated-handoff
Inputs: packet_version: 9
Inputs: review_focus: diff quality and regression risk
Inputs: risk_focus: navigation accessibility and mobile interaction consistency
Inputs: fallback_branch_suffix: -review
Inputs: constraints: Keep review scoped to task surfaces only.
Constraints: No Linear updates. No orchestration file writes. Summary must be concise and emoji-free.
Output: Final review decision summary for Optimus
```
