# Implementation Plan: Guided Wizard Redesign

**Branch**: `005-ui-redesign-wizard` | **Date**: 2026-06-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-ui-redesign-wizard/spec.md`

## Summary

Re-skin and re-flow the existing contact-cleanup frontend into a single guided wizard driven by a
persistent **Stepper** (`Connect → Backup → Draft → Merge → Review → Export`), built on **shadcn-vue**
(Mira style, Indigo theme) layered onto the current Vue 3 + Vite + Pinia app. The wizard is a pure
**presentation + navigation** change: it derives step state from a chain of "active" selections over
the existing read endpoints, renames *working copy → Draft* and the other steps to plain verbs, and
adds a distinct **running** state for the three long background jobs (Backup, Merge, Export). No
backend, OAuth, or data-model changes; all existing safety flows (snapshot, staged delete, per-batch
confirm, dry-run, undo) are re-presented unchanged. The `frontend-design` skill drives visual and
interaction direction toward a simple / clear / predictable UI.

## Technical Context

**Language/Version**: TypeScript 5.6, Vue 3.5 (`<script setup>`)

**Primary Dependencies**: Vue Router 4, Pinia 2, Vite 5; **new** — Tailwind CSS v4 (`@tailwindcss/vite`),
shadcn-vue (reka-ui primitives, `class-variance-authority`, `clsx`, `tailwind-merge`, `tw-animate-css`),
Hugeicons (per Mira preset; lucide acceptable fallback)

**Storage**: N/A (frontend). Active-selection persistence uses the browser (localStorage) + route params;
no new server-side persistence.

**Testing**: Vitest + @vue/test-utils (jsdom), already configured

**Target Platform**: Modern evergreen browsers (desktop + small/mobile viewports)

**Project Type**: Web application — frontend-only change (existing FastAPI backend untouched)

**Performance Goals**: No regression; wizard transitions feel instant (<100ms perceived); existing
job-polling cadences (e.g. export poll 500ms) preserved

**Constraints**: Biome remains the **single** linter/formatter and MUST pass in CI (constitution
Technology Constraints); no competing linter/formatter introduced. `vue-tsc` build must stay green.

**Scale/Scope**: 1 operator, multi-account; ~9 existing pages + ~19 components restyled; 6 wizard steps;
1 new wizard shell + stepper + wizard store; the shadcn-vue `components/ui/**` set actually used.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment | Status |
|-----------|-----------|--------|
| I. Privacy & Data Protection | No new data surfaced; tokens still never rendered; no new scopes; same per-account isolation. | Pass |
| II. Non-Destructive by Default | Export step re-presents — never weakens — dry-run preview, snapshot-before-delete, explicit per-batch confirm, and undo (FR-018). Destructive action stays an explicit labeled control (FR-028). | Pass |
| III. Human-in-the-Loop | All keep/delete/merge/export decisions remain explicit user actions; no automation added. | Pass |
| IV. Test-First (NON-NEGOTIABLE) | TDD: failing Vitest specs for step-state derivation, active-selection chain, running-state, and terminology before implementation. | Pass (committed) |
| V. Auditability & Observability | No change to mutation/audit paths; UI only re-presents existing results. | Pass |
| Tech Constraints — Vue 3 + TS (Vite) | Stays within stack. Tailwind v4 + shadcn-vue are styling/component libraries inside the Vue frontend, **not** a new core technology (language/datastore/dedup engine), so no amendment required. | Pass |
| Tech Constraints — Biome only | Biome remains the sole linter/formatter; generated `components/ui/**` are formatted by Biome and the CI Biome gate stays authoritative. No ESLint/Prettier added. | Pass |

**Result**: No violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/005-ui-redesign-wizard/
├── plan.md              # This file
├── spec.md              # Feature spec (already written + clarified)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── wizard-stepper.md # Phase 1 — UI/state contract for the wizard + step-state derivation
└── checklists/
    └── requirements.md   # Spec quality checklist (passing)
```

### Source Code (repository root)

```text
frontend/
├── vite.config.ts                 # + @tailwindcss/vite plugin
├── components.json                # NEW — shadcn-vue config (style: mira, theme: indigo, base: reka)
├── biome.json                     # unchanged (stays the single formatter/linter)
├── tsconfig*.json                 # @ alias already present; align with shadcn expectations
├── src/
│   ├── style.css                  # NEW — `@import "tailwindcss"` + theme tokens (Indigo)
│   ├── main.ts                    # + import './style.css'
│   ├── lib/
│   │   └── utils.ts               # NEW — `cn()` helper (clsx + tailwind-merge)
│   ├── components/
│   │   ├── ui/                    # NEW — shadcn-vue generated components (stepper, button, card, dialog, badge, input, sonner/toast, …)
│   │   └── wizard/                # NEW — WizardLayout.vue, WizardStepper.vue, StepShell.vue, ActiveSelector.vue
│   ├── stores/
│   │   └── wizard.ts              # NEW — active-selection chain + derived step state (Pinia)
│   ├── pages/                     # RESTYLED into wizard steps (Connect/Backup/Draft/Merge/Review/Export)
│   ├── components/ (existing)     # RESTYLED to shadcn-vue primitives; "working copy" → "Draft" copy
│   ├── router/index.ts            # Re-mapped to wizard step routes (+ legacy redirects)
│   └── services/api.ts            # unchanged (existing endpoints already sufficient)
└── tests/ (src/**/*.spec.ts)      # NEW/UPDATED Vitest specs (wizard store, stepper states, terminology)
```

**Structure Decision**: Web application, **frontend-only**. The redesign adds a shadcn-vue/Tailwind v4
foundation and a thin wizard layer (`stores/wizard.ts` + `components/wizard/**`) over the existing
pages, then restyles pages/components in place. The backend (`services/api.ts` and all FastAPI routes)
is untouched — the wizard composes existing list/preview endpoints to derive progress.

## Phase 0 — Research

See [research.md](./research.md). All Technical-Context unknowns resolved: Mira is a shadcn-vue visual
style and Indigo a valid theme (preset `reka-mira` + Indigo); Stepper is a first-class component with a
`{ state }` slot extended for a custom *running* state; Tailwind v4 + `@tailwindcss/vite` is the
integration path; Biome stays the sole formatter; the wizard's six steps map onto existing endpoints.

## Phase 1 — Design & Contracts

- [data-model.md](./data-model.md) — Wizard step, active-selection chain, derived step-state machine
  (incl. the *running* state), and the exact mapping of each step to existing API state.
- [contracts/wizard-stepper.md](./contracts/wizard-stepper.md) — UI/state contract: stepper states,
  navigation/gating rules (FR-001…FR-009, FR-021…FR-025), and the read endpoints each step consumes.
- [quickstart.md](./quickstart.md) — runnable validation: install the foundation, run the wizard end to
  end, and verify the acceptance scenarios + safeguards.

## Complexity Tracking

No constitution violations — section intentionally empty.
