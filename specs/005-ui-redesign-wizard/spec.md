# Feature Specification: Guided Wizard Redesign

**Feature Branch**: `005-ui-redesign-wizard`

**Created**: 2026-06-21

**Status**: Draft

**Input**: User description: "Давай сделаем редизайн нашего приложения. 1. Используй shadcn-vue в стиле Mira, тема Indigo. 2. Там есть компонент, называется «Stepper» для wizard-ов. Используй его. 3. Пропиши в этом степере такие шаги: Account - Snapshot - Working copy - Deduplication - Triage - Submit. 4. Придумай другое название для working copy, мне оно не очень нравится. Что-то похожее, в одно слово. И, возможно, шаги, которые я расписал, ты для них придумаешь более подходящие названия, чтобы они были максимально простыми и понятными."

## Overview

The application already supports the full contact-cleanup pipeline — connect a Google account,
take a snapshot, work on an editable copy, deduplicate, triage, and export back to Google — but
each stage lives on a separate page with ad-hoc styling and version-control jargon ("working
copy", "deduplication", "triage"). This feature is a **visual and navigational redesign** that
unifies every stage into a single **guided wizard** driven by a persistent **step indicator
(stepper)**, applies one consistent design system with an indigo accent, and replaces internal
jargon with plain, everyday labels.

The wizard presents six ordered steps with renamed, simplified labels:

| # | New label | Plain meaning                         | Replaces (old term) |
|---|-----------|---------------------------------------|---------------------|
| 1 | Connect   | Link your Google account              | Account             |
| 2 | Backup    | Pull a frozen copy of your contacts   | Snapshot            |
| 3 | Draft     | Your editable copy of the contacts    | Working copy        |
| 4 | Merge     | Find & merge duplicates               | Deduplication       |
| 5 | Review    | Swipe to keep or delete               | Triage              |
| 6 | Export    | Push your changes back to Google      | Submit              |

This is a **redesign, not a behavior change**: every existing capability and every safety
guarantee (snapshots, staged/soft deletes, per-batch confirmation, undo, dry-run previews) is
preserved. No backend contracts, OAuth scopes, or destructive-action safeguards are altered.

## Clarifications

### Session 2026-06-21

- Q: How does the linear wizard handle an account that has multiple snapshots and multiple
  drafts? → A: Each step carries exactly one **active** selection that feeds the next step. The
  first three steps may hold many items: **Connect** — several accounts, one active; **Backup** —
  several backups, one active; **Draft** — several drafts, one active. The last three are single
  operations scoped to the active upstream artifact: one **Merge** per active Draft, one **Review**
  per active Merge, one **Export** per active Review. Stepper progress is derived along this chain
  of active selections.
- Q: How should a step that runs as a long background job (Backup pull, Merge dedup, Export) appear
  in the stepper while it executes? → A: A distinct "running / in-progress" state on the stepper
  (e.g. animated indigo indicator) while the job runs; the step flips to *completed* when the job
  finishes, and the operator may navigate to other available steps meanwhile.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Move through the cleanup as one guided flow (Priority: P1)

An operator wants to clean up a Google account from start to finish without having to learn the
app's internal page structure. They land in the app, see a single horizontal step indicator with
the six steps, and always know which step they are on, which are already done, and which is next.
Completing the work on the current step advances them to the next; they can step back to revisit
earlier work.

**Why this priority**: The unified, self-explanatory flow is the core value of the redesign. With
just this — a stepper that ties the existing screens into one ordered journey — a new operator can
complete a full cleanup without external guidance. This is the MVP.

**Independent Test**: Open the app with a fresh account and walk Connect → Backup → Draft → Merge
→ Review → Export. At every point the stepper shows the correct current/completed/upcoming states,
forward progress is only offered once the current step's prerequisite is satisfied, and the user
can navigate back to any completed step and return.

**Acceptance Scenarios**:

1. **Given** a freshly opened app, **When** the operator views any screen, **Then** a persistent
   stepper shows all six steps with exactly one marked "current" and the rest marked "completed"
   or "upcoming".
2. **Given** the operator has finished the work required on the current step, **When** they
   advance, **Then** the next step becomes current and the just-finished step is marked completed.
3. **Given** the operator is on a later step, **When** they select a completed earlier step, **Then**
   they are taken to that step with its prior state intact, and the stepper reflects the move.
4. **Given** the current step's prerequisite is not yet met (e.g., no backup exists yet), **When**
   the operator looks at later steps, **Then** those steps are visibly not-yet-available and cannot
   be activated.

---

### User Story 2 - Understand each step from its label alone (Priority: P2)

An operator who is not a developer wants every step and screen to use words they already
understand. They should not need to know what a "working copy", "deduplication", or "triage" is.

**Why this priority**: Clear language removes the main adoption barrier for non-technical
operators and is an explicit goal of the request. It depends on US1's structure but adds the
plain-language layer on top.

**Independent Test**: Show the six labels and screen headings to someone unfamiliar with the app
and confirm they can correctly state what each step does without help; verify the term "working
copy" appears nowhere in the user-facing UI and is replaced by "Draft".

**Acceptance Scenarios**:

1. **Given** any screen in the wizard, **When** the operator reads the step label and heading,
   **Then** it uses the simplified vocabulary (Connect, Backup, Draft, Merge, Review, Export) and
   not the old terms (Account, Snapshot, Working copy, Deduplication, Triage, Submit).
2. **Given** the "Draft" step, **When** the operator views it, **Then** the editable copy is
   referred to as a "Draft" everywhere it is named in the UI (labels, headings, buttons, empty
   states, confirmations).
3. **Given** any step label, **When** the operator hovers or focuses it, **Then** a short plain-
   language description of what that step does is available.

---

### User Story 3 - Experience one consistent, modern visual design (Priority: P3)

An operator wants every screen to look like part of the same polished product — consistent
spacing, typography, buttons, cards, and a single indigo accent color — instead of a set of
differently-styled pages.

**Why this priority**: A coherent visual language increases trust and reduces cognitive load, but
the flow (US1) and clarity (US2) deliver the functional value first; the unified styling is the
finishing layer.

**Independent Test**: Visit every screen and confirm shared UI elements (buttons, cards, badges,
form fields, the stepper) are visually consistent, use the indigo accent for primary actions and
the active step, and that no screen retains the previous ad-hoc styling.

**Acceptance Scenarios**:

1. **Given** any two screens in the wizard, **When** compared, **Then** shared components
   (buttons, inputs, cards, badges, dialogs) share the same visual styling and indigo accent.
2. **Given** the stepper, **When** displayed, **Then** the current step is emphasized with the
   indigo accent and completed/upcoming steps are visually distinct from it and from each other.
3. **Given** a primary action on any screen (e.g., confirm, continue, export), **When** rendered,
   **Then** it uses the consistent primary-action styling in the indigo theme.

---

### Edge Cases

- **Unmet prerequisite**: Operator tries to reach a later step before the earlier one produced
  what it needs (no account connected → no backup; no backup → no draft; etc.). Later steps stay
  not-available and the stepper communicates why.
- **Empty step**: A step legitimately has nothing to do (e.g., Merge finds zero duplicates, or
  Review has no contacts left to decide). The step still renders, shows a clear empty/"nothing to
  do here" state, and can be passed through.
- **Page refresh / return visit**: Operator reloads the browser mid-flow; the wizard restores the
  correct current step and the stepper state for the active account rather than resetting to step 1.
- **Switching the active selection**: Operator changes the active account (or active backup, or
  active draft); the stepper and current-step state re-derive to reflect that branch independently,
  without destroying the previously active branch's artifacts.
- **Destructive Export**: The redesign must not weaken the existing safeguards on Export — per-batch
  confirmation, dry-run preview, snapshot-before-delete, and undo remain mandatory and clearly
  surfaced within the redesigned Export step.
- **Undecided items at Export**: Existing warning that excludes undecided survivors must remain
  visible and understandable in the new design.
- **Narrow / small viewport**: The six-step stepper remains legible and usable on a small screen
  (e.g., collapses to a compact progress indicator) without losing the current-step information.
- **Reversibility of navigation**: Going back to an earlier completed step must not silently discard
  later work that is still valid.
- **Job running while navigating away**: Operator leaves a step whose background job (Backup, Merge,
  or Export) is still running; the stepper keeps showing that step's running state and reflects
  completion/failure when the job ends, even though the operator is viewing another step.

## Requirements *(mandatory)*

### Functional Requirements

**Wizard & navigation**

- **FR-001**: The application MUST present the contact-cleanup pipeline as a single guided wizard
  with a persistent step indicator (stepper) visible on every step.
- **FR-002**: The stepper MUST contain exactly six ordered steps, in this order: Connect, Backup,
  Draft, Merge, Review, Export.
- **FR-003**: At all times the stepper MUST indicate, for each step, whether it is completed,
  current, upcoming/not-yet-available, or (while that step's background job is executing) running,
  with exactly one step marked current.
- **FR-025**: While a step's background job (Backup pull, Merge dedup, or Export) is executing, the
  stepper MUST show that step in a distinct **running/in-progress** state, MUST transition it to
  completed when the job finishes successfully, and MUST allow the operator to navigate to other
  available steps while it runs.
- **FR-004**: The wizard MUST allow the operator to advance to the next step only when the current
  step's prerequisite has been satisfied.
- **FR-005**: The operator MUST be able to navigate back to any previously completed step and
  return, with that step's prior state preserved.
- **FR-006**: Steps whose prerequisites are not met MUST be presented as not-yet-available and MUST
  NOT be activatable until their prerequisite is satisfied.
- **FR-007**: The wizard MUST restore the operator's correct current step and stepper state on page
  reload and on return visits for the active account (rather than resetting to the first step).
- **FR-008**: The stepper and step state MUST reflect the active account, and MUST update when the
  active account changes.
- **FR-009**: A step that has no work to do MUST still render with a clear empty state and allow the
  operator to proceed.

**Active-selection model**

- **FR-021**: The Connect, Backup, and Draft steps MUST each let the operator create/maintain
  multiple items (Google accounts, backups, and drafts respectively) and designate exactly one as
  **active**; the active item is the sole input to the next step.
- **FR-022**: The Merge, Review, and Export steps MUST each be a single operation scoped to the
  active upstream artifact — one Merge per active Draft, one Review per active Merge, and one Export
  per active Review.
- **FR-023**: The stepper's completed/current state MUST be derived along the chain of active
  selections (active account → active backup → active draft → its merge → its review → its export);
  a step counts as completed only when its active artifact exists.
- **FR-024**: Changing an active selection at an earlier step MUST re-derive the displayed state of
  all later steps to reflect the newly active branch, and MUST NOT silently destroy the artifacts of
  the previously active branch.

**Terminology**

- **FR-010**: All user-facing labels, headings, buttons, empty states, and confirmations MUST use
  the simplified vocabulary — Connect, Backup, Draft, Merge, Review, Export — in place of the prior
  terms Account, Snapshot, Working copy, Deduplication, Triage, Submit.
- **FR-011**: The term "working copy" MUST NOT appear anywhere in the user-facing UI; the editable
  copy MUST be called "Draft" wherever it is named.
- **FR-012**: Each step MUST expose a short plain-language description of what it does, available on
  hover/focus or inline.

**Visual design**

- **FR-013**: The application MUST apply one consistent design system across every screen, such that
  shared UI elements (buttons, inputs, cards, badges, dialogs, the stepper) are visually uniform.
- **FR-014**: The design MUST use an indigo accent as the primary color, applied to primary actions
  and to the current step in the stepper.
- **FR-015**: No screen MUST retain the previous ad-hoc styling; every screen MUST be brought into
  the unified design system.
- **FR-016**: The stepper MUST remain legible and usable on small/narrow viewports without losing
  the current-step indication.

**User-experience principles — simple · clear · predictable**

- **FR-026**: *(Simple)* Each step MUST present a single, clearly-labeled primary action ("what to do
  next") in a consistent location, with any secondary actions visually subordinate; no step MUST
  force the operator to choose among multiple competing primary paths to proceed.
- **FR-027**: *(Predictable)* Equivalent interactions — advancing, going back, selecting the active
  item, confirming, and cancelling — MUST look and behave identically across all six steps, so a step
  the operator has not seen before behaves the way earlier steps trained them to expect.
- **FR-028**: *(Clear, no surprises)* Every state-changing or destructive action MUST be triggered
  only by an explicit, visibly-labeled control; required actions MUST NOT be hidden behind hover-only
  or otherwise non-obvious affordances. Where a gesture is used (e.g. the Review swipe surface), an
  equivalent labeled button MUST also be available.
- **FR-029**: *(Predictable feedback)* Every action MUST produce immediate, visible feedback —
  in-progress, success, or error — so the operator is never left guessing whether it worked or what
  happens next.

**Preservation of existing behavior & safety**

- **FR-017**: The redesign MUST preserve every existing capability of the pipeline; no
  user-reachable functionality may be removed by this feature.
- **FR-018**: The redesign MUST preserve all existing non-destructive safeguards on the Export step
  — dry-run preview, snapshot-before-delete, explicit per-batch confirmation, and undo — and keep
  them clearly visible.
- **FR-019**: The redesign MUST preserve the existing warning that undecided survivors are excluded
  from Export.
- **FR-020**: The redesign MUST NOT change backend contracts, OAuth scopes, or the underlying
  decision/data model; it is a presentation-and-navigation change only.

### Key Entities *(include if feature involves data)*

- **Wizard step**: One of the six ordered stages (Connect, Backup, Draft, Merge, Review, Export);
  has a label, a plain-language description, a prerequisite, and a display state (completed /
  current / upcoming-or-unavailable) for the active account.
- **Active-selection chain**: The single active item at each step that feeds the next — active
  account → active backup → active draft → its merge → its review → its export. Connect, Backup, and
  Draft may each hold multiple items with one marked active; Merge, Review, and Export are singular
  per the active upstream artifact.
- **Step progress (per active branch)**: Which steps are completed and which step is current,
  derived from existing pipeline state along the active-selection chain (whether an account is
  connected and active, an active backup/snapshot exists, an active draft exists, dedup has run on
  it, triage decisions exist for it, an export run exists for it). This is a presentation-level
  derivation, not a new persisted decision record.
- **Draft**: The renamed editable copy of the contacts (formerly "working copy") that the operator
  dedupes and triages before exporting. Same underlying concept and data as today — only the name
  changes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time operator can correctly identify which step they are on and what the next
  action is within 10 seconds of viewing any screen, without external help.
- **SC-002**: In usability testing, at least 90% of non-technical participants can correctly state
  what each of the six steps does from its label and description alone.
- **SC-003**: 100% of the pipeline's previously available capabilities remain reachable through the
  redesigned wizard (zero functionality regressions).
- **SC-004**: 100% of user-facing screens use the unified design system and indigo accent; zero
  screens retain the previous ad-hoc styling, and the term "working copy" appears on zero screens.
- **SC-005**: An operator can complete a full pass (Connect through Export) guided only by the
  stepper and on-screen labels, with no need to consult documentation.
- **SC-006**: All existing Export safeguards (preview, confirmation, snapshot, undo) remain present
  and are surfaced on the redesigned Export step in 100% of export attempts.
- **SC-007**: The stepper remains usable and the current step identifiable across viewport widths
  from small mobile to desktop.
- **SC-008**: At least 90% of first-time operators can identify the single primary "next" action on
  any step within 5 seconds (simplicity).
- **SC-009**: A walkthrough of all six steps finds zero inconsistencies in how equivalent
  interactions (advance, back, select-active, confirm, cancel) are presented and behave
  (predictability).
- **SC-010**: 100% of state-changing actions produce a visible outcome signal (in-progress, success,
  or error); none complete silently.

## Assumptions

- **Design system**: The unified design will be implemented with shadcn-vue components styled in the
  "Mira" visual style with the Indigo theme, using its Stepper component for the wizard indicator.
  These specific tool choices are recorded here as the intended implementation; the requirements
  above are written in user-facing terms so the spec remains verifiable independent of the library.
- **UX guiding principles & design process**: The interface is held to three principles — **simple**
  (one primary action per step, minimal choices), **clear** (plain language, always-visible state),
  and **predictable** (identical patterns across steps, no hidden actions, immediate feedback), as
  captured in FR-026–FR-029 and SC-008–SC-010. During implementation, the `frontend-design` skill
  MUST be applied to drive visual and interaction-design direction (typography, spacing, hierarchy,
  component intent) on top of the shadcn-vue / Mira / Indigo foundation, rather than relying on
  default templated styling.
- **Terminology decisions (confirmed with the operator)**: "Working copy" is renamed to **Draft**;
  the six steps use the simplified plain-verb labels Connect, Backup, Draft, Merge, Review, Export
  rather than the original Account, Snapshot, Working copy, Deduplication, Triage, Submit.
- **Scope is presentation + navigation only**: This feature re-skins and re-flows existing screens
  (Accounts, Snapshot(s), Working copies/dedup/triage, Export/Delete review/Processing) and does not
  add new pipeline capabilities, change backend APIs, or alter OAuth scopes.
- **Existing safety model is reused unchanged**: Snapshots, staged/soft deletes, per-batch
  confirmation, dry-run previews, and undo continue to come from the existing features (001–004) and
  are only re-presented, never weakened.
- **Single-operator, multi-account**: Consistent with the current deployment model — one operator
  managing one or more of their own Google accounts; step progress is tracked per active account.
- **Linear-with-backtracking flow**: Steps are completed roughly in order; the operator may revisit
  completed steps but cannot skip ahead past an unmet prerequisite. Free random-access jumping to
  arbitrary not-yet-reached steps is intentionally out of scope.
