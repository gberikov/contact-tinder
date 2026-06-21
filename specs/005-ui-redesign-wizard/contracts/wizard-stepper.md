# UI / State Contract: Wizard Stepper

This feature exposes **no new HTTP API**. The "contract" here is the **UI/state contract** the wizard
must satisfy — the observable behavior tested in `tasks.md`. It references existing endpoints only
(see `data-model.md` for the full mapping); the OpenAPI surface is unchanged.

## A. Stepper rendering contract (FR-001…FR-003, FR-016)

- The stepper is **persistent** on every wizard route and contains exactly six items in order:
  `Connect, Backup, Draft, Merge, Review, Export` (FR-002).
- Each item renders: an indicator, the plain-verb **title**, and a plain-language **description**
  (FR-012).
- At all times exactly **one** item has `displayState === 'current'`; the rest are `completed`,
  `upcoming`, or `running` (FR-003).
- The **current** step and completed steps use the **Indigo** primary accent; upcoming steps are
  visually muted (FR-014).
- On narrow viewports the stepper stays usable and the current step identifiable (e.g. compact
  "Step N of 6 — <label>" form) (FR-016).

State → visual:

| `displayState` | Indicator | Trigger (button) |
|----------------|-----------|------------------|
| `completed` | check glyph, indigo | enabled (navigates back) |
| `current` | step number, indigo ring | enabled |
| `running` | spinner, indigo (animated) | enabled (may navigate away; job continues) |
| `upcoming` | step number, muted | **disabled** (not activatable) |

## B. Navigation & gating contract (FR-004…FR-009, FR-021…FR-024)

1. **Advance**: the primary "Continue" action and the next stepper item are enabled **only** when the
   current step's completion predicate is true (FR-004). Otherwise the next item is `upcoming` +
   disabled (FR-006).
2. **Back**: selecting any `completed` step navigates to it with its prior state intact (FR-005).
3. **Active selection** (Connect/Backup/Draft): each lets the operator create/maintain multiple items
   and mark exactly one **active**; the active item is the sole input to the next step (FR-021).
4. **Singular ops** (Merge/Review/Export): one operation scoped to the active upstream artifact
   (FR-022).
5. **Re-derive**: changing an upstream active selection re-derives all later steps' displayed state and
   never destroys the previous branch's artifacts (FR-024).
6. **Empty step**: a step with nothing to do still renders a clear empty state and can be passed
   (FR-009).
7. **Restore**: on reload/return, the wizard rehydrates the active chain and lands on the correct
   current step (FR-007).

## C. Running-state contract (FR-025, FR-029)

- While the active **Backup** import job, **Merge** dedup run, or **Export** run reports `running`,
  that step shows the `running` indicator (B above).
- The operator MAY navigate to other available steps while it runs; the stepper keeps showing the
  running state and transitions to `completed` (or back to `current` with a visible error on failure)
  when the job ends (FR-025, FR-029).
- Polling reuses existing store behavior (e.g. `useExportStore.pollUntilDone`); no new endpoint.

## D. Preserved safety contract (FR-017…FR-019, FR-028)

The **Export** step MUST continue to surface, unchanged in behavior:
- a **dry-run preview** (`previewExport` → delete/label/undecided counts, `nothingToExport`);
- the **undecided-survivors warning** (FR-019);
- an explicit, labeled **confirm-delete** control (`confirmExportDelete`) — never a hover/implicit
  trigger (FR-028) — with the existing `write_scope_required` re-consent path;
- **undo** for delete and label (`undoExportDelete`, `undoExportLabel`).

The **Review** step's swipe surface MUST also expose equivalent labeled keep/delete/process buttons
(FR-028) — already present as `SwipeControls`.

## E. Endpoints consumed (existing, unchanged)

`listAccounts`, `connect`, `grantWriteAccess`, `createSnapshot`, `listSnapshots`, `getImportJob`,
`createWorkingCopy`, `listWorkingCopies`, `startDedupRun`, `listDedupRuns`, `getDedupRun`,
`listClusters`, `mergePreview`, `mergeCluster`, `openTriageSession`, `listTriageSessions`,
`getTriageSession`, `getDeck`, `setDecision`, `previewExport`, `startExport`, `getExportRun`,
`confirmExportDelete`, `undoExportDelete`, `undoExportLabel` (+ the remaining triage/processing calls).

No endpoint is added, removed, or changed (FR-020).
