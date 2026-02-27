# Usage Template

## Blank Template
```text
Agent: optimus-prime
Goal: Orchestrate mission completion in automated-handoff mode with cycle-based worker dispatch.
Inputs: primary_mission:
Inputs: task_source:
Inputs: repo_root:
Inputs: worktrees_parent: <repo_parent>/.<repo_name>-workstations
Inputs: tracking_mode: automated-handoff
Inputs: agent_root_path: agents
Inputs: standards_source: agents/agent-making-agent/README.md
Inputs: worktree_policy_path: agents/_shared/WORKTREE_POLICY.md
Inputs: linear_workflow_path: agents/_shared/LINEAR_WORKFLOW.md
Inputs: sleep_minutes: 5
Inputs: max_initialized_workers: 10
Inputs: max_running_workers: 6
Inputs: worker_registry_path: reports/optimus-prime/WORKER_REGISTRY.json
Inputs: cycle_log_path: reports/optimus-prime/CYCLE_LOG.jsonl
Inputs: handoff_log_path: reports/optimus-prime/HANDOFF_LOG.jsonl
Inputs: linear_sync_log_path: reports/optimus-prime/LINEAR_SYNC_LOG.jsonl
Inputs: identity_checkpoint_path: reports/optimus-prime/IDENTITY_CHECKPOINT.md
Inputs: branch_lineage_path: reports/optimus-prime/BRANCH_LINEAGE.json
Inputs: feature_lane_registry_path: reports/optimus-prime/FEATURE_LANES.json
Inputs: packet_require_start_point: true
Inputs: feature_parallelism_policy: feature-affinity-first
Inputs: feature_grouping_fields: parent_issue,epic,label:feature
Inputs: allow_multi_developers_per_feature_when_blocked: true
Inputs: feature_lane_reassignment_policy: sticky-until-complete-or-blocked
Inputs: codex_profile_aliases: codex=default
Inputs: worker_codex_profile_policy: role:developer=codex; role:tester=codex; role:reviewer=codex
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
Inputs: status_profiles_scope: all-configured-plus-primary
Inputs: status_primary_profile_alias: codex
Inputs: orchestration_tooling_policy: deterministic-tool-first
Inputs: rate_status_log_path: reports/optimus-prime/RATE_STATUS_LOG.jsonl
Inputs: profile_rate_registry_path: reports/optimus-prime/PROFILE_RATE_REGISTRY.json
Inputs: rate_gate_action_mode: wind-down-or-wait
Inputs: status_account_parse_required: true
Inputs: developer_agent_path: agents/optimus-fullstack-developer/README.md
Inputs: tester_agent_path: agents/optimus-fullstack-tester/README.md
Inputs: reviewer_agent_path: agents/optimus-reviewer/README.md
Inputs: blocker_project_name: Agents
Inputs: blocker_assignee: me
Inputs: worker_sandbox_policy: role:developer=danger-full-access; role:tester=danger-full-access; role:reviewer=danger-full-access
Inputs: sandboxed_workers_require_explicit_user_request: true
Inputs: tester_fresh_db_per_task_required: true
Inputs: tester_health_registry_path: reports/optimus-prime/TESTER_WORKSTATION_HEALTH.json
Inputs: test_train_mode: off
Inputs: test_branch: test
Inputs: test_next_branch: test-next
Inputs: shared_test_base_url:
Inputs: deploy_test_branch_cmd:
Inputs: test_train_state_path: reports/optimus-prime/TEST_TRAIN_STATE.json
Inputs: test_task_attempts_path: reports/optimus-prime/TEST_TASK_ATTEMPTS.json
Inputs: test_wave_log_path: reports/optimus-prime/TEST_WAVE_LOG.jsonl
Inputs: test_wave_summary_path: reports/optimus-prime/TEST_WAVE_SUMMARY.md
Inputs: worker_role_policy: developers up to 3, testers up to 2, reviewer up to 1
Inputs: developer_scaling: ready 1-3 => 1 dev, ready 4-9 => 2 devs, ready >=10 => 3 devs
Inputs: concurrency_policy: developers do not get next task before test+review pass; testers wait for reviewer outcome before next task
Constraints: Optimus-only Linear updates. Workers do not use linear skill. Workers use minimum required skills only. Worker MCP access must be default-deny via thread-dispatch --disable-all-mcp and expanded only with --enable-only-mcp when packet requirements justify it; never grant workers linear or linear_sse MCP. Worker sandbox mode defaults to `danger-full-access` for developer/tester/reviewer and can be sandboxed only when user explicitly requests it. Every worker packet must include start_from_branch and start_from_commit. Workstation preparation must always pass explicit `--worktrees-parent`: use `worktrees_parent` input when provided, otherwise derive hidden `<repo-parent>/.<repo-name>-workstations` from `repo_root`; never rely on workstation-preparation default parent path. If `tracking_mode=linear`, `linear_workflow_path` must exist and be readable before dispatch; otherwise stop as blocked with remediation. Tool-first enforcement: use `orchestrator-status-snapshot` for status output, `cycle-tick` for cycle decisions, `dispatch-worker-packet` for dispatch/state updates, `linear-handoff-sync` for Linear sync, and `blocker-escalate-to-agents` for unresolved blockers; manual fallback is allowed only when these tools fail/unavailable and must be logged with reason + next fix action. If worker cannot checkout assigned branch `codex/<slot>/<issue>`, worker must continue on `codex/<slot>/<issue>-dev` (developer) or `codex/<slot>/<issue>-test` (tester), commit there, and report intended/fallback mapping; Optimus merges fallback back into intended branch unless that intended branch is actively used by another worker, then merges immediately after it is free. Tester dispatch must pass fresh DB runtime readiness (`reset -> migrate -> seed`) for that slot when `tester_fresh_db_per_task_required=true`; do not substitute read-only checks for required DB runtime validation. For unresolved blockers, Optimus must create/update a blocker issue in project `Agents`, assign it to `me`, and explicitly notify the user to review it. Apply feature-affinity-first planning: spread developers across distinct ready features where possible, keep developer-feature lanes sticky, and only assign multiple developers to one feature when other features are blocked/unavailable. Optimus must use codex-rate-snapshot skill periodically for all configured profiles, derive single-user vs multiple-users from profile identity (auth.json best effort), apply hard rate gates before dispatching new work, and apply soft concurrency throttle caps when soft-gated. Run in 5-minute cycles and skip sleep only while handling user steering. When `test_train_mode != off`, tester/flex-tester packets must always use shared hosted runtime (`runtime_strategy=external_url|shared_runtime`, `runtime_base_url` required, `tester_must_not_start_runtime=true`); only promote `test-next -> test` at wave boundaries after promotion gate approval.
Output: reports/optimus-prime runtime logs + worker prompt packets + synchronized Linear statuses/comments
```

## Filled Example
```text
Agent: optimus-prime
Goal: Finish first 20 ready tasks in MYO backlog with deterministic handoff loops and low token overhead.
Inputs: primary_mission: Complete first 20 ready MYO tasks from current sprint with full dev/test/review chain.
Inputs: task_source: Linear team Myownmint, project Ouroboros, status Ready, ordered by priority then age.
Inputs: repo_root: ../Ouroboros
Inputs: worktrees_parent: /Users/slobodan/Projects/.Ouroboros-workstations
Inputs: tracking_mode: automated-handoff
Inputs: agent_root_path: agents
Inputs: standards_source: agents/agent-making-agent/README.md
Inputs: worktree_policy_path: agents/_shared/WORKTREE_POLICY.md
Inputs: linear_workflow_path: agents/_shared/LINEAR_WORKFLOW.md
Inputs: sleep_minutes: 5
Inputs: max_initialized_workers: 10
Inputs: max_running_workers: 6
Inputs: worker_registry_path: reports/optimus-prime/WORKER_REGISTRY.json
Inputs: cycle_log_path: reports/optimus-prime/CYCLE_LOG.jsonl
Inputs: handoff_log_path: reports/optimus-prime/HANDOFF_LOG.jsonl
Inputs: linear_sync_log_path: reports/optimus-prime/LINEAR_SYNC_LOG.jsonl
Inputs: identity_checkpoint_path: reports/optimus-prime/IDENTITY_CHECKPOINT.md
Inputs: branch_lineage_path: reports/optimus-prime/BRANCH_LINEAGE.json
Inputs: feature_lane_registry_path: reports/optimus-prime/FEATURE_LANES.json
Inputs: packet_require_start_point: true
Inputs: feature_parallelism_policy: feature-affinity-first
Inputs: feature_grouping_fields: parent_issue,epic,label:feature
Inputs: allow_multi_developers_per_feature_when_blocked: true
Inputs: feature_lane_reassignment_policy: sticky-until-complete-or-blocked
Inputs: codex_profile_aliases: codex=default, codex-second=$HOME/.codex-second, codex-third=$HOME/.codex-third, codex-fourth=$HOME/.codex-fourth
Inputs: worker_codex_profile_policy: role:developer=codex-second; role:tester=codex; role:reviewer=codex
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
Inputs: status_profiles_scope: all-configured-plus-primary
Inputs: status_primary_profile_alias: codex
Inputs: orchestration_tooling_policy: deterministic-tool-first
Inputs: rate_status_log_path: reports/optimus-prime/RATE_STATUS_LOG.jsonl
Inputs: profile_rate_registry_path: reports/optimus-prime/PROFILE_RATE_REGISTRY.json
Inputs: rate_gate_action_mode: wind-down-or-wait
Inputs: status_account_parse_required: true
Inputs: developer_agent_path: agents/optimus-fullstack-developer/README.md
Inputs: tester_agent_path: agents/optimus-fullstack-tester/README.md
Inputs: reviewer_agent_path: agents/optimus-reviewer/README.md
Inputs: blocker_project_name: Agents
Inputs: blocker_assignee: me
Inputs: worker_sandbox_policy: role:developer=danger-full-access; role:tester=danger-full-access; role:reviewer=danger-full-access
Inputs: sandboxed_workers_require_explicit_user_request: true
Inputs: tester_fresh_db_per_task_required: true
Inputs: tester_health_registry_path: reports/optimus-prime/TESTER_WORKSTATION_HEALTH.json
Inputs: test_train_mode: final-stage
Inputs: test_branch: test
Inputs: test_next_branch: test-next
Inputs: shared_test_base_url: https://test.example.internal
Inputs: deploy_test_branch_cmd: ./scripts/deploy-test.sh
Inputs: test_train_state_path: reports/optimus-prime/TEST_TRAIN_STATE.json
Inputs: test_task_attempts_path: reports/optimus-prime/TEST_TASK_ATTEMPTS.json
Inputs: test_wave_log_path: reports/optimus-prime/TEST_WAVE_LOG.jsonl
Inputs: test_wave_summary_path: reports/optimus-prime/TEST_WAVE_SUMMARY.md
Inputs: worker_role_policy: developers up to 3, testers up to 2, reviewer up to 1
Inputs: developer_scaling: ready 1-3 => 1 dev, ready 4-9 => 2 devs, ready >=10 => 3 devs
Inputs: concurrency_policy: developers do not get next task before test+review pass; testers wait for reviewer outcome before next task
Constraints: Use workstation-preparation before every new worker thread and always pass explicit `--worktrees-parent` (use `Inputs: worktrees_parent` or derive hidden `<repo-parent>/.<repo-name>-workstations` from `repo_root`; do not rely on skill default path). Keep medium-thinking and high-thinking worker threads stable and reused. Build packet start anchors from branch lineage map so dependent unmerged tasks always get explicit starting point. Use feature-affinity-first scheduling so developers stay feature-specific when parallel feature work exists. Launch worker threads with thread-dispatch MCP minimization (default disable-all; enable only task-required MCPs, never linear/linear_sse for workers). Default worker sandbox is `danger-full-access` for all worker roles; only use sandboxed mode if user explicitly requests it. If `tracking_mode=linear`, require `linear_workflow_path` to exist/readable before dispatch; stop blocked if missing. Enforce deterministic tool-first orchestration: `orchestrator-status-snapshot` (status text/snapshot), `cycle-tick` (dispatch/sleep decision), `dispatch-worker-packet` (packet+dispatch+state updates), `linear-handoff-sync` (Linear status/comment sync), `blocker-escalate-to-agents` (workflow blocker escalation). Only use manual fallbacks if a required tool fails/unavailable, and log fallback reason and planned fix in cycle logs. Use codex-rate-snapshot skill on configured profiles every cycle, stop new dispatch when hard rate gates are hit (or sleep until reset if under 4h), and reduce active background workers to soft throttle cap when soft-gated. If assigned branch checkout is denied because branch is active elsewhere, worker uses `-dev` or `-test` fallback branch, commits there, and reports mapping; Optimus merges fallback back when intended branch is not actively used. Require tester slots to pass fresh DB readiness (`reset -> migrate -> seed`) before tester dispatch when enabled. For unresolved blockers, create/update issue in project `Agents`, assign to `me`, and explicitly tell user to review blocker. For shared train-mode runs, testers never start local app instances; they validate only against shared deployed `test` environment while developers continue merging completed work into `test-next`.
Output: Cycle-by-cycle orchestration until 20 tasks are fully done, with Optimus-managed Linear synchronization and complete local trace logs.
```
