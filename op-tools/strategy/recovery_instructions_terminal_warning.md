# Recovery Nudge: Terminal Warning

Generated at: 2026-03-15T22:01:22Z
Cycle: 45
Reason: Watchdog hard-limit terminal stop is approaching.
Branch: op-simple-canary-20260314T214654Z-ac48393d
Commit ref: op-simple-canary-20260314T214654Z-ac48393d
Last observed commit sha: ee492c18f51b04e675ad527206ca4bd03e026e63
Last observed commit timestamp: 2026-03-15T06:17:04Z
Run-base hard-limit age: 285.26 minutes
Run-base hard-limit threshold: 300 minutes
Warning lead window: 20 minutes

This terminal-warning nudge is emitted when run-base inactivity is approaching the hard watchdog stop.

## Immediate actions
1. Prioritize merge/fan-in work that can move run-base quickly and safely.
2. Verify currently active merge/recovery packets are still making progress.
3. If merge packets are stalled, create direct remediation packets now.
4. Update canonical runtime artifacts after reconciliation so watchdog sees real progress.

After applying this warning, rename this file to `recovery_instructions_terminal_warning_CONSUMED.md`.
