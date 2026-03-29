# Active Cloner AI-First Operating Model v1

## Current preferred direction
The preferred v1 implementation is not a deterministic service-first Cloner.

The preferred v1 is:
- a durable prompt/persona for Cloner
- a project-local skill pack
- persistent notes and lessons
- a reusable tile catalog
- a translation backlog
- an improvement ledger for Earth-level needs

This gives us a useful Cloner sooner and keeps the product aligned with how the work is actually being discovered.

## Core operating loop
1. receive tile intake
2. retrieve surrounding source context
3. identify all required pieces of the capability
4. normalize into tile contract and catalog entry
5. create or update stack variants
6. record translation plan if needed
7. append Earth improvement suggestions if blocked

## Tile intake modes
### 1) User-nominated intake
The operator says:
- “I like this code, turn it into a tile”

Cloner should then:
- inspect the source repo and implementation surface
- pull the supporting files and dependencies
- infer the behavioral unit boundaries
- catalog it as a tile

### 2) Mined intake
Cloner detects repeated implementation families across tasks, prompts, commits, and produced code and proposes a tile candidate.

### 3) Idle translation intake
When the backlog is not empty and no higher-priority intake exists, Cloner can translate existing tiles into adjacent stacks.

## TruthGraph role
TruthGraph should be part of Cloner's normal toolkit because it can help with:
- source file discovery
- symbol and caller lookup
- bundle/context retrieval
- cross-repo closure
- impact-aware extraction

TruthGraph does not remove the need for direct inspection, but it should reduce wasted searching.

## Output discipline
Cloner should leave a durable paper trail:
- tile manifest
- README
- translation map
- variant files
- translation backlog update
- Earth improvement suggestion when needed

## Inspection bar
Cloner passes inspection when another worker can look at the tile package and understand:
- what behavior was captured
- where it came from
- which stacks are supported
- what still needs translation
- what the host app must do to adopt it
