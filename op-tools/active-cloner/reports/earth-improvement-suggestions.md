# Active Cloner Earth Improvement Suggestions

This report captures what Cloner needs from Earth to do its job better.

Use this file for concrete suggestions, not vague wishes.

## 2026-03-29 Seed Suggestions

### 1. Tile fetch and install helper
- need: a reusable installer flow that can fetch the correct tile variant into a host app and wire required dependencies
- why: the tile catalog is useful now, but reuse still requires manual integration work
- likely owner: `active-cloner` plus target-app integration helpers

### 2. Host stack detector
- need: a reliable way to infer app stack and preferred tile variant
- why: future placement should choose `react-vite`, `nuxt-vue`, or another variant automatically
- likely owner: `active-cloner`

### 3. TruthGraph-backed extraction helpers
- need: stronger tile-extraction workflows built on top of TruthGraph lookup, impact, and bundle retrieval
- why: Cloner should gather all relevant source pieces faster and with fewer misses
- likely owner: `TruthGraph` + `active-cloner`

### 4. Idle translation runner
- need: a safe way for Cloner to work through `reports/tile-translation-backlog.md` when no higher-priority intake exists
- why: translation is part of reuse leverage and should not depend on someone remembering it manually
- likely owner: `active-cloner`
