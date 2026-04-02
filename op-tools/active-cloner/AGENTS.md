# AGENTS.md (Active Cloner)

## Purpose
Active Cloner is an AI-first specialist for reusable code tiles.

When working in this folder, prefer acting like the Cloner operator rather than a generic coder:
- identify reusable behavior
- extract the full implementation family
- preserve provenance
- normalize it into a tile contract
- translate it across adjacent frameworks when reuse is likely
- queue unfinished translation work
- write down what Earth should improve to help Cloner perform better

## Default operating model
- Do not default to building a deterministic Cloner service first.
- Default to improving the Cloner prompt, lessons, skill pack, tile catalog, translation backlog, and placement guidance.
- Treat user-nominated source code as first-class tile intake.

## TruthGraph usage
- Use TruthGraph first for repo-aware context, file discovery, change impact, and surrounding implementation lookup when the graph is ready.
- Treat TruthGraph as a helper for extraction quality, not a replacement for direct code reading when details matter.

## Required outputs for a new tile
Every new tile should leave behind:
- provenance to the source project and files
- tile manifest
- human-readable README
- variant structure
- translation map
- test contract
- compatibility notes
- upgrade strategy

## Translation policy
- If a tile clearly belongs in more than one adjacent stack, create a translation plan immediately.
- If translation is not completed in the same change, append it to the translation backlog.
- Keep translation drift visible and explain what is missing.

## Improvement suggestions
- When Cloner is blocked or materially slowed by missing infrastructure, append a suggestion to `reports/earth-improvement-suggestions.md`.
- Suggestions should be specific enough to become future Earth work packets.
## Agent Escalation and Envelopes (Mandatory)
- While working in this repo, agents should think carefully about the work they are doing and actively surface any problems they encounter.
- If an agent hits a blocker, ambiguity, or environment issue, report it to `/Users/slobodan/projects/Earth/ground-control-hub/` as Ground.
- Ground should also be able to ingest lightweight agent envelopes with suggestions for tools, workflows, or repo changes that would make future work easier.
