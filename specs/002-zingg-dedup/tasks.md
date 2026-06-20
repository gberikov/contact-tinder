---
description: "Task list for feature 002-zingg-dedup implementation"
---

# Tasks: Working-Copy Deduplication with Zingg

**Input**: Design documents from `/specs/002-zingg-dedup/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml, quickstart.md

**Tests**: INCLUDED — the constitution makes TDD NON-NEGOTIABLE (Principle IV); dedup decisions,
merge/undo, and the Zingg seam must have failing-first tests. Zingg/Spark is exercised only behind
the `DedupEngine` seam (CI uses `FakeDedupEngine`; the real engine has a separate `slow` test).

**Organization**: Tasks are grouped by user story (US1 P1 → US2 P2 → US3 P3) for independent
implementation and testing. Builds on feature 001 (snapshots & working copies) — those tables and
services already exist.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 (setup, foundational, polish carry no story label)
- Exact file paths included.

## Path Conventions

Web app (per plan.md): backend at `backend/src/`, the Spark/Zingg engine at `backend/dedup/`,
frontend at `frontend/src/`, tests at `backend/tests/` and `frontend/tests/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Stand up the dedup container and dependencies without touching domain logic.

- [X] T001 Create the `dedup` engine package skeleton: `backend/dedup/__init__.py`,
  `backend/dedup/zingg_engine.py`, `backend/dedup/field_defs.py`, and `backend/dedup/model/README.md`
  (documents the bundled pre-trained model dir + how it was trained; research D2).
- [X] T002 Add a `backend/Dockerfile.dedup` (JVM 17 + Apache Spark 3.5 + `zingg` + PostgreSQL JDBC
  driver on `spark.jars`) and a `dedup` service to `docker-compose.yml` running
  `python -m src.workers.dedup_worker` (mirrors the `worker` service; research D1).
- [X] T003 [P] Add dedup dependencies: `zingg` + `pyspark` to a `dedup` optional-dependency group in
  `backend/pyproject.toml` (kept out of the lean backend/web images); add a `slow` pytest marker for
  real-Zingg/perf tests in `[tool.pytest.ini_options]`.
- [X] T004 [P] Add dedup config to `backend/src/core/config.py` (engine selector
  `DEDUP_ENGINE=fake|zingg`, JDBC settings, default `confidence_floor`, Spark `numPartitions`).
  No merge-undo retention/expiry setting in v1 — merges are undoable for the life of the working copy
  (research D6); document this absence rather than adding an expiry knob.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared schema, the engine seam, and the cross-story services. **No user story can start
until this phase is complete.**

**⚠️ CRITICAL**: Blocks all of Phase 3+.

- [X] T005 Create dedup models in `backend/src/models/dedup.py`: `DedupRun`, `DuplicateCluster`,
  `ClusterMember`, `MergeRecord` (fields/enums/indexes per data-model.md), and register them in
  `backend/src/models/__init__.py`.
- [X] T006 Add `status` (`active`/`retired`, default `active`) to `WorkingCopyContact` in
  `backend/src/models/working_copy.py` with the `(working_copy_id, status)` index (data-model.md).
- [X] T007 Create the Alembic migration in `backend/migrations/versions/` for the four new tables,
  `working_copy_contact.status`, and the **partial unique index** on
  `dedup_run(working_copy_id) WHERE status IN ('queued','running')` (FR-007).
- [X] T008 [P] Define the engine seam in `backend/src/integrations/dedup_engine.py`: a `DedupEngine`
  protocol with `run(run_id, input_rows) -> Iterable[MatchRow]` and a `MatchRow` dataclass
  (`wcc_id, z_cluster, z_min_score, z_max_score`) (research D8).
- [X] T009 [P] Implement `FakeDedupEngine` in `backend/src/integrations/dedup_engine.py` (deterministic
  rule-based matcher: same normalised phone or email local-part ⇒ same cluster, synthetic scores) for
  CI; wire engine selection to `DEDUP_ENGINE` config (research D8).
- [X] T010 [P] Implement `contact_flatten` in `backend/src/services/contact_flatten.py`: project a
  `working_copy_contact.payload` → match columns (`wcc_id, first_name, last_name, full_name, email,
  phone, organization`), reusing `contact_fields.py` (research D4).
- [X] T011 [P] Extend `backend/src/services/audit_service.py` with helpers for the new actions
  (`dedup.run.started/completed/failed`, `cluster.merged`, `merge.undone`, `cluster.dismissed`),
  redacted details only (research D10, FR-021).
- [X] T012 Register a `dedup` router and add dedup Pydantic schemas: create
  `backend/src/api/routers/dedup.py` (empty router wired into `backend/src/api/main.py`) and add the
  response/request models from contracts to `backend/src/api/schemas.py`.

**Checkpoint**: Schema migrated, seam + fake engine available, shared services ready — stories can begin.

---

## Phase 3: User Story 1 — Find duplicates in a working copy (Priority: P1) 🎯 MVP

**Goal**: Operator triggers a dedup run; a PG-backed job runs Zingg `match` (or the fake engine) over
the working copy and produces confidence-scored clusters, without changing any contact or the snapshot.

**Independent Test**: On a working copy seeded with known duplicate pairs, `POST` a run, poll to
`completed`, and verify the known duplicates are grouped with scores while the snapshot and contacts
are byte-for-byte unchanged.

### Tests for User Story 1 (write first, must FAIL) ⚠️

- [X] T013 [P] [US1] Contract test for `startDedupRun`/`listDedupRuns`/`getDedupRun` in
  `backend/tests/contract/test_dedup_runs_api.py` (202 enqueue, 409 second active run, run shape).
- [X] T014 [P] [US1] Integration test in `backend/tests/integration/test_dedup_run_ingest.py`:
  FakeDedupEngine output → size-≥2 clusters with `confidence=z_maxScore`; singletons ignored;
  zero-duplicate copy → `cluster_count=0` (US1 AS#2/#3, D5).
- [X] T015 [P] [US1] Integration test in `backend/tests/integration/test_dedup_concurrency.py`:
  second run while one is active is rejected (FR-007 partial unique index).
- [X] T016 [P] [US1] Integration test in `backend/tests/integration/test_snapshot_immutable_dedup.py`:
  snapshot + working-copy payloads identical before/after a run (SC-004, FR-003).
- [X] T017 [P] [US1] Slow integration test in `backend/tests/integration/test_zingg_match_real.py`
  (`@pytest.mark.slow`): real `ZinggDedupEngine` on a seeded set groups ≥90% of true pairs (SC-001).

### Implementation for User Story 1

- [X] T018 [US1] Implement `dedup_service` create-run in `backend/src/services/dedup_service.py`:
  enqueue a `DedupRun` (status `queued`, `model_version`, `confidence_floor`), guarded by the active-run
  rule; emit `dedup.run.started` audit (FR-001, FR-007).
- [X] T019 [US1] Implement run ingest in `backend/src/services/dedup_service.py`: read engine `MatchRow`s,
  group by `z_cluster` (≥2) → `DuplicateCluster` + `ClusterMember`, set `cluster_count`, transition run to
  `completed`, **supersede** prior runs' still-`pending` clusters; emit `dedup.run.completed`/`failed`
  (FR-005/FR-006/FR-008, D5/D7).
- [X] T020 [US1] Implement the PG-backed `dedup_worker` in `backend/src/workers/dedup_worker.py`:
  claim a `queued`/`running` `DedupRun` with `FOR UPDATE SKIP LOCKED`, build the input projection via
  `contact_flatten`, invoke the configured `DedupEngine`, call ingest, handle retry/failure (mirrors
  `import_worker`; research D1/D7).
- [X] T021 [P] [US1] Implement `ZinggDedupEngine` in `backend/dedup/zingg_engine.py`: JDBC input/output
  pipes, `ClientOptions.PHASE=match`, load bundled model, write `dedup_match_raw`, return `MatchRow`s;
  define contact `FieldDefinition`s in `backend/dedup/field_defs.py` (research D2/D3/D4).
- [X] T022 [US1] Implement the dedup-runs endpoints in `backend/src/api/routers/dedup.py`:
  `POST /working-copies/{id}/dedup-runs` (202/409), `GET /working-copies/{id}/dedup-runs`,
  `GET /dedup-runs/{runId}` (contracts/openapi.yaml).
- [X] T023 [P] [US1] Frontend run controls: `frontend/src/services/dedup.ts` (typed client),
  `frontend/src/stores/dedup.ts` (Pinia: start + poll run), and
  `frontend/src/components/DedupRunPanel.vue` (trigger + progress/terminal status) on a new
  `frontend/src/pages/WorkingCopyDedup.vue` route.
- [X] T024 [P] [US1] Frontend test `frontend/tests/dedup-run.spec.ts` (Vitest + Vue Test Utils):
  starting a run shows progress and a completed cluster count.

**Checkpoint**: A run produces confidence-scored clusters; snapshot untouched — MVP demoable.

---

## Phase 4: User Story 2 — Review duplicate clusters (Priority: P2)

**Goal**: Operator browses a completed run's clusters: members side-by-side with key fields and a
confidence score, ordered/filterable by confidence, read-only.

**Independent Test**: With a completed run present, list clusters and confirm each shows members with
names/emails/phones and a confidence score, sorted by confidence, with no mutation on view.

### Tests for User Story 2 (write first, must FAIL) ⚠️

- [X] T025 [P] [US2] Contract test for `listClusters`/`getCluster` in
  `backend/tests/contract/test_clusters_api.py` (ordering by confidence desc, `minConfidence` filter,
  409 when run not completed).
- [X] T026 [P] [US2] Integration test in `backend/tests/integration/test_cluster_review.py`:
  members carry `ContactSummary` (display name/email/phone/org); viewing changes nothing (FR-013).

### Implementation for User Story 2

- [X] T027 [US2] Implement review queries in `backend/src/services/cluster_service.py`:
  list clusters for a run (filter by status/`minConfidence`, order by confidence desc) and fetch one
  cluster with members + `ContactSummary` projection (FR-010/FR-011/FR-012, D5). All lookups MUST be
  scoped by `working_copy_id` (resolved from the run/cluster) so cross-account/cross-working-copy ids
  return not-found and never leak another account's data (FR-022).
- [X] T028 [US2] Implement `GET /dedup-runs/{runId}/clusters` and `GET /clusters/{clusterId}` in
  `backend/src/api/routers/dedup.py` (contracts/openapi.yaml).
- [X] T029 [P] [US2] Frontend review UI: `frontend/src/components/ClusterList.vue`,
  `ClusterCard.vue`, `ConfidenceBadge.vue`, wired into `WorkingCopyDedup.vue` and `stores/dedup.ts`
  (sorted list, confidence filter, read-only member details).
- [X] T030 [P] [US2] Frontend test `frontend/tests/cluster-list.spec.ts`: clusters render sorted by
  confidence with member fields; viewing triggers no mutation calls.

**Checkpoint**: US1 + US2 both work independently — operator can detect and review duplicates.

---

## Phase 5: User Story 3 — Resolve a cluster: merge or dismiss (Priority: P3)

**Goal**: Operator merges a cluster into one survivor contact (reversible) inside the working copy, or
dismisses it as "not a duplicate" — never automatically, snapshot untouched.

**Independent Test**: Merge a cluster → one combined survivor remains, others retired, action audited,
undo restores the exact pre-merge state; dismiss leaves members separate; snapshot unchanged throughout.

### Tests for User Story 3 (write first, must FAIL) ⚠️

- [X] T031 [P] [US3] Contract test for `getMergePreview`/`mergeCluster`/`dismissCluster`/`undoMerge` in
  `backend/tests/contract/test_cluster_resolve_api.py` (preview shape, 200s, 409 conflicts).
- [X] T032 [P] [US3] Integration test in `backend/tests/integration/test_merge_survivor.py`:
  merge updates survivor payload (field union), retires non-survivors, writes `MergeRecord`, marks
  cluster `merged`, audits `cluster.merged`; snapshot unchanged (FR-016, SC-004).
- [X] T033 [P] [US3] Integration test in `backend/tests/integration/test_merge_undo.py`:
  undo restores survivor payload + retired members exactly; repeated merge/undo cycles return the
  working copy's `active` set to its pre-dedup state (FR-018, SC-003).
- [X] T034 [P] [US3] Integration test in `backend/tests/integration/test_resolve_guards.py`:
  resolving a cluster with a non-`active` member is blocked (FR-020); resolving a `superseded` cluster
  is rejected (FR-008 stale-cluster edge case); dismiss is per-run and a re-run re-detects the pair
  (FR-019); no cluster is resolved without an explicit action (SC-005).
- [X] T034a [P] [US3] Integration test in `backend/tests/integration/test_dedup_isolation.py`:
  runs, clusters, and merges for working copy A (account 1) are invisible and non-actionable from
  account 2 / another working copy — list/get/merge/dismiss/undo against a cross-account id return
  not-found/forbidden, never another account's data (FR-022, Principle I).

### Implementation for User Story 3

- [X] T035 [US3] Implement merge-preview builder in `backend/src/services/cluster_service.py`:
  choose default survivor (most complete), union non-conflicting fields, surface single-value
  conflicts + chosen default (FR-015, D6).
- [X] T036 [US3] Implement `merge` in `backend/src/services/cluster_service.py`: apply survivor payload,
  set non-survivors `retired`, write `MergeRecord`, mark cluster `merged`, audit `cluster.merged`;
  reject if not `pending` or any member not `active` (FR-016/FR-020).
- [X] T037 [US3] Implement `dismiss` and `undo` in `backend/src/services/cluster_service.py`:
  dismiss (per-run, audit `cluster.dismissed`); undo a `MergeRecord` (restore survivor + reactivate
  retired, cluster → `pending`, audit `merge.undone`) (FR-018/FR-019, D6).
- [X] T038 [US3] Implement the resolve endpoints in `backend/src/api/routers/dedup.py`:
  `GET /clusters/{id}/merge-preview`, `POST /clusters/{id}/merge`, `POST /clusters/{id}/dismiss`,
  `POST /merge-records/{id}/undo` (contracts/openapi.yaml).
- [X] T039 [P] [US3] Frontend resolve UI: `frontend/src/components/MergePreview.vue` (survivor pick +
  conflict overrides) and merge/dismiss/undo actions in `ClusterCard.vue` + `stores/dedup.ts`.
- [X] T040 [P] [US3] Frontend test `frontend/tests/merge-resolve.spec.ts`: preview shows conflicts;
  confirming merge collapses the cluster; undo restores it; dismiss removes it from the pending list.
  Assert the resolve flow is **single-confirmation** (open cluster → one merge/dismiss action), the
  buildable proxy for SC-007's <15s interaction target.

**Checkpoint**: All three stories independently functional — detect, review, resolve.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verification, hardening, and docs spanning all stories.

- [X] T041 [P] Unit tests in `backend/tests/unit/` for `contact_flatten` projection, survivor field-union
  rules, and `z_max/min` → confidence mapping.
- [X] T042 [P] Add log redaction + structured logging assertions in
  `backend/tests/integration/test_audit_redaction.py`: every dedup run/merge/undo/dismiss is audited
  with no payloads/secrets (SC-006, FR-021).
- [X] T043 Performance check (`@pytest.mark.slow`) in `backend/tests/integration/test_dedup_perf.py`:
  a ~50k-contact working copy completes within ~30 min via the real engine (SC-002, D9). Pin the
  **reference baseline** in the test docstring/quickstart (e.g. 4 vCPU / 8 GB RAM, Spark driver 4 GB,
  `numPartitions=8`) so the target is reproducible.
- [X] T044 [P] Document the bundled-model training procedure once, canonically, in
  `backend/dedup/model/README.md`; have `specs/002-zingg-dedup/quickstart.md` and the root `README.md`
  **link** to it (no duplicated procedure text) to avoid drift.
- [X] T045 Run `quickstart.md` Scenarios A–E end-to-end against docker-compose and fix any gaps;
  while doing so, confirm the JDBC/Spark data path stays on the internal compose network only — no
  contact data egresses the deployment boundary (FR-023, Principle I).
- [X] T046 Run full gate: `pytest -q` (fake engine), `pytest -q -m slow` (real Zingg),
  `frontend` Vitest, and `npx biome ci .` — all green (constitution quality gate).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup — **BLOCKS all user stories**.
- **User Stories (Phase 3–5)**: all depend on Foundational. US1 → US2 → US3 in priority order; US2/US3
  build on US1's clusters but each remains independently testable with seeded data.
- **Polish (Phase 6)**: depends on the desired stories being complete.

### User Story Dependencies

- **US1 (P1)**: only Foundational. Delivers the MVP (detect duplicates).
- **US2 (P2)**: Foundational; consumes US1 clusters (seedable independently).
- **US3 (P3)**: Foundational; resolves US1 clusters (seedable independently).

### Within Each User Story

- Tests written first and FAIL before implementation (Principle IV).
- Models → services → endpoints → frontend.
- `dedup_service`/`cluster_service` before their routers; routers before frontend wiring.

### Parallel Opportunities

- Setup: T003, T004 in parallel.
- Foundational: T008, T009, T010, T011 in parallel (distinct files) after T005–T007.
- US1 tests T013–T017 in parallel; impl T021 (engine) and T023/T024 (frontend) parallel to backend
  service work once the seam exists.
- US2 tests T025–T026 parallel; US3 tests T031–T034a parallel.
- Polish: T041, T042, T044 in parallel.

---

## Parallel Example: User Story 1

```bash
# Tests first (parallel):
Task: "Contract test dedup-runs API in backend/tests/contract/test_dedup_runs_api.py"
Task: "Integration test ingest→clusters in backend/tests/integration/test_dedup_run_ingest.py"
Task: "Integration test concurrency 409 in backend/tests/integration/test_dedup_concurrency.py"
Task: "Integration test snapshot immutable in backend/tests/integration/test_snapshot_immutable_dedup.py"

# Then parallel implementation across files:
Task: "ZinggDedupEngine in backend/dedup/zingg_engine.py"
Task: "Frontend run panel in frontend/src/components/DedupRunPanel.vue"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational (CRITICAL) → 3. Phase 3 US1 → **STOP & VALIDATE** a run
   produces clusters with the snapshot untouched → demo.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → detect duplicates (MVP).
3. US2 → review surface.
4. US3 → reversible merge / dismiss.
Each story adds value without breaking the previous ones.

---

## Notes

- [P] = different files, no dependencies. [Story] labels map tasks to US1/US2/US3 for traceability.
- The real Zingg/Spark path is exercised only behind the `DedupEngine` seam; the default CI lane uses
  `FakeDedupEngine` and excludes `@pytest.mark.slow` (no Spark/JVM in CI) — Principle IV.
- Non-destructive guarantees (snapshot byte-identical, reversible merges) are encoded as tests
  (T016, T032, T033) — verify they pass before claiming completion.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
