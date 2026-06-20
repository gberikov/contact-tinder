# Phase 1 Data Model: Working-Copy Deduplication with Zingg

**Feature**: `002-zingg-dedup` · **Date**: 2026-06-20 · **Store**: PostgreSQL

Conventions follow feature 001: all ids are UUIDs; timestamps are `timestamptz` (UTC); `jsonb` holds
raw/derived Google `Person` payloads. New tables are added via Alembic; the only change to an
existing table is a new `status` column on `working_copy_contact`. No snapshot table is touched.

Entities introduced here: **DedupRun**, **DuplicateCluster**, **ClusterMember**, **MergeRecord**,
plus the `working_copy_contact.status` extension and new `AuditEntry.action` values.

---

## Modified Entity: WorkingCopyContact  *(adds soft-retire)*

| Field | Type | Notes |
|-------|------|-------|
| status | enum(`active`,`retired`) default `active` | NEW — `retired` = merged away, reversible (D6) |

- **Rule**: only `active` rows are "live" contacts in the working copy. A merge sets non-survivors
  to `retired`; undo flips them back to `active`. No row is hard-deleted by dedup.
- **Index**: (`working_copy_id`, `status`) for live-contact listing.
- Existing fields (`id`, `working_copy_id`, `origin_resource_name`, `payload`, timestamps) unchanged;
  `payload` of the **survivor** is overwritten on merge (its pre-merge value is preserved in
  `MergeRecord`).

## Entity: DedupRun

One execution of deduplication over a single working copy.

| Field | Type | Notes |
|-------|------|-------|
| id | uuid (PK) | |
| working_copy_id | uuid (FK→WorkingCopy, ON DELETE CASCADE) | isolation scope (FR-022) |
| status | enum(`queued`,`running`,`completed`,`failed`) | lifecycle (D7) |
| model_version | text | bundled Zingg model id + field-def version (D2) |
| confidence_floor | double | min `z_maxScore` presented; precision default (D5) |
| cluster_count | integer (nullable) | set on `completed` (size-≥2 clusters) |
| params | jsonb (nullable) | redacted run config (numPartitions, blocking, etc.) |
| last_error | text (nullable) | redacted on `failed` (D10) |
| created_at | timestamptz | enqueue time |
| started_at / finished_at | timestamptz (nullable) | worker claim / terminal |

- **State transitions**: `queued → running → completed | failed`. Clusters are exposed only when
  `completed` (FR-006).
- **Concurrency invariant (FR-007)**: **partial unique index** on `working_copy_id` WHERE
  `status IN ('queued','running')` ⇒ at most one active run per working copy.
- **Supersede rule (FR-008)**: when a run reaches `completed`, any prior run's still-`pending`
  clusters for the same working copy transition to `superseded`.
- **Relationships**: 1→N `DuplicateCluster`.

## Entity: DuplicateCluster

A group of ≥2 working-copy contacts Zingg believes are the same person, within one run.

| Field | Type | Notes |
|-------|------|-------|
| id | uuid (PK) | |
| dedup_run_id | uuid (FK→DedupRun, ON DELETE CASCADE) | |
| working_copy_id | uuid (FK→WorkingCopy, ON DELETE CASCADE) | denormalised for isolation queries |
| z_cluster_key | text | Zingg `z_cluster` value (provenance) |
| confidence | double | = `z_maxScore` (FR-005, D5) |
| min_score | double (nullable) | = `z_minScore`; weak-link signal |
| size | integer | member count (≥2) |
| status | enum(`pending`,`merged`,`dismissed`,`superseded`) | resolution state |
| resolved_at | timestamptz (nullable) | set on merge/dismiss |
| created_at | timestamptz | ingest time |

- **State transitions**: `pending → merged` (FR-016) · `pending → dismissed` (FR-019, per-run only) ·
  `pending → superseded` (FR-008). `merged → pending` only via the `MergeRecord` undo path (D6) — see
  MergeRecord. (`pending`/`merged`/`dismissed`/`superseded` are the only states.)
- **Ordering**: presented `ORDER BY confidence DESC` (FR-011).
- **Index**: (`dedup_run_id`, `status`, `confidence`).
- **Relationships**: 1→N `ClusterMember`; 0..1 `MergeRecord` (when merged).

## Entity: ClusterMember

Association of a cluster to one working-copy contact it contains.

| Field | Type | Notes |
|-------|------|-------|
| id | uuid (PK) | |
| cluster_id | uuid (FK→DuplicateCluster, ON DELETE CASCADE) | |
| working_copy_contact_id | uuid (FK→WorkingCopyContact, ON DELETE CASCADE) | the actual contact (D4) |
| match_score | double (nullable) | per-row Zingg score, if available |
| is_survivor | boolean default false | set true on the survivor at merge time (D6) |

- **Uniqueness**: (`cluster_id`, `working_copy_contact_id`) unique.
- **Rule**: members reference **working-copy** contacts only — never `SnapshotContact` (Principle II).
- **Index**: (`working_copy_contact_id`) to detect "member no longer active" on resolve (FR-020).

## Entity: MergeRecord  *(reversible merge log)*

Captures one confirmed merge so it can be undone exactly (D6).

| Field | Type | Notes |
|-------|------|-------|
| id | uuid (PK) | |
| cluster_id | uuid (FK→DuplicateCluster, ON DELETE CASCADE, unique) | one merge per cluster |
| working_copy_id | uuid (FK→WorkingCopy, ON DELETE CASCADE) | isolation |
| survivor_contact_id | uuid (FK→WorkingCopyContact) | the kept contact (FR-016) |
| survivor_payload_before | jsonb | survivor's pre-merge payload (restore on undo) |
| merged_payload | jsonb | payload written to the survivor on confirm |
| retired_member_ids | uuid[] | non-survivor contacts set to `retired` |
| status | enum(`active`,`undone`) default `active` | `undone` after a successful undo |
| created_at | timestamptz | merge time |
| undone_at | timestamptz (nullable) | set on undo |

- **Undo (FR-018, SC-003)**: restore `survivor_payload_before` to the survivor, flip
  `retired_member_ids` back to `status='active'`, set this record `undone`, and set the cluster back
  to `pending` (the run's result is re-actionable).
- **Rule**: never references or mutates the snapshot; pure working-copy state.

## Entity: AuditEntry  *(existing — extended)*

No schema change; new `action` values appended (D10):
`dedup.run.started`, `dedup.run.completed`, `dedup.run.failed`, `cluster.merged`, `merge.undone`,
`cluster.dismissed`.

- `target_type` ∈ {`dedup_run`, `duplicate_cluster`, `working_copy`}; `source_ref` carries the run
  for cluster actions. `details` is redacted (counts, `model_version`, `confidence`) — never payloads
  or secrets (FR-021, SC-006).

## Staging (transient, run-scoped — not domain state)

- **`dedup_match_raw`**: Zingg's JDBC output sink for a run (`wcc_id`, `z_cluster`, `z_minScore`,
  `z_maxScore`, + flattened columns). Read once by the dedup worker to build clusters, then cleared.
  Not exposed by any API; never contains secrets.
- **Input projection** (`dedup_input_<run>` table or parameterised query): flattened, read-only
  view of the run's `active` working-copy contacts for Zingg's input pipe (D3/D4).

---

## Entity-Relationship summary

```text
WorkingCopy 1───N DedupRun 1───N DuplicateCluster 1───N ClusterMember ──→ WorkingCopyContact(active|retired)
                                        │
                                        └──0..1 MergeRecord ──→ survivor WorkingCopyContact
AuditEntry  (append-only; dedup.run.* / cluster.merged / merge.undone / cluster.dismissed)

(Snapshot / SnapshotContact: untouched — read-only foundation from feature 001)
```

## Validation & invariant checklist (for tests)

- A `completed` run with no size-≥2 clusters reports `cluster_count = 0` (US1 #3).
- At most one `queued`/`running` `DedupRun` per `working_copy_id` (FR-007 partial unique index).
- A merge: survivor `payload` updated, non-survivors `retired`, `MergeRecord` written, cluster
  `merged`, audit `cluster.merged` — snapshot unchanged (FR-016, SC-004).
- Undo restores survivor payload + retired members exactly; repeated merge/undo cycles return the
  working copy's `active` set to its pre-dedup state (SC-003).
- Resolving a cluster whose members are no longer all `active` is blocked (FR-020).
- Dismiss affects only its run; a later run re-creates a fresh cluster for the same pair (per-run
  dismissals, D7).
- No cluster transitions to `merged`/`dismissed` without an explicit operator action (SC-005).
- All run/cluster/merge access is scoped by `working_copy_id`; a cross-account/cross-working-copy id
  returns not-found and never another account's data (FR-022).
- Resolving a `superseded` cluster is rejected (only `pending` clusters are resolvable) (FR-008).
