# Mission: Active Cloner

Build a standalone active-thread Cloner that continuously detects reusable implementation patterns across plans, prompts, tasks, commits, and produced code, then converts high-value patterns into adaptable code tiles.

Active Cloner exists to increase engineering leverage. Instead of re-solving the same implementation families repeatedly, it should identify recurring problem classes and synthesize reusable tiles that can be configured by arguments and integrated into different projects.

The cloner must evaluate both language similarity and code similarity:
- compare related prompt/task wording across plan artifacts
- compare commit diffs and resulting code structures
- map prompt intent clusters to implementation clusters
- identify repeated solution patterns that justify a tile

It must prioritize tile creation using available resources and expected reuse impact. Low-frequency patterns can remain as reference patterns; high-frequency, high-value patterns should become maintained tiles.

The mission succeeds when:
- tile reuse measurably reduces repeated implementation effort
- tile quality and safety remain high under cross-project reuse
- tile placement and upgrade history is fully traceable
- BOSS/planner can reference tile catalog entries when decomposing future tasks
