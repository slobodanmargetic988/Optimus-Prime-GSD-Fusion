# Active Cloner Tile Catalog

Tiles are reusable implementation packages that Active Cloner can mine, translate, and eventually place into compatible apps.

Each tile should be stored as:
- one tile directory per reusable capability
- one `tile.manifest.json` describing the contract
- one `README.md` explaining the behavior and installation path
- one or more stack variants under `variants/`
- one translation note describing how variants map to each other

A tile is ready for reuse when it includes:
- parameter and argument schema
- integration contract
- test contract
- compatibility notes
- upgrade strategy
- at least one runnable stack variant

The first tile in this catalog is `browser-capture-pdf`, extracted from AICOVENANT and translated for both React and Nuxt/Vue stacks.
