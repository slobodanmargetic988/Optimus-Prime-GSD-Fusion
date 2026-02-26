# Examples

Use these examples as starting points. Adapt repo paths, checks, and acceptance criteria to your own task packet.

## Example 1: Standard Developer Completion

### Input
```text
Agent: optimus-fullstack-developer
Goal: Implement user-profile timezone preferences end-to-end.
Inputs: task_identifier: MYO-81
Inputs: goal: Add timezone selector in settings UI and persist timezone in backend profile service.
Inputs: repo_root: ../Ouroboros
Inputs: worktree_root: ../workstation-1
Inputs: branch_name: MYO-81-profile-timezone
Inputs: start_from_branch: main
Inputs: start_from_commit: 3c81a2f
Inputs: acceptance_criteria: Timezone saves correctly, is returned by API, and is rendered in settings reload.
Inputs: tracking_mode: automated-handoff
Inputs: packet_version: 2
Inputs: test_focus: backend tests for profile update + frontend settings tests + build
Constraints: No Linear updates. Keep summary concise and machine-readable.
Output: Code + commit(s) + concise summary for Optimus
```

### Expected Output
```text
Implements backend and frontend changes scoped to timezone preference feature.
Runs only relevant checks for touched backend/frontend surfaces.
Commits with task identifier.
Returns short summary fields: task_identifier, branch, head_commit, files_changed_count, checks, decision.
```

## Example 2: Branch Active Elsewhere, Fallback Branch Used

### Input
```text
Agent: optimus-fullstack-developer
Goal: Continue assigned packet even when assigned branch is locked in another worktree.
Inputs: task_identifier: MYO-23
Inputs: goal: Fix navbar toggle race condition.
Inputs: repo_root: ../Ouroboros
Inputs: worktree_root: ../workstation-3
Inputs: branch_name: MYO-23-make-menu-navbar
Inputs: start_from_branch: MYO-22-menu-shell
Inputs: start_from_commit: 8a4de91
Inputs: acceptance_criteria: Toggle open/close works consistently under rapid clicks.
Inputs: tracking_mode: automated-handoff
Inputs: packet_version: 6
Inputs: fallback_branch_suffix: -dev
Constraints: Assigned branch checkout denied because branch is active in another worktree.
Output: Continue work on fallback branch and report mapping in concise summary
```

### Expected Output
```text
Creates fallback branch MYO-23-make-menu-navbar-dev from same base.
Completes fix and commits on fallback branch.
Returns concise summary that includes fallback branch mapping and decision ready_for_test.
```

## Example 3: Blocked by Missing Secret

### Input
```text
Agent: optimus-fullstack-developer
Goal: Add signed upload endpoint and UI uploader wiring.
Inputs: task_identifier: MYO-145
Inputs: goal: Implement signed upload flow for profile avatars.
Inputs: repo_root: ../Ouroboros
Inputs: worktree_root: ../workstation-2
Inputs: branch_name: MYO-145-avatar-upload
Inputs: start_from_branch: main
Inputs: start_from_commit: 5ab1023
Inputs: acceptance_criteria: Upload succeeds with signed URL and UI reflects uploaded image.
Inputs: tracking_mode: automated-handoff
Inputs: packet_version: 1
Constraints: Required cloud signing secret is missing in environment.
Output: blocked summary for Optimus with exact unblock requirement
```

### Expected Output
```text
Stops after confirming blocker is external and required for acceptance.
Returns blocked summary with exact missing secret and required user action.
Does not update Linear and does not produce noisy narrative text.
```
