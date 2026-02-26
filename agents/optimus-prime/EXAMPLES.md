# Examples

Use these examples as starting points. Review and adapt task scope, worker caps, branch policy, and mission target to your own repository and workflow.
For multi-project setups, include `Inputs: worktrees_parent: <repo-parent>/.<repo-name>-workstations` so workstation slots are isolated per repo and hidden by default.

## Example 1: Finish First 20 Tasks With Adaptive Dev Capacity

### Input
```text
Agent: optimus-prime
Goal: Complete first 20 ready tasks while keeping workers token-efficient and deterministic.
Inputs: primary_mission: Finish first 20 ready tasks in current sprint.
Inputs: task_source: Linear project Ouroboros, status Ready, ordered by priority.
Inputs: repo_root: ../Ouroboros
Inputs: tracking_mode: automated-handoff
Inputs: sleep_minutes: 5
Inputs: max_initialized_workers: 10
Inputs: max_running_workers: 6
Inputs: branch_lineage_path: reports/optimus-prime/BRANCH_LINEAGE.json
Inputs: feature_lane_registry_path: reports/optimus-prime/FEATURE_LANES.json
Inputs: packet_require_start_point: true
Inputs: feature_parallelism_policy: feature-affinity-first
Inputs: feature_grouping_fields: parent_issue,epic,label:feature
Inputs: allow_multi_developers_per_feature_when_blocked: true
Inputs: feature_lane_reassignment_policy: sticky-until-complete-or-blocked
Inputs: codex_profile_aliases: codex=default, codex-second=$HOME/.codex-second
Inputs: worker_codex_profile_policy: role:developer=codex-second; role:tester=codex; role:reviewer=codex
Inputs: dispatch_codex_profile_mode: thread-dispatch-codex-home
Inputs: developer_agent_path: agents/optimus-fullstack-developer/README.md
Inputs: tester_agent_path: agents/optimus-fullstack-tester/README.md
Inputs: reviewer_agent_path: agents/optimus-reviewer/README.md
Inputs: worker_role_policy: developers up to 3, testers up to 2, reviewer up to 1
Inputs: developer_scaling: ready 1-3 => 1 dev, ready 4-9 => 2 devs, ready >=10 => 3 devs
Constraints: Workers do not use linear skill. Optimus performs all Linear updates after worker summaries. Every packet includes explicit start_from_branch and start_from_commit resolved from branch lineage state.
Output: reports/optimus-prime logs + continuous cycle summaries + completed dev/test/review chain for mission target
```

### Expected Output
```text
Optimus initializes workstation slots, starts only required developer threads, and keeps at most 6 running workers.
When multiple features are ready, Optimus assigns developers across different features first and keeps feature lanes sticky.
Optimus dispatches complete unit packets and reuses workers by fixed role, fixed thinking profile, and fixed Codex profile assignment.
Tester starts after first developer completion; reviewer starts after first tester completion.
No developer receives a new task until current task passes test and review.
Optimus publishes concise cycle summary, sleeps 5 minutes, and repeats until 20 tasks are fully done.
```

## Example 2: Branch Conflict During Tester Assignment

### Input
```text
Agent: optimus-prime
Goal: Continue orchestration when assigned branch is locked by another worktree.
Inputs: primary_mission: Complete task MYO-23 through review.
Inputs: task_source: Explicit task MYO-23.
Inputs: repo_root: ../Ouroboros
Inputs: tracking_mode: automated-handoff
Inputs: branch_lineage_path: reports/optimus-prime/BRANCH_LINEAGE.json
Inputs: packet_require_start_point: true
Inputs: codex_profile_aliases: codex=default, codex-second=$HOME/.codex-second
Inputs: worker_codex_profile_policy: role:developer=codex-second; role:tester=codex; role:reviewer=codex
Inputs: developer_agent_path: agents/optimus-fullstack-developer/README.md
Inputs: tester_agent_path: agents/optimus-fullstack-tester/README.md
Inputs: reviewer_agent_path: agents/optimus-reviewer/README.md
Constraints: Assigned tester cannot checkout branch codex/test-1/MYO-23 because branch is active elsewhere.
Output: Deterministic fallback branch handling with minimal token chatter
```

### Expected Output
```text
Optimus packet instructs tester to create fallback branch codex/test-1/MYO-23-test.
Tester proceeds with test work on fallback branch and returns short summary.
Optimus records branch mapping in handoff log and merges fallback back into codex/test-1/MYO-23 when branch is free.
If codex/test-1/MYO-23 is actively used by another worker, Optimus defers merge and executes it once that worker is done.
Task remains in deterministic dev/test/review flow without blocking unrelated workers.
```

## Example 3: Stuck Worker Intervention

### Input
```text
Agent: optimus-prime
Goal: Detect and recover from a looping developer worker.
Inputs: primary_mission: Complete 8 tasks.
Inputs: task_source: Ready tasks list MYO-101..MYO-108.
Inputs: repo_root: ../Ouroboros
Inputs: tracking_mode: automated-handoff
Inputs: branch_lineage_path: reports/optimus-prime/BRANCH_LINEAGE.json
Inputs: packet_require_start_point: true
Inputs: codex_profile_aliases: codex=default, codex-second=$HOME/.codex-second, codex-third=$HOME/.codex-third, codex-fourth=$HOME/.codex-fourth
Inputs: worker_codex_profile_policy: slot:dev-1=codex-second; slot:dev-2=codex-second; slot:dev-3=codex-third; slot:test-1=codex-fourth; slot:review-1=codex-fourth
Inputs: dispatch_codex_profile_mode: thread-dispatch-codex-home
Inputs: developer_agent_path: agents/optimus-fullstack-developer/README.md
Inputs: tester_agent_path: agents/optimus-fullstack-tester/README.md
Inputs: reviewer_agent_path: agents/optimus-reviewer/README.md
Constraints: dev-high-1 repeatedly retries same failing command with no progress for multiple cycles.
Output: Controlled intervention and continued mission execution
```

### Expected Output
```text
Optimus flags worker as stale/stuck using cycle logs and repeated-attempt signal.
Optimus sends steering prompt with corrective instructions and timeout.
If still unresolved, Optimus stops that worker, marks task blocked or reassigns to another developer profile, and continues mission cycles.
No worker besides Optimus updates tracking state in Linear.
```

## Example 4: Unmerged Dependency Chain

### Input
```text
Agent: optimus-prime
Goal: Dispatch dependent tasks where MYO-52 and MYO-53 both depend on unmerged MYO-51.
Inputs: primary_mission: Complete MYO-51..MYO-53 in order.
Inputs: task_source: Explicit ordered task set with dependencies MYO-52->MYO-51 and MYO-53->MYO-52.
Inputs: repo_root: ../Ouroboros
Inputs: tracking_mode: automated-handoff
Inputs: branch_lineage_path: reports/optimus-prime/BRANCH_LINEAGE.json
Inputs: packet_require_start_point: true
Constraints: No tasks are merged yet. Each packet must declare exact start anchor from latest unmerged parent branch head commit.
Output: deterministic chained packet dispatch without ambiguous branch starts
```

### Expected Output
```text
Optimus stores MYO-51 branch and head commit in branch lineage registry after developer completion.
MYO-52 packet includes start_from_branch and start_from_commit pointing to MYO-51 head.
MYO-53 packet includes start anchor pointing to latest MYO-52 head.
Workers always receive explicit branch starting point and continue without guesswork.
```

## Example 5: Role-Based Codex Profile Routing

### Input
```text
Agent: optimus-prime
Goal: Use a separate Codex profile for developers while testers and reviewer use default Codex.
Inputs: primary_mission: Complete 10 ready tasks.
Inputs: task_source: Ready tasks in current sprint.
Inputs: repo_root: ../Ouroboros
Inputs: tracking_mode: automated-handoff
Inputs: codex_profile_aliases: codex=default, codex-second=$HOME/.codex-second
Inputs: worker_codex_profile_policy: role:developer=codex-second; role:tester=codex; role:reviewer=codex
Inputs: dispatch_codex_profile_mode: thread-dispatch-codex-home
Constraints: Keep worker thread profile assignment stable after initialization.
Output: background worker dispatch using role-based Codex profiles
```

### Expected Output
```text
Optimus assigns all developer slots to codex-second and tester/reviewer slots to default codex.
Thread-dispatch invocations for developers include --codex-home $HOME/.codex-second.
Tester and reviewer dispatches use default profile with no codex_home override.
Worker registry records codex profile alias per initialized worker thread.
```

## Example 6: Per-Slot Codex Profile Routing

### Input
```text
Agent: optimus-prime
Goal: Pin each worker slot to a specific Codex profile.
Inputs: primary_mission: Complete 20 ready tasks.
Inputs: task_source: Ready tasks in current sprint.
Inputs: repo_root: ../Ouroboros
Inputs: tracking_mode: automated-handoff
Inputs: codex_profile_aliases: codex=default, codex-second=$HOME/.codex-second, codex-third=$HOME/.codex-third, codex-fourth=$HOME/.codex-fourth
Inputs: worker_codex_profile_policy: slot:dev-1=codex-second; slot:dev-2=codex-second; slot:dev-3=codex-third; slot:test-1=codex-fourth; slot:review-1=codex-fourth
Inputs: dispatch_codex_profile_mode: thread-dispatch-codex-home
Constraints: Keep slot profile stable for thread reuse across cycles.
Output: background worker dispatch using slot-based Codex profiles
```

### Expected Output
```text
Optimus resolves profile assignment by slot override and persists it in worker registry.
dev-1 and dev-2 use codex-second; dev-3 uses codex-third; tester/reviewer use codex-fourth.
Each thread-dispatch command uses the correct --codex-home path for the assigned slot profile.
Cycle summaries display worker slot + Codex profile alias for active and idle threads.
```

## Example 7: Single-Profile Rate Gate Wind-Down

### Input
```text
Agent: optimus-prime
Goal: Run normal orchestration but stop handing out new work when primary profile rates are low.
Inputs: primary_mission: Complete ready tasks until rate policy requires wind-down.
Inputs: task_source: Ready tasks in current sprint.
Inputs: repo_root: ../Ouroboros
Inputs: tracking_mode: automated-handoff
Inputs: codex_profile_aliases: codex=default
Inputs: worker_codex_profile_policy: role:developer=codex; role:tester=codex; role:reviewer=codex
Inputs: dispatch_worker_mcp_mode: thread-dispatch-disable-all-by-default
Inputs: worker_mcp_policy: role:developer=none; role:tester=none|playwright,chrome_devtools(on-demand); role:reviewer=none; deny:all-workers=linear,linear_sse; allow:on-demand-developer=context7
Inputs: rate_gate_5h_percent: 15
Inputs: rate_gate_weekly_percent: 10
Inputs: soft_rate_gate_5h_percent: 40
Inputs: soft_rate_gate_weekly_percent: 25
Inputs: soft_rate_gated_max_running_workers: 3
Inputs: rate_reset_wait_max_hours: 4
Inputs: status_check_interval_cycles: 1
Inputs: status_check_on_start: true
Inputs: status_primary_profile_alias: codex
Constraints: Single-profile mode. If 5h or weekly limit is below gate, stop assigning new work. If only gated limit resets within 4h, sleep until reset and continue; otherwise wind down and stop after active workers finish.
Output: rate-aware orchestration with wind-down or wait-and-resume behavior
```

### Expected Output
```text
Optimus runs codex-rate-snapshot for the primary codex profile at startup and every cycle.
If a limit crosses configured gate, Optimus stops dispatching new work immediately.
If hard gates are not hit but soft gate is hit, Optimus reduces active background workers to 3 and only hands out new work within that cap.
If reset is within 4h, Optimus sleeps until reset and resumes dispatch.
If reset is farther than 4h, Optimus enters wind-down and stops after active workers complete.
```

## Example 8: Multi-User Profile Rate Gating (Selective Dispatch)

### Input
```text
Agent: optimus-prime
Goal: Continue dispatching on healthy secondary profiles even when primary profile is gated.
Inputs: primary_mission: Complete as many ready tasks as possible under rate-aware multi-profile routing.
Inputs: task_source: Ready tasks in current sprint.
Inputs: repo_root: ../Ouroboros
Inputs: tracking_mode: automated-handoff
Inputs: codex_profile_aliases: codex=default, codex-second=$HOME/.codex-second, codex-third=$HOME/.codex-third
Inputs: worker_codex_profile_policy: slot:dev-1=codex-second; slot:dev-2=codex-third; slot:test-1=codex-third; slot:review-1=codex
Inputs: dispatch_codex_profile_mode: thread-dispatch-codex-home
Inputs: dispatch_worker_mcp_mode: thread-dispatch-disable-all-by-default
Inputs: worker_mcp_policy: role:developer=none; role:tester=none|playwright,chrome_devtools(on-demand); role:reviewer=none; deny:all-workers=linear,linear_sse; allow:on-demand-developer=context7
Inputs: rate_gate_5h_percent: 15
Inputs: rate_gate_weekly_percent: 10
Inputs: soft_rate_gate_5h_percent: 40
Inputs: soft_rate_gate_weekly_percent: 25
Inputs: soft_rate_gated_max_running_workers: 3
Inputs: rate_reset_wait_max_hours: 4
Inputs: status_check_interval_cycles: 1
Inputs: status_check_on_start: true
Inputs: status_primary_profile_alias: codex
Constraints: Determine profile-running-mode from codex-rate-snapshot profile identity output (auth.json best effort). If accounts differ, treat as multiple-users and gate dispatch per profile, not globally.
Output: profile-selective dispatch based on per-profile rate eligibility
```

### Expected Output
```text
Optimus runs codex-rate-snapshot for codex, codex-second, and codex-third and parses profile identities.
If account identities differ, Optimus records profile-running-mode as multiple-users.
When primary codex profile falls below rate gate, Optimus can still dispatch work to workers on codex-second/codex-third if they remain above gate.
If a profile is not hard-gated but is soft-gated, Optimus throttles active workers on that profile to the soft cap instead of stopping it entirely.
Worker dispatches still use MCP minimization: reviewers/devs run with all MCPs disabled by default, testers get browser MCPs only when a test packet explicitly needs browser verification, and workers never get linear/linear_sse MCP access.
Optimus stops assigning work to any profile once that profile reaches gate and applies wait-or-wind-down when no eligible profiles remain.
```

## Example 9: Feature-Lane Parallelization With Sticky Developer Assignment

### Input
```text
Agent: optimus-prime
Goal: Run three feature streams in parallel without mixing developers across features unless blocked.
Inputs: primary_mission: Complete ready subtasks under features FTR-A, FTR-B, and FTR-C.
Inputs: task_source: Ready subtasks grouped under parent feature issues FTR-A, FTR-B, FTR-C.
Inputs: repo_root: ../Ouroboros
Inputs: tracking_mode: automated-handoff
Inputs: feature_lane_registry_path: reports/optimus-prime/FEATURE_LANES.json
Inputs: feature_parallelism_policy: feature-affinity-first
Inputs: feature_grouping_fields: parent_issue,epic,label:feature
Inputs: allow_multi_developers_per_feature_when_blocked: true
Inputs: feature_lane_reassignment_policy: sticky-until-complete-or-blocked
Inputs: worker_role_policy: developers up to 3, testers up to 2, reviewer up to 1
Constraints: Prefer one developer per feature while multiple features have ready unblocked subtasks. If one feature lane is blocked, allow temporary same-feature parallelism on remaining features using issue-scoped branches.
Output: developer-to-feature lane mapping persisted and referenced in cycle summaries
```

### Expected Output
```text
Optimus assigns dev-1->FTR-A, dev-2->FTR-B, dev-3->FTR-C while all three features have ready work.
Developers stay on their assigned feature lanes across cycles instead of mix-and-match reassignments.
If FTR-C blocks, Optimus may temporarily assign dev-3 to a second issue under FTR-A or FTR-B, but keeps work issue-scoped with separate branches.
Feature lane state and reassignment reasons are recorded in FEATURE_LANES.json and cycle summaries.
```
