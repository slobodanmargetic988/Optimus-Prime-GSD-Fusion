# Mission: Active Debugger

Build a standalone active-thread debugger that continuously detects and resolves small, bounded defects with surgical precision and strong evidence output.

Active Debugger exists to absorb micro-fix loops that do not need full orchestration overhead. It should rapidly handle narrow issues such as configuration drift, artifact wiring mistakes, flaky command wrappers, minor runtime regressions, and small logic defects where scope can be tightly bounded.

The tool must prioritize precision over breadth:
- identify a specific defect
- propose a small targeted patch
- execute scoped verification
- emit clear outcome evidence and handoff notes

The mission succeeds when routine small defects are resolved quickly, safely, and transparently while preserving escalation pathways for larger or riskier issues.
