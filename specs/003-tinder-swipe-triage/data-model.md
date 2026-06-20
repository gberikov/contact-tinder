# Phase 1 Data Model: Tinder-Style Contact Swipe Triage

**Feature**: `003-tinder-swipe-triage` · **Date**: 2026-06-20 · **Store**: PostgreSQL

Conventions follow features 001/002: ids are UUIDs; timestamps are `timestamptz` (UTC); `jsonb` holds
Google `Person` payloads. New tables are added via Alembic (`0003`). **No existing table is altered** —
the deck reuses `working_copy_contact` (`status='active'` survivors; `origin_resource_name` = Google
delete target). The immutable `snapshot`/`snapshot_contact` foundation is never touched.

Entities introduced: **TriageSession**, **TriageDecision**, **ProcessingItem**, **StagedEdit**,
**DeleteBatch**, **DeletionRecord**, plus new `AuditEntry.action` values.

---

## Entity: TriageSession

One swipe pass over a working copy's `active` survivors.

| Field | Type | Notes |
|-------|------|-------|
| id | uuid (PK) | |
| working_copy_id | uuid (FK→WorkingCopy, ON DELETE CASCADE) | isolation scope (FR-010) |
| dedup_run_id | uuid (FK→DedupRun, ON DELETE SET NULL, nullable) | provenance only (D2) |
| status | enum(`in_progress`,`complete`) default `in_progress` | (FR-007 summary) |
| created_at | timestamptz | |
| finished_at | timestamptz (nullable) | set when deck exhausted |

- **Concurrency invariant (D11)**: partial unique index on `working_copy_id` WHERE
  `status='in_progress'` ⇒ at most one open session per working copy.
- **Deck (D1)**: `active` `working_copy_contact` rows for `working_copy_id`,
  `ORDER BY lower(display_name) NULLS LAST, id`. Not stored — computed per load.
- **Relationships**: 1→N `TriageDecision`, 1→N `ProcessingItem`, 0..N `DeleteBatch`.

## Entity: TriageDecision

The current outcome for one contact in a session (one live row per contact; D3).

| Field | Type | Notes |
|-------|------|-------|
| id | uuid (PK) | |
| session_id | uuid (FK→TriageSession, ON DELETE CASCADE) | |
| working_copy_contact_id | uuid (FK→WorkingCopyContact, ON DELETE CASCADE) | the decided contact |
| outcome | enum(`keep`,`delete`,`process`) | latest decision wins (FR-006) |
| decided_at | timestamptz | updated on re-decide |

- **Uniqueness**: (`session_id`, `working_copy_contact_id`) unique — re-decide **updates in place**.
- **History**: each create/update appends an `AuditEntry` (the navigable history lives there, D3).
- **Resume (D3/D11)**: next `active` contact in deck order with no live decision, or whose live
  outcome is `process` with a still-`pending` `ProcessingItem`.
- **Terminal rule (D4)**: when a `ProcessingItem` is marked done, its contact's decision defaults to
  `keep` (re-decidable). A session is `complete` when every `active` contact has a terminal
  (`keep`/`delete`) decision and no `pending` `ProcessingItem` remains.
- **Index**: (`session_id`, `outcome`) for the completion summary counts (SC-006).

## Entity: ProcessingItem

A contact routed to the post-swipe processing queue (D4).

| Field | Type | Notes |
|-------|------|-------|
| id | uuid (PK) | |
| session_id | uuid (FK→TriageSession, ON DELETE CASCADE) | |
| working_copy_contact_id | uuid (FK→WorkingCopyContact, ON DELETE CASCADE) | |
| wants_edit | boolean default false | requested "edit card" |
| wants_transliterate | boolean default false | requested "transliterate name" |
| status | enum(`pending`,`done`) default `pending` | |
| created_at | timestamptz | tagged during swipe |
| resolved_at | timestamptz (nullable) | set when marked done |

- **Uniqueness**: (`session_id`, `working_copy_contact_id`) unique.
- **Rule**: created with no editor interaction during the swipe pass (FR-011). Marking `done` triggers
  the terminal-`keep` default on the contact's `TriageDecision` (D4) unless already re-decided.
- **Index**: (`session_id`, `status`) for the pending-queue listing.

## Entity: StagedEdit  *(reversible working-copy mutation)*

Captures one card edit or accepted transliteration so it can be undone exactly (D6).

| Field | Type | Notes |
|-------|------|-------|
| id | uuid (PK) | |
| working_copy_contact_id | uuid (FK→WorkingCopyContact, ON DELETE CASCADE) | |
| working_copy_id | uuid (FK→WorkingCopy, ON DELETE CASCADE) | isolation |
| kind | enum(`edit`,`transliterate`) | provenance of the change |
| payload_before | jsonb | contact payload before the change (restore on undo) |
| payload_after | jsonb | payload written to the contact |
| status | enum(`active`,`undone`) default `active` | |
| created_at | timestamptz | |
| undone_at | timestamptz (nullable) | |

- **Apply**: write `payload_after` to `working_copy_contact.payload`; record before-image.
- **Undo (FR-016, SC-004)**: restore `payload_before`, set `undone`. Never touches Google or snapshot.
- **Transliteration scope (D5)**: for `kind='transliterate'`, only name fields differ between
  before/after (given/family/display); other fields are untouched.
- **Index**: (`working_copy_contact_id`, `status`) for "latest active edit" lookups.

## Entity: DeleteBatch

A set of queued-for-deletion contacts reviewed and committed to Google together (D8/D10).

| Field | Type | Notes |
|-------|------|-------|
| id | uuid (PK) | |
| working_copy_id | uuid (FK→WorkingCopy, ON DELETE CASCADE) | isolation |
| session_id | uuid (FK→TriageSession, ON DELETE SET NULL, nullable) | provenance |
| account_id | uuid (FK→Account, ON DELETE RESTRICT) | whose Google contacts (scope check) |
| status | enum(`staged`,`previewed`,`committing`,`committed`,`failed`,`undone`) | lifecycle |
| total_count | integer | members at confirm time |
| deleted_count | integer default 0 | progressed by the worker |
| failed_count | integer default 0 | |
| last_error | text (nullable) | **redacted**; no secrets/PII (FR-026) |
| created_at | timestamptz | |
| previewed_at / committed_at / undone_at | timestamptz (nullable) | stage timestamps |

- **State transitions**: `staged → previewed → committing → committed | failed`; `committed → undone`
  via the undo path. The confirm step is **rejected** unless the `Account` holds the `contacts` write
  scope (D9).
- **Snapshot guarantee (FR-020, SC-002)**: every member's `DeletionRecord.payload_before` is persisted
  **before** the batch enters `committing` / any Google call.
- **Relationships**: 1→N `DeletionRecord`.
- **Index**: (`working_copy_id`, `status`).

## Entity: DeletionRecord  *(per-contact, restorable)*

One contact within a delete batch; the restorable snapshot + idempotency unit (D8).

| Field | Type | Notes |
|-------|------|-------|
| id | uuid (PK) | |
| delete_batch_id | uuid (FK→DeleteBatch, ON DELETE CASCADE) | |
| working_copy_contact_id | uuid (FK→WorkingCopyContact, ON DELETE SET NULL, nullable) | source contact |
| origin_resource_name | text | Google `people/c…` delete target (captured at build time) |
| payload_before | jsonb | full Person payload — restore-on-undo source (FR-020) |
| status | enum(`pending`,`deleted`,`skipped_absent`,`failed`,`restored`) | per-contact lifecycle |
| google_result | jsonb (nullable) | redacted API result/metadata |
| restored_resource_name | text (nullable) | new `people/c…` after undo re-create (D8) |
| error | text (nullable) | **redacted** on `failed` |
| created_at | timestamptz | |
| deleted_at / restored_at | timestamptz (nullable) | |

- **Uniqueness**: (`delete_batch_id`, `origin_resource_name`) unique — one delete per contact per batch.
- **Idempotency (FR-022/024)**: `deleted`/`skipped_absent` records are never retried; a Google
  `404 Not Found` → `skipped_absent` (success). Retry processes only `pending`/`failed`.
- **Undo (FR-023)**: re-create via `createContact(payload_before)`, store `restored_resource_name`, set
  `restored`. Restores the working-copy contact's `status` to `active` if it had been removed.

## Entity: AuditEntry  *(existing — extended)*

No schema change; new `action` values appended (FR-025):
`triage.session.started`, `triage.session.completed`, `contact.kept`, `contact.queued_delete`,
`contact.sent_processing`, `contact.edited`, `contact.transliterated`, `edit.undone`,
`delete.batch.previewed`, `delete.batch.committed`, `contact.deleted`, `contact.restored`.

- `target_type` ∈ {`triage_session`, `working_copy_contact`, `delete_batch`, `working_copy`};
  `source_ref` carries the session/batch for per-contact actions. `details` is **redacted** (counts,
  outcome, `kind`, resource-name reference) — never payloads, names, or secrets (FR-026, SC-007).

---

## Entity-Relationship summary

```text
WorkingCopy 1───N TriageSession 1───N TriageDecision ──→ WorkingCopyContact(active|…)
                       │ 1───N ProcessingItem  ──→ WorkingCopyContact
                       │ 0───N DeleteBatch 1───N DeletionRecord ──→ WorkingCopyContact / Google resourceName
WorkingCopyContact 1───N StagedEdit (edit | transliterate; reversible)
Account 1───N DeleteBatch        (write-scope holder; D9)
AuditEntry  (append-only; triage.* / contact.* / delete.batch.* )

(Snapshot / SnapshotContact: untouched — immutable foundation from feature 001)
(DedupRun: referenced for provenance only — survivors come from working_copy_contact.status='active')
```

## Validation & invariant checklist (for tests)

- Deck = exactly the `active` `working_copy_contact` rows, in `lower(display_name), id` order (D1).
- At most one `in_progress` `TriageSession` per `working_copy_id` (partial unique index, D11).
- The deck/summary are computed from current `active` rows each load; if survivors change after a
  session starts, the change is reflected/surfaced and a decision for a now-inactive contact is
  excluded from terminal actions rather than lost (FR-027, D11).
- Re-deciding a contact updates the single `TriageDecision` row (latest wins) and appends an audit
  entry (FR-006, D3).
- A contact swiped `process` opens **no editor**; a `ProcessingItem` is created `pending` (FR-011).
- Marking a `ProcessingItem` done defaults the contact's decision to `keep`, re-decidable (D4).
- Accepting a transliteration changes **only name fields**; a `StagedEdit(kind=transliterate)` records
  before/after; undo restores exactly (FR-014/016, SC-004).
- A name already in Cyrillic / empty yields no destructive change (FR-017).
- 100% of a batch's `DeletionRecord.payload_before` are persisted **before** any Google delete call
  (FR-020, SC-002).
- Confirming a batch is rejected if the `Account` lacks the `contacts` write scope (D9).
- Delete execution is idempotent: re-running a batch never re-deletes `deleted`/`skipped_absent`
  records; a Google `404` → `skipped_absent` = success (FR-022/024).
- Undo re-creates each deleted contact from `payload_before` and reactivates the working-copy contact
  (FR-023).
- A session reaches `complete` only when every `active` contact has a terminal `keep`/`delete` decision
  and no `pending` `ProcessingItem` remains; the summary counts match (SC-006).
- All session/decision/processing/batch access is scoped by `working_copy_id`/`account_id`; a
  cross-account id returns not-found, never another account's data (FR-010).
- No audit entry or log contains payloads, names, or secrets (FR-026, SC-007).
