# Using OP for other projects

OP is a project-updater/build orchestrator. Install it once, then run `opctl`
against a target repository with `--repo-root`.

## Minimum requirements

- macOS or Linux
- Python 3.11+
- `git`, `bash`, and `python3`
- Codex CLI on `PATH`
- at least one authenticated Codex home, usually `~/.codex/auth.json`
- a target project that is a git repository, or permission for OP to bootstrap git

Optional:
- `gh` or `GH_TOKEN`/`GITHUB_TOKEN` for private release install/update
- multiple Codex homes for rate/profile routing
- Playwright/browser dependencies for UI projects
- LangSmith credentials only when intentionally enabling tracing experiments

## Target project setup

From the target project root:

```bash
cd /absolute/path/to/target-project
git status --short --branch
```

Create a strategy manifest when you want OP to reason about priorities before
planning:

```bash
mkdir -p strategy
cat > strategy/STRATEGY_MANIFEST.md <<'EOF'
# Strategy Manifest

## Mission
Build or update this project according to the operator request.

## Scope
- Inspect README, source code, tests, docs, and existing planning artifacts.
- Identify constraints, sequencing risks, and reusable context.
- Produce planner-facing guidance before implementation planning starts.

## Sources to inspect
- README.md
- docs/
- tests/
- package.json or pyproject.toml if present

## Operator preferences
- Prefer small, verifiable changes.
- Preserve existing user work.
- Surface blockers explicitly.
EOF
```

## Plan first

```bash
opctl /op-initialize \
  --repo-root "$PWD" \
  --mission "Build or update this project" \
  --scope "Use the strategy manifest, inspect the project, create a strict plan, and stop before implementation." \
  --json-pretty
```

Outputs:
- `strategy/current/strategy_packet.md` when strategy runs
- `strategy/current/STRATEGY_SUMMARY.md` when strategy runs
- `reports/optimus-prime/planning/*`

## Build

```bash
opctl /op-build \
  --repo-root "$PWD" \
  --start-policy auto \
  --json-pretty
```

Bounded first run:

```bash
opctl /op-build \
  --repo-root "$PWD" \
  --start-policy new \
  --max-build-cycles 1 \
  --json-pretty
```

Skip strategy for a first smoke test:

```bash
opctl /op-build \
  --repo-root "$PWD" \
  --mission "Build or update this project" \
  --scope "Create a strict plan and execute it with evidence." \
  --skip-strategy \
  --override-old-plan \
  --max-build-cycles 1 \
  --json-pretty
```

## Monitor and recover

```bash
opctl /op-status --repo-root "$PWD" --json-pretty
opctl /op-health --repo-root "$PWD" --json-pretty
opctl /op-resume --repo-root "$PWD" --json-pretty
```

Use `--override-old-plan` only when replacing existing planning artifacts is
intentional.

Create `terminate_run.json` in the target project root to stop an active OP
Simple loop on the next cycle boundary.
