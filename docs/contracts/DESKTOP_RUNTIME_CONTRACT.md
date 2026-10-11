# Desktop Runtime Contract

The desktop application invokes the existing Python engine. `scripts/op/opctl.py --input-json -` accepts one JSON request on standard input. Credentials belong only in the child environment or provider CLI configuration, not in request JSON, command arguments, project files, or logs.

## Planning and build settings

- `command`: `/op-initialize` plans only; `/op-build` plans when needed and runs; `/op-resume` continues existing OP Simple state.
- `repo_root`: an existing absolute project directory.
- `mission`, `scope`: inline strings, or use `mission_file` / `scope_file`.
- `max_plan_tasks`: optional integer 1–400. It caps generated `PLAN_PACKETS.tasks`; it is not a target, price, model-token budget, or worker concurrency setting. An explicit value supersedes older minimum-task-count instructions for that run. The planner must preserve scope and verification. Oversized plans fail validation and enter the bounded planner repair loop; they are never truncated.
- `max_parallel_workers`: existing worker concurrency setting, default 8 when omitted.
- `worktrees_parent`: explicit absolute worker-worktree directory. Desktop callers must supply a portable, project-specific path.
- `override_old_plan`: required when intentionally replacing an existing plan. The task cap alone does not authorize overwriting a plan.
- `start_policy`: `/op-build` only, `auto`, `new`, or `resume`. Resume does not accept fresh mission/scope inputs.
- `skip_strategy`: skip optional strategy generation. Strategy, bootstrap and planning use the selected executor when run through the OP command surface.

The cap is persisted in planning `STATE.json` and rechecked before build/simple-build/resume dispatch. The setting governs the planned task bundle; it is not a total LLM-call or execution-time limit. CLI callers that omit it retain existing planning policy. Schema, task dependency, coverage and quality checks remain active for small plans, including a one-task plan.

## Executor configuration

- `executor_provider`: `codex`, `openrouter`, `blackbox`, or `claude`.
- `executor_model`: optional provider-appropriate model identifier. It also applies to planning/bootstrap calls. Omission leaves the selected CLI's model default unless that provider has an existing runtime default.
- Codex subscription: uses the user's authenticated Codex CLI. `selected_aliases` restricts configured subscription homes; `codex` means the default `.codex` home.
- Codex/OpenRouter API configuration: set `profile` (also accepted as `codex_profile`) to a valid Codex config profile and `CODEX_HOME` to its directory. This bypasses subscription-home discovery. The profile must select the actual model provider and credential environment variable; choosing `executor_provider=openrouter` alone does not configure a provider endpoint.
- Claude: invokes the installed Claude CLI and uses its existing login or inherited `ANTHROPIC_API_KEY`. It does not require a Codex account or route through a Codex profile.
- Blackbox: uses the existing Blackbox CLI and lane settings. The desktop must not advertise untested provider configuration as working merely because a binary exists.

Planning uses bounded repair attempts. Provider authentication, quota and permission errors remain real errors; no silent cross-provider fallback is allowed. Existing CLI authentication is not an OS isolation boundary: the user must trust projects they run locally.

## Progress and stop

`output_mode=json+text` enables readable progress with the final structured response. OP Simple state and history are under `.op-simple/current` and `.op-simple/history`; planning output is under `reports/optimus-prime/planning`.

`terminate_run.json` requests a cooperative build stop at a cycle boundary. It is not an immediate process kill. A desktop force-stop must terminate only child processes it owns, including worker descendants, and retain state for recovery. Resume requires the stored initialization state and corresponding Git run-base branch. Never treat absent or invalid state as permission to silently start a replacement run.
