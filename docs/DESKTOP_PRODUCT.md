# Optimus Desktop product contract

Optimus Desktop runs the orchestration engine on the user's computer. The
desktop interface manages projects, run settings and progress; provider CLIs
perform the AI work and the existing Optimus runtime manages planning, worker
worktrees, validation and continuation artifacts. Closing the interface is not
a move to hosted execution: the local machine remains the execution host.

## Free and open source

Optimus and its updates are free. Project code is licensed under Apache 2.0;
third-party components retain their own licenses in [the notices](../THIRD_PARTY_NOTICES.md).
The source repository is public. The CLI is confirmed usable; the desktop app
remains experimental and needs real-project testing and community bug fixes.

The desktop **About** page links to the
[GitHub repository](https://github.com/slobodanmargetic988/Optimus-Prime-GSD-Fusion)
and invites voluntary [GitHub sponsorship](https://github.com/sponsors/slobodanmargetic988).
Sponsorship is optional and does not enable features. Contributions can also take
the form of testing, documentation, issue reports and pull requests.

Users bring their own AI provider account. Provider subscriptions, API usage and
project infrastructure are separate from the free Optimus application. Release
readiness still requires platform signing, compatibility checks and live testing.

## Local provider execution

| Provider | Execution | Credentials |
| --- | --- | --- |
| Codex | Existing Codex CLI execution paths | A supported local Codex login/profile, or an explicitly configured API path |
| Claude | Claude Code CLI for strategy, planner/bootstrap calls and OP Simple managers/workers | Existing Claude CLI login or `ANTHROPIC_API_KEY` inherited by the child process |
| OpenRouter | Existing Codex-compatible provider configuration | User's provider key and compatible configuration |
| Blackbox | Existing Blackbox CLI lane | User's selected authentication lane |

The runtime's provider adapters do not create provider accounts, read and copy
consumer token files, or cover AI usage charges. The desktop
must only enable a provider when its required CLI and configuration are ready.
An installed CLI is not proof of a valid login, sufficient quota or model access.

Claude uses `--print --output-format json`. Prompts travel through standard
input rather than shell interpolation. The adapter can select a model and effort,
resume an explicitly supplied Claude session, and launch background workers.
Manager execution uses fresh provider conversations and resumes the build from
Optimus's saved artifacts; it does not silently reuse a Codex conversation ID.
Malformed results, CLI errors, timeouts and denied required permissions are
recorded as failures. Worker launch records mean the process started; successful
completion still requires the existing evidence and validation checks.

Claude's noninteractive API-key environment takes precedence over its subscription
login. Subscription mode must not inherit an unintended `ANTHROPIC_API_KEY`.
The same billing-selection discipline applies to the other providers.

Optional strategy generation through the OP command surface uses the selected
provider and credentials, just like planning and bootstrap. The desktop skips
strategy by default; users may enable it with a strategy manifest. The standalone
strategy script retains its legacy Codex default. Provider routing has fixture
coverage; live provider compatibility remains a separate release check.

## Execution and evidence boundaries

Only run trusted projects. These workers intentionally edit files and execute
build/test commands using the user's local operating-system permissions.
Claude uses `dontAsk` with grants for reading, editing, searching and Bash;
existing explicit Claude deny rules remain effective. This is not cloud tenant
isolation or an operating-system sandbox.

Each run should retain its project-local planning and `.op-simple` artifacts so
the user can inspect results and continue after a stop. Worktree location,
worker count, task limit and cycle limit are explicit run settings. A task ceiling
must be enforced by plan validation as well as displayed in the interface; no
oversized plan should silently enter the build loop. Stopping a desktop-owned run
must stop all of its tagged child workers.

The Claude quota snapshot identifies `claude-local` and labels quotas as
`provider_managed_unknown`. It contains no invented remaining-token numbers and
does not query Codex's account registry. The provider CLI is responsible for
reporting authentication, model availability and usage-limit failures.

## Runtime integration settings

- `OP_CLAUDE_BIN`: optional executable path for the installed Claude CLI.
- `ANTHROPIC_API_KEY`: optional API-billing credential; never put it in argv, run
  artifacts or product logs.
- `OP_THREAD_DISPATCH_SCRIPT`: explicit bundled Codex dispatcher path. An invalid
  explicit path fails resolution rather than selecting an unrelated user script.
- `OP_WORKSTATION_PREPARE_SCRIPT`: explicit bundled workstation-preparation path,
  with the same fail-closed resolution.
- `OP_EXECUTOR_LOG_ROOT`: configurable executor-log directory. The default is
  `~/.optimus/logs/op-executors`.
- The default worktree parent is `~/.optimus/worktrees`; a desktop run can choose
  a project-specific directory instead.

## Validation scope

The Claude adapter and routing checks use local fixture executables. They verify
actual subprocess arguments, stdin, working directories, result parsing, errors,
timeouts and worker registration without sending prompts to a paid model.
Live provider login, model availability, quota behavior and end-to-end autonomous
project quality require separate testing in the user's chosen provider
environment. Release notes should distinguish that testing from fixture checks.

Official provider references: [Claude CLI](https://code.claude.com/docs/en/cli-reference),
[programmatic execution](https://code.claude.com/docs/en/headless), and
[authentication environment variables](https://code.claude.com/docs/en/env-vars).
