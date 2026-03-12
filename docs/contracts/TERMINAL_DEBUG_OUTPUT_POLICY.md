# Terminal Debug Output Policy

## Purpose
All new OP/BP code must be directly debuggable from standard terminal output without hidden logging dependencies.

## Rules
1. Use terminal output as the primary debug channel.
- Emit clear, timestamped `stdout`/`stderr` lines for important runtime transitions.
- Prefer single-line structured messages with stable keys.

2. Do not embed framework logger dependencies inside core functions by default.
- Core logic should not require a global logger object to be understandable.
- If output control is needed, pass an output callback (for example `emit(msg)`), with a simple terminal default at call site.

3. Background processes must flush output.
- Detached/nohup runners must use line-buffered or explicit flush behavior so progress is visible in real time.

4. Errors must be explicit.
- Print actionable error codes/reasons to `stderr`.
- Avoid silent failures.

5. Keep output human-readable first, machine-parseable second.
- Include context keys (`project=`, `pid=`, `phase=`, `result=`) where useful.
- Avoid excessive verbosity for routine loops.

## Recommended message format
`[component YYYY-MM-DDTHH:MM:SSZ] action key=value key=value`

## Scope
- Applies to new code and newly modified modules.
- Legacy modules can be migrated incrementally during normal maintenance.
