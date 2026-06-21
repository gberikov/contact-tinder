# Phase 1 Data Model: Guided Wizard Redesign

This feature introduces **no new persisted entities**. The model below is a **client-side,
presentation-level** structure (Pinia store `stores/wizard.ts`) derived from existing API data. No
backend schema, migration, or contract changes.

## Entities (client-side)

### WizardStep (static definition)

One of the six ordered steps. Static config, not persisted.

| Field | Type | Notes |
|-------|------|-------|
| `key` | `'connect' \| 'backup' \| 'draft' \| 'merge' \| 'review' \| 'export'` | Stable id |
| `index` | `1..6` | Order in the stepper |
| `label` | string | Plain-verb label (Connect, Backup, Draft, Merge, Review, Export) — FR-010 |
| `description` | string | Short plain-language hint shown in `StepperDescription` — FR-012 |
| `route` | string | `/wizard/<key>` |
| `prerequisiteKey` | step key \| null | Previous step that must be completed to enter — FR-004/FR-006 |
| `isLongJob` | boolean | true for `backup`, `merge`, `export` (can enter the *running* state) — FR-025 |

### ActiveSelectionChain (per browser, persisted in localStorage)

The single active item feeding each subsequent step (FR-021/FR-022). Only the first three carry a
selectable id; the last three are singular per the active upstream artifact.

| Field | Type | Source / meaning |
|-------|------|------------------|
| `accountId` | string \| null | active Google account (Connect) |
| `snapshotId` | string \| null | active backup (Backup) |
| `workingCopyId` | string \| null | active draft (Draft) |
| (merge) | derived | the one DedupRun of the active draft |
| (review) | derived | the one TriageSession of the active draft |
| (export) | derived | the one ExportRun of the active draft |

Persistence: `localStorage["wizard.activeChain"]`. Rehydrated on load; the current route step is
restored from `/wizard/:step` (FR-007).

### DerivedStepState (computed, never stored)

Per step, computed from the active chain + existing endpoints.

| Field | Type | Notes |
|-------|------|-------|
| `displayState` | `'completed' \| 'current' \| 'upcoming' \| 'running'` | Exactly one step is `current` (FR-003) |
| `available` | boolean | false until prerequisite completed (FR-006) |
| `emptyButPassable` | boolean | step has nothing to do but can be passed (FR-009) |

## Step → existing-state derivation (authoritative mapping)

No new endpoints; all from `frontend/src/services/api.ts`.

| Step | Active artifact | Existing API used | `completed` predicate | `running` predicate |
|------|-----------------|-------------------|------------------------|---------------------|
| Connect | `Account` | `listAccounts()` | active `account.status === 'connected'` | — |
| Backup | `Snapshot` | `listSnapshots()` (filter `accountId`), `getImportJob(id)` | active `snapshot.status === 'complete'` | `importJob.status === 'running'` or `snapshot.status === 'importing'` |
| Draft | `WorkingCopy` | `listWorkingCopies()` (filter `snapshotId`) | active working copy exists | — |
| Merge | `DedupRun` | `listDedupRuns(workingCopyId)`, `getDedupRun(id)` | latest run `status === 'completed'` | run `status === 'running'` |
| Review | `TriageSession` | `listTriageSessions(workingCopyId)`, `getTriageSession(id)` | session `status === 'complete'` | — (interactive, not a batch job) |
| Export | `ExportRun` | `previewExport(workingCopyId)`, `startExport()`, `getExportRun(id)` | run `status === 'completed'` | run `status === 'running'` |

Notes:
- "Active account" is a client selection over the existing multi-account list; switching it re-derives
  all downstream steps (FR-008/FR-024) without destroying the prior branch's artifacts.
- Backup/Merge/Export expose existing job/run statuses already polled by the current stores
  (`export.ts` polls to terminal state); the wizard reuses these for the *running* state.

## Step-state machine

```
upcoming ──(prerequisite completed)──▶ current
current  ──(start long job)──────────▶ running        [backup | merge | export only]
running  ──(job status === completed)▶ completed
running  ──(job status === failed)───▶ current (with error surfaced)   [FR-029]
current  ──(active artifact exists)──▶ completed
completed ──(navigate back / select)─▶ current        [FR-005, prior state preserved]
any upstream active selection change ─▶ re-derive all downstream [FR-024]
```

Invariants:
- Exactly one step is `current` at any time (FR-003).
- A step is `available` only if its `prerequisiteKey` step is `completed` (FR-004/FR-006).
- Changing an upstream active selection never deletes downstream artifacts; it only re-derives the
  displayed state (FR-024).

## Terminology mapping (UI copy only — FR-010/FR-011)

| Old (internal / current UI) | New (user-facing) |
|------------------------------|-------------------|
| Account / Accounts | Connect |
| Snapshot | Backup |
| Working copy | **Draft** |
| Deduplication / Dedup | Merge |
| Triage / Swipe | Review |
| Submit / Export to Google | Export |

Underlying API types (`Snapshot`, `WorkingCopy`, `DedupRun`, …) keep their names; only displayed
strings change.
