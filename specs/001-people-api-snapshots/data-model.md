# Phase 1 Data Model: Google People API Snapshots & Working Copies

**Feature**: `001-people-api-snapshots` · **Date**: 2026-06-20 · **Store**: PostgreSQL

Conventions: all ids are UUIDs; all timestamps are `timestamptz` (UTC). `jsonb` holds the raw
Google `Person` payload. Foreign keys cascade per the rules noted. "Immutable" means the
application exposes no update/delete path for those rows except the documented snapshot-delete flow.

---

## Entity: Account  *(Google Account Connection)*

A Google account the operator has authorized (read-only).

| Field | Type | Notes |
|-------|------|-------|
| id | uuid (PK) | |
| google_account_id | text | Google's stable account/profile id; unique |
| email | text | Display label for the connection |
| status | enum(`connected`,`needs_reauth`,`revoked`) | FR-017 sets `needs_reauth` |
| granted_scopes | text[] | Expected: `contacts.readonly` only |
| created_at | timestamptz | |
| updated_at | timestamptz | |

- **Uniqueness**: `google_account_id` unique (one connection per Google account).
- **Relationships**: 1→1 `Credential`; 1→N `Snapshot`.
- **Validation**: `granted_scopes` MUST contain only read-only contacts scope (FR-001).

## Entity: Credential  *(secret — never serialized)*

Encrypted OAuth tokens, isolated from `Account`.

| Field | Type | Notes |
|-------|------|-------|
| id | uuid (PK) | |
| account_id | uuid (FK→Account, unique, ON DELETE CASCADE) | |
| enc_refresh_token | bytea | Ciphertext (AES-GCM/Fernet) — FR-002 |
| enc_access_token | bytea | Ciphertext; short-lived |
| access_token_expiry | timestamptz | |
| key_id | text | Identifies the `TOKEN_ENCRYPTION_KEY` used (rotation) |
| created_at / updated_at | timestamptz | |

- **Rule**: MUST NOT appear in any API response, log, or export (Principle I, FR-002). No read
  endpoint returns this entity.

## Entity: Snapshot

An immutable, point-in-time capture of one account's personal contacts.

| Field | Type | Notes |
|-------|------|-------|
| id | uuid (PK) | |
| account_id | uuid (FK→Account, ON DELETE RESTRICT) | isolation (FR-018) |
| status | enum(`importing`,`complete`,`failed`,`deleting`) | usable only when `complete` |
| source | text = `personal_connections` | FR-003 |
| contact_count | integer | set when finalized |
| next_sync_token | text (nullable) | stored for future incremental sync (D3) |
| created_at | timestamptz | capture start |
| finalized_at | timestamptz (nullable) | set on transition to `complete` |
| label | text (nullable) | optional operator label |

- **State transitions**:
  `importing → complete` (only when import fully succeeds — FR-008) ·
  `importing → failed` (transient-exhausted/auth error — FR-017; not usable, SC-006) ·
  `complete → deleting → (row removed)` (FR-021/FR-022 delete flow).
- **Invariant**: once `complete`, `contact_count` and child `SnapshotContact` rows never change
  (FR-005, SC-003).
- **Relationships**: 1→1 `ImportJob`; 1→N `SnapshotContact`; 1→N `WorkingCopy`.

## Entity: ImportJob

Durable, resumable progress for a snapshot's import (D4).

| Field | Type | Notes |
|-------|------|-------|
| id | uuid (PK) | |
| snapshot_id | uuid (FK→Snapshot, unique, ON DELETE CASCADE) | |
| status | enum(`queued`,`running`,`completed`,`failed`) | |
| page_token | text (nullable) | People API cursor — resume point (FR-016) |
| fetched_count | integer default 0 | progress for UI (FR-015) |
| total_estimate | integer (nullable) | from `totalItems` when available |
| attempts | integer default 0 | backoff/retry accounting (D9) |
| max_attempts | integer default 5 | retry ceiling for transient errors (A1) |
| last_error | text (nullable) | redacted message |
| started_at / updated_at / finished_at | timestamptz | |

- **Resume rule**: a worker picking up a `running`/`queued` job continues from `page_token`.
- **Failure rule**: when `attempts` exceeds `max_attempts` on a transient error (429/5xx), the job
  transitions to `failed` and its snapshot to `failed` — never partially finalized (FR-008,
  SC-006). This bounds the "transient → failed" boundary so it is testable.
- **Uniqueness**: one active import per account at a time (prevents conflicting in-progress
  imports — edge case).

## Entity: SnapshotContact  *(immutable)*

One captured contact within a snapshot.

| Field | Type | Notes |
|-------|------|-------|
| id | uuid (PK) | |
| snapshot_id | uuid (FK→Snapshot, ON DELETE CASCADE) | |
| resource_name | text | Google `people/c...` id |
| etag | text | Google etag at capture |
| payload | jsonb | raw `Person` (FR-004) |
| display_name | text (nullable) | extracted for list/search |
| primary_email | text (nullable) | extracted |
| primary_phone | text (nullable) | extracted |
| captured_at | timestamptz | |

- **Uniqueness**: (`snapshot_id`, `resource_name`) unique.
- **Index**: (`snapshot_id`, `display_name`) for read-only browsing/sort.
- **Fidelity (FR-004)**: `payload` faithfully preserves every captured People field — names,
  phone numbers, email addresses, postal addresses, organizations, biographies/notes, group/label
  memberships, and photo references. The extracted columns above exist only for display/search and
  are not the source of truth; no captured field is dropped.

## Entity: WorkingCopy

An editable, independent derivative of exactly one snapshot.

| Field | Type | Notes |
|-------|------|-------|
| id | uuid (PK) | |
| snapshot_id | uuid (FK→Snapshot, ON DELETE RESTRICT) | blocks snapshot delete (FR-022) |
| label | text | operator-provided name |
| status | enum(`creating`,`ready`) | |
| created_at | timestamptz | |

- **Relationships**: 1→N `WorkingCopyContact`.
- **Rule**: existence blocks deletion of its source snapshot (FR-022).
- **Derived**: `contact_count` = count of `WorkingCopyContact` for this copy; surfaced as
  `WorkingCopy.contactCount` in the API (mirrors `Snapshot.working_copy_count`).

## Entity: WorkingCopyContact  *(editable)*

A contact inside a working copy, initialized from the snapshot.

| Field | Type | Notes |
|-------|------|-------|
| id | uuid (PK) | |
| working_copy_id | uuid (FK→WorkingCopy, ON DELETE CASCADE) | |
| origin_resource_name | text | links back to source contact (read-only ref) |
| payload | jsonb | editable copy of `Person` |
| created_at / updated_at | timestamptz | |

- **Rule**: writes here MUST NOT touch `SnapshotContact` (FR-011/FR-012). Editing semantics are
  exercised by later features; v1 only creates the copy.

## Entity: AuditEntry  *(append-only)*

| Field | Type | Notes |
|-------|------|-------|
| id | uuid (PK) | |
| occurred_at | timestamptz | |
| action | enum(`snapshot.created`,`snapshot.deleted`,`working_copy.created`) | FR-019/FR-023 |
| actor | text = `operator` | single-operator deployment |
| target_type | text | `snapshot` / `working_copy` |
| target_id | uuid | |
| source_ref | uuid (nullable) | e.g. source snapshot for a working copy |
| details | jsonb | redacted; never contains tokens/secrets (Principle V) |

- **Rule**: insert-only; no update/delete path.

---

## Derived/reported values

- `Snapshot.working_copy_count` = count of `WorkingCopy` where `snapshot_id = Snapshot.id`
  (FR-014); surfaced in the snapshots list and used to enforce the delete guard (FR-022).

## Entity-Relationship summary

```text
Account 1───1 Credential
Account 1───N Snapshot 1───1 ImportJob
                  │
                  ├───N SnapshotContact        (immutable)
                  └───N WorkingCopy 1───N WorkingCopyContact   (editable)
AuditEntry  (append-only, references snapshots / working copies)
```
