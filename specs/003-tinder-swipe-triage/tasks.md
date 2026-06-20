---
description: "Task list for feature 003-tinder-swipe-triage implementation"
---

# Tasks: Tinder-Style Contact Swipe Triage

**Input**: Design documents from `/specs/003-tinder-swipe-triage/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml, quickstart.md

**Tests**: INCLUDED — the constitution makes TDD NON-NEGOTIABLE (Principle IV). Decision/resume,
staged-edit undo, transliteration, snapshot-before-delete, idempotent deletes, and the Google **write
seam** all get failing-first tests. The live Google API is exercised only behind the
`PeopleWriteClient` seam (CI uses `FakePeopleWriteClient`; no live Google in the default lane).

**Organization**: Tasks grouped by user story (US1 P1 → US2 P2 → US3 P3) for independent
implementation and testing. Builds on features 001 (snapshots & working copies) and 002 (dedup) — those
tables/services exist; the deck is the `active` `working_copy_contact` survivors.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 (setup, foundational, polish carry no story label)
- Exact file paths included.

## Path Conventions

Web app (per plan.md): backend at `backend/src/`, frontend at `frontend/src/`, tests at
`backend/tests/` and `frontend/tests/`. **No new container** — the delete worker runs in the existing
`worker` service.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Configuration and scaffolding without domain logic.

- [X] T001 Add feature-003 config to `backend/src/core/config.py`: a `PEOPLE_WRITE_CLIENT=fake|google`
  selector (default `fake` for CI), the incremental Google `https://www.googleapis.com/auth/contacts`
  write scope as an **opt-in** value (NOT added to the default `google_scopes`; requested only on
  delete enablement — research D9), and a documented note that delete/edit undo has **no expiry**
  (life of the working copy — research D12).
- [X] T002 [P] Scaffold the frontend triage routes/nav: add `WorkingCopyTriage`, `Processing`, and
  `DeleteReview` routes to `frontend/src/router/index.ts` and a nav entry (empty page stubs for now).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared schema, audit helpers, and the router/schema wiring. **No user story can start
until this phase is complete.**

**⚠️ CRITICAL**: Blocks all of Phase 3+.

- [X] T003 Create triage models in `backend/src/models/triage.py`: `TriageSession`, `TriageDecision`,
  `ProcessingItem`, `StagedEdit`, `DeleteBatch`, `DeletionRecord` (fields/enums/indexes per
  data-model.md), and register them in `backend/src/models/__init__.py`.
- [X] T004 Create the Alembic migration `backend/migrations/versions/0003_tinder_swipe_triage.py` for
  the six new tables, with: the **partial unique index** on `triage_session(working_copy_id) WHERE
  status='in_progress'` (D11); unique `(session_id, working_copy_contact_id)` on `triage_decision` and
  `processing_item`; unique `(delete_batch_id, origin_resource_name)` on `deletion_record`; and the
  listing indexes from data-model.md. No change to existing tables.
- [X] T005 [P] Extend `backend/src/services/audit_service.py` with helpers for the new actions
  (`triage.session.started/completed`, `contact.kept/queued_delete/sent_processing`, `contact.edited`,
  `contact.transliterated`, `edit.undone`, `delete.batch.previewed/committed`, `contact.deleted`,
  `contact.restored`) — redacted details only, never payloads/names/secrets (FR-025/026).
- [X] T006 Register a `triage` router and add triage Pydantic schemas: create
  `backend/src/api/routers/triage.py` (empty router wired into `backend/src/api/main.py`) and add the
  request/response models from `contracts/openapi.yaml` to `backend/src/api/schemas.py`.

**Checkpoint**: Schema migrated, audit + router wiring ready — stories can begin.

---

## Phase 3: User Story 1 — Rapid swipe triage of survivors (Priority: P1) 🎯 MVP

**Goal**: Operator opens a session over the active survivors and swipes each contact keep / delete /
process, with immediate advance, stable order, resume, re-decide, and a completion summary — writing
nothing to Google.

**Independent Test**: On a working copy with active survivors, open a session, swipe each card, close
and reopen → decisions persisted and resume at the next undecided contact; re-decide updates the
outcome; nothing reaches Google; the summary counts match.

### Tests for User Story 1 (write first, must FAIL) ⚠️

- [X] T007 [P] [US1] Contract test for `openTriageSession`/`listTriageSessions`/`getTriageSession`/
  `getDeck`/`setDecision`/`undoDecision` in `backend/tests/contract/test_triage_sessions_api.py`
  (200 vs 201 open, deck shape + stable order, PUT 200, DELETE 204, 409 non-active contact, 404
  cross-account).
- [X] T008 [P] [US1] Integration test in `backend/tests/integration/test_triage_swipe_resume.py`:
  decisions persist across reload; resume returns the next undecided contact in `lower(display_name),
  id` order; summary counts (keep/delete/processing/remaining) are correct; zero Google calls (US1
  AS#1–5/#7, SC-003/006, D1/D13).
- [X] T009 [P] [US1] Integration test in `backend/tests/integration/test_triage_redecide.py`:
  re-deciding updates the single `TriageDecision` row (latest wins) and appends an audit entry; `DELETE`
  returns the contact to undecided (FR-006, D3, US1 AS#6).
- [X] T010 [P] [US1] Integration test in `backend/tests/integration/test_triage_isolation.py`:
  sessions/decks/decisions for working copy A are invisible/non-actionable from another account or
  working copy — cross-account ids return not-found, never another account's data (FR-010, Principle I).
- [X] T011 [P] [US1] Unit test in `backend/tests/unit/test_triage_units.py`: deck ordering + cursor
  paging, and the completion predicate (complete only when every active contact is terminal
  keep/delete and no pending ProcessingItem remains) (D1/D3/D4).
- [X] T011a [P] [US1] Integration test in `backend/tests/integration/test_triage_stale_deck.py`:
  when survivors change after a session starts (a contact is retired by a dedup re-run), the deck/
  summary reflect current `active` rows, the user is informed, and a decision for a now-inactive
  contact is excluded from terminal actions rather than silently lost (FR-027, D11, edge "Working copy
  changes underneath").

### Implementation for User Story 1

- [X] T012 [US1] Implement `triage_service` in `backend/src/services/triage_service.py`: open/resume a
  session (guarded by the one-`in_progress`-per-working-copy partial unique index), the deck query
  (active survivors, stable order, opaque cursor), record/re-decide an outcome (upsert one row, audit
  the change; `process` creates/updates a pending `ProcessingItem`), undo a decision, and the
  completion + summary computation. Compute the deck/summary from current `active` survivors each load
  so a working-copy change after start is reflected and surfaced, and a decision for a now-inactive
  contact is excluded from terminal actions (FR-027). All access scoped by `working_copy_id`/
  `account_id` (FR-001..010/027, D1/D3/D11/D13).
- [X] T013 [US1] Implement the session/deck/decision endpoints in `backend/src/api/routers/triage.py`:
  `POST`/`GET /working-copies/{id}/triage-sessions`, `GET /triage-sessions/{sid}`,
  `GET /triage-sessions/{sid}/deck`, `PUT`/`DELETE /triage-sessions/{sid}/decisions/{contactId}`
  (contracts/openapi.yaml).
- [X] T014 [P] [US1] Frontend swipe surface: `frontend/src/services/triage.ts` (typed client),
  `frontend/src/stores/triage.ts` (Pinia: session + deck prefetch + **optimistic** decide + resume),
  and `frontend/src/components/SwipeDeck.vue`, `ContactCard.vue`, `SwipeControls.vue`,
  `CompletionSummary.vue` on `frontend/src/pages/WorkingCopyTriage.vue`.
- [X] T015 [P] [US1] Frontend test `frontend/tests/triage-swipe.spec.ts` (Vitest + Vue Test Utils):
  swipe right/left/up map to keep/delete/process, the card advances optimistically, re-open resumes at
  the next undecided card.

**Checkpoint**: Swipe triage works end-to-end with persistence/resume; nothing hits Google — MVP demoable.

---

## Phase 4: User Story 2 — Post-swipe processing queue: edit & transliterate (Priority: P2)

**Goal**: Operator opens the processing queue, edits cards and/or accepts reviewed Latin→Cyrillic name
suggestions; changes are staged against the working copy and reversible; a processed contact defaults
to a terminal keep.

**Independent Test**: With contacts tagged for processing, open the queue, accept a transliteration for
one (only name fields change) and edit another; both stage reversible `StagedEdit`s, persist on reload,
mark the item done (decision → keep), and undo restores exactly.

### Tests for User Story 2 (write first, must FAIL) ⚠️

- [X] T016 [P] [US2] Contract test for `listProcessing`/`getProcessingItem`/`completeProcessingItem`/
  `getTransliterationSuggestion`/`applyEdit`/`acceptTransliteration`/`undoStagedEdit` in
  `backend/tests/contract/test_processing_api.py` (queue listing, item w/ suggestion, 200s, 409 on
  already-undone edit).
- [X] T017 [P] [US2] Integration test in `backend/tests/integration/test_processing_flow.py`:
  a `process` swipe creates a pending item with no editor; accepting a transliteration changes **only
  name fields** and stages `StagedEdit(kind=transliterate)`; editing stages `StagedEdit(kind=edit)`;
  marking done defaults the decision to `keep` (re-decidable); undo restores the prior payload exactly
  (FR-011/013/014/015/016, D4/D6, SC-004).
- [X] T018 [P] [US2] Unit test in `backend/tests/unit/test_transliteration.py` (table-driven): digraphs
  (`sh→ш`, `ch→ч`, `zh→ж`, `kh→х`, `ts→ц`, `ya→я`, `yo→ё`), case preservation, already-Cyrillic
  passthrough, empty-name no-op (FR-017, D5).

### Implementation for User Story 2

- [X] T019 [P] [US2] Implement the pure transliterator in `backend/src/services/transliteration.py`:
  deterministic Latin→Cyrillic for name fields, longest-match digraphs, case-preserving, no I/O;
  returns "no suggestion" for empty/already-Cyrillic input (D5).
- [X] T020 [US2] Implement `processing_service` in `backend/src/services/processing_service.py`: list the
  queue, compute a transliteration suggestion, apply an edit (`StagedEdit(kind=edit)` + payload write),
  accept a transliteration (`StagedEdit(kind=transliterate)`, name fields only), mark an item done
  (default the contact's decision to `keep`), and undo a `StagedEdit` (restore `payload_before`); audit
  each action (FR-012..016, D4/D6).
- [X] T021 [US2] Implement the processing/edit/transliteration endpoints in
  `backend/src/api/routers/triage.py`: `GET /triage-sessions/{sid}/processing`,
  `GET /processing-items/{id}`, `POST /processing-items/{id}/done`,
  `GET /working-copy-contacts/{id}/transliteration-suggestion`,
  `PUT /working-copy-contacts/{id}/edits`, `POST /working-copy-contacts/{id}/transliteration`,
  `POST /staged-edits/{id}/undo` (contracts/openapi.yaml).
- [X] T022 [P] [US2] Frontend processing UI: `frontend/src/components/ProcessingQueue.vue`,
  `EditCardForm.vue`, `TransliterationReview.vue` on `frontend/src/pages/Processing.vue`, wired into
  `stores/triage.ts` and `services/triage.ts`.
- [X] T023 [P] [US2] Frontend test `frontend/tests/processing-queue.spec.ts`: suggestion shown for
  Latin names only, accepting stages a change, editing stages a change, marking done removes the item
  and the contact reads as keep.

**Checkpoint**: US1 + US2 both work independently — fast triage plus deferred edit/transliterate.

---

## Phase 5: User Story 3 — Review & commit the delete batch to Google (Priority: P3)

**Goal**: Operator reviews queued deletions as a batch: dry-run preview, a restorable snapshot of every
contact persisted before any Google call, explicit per-batch confirmation (scope-gated), idempotent
deletion via the worker, and undo that re-creates contacts.

**Independent Test** (fake write client): build a batch from delete decisions → preview lists exactly
those contacts and a `payload_before` is stored for each before any delete → confirm (403 without the
write scope; 202 with it) → records become `deleted`/`skipped_absent` → re-run is idempotent → undo
re-creates every contact; the source snapshot is untouched throughout.

### Tests for User Story 3 (write first, must FAIL) ⚠️

- [X] T024 [P] [US3] Contract test for `createDeleteBatch`/`getDeleteBatch`/`previewDeleteBatch`/
  `confirmDeleteBatch`/`undoDeleteBatch` in `backend/tests/contract/test_delete_batch_api.py`
  (201/409 empty, preview list shape, confirm 202/403-no-scope/409-state, undo 202/409).
- [X] T025 [P] [US3] Integration test in `backend/tests/integration/test_delete_batch.py` (fake write
  client): build → a `DeletionRecord.payload_before` exists for **every** queued contact **before** any
  delete call (SC-002) → preview → confirm → worker marks records `deleted`; a contact missing in Google
  → `skipped_absent` (success) (FR-019/020/021/024).
- [X] T026 [P] [US3] Integration test in `backend/tests/integration/test_delete_idempotency.py`:
  re-processing a batch never re-deletes `deleted`/`skipped_absent` records; a forced transient failure
  leaves a `failed` record that a retry completes (FR-022, D8/D10).
- [X] T027 [P] [US3] Integration test in `backend/tests/integration/test_delete_scope_undo.py`:
  confirm without the `contacts` write scope → `403` prompting re-consent (D9); undo re-creates each
  contact via the fake `createContact`, records `restored` with the new resource name, and reactivates
  the working-copy contact (FR-023).
- [X] T028 [P] [US3] Integration test in `backend/tests/integration/test_delete_snapshot_immutable.py`:
  the source `snapshot`/`snapshot_contact` rows are byte-identical before/after a batch commit and undo
  (Principle II).

### Implementation for User Story 3

- [X] T029 [P] [US3] Extend `backend/src/integrations/people_client.py` with a `PeopleWriteClient`
  protocol (`delete_contact(resource_name)`, `create_contact(payload) -> resource_name`), a
  `GooglePeopleWriteClient` (maps 404→absent, 429/5xx→typed retryable errors), and a
  `FakePeopleWriteClient` for CI; select via `PEOPLE_WRITE_CLIENT` config (D8/D9).
- [X] T030 [US3] Implement `delete_batch_service` in `backend/src/services/delete_batch_service.py`:
  build a batch from the session's `delete` decisions — including only contacts still `active`
  (a now-inactive contact is excluded and surfaced, not deleted — FR-027), **capturing `payload_before`
  + resource name for every record before anything else** (SC-002); dry-run preview; confirm (reject with 403 if the
  account lacks the write scope, else enqueue → `committing`); undo (enqueue re-create); audit
  `delete.batch.previewed/committed`, `contact.deleted/restored` (FR-018..024, D8/D9).
- [X] T031 [US3] Implement the PG-backed `delete_worker` in `backend/src/workers/delete_worker.py`:
  claim a `committing`/undoing `DeleteBatch` with `FOR UPDATE SKIP LOCKED`, process each
  `DeletionRecord` idempotently (`deleteContact`; 404 → `skipped_absent`; retry/backoff on
  rate-limit/transient; redacted errors), update batch counts/status, and re-create on undo; wire its
  invocation into the existing `worker` service in `docker-compose.yml` (no new container) (D10).
- [X] T032 [US3] Implement the delete-batch endpoints in `backend/src/api/routers/triage.py`:
  `POST /working-copies/{id}/delete-batches`, `GET /delete-batches/{id}`,
  `GET /delete-batches/{id}/preview`, `POST /delete-batches/{id}/confirm`,
  `POST /delete-batches/{id}/undo` (contracts/openapi.yaml).
- [X] T033 [P] [US3] Frontend delete review UI: `frontend/src/components/DeleteBatchReview.vue` on
  `frontend/src/pages/DeleteReview.vue` (dry-run preview list, explicit confirm, write-scope
  re-consent prompt on 403, undo), wired into `stores/triage.ts` and `services/triage.ts`.
- [X] T034 [P] [US3] Frontend test `frontend/tests/delete-review.spec.ts`: preview lists the contacts,
  confirm requires an explicit action and surfaces the re-consent prompt on 403, undo restores.

**Checkpoint**: All three stories independently functional — swipe, process, and safely delete.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verification, hardening, and docs spanning all stories.

- [X] T035 [P] Audit-redaction integration test in
  `backend/tests/integration/test_triage_audit_redaction.py`: every decision/edit/transliteration/
  delete/restore is audited with no payloads, names, or secrets in `details` (SC-007, FR-026).
- [X] T036 [P] Swipe-latency proxy in `frontend/tests/triage-swipe.spec.ts` (extend): assert the deck
  prefetches the next card and decisions advance optimistically (no blocking network in the swipe
  path) — the buildable proxy for SC-001's <3 s median; document the assumption in the test.
- [X] T037 Security hardening pass: assert the `contacts` write scope is requested **only** via
  incremental consent (never in the default `google_scopes`), no tokens/PII in logs or API responses,
  and per-account/per-working-copy isolation across triage, processing, and delete batches
  (Principles I & V; reuse feature 001's hardening assertion).
- [ ] T038 Run `quickstart.md` Scenarios 1–3 end-to-end against docker-compose with the fake write
  client; confirm the delete worker runs inside the existing `worker` service and the real Google
  write path is documented (no live calls in CI).
- [X] T039 Run the full gate: `pytest -q` (fake write client), `frontend` Vitest, and `npx biome ci .`
  — all green (constitution quality gate).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup — **BLOCKS all user stories**.
- **User Stories (Phase 3–5)**: all depend on Foundational. US1 → US2 → US3 in priority order; US2
  consumes US1's `process` items and US3 consumes US1's `delete` decisions, but each remains
  independently testable with seeded data.
- **Polish (Phase 6)**: depends on the desired stories being complete.

### User Story Dependencies

- **US1 (P1)**: only Foundational. Delivers the MVP (swipe triage with persistence/resume).
- **US2 (P2)**: Foundational; consumes US1 `process` items (seedable independently).
- **US3 (P3)**: Foundational; consumes US1 `delete` decisions (seedable independently).

### Within Each User Story

- Tests written first and FAIL before implementation (Principle IV).
- Models (Foundational) → services → endpoints → frontend.
- `triage_service`/`processing_service`/`delete_batch_service` before their routers; routers before
  frontend wiring; the `PeopleWriteClient` seam (T029) before the delete worker/service (T030/T031).

### Parallel Opportunities

- Setup: T001, T002 in parallel.
- Foundational: T005 parallel to T003/T004; T006 after T003.
- US1 tests T007–T011 in parallel; frontend T014/T015 parallel to backend service work once endpoints exist.
- US2 tests T016–T018 in parallel; T019 (pure transliterator) parallel to everything.
- US3 tests T024–T028 in parallel; T029 (write seam) parallel to test-writing.
- Polish: T035, T036 in parallel.

---

## Parallel Example: User Story 1

```bash
# Tests first (parallel):
Task: "Contract test triage sessions/deck/decisions in backend/tests/contract/test_triage_sessions_api.py"
Task: "Integration test swipe→resume in backend/tests/integration/test_triage_swipe_resume.py"
Task: "Integration test re-decide/undo in backend/tests/integration/test_triage_redecide.py"
Task: "Integration test isolation in backend/tests/integration/test_triage_isolation.py"

# Then parallel across files:
Task: "triage_service in backend/src/services/triage_service.py"
Task: "Frontend swipe deck in frontend/src/components/SwipeDeck.vue"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational (CRITICAL) → 3. Phase 3 US1 → **STOP & VALIDATE** swipe
   triage persists and resumes with zero Google writes → demo.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → swipe triage (MVP).
3. US2 → processing queue (edit + transliterate).
4. US3 → snapshot-protected delete batch to Google.
Each story adds value without breaking the previous ones.

---

## Notes

- [P] = different files, no dependencies. [Story] labels map tasks to US1/US2/US3 for traceability.
- This is the FIRST feature that writes to Google. The live write path is exercised only behind the
  `PeopleWriteClient` seam; the default CI lane uses `FakePeopleWriteClient` (no live Google) —
  Principle IV. The `contacts` write scope is opt-in via incremental consent — Principle I.
- Non-destructive guarantees (snapshot-before-delete, idempotent deletes, reversible edits/deletes,
  source snapshot untouched) are encoded as tests (T025, T026, T027, T028) — verify they pass before
  claiming completion.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
