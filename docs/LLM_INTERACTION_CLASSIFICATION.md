# LLM Interaction Classification

This document classifies LLM-interacting runtime steps using the required enums:
- `reasoning_effort`
- `tooling_effort`

## Classification Map

| Runtime Step | Code Reference | reasoning_effort | tooling_effort | Notes |
|---|---|---|---|---|
| Selected-provider planning, bootstrap, and strategy dispatch | `scripts/op/op_core.py::_run_planning_executor` | `high_effort` | `high_tooling` | Routes to the operator-selected local CLI; never silently substitutes a provider. |
| Plan generation and repair loop | `scripts/op/op_core.py::_run_llm_plan_generation` | `high_effort` | `high_tooling` | Enforces optional plan task cap and the existing schema/quality gates. |
| Codex planning CLI execution | `scripts/op/planner/llm_planner.py::run_codex_exec` | `high_effort` | `high_tooling` | Honors explicit Codex configuration profile and model, including API configurations. |
| Strategy generation | `scripts/op/strategy_runner.py::run_strategy` | `high_effort` | `high_tooling` | Optional injected executor follows the selected provider; default standalone behavior remains Codex. |
| Claude CLI execution and worker launch | `scripts/op/claude_executor.py::run_claude_exec`, `launch_claude_background` | `high_effort` | `high_tooling` | Uses Claude CLI login or caller environment credentials; local repository tools are explicitly permitted. |
| OP Simple manager execution via Codex/OpenRouter backend | `scripts/op/op_simple_build.py::_codex_exec_prompt` | `high_effort` | `medium_tooling` | Manager prompt execution with artifact validation loops. |
| OP Simple manager execution via Blackbox backend | `scripts/op/op_simple_build.py::_blackbox_exec_prompt` | `medium_effort` | `low_tooling` | Non-interactive single-shot prompt execution. |
| OP Simple worker dispatch orchestrator | `scripts/op/op_simple_build.py::_dispatch_packets` | `high_effort` | `medium_tooling` | Dispatches worker prompts and tracks runtime launch state. |
| OP Simple worker dispatch via Blackbox lane | `scripts/op/op_simple_build.py::_launch_blackbox_dispatch` | `medium_effort` | `low_tooling` | Background non-interactive blackbox launch with lane-specific auth mode. |
| OP Build packet dispatch bridge | `scripts/op/op_core.py::_dispatch_task_packet` | `high_effort` | `medium_tooling` | Produces dispatch payloads and invokes worker packet tool. |
| Worker packet dispatch via Codex/OpenRouter backend | `skills/dispatch-worker-packet/scripts/dispatch_worker_packet.py::ThreadDispatchRunner.dispatch` | `high_effort` | `medium_tooling` | Thread-dispatch based launch with resume fallback handling. |
| Worker packet dispatch via Blackbox backend | `skills/dispatch-worker-packet/scripts/dispatch_worker_packet.py::BlackboxDispatchRunner.dispatch` | `medium_effort` | `low_tooling` | Background non-interactive blackbox launch. |

## Routing Guardrail

Default routing guardrail in this repo remains active:
- Do not route steps above `medium_effort` or above `medium_tooling` to variable/free-tier model paths.
- Steps marked `requires_input_classification` must not be routed until input-driven classification is resolved.
