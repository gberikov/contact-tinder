# Feature Specification: Export Triage Results to Google Contacts

**Feature Branch**: `004-google-contacts-export`

**Created**: 2026-06-20

**Status**: Draft

**Input**: User description: "Мы с тобой уже импортировали данные, сделали дедупликацию, провели триаж. Теперь нужно сделать экспорт в Google Contacts. Это уже write-операция. Все объекты, которые были помечены как удаленные, их нужно удалить. Все объекты, которые попали в Processing Queue, Их надо пометить меткой Process, Чтобы я мог их легко отфильтровать и допроверить"

## Clarifications

### Session 2026-06-20

- Q: On export, what should happen to the contacts in the Processing Queue? → A: Apply the `Process` label only — do NOT push the staged edits/transliterations; the user will re-check and edit those manually in Google using the label as a filter.
- Q: Deleting the delete-marked contacts and applying the `Process` label are two write operations — how are they governed within the export? → A: One Export screen that previews both, but deletions require their own explicit confirmation (safety rule); labeling runs alongside.
- Q: Must the triage session be complete before export can run? → A: No — export may run anytime; it acts only on current terminal `delete`/processing decisions and warns (and excludes) when survivors are still undecided.
- Q: How is a Processing-Queue contact handled when it no longer exists in Google at label time? → A: Treat as skipped / already-satisfied (success), reported as skipped-absent; it does not fail the batch.
- Q: How does the export execute and surface progress? → A: As a background worker job for both deletes and labels; the Export screen shows live progress and the report updates as work completes; the user may navigate away and return.

## User Scenarios & Testing *(mandatory)*

This feature is the **write-to-Google export** that commits the decisions captured during triage
(feature 003). Until now everything has been staged and non-destructive: contacts were imported
(feature 001), deduplicated (feature 002), and triaged into **keep / delete / send-to-processing**
decisions (feature 003) without a single change reaching Google. This feature performs the outward,
write-side actions that turn those staged decisions into changes in the user's real Google Contacts.

The export performs exactly two kinds of write, surfaced together on one **Export** screen:

1. **Delete** — every contact the user marked **delete** during triage is deleted in Google, as a
   snapshot-protected, explicitly-confirmed, idempotent, undoable batch (the project's headline
   destructive action).
2. **Label `Process`** — every contact the user routed to the **Processing Queue** (and did not later
   re-decide to delete) is tagged with a `Process` label/group in Google Contacts, so the user can
   filter to exactly those contacts later and finish reviewing/editing them by hand. The staged edits
   and Latin→Cyrillic transliterations from feature 003 are **not** pushed by this export — the label is
   a marker for manual follow-up, per the user's "чтобы я мог их допроверить".

Contacts marked **keep** are left exactly as they are in Google; the export creates no new contacts.
Everything stays consistent with the constitution: non-destructive by default (snapshot + undo before
any delete), human-in-the-loop (explicit per-batch delete confirmation), least-privilege scopes
(write permission requested via incremental consent only when first needed), and full auditability.

### User Story 1 - Delete the marked contacts in Google (Priority: P1)

The user has finished triage and marked a set of contacts for deletion. They open the Export screen,
see a dry-run preview listing exactly which contacts will be deleted, and explicitly confirm. The
system records a restorable snapshot of every affected contact before any deletion call, then executes
the deletions in Google. The result is reported per contact, the whole batch is undoable within the
retention window, and re-running after a partial failure only retries what did not yet succeed.

**Why this priority**: Deletion is the destructive, irreversible-in-Google action and the core reason
the user wants an export at all ("их нужно удалить"). It is the smallest slice that delivers the
feature's headline value, and it carries the highest risk, so it is specified and built first.

**Independent Test**: With several contacts marked delete in a working copy, open the Export screen,
verify the preview lists exactly those contacts and nothing else, confirm, and (against a non-production
/ mocked Google seam) verify that a snapshot was persisted for each before any delete call, every
deletion is audited, a Google "already gone" response is treated as success, a forced partial failure
is retryable without re-deleting, and undo restores the affected contacts.

**Acceptance Scenarios**:

1. **Given** a working copy with contacts marked delete during triage, **When** the user opens the
   Export screen, **Then** a dry-run preview lists every contact that will be deleted, the count
   matches the number of current `delete` decisions, and nothing has been sent to Google yet.
2. **Given** a contact that was marked delete and then re-decided to keep, **When** the export preview
   is built, **Then** that contact is excluded from the deletion set (latest decision wins).
3. **Given** the deletion preview, **When** the user confirms, **Then** a restorable snapshot of every
   affected contact is persisted before any deletion call is made to Google.
4. **Given** a confirmed deletion, **When** the deletions execute, **Then** each one is recorded in the
   append-only audit log with who, what, when, the before-state reference, and the Google result.
5. **Given** a contact that no longer exists in Google at export time, **When** its deletion runs,
   **Then** it is treated as already-deleted (success), not an error.
6. **Given** a deletion run that fails partway through, **When** the user retries, **Then** only
   contacts not yet deleted are attempted again and no contact is deleted twice.
7. **Given** a recently committed deletion, **When** the user triggers undo within the retention window,
   **Then** the affected contacts are restored from the snapshot.

---

### User Story 2 - Label the Processing-Queue contacts with `Process` (Priority: P2)

Every contact the user sent to the Processing Queue during triage needs to be findable in Google
Contacts afterwards so the user can finish reviewing it by hand. On export, the system applies a
`Process` label (a Google Contacts group) to each such contact, creating the `Process` label if it does
not yet exist. The user can then open Google Contacts, filter by `Process`, and work through exactly
those contacts. Applying the label is a reversible, audited write; it does not delete or edit any
contact data, and it does not push the staged edits/transliterations from feature 003.

**Why this priority**: Labeling is the non-destructive half of the export and the user's mechanism for
"легко отфильтровать и допроверить". It is independently valuable and lower-risk than deletion, so it
ships after the delete path but does not depend on it.

**Independent Test**: With several contacts in the Processing Queue, run the labeling action against a
mocked Google seam, and verify a `Process` label/group is created if absent, every queued contact (that
is not in the deletion set) becomes a member, the action is audited, applying it twice does not create
duplicates or duplicate the group, and removing the label (undo) is possible.

**Acceptance Scenarios**:

1. **Given** contacts that were sent to the Processing Queue and not later marked delete, **When** the
   user runs the export, **Then** every such contact is assigned the `Process` label in Google.
2. **Given** no `Process` label/group exists in the account yet, **When** labeling runs, **Then** the
   `Process` label is created once and reused for all members.
3. **Given** a `Process` label already exists, **When** labeling runs, **Then** the existing label is
   reused and no duplicate label/group is created.
4. **Given** a contact that is already labeled `Process`, **When** labeling runs again, **Then** the
   operation is idempotent and the contact is not duplicated within the group.
5. **Given** the labeling completed, **When** the user opens Google Contacts and filters by `Process`,
   **Then** exactly the Processing-Queue contacts appear, and the staged edits/transliterations are
   visibly NOT applied (the label is a marker for manual follow-up).
6. **Given** a labeling write that fails partway, **When** the user retries, **Then** only contacts not
   yet labeled are attempted again.
7. **Given** a labeling action was applied, **When** the user reverses it within the retention window,
   **Then** the `Process` membership is removed from the affected contacts and the action is audited.

---

### User Story 3 - Unified Export screen and post-export report (Priority: P3)

The user wants a single place to run "the export" and understand what happened. One Export screen shows
both pending write actions for the working copy — N contacts to delete, M contacts to label `Process` —
with accurate counts and dry-run previews. Deletion requires its own explicit confirmation; labeling
runs alongside without a separate per-item confirmation. After the run, a report shows per-action
results (deleted, skipped-already-gone, labeled, failed) with entry points to undo, and the export is
re-runnable so any failures can be retried until everything is committed.

**Why this priority**: This is the orchestration and reporting layer that ties US1 and US2 into the one
"экспорт" the user asked for. It depends on both write paths existing, so it is sequenced last; the
individual write actions already deliver value without the combined surface.

**Independent Test**: With both a deletion set and a Processing-Queue set staged, open the Export
screen, verify both counts and previews are accurate, that confirming triggers the delete confirmation
but labeling does not require a separate confirmation, run the export, and verify the post-export report
shows correct per-action outcomes and that a partial failure can be retried to completion.

**Acceptance Scenarios**:

1. **Given** a working copy with staged delete and processing decisions, **When** the user opens the
   Export screen, **Then** it shows the number of contacts to be deleted and the number to be labeled
   `Process`, each with a preview, and indicates nothing has been written yet.
2. **Given** the Export screen, **When** the user starts the export, **Then** the deletion step requires
   an explicit confirmation while the labeling step proceeds without a separate per-item confirmation.
3. **Given** an export has run, **When** it completes, **Then** a report shows, per action, how many
   contacts were deleted, treated as already-gone, labeled, and failed, with undo entry points.
4. **Given** an export that partially failed, **When** the user re-runs it, **Then** already-completed
   work is not repeated and only outstanding deletions/labels are attempted.
5. **Given** there is nothing to delete and nothing to label, **When** the user opens the Export screen,
   **Then** an explicit empty/"nothing to export" state is shown instead of runnable actions.

---

### Edge Cases

- **Nothing to export**: no delete decisions and no Processing-Queue contacts — the Export screen shows
  an explicit empty state, not a runnable (and no-op) action.
- **Re-decided contact**: a contact marked delete then changed to keep is not deleted; a contact in the
  Processing Queue then re-decided to delete is deleted and not labeled (the two sets are disjoint, and
  the latest terminal decision governs which set a contact lands in).
- **Already deleted in Google**: a contact queued for deletion that no longer exists in Google at export
  time is treated as already-satisfied (success), never an error.
- **Label already present / already exists**: re-running labeling does not create a duplicate `Process`
  label/group nor duplicate memberships (idempotent).
- **Label target gone from Google**: a Processing-Queue contact that no longer exists in Google at label
  time is treated as skipped / already-satisfied (success), reported as skipped-absent — it never fails
  the labeling run.
- **Missing write permission**: if the account has not yet granted the Google write permission needed
  for deletion and/or labeling, the export requests it via incremental consent before the first write;
  it never attempts a write without the required scope and surfaces a clear prompt.
- **Partial failure / quota / rate limit during a run**: the export surfaces the throttle, leaves
  completed work committed, and remains retryable and idempotent (no double-delete, no double-label).
- **Working copy changed since triage**: if a contact in the delete or label set is no longer an active
  survivor of the working copy at export time, it is excluded from the action and surfaced in the
  report rather than silently acted on or lost.
- **Staged edits not pushed**: contacts labeled `Process` keep their original Google data; the export
  must not write the staged edits/transliterations — the label is purely a follow-up marker.
- **Undo after manual change in Google**: if a deleted contact was already manually re-created in
  Google, or a label was already removed by the user, undo treats the state as already-satisfied rather
  than failing the whole batch.

## Requirements *(mandatory)*

### Functional Requirements

#### Sourcing the export sets

- **FR-001**: The system MUST derive the **deletion set** from the working copy's current terminal
  triage decisions — exactly the active survivors whose latest decision is `delete`. Contacts re-decided
  away from `delete` MUST be excluded (latest decision wins).
- **FR-002**: The system MUST derive the **label set** as exactly the active survivors that were routed
  to the Processing Queue and whose latest terminal decision is NOT `delete`. The deletion set and the
  label set MUST be disjoint.
- **FR-003**: The system MUST exclude from both sets any contact that is no longer an active survivor of
  the working copy at export time, and surface such exclusions in the export preview/report rather than
  silently acting on or dropping them.

#### Deletion write

- **FR-004**: The system MUST provide a dry-run preview of the deletion set listing exactly which
  contacts will be deleted, before anything is sent to Google.
- **FR-005**: The system MUST persist a restorable snapshot of every contact in the deletion set BEFORE
  executing any deletion against Google.
- **FR-006**: The system MUST require an explicit, per-batch user confirmation before deleting in
  Google; no deletion may occur without it.
- **FR-007**: Deletion execution MUST be idempotent and safe to retry after a partial failure; a contact
  already deleted in a prior run MUST NOT be deleted again.
- **FR-008**: A contact already absent in Google at export time MUST be treated as already-deleted
  (success), not a failure.
- **FR-009**: The system MUST support undo of a committed deletion within the retention window (the
  lifetime of the working copy — **no timed expiry**; see Assumptions), restoring affected contacts from
  the snapshot.

#### Label (`Process`) write

- **FR-010**: The system MUST ensure a label/group named `Process` exists in the target Google account,
  creating it once if absent and reusing it if it already exists (never creating a duplicate).
- **FR-011**: The system MUST assign the `Process` label to every contact in the label set.
- **FR-012**: Label assignment MUST be idempotent — re-running it MUST NOT duplicate the label/group or
  add a contact to it more than once.
- **FR-012a**: A contact in the label set that no longer exists in Google at label time MUST be treated
  as skipped / already-satisfied (success), reported as skipped-absent, and MUST NOT fail the labeling
  run (mirroring the deletion already-gone rule, FR-008).
- **FR-013**: The system MUST NOT push the staged edits or Latin→Cyrillic transliterations (from feature
  003) to Google during this export; labeled contacts retain their existing Google field data. The
  label is solely a marker enabling the user to filter and manually re-check them.
- **FR-014**: Label assignment MUST be reversible within the retention window (the lifetime of the
  working copy — **no timed expiry**; see Assumptions): the `Process` membership can be removed from the
  affected contacts, and the reversal MUST be auditable.
- **FR-015**: Label assignment runs as part of the export WITHOUT a separate per-item confirmation
  (deletion's explicit confirmation does not gate labeling).

#### Export orchestration & reporting

- **FR-016**: The system MUST present a single Export screen for a working copy that shows both pending
  actions — the count and preview of contacts to delete and the count and preview of contacts to label
  `Process` — and indicates that nothing has been written yet.
- **FR-017**: When nothing is staged for either action, the Export screen MUST show an explicit empty /
  "nothing to export" state instead of runnable actions.
- **FR-017a**: The export MUST be runnable regardless of whether the triage session is complete; it
  acts only on contacts with a current terminal decision. When one or more active survivors are still
  undecided, the Export screen MUST warn the user and MUST exclude those undecided contacts from both
  the deletion and label sets (they are never acted on by default).
- **FR-018**: The system MUST produce a post-export report giving, per action, how many contacts were
  deleted, treated as already-gone (skipped-absent), labeled, and failed, with entry points to undo each
  action.
- **FR-019**: The export MUST be re-runnable; on re-run it MUST attempt only outstanding work (deletions
  or labels not yet successfully applied) and never repeat completed work.
- **FR-019a**: The export MUST execute as a background job (in the existing worker) for both deletions
  and labeling. The Export screen MUST show live progress while it runs and the report MUST update as
  work completes; the user MAY navigate away and return without interrupting or losing the run.

#### Permissions, isolation & auditability

- **FR-020**: The system MUST request the narrowest Google write permission(s) required for deletion and
  for labeling, obtaining them via incremental consent, and MUST refuse to attempt a write for which the
  required permission has not been granted (surfacing a clear prompt instead).
- **FR-021**: All export actions MUST be isolated to the acting account's own contacts; one account MUST
  never delete or label another account's contacts.
- **FR-022**: Every export mutation (delete, label-assign, restore, label-remove) and the snapshot taken
  before deletion MUST be recorded in the append-only audit log capturing who, what, when, the
  before-state reference, and the Google API result.
- **FR-023**: Logs, the export report, and any diagnostic output MUST redact contact PII and secrets.
- **FR-024**: The export MUST surface Google rate-limit/quota responses to the user and remain retryable
  and idempotent under them.

### Key Entities *(include if feature involves data)*

- **Export Run**: One invocation of the export for a working copy/account. Tracks which actions it
  covers (delete, label), their progress/status, and links to the resulting report. Re-runnable.
- **Deletion Set / Delete Batch**: The set of contacts whose terminal decision is `delete`, reviewed and
  committed to Google together, with its per-contact restorable snapshot, status (staged / previewed /
  committing / committed / undone), and result. Reuses the snapshot-protected delete-batch concept.
- **Deletion Record**: One contact within a delete batch — the restorable snapshot (full contact
  payload), its Google delete target, per-contact status (pending / deleted / already-gone / failed /
  restored), and result. The idempotency and undo unit.
- **Label Set / `Process` Label Action**: The set of Processing-Queue contacts to be tagged, the
  reference to the `Process` Google label/group (created-or-reused), per-contact membership status
  (pending / labeled / failed / removed), and result. The reversibility/idempotency unit for labeling.
- **`Process` Label**: The Google Contacts label/group named `Process` used to mark contacts for manual
  follow-up; created once per account if absent, reused thereafter.
- **Export Report**: The per-action summary of an export run (deleted, already-gone, labeled, failed,
  excluded) with undo entry points — redacted of PII.
- **Audit Entry**: An append-only record of each export mutation (who, what, when, before-state
  reference, Google result) — reused from the project-wide audit log.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of contacts in the deletion set have a restorable snapshot persisted BEFORE any
  deletion is sent to Google — zero deletions occur without a recoverable copy.
- **SC-002**: After a successful export, 100% of the Processing-Queue contacts (that were not deleted)
  carry the `Process` label in Google, and filtering by `Process` in Google Contacts returns exactly
  that set — no more, no fewer.
- **SC-003**: No deletion or labeling occurs for any contact whose latest terminal decision does not
  call for it (zero contacts deleted that were re-decided to keep; zero labeled that were re-decided to
  delete).
- **SC-004**: Re-running an export after a partial failure completes the outstanding work without
  repeating any completed work — zero double-deletes and zero duplicate labels/memberships.
- **SC-005**: Any committed deletion can be undone within the retention window, restoring the affected
  contacts; any applied `Process` label can be removed within the retention window.
- **SC-006**: A contact already absent in Google at export time is reported as already-deleted (success)
  and never causes the batch to fail.
- **SC-007**: 100% of export mutations (delete, label, restore, remove) and pre-delete snapshots produce
  an audit entry, and no audit entry, log, or report contains unredacted PII or secrets.
- **SC-008**: The export never writes to Google using a permission the account has not granted; when a
  required write permission is missing, the user is prompted to grant it and no write is attempted until
  it is granted.

## Assumptions

- This feature builds directly on feature 001 (snapshots & working copies), feature 002 (Zingg dedup),
  and feature 003 (swipe triage). The export consumes feature 003's staged terminal decisions
  (`keep` / `delete`) and Processing-Queue membership; it reuses the snapshot/undo foundation and the
  Google write seam (`deleteContact` / contact-write client) established earlier rather than rebuilding
  them. The snapshot-protected delete-batch flow described in feature 003's US3 is realized here as the
  deletion half of the export.
- "Delete" means deleting the contact in **Google Contacts**, executed only via the guarded,
  snapshot-protected, explicitly-confirmed, idempotent batch (Constitution: Non-Destructive by Default).
- The `Process` label is a **Google Contacts label/group** named `Process`; applying it adds the contact
  to that group. It is created once per account if absent and reused thereafter. Filtering by it in
  Google Contacts is the user's intended manual re-check workflow.
- Per the clarification, the export applies the `Process` label **only**; it does NOT push the staged
  edits or transliterations from feature 003 to Google. Those staged changes remain in the working copy
  for the user to apply manually (or in a future feature); the label exists so the user can find them.
- Contacts decided `keep` are left untouched in Google, and the export creates no new contacts. (Contact
  re-creation exists only as the undo/restore path for a deletion.)
- The deletion set and the label set are disjoint and governed by each contact's latest terminal
  decision; "send to processing" resolves to a kept-and-labeled contact unless the user re-decided it to
  delete.
- The undo "retention window" is the **lifetime of the working copy**, consistent with features 002/003
  — undo for committed deletes and removal of an applied `Process` label stay available for as long as
  the working copy (and its delete/label records) exists, with no timed expiry.
- The write permission(s) for deletion and labeling are requested via **incremental consent** at the
  least-privilege level; the same broad contacts-write grant may already satisfy both, but the export
  must not assume a grant it has not confirmed.
- Single-tenant, self-hosted deployment supporting multiple Google accounts belonging to the operator;
  both the deletion and the `Process`-labeling work run as background jobs in the existing PG-backed
  worker (no new container), consistent with the established stack and constitution.
