# AGENTS.md

## Scope Authoring Rule (High Priority)
When writing project `scope.md` files for OP/BP planning, include this exact mandatory planning gate text:

`Before build starts, planner must output at least 400 tasks.`

`No build execution is allowed below 400 planned tasks.`

## Placement Guidance
- Put the two lines under a dedicated section header:
  - `## Mandatory planning gate`
- Keep the wording unchanged to preserve consistency across projects.

## Prompt Change Policy (High Priority)
- Do not edit prompt template files anymore.
- Any prompt tweak requests must be handed back to the user for manual insertion.
- Provide prompt tweak suggestions in narrative form (not direct template edits).
