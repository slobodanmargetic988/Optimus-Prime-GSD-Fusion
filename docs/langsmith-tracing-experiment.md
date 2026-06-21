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

## Useful metadata

Optional metadata knobs:

```bash
export LANGSTACK_ENVIRONMENT=dev
export LANGSTACK_AGENT_VERSION=langstack-experiment-v1
export LANGSTACK_TRACE_MODEL=deterministic-replay
```

This experiment starts with deterministic replay spans because the current pipeline materializes LLM-call-shaped trace rows rather than issuing live model requests in this path.
That gives us LangSmith visibility into the existing autonomous builder trace structure first, then leaves a clear place to wrap real model calls when those are introduced.
