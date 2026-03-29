# Active Cloner Vision v2: Reusable Tile Library and Translation Engine

## Why this update exists
The original Cloner framing correctly emphasized mining reusable code from task, prompt, and commit history.

What it understated is the product surface that should exist even before full automation:
- a curated tile catalog
- framework-aware variants of the same capability
- explicit translation between variants
- future host-aware placement into compatible apps

That is now the clearer vision.

## Core product idea
Active Cloner should become the Earth-wide home for reusable implementation tiles.

Each tile is:
- a meaningful behavioral unit, not a trivial snippet
- backed by provenance from a real source project
- described by an integration and test contract
- stored with one or more framework variants
- eligible for future host-aware placement

## What Cloner should do
1. detect repeated high-value implementation families
2. extract the strongest real implementation from an existing project
3. normalize it into a tile manifest and catalog entry
4. translate it into adjacent stacks when reuse is likely
5. recommend or eventually place the correct variant into a target app

## Why translation matters
Many Earth apps solve similar UI and workflow problems across adjacent stacks:
- React
- Vue / Nuxt
- FastAPI-backed frontends with similar browser behavior

If Cloner only stores one framework source, reuse still costs too much.

If Cloner stores and maintains translated variants, reuse becomes much closer to plug-and-play.

## Manual-first, automation-next
The right order is:
- manual extraction of a real capability
- durable tile storage
- translated sibling variants
- clear contracts and provenance
- later, automatic retrieval, recommendation, and insertion

This keeps the catalog useful immediately instead of waiting for a perfect autonomous miner.

## Immediate implications
- tile catalog structure is part of the product, not incidental scaffolding
- translation maps are first-class artifacts
- variant drift must be tracked explicitly
- host compatibility should influence future placement automatically

## First proof point
The browser capture to PDF tile extracted from AICOVENANT is the first concrete example of this vision:
- real source provenance
- reusable behavior
- React variant
- Nuxt/Vue variant
- future-ready placement shape
