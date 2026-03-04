# Lane Diagrams Index

This directory contains lane-scoped flow/state diagrams.

Location contract:
1. Lane diagrams live in `docs/plans/diagrams/LANE_<X>_FLOW_DIAGRAMS.md`.
2. Keep diagrams aligned with behavior in the corresponding lane status/spec docs.

Files:
1. [LANE_A_FLOW_DIAGRAMS.md](/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/docs/plans/diagrams/LANE_A_FLOW_DIAGRAMS.md)
2. [LANE_B_FLOW_DIAGRAMS.md](/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/docs/plans/diagrams/LANE_B_FLOW_DIAGRAMS.md)
3. [LANE_C_FLOW_DIAGRAMS.md](/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/docs/plans/diagrams/LANE_C_FLOW_DIAGRAMS.md)
4. [LANE_D_FLOW_DIAGRAMS.md](/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/docs/plans/diagrams/LANE_D_FLOW_DIAGRAMS.md)
5. [LANE_E_FLOW_DIAGRAMS.md](/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/docs/plans/diagrams/LANE_E_FLOW_DIAGRAMS.md)

Draw.io desktop files (Lane B):
1. [LANE_B_INITIALIZE_BUILD_FLOW.drawio](/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/docs/plans/diagrams/LANE_B_INITIALIZE_BUILD_FLOW.drawio)
2. [LANE_B_TASK_LIFECYCLE.drawio](/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/docs/plans/diagrams/LANE_B_TASK_LIFECYCLE.drawio)
3. [LANE_B_BUILD_CYCLE_FLOW.drawio](/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/docs/plans/diagrams/LANE_B_BUILD_CYCLE_FLOW.drawio)

Draw.io desktop files (Lane A):
1. [LANE_A_CONTROLLER_TICK_FLOW.drawio](/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/docs/plans/diagrams/LANE_A_CONTROLLER_TICK_FLOW.drawio)

Maintenance rule:
1. Any behavior-changing PR touching lane logic must update that lane’s diagram file in the same PR.
2. If behavior and diagram diverge, lane status must explicitly call out `diagram drift` until fixed.
