# GitNexus Usage Findings

Date: 2026-03-18

Sample analyzed:
- Session log: `/Users/slobodan/.codex/sessions/2026/03/17/rollout-2026-03-17T15-01-23-019cfc19-ede3-7d50-9684-2832b2557ab6.jsonl`
- Merge/recovery block: 2026-03-17 19:20 to 22:45 UTC
- Review block: 2026-03-18 04:38 to 04:45 UTC

## Executive summary

GitNexus was useful in this sample as a secondary structural tool, but it was not dependable enough to act as the primary navigator for the work. The strongest workflows were `detect_changes` and `cypher`. The weakest workflows were `query`, `context`, and some `impact` calls exactly when the investigation needed fast, precise answers on the live repo snapshot.

The most important failure mode was not bad ranking. It was transport instability against `http://127.0.0.1:4747/api/mcp`, plus some repo-target ambiguity and symbol/file targeting friction on large strategy files.

## Visible usage counts

Visible GitNexus calls across the sampled turns: `56`

Visible outcomes:

| Tool | Calls | Success | Fail |
| --- | ---: | ---: | ---: |
| `list_repos` | 9 | 7 | 2 |
| `detect_changes` | 4 | 4 | 0 |
| `context` | 6 | 3 | 3 |
| `impact` | 28 | 19 | 9 |
| `query` | 4 | 2 | 2 |
| `cypher` | 5 | 5 | 0 |
| Total | 56 | 40 | 16 |

Notes:
- The long merge/recovery block was compacted in the session log several times, so these are visible-call counts, not guaranteed full counts.
- The fallback analysis below uses semantic investigation clusters, not raw command totals.

## Overall assessment

What GitNexus did well:
- `detect_changes` was the most dependable tool in this sample.
- `cypher` was the most reliable GitNexus-native fallback when higher-level tools were not enough.
- File-level scope checks and coarse graph confirmation were useful when the server was healthy.

What GitNexus did poorly:
- `query` was not reliable enough to kick off large runtime-flow reviews.
- `context` was too fragile on common symbol names and during transport instability.
- `impact` often helped, but too many calls failed or under-pinned important work on large strategy monoliths.
- It struggled to answer "what is the live implementation surface I need right now?" when the repo had branch-era recovery work, wrappers, facades, and multiple large files with overlapping symbols.

Bottom line:
- Good sidecar for graph-aware scope checks.
- Weak primary navigator for merge archaeology and runtime truth-finding in this sample.

## Timestamped fallback episodes

These are the five clear moments where GitNexus either failed outright or failed to pinpoint the needed information, and the work had to continue through direct shell search and source inspection.

| Episode | Time (UTC) | What GitNexus was trying to answer | What failed | What the manual fallback did |
| --- | --- | --- | --- | --- |
| E1 | 2026-03-17 20:28:24 to 20:29:09 | Symbol context and blast radius in `scripts/strategy_llm_pipeline.py` around `_detect_requirement`, `_validate_output`, `main`, and the file itself | `impact` timed out and transport-failed; `context` transport-failed; one `cypher` attempt also hit binder friction | Switched to direct file and branch archaeology on the big pipeline file and later used `rg`, `sed`, and `git show` to recover missing REQ-038/040/041/044 surfaces |
| E2 | 2026-03-17 20:41:11 to 20:54:28 | Whether `strategy_context_sweep.py` and later `strategy_artifacts_handoff.py` still carried REQ-017/018 and REQ-048/049 live behavior | `impact` transport-failed on `strategy_context_sweep.py`; later GitNexus under-supported the handoff recovery search | Fell back to task-plan inspection, `rg` on exported function names, test references, fixture references, and `git show` against task branches to recover the right implementations |
| E3 | 2026-03-17 21:14:01 to 21:17:30 | Repo/index availability and live REQ-039/047 symbol coverage in `strategy_llm_pipeline.py` | `list_repos` transport-failed; later `impact` could not find REQ-039/047 builder targets and file-level impact under-reported the surface | Used `PYTHONPATH` test runs, `rg` for REQ-039/047 functions and constants, and branch snapshots via `git show` to prove the live module was missing process/export surfaces |
| E4 | 2026-03-17 21:26:17 to 21:35:54 | Blast radius and live-vs-stale surface for `strategy_artifacts_handoff.py`, `strategy_context_sweep.py`, `strategy_llm_pipeline.py`, REQ-020, REQ-041, and REQ-045 | `impact` could not find `strategy_artifacts_handoff.py`, then timed out or transport-failed on other targets; duplicate repo names were also causing ambiguity pressure | Switched to `sed`, `rg`, `git grep`, `git show`, targeted pytest, and CLI help to determine that REQ-041/045 had richer implementations hidden by flattening wrappers and REQ-020 was genuinely stale |
| E5 | 2026-03-18 04:39:43 to 04:43:00 | High-level runtime flow for "strategy pre-planner runtime pipeline op-initialize op-plan strategy artifacts" during the mission-vs-code review | `query` transport-failed immediately | The rest of the review was done through `16` `rg` discovery searches and `55` direct file reads across `scripts/op/op_core.py`, strategy files, prompts, validators, and mission/scope docs |

## Episode details

### E1: Large strategy pipeline symbol recovery

Anchor timestamps:
- `2026-03-17T20:28:24.792Z` to `2026-03-17T20:28:39.109Z`

GitNexus attempts:
- `impact` failures on shared strategy pipeline targets
- `context` on `_detect_requirement`, `_validate_output`, and `main` in `scripts/strategy_llm_pipeline.py`
- `cypher` follow-up to probe the indexed file graph

What it was trying to answer:
- Which live symbols still existed in the current `strategy_llm_pipeline.py`
- What depended on that surface before edits
- Whether the missing task families were still represented in the main file

What happened:
- `impact` timed out or transport-failed.
- `context` transport-failed on all three symbol lookups.
- `cypher` partly worked, but one query hit binder friction instead of directly surfacing the needed symbol map.

Why this mattered:
- This was the first clear signal that GitNexus was not dependable enough for symbol-level surgery inside the largest strategy monolith.

Fallback pattern:
- Refresh CLI-side health with `gitnexus list` and `gitnexus status`
- Then abandon MCP-level navigation and use `rg`, `sed`, and `git show` to inspect the live file and task-branch snapshots

### E2: REQ-017/018 and REQ-048/049 recovery

Anchor timestamps:
- `2026-03-17T20:41:11.237Z` to `2026-03-17T20:54:28.324Z`

GitNexus attempts:
- `impact` on `strategy_context_sweep.py`
- Later recovery work around REQ-048/049 in `strategy_artifacts_handoff.py`

What it was trying to answer:
- Whether `strategy_context_sweep.py` still exposed the REQ-017/018 live processing entrypoints
- Whether `strategy_artifacts_handoff.py` still carried the correct REQ-048/049 live generator surfaces or only partial facades

What happened:
- `impact` transport-failed on `strategy_context_sweep.py`
- The graph did not give a clean "missing vs superseded" answer for the handoff recovery problem

Why this mattered:
- This was the strongest case where GitNexus failed the exact task that mattered: deciding whether a task family was really missing or just superseded.

Fallback pattern:
- Read the plan packets to find the exact task family
- `rg` for `extract_strategic_debt_signals`, `detect_overlap_and_conflicts`, `REQ_048`, `REQ_049`, `process_req_048`, and `process_req_049`
- Read tests, contracts, fixtures, and branch snapshots with `sed` and `git show`

### E3: REQ-039/047 live surface verification

Anchor timestamps:
- `2026-03-17T21:14:01.738Z` to `2026-03-17T21:17:30.577Z`

GitNexus attempts:
- `list_repos`
- `impact` on `build_req_039_recommendation_rationale_quality_scoring`
- `impact` on `build_req_047_llm_call_trace_and_decision_ledger`
- File-level `impact` on `strategy_llm_pipeline.py`

What it was trying to answer:
- Whether GitNexus could still see the live REQ-039/047 implementations and their callers
- Whether the missing-surface suspicion was real

What happened:
- `list_repos` transport-failed
- Symbol-targeted `impact` calls returned "target not found"
- File-level `impact` under-reported the file as low-risk and unconnected, which was not enough to support the merge decision

Why this mattered:
- This is a good example of "not a hard error, but still not enough." Even successful output did not pinpoint the important truth.

Fallback pattern:
- Re-run relevant tests with correct `PYTHONPATH`
- `rg` for REQ-039/047 functions, constants, trace helpers, and exported builders
- Compare with branch snapshots using `git show`

### E4: Wrapper-vs-rich-implementation conflict

Anchor timestamps:
- `2026-03-17T21:26:17.984Z` to `2026-03-17T21:35:54.625Z`

GitNexus attempts:
- `impact` on `strategy_artifacts_handoff.py`
- `impact` on `strategy_context_sweep.py`
- `impact` on `strategy_llm_pipeline.py`

What it was trying to answer:
- Which strategy surfaces were live, stale, or flattened by compatibility wrappers
- Whether REQ-020, REQ-041, and REQ-045 were really missing or only partially overridden

What happened:
- One `impact` call said `strategy_artifacts_handoff.py` target not found
- Other `impact` calls timed out or transport-failed
- Duplicate repo names increased ambiguity pressure at exactly the wrong time

Why this mattered:
- The real merge insight came from outside GitNexus: REQ-041 and REQ-045 still had richer implementations, but wrapper layers were flattening them back into older shapes.

Fallback pattern:
- Use `git grep` across task branches
- Read live files and branch snapshots with `sed` and `git show`
- Run targeted tests
- Use CLI help and repo inspection to reason around the repo-name ambiguity

### E5: Mission-vs-code runtime review

Anchor timestamps:
- `2026-03-18T04:39:43.613Z` to `2026-03-18T04:43:00.129Z`

GitNexus attempts:
- `query` for `strategy pre-planner runtime pipeline op-initialize op-plan strategy artifacts`

What it was trying to answer:
- The main execution flow for the strategy tool and whether it truly steered planning or mostly emitted artifacts

What happened:
- `query` transport-failed immediately

Why this mattered:
- This was the cleanest proof that GitNexus could not be relied on for top-down runtime review in this session.

Fallback pattern:
- `16` discovery-style `rg` searches
- `55` direct file reads
- Review completed through `scripts/op/op_core.py`, strategy entrypoints, validators, prompts, and mission/scope docs without GitNexus

## How often GitNexus forced real fallback work

Strict count of clear fallback investigations caused by GitNexus failure or non-pinpointing behavior: `5`

Important distinction:
- This is not the same as saying every later `rg` or `sed` read was a fallback.
- Many shell reads are normal coding work.
- The count above only includes episodes where GitNexus either broke or failed to answer the key question well enough, and the investigation had to shift modes.

## What this sample says about GitNexus today

Most useful on:
- scope verification
- changed-surface detection
- graph-aware confirmation once the operator already knows roughly where to look

Least useful on:
- branch-era recovery and merge archaeology
- giant multi-surface files with overlapping old/new behavior
- "is this missing or truly superseded?" judgments
- top-down runtime review when the MCP transport is unstable

## Improvement ideas

### Reliability

- Add stronger MCP health checking before the tool call starts.
- Add transparent retry/backoff for transient transport errors.
- Expose a fast "server unhealthy" state instead of waiting for long timeouts.
- If CLI is healthy and MCP transport is down, degrade to CLI-backed behavior instead of full failure where possible.

### Better fallback behavior

- When `query`, `context`, or `impact` fails, return a structured degraded fallback using indexed file matches or text-backed hints instead of only an error.
- Provide a hybrid graph-plus-text mode so the tool can still guide the operator even when symbol coverage is incomplete.
- Offer "closest matching symbols/files" automatically when a target is not found.

### Better giant-file support

- Add a first-class file exploration mode for monolithic files.
- Return top symbols, exports, and internal high-centrality helpers for a file in one call.
- Support deterministic symbol listings for common names like `main`, `run`, and `validate_*`.

### Better ambiguity handling

- Improve duplicate repo-name disambiguation when mirror repos and live repos share a name.
- Let the operator target a repo by absolute path, not just repo label.
- Let `impact` and `context` take stronger disambiguators such as file path plus line or exact symbol location.

### Better merge-archaeology support

- Add a workflow that can answer "is this task family present, superseded, or missing?"
- Add branch- or commit-aware graph queries so recovery work can compare live code against task branch snapshots directly.
- Add a requirement-family coverage query that correlates code, tests, contracts, fixtures, and samples.

### Better operator feedback

- Include repo freshness, repo identity, and branch snapshot details inline with every response.
- Distinguish clearly between:
  - transport/server failure
  - symbol not indexed
  - symbol not found
  - repo ambiguity
  - empty result because no callers/dependents exist

## Final judgment from this sample

If the question is "can GitNexus help?", the answer is yes.

If the question is "can GitNexus be trusted as the primary source of truth for a long merge/recovery investigation on this repo snapshot?", the answer from this sample is no.

The critical merge and review decisions in this run ultimately came from:
- `rg`
- `sed`
- `git show`
- targeted test runs
- direct source comparison

GitNexus still added value, but mostly as a sidecar structural tool rather than the lead navigator.

## CGC comparison

I also replayed the same general investigation needs against `cgc` (CodeGraphContext) from the current repo working directory on 2026-03-18.

### What CGC looked like before refresh

Useful immediately:
- `cgc list` worked and showed the current repo plus mirror repos.
- Exact-name lookup worked for simple live symbols such as `_detect_requirement`, `_validate_output`, and `command_plan`.
- Caller lookup worked for simple function analysis such as:
  - `_validate_output` called by `main`
  - `_detect_requirement` called by `run` and `main`
  - `command_plan` called by `command_initialize` and `_apply_strategy_action`

Not useful immediately:
- It missed many of the strategy surfaces that mattered most in the GitNexus sample:
  - `build_req_041_recommendation_dependency_effect_modeling`
  - `build_req_045_alternative_strategic_scenario_generator`
  - `strategy_artifacts_handoff.py`
  - `op_initialize_pre_plan_strategy_hook`
  - `recommendation_to_planner_mapping_artifact`
  - `blocker_handling_policy_artifact`
- Content search for strategic runtime/planner hooks returned nothing before refresh.

### Important CGC-specific failure mode

When I tried parallel CLI use, CGC repeatedly failed with a KuzuDB file-lock error:

- `Database Connection Error: IO exception: Could not set lock on file`
- DB path: `/Users/slobodan/.codegraphcontext/kuzudb`

Practical impact:
- CGC did not tolerate the same kind of parallel probing that GitNexus tolerated.
- For this kind of fast interactive investigation, that is a meaningful ergonomics and latency problem.

### Refresh behavior

When I ran `cgc index .`, CGC reported:

- `Repository '.' exists but has no files (likely interrupted). Re-indexing...`

That explains many of the pre-refresh misses.

However, the refresh itself was expensive:
- It ran CPU-hot for more than 25 minutes on this repo.
- It produced almost no progress output after startup.
- I stopped it manually rather than leave it running indefinitely.

### What improved after partial refresh

After the interrupted-but-substantial refresh, CGC got much better:

- It found `build_req_041_recommendation_dependency_effect_modeling`.
- It found `build_req_045_alternative_strategic_scenario_generator`.
- It found `strategy_artifacts_handoff.py` as a file in both the root scripts path and the `op-tools/strategy` subtree.
- Content search found `op_initialize_pre_plan_strategy_hook`.
- Content search found `recommendation_to_planner_mapping_artifact`.
- Content search found `blocker_handling_policy_artifact`.

This means the earlier misses were not purely conceptual limitations. A large part of the problem was broken or incomplete index state.

### Where CGC was better

- Exact-name lookup was straightforward and readable once the index had the data.
- Caller lookup for simple functions was fast and clean.
- Content search, after refresh, was useful for locating planner-hook and artifact-surface references across code and tests.

### Where CGC was worse

- Broken index state was more misleading at first glance.
- Recovery from that state was much heavier than GitNexus recovery in this environment.
- Parallel queries were effectively a non-starter because of the KuzuDB lock behavior.
- I did not find direct equivalents for:
  - `detect_changes`
  - GitNexus-style high-level process/execution-flow query
  - GitNexus-style structured impact/risk summaries

### Practical verdict

For this repo and this sample:

- If the question is exact symbol lookup or simple caller analysis, CGC can be good once its index is healthy.
- If the question is "help me do a long, parallel, merge-archaeology investigation right now," CGC was less practical than GitNexus.
- The biggest CGC problem was not answer quality after refresh. It was the cost and fragility of getting to a healthy refresh state in the first place.
