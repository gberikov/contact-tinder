# Addendum Spec: Deletions in Connect/Backup/Draft + Passable Review

**Parent feature**: `005-ui-redesign-wizard`

**Branch**: `feature/005-redesign`

**Created**: 2026-06-21

**Status**: Draft (approved design, pending spec review)

**Input**: User description: "Теперь давай добавим возможность удаления аккаунтов в коннекте,
снэпшотов в Backup, драфтов. Плюс давай добавим возможность продолжить в ревью даже если мы не
сделали триаж."

## Overview

Feature 005 turned the contact-cleanup pipeline into one guided wizard
(`Connect → Backup → Draft → Merge → Review → Export`). This addendum adds two capabilities that
operators need while using that wizard:

1. **Destructive cleanup of the active-selection chain** — delete a connected account in **Connect**,
   a backup in **Backup**, and a draft in **Draft**. Deletion is **cascading**: removing a parent
   also removes everything derived from it, and the operator is **warned about the cascade** before
   confirming.
2. **A passable Review step** — let the operator advance from **Review** to **Export** even when the
   triage swipe-through is not finished (or never started). Export's existing undecided-contacts
   warning remains the safety net.

### Deviation from "frontend-only"

Feature 005 was scoped as a frontend-only redesign. **This addendum knowingly extends the backend**
because the wizard exposed a gap: there is no way to delete a draft (working copy). Account and
backup deletion endpoints already exist; draft deletion does not. The user approved adding the
backend support. The parent `plan.md`/`CLAUDE.md` "NO backend changes" note is superseded for this
addendum and must be annotated accordingly.

## Clarifications

### Session 2026-06-21

- Q: Draft deletion needs a backend endpoint that does not exist (`DELETE /working-copies/{id}`).
  Add it, skip drafts, or UI-only stub? → A: **Add the backend endpoint.**
- Q: How to behave when deleting an account/backup that still has children (backups/drafts), given
  the backend currently blocks it (FK `RESTRICT`)? → A: **Cascade-delete everything, but warn the
  operator first.**
- Q: When may the operator continue Review → Export without finishing triage? → A: **Always** —
  Continue is enabled on Review regardless of triage progress.
- Q: How is a destructive deletion confirmed (no dialog component exists yet)? → A: **Add a
  shadcn-vue AlertDialog** and use it for all three deletions.

## Design Decisions & Rationale

### Cascade is implemented in the service layer, not via a schema migration

Backend tests run on in-memory **SQLite without `PRAGMA foreign_keys`**, so database-level FK
cascades do not fire in tests; the existing "delete children first" rule for snapshots is enforced
by a **service-level guard**, not the database. Therefore this addendum implements the cascade as an
**explicit, ordered delete in the service layer** rather than changing FK `ondelete` from `RESTRICT`
to `CASCADE`. Consequences:

- No Alembic migration is required; the schema is unchanged.
- The existing `RESTRICT` constraints remain as a safety backstop — because the service deletes
  children first, a `RESTRICT` parent delete never fires in normal flow, and a bug that skips a child
  surfaces loudly as an integrity error instead of silently orphaning rows.
- Behavior is identical on SQLite (tests) and PostgreSQL (prod).

### Safe deletion order (children before parents)

`account → snapshot → working_copy → (dedup | triage | export | contacts)`.

Cascade is composed one direction only to avoid circular service imports:
`account_service` → `snapshot_service` → `working_copy_service`. `working_copy_service` imports none
of the others.

## Requirements

### Backend

- **FR-A1** `working_copy_service.delete_working_copy(session, working_copy_id, *, confirm: bool)`:
  - 404 (`NotFoundError`) if the working copy does not exist.
  - 400 (`ConflictError`, code `confirmation_required`) if `confirm` is falsy — mirroring
    `delete_snapshot`.
  - Explicitly delete, in FK-safe order, every row derived from the working copy: export runs and
    their delete/label batches & deletion records; triage sessions, decisions, processing items,
    staged edits, delete batches & deletion records; dedup runs, clusters, cluster members & merge
    records; then `working_copy_contact` rows; then the `working_copy`. (`working_copy_contact`
    already ORM-cascades via the `contacts` relationship; the dedup/triage/export tables do not and
    must be deleted explicitly.)
  - Record an audit entry `working_copy.deleted` (mirroring `snapshot.deleted`) with the draft label
    and contact count before deletion.
  - Commit.
- **FR-A2** Router: `DELETE /api/working-copies/{working_copy_id}?confirm=true` → `204`.
- **FR-A3** `snapshot_service.delete_snapshot` no longer refuses when working copies exist. Instead it
  first deletes each child working copy via `working_copy_service.delete_working_copy(..., confirm=True)`,
  then deletes the snapshot (its `contacts`/`import_job` ORM-cascade). The `confirm` guard on the
  snapshot itself is unchanged.
- **FR-A4** Account deletion cascades: `account_service` deletes each of the account's snapshots
  (via `snapshot_service.delete_snapshot(..., confirm=True)`) before deleting the account. The route
  `DELETE /api/accounts/{id}` → `204` is unchanged in shape.
- **FR-A5** All cascade deletes are auditable: each level records its existing audit action
  (`snapshot.deleted`, `working_copy.deleted`).

### Frontend

- **FR-A6** `api.ts` gains `deleteWorkingCopy(id)` → `DELETE /working-copies/{id}?confirm=true`.
  `disconnect` (accounts) and `deleteSnapshot` already exist and are reused.
- **FR-A7** A reusable shadcn-vue **AlertDialog** is added under `components/ui/alert-dialog/`
  (Biome-formatted, consistent with other generated `components/ui/**`). A `ConfirmDeleteDialog`
  wrapper presents: the item being deleted, a **cascade warning with counts** ("This also deletes
  N backups and M drafts"), and "Cancel" / "Delete" actions. Counts are derived client-side from the
  already-loaded `snapshots` and `workingCopies` collections — no new endpoints.
- **FR-A8** `ActiveSelector` gains an optional per-item delete affordance (trash icon) that emits a
  `delete` event. **Connect**, **Backup**, and **Draft** steps wire it to open `ConfirmDeleteDialog`
  and call the corresponding API.
- **FR-A9** After a successful delete, the active-selection chain is repaired: if the deleted item —
  or any ancestor of the current active selection — was active, the corresponding entries in
  `activeAccountId` / `snapshotByAccount` / `workingCopyBySnapshot` are cleared and persisted, then
  `wizard.hydrate()` refreshes all collections.
- **FR-A10** Deletion errors (e.g. backend conflict) surface inline on the step, reusing each step's
  existing `error` display.

### Review gate

- **FR-A11** The operator can always continue from **Review** to **Export**, regardless of whether a
  triage session exists or is complete. Concretely, `Review` is treated as **passable** in the
  wizard store so `WizardLayout`'s `canContinue` is true on Review, and `available('export')` no
  longer requires Review to be `completed`.
- **FR-A12** Review's *completed* state (triage session `complete`) is unchanged — the stepper still
  shows a checkmark only when triage actually finished; "passable" only governs forward navigation.
- **FR-A13** Export's existing undecided-contacts warning (`UndecidedWarning` / `undecidedCount`) is
  the safety net for proceeding with incomplete triage and is unchanged.

## Non-Goals

- No undo/restore for deletions beyond what already exists downstream — a deleted account, backup, or
  draft is gone (the cascade warning is the safeguard).
- No change to Merge/Export behavior other than the Review→Export gate relaxation.
- No FK schema migration (see Design Decisions).
- No soft-delete/trash bin for accounts, backups, or drafts.

## Testing

- **Backend contract** (`tests/contract/test_working_copies_api.py`): `DELETE /working-copies/{id}`
  returns 400 without `confirm`, 404 for unknown id, 204 on success.
- **Backend integration** (mirror `tests/integration/test_snapshot_delete.py`): after deleting a
  draft that has dedup/triage/export data, all derived rows are gone and the draft no longer lists.
- **Backend integration**: deleting a snapshot that has drafts now succeeds and removes the drafts;
  deleting an account that has snapshots+drafts succeeds and removes the whole subtree.
- **Frontend**: deleting the active account/backup/draft clears the active chain and the wizard
  re-derives its step state; the confirm dialog shows correct cascade counts; Continue is enabled on
  Review with no triage session.

## Acceptance

1. In **Connect**, an account with backups/drafts can be deleted after confirming a dialog that warns
   how many backups and drafts will also be removed; afterwards it is gone and the chain resets.
2. In **Backup**, a backup with drafts can be deleted the same way.
3. In **Draft**, a draft can be deleted; its Merge/Review/Export data disappears with it.
4. On **Review**, "Continue" is always enabled and lands on **Export**, where the undecided warning
   still appears if triage was skipped or partial.
