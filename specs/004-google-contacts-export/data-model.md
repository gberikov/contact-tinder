# Phase 1 Data Model: Export Triage Results to Google Contacts

**Feature**: `004-google-contacts-export` · **Date**: 2026-06-20 · **Store**: PostgreSQL

Conventions follow features 001–003: ids are UUIDs; timestamps are `timestamptz` (UTC); `jsonb` via the
cross-dialect `JsonB` type. New tables are added via Alembic **`0004`**. **No existing table is altered.**
The export **reuses** `delete_batch` / `deletion_record` (003), `working_copy_contact`
(`status='active'` survivors), `triage_decision` / `processing_item` (the set sources), and `account`
(`granted_scopes` write-scope gate). The immutable `snapshot`/`snapshot_contact` foundation is untouched.

Entities introduced: **ExportRun**, **LabelBatch**, **LabelAssignment**, **ContactLabel**, plus new
`AuditEntry.action` values. The delete half of the export persists nothing new — it drives the existing
`DeleteBatch`/`DeletionRecord`.

---

## Entity: ExportRun

One export of a working copy's staged triage results to Google. Orchestrates the (reused) delete batch
and the (new) label batch and aggregates their results into the report.

| Field | Type | Notes |
|-------|------|-------|
| id | uuid (PK) | |
| working_copy_id | uuid (FK→WorkingCopy, ON DELETE CASCADE) | isolation scope (FR-021) |
| account_id | uuid (FK→Account, ON DELETE RESTRICT) | whose Google contacts (scope gate) |
| session_id | uuid (FK→TriageSession, ON DELETE SET NULL, nullable) | provenance |
| delete_batch_id | uuid (FK→DeleteBatch, ON DELETE SET NULL, nullable) | the reused delete batch (D7) |
| label_batch_id | uuid (FK→LabelBatch, ON DELETE SET NULL, nullable) | the new label batch (D7) |
| status | enum(`previewing`,`running`,`completed`,`failed`) default `previewing` | aggregate lifecycle |
| undecided_count | integer default 0 | active survivors with no terminal decision — warned & excluded (FR-017a) |
| created_at | timestamptz | |
| completed_at | timestamptz (nullable) | set when both batches reach terminal state |

- **Derivation (D2/D7)**: the delete set and label set are computed from current `active` survivors and
  their latest `TriageDecision`/`ProcessingItem` at preview/start time; the two sets are **disjoint**.
- **Report**: not stored as a blob — aggregated on read from the linked batches' records (D7).
- **Relationships**: 0..1 `DeleteBatch`, 0..1 `LabelBatch` (either may be absent if its set is empty).
- **Index**: (`working_copy_id`, `status`).

## Entity: LabelBatch

A set of contacts to be tagged with the `Process` label, committed to Google together (mirrors
`DeleteBatch`; research D3).

| Field | Type | Notes |
|-------|------|-------|
| id | uuid (PK) | |
| working_copy_id | uuid (FK→WorkingCopy, ON DELETE CASCADE) | isolation |
| session_id | uuid (FK→TriageSession, ON DELETE SET NULL, nullable) | provenance |
| account_id | uuid (FK→Account, ON DELETE RESTRICT) | scope gate |
| contact_label_id | uuid (FK→ContactLabel, ON DELETE SET NULL, nullable) | resolved `Process` group (D5) |
| status | enum(`staged`,`labeling`,`committed`,`failed`,`unlabeling`,`undone`) | lifecycle |
| total_count | integer default 0 | members at start time |
| labeled_count | integer default 0 | progressed by the worker (labeled + skipped_absent) |
| failed_count | integer default 0 | |
| last_error | text (nullable) | **redacted**; no secrets/PII (FR-023) |
| created_at | timestamptz | |
| committed_at / undone_at | timestamptz (nullable) | stage timestamps |

- **State transitions**: `staged → labeling → committed | failed`; `committed → unlabeling → undone`
  (undo removes memberships). Enqueued alongside the delete confirm — **no separate per-item
  confirmation** (FR-015). The write-scope gate (`account_has_write_scope`) applies before any Google call
  (FR-020); labeling needs no scope beyond delete's (research D1).
- **Group ensure (D5)**: before assigning members the worker resolves/creates the `Process` group and
  links `contact_label_id`.
- **Relationships**: 1→N `LabelAssignment`.
- **Index**: (`working_copy_id`, `status`).

## Entity: LabelAssignment  *(per-contact, reversible)*

One contact within a label batch; the idempotency + undo unit (mirrors `DeletionRecord`; research D3).
No full-payload snapshot is needed — the before-state is "not a member", recovered by removing it.

| Field | Type | Notes |
|-------|------|-------|
| id | uuid (PK) | |
| label_batch_id | uuid (FK→LabelBatch, ON DELETE CASCADE) | |
| working_copy_contact_id | uuid (FK→WorkingCopyContact, ON DELETE SET NULL, nullable) | source contact |
| origin_resource_name | text | Google `people/c…` target (captured at build time) |
| status | enum(`pending`,`labeled`,`skipped_absent`,`failed`,`removed`) | per-contact lifecycle |
| google_result | jsonb (nullable) | redacted API result/metadata |
| error | text (nullable) | **redacted** on `failed` |
| created_at | timestamptz | |
| labeled_at / removed_at | timestamptz (nullable) | |

- **Uniqueness**: (`label_batch_id`, `origin_resource_name`) unique — one assignment per contact per batch.
- **Idempotency (FR-012/012a)**: `labeled`/`skipped_absent` rows are never re-applied; a Google `404`
  (contact gone) → `skipped_absent` = success. Re-run processes only `pending`/`failed`.
- **Undo (FR-014)**: remove the membership via `contactGroups.members.modify`
  (`resourceNamesToRemove`), set `removed`. Never deletes contact data.

## Entity: ContactLabel  *(resolved Google group, per account)*

The `Process` contact group resolved/created once per account (research D5), so re-runs reuse it.

| Field | Type | Notes |
|-------|------|-------|
| id | uuid (PK) | |
| account_id | uuid (FK→Account, ON DELETE CASCADE) | owner |
| name | text default `Process` | label/group name |
| group_resource_name | text | Google `contactGroups/…` resourceName (authoritative once set) |
| created_at | timestamptz | |

- **Uniqueness**: (`account_id`, `name`) unique — at most one `Process` group reference per account
  (prevents duplicate groups, FR-010).

## Entity: DeleteBatch / DeletionRecord  *(existing — reused, unchanged)*

The deletion half of the export uses feature 003's tables and `delete_batch_service` verbatim: snapshot
(`payload_before`) persisted before any delete, dry-run preview, explicit confirm (scope-gated),
idempotent execution, `404 → skipped_absent`, undo via `create_contact`. The new `ExportRun` links the
`DeleteBatch` it created via `delete_batch_service.create_batch`. **No schema change.**

## Entity: AuditEntry  *(existing — extended)*

No schema change; new `action` values appended (FR-022):
`export.run.started`, `export.run.completed`, `label.group.created`, `label.batch.committed`,
`contact.labeled`, `contact.unlabeled`.

- `target_type` ∈ {`export_run`, `label_batch`, `working_copy_contact`, `contact_label`};
  `source_ref` carries the export run / label batch for per-contact actions. `details` is **redacted**
  (counts, result, group-resource ref) — never payloads, names, or secrets (FR-023). Delete-side actions
  reuse 003's `delete.batch.previewed/committed`, `contact.deleted`, `contact.restored`.

---

## Entity-Relationship summary

```text
WorkingCopy 1───N ExportRun ──0..1──→ DeleteBatch  1───N DeletionRecord  ──→ WorkingCopyContact / Google
                      │      ──0..1──→ LabelBatch   1───N LabelAssignment ──→ WorkingCopyContact / Google
                      └─ derives delete set + label set (disjoint) from TriageDecision / ProcessingItem
Account 1───N ExportRun, 1───N LabelBatch, 1───N ContactLabel(name='Process')   (write-scope holder; D1)
LabelBatch ──→ ContactLabel (resolved `Process` group, ensured once per account; D5)
AuditEntry (append-only; export.run.* / label.* / contact.labeled|unlabeled  +  003's delete.* )

(snapshot / snapshot_contact: untouched. delete_batch / deletion_record: reused unchanged from 003.)
```

## Validation & invariant checklist (for tests)

- Delete set = active survivors with latest decision `delete`; label set = active survivors routed to
  processing with latest decision ≠ `delete`; the two are **disjoint** (D2, FR-002).
- Undecided active survivors are counted in `ExportRun.undecided_count`, **excluded** from both sets, and
  surfaced as a warning (FR-017a).
- Contacts no longer `active` at export time are excluded from both sets (FR-003).
- 100% of the delete set has a `DeletionRecord.payload_before` persisted before any Google delete (SC-001,
  reused from 003).
- A `Process` group is created at most once per account; re-runs reuse `ContactLabel.group_resource_name`
  (FR-010/012); `(account_id, name)` is unique.
- Labeling is idempotent: re-running a batch never re-labels `labeled`/`skipped_absent` rows; a Google
  `404` → `skipped_absent` = success (FR-012/012a).
- Undo of a label batch removes membership for every `labeled` assignment and audits `contact.unlabeled`
  (FR-014); undo of a delete batch reuses 003's restore (FR-009).
- Any Google write (delete or label) is rejected when `account.granted_scopes` lacks the
  `…/auth/contacts` scope; no new scope is required for labeling (FR-020, SC-008, research D1).
- `ExportReport` counts (deleted / skipped-absent / labeled / failed / excluded) equal the aggregated
  batch-record statuses; re-running attempts only `pending`/`failed` records (FR-018/019, SC-004).
- All export access is scoped by `working_copy_id`/`account_id`; a cross-account id returns not-found
  (FR-021).
- No audit entry, report, or log contains payloads, names, or secrets (FR-023, SC-007).
- Staged edits/transliterations are present in the working copy but **never written to Google** by the
  export (FR-013, research D4).
