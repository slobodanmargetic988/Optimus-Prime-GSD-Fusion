# BP Project Note (2026-03-10)

## Immediate research note
- Research backend efficiency tradeoffs for Go vs Python/FastAPI in BP workloads.
- Output needed:
  - throughput and latency benchmarks for representative BP APIs
  - memory and ops complexity comparison
  - recommendation matrix for when Go should be selected as backend default

## New project tracks

### 1) Elasticsearch rollout track
- Goal: install and operate Elasticsearch across:
  - primary Mac desktop
  - Tanja laptop
  - mobile devices target set
  - family desktop set
- Deliverables:
  - reproducible install/runbook per device class
  - baseline cluster topology and sync strategy
  - backup, restore, and security hardening checklist

### 2) Torrent-based storage exploration
- Goal: evaluate torrent/distributed content approaches as a storage layer alternative for specific artifact types.
- Deliverables:
  - feasibility and risk matrix (privacy, legal, reliability, availability)
  - candidate architecture and prototype plan
  - explicit no-go conditions

### 3) Oroboro flagship brand build blocks
- Goal: use BP outputs as building blocks for flagship brand identity: **OROBORO**.
- Brand direction note:
  - giant white python
  - hologram-emitting eyes
  - building its own tail (not eating it)
  - shape is a bent loop, not a perfect circle
- Deliverables:
  - brand spec + mascot behavior brief
  - reusable design tokens and narrative guidelines
  - launch assets roadmap

### 4) Ground root-project tracker
- Goal: one root project named **Ground** that ties together many autonomous project repos and their telemetry.
- Architecture intent:
  - one root repo tracks all subprojects
  - each subproject has its own repo lifecycle
  - cross-project linking and dependency mapping must be queryable
- Search/index direction:
  - Elasticsearch as primary indexing/query engine for project/telemetry docs
  - document format should be token-efficient for LLM workflows

### 5) Token-efficient structured document format research
- Requirement: identify JSON-compatible/adjacent formats optimized for LLM token usage.
- Current candidate to evaluate first: **TOON (Token-Oriented Object Notation)**.
- Comparison set:
  - minified JSON + short-key schema
  - JSONL for event streams
  - TOON for prompt payloads
  - CBOR/MessagePack for transport/storage (non-human-readable baseline)
- Deliverable: benchmark report with token cost, readability, tooling maturity, and conversion reliability.

### 6) Human-readable execution trace policy
- Goal: every important code path emits a human-readable question/reason + observed answer/outcome.
- Policy intent:
  - explain why code executed
  - show what exactly was executed
  - record result in understandable language
- This supplements tests with traceable internal debugging and auditability.

### 7) AI Ninja Doctor project
- Goal: cross-device autonomous maintenance + protection agent.
- Product intent:
  - autonomous software maintenance
  - anti-attack protective posture
  - infection rollback using known-clean integrity checkpoints
  - minimalist UX: ninja-doctor run animation appears 3 times daily while user is present
- Deliverables:
  - integrity snapshot/restore model
  - defense + containment engine design
  - cross-platform runtime plan

### 8) Funding track and wallet recovery support
- Goal: recover access to your own historical crypto wallet assets and fund project roadmap.
- Strict compliance boundary:
  - only lawful recovery of wallets you own
  - no brute-force searching for third-party keys/addresses
  - no attempts to access non-owned funds
- Deliverables:
  - owner-proof recovery workflow (seed backups, derivation paths, xpub history, exchange exports)
  - deterministic balance audit for owned address sets
  - incident log for each attempted recovery path

## Prioritization suggestion (next sequencing)
1. Ground root-project tracker + telemetry model (foundation).
2. Token-efficient format benchmark (enables scale + lower LLM cost).
3. Elasticsearch rollout pilot (desktop + one laptop first).
4. Go backend efficiency study (decision gate for backend standardization).
5. Ninja Doctor and finance agent tracks as separate high-risk programs with governance gates.
