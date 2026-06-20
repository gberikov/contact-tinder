# Implementation Plan: Tinder-Style Contact Swipe Triage

**Branch**: `003-tinder-swipe-triage` | **Date**: 2026-06-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-tinder-swipe-triage/spec.md`

## Summary

Add a fast, card-based **triage surface** over the **post-dedup survivors** of a working copy (the
`active` `working_copy_contact` rows left after feature 002's merges). The operator opens a
**TriageSession** and swipes each contact to one of three outcomes — **keep**, **delete** (queue for
deletion in Google), or **send to additional processing**. Swipes only stage decisions; nothing is
written to Google during the pass, and the deck is shown in a stable order so a session can be paused
and resumed. The operator can re-decide any contact at any time (live decision + audit history).

Contacts swiped to **additional processing** are tagged only (no inline editor — to preserve swipe
momentum) and handled afterwards in a **ProcessingQueue**: edit the card and/or transliterate the
**name fields** (given/family/display) Latin→Cyrillic via a reviewable suggestion. Edits and accepted
transliterations are staged against the working copy as reversible **StagedEdit** records. A processed
contact defaults to a terminal **keep** disposition (re-decidable).

Deletions accumulate into a **DeleteBatch** that the operator reviews: a dry-run preview lists exactly
which contacts will be deleted, a restorable **DeletionRecord** (full payload) is persisted for every
affected contact *before* any Google call, and an explicit per-batch confirmation triggers a
**PG-backed delete worker** (mirroring 001's `import_worker` / 002's `dedup_worker`) that calls Google
People `deleteContact` idempotently. Undo restores deleted contacts. **This is the first feature that
writes to Google**, so it introduces a narrow People *write* seam and the corresponding OAuth scope
(incremental consent). Every decision and mutation is appended to the existing `AuditEntry` log.

## Technical Context

**Language/Version**: Python 3.12 (backend + new delete worker); TypeScript 5.x (frontend). No JVM /
Spark in this feature.

**Primary Dependencies**: existing — FastAPI, SQLAlchemy 2.x + Alembic, psycopg, Pydantic, Vue 3 +
Vite + Pinia, Biome. New — a `PeopleWriteClient` seam extending the existing `people_client.py`
(`deleteContact` + `createContact` for undo) with a CI fake; a small **deterministic transliteration**
module (pure Python, Latin→Cyrillic for names — no third-party service, no network). No new container.

**Storage**: PostgreSQL — adds `triage_session`, `triage_decision`, `processing_item`, `staged_edit`,
`delete_batch`, `deletion_record` tables and new `AuditEntry.action` values. Reuses
`working_copy_contact` (the deck = `status='active'` rows; `origin_resource_name` is the Google delete
target). No schema change to existing tables; the immutable `snapshot`/`snapshot_contact` foundation is
never touched.

**Testing**: backend `pytest` with the **`PeopleWriteClient` seam** — a deterministic fake in CI (no
live Google), so delete/restore, idempotency, and partial-failure retry are tested without mutating
real data (Principle IV); FastAPI `TestClient` for API contracts; transliteration covered by pure
unit tests (table-driven); frontend `Vitest` + Vue Test Utils for the swipe deck, processing queue,
and delete-batch review; Biome `ci` gate. A slow-marked integration test may exercise the real Google
write path outside the default CI lane.

**Target Platform**: Linux containers via docker-compose; reuses `db`, `backend`, `worker`, `web`. The
delete worker runs in the existing `worker` service (same PG-backed job pattern); no new service.

**Performance Goals**: SC-001 — median time to decide one contact **< 3 s**; the swipe interaction
never blocks on per-card work (transliteration/edit deferred to the queue; decisions persisted via a
lightweight write, deck prefetched/paginated). A 100-card deck is triaged in one sitting without lag.

**Constraints**: non-destructive — a restorable `DeletionRecord` (full payload) exists for 100% of
contacts before any Google delete (SC-002, Principle II); dry-run preview + explicit per-batch
confirmation required before any Google write (FR-019/021); delete execution idempotent and retry-safe
(FR-022); contacts absent in Google at commit time count as success (FR-024); transliteration is always
a reviewed suggestion, never silent, name fields only (FR-014/015); per-account / per-working-copy
isolation (FR-010); edits & deletes reversible (SC-004); resume preserves 100% of decisions (SC-003).

**Scale/Scope**: single self-hosted operator; multiple working copies; up to ~50,000 contacts per
working copy (deck of the `active` survivors); typical delete batches tens–hundreds of contacts.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How this plan complies |
|-----------|--------|------------------------|
| I. Privacy & Data Protection | ✅ PASS (justified scope expansion) | **New OAuth scope**: deleting in Google requires `https://www.googleapis.com/auth/contacts` — Google offers **no delete-only or readonly-delete scope**, so this is the *narrowest scope that satisfies the feature* (Principle I). It is requested only via **incremental consent** when the operator opts into the delete capability, recorded in `account.granted_scopes`; read-only flows are unaffected. Tokens stay encrypted in `Credential`, never logged/returned (existing). Contact PII never leaves the deployment except the unavoidable `deleteContact` call to Google for contacts the operator chose to delete. Per-account/per-working-copy isolation via `working_copy_id`/`account_id` scoping (FR-010). See Complexity Tracking for the scope-expansion record. |
| II. Non-Destructive by Default | ✅ PASS | Swiping writes **nothing** to Google (FR-008). Delete is staged → dry-run preview (FR-019) → **restorable snapshot persisted for every contact before any delete** (FR-020, SC-002) → **explicit per-batch confirmation** (FR-021). Deletes are **undoable** (re-create from `DeletionRecord.payload_before`, FR-023) and idempotent/retry-safe (FR-022). Edits/transliterations are staged `StagedEdit`s, reversible (FR-016). The snapshot foundation is never mutated. |
| III. Human-in-the-Loop | ✅ PASS | Every keep/delete/process outcome is an explicit swipe (FR-009). Transliteration is only a **suggestion** the operator accepts/edits — never auto-applied (FR-015). No deletion occurs without explicit per-batch confirmation (FR-021). Processing routes ambiguous work to a deliberate review queue rather than auto-resolving. |
| IV. Test-First | ✅ PASS | TDD throughout; the `PeopleWriteClient` seam lets CI test delete/restore, idempotency, and partial-failure retry with a deterministic fake — **no live Google in CI**. Decision persistence/resume, re-decide, staged-edit undo, snapshot-before-delete, and isolation are integration-tested; transliteration is pure-unit-tested. |
| V. Auditability & Observability | ✅ PASS | Append-only `AuditEntry` extended: `triage.session.started/completed`, `contact.kept/queued_delete/sent_processing` (decision changes), `contact.edited`, `contact.transliterated`, `edit.undone`, `delete.batch.previewed/committed`, `contact.deleted`, `contact.restored` — each with target + before-state ref, redacted details (no payloads/secrets), and (for Google writes) the API result (FR-025/026). |

**Result**: PASS — one justified, recorded deviation (OAuth write-scope expansion), mandated by the
feature's headline delete capability and kept as narrow as Google permits. See Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/003-tinder-swipe-triage/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── openapi.yaml      # Phase 1 output — triage/processing/transliterate/delete-batch REST contract
├── checklists/
│   └── requirements.md   # Spec quality checklist (from /speckit-specify)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   └── triage.py             # NEW: TriageSession, TriageDecision, ProcessingItem,
│   │                              #      StagedEdit, DeleteBatch, DeletionRecord
│   ├── services/
│   │   ├── triage_service.py         # NEW: open/resume session, deck (active survivors, stable order),
│   │   │                              #      record/re-decide outcomes, completion summary
│   │   ├── processing_service.py     # NEW: processing queue, apply edit, accept transliteration
│   │   ├── transliteration.py        # NEW: pure Latin→Cyrillic suggestion for name fields (no I/O)
│   │   ├── delete_batch_service.py   # NEW: build batch, dry-run preview, snapshot, confirm, undo
│   │   └── audit_service.py          # extend with triage/delete/edit actions
│   ├── integrations/
│   │   └── people_client.py          # extend: PeopleWriteClient seam (deleteContact/createContact)
│   │                                  #         + FakePeopleWriteClient for CI
│   ├── workers/
│   │   └── delete_worker.py          # NEW: PG-backed delete-batch consumer (FOR UPDATE SKIP LOCKED),
│   │                                  #      idempotent per DeletionRecord, redacted errors
│   ├── api/routers/
│   │   └── triage.py                 # NEW: routers matching contracts/openapi.yaml
│   └── core/                         # reuse config/db/logging/backoff; add `contacts` write scope
│                                     #   (incremental) + delete-undo retention note to config
├── migrations/                       # Alembic: 0003 — new triage/delete tables + new audit actions
└── tests/
    ├── contract/                  # triage/processing/transliterate/delete-batch API + write seam
    ├── integration/               # swipe→decide→resume, re-decide, process(edit/translit)→keep,
    │                              #   delete batch (preview→snapshot→confirm→delete→undo),
    │                              #   idempotency/partial-failure, isolation, snapshot-immutability
    └── unit/                      # transliteration table tests, deck ordering, decision supersession

frontend/
├── src/
│   ├── components/   # SwipeDeck, ContactCard, SwipeControls, ProcessingQueue, EditCardForm,
│   │                 #   TransliterationReview, DeleteBatchReview, CompletionSummary
│   ├── pages/        # WorkingCopyTriage (swipe), Processing (queue), DeleteReview (commit)
│   ├── services/     # typed triage API client (from openapi.yaml)
│   └── stores/       # Pinia: triage session + deck + decisions + delete batch
└── tests/            # Vitest + Vue Test Utils (gesture mapping, optimistic decide, resume)

docker-compose.yml     # no new service; delete worker runs in existing `worker`
.env / config          # add incremental `contacts` write scope toggle; document delete-undo retention
```

**Structure Decision**: Keep feature 001/002's web-application layout. **No new container** — unlike
002 (which needed the JVM/Spark `dedup` image), triage is pure Python + TypeScript, and the Google
delete job reuses the established **PG-backed worker** pattern inside the existing `worker` service.
The backend reaches Google only through the extended `people_client.py` **write seam** (real impl +
CI fake), keeping the live API out of CI per Principle IV. PostgreSQL remains the single datastore;
the deck is just the `active` `working_copy_contact` survivors, so triage composes directly on top of
002's output with no data duplication.

## Complexity Tracking

> One justified deviation: an OAuth **write-scope expansion**. Recorded here per the constitution's
> requirement that any deviation be justified in writing.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| New Google OAuth scope `…/auth/contacts` (read-write) beyond the app's `contacts.readonly` baseline | The headline feature deletes contacts in Google; `people.deleteContact` requires this scope | A narrower scope is impossible — Google has **no delete-only or readonly-delete scope**. Risk is contained by: requesting it **only via incremental consent** when the operator enables deletion, snapshot-before-delete + explicit per-batch confirmation (Principle II), idempotent deletes, and full audit. Not requesting it would make the core feature impossible. |
