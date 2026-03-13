# Strategy Vision Clarifications (2026-03-13)

## User Clarifications Captured
1. Strategy is intended as an LLM-first pre-planner tool (similar placement to `op-plan`), not a deterministic summary script.
2. Strategy should run before `op-plan` and can be integrated into `op-initialize` pre-plan cycle.
3. Strategy must perform a broad Earth + subproject sweep and produce a rich project-specific intelligence packet.
4. Strategy outputs must include what other apps already provide, what they need from the target project, and how interactions should be shaped.
5. Strategy can use one or multiple consecutive LLM calls to achieve higher-quality reasoning.
6. After generation, Strategy outputs must be validated by deterministic validators (tool-call style) before planner consumption.
7. Goal is to reduce planner hallucination by giving planner richer, validated strategic context beyond mission/scope alone.

## Wave 1 Interpretation
- Wave 1 focuses on architecture/task alignment and removal of low-value deterministic-only framing.
- Later waves can further tighten task-level execution contracts and preflight scaffold behavior if needed.

## Wave 2 (non-TDD request)
- User requested removing TDD-first sequencing for Strategy to observe autonomous build behavior without test-driven ordering.
- User requested elimination of trivial/pure-ceremonial tasks.
- Wave 2 implements direct implementation-first stages plus targeted hardening/acceptance only where strategically necessary.

## Wave 3 (task quality lock request)
- User requested a serious review-only pass to tighten task execution detail after Wave 2 changes.
- Wave 3 keeps architecture intact and adds requirement-anchored scope locks to every task so managers have explicit boundaries and lower invention pressure.
