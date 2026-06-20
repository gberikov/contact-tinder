---
description: "Task list for feature 001-people-api-snapshots"
---

# Tasks: Google People API Snapshots & Working Copies

**Input**: Design documents from `/specs/001-people-api-snapshots/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml, quickstart.md

**Tests**: INCLUDED — the constitution mandates Test-First (Principle IV, NON-NEGOTIABLE). Test
tasks MUST be written and fail before their implementation tasks.

**Organization**: Tasks are grouped by user story (US1=P1, US2=P2, US3=P3) plus a deletion phase
(FR-021/022/023) whose guard depends on working copies.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 for user-story tasks; setup/foundational/deletion/polish are unlabeled
- Web-app layout: `backend/src/`, `backend/tests/`, `frontend/src/`, `frontend/tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and tooling

- [X] T001 Create monorepo structure (`backend/`, `frontend/`, top-level `docker-compose.yml`) per plan.md
- [X] T002 [P] Initialize backend Python 3.12 project in `backend/pyproject.toml` (FastAPI, SQLAlchemy 2.x, Alembic, google-api-python-client, google-auth-oauthlib, cryptography, psycopg, pytest, respx)
- [X] T003 [P] Initialize frontend Vue 3 + Vite + TypeScript project in `frontend/` (package.json, vite config, Pinia, vue-router, Vitest)
- [X] T004 [P] Configure Biome lint/format in `frontend/biome.json` and add `biome ci` script
- [X] T005 [P] Author `docker-compose.yml` with services `db` (PostgreSQL), `backend`, `worker`, `web`
- [X] T006 [P] Add `.env.example` with `DATABASE_URL`, `GOOGLE_OAUTH_CLIENT_ID/SECRET/REDIRECT_URI`, `TOKEN_ENCRYPTION_KEY`, `IMPORT_MAX_ATTEMPTS` (real `.env` already git-ignored)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST complete before ANY user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T007 Implement core config loader and SQLAlchemy engine/session in `backend/src/core/config.py` and `backend/src/core/db.py`
- [X] T008 Initialize Alembic migrations framework in `backend/migrations/`
- [X] T009 [P] Implement structured logging with token/PII redaction in `backend/src/core/logging.py` (Principle V)
- [X] T010 [P] Implement token encryption util (AES-GCM/Fernet, key from `TOKEN_ENCRYPTION_KEY`, `key_id`) in `backend/src/services/crypto.py` (Principle I)
- [X] T011 [P] Implement exponential backoff + jitter helper (honor `Retry-After`, capped at `max_attempts`) in `backend/src/core/backoff.py`
- [X] T012 [P] Create `Account` + `Credential` models in `backend/src/models/account.py` (credential isolated, never serialized)
- [X] T013 [P] Create `Snapshot` + `ImportJob` (incl. `attempts`/`max_attempts`) + `SnapshotContact` models in `backend/src/models/snapshot.py`
- [X] T014 [P] Create `WorkingCopy` + `WorkingCopyContact` models in `backend/src/models/working_copy.py`
- [X] T015 [P] Create `AuditEntry` model in `backend/src/models/audit.py`
- [X] T016 Generate initial Alembic migration for all tables (uniques/indexes per data-model.md) in `backend/migrations/versions/` (depends on T012–T015)
- [X] T017 Implement `PeopleClient` seam (interface + Google-backed impl) and a fake for tests in `backend/src/integrations/people_client.py` and `backend/tests/fakes/fake_people_client.py`
- [X] T018 Implement append-only `audit_service` in `backend/src/services/audit_service.py` (depends on T015)
- [X] T019 Setup FastAPI app, error handlers, and Pydantic schemas mirroring `contracts/openapi.yaml` in `backend/src/api/main.py`, `backend/src/core/errors.py`, `backend/src/api/schemas.py`
- [X] T020 [P] Frontend scaffolding: vue-router routes, Pinia setup, and typed API client base in `frontend/src/router/index.ts`, `frontend/src/stores/`, `frontend/src/services/api.ts`

**Checkpoint**: Foundation ready — user stories can begin

---

## Phase 3: User Story 1 - Connect account & capture a snapshot (Priority: P1) 🎯 MVP

**Goal**: Operator connects a Google account (read-only) and imports its personal contacts into a
new immutable snapshot, with visible progress and atomic finalization.

**Independent Test**: Connect a test account, create a snapshot, and verify it reaches `complete`
with a contact count matching the account; verify resume after worker restart and that an
interrupted import never finalizes.

### Tests for User Story 1 ⚠️ (write first, must fail)

- [X] T021 [P] [US1] Contract test for accounts endpoints (connect/callback/list/disconnect) in `backend/tests/contract/test_accounts_api.py`
- [X] T022 [P] [US1] Contract test for `POST /accounts/{id}/snapshots` and `GET /snapshots/{id}/import` in `backend/tests/contract/test_snapshots_create_api.py`
- [X] T023 [P] [US1] PeopleClient adapter contract test (pagination at pageSize=1000, backoff on 429, `metadata.deleted`, sync token) in `backend/tests/contract/test_people_client.py`
- [X] T024 [P] [US1] Integration test: full import finalizes snapshot `complete` with exact count, zero loss, and `payload` retains addresses/organizations/notes/memberships/photo refs (FR-004) in `backend/tests/integration/test_import_finalize.py`
- [X] T025 [P] [US1] Integration test: resumability — worker restart continues from persisted `page_token` in `backend/tests/integration/test_import_resume.py`
- [X] T026 [P] [US1] Integration test: interrupted/401 import AND retry-ceiling exhaustion (`attempts > max_attempts`) → snapshot `failed`, account `needs_reauth` on auth error, no partial usable snapshot in `backend/tests/integration/test_import_atomicity.py`
- [X] T027 [P] [US1] Integration test: tokens encrypted at rest and absent from all API responses/logs in `backend/tests/integration/test_token_privacy.py`
- [X] T028 [P] [US1] Integration test: per-account isolation — account A's snapshot/contacts never appear under account B; cross-account access denied (FR-018, SC-009) in `backend/tests/integration/test_multi_account_isolation.py`

### Implementation for User Story 1

- [X] T029 [US1] Implement `account_service` OAuth flow (build auth URL, exchange code, encrypt+store tokens, status transitions) in `backend/src/services/account_service.py` (depends T010, T012)
- [X] T030 [US1] Implement accounts router (connect/callback/list/disconnect) in `backend/src/api/routers/accounts.py`
- [X] T031 [US1] Implement `snapshot_service.create_snapshot` (create `importing` snapshot + enqueue `ImportJob`; reject if an import is already active → 409; all queries scoped by `account_id`) in `backend/src/services/snapshot_service.py` (depends T013)
- [X] T032 [US1] Implement snapshot create + import-status endpoints in `backend/src/api/routers/snapshots.py`
- [X] T033 [US1] Implement `import_worker`: PG queue (`FOR UPDATE SKIP LOCKED`), paged People fetch, persist `page_token`/`fetched_count`, backoff capped at `max_attempts` (exhaustion → job+snapshot `failed`), transactional finalize to `complete`, store `next_sync_token` in `backend/src/workers/import_worker.py` (depends T017, T011, T031)
- [X] T034 [US1] Emit `snapshot.created` audit entry from snapshot creation path (depends T018)
- [X] T035 [P] [US1] Frontend Accounts page (connect/list/disconnect, `needs_reauth` prompt) in `frontend/src/pages/Accounts.vue` + store
- [X] T036 [P] [US1] Frontend snapshot-create action with live import progress polling in `frontend/src/pages/Snapshots.vue` + `frontend/src/stores/snapshots.ts`

**Checkpoint**: US1 fully functional — operator can connect an account and produce a verifiable, immutable backup. **This is the MVP.**

---

## Phase 4: User Story 2 - View snapshots & contents (Priority: P2)

**Goal**: Operator sees all snapshots with metadata and browses a snapshot's contacts read-only.

**Independent Test**: With snapshots present, the list shows account/date/count/workingCopyCount;
opening a snapshot lists contacts with no edit affordance; reopening shows identical data.

### Tests for User Story 2 ⚠️ (write first, must fail)

- [X] T037 [P] [US2] Contract test for `GET /snapshots`, `GET /snapshots/{id}`, `GET /snapshots/{id}/contacts` in `backend/tests/contract/test_snapshots_read_api.py`
- [X] T038 [P] [US2] Integration test: list ordering (newest first), `workingCopyCount`, read-only contacts, zero drift in `backend/tests/integration/test_snapshot_view.py`

### Implementation for User Story 2

- [X] T039 [US2] Add read methods to `snapshot_service` (list newest-first with `workingCopyCount`, detail, paginated contacts with `q` filter) in `backend/src/services/snapshot_service.py`
- [X] T040 [US2] Add snapshot read endpoints (list/detail/contacts) in `backend/src/api/routers/snapshots.py`
- [X] T041 [P] [US2] Frontend SnapshotList page in `frontend/src/pages/Snapshots.vue`
- [X] T042 [P] [US2] Frontend SnapshotDetail page + read-only `ContactTable` component in `frontend/src/pages/Snapshot.vue`, `frontend/src/components/ContactTable.vue`

**Checkpoint**: US1 + US2 work independently

---

## Phase 5: User Story 3 - Create a working copy (Priority: P3)

**Goal**: Operator creates independent, editable working copies from any `complete` snapshot
without altering the snapshot; multiple copies per snapshot supported.

**Independent Test**: Create a working copy from a snapshot, verify same count and that the
snapshot is unchanged; create a second copy and verify both exist independently.

### Tests for User Story 3 ⚠️ (write first, must fail)

- [X] T043 [P] [US3] Contract test for `POST /snapshots/{id}/working-copies`, `GET /working-copies`, `GET /working-copies/{id}/contacts` in `backend/tests/contract/test_working_copies_api.py`
- [X] T044 [P] [US3] Integration test: deep-copy independence, snapshot unchanged, multiple copies, `contactCount` populated, block when snapshot not `complete` in `backend/tests/integration/test_working_copy.py`

### Implementation for User Story 3

- [X] T045 [US3] Implement `working_copy_service` (create via deep copy of snapshot contacts, list, paginated contacts, derived `contact_count`; reject if snapshot not `complete` → 409) in `backend/src/services/working_copy_service.py` (depends T014)
- [X] T046 [US3] Implement working-copies endpoints in `backend/src/api/routers/working_copies.py`
- [X] T047 [US3] Emit `working_copy.created` audit entry from creation path (depends T018)
- [X] T048 [P] [US3] Frontend WorkingCopies list + "create working copy" action on snapshot detail in `frontend/src/pages/WorkingCopies.vue` and `frontend/src/pages/Snapshot.vue`

**Checkpoint**: All three user stories independently functional

---

## Phase 6: Snapshot Deletion & Guard (FR-021/022/023)

**Purpose**: Operator-initiated snapshot deletion — explicit confirmation, blocked while working
copies exist, audited. Sequenced after US3 because the guard depends on working copies.

### Tests ⚠️ (write first, must fail)

- [X] T049 [P] Contract test for `DELETE /snapshots/{id}` (require `confirm=true` → 400 without; 409 guard) in `backend/tests/contract/test_snapshot_delete_api.py`
- [X] T050 [P] Integration test: delete blocked while working copies exist; succeeds after removal with confirmation; `snapshot.deleted` audit recorded in `backend/tests/integration/test_snapshot_delete.py`

### Implementation

- [X] T051 Implement `snapshot_service.delete_snapshot` (require confirmation, block if `workingCopyCount > 0`, transactional delete, emit `snapshot.deleted` audit) in `backend/src/services/snapshot_service.py`
- [X] T052 Implement delete endpoint in `backend/src/api/routers/snapshots.py`
- [X] T053 [P] Frontend delete action with confirmation dialog and blocked-reason messaging in `frontend/src/pages/Snapshots.vue`

**Checkpoint**: Full snapshot lifecycle (create → view → derive → delete) complete

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Quality, validation, and hardening across stories

- [X] T054 [P] Backend unit tests (crypto round-trip, backoff + max-attempts ceiling, contact field-extraction asserting payload retains addresses/organizations/notes/memberships/photo refs) in `backend/tests/unit/`
- [X] T055 [P] Frontend Vitest unit tests for stores/components in `frontend/tests/`
- [X] T056 Run `biome ci` on `frontend/` and fix violations (constitution CI gate)
- [X] T057 [P] Author setup/run docs (Google Cloud OAuth setup, env, compose) in `README.md`
- [X] T058 Security hardening pass: assert no tokens/PII in logs or API responses; verify only `contacts.readonly` requested; verify per-account isolation (Principles I & V)
- [ ] T059 Execute `quickstart.md` end-to-end (US1–US3 + deletion + multi-account isolation + privacy spot-check; validate SC-001…SC-009)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (P1)**: no dependencies
- **Foundational (P2)**: depends on Setup — BLOCKS all stories
- **US1 (P3)**: depends on Foundational — MVP
- **US2 (P4)**: depends on Foundational; uses US1 data but independently testable (can seed snapshots in tests)
- **US3 (P5)**: depends on Foundational; uses US1 snapshots but independently testable
- **Deletion (P6)**: depends on US3 (guard needs working copies) and US1 (snapshots)
- **Polish (P7)**: depends on all targeted stories

### Within Each Story

- Tests (TDD) written and failing before implementation
- Models (Foundational) → services → endpoints → frontend
- `snapshot_service.py` and `api/routers/snapshots.py` are touched across US1/US2/Deletion → those edits are sequential (not parallel) across phases

### Parallel Opportunities

- Setup: T002–T006 in parallel
- Foundational: T009–T015 in parallel (then T016 migration); T020 frontend in parallel with backend
- US1 tests T021–T028 all parallel; frontend T035–T036 parallel with backend wiring
- US2 tests T037–T038 parallel; frontend T041–T042 parallel
- US3 tests T043–T044 parallel
- Across stories: with multiple developers, US1/US2/US3 backends can progress in parallel after Foundational, coordinating on shared `snapshot_service.py`/`snapshots.py`

---

## Parallel Example: User Story 1 tests

```bash
Task: "Contract test accounts endpoints in backend/tests/contract/test_accounts_api.py"
Task: "Contract test snapshot create/import in backend/tests/contract/test_snapshots_create_api.py"
Task: "PeopleClient adapter contract test in backend/tests/contract/test_people_client.py"
Task: "Integration test import finalize (+ payload fidelity) in backend/tests/integration/test_import_finalize.py"
Task: "Integration test import resume in backend/tests/integration/test_import_resume.py"
Task: "Integration test import atomicity (+ retry ceiling) in backend/tests/integration/test_import_atomicity.py"
Task: "Integration test token privacy in backend/tests/integration/test_token_privacy.py"
Task: "Integration test multi-account isolation in backend/tests/integration/test_multi_account_isolation.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1 (Setup) + Phase 2 (Foundational)
2. Complete Phase 3 (US1)
3. **STOP & VALIDATE**: connect account → snapshot → verify count, resume, atomicity, token privacy, isolation
4. This is a usable "back up my Google Contacts" product on its own

### Incremental Delivery

- Foundation → US1 (MVP) → US2 (visibility) → US3 (working copies) → Deletion → Polish
- Each phase is an independently testable increment that doesn't break prior phases

---

## Notes

- [P] = different files, no incomplete dependencies
- Constitution gates: read-only scope, encrypted tokens never serialized, immutable snapshots,
  audit entries, Biome CI, no live Google calls in CI (PeopleClient seam)
- Verify each test fails before implementing; commit after each task or logical group
