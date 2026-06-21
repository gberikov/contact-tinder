# Phase 0 Research: Export Triage Results to Google Contacts

**Feature**: `004-google-contacts-export` · **Date**: 2026-06-20

Decisions resolving the Technical Context unknowns and the spec's clarifications. Each is Decision /
Rationale / Alternatives. The deletion path is inherited from feature 003 (research D8–D12); this
document focuses on what is **new**: the `Process` label write, the export orchestration, and how both
reuse existing infrastructure.

---

## D1 — `Process` label = Google **contact group**; reuses the existing `…/auth/contacts` scope (NO new consent)

- **Decision**: The `Process` label is a Google **contact group** (`contactGroups` resource). Applying it
  = ensuring a group named `Process` exists (`contactGroups.create`, reused if present) and adding each
  target contact via `contactGroups.members.modify` (`resourceNamesToAdd`); removal (undo) uses
  `resourceNamesToRemove`. **All of these operations are authorized by the same
  `https://www.googleapis.com/auth/contacts` write scope feature 003 already requests** — Google does not
  define a separate contact-group scope. Therefore this feature introduces **no new OAuth scope and no new
  incremental-consent step**; the existing `delete_batch_service.account_has_write_scope(account)` gate
  guards labeling too (FR-020, SC-008).
- **Rationale**: "Label" in the Google Contacts UI **is** a contact group; filtering by it is exactly the
  operator's "легко отфильтровать и допроверить" workflow. Reusing the already-granted write scope keeps
  least-privilege intact (Principle I) and means **no Constitution deviation beyond 003's recorded one**.
- **Alternatives**: A separate "starred"/`memberships` hack — rejected: not user-filterable as a named
  label. Requesting a narrower scope — impossible; `contactGroups` writes require the broad contacts
  scope. Writing labels via `updateContact` memberships — rejected: contact-group membership is the
  supported, idempotent mechanism and avoids clobbering other fields.

## D2 — Label set = processing-routed, not-deleted, still-active survivors (disjoint from delete set)

- **Decision**: The **label set** is every `working_copy_contact` with `status='active'` that (a) has a
  `ProcessingItem` in the working copy's current triage session and (b) whose latest `TriageDecision`
  outcome is **not** `delete`. The **delete set** is the active survivors whose latest decision **is**
  `delete` (003's existing derivation). The two are **disjoint** by construction. A contact routed to
  processing is labeled regardless of whether its `ProcessingItem` is `pending` or `done` — because edits
  are **not** pushed (D4), so even locally-"done" contacts still need manual re-check in Google.
- **Rationale**: Matches the user's words — "все объекты, которые попали в Processing Queue" — and the
  terminal-decision model from 003 (process defaults to `keep` unless re-decided to `delete`). Disjoint
  sets prevent a contact being both deleted and labeled (FR-002). Using `status='active'` excludes
  contacts merged away or already deleted (FR-003).
- **Alternatives**: Label only `pending` processing items — rejected: "done"-but-not-pushed contacts
  still need re-checking, and the user asked for *all* queue contacts. Label all kept contacts —
  rejected: only processing-routed ones were flagged for follow-up.

## D3 — `LabelBatch` / `LabelAssignment` mirror `DeleteBatch` / `DeletionRecord`

- **Decision**: Labeling gets its own batch entities mirroring the proven delete pattern: a `LabelBatch`
  (lifecycle `staged → committing(labeling) → committed | failed`, plus `undoing → undone` for removal)
  with one `LabelAssignment` per contact (`pending → labeled | skipped_absent | failed`, `removed` on
  undo). Each assignment stores `origin_resource_name` and is the idempotency/undo unit. The resolved
  `Process` group resourceName is recorded (D5) so the worker need not re-resolve it per contact.
- **Rationale**: Reuses 003's worker/idempotency/audit semantics verbatim, so partial-failure retry and
  reversibility behave identically and are testable the same way. No snapshot of full payload is needed
  (labeling adds a membership; it never destroys data) — the before-state is simply "not a member",
  recoverable by removing the membership.
- **Alternatives**: Fold labeling into `DeleteBatch` with a `kind` column — rejected: muddies the
  snapshot-protected delete invariants and its status set; separate tables keep each path clean.
  A single bulk `contactGroups.members.modify` with all members — used as the **execution** mechanism in
  batches (D6) but still tracked per-assignment for idempotency/undo/audit granularity.

## D4 — Staged edits / transliterations are NOT pushed (label only)

- **Decision**: Per the spec clarification, the export's labeling writes **only** the `Process`
  membership. The `StagedEdit` rows from feature 003 (card edits, accepted transliterations) are **not**
  synced to Google by this feature; they remain in the working copy. The label is purely a marker for the
  operator to find and manually apply/verify those changes in Google. `people.updateContact` is **out of
  scope** (as it already was in 003, research D7).
- **Rationale**: Exactly the user's intent ("чтобы я мог их допроверить") and keeps the write surface
  minimal (delete + group-membership only). Pushing edits is a separable future "apply working copy to
  Google" feature.
- **Alternatives**: Push edits + label (the clarification's option B) — explicitly rejected by the user.

## D5 — `Process` group resolution: ensure-once per account, recorded in `contact_label`

- **Decision**: On the first labeling run for an account, resolve the `Process` group: look up an
  existing group named `Process`; if absent, create it once (`contactGroups.create`) and audit
  `label.group.created`. Persist the resolved group resourceName in a small `contact_label` row keyed by
  `(account_id, name='Process')` so subsequent runs reuse it without re-creating (idempotent, FR-010/012).
  Ensuring is performed once per `LabelBatch` before member assignment, inside the worker.
- **Rationale**: Avoids duplicate `Process` groups across re-runs and accounts, and avoids a list/scan on
  every contact. Storing the resourceName makes membership add/remove direct and idempotent.
- **Alternatives**: Resolve by listing groups every run — rejected: extra Google calls and a race window;
  the cached resourceName is authoritative once created. Hard-code a label name only — kept simple as
  `Process` (optionally `config.process_label_name`), no per-run user choice.

## D6 — Execution model: background `label_worker` in the existing `worker`; bulk member modify with backoff

- **Decision**: Confirming/launching an export sets the `LabelBatch` to a `labeling` (committing) status
  consumed by a new `label_worker.run_once` added to the combined `run_all.py` loop (claims one batch via
  `SELECT … FOR UPDATE SKIP LOCKED`, like the delete worker). It ensures the group (D5), then assigns
  members — chunked into `contactGroups.members.modify` calls (Google caps members-modify per request, so
  batches are chunked, e.g. ≤ ~500 resourceNames/call) — with the existing retry/backoff for
  `RateLimitedError`/`TransientError`, marking each `LabelAssignment` idempotently. `404`/absent member →
  `skipped_absent` = success (FR-012a). Undo runs the same loop in `unlabeling` mode (remove members).
- **Rationale**: Q3 chose a **background job for both deletes and labels**; reusing the PG-backed worker
  keeps PostgreSQL the only datastore (no Redis), keeps Google I/O off the request path, and inherits
  proven concurrency/retry. No new container.
- **Alternatives**: Synchronous inline labeling — rejected per Q3 and because large batches + rate limits
  would block the UI. One member-modify per contact — rejected: chunked bulk modify is far fewer calls;
  per-assignment tracking is preserved independently of call batching.

## D7 — ExportRun orchestration, undecided-survivor warning, and the report

- **Decision**: An `ExportRun` (per working copy/account) ties the export together. On open, the Export
  screen calls a **preview** that derives both sets (D2), counts them, and returns a **warning + the count
  of undecided active survivors**, which are **excluded** from both actions (FR-017a). Starting the export
  creates/links a `DeleteBatch` (via the existing `delete_batch_service.create_batch`, which already
  snapshots and excludes stale contacts) and a `LabelBatch`; **deletion still requires its explicit
  confirm** (`delete_batch_service.confirm`, scope-gated), while the `LabelBatch` is enqueued alongside
  without a separate per-item confirmation (FR-015). The run aggregates both batches' per-record results
  into an **ExportReport** (deleted / skipped-absent / labeled / failed / excluded) with undo entry points
  (FR-018), and is **re-runnable** — re-running attempts only `pending`/`failed` records in each batch and
  never repeats completed work (FR-019), reusing the delete worker's idempotency and the new label
  worker's.
- **Rationale**: Keeps the destructive action behind its existing guard while presenting "one export" UX
  (Q2). The report is a thin aggregation over the two batches' rows, so it stays consistent with the
  audit log and needs no separate result store.
- **Alternatives**: A single combined confirmation for both writes (Q2 option C) — rejected by the user.
  Recomputing report counts from the audit log — rejected: the batch/record rows are the system of record
  for live status; audit is the immutable history.

## D8 — Empty state, isolation, redaction, retention (reuse 003 conventions)

- **Decision**: When both sets are empty, the Export screen shows an explicit "nothing to export" state
  (FR-017). All export access is scoped by `working_copy_id`/`account_id`; cross-account ids return
  not-found (FR-021). Audit `details`, the report, and logs carry only counts/refs/results — never
  payloads, names, or secrets (FR-022/023). Undo retention = **life of the working copy** (no timed
  expiry), consistent with 002/003 (research D12): a committed delete is undoable while its
  `DeletionRecord`s exist, and an applied `Process` label is removable while its `LabelAssignment`s exist.
- **Rationale**: Uniformity with the established codebase; no new retention/expiry machinery.
- **Alternatives**: A fixed N-day undo window — rejected (adds a scheduler, risks destroying the recovery
  path), exactly as in 003.

---

## Resolved unknowns summary

| Technical Context item | Resolution |
|------------------------|------------|
| `Process` label mechanism + OAuth scope | D1 — contact group; reuses 003's `…/auth/contacts`; no new scope |
| Which contacts get labeled (set derivation) | D2 — processing-routed, not-deleted, active; disjoint from delete set |
| Label persistence model | D3 — `LabelBatch` / `LabelAssignment` mirroring delete path |
| Edits→Google boundary | D4 — label only; staged edits NOT pushed |
| `Process` group create-or-reuse | D5 — ensure-once per account, cached in `contact_label` |
| Execution / background model | D6 — `label_worker` in existing `worker`; chunked bulk member-modify + backoff |
| Orchestration / undecided warning / report / re-run | D7 — `ExportRun` + `ExportReport`; delete keeps its confirm |
| Empty state / isolation / redaction / retention | D8 — reuse 003 conventions |
| Delete path (scope/idempotency/undo/worker) | Inherited from 003 (research D8–D12), reused unchanged |

No `NEEDS CLARIFICATION` items remain.
