# AGENTS.md

## Scope Authoring Rule (High Priority)
When writing project `scope.md` files for OP/BP planning, include this exact mandatory planning gate text:

`Before build starts, planner must output at least 400 tasks.`

`No build execution is allowed below 400 planned tasks.`

## Placement Guidance
- Put the two lines under a dedicated section header:
  - `## Mandatory planning gate`
- Keep the wording unchanged to preserve consistency across projects.

## Prompt Change Policy (High Priority)
- Do not edit prompt template files anymore.
- Any prompt tweak requests must be handed back to the user for manual insertion.
- Provide prompt tweak suggestions in narrative form (not direct template edits).

## Explicit Desktop Planning Limits
- The operator can explicitly choose `--max-plan-tasks N` / JSON `max_plan_tasks` from 1 through 400. For that run, this newer operator choice overrides the fixed 400-task minimum above and any older minimum in scope documents.
- This setting is a maximum, not a required task count. Keep requested scope and quality checks; reject or replan an oversized plan rather than truncating it or silently omitting work.
- If the setting is omitted, preserve existing CLI planning policy. Plans created with a cap persist it in planning `STATE.json`; build and resume recheck that cap before dispatch.
- Implement the override through runtime configuration and deterministic validation. Prompt template files remain unchanged.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **Optimus-Prime-GSD-Fusion** (25139 symbols, 30023 relationships, 232 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/Optimus-Prime-GSD-Fusion/context` | Codebase overview, check index freshness |
| `gitnexus://repo/Optimus-Prime-GSD-Fusion/clusters` | All functional areas |
| `gitnexus://repo/Optimus-Prime-GSD-Fusion/processes` | All execution flows |
| `gitnexus://repo/Optimus-Prime-GSD-Fusion/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->

## OP-Build Alignment (Mandatory)
- Earth root policy lives in `/Users/slobodan/projects/Earth/AGENTS.md`.
- Canonical Earth `op-build` guidance lives in `/Users/slobodan/projects/Earth/OP_BUILD_ECOSYSTEM_GUIDE.md`.
- This repo owns Earth-wide `op-build` runtime behavior; changes here affect how the rest of the ecosystem builds.
- Repo-local experiments here may extend `op-build`, but they should preserve clear contracts for every downstream repo that depends on it.
- If you make a commit during an `op-build` task, push it immediately after the commit.

## Repo-Specific OP-Build Role Guidance
- `planner`: define runtime changes in terms of operator-visible build outcomes, resume behavior, executor routing, and downstream compatibility.
- `architect`: protect the contract between orchestration state, repo-local overrides, executor selection, and recovery semantics.
- `implementer`: prefer auditable runtime improvements over prompt-only magic, hidden branching, or one-off repo hacks.
- `tester`: prove resume safety, bounded-cycle behavior, executor selection, and evidence clarity with runnable checks.
- `reviewer`: treat regressions in orchestration correctness, packet generation, merge behavior, or downstream repo assumptions as high severity.
- `documenter`: update this file and supporting OP docs whenever runtime contracts, flags, or worker expectations change.
## Agent Escalation and Envelopes (Mandatory)
- While working in this repo, agents should think carefully about the work they are doing and actively surface any problems they encounter.
- If an agent hits a blocker, ambiguity, or environment issue, report it to `/Users/slobodan/projects/Earth/ground-control-hub/` as Ground.
- Ground should also be able to ingest lightweight agent envelopes with suggestions for tools, workflows, or repo changes that would make future work easier.
