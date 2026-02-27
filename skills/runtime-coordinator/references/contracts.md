# Runtime Coordinator Contracts

## Runtime profile source
- `reports/optimus-prime/config/RUNTIME_PROFILES.json`

## Runtime state sinks
- `reports/optimus-prime/RUNTIME_REGISTRY.json`
- `reports/optimus-prime/TEST_RUNTIME_LEASES.json`

## Blocker intelligence sinks
- `reports/optimus-prime/BLOCKERS.jsonl`
- `reports/optimus-prime/BLOCKER_INDEX.json`
- `reports/optimus-prime/BLOCKER_ADAPTATION_CANDIDATES.md`

## Strategy values
- `none`
- `external_url`
- `shared_runtime`
- `isolated_runtime`

## Mutating flow policies
- `serialized`
- `account_pool`
- `isolated`

## Blocker category values
- `infra`
- `runtime`
- `env`
- `test-train`
- `dependency`
- `code`
- `test`
- `review`
- `orchestration`
- `external`
- `unknown`

## Deterministic requirements
- Runtime strategy must be machine-readable and packet-ready.
- Shared mutating flows must not collide: lease conflict returns blocked result.
- In test-train mode (`final-stage|forced-shared-env`), tester flows must resolve to hosted/shared runtime only and return `tester_must_not_start_runtime=true`.
- Every runtime-blocked state should append a blocker event.
- `log_blocker` action should be used by orchestrator for any non-runtime blocked state so blocker tracking remains complete.
- Blocker index must aggregate by `fingerprint` with first/last seen + count.
