# Quickstart: Export Triage Results to Google Contacts

**Feature**: `004-google-contacts-export` · validates the spec end-to-end against the **CI fake**
write client (no live Google). For the real Google path, set `PEOPLE_WRITE_CLIENT=google` on the
`worker` and ensure the account granted the `…/auth/contacts` scope (already used by feature 003).

This is a **validation/run guide**, not implementation. Entities → `data-model.md`; endpoints →
`contracts/openapi.yaml`; decisions → `research.md`.

## Prerequisites

- Stack up: `docker compose up -d db backend worker web` (the `worker` runs `run_all.py`, which after
  this feature also drives **label batches** — no new container).
- A working copy that has been triaged (feature 003): some contacts decided `delete`, some routed to the
  Processing Queue, the rest `keep`. Reuse `specs/003-tinder-swipe-triage/quickstart.md` to produce one.
- Backend defaults to the **fake** write client (`PEOPLE_WRITE_CLIENT=fake`) — labeling and deletion are
  recorded in-memory; CI never mutates real Google data (Principle IV).

## Scenario A — Preview the export (US3, no writes)

1. `GET /api/working-copies/{id}/export/preview`.
2. **Expect**: `deleteCount` = active survivors decided `delete`; `labelCount` = active survivors routed
   to processing and not deleted (sets are **disjoint**); `undecidedCount` > 0 only if survivors remain
   undecided; `labelName: "Process"`. Nothing is written to Google. If both counts are 0,
   `nothingToExport: true` (FR-017 empty state).
3. **Disjointness check**: a contact decided `delete` appears in `deleteSet` only; a processing contact
   re-decided to `delete` appears in `deleteSet`, never `labelSet` (D2).

## Scenario B — Run the export: delete (confirmed) + label (alongside) (US1 + US2)

1. `POST /api/working-copies/{id}/export` → `201` with an `ExportRun` (status `previewing`) linking a
   staged `deleteBatchId` and `labelBatchId`.
2. `POST /api/export-runs/{runId}/confirm-delete`:
   - **Without the write scope** → `403 write_scope_required` (FR-020/SC-008); nothing is enqueued.
   - **With the write scope** → `202`; the run goes `running`; the delete batch → `committing`, the label
     batch → `labeling`. Labeling required **no separate confirmation** (FR-015).
3. The background `worker` processes both:
   - **Delete**: snapshot already persisted before any call (SC-001); `delete_contact` per record;
     `404 → skipped_absent` (FR-008); retried on rate-limit/transient; contact `status → retired`.
   - **Label**: ensures the `Process` group once (creating it if absent → audit `label.group.created`,
     cached in `contact_label`), then adds members idempotently; `404 → skipped_absent` (FR-012a).
4. `GET /api/export-runs/{runId}` → **Expect** `status: completed` and a `report` whose counts match:
   `deleted` + `skippedAbsentDelete` = delete set; `labeled` + `skippedAbsentLabel` = label set;
   `failed: 0`; `excluded` = any contacts that went inactive/undecided (FR-018).

## Scenario C — Idempotent re-run after a partial failure (SC-004)

1. Force a transient failure for one contact (fake client option) and run Scenario B → that record is
   `failed`, the rest succeed; run `status: failed`.
2. Re-`POST /confirm-delete` (or the re-run entry point) → **Expect** only `pending`/`failed` records are
   retried; already `deleted`/`labeled`/`skipped_absent` records are untouched; no double-delete, no
   duplicate `Process` membership, and the `Process` group is **not** recreated (FR-019, D5).

## Scenario D — Undo (US1/US2, retention = life of working copy)

1. `POST /api/export-runs/{runId}/undo-delete` → `202`; the worker re-creates each deleted contact from
   its snapshot, restores `working_copy_contact.status='active'` (FR-009, reused from 003).
2. `POST /api/export-runs/{runId}/undo-label` → `202`; the worker removes the `Process` membership for
   each `labeled` assignment (`removed`), audits `contact.unlabeled` (FR-014). Contact data is untouched.

## Scenario E — Staged edits are NOT pushed (FR-013)

1. Before export, transliterate/edit a processing contact (feature 003) — a `StagedEdit` exists.
2. After export, inspect the fake write client (or real Google): the contact carries the `Process` label
   but its **name/fields are unchanged in Google** — the staged edit stayed in the working copy. The
   label is the marker to apply it manually (D4).

## Automated coverage (maps to Success Criteria)

| Test | Asserts | Spec |
|------|---------|------|
| `unit/test_export_sets.py` | delete vs label vs excluded derivation; disjoint; undecided counted/excluded | FR-002/003/017a |
| `unit/test_label_idempotency.py` | re-run skips done rows; group ensured once; report counts | FR-012/019, SC-004 |
| `integration/test_export_flow.py` | preview→confirm→delete+label→report→completed | US1/US2/US3, FR-018 |
| `integration/test_export_scope_gate.py` | confirm-delete `403` without write scope; no writes attempted | FR-020, SC-008 |
| `integration/test_label_404.py` | absent contact → `skipped_absent` success | FR-012a, SC-006 |
| `integration/test_export_undo.py` | delete-undo restores; label-undo removes membership | FR-009/014, SC-005 |
| `contract/test_export_api.py` | endpoints match `contracts/openapi.yaml` | — |
| audit assertions across the above | every mutation audited; no PII/secrets in details/report/logs | FR-022/023, SC-007 |

**Done when**: Scenarios A–E pass against the fake client, the audit log shows
`export.run.started/completed`, `label.group.created`, `label.batch.committed`, `contact.labeled`
(+ `contact.unlabeled` on undo) with redacted details, and Biome + pytest are green.
