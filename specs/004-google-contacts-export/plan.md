# Implementation Plan: Export Triage Results to Google Contacts

**Branch**: `feature/004-export-to-google` (git) · `004-google-contacts-export` (spec dir) | **Date**: 2026-06-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-google-contacts-export/spec.md`

## Summary

This is the **write-to-Google export** that commits the staged triage results from feature 003. It
performs exactly two kinds of Google write, surfaced together on one **Export** screen and executed as
a background job in the existing `worker`:

1. **Delete** — every active survivor whose latest terminal decision is `delete` is deleted in Google.
   This **reuses, unchanged, feature 003's already-built path**: `DeleteBatch` → `DeletionRecord`
   (snapshot persisted before any call), dry-run preview, explicit per-batch confirmation, idempotent
   `people.deleteContact`, `404 → skipped_absent = success`, and undo via `people.createContact`.
2. **Label `Process`** — every active survivor that was routed to the Processing Queue and is **not**
   in the deletion set gets a `Process` label (a Google **contact group**) so the operator can filter to
   exactly those contacts in Google Contacts and finish reviewing them by hand. This is **new**: a
   `LabelBatch` → `LabelAssignment` flow mirroring the delete path (idempotent, reversible, `404 →
   skipped_absent`, audited). Per the clarification, the export applies the label **only** — it does
   **not** push the staged edits/transliterations to Google (those stay in the working copy).

An **ExportRun** orchestrates the two: it derives both sets from current terminal decisions, **warns and
excludes** undecided survivors (FR-017a), runs as a background job (deletes still require their explicit
confirmation; labeling runs alongside), and produces a per-action **report** with undo entry points.

The key external finding (research D1): Google's contact-group operations (`contactGroups.create`,
`contactGroups.members.modify`) use the **same `…/auth/contacts` scope already requested for deletion in
feature 003** — so **this feature introduces NO new OAuth scope and no new consent step** beyond the
write grant 003 already established. The existing `account_has_write_scope` gate covers labeling too.

## Technical Context

**Language/Version**: Python 3.12 (backend + existing worker); TypeScript 5.x (frontend). No JVM/Spark.

**Primary Dependencies**: existing — FastAPI, SQLAlchemy 2.x + Alembic, psycopg, Pydantic, Vue 3 + Vite
+ Pinia, Biome. **Reused as-is**: `delete_batch_service`, `delete_worker`, `PeopleWriteClient`
(delete/create), `account_has_write_scope`, `audit_service`. **New**: contact-group methods on the
`PeopleWriteClient` seam (`ensure_label`, `add_label_members`, `remove_label_members`) + their CI fake;
`label_batch_service` and `export_service`; an export/label REST router; a `LabelBatch` consumer added
to the existing combined worker loop (`run_all.py`). No new third-party dependency, no network service.

**Storage**: PostgreSQL. Alembic `0004` adds `export_run`, `label_batch`, `label_assignment`, and
`contact_label` (the resolved `Process` group resourceName per account), plus new `AuditEntry.action`
values. **Reuses** `delete_batch`/`deletion_record` (003) and `working_copy_contact` (the deletion/label
sets derive from `status='active'` rows + their `TriageDecision`/`ProcessingItem`). No existing table is
altered; the immutable `snapshot`/`snapshot_contact` foundation is never touched.

**Testing**: backend `pytest` against the **`PeopleWriteClient` seam** — the fake is extended with
contact-group state so labeling create/assign/remove, idempotency, `404 → skipped_absent`, and
partial-failure retry are all tested with **no live Google in CI** (Principle IV). FastAPI `TestClient`
for the export/label API contract; integration tests for the full export run (derive sets → confirm
delete → label → report → undo) and for set-disjointness / undecided-warning / scope-gating; frontend
`Vitest` + Vue Test Utils for the Export screen, confirmation, and report. Biome `ci` gate. A
slow-marked integration test may exercise the real Google contact-group path outside the default lane.

**Target Platform**: Linux containers via docker-compose; reuses `db`, `backend`, `worker`, `web`. The
label work runs in the **existing `worker`** (its combined `run_all.py` loop gains a label-batch claim);
no new service, consistent with 003's delete worker.

**Performance Goals**: the export is non-blocking — both writes run as a background job (FR-019a); the
Export screen reflects live progress. No per-card latency budget applies (unlike 003's swipe). Google
I/O stays off the request path; rate-limit/transient errors are retried with the existing backoff and
leave completed work committed (idempotent re-run).

**Constraints**: non-destructive — 100% of the deletion set has a restorable snapshot before any delete
(SC-001, reused from 003); explicit per-batch delete confirmation (FR-006); labeling is additive and
reversible (remove membership, FR-014); both writes idempotent and `404 → skipped_absent` (FR-007/008/
012a); the export never writes with a scope the account has not granted (FR-020, SC-008); deletion and
label sets are disjoint and governed by the latest terminal decision (FR-002); per-account/per-working-
copy isolation (FR-021); staged edits are **not** pushed (FR-013); audit + PII redaction throughout
(FR-022/023).

**Scale/Scope**: single self-hosted operator; multiple Google accounts; up to ~50,000 contacts per
working copy; typical export tens–hundreds of deletes and tens–hundreds of labels.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How this plan complies |
|-----------|--------|------------------------|
| I. Privacy & Data Protection | ✅ PASS (no new deviation) | **No new OAuth scope.** Labeling uses Google `contactGroups`, covered by the **same `…/auth/contacts` write scope feature 003 already requested via incremental consent** — the existing `account_has_write_scope` gate guards both delete and label writes (a write is refused, with a re-consent prompt, when the scope is absent — FR-020/SC-008). No broader grant than 003's recorded one. Contact PII leaves the box only via the unavoidable delete/label calls for contacts the operator chose; tokens stay encrypted in `Credential`, never logged/returned. Per-account/per-working-copy isolation (FR-021). |
| II. Non-Destructive by Default | ✅ PASS | Deletion reuses 003's guarded path: snapshot-before-delete (SC-001), dry-run preview, explicit per-batch confirm (FR-004/005/006), idempotent, undoable (FR-007/009). Labeling is inherently **additive and reversible** — membership can be removed within the retention window (FR-014); it edits/deletes no contact data and does **not** push staged edits (FR-013). Both treat `404` as already-satisfied success (FR-008/012a). |
| III. Human-in-the-Loop | ✅ PASS | The export acts only on **explicit** terminal triage decisions; undecided survivors are **warned and excluded**, never acted on by default (FR-017a). Deletion still requires explicit per-batch confirmation (FR-006). Labeling is the operator's deliberate mechanism to **re-check** contacts by hand in Google — automation marks, the human disposes. |
| IV. Test-First | ✅ PASS | TDD throughout; the extended `PeopleWriteClient` fake lets CI cover label create/assign/remove, idempotency, `404→skipped_absent`, partial-failure retry, set-disjointness, undecided-exclusion, and scope-gating — **no live Google in CI**. Reused delete behavior keeps its existing tests. |
| V. Auditability & Observability | ✅ PASS | Append-only `AuditEntry` extended: `export.run.started/completed`, `label.group.created`, `label.batch.committed`, `contact.labeled`, `contact.unlabeled` — each with target + before-state ref, redacted details (no payloads/PII/secrets), and (for Google writes) the API result. Delete actions reuse 003's `delete.batch.*`/`contact.deleted`/`contact.restored`. Rate-limit/quota handling surfaced and retryable (FR-024). |

**Result**: PASS — **no new deviation**. The only standing deviation (the `…/auth/contacts` write scope)
was already justified and recorded in feature 003; this feature reuses it without widening it, so
Complexity Tracking has no new entry.

## Project Structure

### Documentation (this feature)

```text
specs/004-google-contacts-export/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── openapi.yaml     # Phase 1 output — export / label-batch REST contract
├── checklists/
│   └── requirements.md  # Spec quality checklist (from /speckit-specify)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   └── export.py               # NEW: ExportRun, LabelBatch, LabelAssignment, ContactLabel
│   │                                #      (DeleteBatch/DeletionRecord reused from models/triage.py)
│   ├── services/
│   │   ├── export_service.py       # NEW: derive delete+label sets from terminal decisions, warn on
│   │   │                            #      undecided survivors, create ExportRun (+ DeleteBatch via
│   │   │                            #      delete_batch_service, + LabelBatch), report, undo wiring
│   │   ├── label_batch_service.py  # NEW: build label set (processing, not-deleted, active), ensure
│   │   │                            #      `Process` group, assign/remove members idempotently,
│   │   │                            #      404→skipped_absent, audited (mirrors delete_batch_service)
│   │   ├── delete_batch_service.py  # REUSED unchanged (003) — export drives its lifecycle
│   │   └── audit_service.py         # reused; new label/export action strings
│   ├── integrations/
│   │   └── people_client.py         # EXTEND seam: ensure_label / add_label_members /
│   │                                 #   remove_label_members on PeopleWriteClient + Fake + Google impl
│   ├── workers/
│   │   ├── label_worker.py          # NEW: PG-backed LabelBatch consumer (FOR UPDATE SKIP LOCKED),
│   │   │                            #      idempotent per LabelAssignment, redacted errors
│   │   ├── delete_worker.py         # REUSED unchanged (003)
│   │   └── run_all.py               # EXTEND: add label_worker.run_once to the combined loop
│   ├── api/
│   │   ├── routers/export.py        # NEW: Export screen + label-batch endpoints (mirrors openapi.yaml)
│   │   └── schemas.py               # add Export/LabelBatch/ExportReport Pydantic schemas
│   └── core/config.py               # reuse; (optional) `process_label_name` default = "Process"
├── migrations/versions/
│   └── 0004_google_contacts_export.py   # NEW: export_run, label_batch, label_assignment, contact_label
└── tests/
    ├── contract/    # export + label-batch API; extended write-seam (group create/assign/remove)
    ├── integration/ # full export run (derive→confirm delete→label→report→undo); disjoint sets;
    │                #   undecided warning/exclusion; scope-gating; idempotent re-run; 404 handling
    └── unit/        # set derivation (delete vs label vs excluded), label idempotency, report counts

frontend/
├── src/
│   ├── components/   # ExportSummary, ExportPreview (delete + label sections), DeleteConfirm
│   │                 #   (reuse DeleteReview pieces), LabelPreview, ExportReport, UndecidedWarning
│   ├── pages/        # Export.vue  (route /working-copies/:id/export)
│   ├── router/       # add the export route
│   ├── services/api.ts  # typed export/label client (from openapi.yaml)
│   └── stores/       # export.ts (Pinia: run state, previews, progress, report) — or extend triage.ts
└── tests/            # Vitest + VTU: previews/counts, delete confirmation gate, live progress, report

docker-compose.yml     # NO new service — label batches run in the existing `worker` (run_all.py)
.env / config          # no new scope; document `Process` label name if made configurable
```

**Structure Decision**: Keep features 001–003's web-application layout. **Maximal reuse**: the delete
half of the export is feature 003's existing, tested path driven by the new `ExportRun`; only the
**label** write (seam methods, `LabelBatch`/`LabelAssignment`, `label_worker`) and the **Export
orchestration** (`export_service`, Export page, report) are new. **No new container** and **no new OAuth
scope** — labeling rides the existing `worker` and the `…/auth/contacts` grant from 003. PostgreSQL
stays the single datastore; both write paths reach Google only through the extended `PeopleWriteClient`
seam (real impl + CI fake), keeping the live API out of CI (Principle IV).

## Complexity Tracking

> No new deviations. The single standing deviation — the `…/auth/contacts` write scope — was justified
> and recorded in feature 003's plan and is **reused without widening** here (labeling needs no
> additional scope). Nothing to add.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _(none new)_ | — | — |
