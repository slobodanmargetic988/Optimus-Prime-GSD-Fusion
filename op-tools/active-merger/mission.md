# Mission: Active Merger

Build a standalone active-thread merge manager that continuously monitors commit streams and handles merge lifecycle decisions independently from BOSS.

Active Merger exists to remove routine merge burden from orchestration planning cycles. Its job is to detect newly produced commits, evaluate each commit in project context, and either merge, hold, or reject with explicit rationale and evidence.

The service must be fast, continuous, and audit-friendly:
- it polls monitored sources frequently
- it handles commit decisions incrementally
- it records every decision in human-readable and machine-readable form
- it preserves branch safety and policy controls

The mission succeeds when merge throughput improves, BOSS cycle time drops, and no loss of traceability or safety occurs.
