# OP Simple API Profile Integration Plan

## Status
- Draft future plan.
- Not implemented yet.
- Goal: support Codex API-key profile execution without requiring per-profile `auth.json` discovery.

## Problem
Current profile discovery and gating are strongly coupled to `.codex*` folders with first-level `auth.json` and `CODEX_HOME` routing. That blocks clean API-key-only setups and makes profile selection dependent on local auth file shape.

## Goals
- Add first-class API-based profile support for `/op-initialize` and `/op-simple-build`.
- Keep `auth.json`/`CODEX_HOME` mode fully backward compatible.
- Allow mixed fleets in one run:
  - some profiles from `CODEX_HOME`
  - some profiles from API key env-based credentials
- Keep runtime safe when rate/budget data is partial or unavailable.
- Never persist raw API keys in repo artifacts.

## Non-Goals
- Rewriting dispatcher/boss orchestration model.
- Removing existing `.codex*` auth-based support.
- Adding hard dependency on external billing APIs in the first delivery phase.

## Proposed Model

### 1) Profile Source Abstraction
Introduce profile `auth_mode`:
- `codex_home` (existing behavior)
- `api_key_env` (new behavior)

Each selected profile row resolves to one runtime launch contract:
- `alias`
- `auth_mode`
- `credential_ref` (never raw key)
- `provider` (default `openai`)
- optional provider fields (`base_url`, `org_id`, `project_id`)

### 2) Config-First Profile Registry
Add optional profile registry in global/project config (`scripts/install/config.py`):
- `profiles.registry[]` (ordered, explicit)
- Each row includes:
  - `alias`
  - `auth_mode` (`codex_home|api_key_env`)
  - `codex_home` (required for `codex_home`)
  - `api_key_env_var` (required for `api_key_env`, for example `OPENAI_API_KEY_OP1`)
  - optional: `provider`, `base_url_env_var`, `org_env_var`, `project_env_var`
  - optional: `enabled` (default `true`)

Resolution order:
1. explicit `profiles.registry` rows
2. fallback existing `.codex*` autodiscovery

### 3) Artifact Contract Updates
Extend planning/runtime profile artifacts while keeping old fields valid.

`reports/optimus-prime/planning/PROFILE_SELECTION.json` row additions:
- `auth_mode`
- `credential_ref` (for example `env:OPENAI_API_KEY_OP1` or `codex_home:/Users/.../.codex-second`)
- `provider`
- optional provider metadata refs

`.op-simple/current/profile_snapshot.json` row additions:
- `auth_mode`
- `provider`
- `rate_source` (`session_snapshot|api_usage|unknown`)
- `budget_source` (`none|env|external`)
- `budget_soft_gated` (boolean)

No raw secrets in:
- `PROFILE_SELECTION.json`
- `profile_snapshot.json`
- logs
- manager packets

### 4) Runtime Launch Behavior
Update manager/worker launch env assembly:
- `codex_home` profile:
  - keep current behavior (`CODEX_HOME=<path>`)
- `api_key_env` profile:
  - load API key from configured env var at runtime
  - export `OPENAI_API_KEY` for launched Codex process
  - optionally export `OPENAI_BASE_URL`, `OPENAI_ORG_ID`, `OPENAI_PROJECT_ID` from configured env refs
  - do not write env values into artifacts/logs

If required env var missing:
- mark profile hard-gated for this cycle with deterministic reason code
- continue cycle safely (no fatal crash unless no eligible profiles remain)

## Rate/Budget Gating Strategy

### Phase 1 (safe minimum)
- Keep current snapshot-based gating for `codex_home`.
- For `api_key_env` profiles:
  - if session-based rate snapshot is available, use it
  - otherwise treat as `soft_gated` with conservative active-worker cap
  - never mark `eligible` without at least credential availability

### Phase 2 (improved)
- Add optional API usage adapter to enrich gating with account-level budget/rate signals.
- Keep adapter failure non-fatal; fallback to Phase 1 conservative gates.

## Required Code Changes

### A) Config Layer
- `scripts/install/config.py`
  - add schema validation for `profiles.registry`
  - keep defaults backward compatible (registry optional)
- tests:
  - `scripts/install/tests/test_config_resolution.py`

### B) Initialize/Profile Selection
- `scripts/op/op_core.py`
  - add profile discovery path from config registry
  - update `PROFILE_SELECTION.json` writer/reader contracts for `auth_mode`
  - keep `.codex*` detection as fallback
- tests:
  - `scripts/op/tests/test_op_core.py`
  - integration coverage in `scripts/op/tests/test_op_build_integration.py`

### C) OP Simple Runtime
- `scripts/op/op_simple_build.py`
  - update alias->launch context mapping from `codex_home` only to `profile launch contract`
  - pass API env credentials for `api_key_env` profiles
  - extend snapshot handling to include `auth_mode` metadata and conservative gates
- tests:
  - `scripts/op/tests/test_op_simple_build.py`

### D) Skills and Snapshot Tooling
- `skills/minimal-rate-snapshot`
  - remove hard dependency on local `auth.json` identity parsing for eligibility
  - support profile rows that are API-env-backed
  - keep identity read best-effort only

## Prompt/Docs Updates
- Update manager docs/prompts to describe mixed profile modes and secret handling:
  - BOSS should assign only eligible profiles regardless of `auth_mode`.
- Update:
  - `docs/plans/OP_SIMPLE_EXECUTION_SPEC_V2.md`
  - `docs/plans/OP_SIMPLE_SCHEMA_CATALOG_V2.md`
  - runtime operator docs/README command examples

## Safety Rules
- Never persist API keys.
- Never echo sensitive env var values in logs.
- Artifact reasons must be explicit:
  - `api_key_env_missing`
  - `api_profile_snapshot_unavailable`
  - `api_profile_budget_soft_gated`
  - `api_profile_hard_gated`

## Rollout Plan

### Milestone 1: Registry + Launch Contract
- Config schema + parsing
- `PROFILE_SELECTION` contract extension
- runtime launch env support for `api_key_env`
- unit tests green

### Milestone 2: Gating Hardening
- conservative fallback policy for API profiles
- snapshot tool updates
- e2e canary with mixed profile fleet

### Milestone 3: Optional Budget/Rate Adapter
- pluggable external usage source
- stricter soft/hard gate decisions
- docs + operational guidance

## Acceptance Criteria
- `/op-initialize` succeeds with profiles that have no local `auth.json`.
- `/op-simple-build` can dispatch BOSS/workers with `api_key_env` profile rows.
- Mixed `codex_home` + `api_key_env` runs dispatch safely.
- Missing API env var is handled as deterministic profile gating, not runtime crash.
- No secret leakage in artifacts/history/logs.
- Existing auth.json-based flows remain unchanged.
