# Examples

Use these examples as starting points. Adapt test scope, command set, and decision threshold to your own task packet.

## Example 1: Ready For Review

### Input
```text
Agent: optimus-fullstack-tester
Goal: Validate profile timezone feature before review handoff.
Inputs: task_identifier: MYO-81
Inputs: repo_root: ../Ouroboros
Inputs: worktree_root: ../workstation-5
Inputs: branch_name: MYO-81-profile-timezone
Inputs: start_from_branch: main
Inputs: start_from_commit: 3c81a2f
Inputs: acceptance_criteria: Timezone persists and renders correctly after reload.
Inputs: test_target: profile service tests + settings UI tests + build
Inputs: tracking_mode: automated-handoff
Inputs: packet_version: 3
Inputs: harness_mode: targeted
Constraints: No Linear updates. Return concise summary only.
Output: test decision for Optimus routing
```

### Expected Output
```text
Runs focused backend/frontend checks required for acceptance criteria.
Returns concise summary with decision ready_for_review.
Includes task_identifier, branch, head_commit, checks, and findings.
```

## Example 2: Needs Developer Fix

### Input
```text
Agent: optimus-fullstack-tester
Goal: Validate invoice approval flow and report defects.
Inputs: task_identifier: BILL-55
Inputs: repo_root: ../Billing
Inputs: worktree_root: ../workstation-2
Inputs: branch_name: BILL-55-approval-flow
Inputs: start_from_branch: BILL-54-role-guards
Inputs: start_from_commit: 2f7d91a
Inputs: acceptance_criteria: Non-approvers cannot approve and UI must show denied state.
Inputs: test_target: authorization tests + approval UI interaction checks
Inputs: tracking_mode: automated-handoff
Inputs: packet_version: 2
Inputs: harness_mode: targeted
Constraints: No Linear updates. Return concise summary only.
Output: test decision for Optimus routing
```

### Expected Output
```text
Identifies reproducible authorization or UI regression failure.
Returns concise summary with decision needs_dev_fix and short findings list.
Provides minimal repro clue without long narrative.
```

## Example 3: Branch Conflict Fallback

### Input
```text
Agent: optimus-fullstack-tester
Goal: Continue testing when assigned branch is active in another worktree.
Inputs: task_identifier: MYO-23
Inputs: repo_root: ../Ouroboros
Inputs: worktree_root: ../workstation-6
Inputs: branch_name: MYO-23-make-menu-navbar
Inputs: start_from_branch: MYO-22-menu-shell
Inputs: start_from_commit: 8a4de91
Inputs: acceptance_criteria: Navbar toggle behavior is stable.
Inputs: test_target: navbar tests
Inputs: tracking_mode: automated-handoff
Inputs: packet_version: 8
Inputs: fallback_branch_suffix: -test
Constraints: Branch checkout denied due active usage in another worktree.
Output: fallback execution and concise summary
```

### Expected Output
```text
Creates and uses MYO-23-make-menu-navbar-test.
Runs required test scope and returns concise summary with fallback mapping.
Does not update Linear or orchestration files.
```
