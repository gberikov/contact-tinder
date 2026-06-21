# Phase 1 Data Model: Validate & Normalize (Tidy)

Two new persisted entities (`validation_run`, `validation_item`) plus **reuse** of the existing
`StagedEdit` (feature 003) for all mutations. Migration: `0005_validate_normalize`. No existing table
is altered (the only change is widening `StagedEdit.kind`'s allowed *value set* to include
`normalize` — the column is already `String(16)`, so there is no DDL change). Cross-dialect
(Postgres + SQLite for tests): JSON via `JsonB`, like features 002–004.

## Enumerations (string sets, cross-dialect)

```
VALIDATION_RUN_STATES = ("queued", "running", "completed", "failed")
FIELD_KINDS           = ("phone", "email", "website")
ISSUE_TYPES = (
    "invalid_phone",        # phone unparseable / not valid for the region
    "unclear_type",         # valid phone, missing type, not confidently mobile
    "invalid_email",        # email syntactically invalid
    "dead_email_domain",    # email domain has no MX record
    "website_unreachable",  # transport-level failure (DNS/connect/TLS/timeout)
    "website_unsafe",       # SSRF guard: resolves to a non-public address
)
VALIDATION_ITEM_STATES = ("pending", "resolved", "skipped")
# StagedEdit.kind widened: ("edit", "transliterate", "normalize")
```

## Entity: `validation_run`

One execution of the validation/normalization pass over a Draft's kept contacts (spec: *Tidy run*).

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID PK | |
| `working_copy_id` | UUID FK → `working_copy.id` `ON DELETE CASCADE` | the active Draft |
| `session_id` | UUID FK → `triage_session.id` `ON DELETE SET NULL`, nullable | the Review session whose keep-decisions define the kept set |
| `status` | `String(16)` | `queued \| running \| completed \| failed` (default `queued`) |
| `default_region` | `String(2)`, nullable | ISO-3166 region used to parse national-format phones (D2) |
| `checked_count` | Integer default 0 | field values examined (FR-020) |
| `auto_applied_count` | Integer default 0 | auto-fixes staged (FR-020) |
| `queued_count` | Integer default 0 | items needing manual attention (FR-020) |
| `last_error` | `Text`, nullable | redacted failure message (FR-005, Principle V) |
| `created_at` | tz datetime | |
| `started_at` | tz datetime, nullable | set when the worker claims it |
| `completed_at` | tz datetime, nullable | terminal timestamp |

Index: `ix_validation_run_copy_status (working_copy_id, status)` — latest-run lookup per Draft
(mirrors `ix_export_run_copy_status`). Relationship: `items` → `ValidationItem` (cascade
all, delete-orphan).

**Derived (not stored)**: `ValidationRunOut.pendingCount` = live
`COUNT(validation_item WHERE status='pending')`, computed at serialization time. `queued_count` (the
total items the run created) **is** stored; `pendingCount` shrinks as items are resolved/skipped.

**Kept set**: contacts in `working_copy_id` whose latest `TriageDecision.outcome != 'delete'` for
`session_id` (i.e. `keep`/`process`, or no decision = survivor). Excludes deletions (FR-006).

## Entity: `validation_item`

One finding needing a human decision (spec: *queue item*).

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID PK | |
| `validation_run_id` | UUID FK → `validation_run.id` `ON DELETE CASCADE` | |
| `working_copy_contact_id` | UUID FK → `working_copy_contact.id` `ON DELETE CASCADE` | the contact |
| `field_kind` | `String(8)` | `phone \| email \| website` |
| `field_index` | Integer | position within that field's array in the payload (locates the value) |
| `issue_type` | `String(24)` | one of `ISSUE_TYPES` |
| `original_value` | `Text` | the value as stored (display + locate) |
| `suggested_value` | `Text`, nullable | optional suggestion (e.g. a normalized phone for an unclear-type item) |
| `status` | `String(16)` | `pending \| resolved \| skipped` (default `pending`) |
| `resolution` | `JsonB`, nullable | what the operator chose (e.g. `{"action":"set_type","type":"work"}`) |
| `staged_edit_id` | UUID FK → `staged_edit.id` `ON DELETE SET NULL`, nullable | the StagedEdit a resolution produced (traceable undo) |
| `created_at` | tz datetime | |
| `resolved_at` | tz datetime, nullable | |

Indexes: `ix_validation_item_run_status (validation_run_id, status)` — pending-queue listing.

## Reused entity: `StagedEdit` (feature 003 — unchanged shape)

All Tidy mutations are `StagedEdit` rows with `kind="normalize"` (auto-fixes) or `kind="edit"`/
`"normalize"` (queue resolutions). `payload_before`/`payload_after` hold the whole contact payload;
`undo_staged_edit` reverts `payload`. No new columns. See `models/triage.py`.

## Auto-vs-queue decision table (authoritative)

| Field | Condition | Action |
|-------|-----------|--------|
| phone | unparseable / `is_valid_number == False` | queue `invalid_phone` |
| phone | valid; E.164 ≠ stored | **auto** StagedEdit → E.164 (FR-009) |
| phone | valid; no type; `number_type == MOBILE` | **auto** StagedEdit → type `mobile` (FR-010) |
| phone | valid; no type; not confidently mobile | queue `unclear_type` (suggest E.164; choose type) |
| email | syntax invalid | queue `invalid_email` |
| email | syntax ok; domain has no MX | queue `dead_email_domain` |
| email | syntax ok; domain has MX | no action (valid) |
| website | resolves to non-public IP (any hop) | queue `website_unsafe` — never fetched (FR-029) |
| website | reachable; canonical URL (scheme added and/or https) ≠ stored | **auto** StagedEdit → canonical (FR-015) |
| website | scheme-less but host reachable | **auto** StagedEdit → add scheme (FR-015) |
| website | transport failure (DNS/connect/TLS/timeout) | queue `website_unreachable` (FR-016) |
| website | reachable; canonical already equals stored | no action |

A single contact may yield several auto-fixes **and** several queue items across its fields (FR-007).

## Run state machine

```
queued ──(worker claims, FOR UPDATE SKIP LOCKED)──▶ running
running ──(pass finishes)─────────────────────────▶ completed   (counts populated; queue may be non-empty)
running ──(unhandled error)───────────────────────▶ failed      (last_error set; retry offered, FR-005)
running ──(worker restart)────────────────────────▶ running     (re-claimed, resumes — D8)
```

Item lifecycle: `pending → resolved` (operator applies an action → StagedEdit, `staged_edit_id` set)
or `pending → skipped` (left unchanged, FR-019). Undo of a resolution reverts its `StagedEdit`; the
item may be re-resolved.

## Derivation for the wizard (client-side, extends 005 `data-model`)

| Step | Active artifact | API used | `completed` predicate | `running` predicate |
|------|-----------------|----------|------------------------|---------------------|
| Tidy | `ValidationRun` | `listValidationRuns(workingCopyId)` (newest-first), `getValidationRun(id)` | latest run `status === 'completed'` | latest run `status === 'running'` |

- `tidy` is inserted at **index 6**; **Export** becomes index 7 with `prerequisiteKey = 'tidy'`.
- `passable('tidy')` is **always true** (passable with a warning when `pendingCount` of unresolved
  items > 0 — FR-004), joining `review` in the always-passable set. `pendingCount` is a **derived**
  live count of `validation_item` rows with `status='pending'` (not a stored column).
- `emptyButPassable('tidy')` = latest run `completed` with `auto_applied_count == 0` and zero pending
  items (nothing to fix — renders the "nothing to clean" empty state).
- Switching the active Draft re-derives Tidy and never destroys another branch's run/items
  (edge case *Changing an upstream selection*).

## Settings (env, `core/config.py`)

| Setting | Default | Purpose |
|---------|---------|---------|
| `phone_default_region` | `"KZ"` | fallback region when a run supplies none (D2) |
| `website_check_timeout_seconds` | `5.0` | per-request time limit (SC-008) |
| `website_check_concurrency` | `8` | bounded async fan-out (D8) |
| `website_check_max_redirects` | `5` | redirect-hop cap (D5/D6) |
| `geoip_db_path` | `""` | optional local GeoLite2-Country DB for region detection (D3) |

No OAuth scope, token, or audit-path change. The region the operator actually picks lives client-side
(localStorage) and is passed per run as `default_region` (D2).
