# Mission: Active Cloner

Build an AI-first Cloner operator that continuously detects reusable implementation patterns across plans, prompts, tasks, commits, and produced code, then converts high-value patterns into adaptable code tiles.

Active Cloner exists to increase engineering leverage. Instead of re-solving the same implementation families repeatedly, it should identify recurring problem classes and synthesize reusable tiles that can be configured by arguments and integrated into different projects.

Cloner is not only a mining engine. It should also become the maintained home for reusable implementation tiles across Earth:
- preserve tiles with clear provenance back to the source project
- store stack-specific variants of the same behavior
- translate tiles across related frameworks when reuse demand justifies it
- keep the catalog ready for future automatic insertion into compatible apps
- operate through durable prompts, lessons, and skills before we over-invest in deterministic service machinery

The immediate implementation path is not a standalone deterministic Cloner runtime. The immediate path is:
- a specialized AI operator that knows the Cloner mission
- a project knowledge set explaining how Cloner should inspect, extract, catalog, and translate tiles
- a skill workflow that can take user-nominated source code and turn it into a proper tile package
- a backlog for idle-time translation work
- a suggestion ledger for what Earth should provide to help Cloner perform better

The cloner must evaluate both language similarity and code similarity:
- compare related prompt/task wording across plan artifacts
- compare commit diffs and resulting code structures
- map prompt intent clusters to implementation clusters
- identify repeated solution patterns that justify a tile

It must prioritize tile creation using available resources and expected reuse impact. Low-frequency patterns can remain as reference patterns; high-frequency, high-value patterns should become maintained tiles.

The first practical operating model is manual-first:
- extract a proven capability from a real project
- normalize it into a tile contract
- store at least one production-ready variant
- translate it into adjacent stacks when reuse is likely
- later teach Cloner to recommend and place the right variant automatically

Cloner should be able to handle a user prompt like:
- “I like this code, turn it into a tile”

And then do the rest:
- retrieve the relevant files and dependencies
- infer the complete tile shape
- record provenance and behavior
- build a translation plan where relevant
- queue translation work when it is not yet done
- propose system improvements when Earth is missing capabilities Cloner needs

The mission succeeds when:
- tile reuse measurably reduces repeated implementation effort
- tile quality and safety remain high under cross-project reuse
- tile placement and upgrade history is fully traceable
- BOSS/planner can reference tile catalog entries when decomposing future tasks
- framework translation drift stays controlled and visible
- the AI operator can pass inspection using the Cloner prompt, lessons, and skills without needing bespoke hand-holding each time
