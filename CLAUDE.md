<!-- SPECKIT START -->
## Active feature: 005-ui-redesign-wizard

Read the current implementation plan for technologies, structure, and constraints:
`specs/005-ui-redesign-wizard/plan.md`

Supporting design artifacts:
- Spec: `specs/005-ui-redesign-wizard/spec.md`
- Research: `specs/005-ui-redesign-wizard/research.md`
- Data model: `specs/005-ui-redesign-wizard/data-model.md`
- UI/state contract: `specs/005-ui-redesign-wizard/contracts/wizard-stepper.md`
- Quickstart: `specs/005-ui-redesign-wizard/quickstart.md`

Builds on features 001–004 (snapshots/working copies, Zingg dedup, swipe triage, Google export).

Stack: Python 3.12 / FastAPI + worker · PostgreSQL · Vue 3 + TS (Vite) · Biome. Feature 005 is a
**frontend-only redesign** that wraps the existing pipeline in one guided wizard driven by a
persistent **Stepper** (`Connect → Backup → Draft → Merge → Review → Export`), built with
**shadcn-vue** (Mira style, Indigo theme, Tailwind v4 via `@tailwindcss/vite`) and reka-ui. It is a
**presentation + navigation** change only: NO backend, OAuth, or data-model changes. Step state is
derived client-side along a **chain of active selections** (active account → backup → draft → its
merge → review → export) over existing read endpoints in `services/api.ts`; the chain persists in
localStorage + route (`/wizard/:step`) so reload restores the current step. Renames *working copy →
**Draft*** and uses plain-verb labels. Adds a distinct **running** state for the three long jobs
(Backup import, Merge dedup, Export run). All existing safety flows (snapshot, staged delete,
per-batch confirm, dry-run, undo, undecided warning) are re-presented **unchanged**. UX bar:
simple · clear · predictable (FR-026–029 / SC-008–010), applying the `frontend-design` skill.
**Biome stays the single linter/formatter** (constitution); generated `components/ui/**` are
Biome-formatted and the CI Biome gate stays authoritative. Governing principles:
`.specify/memory/constitution.md` (privacy, non-destructive, human-in-loop, test-first, auditability).
<!-- SPECKIT END -->
