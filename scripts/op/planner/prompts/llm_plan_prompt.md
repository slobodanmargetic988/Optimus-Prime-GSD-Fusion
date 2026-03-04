You are generating a deterministic Optimus planning bundle.

Hard requirements:
1. Output artifacts by writing a JSONL file at: {{BUNDLE_PATH}}
2. Each JSONL line MUST be one object with fields:
   - artifact_path (string; must resolve under reports/optimus-prime/planning)
   - content_type (json|text)
   - content (object/array for json, string for text)
   - checksum_sha256 (sha256 of canonical content)
3. After writing the bundle, run this validator command:
   {{VALIDATOR_COMMAND}}
4. If validation fails, fix artifacts and rerun validator until it passes.
5. Do not output prose files outside required artifacts.
6. The output must match the planner example contract in both folder path shape and per-file structure:
   {{EXAMPLE_ROOT}}

Context:
- repo_root: {{REPO_ROOT}}
- mission_source: {{MISSION_SOURCE}}
- scope_source: {{SCOPE_SOURCE}}
- map_artifact: {{MAP_PATH}}
- architecture_notes: {{ARCH_PATH}}

Required artifacts in bundle:
- PLAN_PACKETS.json
- PLAN_CHECK.json
- TASK_EXECUTION_STATE.json
- TEST_CONTRACT.md
- PLAYWRIGHT_UAT_MATRIX.md
- VERIFICATION.md
- UAT.md
- STATE.json
- STATE.md
- evidence/<task_id>/TASK_EVIDENCE.json for every task in PLAN_PACKETS.tasks

Planning requirements:
1. Build a parallelizable task DAG with explicit dependencies.
2. Every task has non-empty requirement_ids.
3. Every task must include lane-aware runtime metadata (required, no defaults):
   - lane_id in format <phase_id>/lane-[a-c]
   - status set to pending
   - gaps_that_need_patching as a list (default empty)
   - verification_contract object with explicit fields:
     - mode (tdd_red|implementation_green|hardening)
     - dev_expectation (expect_fail|expect_pass)
     - test_expectation (expect_fail|expect_pass)
     - review_expectation (expect_fail|expect_pass)
     - expected_failure_reason_codes[] (non-empty)
     - infra_failure_reason_codes[] (non-empty)
4. Every TASK_EXECUTION_STATE task row must include:
   - gapfix_state object:
     - active_batch_id (null on initialize)
     - active (false on initialize)
     - target_gap_stage (null on initialize)
     - consumed_gap_ids ([] on initialize)
     - batch_started_cycle (null on initialize)
     - batch_last_updated_at (null on initialize)
   - progress_watchdog object:
     - started (false on initialize)
     - first_dispatched_cycle (null on initialize)
     - task_started_cycle (null on initialize)
     - last_forward_progress_cycle (null on initialize)
     - consecutive_no_forward_progress_cycles (0 on initialize)
     - threshold_cycles (25)
     - triggered (false)
     - triggered_at (null)
5. Phase graph must be acyclic and task phase_id must map to a valid phase.
6. Per phase, use at most 3 distinct lanes.
7. TDD-first: each requirement and task must include verification intent.
   - phase-1 seed TDD tasks MUST use verification_contract.mode=tdd_red and expect_fail for dev/test/review.
8. For each functionality tree with more than 2 tasks, include at least 2 terminal hardening/review tasks.
9. PLAN_CHECK.passed must be true.
10. Keep plan quality high enough for autonomous op-build execution.

Strict output discipline:
- Write only the required JSONL bundle file + required artifact content.
- No markdown commentary in stdout is required.
