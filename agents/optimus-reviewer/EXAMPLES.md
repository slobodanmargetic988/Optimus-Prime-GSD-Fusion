# Examples

Use these examples as starting points. Adapt review focus and risk criteria to your own task packet.

## Example 1: Review Passed

### Input
```text
Agent: optimus-reviewer
Goal: Final review of timezone preference feature after testing.
Inputs: task_identifier: MYO-81
Inputs: repo_root: ../Ouroboros
Inputs: worktree_root: ../workstation-8
Inputs: branch_name: MYO-81-profile-timezone-test
Inputs: start_from_branch: MYO-81-profile-timezone
Inputs: start_from_commit: 7b2f941
Inputs: acceptance_criteria: Timezone persists and renders correctly after reload.
Inputs: dev_summary: Added backend timezone persistence and settings UI selector wiring.
Inputs: test_summary: API tests, UI tests, and build pass.
Inputs: tracking_mode: automated-handoff
Inputs: packet_version: 4
Inputs: review_focus: correctness and maintainability of patch
Constraints: No Linear updates. Return concise summary only.
Output: review decision summary for Optimus
```

### Expected Output
```text
Validates developer and tester evidence with focused diff review.
Returns concise summary with decision review_passed.
Includes required fields only.
```

## Example 2: Needs Developer Fix

### Input
```text
Agent: optimus-reviewer
Goal: Catch remaining risk before merge routing.
Inputs: task_identifier: BILL-55
Inputs: repo_root: ../Billing
Inputs: worktree_root: ../workstation-9
Inputs: branch_name: BILL-55-approval-flow-test
Inputs: start_from_branch: BILL-55-approval-flow
Inputs: start_from_commit: 4d70a11
Inputs: acceptance_criteria: Non-approvers blocked and denial state consistently rendered.
Inputs: dev_summary: Added role guard and denial banner.
Inputs: test_summary: Main path tests pass.
Inputs: tracking_mode: automated-handoff
Inputs: packet_version: 3
Inputs: review_focus: edge-case authorization paths
Constraints: No Linear updates. Return concise summary only.
Output: review decision summary for Optimus
```

### Expected Output
```text
Finds unresolved edge case or regression risk requiring code change.
Returns concise summary with decision needs_dev_fix and short findings.
Does not produce long narrative output.
```

## Example 3: Branch Conflict Fallback

### Input
```text
Agent: optimus-reviewer
Goal: Continue review when assigned branch is active elsewhere.
Inputs: task_identifier: MYO-23
Inputs: repo_root: ../Ouroboros
Inputs: worktree_root: ../workstation-10
Inputs: branch_name: MYO-23-make-menu-navbar-test
Inputs: start_from_branch: MYO-23-make-menu-navbar
Inputs: start_from_commit: a1b2c3d
Inputs: acceptance_criteria: Navbar behavior remains correct across responsive breakpoints.
Inputs: dev_summary: Toggle race fix implemented.
Inputs: test_summary: Targeted tests pass.
Inputs: tracking_mode: automated-handoff
Inputs: packet_version: 10
Inputs: fallback_branch_suffix: -review
Constraints: Branch checkout denied due active usage in another worktree.
Output: fallback execution and concise summary
```

### Expected Output
```text
Creates and uses MYO-23-make-menu-navbar-test-review.
Completes focused review and returns concise summary with fallback mapping.
No Linear updates performed by reviewer.
```
