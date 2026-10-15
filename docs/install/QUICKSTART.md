# OP Install Quickstart

This guide is for installing OP once, then using `opctl` to plan and build other
projects.

## Requirements

- macOS or Linux
- Python 3.11+
- `git`, `bash`, and `python3` on `PATH`
- Codex CLI available on `PATH` for strategy/planning/build LLM calls
- at least one authenticated Codex home, usually `~/.codex/auth.json`
- Network access to the public GitHub repository when installing from releases

Optional but useful:
- `gh` authenticated with `gh auth login`
- additional Codex homes such as `~/.codex-second` when using multiple accounts
- Playwright/browser tooling for projects that need UI verification
- LangSmith credentials only when intentionally enabling tracing experiments

## 1. Configure GitHub authentication for the release installer

Use one of:

```bash
gh auth login
```

or:

```bash
export GH_TOKEN="<token>"
# or
export GITHUB_TOKEN="<token>"
```

Token resolution order in installer/update:
1. `gh auth token`
2. `GH_TOKEN`
3. `GITHUB_TOKEN`

## 2. Install from a public prerelease

```bash
python3 scripts/install/op_install.py \
  --repo-owner slobodanmargetic988 \
  --repo-name Optimus-Prime-GSD-Fusion \
  --channel prerelease \
  --mode global \
  --json-pretty
```

Version-pinned install:

```bash
python3 scripts/install/op_install.py \
  --repo-owner slobodanmargetic988 \
  --repo-name Optimus-Prime-GSD-Fusion \
  --channel prerelease \
  --version 0.3.0-rc.2 \
  --mode global \
  --json-pretty
```

## 3. Validate the install

```bash
~/.local/bin/opctl doctor --json-pretty
~/.local/bin/opctl version --json-pretty
```

Add the global launcher directory to `PATH` if needed:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## 4. Use OP on another project

From the target project root:

```bash
cd /absolute/path/to/target-project
```

Recommended strategy-enabled setup:

```bash
mkdir -p strategy
cat > strategy/STRATEGY_MANIFEST.md <<'EOF'
# Strategy Manifest

## Mission
Build or update this project according to the operator request.

## Scope
- Inspect README, source code, tests, and existing planning docs.
- Identify constraints, sequencing risks, and reusable project context.
- Produce planner-facing strategy guidance before task planning starts.

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

Initialize planning:

```bash
opctl /op-initialize \
  --repo-root "$PWD" \
  --mission "Build or update this project" \
  --scope "Use the strategy manifest, inspect the project, create a strict plan, and stop before implementation." \
  --json-pretty
```

Then run the autonomous build loop:

```bash
opctl /op-build \
  --repo-root "$PWD" \
  --start-policy auto \
  --json-pretty
```

If you want to skip the strategy stage for a first smoke test:

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

Use `--override-old-plan` only when you intentionally want to replace existing
`reports/optimus-prime/planning` artifacts.

## 5. Local project install mode

Local mode installs launchers into the target repo under `.optimus-prime/bin`.

```bash
python3 scripts/install/op_install.py \
  --repo-owner slobodanmargetic988 \
  --repo-name Optimus-Prime-GSD-Fusion \
  --channel prerelease \
  --mode local \
  --repo-root /absolute/path/to/target-project \
  --json-pretty
```

Then use:

```bash
/absolute/path/to/target-project/.optimus-prime/bin/opctl doctor --json-pretty
```

## 6. Fallback local bundle mode

```bash
python3 -m scripts.release.build_lane_c_bundle \
  --repo-root /absolute/path/to/Optimus-Prime-GSD-Fusion \
  --out-dir /absolute/path/to/Optimus-Prime-GSD-Fusion/dist \
  --json-pretty

python3 scripts/install/op_install.py \
  --bundle-dir /absolute/path/to/Optimus-Prime-GSD-Fusion/dist/optimus-prime-0.3.0-rc.2 \
  --mode global \
  --json-pretty
```

## 7. Optional: create additional Codex profiles for multi-account OP usage

Create `~/.codex-second` from your default `.codex`:

```bash
python3 "$CODEX_HOME/skills/create-codex-profile/scripts/create_codex_profile.py" \
  --profile second \
  --json-pretty
```

The profile creator copies `auth.json` + `sessions/` and symlinks all other top-level `.codex` items so installed OP skills remain shared across profiles.

Beginner non-technical demo: [BEGINNER_DEMO.md](BEGINNER_DEMO.md).
More project-usage detail: [USING_OP_FOR_PROJECTS.md](USING_OP_FOR_PROJECTS.md).
