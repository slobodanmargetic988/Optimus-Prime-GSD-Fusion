# LLM Interaction Classification

This document classifies LLM-interacting runtime steps using the required enums:
- `reasoning_effort`
- `tooling_effort`

## Classification Map

| Runtime Step | Code Reference | reasoning_effort | tooling_effort | Notes |
|---|---|---|---|---|
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
