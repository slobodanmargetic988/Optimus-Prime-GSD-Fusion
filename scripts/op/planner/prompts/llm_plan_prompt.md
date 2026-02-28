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
- GAPS.json
- GAP_CLOSURE_PLAN_PACKETS.json
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
3. Phase graph must be acyclic and task phase_id must map to a valid phase.
4. TDD-first: each requirement and task must include verification intent.
5. For each functionality tree with more than 2 tasks, include at least 2 terminal hardening/review tasks.
6. PLAN_CHECK.passed must be true.
7. Keep plan quality high enough for autonomous op-build execution.

Strict output discipline:
- Write only the required JSONL bundle file + required artifact content.
- No markdown commentary in stdout is required.
