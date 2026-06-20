# Quickstart & Validation: Tinder-Style Contact Swipe Triage

**Feature**: `003-tinder-swipe-triage` · **Date**: 2026-06-20

Runnable scenarios that prove the feature end-to-end. References: [spec.md](spec.md),
[plan.md](plan.md), [data-model.md](data-model.md), [contracts/openapi.yaml](contracts/openapi.yaml).
No live Google in CI — the `PeopleWriteClient` seam is faked (Principle IV).

## Prerequisites

- A working copy in `ready` status with `active` `working_copy_contact` survivors (from features 001
  → 002). Dedup is **not** required (D2), but the intended flow is post-dedup survivors.
- Backend, `db`, and `worker` services running (docker-compose). No new container is needed.
- For the **real** delete path only (outside CI): the `Account` must have granted the Google
  `https://www.googleapis.com/auth/contacts` write scope via incremental consent (D9). CI/local
  validation uses the fake write client and needs no scope.

## Setup

```bash
# Backend deps + DB migration (adds 0003 triage/delete tables + new audit actions)
cd backend
uv sync            # or: pip install -e .
alembic upgrade head

# Frontend deps
cd ../frontend
pnpm install
```

Config (backend `.env`): the delete capability adds an opt-in write scope and reuses the existing
worker. CI keeps `PEOPLE_WRITE_CLIENT=fake` (default). See `core/config.py`.

## Run the test suites (primary validation)

```bash
# Backend — contract + integration + unit (no live Google; fake write seam)
cd backend
rtk pytest                      # all green
rtk pytest -m "not slow"        # default CI lane (excludes the real-Google integration test)

# Frontend — swipe deck, processing queue, delete review
cd ../frontend
rtk vitest run
rtk lint                        # Biome gate (must pass — Constitution Quality Gate)
```

## Scenario 1 — Rapid swipe triage (US1, P1)

1. `POST /api/working-copies/{id}/triage-sessions` → a `TriageSession` (`in_progress`) with a summary
   whose `total` = number of `active` survivors and `remaining` = `total`.
2. `GET /api/triage-sessions/{sid}/deck?limit=10` → the first undecided cards in stable order
   (`lower(display_name), id`).
3. For each card, `PUT /api/triage-sessions/{sid}/decisions/{contactId}` with `{"outcome":"keep"}`,
   `{"outcome":"delete"}`, or `{"outcome":"process"}`.
   - **Expected**: `remaining` decreases; `delete` writes nothing to Google; `process` creates a
     `pending` ProcessingItem and opens **no** editor.
4. Re-decide: `PUT …/decisions/{contactId}` again with a new outcome → the single decision row updates
   (latest wins); `DELETE …/decisions/{contactId}` returns the contact to undecided.
5. Re-open the session (new `GET /deck`) → resumes at the next undecided contact; all prior decisions
   intact (**SC-003**).
6. When every active contact has a terminal decision and no pending ProcessingItem remains, the session
   is `complete` and `GET /triage-sessions/{sid}` returns a summary with counts per outcome (**SC-006**).

**Pass when**: decisions persist across reload, re-decide works, nothing hit Google, and the summary
counts are correct.

## Scenario 2 — Processing queue: edit & transliterate (US2, P2)

1. `GET /api/triage-sessions/{sid}/processing?status=pending` → the contacts sent to processing.
2. `GET /api/processing-items/{itemId}` → includes a `transliterationSuggestion` for Latin names
   (`hasSuggestion=false` for empty/already-Cyrillic names — **FR-017**).
3. Transliterate: `POST /api/working-copy-contacts/{contactId}/transliteration` with the accepted (or
   corrected) `fields` → a `StagedEdit(kind=transliterate)`; only **name fields** change (**FR-014**).
4. Edit: `PUT /api/working-copy-contacts/{contactId}/edits` with an edited `payload` →
   `StagedEdit(kind=edit)`.
5. `POST /api/processing-items/{itemId}/done` → item `done`; the contact's decision **defaults to
   keep** (re-decidable) (**D4**).
6. Undo: `POST /api/staged-edits/{editId}/undo` → contact payload restored exactly (**SC-004**).

**Pass when**: suggestions appear for Latin names only, accepted changes touch only name fields,
edits/transliterations are reversible, and processed contacts become terminal-keep.

## Scenario 3 — Delete batch → Google commit & undo (US3, P3)

1. `POST /api/working-copies/{id}/delete-batches` → a `DeleteBatch` (`staged`); a `DeletionRecord` with
   `payload_before` (full snapshot) is captured for **every** queued contact **before** any Google call
   (**SC-002**).
2. `GET /api/delete-batches/{bid}/preview` → dry-run list of exactly the contacts to be deleted; still
   nothing sent to Google (**FR-019**).
3. `POST /api/delete-batches/{bid}/confirm`:
   - Without the write scope → `403` prompting re-consent (**D9**).
   - With the scope → `202`, status `committing`; the `delete_worker` calls `deleteContact` per record.
4. Watch `GET /api/delete-batches/{bid}` → `committed`; each record `deleted`, or `skipped_absent` if
   the contact was already gone in Google (**FR-024**). Re-running is idempotent (**FR-022**).
5. Undo: `POST /api/delete-batches/{bid}/undo` → `202`; the worker re-creates each contact from
   `payload_before` (records `restored` with the new resource name) (**FR-023**).

**Pass when** (with the fake write client in CI): snapshots precede deletes, confirm is scope-gated,
deletes are idempotent and audited, and undo restores every contact.

## Audit & isolation checks (Principles I & V)

- After each scenario, `audit_entry` contains the matching actions (`contact.queued_delete`,
  `contact.transliterated`, `delete.batch.committed`, `contact.deleted`, `contact.restored`, …) with
  **no** payloads, names, or secrets in `details` (**SC-007**).
- Requesting another account's / working copy's session, contact, or batch id returns `404` — never
  another account's data (**FR-010**).
- Grep logs/responses: no tokens, no contact PII (reuse feature 001's security-hardening assertion).
