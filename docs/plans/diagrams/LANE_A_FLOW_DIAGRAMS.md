# Lane A Flow Diagrams

## Controller Tick Flow (single cycle)

```mermaid
flowchart LR
  A["Tick start (cycle_number += 1)"] --> B["Build snapshot (workers, latest logs)"]
  B --> C["Evaluate rate state (hard/soft/all-blocking + warnings)"]
  C --> D["Emit snapshot/warning events"]
  D --> E{"Terminal evidence?"}
  E -- "PROJECT_DONE valid" --> T1["terminal_reason=project_done"]
  E -- "INSURMOUNTABLE_BLOCKER valid" --> T2["terminal_reason=insurmountable_blocker"]
  E -- "all profiles hard-gated" --> T3["Write ALL_RATE_GATES_BLOCKING.json + terminal_reason=all_rate_gates_blocking"]
  E -- "none" --> F["Build directives (snapshot/rate/idle/runtime/blocker/handoff/test-train)"]

  F --> G["Append directive events"]
  G --> H["Write HEARTBEAT.json (running)"]
  H --> I{"max_cycles reached?"}
  I -- "yes" --> M["Return running: max_cycles_reached_without_terminal"]
  I -- "no" --> J["Append sleep event"]
  J --> K{"dry_run or sleep=0?"}
  K -- "yes" --> A
  K -- "no" --> L["time.sleep(sleep_minutes*60)"]
  L --> A

  T1 --> Z["Write FINAL_STATE.json + terminal event + return terminal"]
  T2 --> Z
  T3 --> Z
```

## Notes

1. Locking: controller acquires `lock.pid` before loop and releases on exit/finally.
2. Tick outputs: `EVENTS.jsonl`, `HEARTBEAT.json`, and optionally `FINAL_STATE.json`.
3. Keep aligned with `skills/optimus-cycle-controller/scripts/optimus_cycle_controller.py` and `docs/plans/LANE_A_IMPLEMENTATION_STATUS.md`.
