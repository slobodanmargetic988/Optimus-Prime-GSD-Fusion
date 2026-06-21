# LangSmith tracing experiment

This branch adds an optional LangSmith tracing bridge for the strategy LLM pipeline CLI.
It is disabled by default and does not change deterministic payloads, JSONL trace rows, or validation contracts.

## Install

```bash
caffeinate -dimsu python3 -m pip install langsmith
```

## Enable

Set one of these switches before running `scripts/strategy_llm_pipeline.py`:

```bash
export LANGSTACK_TRACING=true
export LANGSMITH_API_KEY="..."
export LANGSMITH_PROJECT="optimus-prime-gsd-fusion"
```

EU LangSmith workspaces must also set the EU API endpoint:

```bash
export LANGSMITH_ENDPOINT="https://eu.api.smith.langchain.com"
```

You can also force tracing for one CLI run:

```bash
python3 scripts/strategy_llm_pipeline.py --input-json examples/fixtures/multi-call-strategy-pipeline-planner.json --json-pretty --langsmith-tracing
```

## Trace shape

The bridge emits nested `@traceable` runs:

- `strategy_pipeline.run_pipeline`: top-level request and result summary.
- `strategy_pipeline.loop_iteration`: one run per existing `llm_call_trace_rows` item.
- `strategy_pipeline.invoke_llm_placeholder`: LLM-shaped span with prompt objective, model label, and output summary.
- `strategy_pipeline.tool_artifact_refs`: tool-shaped span for input refs, output refs, and artifact refs.

By default, trace inputs are compact summaries to reduce accidental source-code or secret exposure.
Set `LANGSTACK_TRACE_INCLUDE_PAYLOADS=true` only when you intentionally want full redacted payload snapshots in LangSmith.
Keys matching token, secret, password, credential, authorization, or API key patterns are redacted before tracing.

Failed OP events are intentionally raised inside the `@traceable` wrapper and then caught by OP, so LangSmith marks the trace run as `error` without changing OP command behavior.
Failure traces include compact error summaries and, when available, a bounded redacted excerpt from `llm_stderr_ref` so root causes such as Codex config parse failures are visible in LangSmith.

## Useful metadata

Optional metadata knobs:

```bash
export LANGSTACK_ENVIRONMENT=dev
export LANGSTACK_AGENT_VERSION=langstack-experiment-v1
export LANGSTACK_TRACE_MODEL=deterministic-replay
```

This experiment starts with deterministic replay spans because the current pipeline materializes LLM-call-shaped trace rows rather than issuing live model requests in this path.
That gives us LangSmith visibility into the existing autonomous builder trace structure first, then leaves a clear place to wrap real model calls when those are introduced.

## OP build tracing

The OP command surface also emits optional LangSmith spans when tracing is enabled:

- `op.command.start/result/error`: top-level OP command lifecycle.
- `op.plan.planner_attempt.start/result/error`: Codex planner attempts during `/op-plan` and `/op-initialize`.
- `op.build.controller_cycle.*`: legacy controller-cycle orchestration boundaries.
- `op.build.dispatch.*`: legacy worker dispatch boundaries.
- `op.simple_build.start/result`: OP Simple runtime lifecycle used by `/op-build`.
- `op.simple_build.cycle.start/summary`: each OP Simple cycle.
- `op.simple_build.manager.start/result`: manager LLM calls such as BOSS, merge-manager, and wrapup-manager.
- `op.simple_build.worker_dispatch.start/result`: worker packet dispatch launches.

To run the first calculator-app experiment with strategy skipped, planning enabled, and Codex as the executor:

```bash
export LANGSTACK_TRACING=true
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY="..."
export LANGSMITH_PROJECT="optimus-prime-gsd-fusion-op-build"
# For EU LangSmith accounts:
# export LANGSMITH_ENDPOINT="https://eu.api.smith.langchain.com"
export LANGSTACK_ENVIRONMENT=dev
export LANGSTACK_AGENT_VERSION=langstack-op-build-experiment-v1

caffeinate -dimsu python3 scripts/op/opctl.py \
  --command /op-build \
  --repo-root /Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion \
  --skip-strategy \
  --start-policy new \
  --override-old-plan \
  --executor-provider codex \
  --mission "Build a small calculator app for the first LangSmith traced OP build run." \
  --scope "Create a simple calculator app with digit input, add/subtract/multiply/divide, clear, equals, keyboard-friendly interaction if practical, and a focused verification command." \
  --max-build-cycles 3 \
  --json-pretty
```

Remove `--max-build-cycles 3` when you want the autonomous loop to continue until its normal terminal condition.
