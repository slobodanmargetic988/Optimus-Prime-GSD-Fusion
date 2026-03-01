# Lane B Flow Diagrams

## Initialize/Plan/Build Control Flow

```mermaid
flowchart LR
  A["/op-initialize"] --> B["check-or-initialize-git"]
  B --> C["/op-map-codebase"]
  C --> D["/op-new-project"]
  D --> E["Profile autodetect -> PROFILE_SELECTION.json"]
  E --> F["/op-plan (LLM planner attempt)"]
  F --> G{"PLAN_BUNDLE + validation pass?"}
  G -- "No (attempt < 10)" --> F
  G -- "No (attempt = 10)" --> H["Fail: planner_retry_exhausted"]
  G -- "Yes" --> I["Atomic write canonical planning artifacts"]
  I --> J["/op-build"]

  K["/op-resume"] --> L["Reconcile stop ledger/tasks/workers"]
  L --> J

  J --> M["Preflight: lock + required artifacts + recover malformed gap artifacts"]
  M --> N{"Preflight OK?"}
  N -- "No" --> O["blocked_preflight"]
  N -- "Yes" --> P["Cycle: refresh profile rates -> controller tick -> ingest directives by control id/run id -> handoff/evidence sync -> gaps refresh -> phase/gate checks -> dispatch/skip -> watchdog update -> persist state -> sleep"]

  P --> Q{"Terminal condition?"}
  Q -- "No" --> P
  Q -- "Strict done satisfied" --> R["completed"]
  Q -- "operator stop / watchdog / hard terminal / long hard-rate-gate" --> S["stopped/blocked terminal"]
```

## Canonical Task Lifecycle

```mermaid
stateDiagram-v2
  [*] --> queued
  queued --> dev_in_progress
  dev_in_progress --> dev_done
  dev_done --> test_in_progress: ready_for_test
  test_in_progress --> test_done
  test_done --> review_in_progress: ready_for_review
  review_in_progress --> review_done

  dev_in_progress --> blocked: evidence invalid/missing or worker/slot failure
  test_in_progress --> blocked: verify/UAT failure
  review_in_progress --> blocked: review blocker
  blocked --> queued: remediation/requeue

  review_done --> [*]
```

## Build Cycle Tick Flow

```mermaid
flowchart LR
  A["Cycle start (last_cycle + 1)"] --> B["Refresh profile rate snapshot (selected aliases)"]
  B --> C["Run controller tick (max_cycles=1, control_number/run_id)"]
  C --> D["Load correlated directives"]
  D --> E["Apply directives (runtime/test-train/dispatch filters)"]
  E --> F["Handoff ingest + evidence sync + stale task recovery"]
  F --> G["Refresh gaps + closure packets + phase barrier checks"]
  G --> H["Normalize worker registry (dead PID cleanup)"]
  H --> I{"Dispatch decision (caps, gates, retries, profile assignment)"}
  I -- "dispatch" --> J["Dispatch next eligible task"]
  I -- "skip" --> K["Skip dispatch (blocked/gated/none eligible)"]
  J --> L["Re-ingest handoff updates"]
  K --> L
  L --> M["Strict-done + watchdog + progress ledger"]
  M --> N{"Terminal state?"}
  N -- "yes" --> O["Return terminal (completed/stopped/blocked)"]
  N -- "no" --> P["Persist state + sleep"]
  P --> A
```

## Sync Contract

1. Update this file in the same PR for behavior changes touching `/op-initialize`, `/op-plan`, `/op-build`, or `/op-resume`.
2. If behavior and diagram diverge, corresponding lane status must include `diagram drift` until reconciled.
