# Usage Template

## Blank Template
```text
Agent: optimus-planner
Goal: Build execution-ready plan for Optimus autonomous workflow.
Inputs: product_goal:
Inputs: target_users:
Inputs: scope_constraints:
Inputs: repo_root:
Inputs: tracking_mode: local
Inputs: plan_output_dir: docs/plans/
Inputs: tdd_policy: strict-test-first
Inputs: quality_gates: dev-self-check -> tester -> reviewer
Constraints: Produce Phase 1 first, then Phase 2 after approval. Tests defined before implementation tasks.
Output: Approved planning packet + TDD-aligned user stories + roadmap order
```

## Filled Example
```text
Agent: optimus-planner
Goal: Plan V2 of Optimus cycle controller and full GSD fusion workflow.
Inputs: product_goal: Deterministic autonomous orchestration with controller-owned cycle logic.
Inputs: target_users: solo founder operating multiple Codex workers.
Inputs: scope_constraints: standalone repo, no backward compatibility required.
Inputs: repo_root: /Users/slobodan/projects/Optimus-Prime-GSD-Fusion
Inputs: tracking_mode: local
Inputs: plan_output_dir: docs/plans/
Inputs: tdd_policy: strict-test-first
Inputs: quality_gates: dev-self-check -> tester -> reviewer
Constraints: Write test cases first from stories and task specs; include gate evidence requirements.
Output: Lane plans, user stories, acceptance criteria, test suite spec, feature build order
```
