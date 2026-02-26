# Lane C — Installable Product Plan (Distribution, UX, and Adoption)

## Summary
Lane C converts the fused Optimus system (Lane A + Lane B) into a clean, installable product that users can run from terminal with minimal setup friction.

This lane is packaging/productization only. Core orchestration logic is expected to already exist.

---

## Objectives
1. Provide one-command install and update paths.
2. Provide clean CLI/command UX for full workflow.
3. Validate environment and dependencies automatically.
4. Ship templates/configuration that are safe and deterministic by default.
5. Provide docs and diagnostics so users can operate without manual internals knowledge.

---

## C1 — Installer + Uninstaller

### Scope
Build installation tooling for global and local modes:
- install commands/skills/workflows/templates
- set default config and runtime paths
- uninstall cleanly

### Acceptance criteria
- install works on clean machine with deterministic output
- uninstall removes installed components and leaves user workspace intact

---

## C2 — CLI Command Surface

### Scope
Define stable command namespace (examples):
- init project
- plan phase
- execute phase
- verify phase/UAT
- show progress/status
- pause/resume
- health/repair
- update

### Acceptance criteria
- help command documents every command and arguments
- command errors are actionable and machine-parseable

---

## C3 — Config + Profile System

### Scope
Create robust config model:
- model profiles (quality/balanced/budget)
- workflow toggles
- rate gate defaults
- path overrides
- per-project overrides + optional global defaults

### Acceptance criteria
- deterministic config resolution precedence
- config validation errors include exact fix guidance

---

## C4 — Environment Validation

### Scope
Add preflight diagnostics:
- required binaries/tools present
- MCP availability checks
- skill integrity checks
- write permissions and workspace sanity checks

### Acceptance criteria
- one command outputs full readiness status
- optional `--repair` fixes auto-fixable issues

---

## C5 — Product Docs + Templates

### Scope
Ship user docs and starter templates:
- quick start
- full workflow guide
- troubleshooting
- architecture overview
- migration notes for users coming from custom orchestrators

### Acceptance criteria
- first-time user can run end-to-end sample workflow from docs only
- docs align with CLI behavior and current schemas

---

## C6 — Release and Versioning Framework

### Scope
Add product release discipline:
- semantic versioning
- changelog
- compatibility notes
- release verification checklist

### Acceptance criteria
- every release has deterministic checklist pass
- rollback procedure documented and tested

---

## Public Interfaces / Types

## 1) Product config schema
Includes runtime defaults, profile mappings, tool paths, workflow toggles.

## 2) Command output schema
Standardize machine-readable output for automation and orchestration wrappers.

## 3) Diagnostic schema
Structured health report with code/severity/fixability.

---

## Test Cases (Lane C)
1. Fresh install succeeds in global mode.
2. Fresh install succeeds in local project mode.
3. Update preserves user custom config where expected.
4. Uninstall removes installed artifacts and commands.
5. Health check catches missing dependencies and invalid config.
6. Health repair resolves all auto-fixable errors.
7. End-to-end smoke workflow from docs passes.

---

## Definition of Done (Lane C)
- Product is installable, updatable, and uninstallable with deterministic behavior.
- CLI workflow is stable and documented.
- Health/diagnostics and repair tooling are available.
- Release process is documented and reproducible.

---

## Explicit Assumptions
- Lane A and Lane B capabilities are implemented and validated first.
- Packaging and UX decisions can evolve after additional GSD usage testing.
