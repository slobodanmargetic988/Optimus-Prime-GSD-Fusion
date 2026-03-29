---
name: active-cloner-operator
description: "Operate as Active Cloner: extract user-nominated or mined reusable code into tiles, use TruthGraph to gather surrounding context, build framework variants, queue translation work, and record Earth-level improvement suggestions."
---

# Active Cloner Operator

Use this skill when the task is about:
- turning existing code into a reusable tile
- cataloging reusable capabilities
- planning or performing cross-framework translation
- deciding what Cloner should do next
- recording what Cloner needs from Earth to perform better

## Default workflow
1. Read `AGENTS.md`, `mission.md`, `scope.md`, and the latest vision/operating-model notes in this project.
2. Use [$truthgraph-context](/Users/slobodan/projects/Earth/TruthGraph/.codex-skills/truthgraph-context/SKILL.md) first when it can speed up source discovery, impact lookup, or surrounding context retrieval.
3. If the user nominates source code, treat that as first-class tile intake.
4. Collect the full capability surface:
   - source files
   - dependencies
   - host integration points
   - tests or verification expectations
5. Normalize the capability into the Active Cloner tile structure:
   - `tiles/catalog.json`
   - `tiles/<tile-id>/README.md`
   - `tiles/<tile-id>/tile.manifest.json`
   - `tiles/<tile-id>/translation-map.md`
   - `tiles/<tile-id>/variants/<stack>/...`
6. If a second framework variant is clearly relevant:
   - create it now, or
   - append a concrete queued item to `reports/tile-translation-backlog.md`
7. If Cloner is slowed by missing Earth capabilities, append a concrete suggestion to `reports/earth-improvement-suggestions.md`.

## Behavioral rules
- Prefer a real source implementation over greenfield invention.
- Preserve provenance to the source repo and file paths.
- Keep tile behavior human-explainable and adoption-ready.
- Do not leave translation as an untracked idea. Either implement it or queue it.
- Treat TruthGraph as a helper that improves extraction quality.

## Expected outputs
- a reusable tile package or a concrete plan to produce one
- translation status for relevant adjacent stacks
- explicit next-step suggestions when Earth is missing Cloner-supporting capabilities
