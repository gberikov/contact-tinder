# Phase 0 Research: Tinder-Style Contact Swipe Triage

**Feature**: `003-tinder-swipe-triage` · **Date**: 2026-06-20

Decisions resolving the Technical Context unknowns and the clarifications recorded in the spec. Each is
written as Decision / Rationale / Alternatives.

---

## D1 — Deck source = `active` working-copy survivors, stable order

- **Decision**: The triage deck is the set of `working_copy_contact` rows with `status='active'` for
  the selected working copy (the "post-dedup survivors" — `retired` rows were merged away by feature
  002). Order is **stable and deterministic**: `ORDER BY lower(display_name) NULLS LAST, id`, where
  `display_name` is derived from `payload.names[0].displayName`. A `TriageSession` optionally records
  the `dedup_run_id` it followed, for provenance only.
- **Rationale**: Triage composes directly on 002's output with zero data duplication; using `active`
  rows means merges are already reflected. A deterministic order makes pause/resume position
  reproducible (SC-003) and tests repeatable. Sorting by `id` as a tiebreak guarantees total order.
- **Alternatives**: Requiring a *completed dedup run* to triage — rejected: survivors are well-defined
  by `status='active'` even if no run exists, and coupling would block triage on dedup. Confidence- or
  recency-based ordering — rejected per clarification (stable order chosen); can be a future option.

## D2 — Triage does NOT require a completed dedup run

- **Decision**: A `TriageSession` can be opened for any `ready` working copy; if dedup never ran, the
  deck is simply all `active` contacts. `dedup_run_id` is nullable.
- **Rationale**: Keeps the feature independently testable and useful; avoids a hard dependency cycle.
- **Alternatives**: Hard requirement on a `completed` run — rejected (unnecessary coupling).

## D3 — Decision model: one live decision per contact, re-decidable; history via audit

- **Decision**: `triage_decision` holds **one row per (session, working_copy_contact)** with a unique
  constraint; `outcome ∈ {keep, delete, process}`. Re-deciding **updates the row in place** (latest
  wins, FR-006) and appends an `AuditEntry`, so the full decision history lives in the append-only
  audit log while the live state stays a single row. "Resume" = the next `active` contact in D1 order
  that has no live decision (or whose only state is an unresolved `process`).
- **Rationale**: Satisfies "re-decide any contact at any time" + "navigable history" without an
  append-heavy decisions table; the audit log is already the system of record for history (Principle
  V). Single-row state keeps the completion summary and resume query simple and fast (SC-001/003/006).
- **Alternatives**: Append-only decisions with `superseded` flags — rejected: duplicates what the
  audit log already provides and complicates "current outcome" queries.

## D4 — "Additional processing" → ProcessingItem; terminal disposition defaults to `keep`

- **Decision**: Swiping **process** creates/updates a `processing_item` (status `pending`) and sets the
  contact's live decision `outcome='process'` — **no editor opens during the swipe** (FR-011). In the
  post-swipe **ProcessingQueue**, the operator edits and/or transliterates; when the item is marked
  done, the contact's terminal decision **defaults to `keep`** (re-decidable to `delete`), per the
  clarification. A contact never stays stuck in `process` once its queued work is complete.
- **Rationale**: Preserves swipe momentum (the user's explicit "не терять динамику"), while guaranteeing
  every contact resolves to a terminal keep/delete (FR-002, edge case "Processing then deciding").
- **Alternatives**: Force an explicit keep/delete after processing, or bounce the card back into the
  deck — both rejected per clarification (default-keep chosen) as friction that breaks flow.

## D5 — Transliteration: deterministic, in-process, name fields only, reviewed

- **Decision**: A **pure-Python deterministic transliterator** (`services/transliteration.py`, no I/O,
  no third-party service) converts Latin → Cyrillic for **name fields only** (given / family / display
  name). It uses a phonetic Latin→Russian-Cyrillic mapping with digraph handling (e.g. `sh→ш`, `ch→ч`,
  `zh→ж`, `yo→ё`, `ya→я`, `kh→х`, `ts→ц`), longest-match first, case-preserving. The API returns a
  **suggestion**; the operator accepts or edits it before it is staged (FR-014/015). Names already in
  Cyrillic are returned unchanged; empty names yield no suggestion (FR-017).
- **Rationale**: Determinism makes it table-unit-testable and keeps PII in-process (Principle I — no
  external transliteration service). Name-only scope matches the clarification and minimizes the risk
  of corrupting non-name data. Human review (Principle III) covers the inherent ambiguity of personal
  names, so the mapping need only be a good default, not perfect.
- **Alternatives**: A third-party `transliterate` library — rejected: heavier dependency for a small,
  testable mapping and less control over name-specific digraphs. GOST/ICAO strict standards — rejected:
  optimized for document transliteration, not phonetic personal-name rendering; review covers edge
  cases anyway. An LLM/network call — rejected: sends PII off-box (Principle I) and is nondeterministic.

## D6 — Staged edits & transliterations as reversible `StagedEdit` records

- **Decision**: Editing a card or accepting a transliteration writes a `staged_edit`
  (`kind ∈ {edit, transliterate}`, `payload_before`, `payload_after`, `status active|undone`) and
  updates `working_copy_contact.payload`. Undo restores `payload_before` and marks the record `undone`.
  This mirrors feature 002's `MergeRecord` reversibility pattern.
- **Rationale**: Uniform, auditable, reversible mutation of the working copy (FR-016, SC-004); reuses an
  established, tested pattern. Edits affect only the working copy.
- **Alternatives**: Mutating `payload` in place without a before-image — rejected: not reversible,
  violates Principle II.

## D7 — Edits/transliterations are staged in the working copy; NOT pushed to Google in this feature

- **Decision**: The **only** Google write in this feature is `deleteContact`. Edits and accepted
  transliterations are staged against the working copy and are **not** synced to Google here; pushing
  contact updates to Google (`people.updateContact`) is **out of scope** and deferred to a future
  "apply working copy to Google" feature.
- **Rationale**: Bounds the feature and its OAuth/risk surface to exactly the headline destructive
  action (delete). The working copy is the staging area; a later sync feature can apply edits. The spec
  describes edits only as "staged against the working copy" (FR-013), consistent with this boundary.
- **Alternatives**: Push edits to Google immediately — rejected: scope creep, broader write surface,
  and not required by any FR.

## D8 — Google delete: scope, idempotency, undo

- **Decision**: Deletion uses People API `people.deleteContact(resourceName=…)` where `resourceName` is
  `working_copy_contact.origin_resource_name`. Required scope is `https://www.googleapis.com/auth/
  contacts` (read-write) — Google has **no delete-only scope**; it is the narrowest that works. Each
  `deletion_record` tracks per-contact status (`pending → deleted | skipped_absent | failed`).
  Execution is **idempotent**: a record already `deleted` is not retried; a `404 Not Found` from Google
  is treated as `skipped_absent` = success (FR-024). Undo re-creates the contact via
  `people.createContact(body=payload_before)` and records the new `resourceName`.
- **Rationale**: Satisfies FR-020/022/023/024 and Principle II. Per-record status makes partial-failure
  retry safe and resumable (mirrors `import_job`/`dedup_run` worker semantics).
- **Alternatives**: `batchDeleteContacts` (bulk) — viable later for throughput, but per-record status
  gives cleaner idempotency, undo, and audit; revisit if delete volume demands it. Soft-delete only in
  Google — not possible (Google delete is hard); hence the snapshot-and-recreate undo.

## D9 — Incremental OAuth consent for the write scope

- **Decision**: The `contacts` write scope is requested **only when the operator enables deletion**,
  via an incremental-consent re-auth (`include_granted_scopes=true`, `prompt=consent`). The result is
  recorded in `account.granted_scopes`. The delete-batch confirm endpoint **rejects with a clear error**
  if the account lacks the write scope, prompting re-auth. Read-only flows (001/002) are unchanged.
- **Rationale**: Keeps the broad scope opt-in and least-privilege by default (Principle I); existing
  read-only accounts are never silently upgraded.
- **Alternatives**: Always request `contacts` at first connect — rejected: violates narrowest-scope
  default for users who never delete.

## D10 — Delete worker = PG-backed job in the existing `worker` service

- **Decision**: Committing a `DeleteBatch` enqueues it as a PG row consumed by a new `delete_worker`
  using `SELECT … FOR UPDATE SKIP LOCKED`, exactly like `import_worker`/`dedup_worker`. It processes
  `deletion_record`s with retry/backoff for `RateLimitedError`/`TransientError`, surfaces redacted
  errors, and updates batch status (`committing → committed | failed`). No new container; runs in
  `worker`.
- **Rationale**: Reuses the proven concurrency/retry pattern and keeps PostgreSQL the only datastore
  (no Redis). Long-running Google I/O stays off the request path (SC-001 swipe latency unaffected).
- **Alternatives**: Synchronous delete in the request handler — rejected: blocks the UI, no clean
  retry/resume, risks partial commits on timeout.

## D11 — Resume, concurrency, and "working copy changed underneath"

- **Decision**: A session is bound to one `working_copy_id`. The deck and resume position are computed
  from current `active` rows each load (D1/D3), so they naturally reflect changes. If a contact with a
  live `delete`/`process` decision is no longer `active` at delete-commit time, its `deletion_record`
  is `skipped_absent`/ignored and the operator is informed in the preview. Only one **in-progress**
  session per working copy is enforced by a partial unique index (mirrors 002's one-active-run rule).
- **Rationale**: Robust to a dedup re-run between sessions without losing decisions (edge case
  "Working copy changes underneath"); avoids stale-card surprises.
- **Alternatives**: Snapshotting the deck at session start — rejected: would show contacts already
  merged away and diverge from working-copy truth.

## D12 — Undo retention = life of the working copy (consistent with 002)

- **Decision**: No timed expiry. `StagedEdit` undo and `DeletionRecord`-based delete undo remain
  available while the records exist (life of the working copy), matching feature 002's merge-undo
  choice. The "retention window" in the spec is therefore "until the working copy is deleted".
- **Rationale**: Consistency with the existing codebase (config already states no merge-undo expiry)
  and maximal safety (Principle II). Simpler than a scheduler.
- **Alternatives**: A fixed N-day window with a purge job — rejected: adds a scheduler and risks
  destroying the only recovery path; revisit only if storage pressure appears.

## D13 — Swipe latency budget (SC-001 < 3 s median)

- **Decision**: The frontend records a decision with an **optimistic** UI advance and a lightweight
  `POST` to persist; the deck is **prefetched/paginated** so the next card is already loaded. No
  transliteration or Google call happens during the pass (deferred to the queue / delete batch).
- **Rationale**: Keeps per-card interaction well under 3 s; persistence is a single small row
  upsert. Durability (SC-003) is preserved because each decision is POSTed (not only held client-side).
- **Alternatives**: Persist all decisions in one batch at the end — rejected: a crash mid-pass would
  lose decisions (violates SC-003).

---

## Resolved unknowns summary

| Technical Context item | Resolution |
|------------------------|------------|
| Deck source / ordering | D1 — `active` survivors, deterministic order |
| Dependency on dedup run | D2 — not required |
| Decision persistence / resume / re-decide | D3, D11, D13 |
| Processing terminal state | D4 |
| Transliteration engine & scope | D5 |
| Staged edits reversibility | D6 |
| Edits→Google boundary | D7 |
| Google delete: scope/idempotency/undo | D8, D9 |
| Delete execution model | D10 |
| Undo retention | D12 |

No `NEEDS CLARIFICATION` items remain.
