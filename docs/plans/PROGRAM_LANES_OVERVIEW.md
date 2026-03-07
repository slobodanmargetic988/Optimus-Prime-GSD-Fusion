# Optimus Prime GSD Fusion — Program Lanes Overview

## Product Vision (Review Anchor)
1. User flow is two-step:
   - `/op-initialize` prepares the project (git bootstrap when needed, map, project baseline, profile detection + rate snapshot seeding, strict LLM plan).
   - `/op-build` executes autonomously until strict done or deterministic hard stop.
2. New-only model:
   - no backward-compat behavior branches,
   - strict machine-validated artifacts and gates,
   - deterministic failure codes over implicit fallback.
3. Lane boundaries:
   - Lane B owns planner + autonomous runtime behavior,
   - Lane C owns install/distribution/ops UX,
   - Lane D is future chaos/reliability hardening,
   - Lane E is future thread-continuation/token-efficiency.

## Lane A (implemented)
Deterministic cycle controller core and stop-prevention rules.

- Spec: `/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/docs/plans/LANE_A_PHASE1_PLAN.md`
- Status: `/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/docs/plans/LANE_A_IMPLEMENTATION_STATUS.md`

## Lane B (done)
Full GSD fusion capabilities: planning lifecycle, plan gates, test-first contracts, UAT/gap closure, reliability layer.

- Implemented now: Batch 1 runtime pipeline + hard gate remediation (`bootstrap/start/health/deploy/stop/repair`, single-flight locking, stale lease sweep, runtime repair routing, test-train hard gates).
- Implemented now: OP command surface and planning/build flow (`/op-map-codebase`, `/op-new-project`, `/op-plan`, `/op-initialize`, `/op-build`, `/op-health`, `/op-status`, `/op-resume`) with strict build preflight, canonical task execution state, multi-phase DAG planning, strict phase barriers, artifact-first task evidence gating, deterministic UAT gap tracking/closure packets, single-flight loop lock, strict-first dispatch gating, state-derived test-train adapter mode, truncation-safe handoff offset recovery, remediation-then-continue behavior, strict-done completion gate, and hard rate-gate policy (`<=2h` wait/resume, `>2h` manual rerun stop).
- Implemented now: initialize bootstrap semantics are explicit: check git state, LLM-assisted git bootstrap when missing, deterministic git verification, then map -> new-project -> profile detection/state update -> rate snapshot seed -> strict LLM plan generation.
- Current posture: done for intended scope, validated as a usable autonomous app-building engine.
- Next lane focus: Lane C packaging/installer UX and private prerelease validation.

- Spec: `/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/docs/plans/LANE_B_FULL_GSD_FUSION_PLAN.md`
- Status: `/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/docs/plans/LANE_B_IMPLEMENTATION_STATUS.md`

## Lane C (in progress)
Installable product packaging, command UX, diagnostics, docs, and release framework.

- Implemented now: deterministic GitHub-first release bundle builder + checksum artifacts, install/update/uninstall/doctor commands, product `opctl` wrapper, private release fetch/auth installer path, release publish workflow, and private smoke matrix workflow.
- Pending next: first real private prerelease execution (`vX.Y.Z-rc.N`) and green smoke evidence across macOS/Linux + global/local.

- Spec: `/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/docs/plans/LANE_C_INSTALLABLE_PRODUCT_PLAN.md`
- Status: `/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/docs/plans/LANE_C_IMPLEMENTATION_STATUS.md`

## Sequencing Rule
Lane A -> Lane B -> Lane C, with Lane D and Lane E as post-core extension lanes.

## Diagrams
1. [Diagram index](/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/docs/plans/diagrams/README.md)
2. [Lane A diagrams](/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/docs/plans/diagrams/LANE_A_FLOW_DIAGRAMS.md)
3. [Lane B diagrams](/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/docs/plans/diagrams/LANE_B_FLOW_DIAGRAMS.md)
4. [Lane C diagrams](/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/docs/plans/diagrams/LANE_C_FLOW_DIAGRAMS.md)
5. [Lane D diagrams](/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/docs/plans/diagrams/LANE_D_FLOW_DIAGRAMS.md)
6. [Lane E diagrams](/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/docs/plans/diagrams/LANE_E_FLOW_DIAGRAMS.md)

Policy:
1. Behavior-changing lane PRs must update the corresponding diagram file in the same PR.
2. If not updated yet, lane status must carry a `diagram drift` note.
