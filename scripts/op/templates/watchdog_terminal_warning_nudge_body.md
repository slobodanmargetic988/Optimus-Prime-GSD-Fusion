This terminal-warning nudge is emitted when run-base inactivity is approaching the hard watchdog stop.

## Immediate actions
1. Prioritize merge/fan-in work that can move run-base quickly and safely.
2. Verify currently active merge/recovery packets are still making progress.
3. If merge packets are stalled, create direct remediation packets now.
4. Update canonical runtime artifacts after reconciliation so watchdog sees real progress.

After applying this warning, rename this file to `recovery_instructions_terminal_warning_CONSUMED.md`.
