---
description: "Task list for feature 004-google-contacts-export implementation"
---

# Tasks: Export Triage Results to Google Contacts

**Input**: Design documents from `/specs/004-google-contacts-export/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml, quickstart.md

**Tests**: INCLUDED — the constitution makes TDD NON-NEGOTIABLE (Principle IV). Set derivation, the new
Google **label write** (contact-group create/assign/remove), idempotency, `404→skipped_absent`,
scope-gating, and undo all get failing-first tests. The live Google API is exercised only behind the
`PeopleWriteClient` seam (CI uses `FakePeopleWriteClient`; no live Google in the default lane).

**Organization**: Tasks grouped by user story (US1 P1 → US2 P2 → US3 P3) for independent implementation
and testing. **Heavy reuse of feature 003**: the delete path (`DeleteBatch`/`DeletionRecord`,
`delete_batch_service`, `delete_worker`, `PeopleWriteClient` delete/create, `account_has_write_scope`,
`audit_service`) already exists and is driven, unchanged, by the new `ExportRun`. The **new** work is the
`Process`-label write and the export orchestration. **No new OAuth scope** (`contactGroups` reuses the
`…/auth/contacts` grant) and **no new container** (label batches run in the existing `worker`).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 (setup, foundational, polish carry no story label)
- Exact file paths included.

## Path Conventions

Web app (per plan.md): backend at `backend/src/`, frontend at `frontend/src/`, tests at `backend/tests/`
and `frontend/tests/`. **No new container** — label batches run in the existing `worker` (`run_all.py`).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Configuration and scaffolding without domain logic.

- [X] T001 Add feature-004 config to `backend/src/core/config.py`: a `process_label_name: str = "Process"`
  setting (the Google contact-group name), and a documented note that **labeling reuses the existing
  `google_contacts_write_scope` — NO new scope is added** (research D1) and that label-undo has **no
  expiry** (life of the working copy — research D8).
- [X] T002 [P] Scaffold the frontend export route: add the `/working-copies/:id/export` route
  (`name: 'working-copy-export'`) to `frontend/src/router/index.ts` and a nav entry, with an empty
  `frontend/src/pages/Export.vue` stub.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared schema, schemas, and router wiring that every story builds on. **No user story can
start until this phase is complete.**

**⚠️ CRITICAL**: Blocks all of Phase 3+.

- [X] T003 Create export models in `backend/src/models/export.py`: `ExportRun`, `LabelBatch`,
  `LabelAssignment`, `ContactLabel` (fields/enums/indexes per data-model.md — incl. unique
  `(label_batch_id, origin_resource_name)` on `label_assignment` and unique `(account_id, name)` on
  `contact_label`); register them in `backend/src/models/__init__.py`. Reuse `DeleteBatch`/`DeletionRecord`
  from `models/triage.py` (do not duplicate).
- [X] T004 Create the Alembic migration `backend/migrations/versions/0004_google_contacts_export.py`
  for the four new tables with their indexes/unique constraints; `down_revision = "0003_tinder_swipe_triage"`.
  No existing table is altered.
- [X] T005 [P] Add export Pydantic schemas to `backend/src/api/schemas.py`: `ExportPreviewOut`,
  `StartExportBody`, `ExportRunOut`, `ExportReportOut` (reuse the existing `ContactSummaryOut` for set
  members) — field names/casing per `contracts/openapi.yaml`.
- [X] T006 [P] Create the export router skeleton `backend/src/api/routers/export.py` (endpoints declared,
  bodies raising `NotImplementedError`) and include it in `backend/src/api/main.py`.

**Checkpoint**: Schema + wiring ready — US1/US2/US3 can begin.

---

## Phase 3: User Story 1 - Delete the marked contacts in Google (Priority: P1) 🎯 MVP

**Goal**: Run an export that deletes the `delete`-decided active survivors via the existing
snapshot-protected, confirmed, idempotent, undoable delete path — now orchestrated by an `ExportRun`.

**Independent Test**: With contacts decided `delete`, `POST /export` → `POST /confirm-delete` (scope-gated)
→ worker deletes against the **fake** seam → `GET /export-runs/{id}` report shows correct deleted /
skipped-absent counts; re-run is idempotent; `undo-delete` restores. (Seam/API-level per spec US1.)

### Tests for User Story 1 (write FIRST, ensure they FAIL) ⚠️

- [X] T007 [P] [US1] Contract test for the export delete endpoints (`previewExport`, `startExport`,
  `getExportRun`, `confirmExportDelete` incl. `403 write_scope_required`, `undoExportDelete`) in
  `backend/tests/contract/test_export_api.py`, asserting conformance to `contracts/openapi.yaml`.
- [X] T008 [P] [US1] Integration test for the delete-export flow in
  `backend/tests/integration/test_export_delete_flow.py`: start → confirm-delete → `delete_worker`
  deletes (fake) → report; idempotent re-run; `404 → skipped_absent` success; `undo-delete` restores the
  contact and `working_copy_contact.status='active'`. **Also assert FR-024**: a fake-seam `429`/quota
  error is surfaced in the report (run not silently dropped) and the run remains retryable & idempotent —
  a retry completes the remaining records with no double-delete (reuses 003's backoff path, plan.md).
- [X] T009 [P] [US1] Unit test for set derivation in `backend/tests/unit/test_export_sets.py`: delete set
  = active survivors with latest decision `delete`; re-decided-to-keep excluded; `undecided_count`
  counts undecided active survivors and they are excluded (FR-002/003/017a).

### Implementation for User Story 1

- [X] T010 [US1] Create `backend/src/services/export_service.py`: `preview(working_copy_id, session_id)`
  deriving the delete set (and `undecided_count`) and returning counts + dry-run summaries; `start(...)`
  creating an `ExportRun` and linking a `DeleteBatch` via `delete_batch_service.create_batch` (snapshots
  first); `get_run` with report aggregation (delete portion: deleted / skipped-absent / failed / excluded).
- [X] T011 [US1] In `export_service.py`, add `confirm_delete(run_id)` driving
  `delete_batch_service.confirm` (scope-gated → propagate `403 write_scope_required`), set
  `ExportRun.status='running'`, and `undo_delete(run_id)` via `delete_batch_service.request_undo`; audit
  `export.run.started`/`export.run.completed`.
- [X] T012 [US1] Implement the export router endpoints in `backend/src/api/routers/export.py`:
  `GET /working-copies/{id}/export/preview`, `POST /working-copies/{id}/export`, `GET /export-runs/{id}`,
  `POST /export-runs/{id}/confirm-delete`, `POST /export-runs/{id}/undo-delete` — mapping
  `export_service` to the schemas (no label fields yet). (Note: the report's `deleteStatus` enum reuses
  003's `DeleteBatch.BATCH_STATES` in `models/triage.py` — verified to match `openapi.yaml`
  `[staged, previewed, committing, committed, failed, undoing, undone]`; do not redefine it.)

**Checkpoint**: Delete-export works end-to-end against the fake seam; US1 independently testable.

---

## Phase 4: User Story 2 - Label the Processing-Queue contacts with `Process` (Priority: P2)

**Goal**: Apply a `Process` Google contact group to the Processing-Queue survivors (not deleted) —
idempotent, reversible, `404→skipped_absent` — without pushing staged edits.

**Independent Test**: With processing contacts, run the label half → the `Process` group is created once
and members added (fake seam); re-run adds no duplicates; an absent contact → skipped-absent; `undo-label`
removes membership; staged edits are NOT written to Google.

### Tests for User Story 2 (write FIRST, ensure they FAIL) ⚠️

- [X] T013 [P] [US2] Seam test for the contact-group write methods in
  `backend/tests/contract/test_write_seam_labels.py`: `FakePeopleWriteClient.ensure_label` creates once /
  reuses; `add_label_members` / `remove_label_members` track membership; absent member raises
  `ContactNotFoundError`.
- [X] T014 [P] [US2] Integration test for the label flow in
  `backend/tests/integration/test_export_label_flow.py`: ensure-group-once (audit `label.group.created`,
  cached in `contact_label`), assign members, idempotent re-run, `404→skipped_absent`, `undo-label`
  removes membership and audits `contact.unlabeled`. **Also assert `undoExportLabel`
  (`POST /export-runs/{id}/undo-label`) conforms to `contracts/openapi.yaml`** (request/response shape,
  202) so FR-014's endpoint has contract coverage — the US1 contract test T007 covers only the
  delete-side ops.
- [X] T015 [P] [US2] Unit test in `backend/tests/unit/test_label_sets.py`: label set = active survivors
  routed to processing with latest decision ≠ `delete`; **disjoint** from the delete set; a processing
  contact re-decided to `delete` is in the delete set only (FR-002, research D2).

### Implementation for User Story 2

- [X] T016 [US2] Extend the write seam in `backend/src/integrations/people_client.py`: add
  `ensure_label(name) -> group_resource_name`, `add_label_members(group, resource_names)`,
  `remove_label_members(group, resource_names)` to the `PeopleWriteClient` Protocol, the
  `GooglePeopleWriteClient` (via `contactGroups.create` + `contactGroups.members.modify`, same
  `…/auth/contacts` scope), and the `FakePeopleWriteClient` (in-memory group + membership state).
- [X] T017 [P] [US2] Create `backend/src/services/label_batch_service.py` mirroring
  `delete_batch_service`: `create_batch` builds the label set into `LabelAssignment`s; `process_batch`
  ensures the `ContactLabel` group (D5), assigns members idempotently (chunked), `404→skipped_absent`,
  audits `label.batch.committed`/`contact.labeled`; `process_undo` removes membership (`contact.unlabeled`).
  Takes an injected `PeopleWriteClient` (CI fake).
- [X] T018 [US2] Create `backend/src/workers/label_worker.py`: claim a `LabelBatch` in
  `labeling`/`unlabeling` status with `FOR UPDATE SKIP LOCKED`, build the per-account write client (reuse
  `delete_worker.build_write_client` pattern), and call `label_batch_service.process_batch`/`process_undo`.
- [X] T019 [US2] Wire `label_worker.run_once` into the combined loop in `backend/src/workers/run_all.py`
  (add `("label", label_worker.run_once)`); update the loop's log/comment.
- [X] T020 [US2] Extend `backend/src/services/export_service.py`: on `start`, also create a `LabelBatch`
  (when the label set is non-empty) and link it to the `ExportRun`; on `confirm_delete`, enqueue the
  `LabelBatch` (`labeling`) alongside the delete batch **without a separate confirmation** (FR-015); add
  `undo_label(run_id)`; extend the report with `labeled`/`skippedAbsentLabel`/label status.
- [X] T021 [US2] Add label fields/endpoint to `backend/src/api/routers/export.py`: include
  `labelCount`/`labelSet`/`labelName` in the preview and `labeled`/`skippedAbsentLabel`/`labelStatus` in
  the report, and add `POST /export-runs/{id}/undo-label`.

**Checkpoint**: Both write halves work against the fake seam; the export report covers delete + label.

---

## Phase 5: User Story 3 - Unified Export screen & post-export report (Priority: P3)

**Goal**: One Export screen previews both actions with accurate counts, warns on undecided survivors,
shows the empty state, gates deletion behind its explicit confirm, runs labeling alongside, and shows a
live-updating report with undo entry points; re-runnable after partial failure.

**Independent Test**: With staged delete + processing sets, open `/working-copies/:id/export`: both
counts/previews are accurate, undecided warning shows, confirm triggers the delete confirmation (labeling
needs none), progress updates live, and the report shows correct per-action outcomes with undo links.

### Tests for User Story 3 (write FIRST, ensure they FAIL) ⚠️

- [X] T022 [P] [US3] Frontend test for the Export page previews in
  `frontend/tests/Export.preview.spec.ts`: delete + label sections render counts/lists; `undecidedCount`
  shows a warning; both-empty shows the "nothing to export" state (FR-017).
- [X] T023 [P] [US3] Frontend test for the run/report in `frontend/tests/Export.run.spec.ts`: confirm-delete
  gating, live progress polling to `completed`, report counts + undo (delete/label) entry points.
- [X] T024 [P] [US3] Backend integration test for the unified run/report in
  `backend/tests/integration/test_export_run_report.py`: full run drives both batches to terminal state,
  `ExportRun.status` → `completed`/`failed`, report counts equal aggregated record statuses; re-run
  attempts only `pending`/`failed` (FR-018/019, SC-004).

### Implementation for User Story 3

- [X] T025 [P] [US3] Add typed export API client methods (preview/start/get/confirm-delete/undo-delete/
  undo-label) to `frontend/src/services/api.ts` per `contracts/openapi.yaml`.
- [X] T026 [P] [US3] Create the Pinia store `frontend/src/stores/export.ts`: run state, previews,
  progress polling, and report.
- [X] T027 [US3] Build `frontend/src/pages/Export.vue`: preview (delete + label sections), undecided
  warning, empty state, explicit delete confirmation, live progress, and the report with undo entry
  points (uses the store + components below).
- [X] T028 [P] [US3] Create components in `frontend/src/components/`: `ExportPreview.vue`,
  `LabelPreview.vue`, `UndecidedWarning.vue`, `ExportReport.vue`.
- [X] T029 [US3] Add navigation to the Export screen from `WorkingCopyTriage.vue` / `DeleteReview.vue`
  (link with the working-copy id), completing the triage→export flow.

**Checkpoint**: The unified Export screen drives the full feature; all three stories work.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T030 [P] Audit/redaction test in `backend/tests/integration/test_export_audit_redaction.py`: every
  export mutation produces an audit entry and no audit `details`, report, or log contains payloads, names,
  or secrets (FR-022/023, SC-007).
- [X] T031 [P] Run all `quickstart.md` scenarios A–E against the fake client and confirm expected audit
  actions (`export.run.started/completed`, `label.group.created`, `label.batch.committed`,
  `contact.labeled`, `contact.unlabeled`).
- [X] T032 [P] Update `docker-compose.yml` worker comment (the `worker` now also drives **label** batches)
  and document `process_label_name` in `.env.example`.
- [X] T033 Run the full gate: backend `pytest` green and frontend Biome `ci` + `vitest` green.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup — **BLOCKS all user stories**.
- **User Stories (Phase 3+)**: all depend on Foundational.
  - US1 (P1) and US2 (P2) are backend/seam-level and largely independent; US2's `export_service` changes
    (T020/T021) extend US1's files, so if run in parallel, coordinate those two tasks.
  - US3 (P3) consumes the US1+US2 API (preview/report must expose both halves) — start its **frontend**
    after the export endpoints exist, but the frontend tests (T022–T023) can be written first (TDD).
- **Polish (Phase 6)**: after all desired stories are complete.

### Within Each User Story

- Tests (US1: T007–T009; US2: T013–T015; US3: T022–T024) MUST be written and FAIL before implementation.
- Models → services → workers → endpoints → frontend.
- Seam extension (T016) before `label_batch_service` (T017) before `label_worker` (T018) before wiring
  (T019) before `export_service` label integration (T020).

### Parallel Opportunities

- T002 (frontend route) ∥ T001 (config).
- Foundational T005 (schemas) ∥ T006 (router skeleton) after T003/T004.
- US1 tests T007 ∥ T008 ∥ T009; US2 tests T013 ∥ T014 ∥ T015; US3 tests T022 ∥ T023 ∥ T024.
- US3 frontend T025 (client) ∥ T026 (store) ∥ T028 (components) before T027 (page) wires them.
- Polish T030 ∥ T031 ∥ T032.

---

## Parallel Example: User Story 2

```bash
# Write the failing tests together first:
Task: "Seam test for contact-group write methods in backend/tests/contract/test_write_seam_labels.py"
Task: "Integration test for the label flow in backend/tests/integration/test_export_label_flow.py"
Task: "Unit test for label-set derivation in backend/tests/unit/test_label_sets.py"

# Then the independent implementation pieces (service is [P] vs the seam it depends on — do T016 first):
Task: "Create backend/src/services/label_batch_service.py"   # after T016
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → Phase 2 Foundational (CRITICAL — blocks everything).
2. Phase 3 US1: delete-export via `ExportRun` over the existing delete path.
3. **STOP & VALIDATE**: quickstart Scenario B/C/D (delete only) against the fake seam; demo.

### Incremental Delivery

1. Setup + Foundational → schema + wiring ready.
2. US1 (delete export) → test → demo (MVP).
3. US2 (Process label) → test → demo (the new write capability).
4. US3 (unified Export screen + report) → test → demo (the full operator UX).

### Parallel Team Strategy

After Foundational: Dev A on US1 (export_service/router/delete tests), Dev B on US2 (seam +
label_batch_service + label_worker), Dev C writes US3 frontend tests/components against the contract;
US3 page wiring lands once US1+US2 endpoints expose both halves.

---

## Notes

- [P] = different files, no dependencies on incomplete tasks. [Story] maps task → user story.
- The delete machinery (003) is reused unchanged — US1 adds orchestration, not a new delete engine.
- **No new OAuth scope** and **no new container**: labeling rides the `…/auth/contacts` grant and the
  existing `worker`.
- Verify each story's tests fail before implementing; commit after each task or logical group.
- Never let the export write staged edits to Google (FR-013) — label only.
