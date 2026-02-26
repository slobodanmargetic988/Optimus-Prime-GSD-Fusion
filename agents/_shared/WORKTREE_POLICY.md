# Shared Worktree Policy
Last Updated: 2026-02-24 19:42 CET

Use this file as the default policy for worktree handling across agents.

## Policy
- Do not create a new Git worktree without explicit user permission.
- Prefer resolving branch-switch blockers inside the current assigned worktree.
- If local tracked changes block branch switch and a commit will safely resolve it, commit with a clear message and continue.
- If commit is unsafe or ambiguous, stop and ask the user how to proceed.

## Dedicated Worker Slots
- Preferred orchestration model is dedicated slot worktrees:
  - `dev-1`, `dev-2`, `dev-3`, `test-1`, `review-1`
- One slot must keep one stable worktree path during a sprint cycle.
- Inside each slot worktree, each task must use its own feature branch:
  - branch format: `codex/<slot>/<issue-or-task-id>`
- Never run two different active tasks on the same branch.

## Branch Checkout Fallback (Locked Branch)
- Trigger: assigned branch `codex/<slot>/<issue-or-task-id>` cannot be checked out because it is already active in another worktree.
- Developer fallback branch format: `codex/<slot>/<issue-or-task-id>-dev`
- Tester fallback branch format: `codex/<slot>/<issue-or-task-id>-test`
- Worker must:
  - create fallback branch from packet anchor (`start_from_commit`) and continue work there
  - commit task changes on fallback branch
  - report fallback mapping in completion summary (`intended_branch`, `fallback_branch`, `fallback_reason=active-elsewhere`)

## Fallback Merge-Back Ownership (Optimus)
- Optimus decides and performs fallback merge-back.
- Default action: merge fallback branch into intended branch after worker completion.
- Defer merge-back only when another worker is actively running on that exact intended branch.
- If deferred, queue merge-back and execute immediately after that active worker exits the intended branch.
- Record merge-back/defer decision in handoff/cycle logs and update branch lineage.

## Hard Report Write Gate (Tester/Reviewer)
- Tester and reviewer roles must write report/state/event files only inside the currently checked-out git worktree root.
- Forbidden:
  - writing to an absolute base-repo path that is outside current `git rev-parse --show-toplevel`
  - writing to shared sprint files for task-specific output
  - writing task output outside `/reports/issues/<task_identifier>/`
- Required preflight before any write:
  1. `WORKTREE_ROOT="$(git rev-parse --show-toplevel)"`
  2. `CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"`
  3. verify branch matches task context (`branch_name` input or contains task identifier)
  4. set `ISSUE_DIR="$WORKTREE_ROOT/reports/issues/<task_identifier>"`
  5. create/write only files under `ISSUE_DIR`
- If any preflight check fails:
  - stop immediately
  - emit blocked/not-ready event
  - do not write any report file

## Safe Auto-Commit Rule
Agent may auto-commit blocked local changes only when all conditions are true:
1. Changes are task-scoped or orchestration/report-file scoped for the current task.
2. Commit resolves branch-switch blocker without hiding unrelated work.
3. Commit message is explicit and traceable (for example `chore: checkpoint local report updates before branch switch`).
4. No destructive git operation is needed.

## Ask-User Rule
Agent must stop and ask the user when any condition is true:
- Local changes appear unrelated/mixed across multiple tasks.
- Agent cannot confidently determine safe commit scope.
- Branch strategy is unclear (for example target branch uncertain).
- Proposed commit would include files the user likely did not intend to checkpoint.

## Override Precedence
1. Explicit user instruction in current request
2. Per-agent explicit input
3. This shared policy file
4. Agent-local fallback behavior
