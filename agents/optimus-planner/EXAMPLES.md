# Examples

## Example 1: Lane Planning for Controller Core

### Input
```text
Agent: optimus-planner
Goal: Produce lane plan for cycle controller hard-stop prevention.
Inputs: product_goal: Deterministic cycle control and terminal-state enforcement.
Inputs: target_users: Optimus Prime orchestrator.
Inputs: scope_constraints: terminal reasons limited to 3 allowed reasons.
Inputs: repo_root: /Users/slobodan/projects/Optimus-Prime-GSD-Fusion
Inputs: tdd_policy: strict-test-first
```

### Expected Output
```text
Phase 1 docs approved, then Phase 2 stories with tests-first mapping.
Controller contracts defined (events, heartbeat, final-state).
Acceptance criteria include proof that Optimus cannot stop without terminal FINAL_STATE.
```

## Example 2: Full Product Planning

### Input
```text
Agent: optimus-planner
Goal: Extend from Lane A to full GSD fusion + packaging lanes.
Inputs: product_goal: End-to-end autonomous coding workflow with deterministic gates.
Inputs: target_users: Operator running multi-agent delivery loops.
Inputs: scope_constraints: Keep Agents repo untouched; standalone implementation.
Inputs: repo_root: /Users/slobodan/projects/Optimus-Prime-GSD-Fusion
Inputs: quality_gates: dev-self-check -> tester -> reviewer
```

### Expected Output
```text
Roadmap with Lane A/B/C sequence.
Story-level acceptance criteria and test cases written before implementation tasks.
Explicit handoff criteria that shift tester focus to meaningful Playwright validation.
```
