---
description: "Task list for 006-validate-normalize"
---

# Tasks: Validate & Normalize (Tidy step)

**Input**: Design documents from `specs/006-validate-normalize/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/validation-api.md, quickstart.md

**Tests**: Included. Constitution Principle IV (Test-First, NON-NEGOTIABLE) requires failing tests
before implementation for behavior with correctness/safety implications — here phone/email/website
validation, the auto-vs-queue split, reversible edits, the SSRF guard, and the wizard derivation.
Backend specs use `pytest` (+ `respx` for httpx, monkeypatch for DNS/geoip); frontend specs use
`vitest`. **Write each test task and confirm it FAILS before its implementation task.**

**Scope reminder**: Touches **both** tiers. Backend gains a self-contained validation slice (model →
stateless checkers → `validation_service` → worker → router) reusing StagedEdit/undo/audit (feature
003); frontend adds a 7th wizard step. No Google push, no new OAuth scope, no existing endpoint
changed. Backend paths under `backend/`, frontend under `frontend/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 / US3 (maps to spec.md user stories)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Bring in the validation libraries and tunables.

- [X] T001 Add runtime deps to `backend/pyproject.toml`: `phonenumbers`, `email-validator`
  (pulls `dnspython`), promote `httpx` from `[dev]` to runtime; add optional `geoip2` (note: GeoLite2
  DB is operator-supplied via `geoip_db_path`). Run `uv sync` / `pip install -e .`.
- [X] T002 Add settings to `backend/src/core/config.py`: `phone_default_region="KZ"`,
  `website_check_timeout_seconds=5.0`, `website_check_concurrency=8`, `website_check_max_redirects=5`,
  `geoip_db_path=""` (per data-model.md Settings table).
- [X] T003 [P] Confirm baselines before any feature work: `cd backend && pytest -m "not slow"` green and
  `cd frontend && npm run build` (`vue-tsc -b && vite build`) green.

**Checkpoint**: Deps installed; settings present; baselines green.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Persistence, the stateless checker services (shared by US1 + US2), and the router/worker/
frontend scaffolding every story renders inside.

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete.

### Persistence & schemas

- [X] T004 Create Alembic migration `backend/migrations/versions/0005_validate_normalize.py` adding
  `validation_run` and `validation_item` tables per data-model.md (FKs, indexes
  `ix_validation_run_copy_status`, `ix_validation_item_run_status`); `alembic upgrade head`.
- [X] T005 [P] Create `backend/src/models/validation.py`: `ValidationRun` + `ValidationItem` ORM models
  and the status/issue string sets (`VALIDATION_RUN_STATES`, `FIELD_KINDS`, `ISSUE_TYPES`,
  `VALIDATION_ITEM_STATES`); register in `backend/src/models/__init__.py`.
- [X] T006 [P] Widen `EDIT_KINDS` in `backend/src/models/triage.py` to `("edit","transliterate","normalize")`
  and update the `StagedEdit.kind` comment (no DDL — column is already `String(16)`).
- [X] T007 Add `Validation*` Pydantic schemas to `backend/src/api/schemas.py`: `StartValidationBody`,
  `ValidationRunOut`, `ValidationItemOut`, `ResolveValidationItemBody`, `DetectRegionOut` per
  contracts/validation-api.md.

### Stateless checker services (TDD — tests FIRST, must fail)

- [X] T008 [P] Unit test `backend/tests/unit/test_phone_normalizer.py`: KZ/RU national + `+E.164`
  inputs → validity, E.164 string, `mobile` vs unclear (fixed-line / `FIXED_LINE_OR_MOBILE`).
- [X] T009 [P] Unit test `backend/tests/unit/test_email_validator_service.py`: syntax pass/fail; MX
  present vs absent (monkeypatch `email_validator`'s deliverability/DNS).
- [X] T010 [P] Unit test `backend/tests/unit/test_website_checker.py` (respx + monkeypatched resolver):
  200/302→final/403/timeout/connection-error → reachable vs `website_unreachable`; `http→https`
  upgrade only when https responds; **SSRF guard** rejects `127.0.0.1`/RFC1918/`169.254.169.254`/ULA on
  the initial URL **and** on a redirect hop → `website_unsafe`, no fetch.
- [X] T011 [P] Unit test `backend/tests/unit/test_region_service.py`: public IP + GeoLite2 → region;
  private/loopback IP or missing DB → `null` (monkeypatch geoip2).
- [X] T012 [P] Implement `backend/src/services/phone_normalizer.py` (parse/validate/E.164/`number_type`
  → mobile-or-unclear) to pass T008.
- [X] T013 [P] Implement `backend/src/services/email_validator_service.py` (syntax + MX via
  `email-validator`; classify `invalid_email` vs `dead_email_domain`) to pass T009.
- [X] T014 [P] Implement `backend/src/services/website_checker.py` (`httpx` sync+async, manual redirect
  loop capped at `website_check_max_redirects`, per-hop SSRF guard via `socket.getaddrinfo` +
  `ipaddress`, timeout) returning reachable / upgrade-https / `website_unreachable` / `website_unsafe`
  to pass T010.
- [X] T015 [P] Implement `backend/src/services/region_service.py` (GeoLite2 lookup when `geoip_db_path`
  set + public IP, else `None`) to pass T011.

### Router / worker / frontend scaffolding

- [X] T016 Create router skeleton `backend/src/api/routers/validation.py` (empty `APIRouter(prefix="/api")`),
  register it in `backend/src/api/routers/__init__.py` and `backend/src/api/main.py`.
- [X] T017 Create worker skeleton `backend/src/workers/validation_worker.py` with `claim_next_run`
  (`FOR UPDATE SKIP LOCKED` over `queued`/`running` `ValidationRun`) + `run_once`, and add
  `("validation", validation_worker.run_once)` to the loop in `backend/src/workers/run_all.py`.
- [X] T018 Add `'tidy'` to `frontend/src/wizard/steps.ts` at **index 6** (label "Tidy", description,
  route `/wizard/tidy`, `prerequisiteKey: 'review'`, `isLongJob: true`, an icon); set **Export** to
  index 7 with `prerequisiteKey: 'tidy'`.
- [X] T019 Add the `/wizard/tidy` child route (before `export`) → `@/pages/wizard/TidyStep.vue` in
  `frontend/src/router/index.ts`.
- [X] T020 [P] Create tidy Pinia store skeleton `frontend/src/stores/tidy.ts` (state for current run +
  items + region; empty actions filled in US1/US2).
- [X] T021 [P] Add validation endpoint stubs + types to `frontend/src/services/api.ts`
  (`startValidationRun`, `listValidationRuns`, `getValidationRun`, `listValidationItems`,
  `resolveValidationItem`, `skipValidationItem`, `undoStagedEdit`, `detectRegion`).
- [X] T022 [P] Create `frontend/src/pages/wizard/TidyStep.vue` skeleton + `frontend/src/components/tidy/`
  directory (hosts the panel/queue components filled in US1/US2).

**Checkpoint**: Tables migrated; checkers green; router/worker/step scaffolding renders an empty Tidy
step inside the wizard.

---

## Phase 3: User Story 1 — Auto-clean the obvious things (Priority: P1) 🎯 MVP

**Goal**: A background run over the Draft's kept contacts auto-applies E.164, confident-mobile type,
and `http→https` (when https reachable) as reversible StagedEdits, with a summary and undo.

**Independent Test**: Seed a Draft with a badly-formatted valid phone, a typeless mobile, and an
`http://` site whose https works; start a run; verify the phone is E.164, the type is `mobile`, the
site is `https://`, `autoAppliedCount` reflects them, and each is undoable to its exact prior value.

### Tests for US1 (write first, must fail) ⚠️

- [X] T023 [P] [US1] Integration test `backend/tests/integration/test_validation_auto.py`: seeded Draft
  → auto StagedEdits (E.164 / mobile type / http→https) + correct `checked/auto_applied` counts;
  **idempotent re-run** stages nothing new; original snapshot untouched.
- [X] T024 [P] [US1] Contract test `backend/tests/contract/test_validation_run_api.py`: `POST
  /working-copies/{id}/validation-runs` (201; 409 when one is active) and `GET /validation-runs/{id}`
  shapes per contract.
- [X] T025 [P] [US1] Worker test `backend/tests/integration/test_validation_worker.py`: a `queued` run
  is claimed and driven to `completed`; counts populated; resumes if re-claimed.
- [X] T026 [P] [US1] Frontend test `frontend/tests/tidy-store.spec.ts`: tidy store `startRun` →
  poll → summary counts; undo calls `undoStagedEdit`.

### Implementation for US1

- [X] T027 [US1] Implement the auto path in `backend/src/services/validation_service.py`: create/claim/
  complete a `ValidationRun`, compute the **kept set** (latest `TriageDecision != 'delete'`), iterate
  phones/websites, apply E.164 / mobile-type / http→https via a `_stage(...)` `kind="normalize"`
  StagedEdit (reuse the `processing_service` staging pattern + `audit_service`), increment counts.
- [X] T028 [US1] Implement run endpoints in `backend/src/api/routers/validation.py`: `POST
  /working-copies/{id}/validation-runs`, `GET /working-copies/{id}/validation-runs` (list,
  newest-first — needed by the wizard derivation/restore, FR-003), and `GET /validation-runs/{id}`,
  wired to the service/schemas. `ValidationRunOut.pendingCount` is computed live as
  `COUNT(items WHERE status='pending')` at serialization (not a stored column).
- [X] T029 [US1] Implement `validation_worker.run_once` body: claim a `queued` run and call
  `validation_service.run(...)` to terminal; fan out website checks with
  `asyncio.Semaphore(website_check_concurrency)` over `httpx.AsyncClient`; set `failed`+`last_error`
  on unhandled error.
- [X] T030 [US1] Expose/confirm the staged-edit undo route `POST /api/staged-edits/{id}/undo` (reuse
  `processing_service.undo_staged_edit`; add to the triage or validation router if not already routed)
  so US1 auto-fixes are reversible per FR-022.
- [X] T031 [US1] Implement tidy store actions in `frontend/src/stores/tidy.ts`: `startRun(defaultRegion)`,
  `pollRun` (to terminal, reusing the export-poll cadence), `summary`, `undoEdit`.
- [X] T032 [US1] Build `frontend/src/components/tidy/TidyRunPanel.vue`: start button → running state →
  summary counts (auto-applied / queued / checked) with an undo affordance; render it in
  `TidyStep.vue`. Wire `frontend/src/services/api.ts` run + undo calls.

**Checkpoint**: A run cleans the obvious things end-to-end and every change is undoable; US1 testable
via API + the Tidy panel.

---

## Phase 4: User Story 2 — Work a queue of human-only decisions (Priority: P1)

**Goal**: Everything uncertain/broken (invalid phone, unclear type, invalid email, dead email domain,
unreachable website, SSRF-unsafe website) is queued with explicit, labeled resolution actions.

**Independent Test**: Seed a Draft with an unparseable phone, a typeless fixed-line, a
syntactically-invalid email (`bob@@example`), `mail@gmial.com` (dead domain), a dead site, and
`http://127.0.0.1/`; run; verify one queue item per finding with the correct `issueType` — including
both `invalid_email` and `dead_email_domain` — and no fetch to `127.0.0.1`; resolve one (StagedEdit
created) and skip one (unchanged).

### Tests for US2 (write first, must fail) ⚠️

- [X] T033 [P] [US2] Integration test `backend/tests/integration/test_validation_queue.py`: each of the
  six `issue_type`s is produced for the right input — seed must include a **syntactically invalid**
  email (→ `invalid_email`) **and** a dead-domain email (→ `dead_email_domain`) as distinct cases,
  plus `website_unsafe` with **no** outbound request; assert `suggested_value` set for `unclear_type`.
- [X] T034 [P] [US2] Contract test `backend/tests/contract/test_validation_items_api.py`: list items,
  `resolve` (set_type / edit_value / remove_field → StagedEdit + `staged_edit_id`; 409 on re-resolve),
  `skip` (unchanged) per contract.
- [X] T035 [P] [US2] Frontend test `frontend/tests/tidy-queue.spec.ts`: queue renders one row per item
  with issue-appropriate actions; resolve/skip/undo call the right api methods and update counts.

### Implementation for US2

- [X] T036 [US2] Extend `backend/src/services/validation_service.py`: create `ValidationItem` rows for
  `invalid_phone` / `unclear_type` (+`suggested_value` = E.164) / `invalid_email` /
  `dead_email_domain` / `website_unreachable` / `website_unsafe`, incrementing `queued_count`.
- [X] T037 [US2] Implement resolution in `validation_service.py`: `resolve_item` (set_type / edit_value
  / remove_field → reversible StagedEdit, link `staged_edit_id`, audit, mark `resolved`; re-validate a
  phone `edit_value` and keep `pending` if still invalid) and `skip_item` (mark `skipped`, no edit).
- [X] T038 [US2] Implement item endpoints in `backend/src/api/routers/validation.py`: `GET
  /validation-runs/{id}/items`, `POST /validation-items/{id}/resolve`, `POST /validation-items/{id}/skip`.
- [X] T039 [US2] Wire `listValidationItems` / `resolveValidationItem` / `skipValidationItem` in
  `frontend/src/services/api.ts` and add queue actions to `frontend/src/stores/tidy.ts`.
- [X] T040 [US2] Build `frontend/src/components/tidy/TidyQueue.vue` + `TidyQueueItem.vue`: per-issue
  labeled actions (choose type / edit value / remove field / skip) with immediate feedback; render the
  queue under the panel in `TidyStep.vue`.

**Checkpoint**: MVP complete — kept contacts are validated + normalized, with a working manual queue;
US1 + US2 testable independently.

---

## Phase 5: User Story 3 — Tidy fits the wizard like every other step (Priority: P2)

**Goal**: Tidy behaves as the 7th step: running state, navigate-away/return, reload-restore, a
highlighted+changeable parsing region, and passability with a clear warning.

**Independent Test**: Start Tidy, navigate away and back (still running), reload (run + queue
restored), see the region highlighted, and Continue to Export with open items showing a warning.

### Tests for US3 (write first, must fail) ⚠️

- [X] T041 [P] [US3] Frontend test `frontend/tests/steps.spec.ts`: `WIZARD_STEPS` has 7 entries with
  `tidy` between `review` and `export`, and `export.prerequisiteKey === 'tidy'`.
- [X] T042 [P] [US3] Frontend test `frontend/tests/wizard-tidy.spec.ts`: wizard store derives `tidy`
  `completed`/`running`/`emptyButPassable` from the latest run, `passable('tidy') === true`, and Export
  is gated on Tidy.
- [X] T043 [P] [US3] Frontend test `frontend/tests/tidy-region.spec.ts`: region detection
  (`detectRegion` → fallback to `navigator.language`) sets the highlighted default; passable-with-
  warning surfaces the unresolved count.

### Implementation for US3

- [X] T044 [US3] Extend `frontend/src/stores/wizard.ts`: add `validationRuns` state + `loadTidy()`, and
  `completed/running/emptyButPassable` for `tidy` plus `passable('tidy') === true` (join `review`);
  Export gating follows from `steps.ts` (T018). Persist nothing new server-side.
- [X] T045 [US3] Region setting: `region_service` detect endpoint `GET /api/settings/detect-region` in
  `validation.py`; frontend `detectRegion()` + `navigator.language`/timezone fallback; persist the
  chosen region in localStorage and render it **highlighted + changeable** in `TidyRunPanel.vue`;
  pass it as `defaultRegion` to `startRun`.
- [X] T046 [US3] Passability + lifecycle UX in `TidyStep.vue`/`TidyRunPanel.vue`: Continue-to-Export
  with a warning of unresolved-item count (explicit confirmed action, FR-004); restore run + queue on
  reload/return; keep showing running when navigated away; surface failure + retry (FR-005).

**Checkpoint**: Tidy is a first-class wizard step consistent with Backup/Merge/Export.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T047 [P] Verify auditability (Principle V): every auto-fix, resolution, and undo writes an
  `audit_service` entry (before→after/why); structured logs redact secrets/PII; `last_error` redacted.
- [X] T048 [P] Confirm the `worker` container runs the combined loop (no compose change needed since
  `validation_worker` is in `run_all.py`); document the optional `GEOIP_DB_PATH` / website-check env
  knobs in the backend README.
- [X] T049 [P] Green gates: `cd backend && pytest -m "not slow"`, `cd frontend && npm run lint`
  (`biome ci .`) + `npm run build` (`vue-tsc`), then run `specs/006-validate-normalize/quickstart.md`
  end-to-end (incl. the SSRF no-request check).

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (P1)**: no deps.
- **Foundational (P2)**: depends on Setup; **blocks all user stories**. Within P2, checker tests
  (T008–T011) precede their impl (T012–T015); migration/models (T004–T006) precede the service work in
  later phases.
- **US1 (P3)** and **US2 (P4)** are both P1 and together form the MVP. US2 depends on US1's
  `validation_service` run scaffolding (T027) and worker (T029); otherwise their UI tasks are
  independent. US1 should land first (run + auto path), then US2 layers the queue.
- **US3 (P5, P2-priority)**: depends on the Tidy step existing (Foundational) and a run to derive state
  from (US1); can be built after US1, in parallel with US2's frontend.
- **Polish (P6)**: after the desired stories are complete.

### Within each story

- Tests first and FAILING before implementation (Principle IV).
- Backend: models → service → endpoints → worker; Frontend: store → components.

### Parallel opportunities

- Setup T003 is independent.
- Foundational: T005/T006 [P]; all checker tests T008–T011 [P]; all checker impls T012–T015 [P] (after
  their tests); frontend scaffolding T020/T021/T022 [P].
- US1 tests T023–T026 [P]; US2 tests T033–T035 [P]; US3 tests T041–T043 [P].
- US2 frontend (T039/T040) can proceed alongside US3 frontend (T044–T046) once US1 lands.

---

## Parallel Example: Foundational checkers

```bash
# Write the four checker unit tests together (must fail):
Task: "Unit test phone_normalizer in backend/tests/unit/test_phone_normalizer.py"
Task: "Unit test email_validator_service in backend/tests/unit/test_email_validator_service.py"
Task: "Unit test website_checker (incl. SSRF) in backend/tests/unit/test_website_checker.py"
Task: "Unit test region_service in backend/tests/unit/test_region_service.py"

# Then implement them together (different files):
Task: "Implement phone_normalizer in backend/src/services/phone_normalizer.py"
Task: "Implement email_validator_service in backend/src/services/email_validator_service.py"
Task: "Implement website_checker in backend/src/services/website_checker.py"
Task: "Implement region_service in backend/src/services/region_service.py"
```

---

## Implementation Strategy

### MVP (US1 + US2)

1. Phase 1 Setup → Phase 2 Foundational (checkers green, scaffolding renders).
2. Phase 3 US1 → **STOP & validate**: a run cleans the obvious things, all undoable.
3. Phase 4 US2 → **STOP & validate**: the manual queue resolves the rest. This is the shippable MVP —
   kept contacts are validated and normalized with full human control and reversibility.

### Incremental delivery

4. Phase 5 US3 → the step becomes a polished, passable wizard member (running/restore/region/warning).
5. Phase 6 Polish → audit/log verification, env docs, full quickstart + gate run.

---

## Notes

- [P] = different files, no incomplete-task dependency.
- Reuse, don't reinvent: StagedEdit/undo/audit (003), the combined worker + `FOR UPDATE SKIP LOCKED`
  (002/004), the running-state + poll pattern (004/005).
- Safety invariants to keep green throughout: no Google push from Tidy; all changes reversible
  StagedEdits on the Draft; snapshot never touched; SSRF guard fires on every redirect hop; no SMTP
  probing.
- Commit after each task or logical group; verify tests fail before implementing.
