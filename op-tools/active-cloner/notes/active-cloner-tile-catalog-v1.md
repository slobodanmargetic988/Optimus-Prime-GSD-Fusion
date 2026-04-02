# Active Cloner Tile Catalog v1

## Why this exists
Active Cloner needs a durable place to store reusable implementation packages before the full mining and auto-placement loop exists.

This catalog is the manual-first bridge:
- we can extract high-value code from existing apps now
- we can store it with framework variants and translation notes now
- later, Active Cloner can learn to discover, translate, rank, and place the same tile format automatically

## Catalog structure
- `tiles/catalog.json`: machine-readable tile index
- `tiles/<tile-id>/README.md`: human-facing overview and provenance
- `tiles/<tile-id>/tile.manifest.json`: contract, params, tests, compatibility, and upgrade strategy
- `tiles/<tile-id>/translation-map.md`: variant mapping and drift rules
- `tiles/<tile-id>/variants/<stack>/...`: stack-specific source ready for reuse

## Translation model
The translation layer should treat one tile as one behavior with multiple framework realizations.

Current expectation:
- React source can be extracted directly from an existing app
- Vue and Nuxt translations should be kept behaviorally aligned and stored as first-class variants, not as TODO placeholders
- future Cloner automation can pick a preferred source variant and generate or refresh sibling variants when the target stack differs

## Placement direction for future work
A future placement engine should be able to:
- inspect target app framework and package manager
- fetch the matching tile variant
- install dependency prerequisites
- insert the tile into the host shell with a deterministic adaptation trace
- record the placement into a warranty registry so upgrades stay trackable
