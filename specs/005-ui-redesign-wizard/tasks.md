---
description: "Task list for 005-ui-redesign-wizard"
---

# Tasks: Guided Wizard Redesign

**Input**: Design documents from `specs/005-ui-redesign-wizard/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/wizard-stepper.md, quickstart.md

**Tests**: Included. Constitution Principle IV (Test-First, NON-NEGOTIABLE) requires failing tests
before implementation for behavior with correctness/safety implications — here the wizard step-state
derivation, active-selection chain, running-state, gating, and terminology. Vitest specs live in
`frontend/tests/`.

**Scope reminder**: Frontend-only. No backend, OAuth, or data-model changes. All paths below are under
`frontend/`. Existing endpoints in `frontend/src/services/api.ts` are consumed unchanged.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 / US3 (maps to spec.md user stories)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Stand up the Tailwind v4 + shadcn-vue (Mira / Indigo) foundation in the existing Vite app.

- [X] T001 Add Tailwind v4: `npm install tailwindcss @tailwindcss/vite` and register the `tailwindcss()` plugin in `frontend/vite.config.ts` (keep existing vue() plugin, `@` alias, and `/api` proxy).
- [X] T002 Create `frontend/src/style.css` with `@import "tailwindcss";` plus the Indigo `@theme inline` CSS variable tokens (`--primary` etc.), and import it from `frontend/src/main.ts`.
- [X] T003 Run shadcn-vue init (base `reka`, style `mira`, theme `indigo`) producing `frontend/components.json` and `frontend/src/lib/utils.ts` (`cn()` helper); align `frontend/tsconfig.json` / `tsconfig.app.json` path alias if needed.
- [X] T004 Add the shadcn-vue components used by the redesign: `npx shadcn-vue@latest add stepper button card dialog badge input label separator skeleton tooltip sonner` → populates `frontend/src/components/ui/**`.
- [X] T005 [P] Format generated `frontend/src/components/ui/**` with Biome and confirm `npm run lint` (`biome ci .`) passes; add a minimal scoped `biome.json` override ONLY if a generated file genuinely conflicts (no second formatter).
- [X] T006 [P] Confirm baseline still builds: `npm run build` (`vue-tsc -b && vite build`) green with the new foundation before any wizard work.

**Checkpoint**: shadcn-vue/Tailwind foundation installed; lint + build green.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Wizard shell, step definitions, routing, and store skeleton that every step renders inside.

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete.

- [X] T007 Create static step definitions (key, index, label, description, route `/wizard/<key>`, `prerequisiteKey`, `isLongJob`) for the 6 steps in `frontend/src/wizard/steps.ts` per data-model.md.
- [X] T008 Create the wizard Pinia store skeleton in `frontend/src/stores/wizard.ts`: active-selection chain state (`accountId`/`snapshotId`/`workingCopyId`), localStorage key `wizard.activeChain`, and empty getters/actions to be filled in US1.
- [X] T009 Restructure `frontend/src/router/index.ts` to `/wizard/:step` routes mapping each step to its page component, with legacy-path redirects (`/snapshots`, `/working-copies`, `/accounts`, … → matching wizard step) and `/` → first incomplete step.
- [X] T010 Create `frontend/src/components/wizard/WizardLayout.vue` (renders the persistent stepper + `<RouterView/>` for the active step) and `frontend/src/components/wizard/WizardStepper.vue` placeholder shell using `@/components/ui/stepper`.
- [X] T011 Update `frontend/src/App.vue` to render `WizardLayout` (remove the old `<header>/<nav>` and ad-hoc `<style>`; keep the app mount point).

**Checkpoint**: Wizard shell renders all six existing pages inside the stepper route skeleton.

---

## Phase 3: User Story 1 — Guided wizard flow (Priority: P1) 🎯 MVP

**Goal**: One guided flow with a persistent stepper showing completed/current/upcoming/running states, prerequisite gating, back-navigation, the active-selection chain, and reload restore.

**Independent Test**: Walk Connect → Backup → Draft → Merge → Review → Export; stepper states are correct, later steps gate on prerequisites, switching an active selection re-derives downstream without data loss, long jobs show a running state, and a browser reload restores the current step (quickstart steps 1, 3–7, 11–12).

### Tests for User Story 1 (write FIRST — must FAIL) ⚠️

- [X] T012 [P] [US1] Spec for step-state derivation (completed/current/upcoming) from the active chain over mocked `api`, including the `emptyButPassable` case — a step with no work to do is still derivable as passable (FR-009) — in `frontend/tests/wizard-derivation.spec.ts`.
- [X] T013 [P] [US1] Spec for gating + navigation: exactly one `current`, upcoming steps disabled (FR-006), back-nav to completed steps preserves state (FR-005) in `frontend/tests/wizard-stepper.spec.ts`.
- [X] T014 [P] [US1] Spec for the running state: backup import / merge run / export run `running` → step `running` → `completed`, and `failed` → `current` with error (FR-025/029) in `frontend/tests/wizard-running.spec.ts`.
- [X] T015 [P] [US1] Spec for active-selection chain + persistence: switching active account/snapshot/draft re-derives downstream (FR-024) and rehydrates from localStorage on reload (FR-007); MUST explicitly assert that after switching, the previously active branch's artifacts (its snapshot/draft/merge/review/export) remain intact — i.e. switching back re-shows the prior branch's completed state unchanged — in `frontend/tests/wizard-active-chain.spec.ts`.

### Implementation for User Story 1

- [X] T016 [US1] Implement step-state derivation getters in `frontend/src/stores/wizard.ts` mapping each step to existing endpoints (`listAccounts`, `listSnapshots`+`getImportJob`, `listWorkingCopies`, `listDedupRuns`+`getDedupRun`, `listTriageSessions`+`getTriageSession`, `previewExport`+`getExportRun`) per data-model.md. Note: `api.listSnapshots()` and `api.listWorkingCopies()` take no args — filter by `accountId` / `snapshotId` **client-side** over the unfiltered lists (no endpoint change, FR-020).
- [X] T017 [US1] Implement active-selection setters + downstream re-derivation + localStorage persist/rehydrate in `frontend/src/stores/wizard.ts` (depends on T016).
- [X] T018 [US1] Build `frontend/src/components/wizard/WizardStepper.vue`: render all 6 steps with title/description, Indigo accent on current+completed, disabled triggers for `upcoming`, click-to-go-back for `completed` (FR-001–006, 014).
- [X] T019 [US1] Add the running-state indicator (spinner + `data-running`) to the active step in `WizardStepper.vue`, wired to job statuses and safe to leave running while navigating away (FR-025).
- [X] T020 [US1] Add prerequisite route guards + current-step restore in `frontend/src/components/wizard/WizardLayout.vue` / router (block `upcoming`, land on correct step on load) (FR-004/006/007).
- [X] T021 [US1] Create `frontend/src/components/wizard/ActiveSelector.vue` (list multiple items + create + mark exactly one active) and wire it into the Connect, Backup, and Draft step pages (FR-021).
- [X] T022 [US1] Make the stepper responsive: compact "Step N of 6 — <label>" presentation on narrow viewports without losing current-step identity (FR-016/SC-007).

**Checkpoint**: MVP — the guided wizard is fully navigable and state-correct over the existing (not-yet-restyled) pages. T012–T015 pass.

---

## Phase 4: User Story 2 — Plain-language terminology (Priority: P2)

**Goal**: Every label/heading/button/empty-state uses the simplified vocabulary; "working copy" is gone, replaced by "Draft", with per-step plain-language descriptions.

**Independent Test**: Read all six labels + descriptions and every screen heading; confirm the new vocabulary and that "working copy" appears nowhere (quickstart step 2).

### Tests for User Story 2 (write FIRST — must FAIL) ⚠️

- [X] T023 [P] [US2] Spec asserting stepper labels are exactly Connect/Backup/Draft/Merge/Review/Export, each has a description, and the string "working copy" is absent from rendered wizard output in `frontend/tests/wizard-terminology.spec.ts`.

### Implementation for User Story 2

- [X] T024 [US2] Finalize plain-verb labels + plain-language descriptions in `frontend/src/wizard/steps.ts` (FR-010/012).
- [X] T025 [P] [US2] Rename "working copy" → "Draft" in the Draft step page `frontend/src/pages/WorkingCopies.vue` (labels, headings, buttons, empty states) (FR-011).
- [X] T026 [P] [US2] Sweep remaining old terms (Account→Connect, Snapshot→Backup, Deduplication→Merge, Triage→Review, Submit→Export; working copy→Draft) across `frontend/src/pages/**` and `frontend/src/components/**` user-facing strings (FR-010).
- [X] T027 [US2] Verify confirmations/dialogs/toasts copy uses the new vocabulary across steps (FR-010).

**Checkpoint**: US1 + US2 — guided flow with fully plain-language copy. T023 passes.

---

## Phase 5: User Story 3 — Consistent visual design + UX principles (Priority: P3)

**Goal**: Every screen uses the unified Mira/Indigo shadcn-vue system with one primary action per step, identical interaction patterns, and visible feedback (simple · clear · predictable).

**Independent Test**: Visit every screen; shared components are visually uniform with the Indigo accent, each step has a single clear primary action, equivalent interactions behave identically, and no screen retains old ad-hoc styling (quickstart steps 8–10, section 4).

### Tests for User Story 3 (write FIRST — must FAIL) ⚠️

- [X] T028 [P] [US3] Smoke spec asserting each step page renders a single primary action via the shadcn `Button` and uses `@/components/ui` primitives (no legacy raw `<table>`/inline-styled blocks) in `frontend/tests/wizard-consistency.spec.ts`.

### Implementation for User Story 3 (restyle — parallel, different files)

- [X] T029 [P] [US3] Restyle Connect — `frontend/src/pages/Accounts.vue` (shadcn Card/Button/Badge; single primary action).
- [X] T030 [P] [US3] Restyle Backup — `frontend/src/pages/Snapshots.vue` and `frontend/src/pages/Snapshot.vue`.
- [X] T031 [P] [US3] Restyle Draft — `frontend/src/pages/WorkingCopies.vue`.
- [X] T032 [P] [US3] Restyle Merge — `frontend/src/pages/WorkingCopyDedup.vue` + `frontend/src/components/{ClusterList,ClusterCard,MergePreview,DedupRunPanel,ConfidenceBadge}.vue`.
- [X] T033 [P] [US3] Restyle Review — `frontend/src/pages/WorkingCopyTriage.vue` + `frontend/src/pages/Processing.vue` + `frontend/src/components/{SwipeDeck,SwipeControls,ProcessingQueue,TransliterationReview,EditCardForm,CompletionSummary}.vue` (swipe surface keeps labeled keep/delete/process buttons — FR-028). Note: `ContactCard.vue` is restyled in T035, not here, to avoid a parallel-edit conflict.
- [X] T034 [P] [US3] Restyle Export — `frontend/src/pages/Export.vue` + `frontend/src/pages/DeleteReview.vue` + `frontend/src/components/{ExportPreview,ExportReport,UndecidedWarning,DeleteBatchReview,LabelPreview}.vue` (keep dry-run preview, undecided warning, explicit labeled confirm, undo — FR-018/019/028).
- [X] T035 [P] [US3] Restyle shared `frontend/src/components/ContactTable.vue` and `frontend/src/components/ContactCard.vue` to shadcn Table/Card primitives.
- [X] T036 [US3] Apply the `frontend-design` skill pass on the wizard shell + tokens (typography scale, spacing rhythm, hierarchy) in `frontend/src/style.css` + `frontend/src/components/wizard/**` (FR-013/SC-004).
- [X] T037 [US3] Add visible feedback for every state-changing action via `sonner` toasts + inline in-progress/success/error states across step pages (FR-029/SC-010).
- [X] T038 [US3] Predictability sweep: make advance/back/select-active/confirm/cancel controls look and behave identically across all six step pages (FR-026/027/SC-008/009).

**Checkpoint**: All three stories independently functional; whole app on the unified system.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T039 [P] Remove dead legacy nav/styles and obsolete routes from `frontend/src/App.vue` and `frontend/src/router/index.ts`; ensure only wizard routes + redirects remain.
- [X] T040 Update existing page specs in `frontend/tests/` (e.g. `dedup.test.ts`, `triage-swipe.test.ts`, `Export.*.spec.ts`, `delete-review.test.ts`, `processing-queue.test.ts`) for renamed copy/markup so the suite stays green.
- [X] T041 [P] Run the full quality gate: `npm run lint` + `npm run build` + `npm run test` — all green (constitution Biome gate + TDD).
- [ ] T042 Execute the `quickstart.md` validation walkthrough (steps 1–12 + UX-principle checks) and confirm every row passes.
- [X] T043 [P] Add a short note to `frontend/README` (or repo docs) describing the wizard flow and the shadcn-vue/Mira/Indigo foundation.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately. T001→T002→T003→T004 are sequential (shared config / CLI order); T005, T006 follow.
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all user stories. T007–T011 are mostly sequential (shared files: router, App.vue, store).
- **User Stories (Phase 3–5)**: all depend on Foundational. Recommended priority order P1 → P2 → P3; US2 and US3 can overlap once US1's store/stepper exist.
- **Polish (Phase 6)**: after the desired stories are complete.

### User Story Dependencies

- **US1 (P1)**: after Foundational — no dependency on US2/US3. Delivers the working guided flow (MVP).
- **US2 (P2)**: after Foundational; lightly builds on US1's `steps.ts`/stepper but is independently testable (terminology).
- **US3 (P3)**: after Foundational; restyles screens independently. Best after US1 so the shell is stable; does not require US2.

### Within Each User Story

- Tests (T012–T015, T023, T028) written and FAILING before implementation.
- Store derivation (T016) before setters/persistence (T017) before stepper UI (T018–T020).

### Parallel Opportunities

- T005, T006 in Setup.
- US1 tests T012–T015 together.
- US3 restyle tasks T029–T035 in parallel (different files); T036–T038 after the screens exist.
- Polish T039, T041, T043 in parallel.

---

## Parallel Example: User Story 3 restyle

```bash
# After Foundational + US1, launch the screen restyles together (different files):
Task: "Restyle Connect — frontend/src/pages/Accounts.vue"
Task: "Restyle Backup — frontend/src/pages/Snapshots.vue + Snapshot.vue"
Task: "Restyle Draft — frontend/src/pages/WorkingCopies.vue"
Task: "Restyle Merge — frontend/src/pages/WorkingCopyDedup.vue + cluster/merge components"
Task: "Restyle Review — triage + processing pages/components"
Task: "Restyle Export — Export.vue + DeleteReview.vue + export components"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1.
4. **STOP and VALIDATE**: the guided wizard navigates with correct states over the existing pages.
5. Demo the MVP (flow works even before the restyle/terminology sweep).

### Incremental Delivery

1. Setup + Foundational → shell ready.
2. US1 → guided flow (MVP) → demo.
3. US2 → plain-language copy → demo.
4. US3 → unified Mira/Indigo visual system + UX principles → demo.
5. Polish → gates green + quickstart validated.

---

## Notes

- [P] = different files, no incomplete-task dependency.
- TDD: verify each spec fails before implementing (constitution Principle IV).
- Biome stays the single linter/formatter; CI `biome ci .` must pass on generated `components/ui/**`.
- No backend/OAuth/data-model changes — if a task seems to need one, stop: it's out of scope (FR-020).
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
