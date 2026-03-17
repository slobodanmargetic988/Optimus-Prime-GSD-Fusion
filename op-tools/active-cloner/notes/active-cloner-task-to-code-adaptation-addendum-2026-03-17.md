# Active Cloner Exploration Addendum: Task-to-Code Adaptation

## Status
- This note describes one promising approach we are exploring.
- It is not yet the final or exclusive implementation direction for Active Cloner.
- The purpose of this note is to capture a stronger product framing before the idea gets diluted into generic "knowledge graph" work.

## Core reframing
Active Cloner should not be framed primarily as a generic document graph builder or a generic knowledge graph product.

The higher-value framing is:
- ingest large task/plan corpora
- identify tasks that are structurally or semantically similar
- map those tasks to code that already satisfies similar intent
- build adaptation packets so future workers start from retrieved implementation instead of greenfield invention

In that framing, Active Cloner becomes a task-to-code adaptation engine.

## Why this direction matters
The main problem is not "we need a graph because graphs are interesting."

The real problem is:
- we have hundreds of task plans
- many of them describe overlapping implementation families
- LLM workers still tend to rebuild from scratch
- cross-project reuse is too expensive to rediscover manually

If Active Cloner can connect similar tasks to existing code and tests, it can shift future work from invention to adaptation.

That is the leverage target.

## Working hypothesis
The most useful pipeline is likely:
1. ingest task plans and normalize them into structured task records
2. compute task-to-task similarity using deterministic features plus semantic similarity
3. search indexed codebases for implementation candidates that match task intent
4. assemble adaptation packets with candidate files, symbols, tests, and warnings
5. let a future worker adapt retrieved code rather than starting from zero

This aligns directly with the intended future role of Active Cloner.

## Proposed system layers

## 1) Structured task store
Normalize task documents into records with fields such as:
- task id
- project id
- lane / phase
- title
- intent
- constraints
- inputs
- outputs
- acceptance criteria
- related docs
- related code candidates

This layer should be explicit and queryable. It should not depend on opaque LLM-only interpretation.

## 2) Similarity layer
Use a hybrid approach:
- deterministic features: tags, repo, lane, keywords, acceptance patterns, artifact names
- semantic similarity: embeddings over task text, scope, and acceptance criteria

Goal:
- find nearest-neighbor tasks
- cluster repeated implementation families
- identify high-confidence reuse opportunities

## 3) Code candidate retrieval layer
Use existing code graph tools instead of forcing Active Cloner to rediscover code structure from scratch.

Likely split:
- GitNexus for repo-local structural retrieval, impact analysis, refactor/review context, symbol/process inspection
- CodeGraphContext for cross-project discovery and broad ecosystem search

This layer should answer questions like:
- which files already implement behavior like this task describes?
- which symbols and tests are most likely relevant?
- which prior implementations are closest in structure and intent?

## 4) Relationship layer
Maintain explicit relationships such as:
- task -> similar task
- task -> candidate repo
- task -> candidate file
- task -> candidate symbol
- task -> likely tests
- task -> reused implementation family

This can be stored as graph edges, structured records, or both.

The important part is traceable retrieval, not graph purity.

## 5) Adaptation packet layer
Produce a deterministic packet for a future worker containing:
- similar prior tasks
- candidate files and symbols
- closest matching implementations
- likely affected tests
- repo boundaries
- risk notes / blast-radius hints

This packet should become the starting point for implementation.

## What to borrow from existing tools

## Cognee
Potentially useful for:
- document ingestion ideas
- dataset organization
- chunking strategies
- document corpus handling

Not a good core fit for the product itself because:
- it is LLM-first in a way that makes the core extraction pipeline opaque
- it is oriented toward semantic document graphing, not task-aware code adaptation
- it does not directly solve task -> reusable implementation -> adapted code

Conclusion:
- borrow ideas and maybe selected ingestion/storage patterns
- do not center Active Cloner on Cognee's product model

## GitNexus
Very useful source of leverage for:
- repo-local code understanding
- impact analysis
- refactor/review workflows
- symbol and execution-flow retrieval

Conclusion:
- likely a strong engine dependency for the code retrieval stage

## CodeGraphContext
Very useful source of leverage for:
- shared multi-repo discovery
- cross-project code search
- ecosystem-wide candidate hunting

Conclusion:
- likely useful before GitNexus in broad candidate discovery
- then GitNexus can do deeper local inspection

## Ground
Useful for:
- canonical identity discipline
- project/task/run/artifact linkage
- portfolio-level traceability

Conclusion:
- Ground should remain a truth layer for runtime/project identity, not the code retrieval engine

## Suggested execution model
The likely combined retrieval path is:
1. search tasks for similar past work
2. use cross-project discovery to find candidate repos / files
3. use repo-local code graph tooling to inspect likely implementations deeply
4. generate an adaptation packet
5. dispatch a worker to modify retrieved code into the current target shape

This suggests Active Cloner should be a coordinator over multiple retrieval engines, not a monolithic graph-only system.

## Important design guardrail
We should avoid building "one giant magical graph" as the first move.

A better first implementation is:
- normalized task records
- similarity index
- code candidate retrieval adapters
- deterministic adaptation packets

The graph can support this, but the graph should not become the product by itself.

## Practical v1 candidate
A first useful version could be:

### task_indexer
- ingest task plans
- emit normalized task records

### task_similarity
- compute nearest-neighbor and cluster relationships

### code_candidate_finder
- query CGC for broad multi-repo candidates
- query GitNexus for deep repo-local structure

### clone_packet_builder
- emit a deterministic packet with:
  - similar tasks
  - candidate code
  - candidate tests
  - constraints
  - risk notes

### worker_adapter
- consume the packet
- adapt existing code
- verify with tests and impact analysis

## Why this is only an exploration note
This direction feels stronger than a generic graph-first approach, but it still needs proof.

Open questions:
- how accurate task similarity will be at Earth scale
- how much code retrieval can be made deterministic before semantics are needed
- whether the first tile/unit of reuse should be "code tile", "adaptation packet", or both
- how much of the pipeline should be persisted as explicit graph edges versus search indexes and manifests

## Current position
At the moment, this is the most promising Active Cloner direction under discussion:
- not generic knowledge graphing
- not pure tile synthesis in the abstract
- but task-aware retrieval and code adaptation at ecosystem scale

If it proves out, it can become one of the main foundations for reducing repeated implementation effort across Earth.

## Canonical provenance split
This exploration direction depends on a clean split between shared Earth truth and Active Cloner intelligence.

### Earth / Ground should own
- canonical planning provenance ingestion
- normalized task records and shared IDs
- joins between task planning artifacts, mission/scope references, runs, evidence artifacts, and commit SHAs

This is shared infrastructure and should not be trapped inside Active Cloner alone.

### Active Cloner should own
- task similarity and clustering
- phrase-to-commit and phrase-to-implementation pattern discovery
- implementation candidate retrieval
- adaptation packet generation
- reuse analytics

This keeps Active Cloner focused on reuse leverage rather than becoming the canonical system of record for all planning provenance.

## Existing ingredients already present
We are not starting from a blank slate.

Important fragments already exist across Earth:
- `PLAN_PACKETS.json` already contains rich task text and structure such as:
  - `task_id`
  - `title`
  - `requirement_ids`
  - `must_haves`
  - `verify_commands`
  - some deliverable / target references
- trace-event envelopes already carry canonical runtime linkage such as:
  - `task_id`
  - `run_id`
  - `artifact_id`
  - `commit_sha`
- task evidence and handoff files already capture task-scoped outcomes and evidence summaries

What is still missing is the normalized join layer that turns those fragments into one reusable provenance record for Earth-wide analytics and reuse workflows.
