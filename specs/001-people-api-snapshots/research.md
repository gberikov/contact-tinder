# Phase 0 Research: Google People API Snapshots & Working Copies

**Feature**: `001-people-api-snapshots` · **Date**: 2026-06-20

This document resolves the technical unknowns for the data-foundation feature. The core stack is
fixed by the constitution (Python 3.12 / FastAPI, Vue 3 / TS / Vite, PostgreSQL, self-hosted
docker-compose); research focuses on *how* to use it for safe, resumable, read-only contact
capture.

---

## D1. Google OAuth scope

- **Decision**: Request only `https://www.googleapis.com/auth/contacts.readonly`.
- **Rationale**: This feature never writes to Google (FR-001, FR-003). Read-only is the narrowest
  scope that satisfies it — directly satisfies Constitution Principle I ("narrowest scope").
- **Alternatives considered**: `contacts` (read/write) — rejected, grants delete/write the feature
  must not have. `directory.readonly` — rejected, directory entries are out of scope.

## D2. Contact source & endpoint

- **Decision**: Capture **personal connections only** via `people.connections.list` on
  `resourceName=people/me`, with `sources=READ_SOURCE_TYPE_CONTACT` (exclude `PROFILE`-only and
  `otherContacts`).
- **Rationale**: Clarified scope (personal contacts only). `otherContacts.list` and directory are
  explicitly out of scope.
- **personFields requested**: `names,nicknames,emailAddresses,phoneNumbers,addresses,organizations,
  biographies,birthdays,urls,memberships,photos,metadata`. `metadata` is required to capture
  `resourceName` + `etag` and to detect `metadata.deleted` during future incremental syncs.
- **Alternatives considered**: Requesting every personField — rejected as unnecessary payload;
  the set above covers the fields the spec enumerates (FR-004) plus identity metadata.

## D3. Pagination, scale & resumability

- **Decision**: Page with `pageSize=1000` (max), looping on `nextPageToken`. Persist the current
  `pageToken` and running fetched count on the **ImportJob** row after each page so the import is
  **resumable across process restarts**. Request `requestSyncToken=true` and store the final
  `nextSyncToken` on the snapshot for future incremental features.
- **Rationale**: 50,000 contacts ÷ 1000 = ~50 requests — well within a single background job
  (FR-016, FR-020, SC-008). Persisting the page cursor in PostgreSQL (not in memory) makes the
  job durable without introducing a new datastore.
- **Sync-token caveat**: The first page of a full-sync request (`requestSyncToken=true`) carries an
  **additional fixed quota**; exceeding it returns 429. Sync tokens expire after 7 days
  (`EXPIRED_SYNC_TOKEN`) → fall back to a fresh full sync. For v1 we only *store* the sync token;
  we do not yet consume it.
- **Alternatives considered**: In-memory pagination — rejected, not resumable. Storing all pages
  then committing — acceptable, but per-page cursor persistence gives finer resume granularity.

## D4. Background job mechanism (no new datastore)

- **Decision**: Implement the resumable import as a **PostgreSQL-backed job queue**: an
  `import_job` table consumed by a dedicated worker process (separate docker-compose service)
  using `SELECT ... FOR UPDATE SKIP LOCKED`. Progress (`page_token`, `fetched_count`, `attempts`)
  is written back to the same row.
- **Rationale**: FR-016 requires a resumable background job. A DB-backed queue keeps **PostgreSQL
  as the only datastore**, avoiding a constitutional amendment (the Technology Constraints section
  treats adding a datastore as a constitutional change). It is durable, transactional, and simple
  for a single-operator self-hosted deployment.
- **Alternatives considered**: Celery/RQ/arq on **Redis** — rejected for v1 because Redis is an
  additional datastore (constitutional change) and overkill at this scale. FastAPI
  `BackgroundTasks` — rejected: not durable, dies with the request/process. Revisit Redis only if
  future features (e.g., Spark/Zingg orchestration) justify it via amendment.

## D5. OAuth token storage & encryption at rest

- **Decision**: Store refresh/access tokens **encrypted at rest** using authenticated symmetric
  encryption (`cryptography` Fernet / AES-GCM). The encryption key comes from an environment
  secret (`TOKEN_ENCRYPTION_KEY`), never committed. Ciphertext lives in a dedicated `credential`
  table, separate from the `account` table, and is **never** serialized into any API response,
  log, or export.
- **Rationale**: Constitution Principle I (NON-NEGOTIABLE) + FR-002. Separating credentials from
  account metadata makes accidental over-serialization far less likely.
- **Alternatives considered**: PostgreSQL `pgcrypto` column encryption — viable, but keeps the key
  in DB/SQL surface; app-level encryption keeps the key in the app secret boundary. OS keyring —
  rejected, doesn't fit a containerized multi-account server.

## D6. Snapshot immutability & working-copy derivation

- **Decision**: A **Snapshot** is finalized (`status=complete`) only inside the transaction that
  records the last page; before that it is `importing` and never surfaced as usable (FR-008).
  Snapshot contacts are stored as immutable rows (raw People `Person` JSON in `jsonb` + a few
  extracted display columns). A **WorkingCopy** is created by a server-side bulk copy of the
  snapshot's contacts into `working_copy_contact` rows — a deep copy, fully independent (FR-011).
- **Rationale**: Immutability is enforced by application invariants (no update/delete paths against
  finalized snapshot contacts) plus DB-level guards. Deep copy guarantees edits to a working copy
  can never touch the snapshot (Principle II).
- **Alternatives considered**: Copy-on-write / sharing rows between snapshot and working copy —
  rejected: risks mutating shared rows, violating immutability; storage savings not worth the risk
  at this scale.

## D7. Photo handling

- **Decision**: Capture photo **URLs/metadata** from the `photos` personField only; do not download
  or store binary images in v1.
- **Rationale**: Spec assumption; avoids large binary storage. URLs are part of the Person payload.
- **Alternatives considered**: Downloading binaries to blob storage — deferred to a future feature.

## D8. Multi-account isolation

- **Decision**: Every snapshot, import job, and contact row carries an `account_id` foreign key.
  All queries are scoped by account; the snapshots list joins across accounts but always labels the
  owning account. No cross-account merge path exists in v1.
- **Rationale**: FR-018, SC-009, Constitution Principle I (data isolation). Multiple accounts is a
  v1 requirement (clarified).
- **Alternatives considered**: Single-account v1 — rejected per clarification.

## D9. Resilience: rate limits & token expiry

- **Decision**: Wrap People API calls with **exponential backoff + jitter** on `429`/`5xx`
  (respecting `Retry-After` when present), capped at a configured `max_attempts` (default 5) per
  import job. Once retries are exhausted on a transient error, the job and its snapshot are marked
  `failed` (never partially finalized) — this gives the "transient → failed" boundary a testable
  threshold. On `401`/invalid-grant (expired/revoked token), mark the account `needs_reauth`, fail
  the import job **without finalizing** the snapshot, and prompt re-authorization in the UI
  (FR-017). On `410 EXPIRED_SYNC_TOKEN` (future incremental), restart a full sync.
- **Rationale**: FR-016/FR-017 and the documented full-sync first-page quota. Failing without
  finalizing preserves the "no partial snapshot" guarantee (FR-008, SC-006).
- **Alternatives considered**: Fail-fast with no retry — rejected, transient 429s are expected at
  scale.

## D10. Testing strategy & seams (Test-First)

- **Decision**: 
  - **Backend**: `pytest`; the People API is accessed through a thin `PeopleClient` interface so
    tests inject a fake/recorded client — **CI never calls live Google** (Principle IV). HTTP-level
    mocking via `respx`/`responses` for adapter contract tests. API contract tests via FastAPI
    `TestClient` against the OpenAPI in `contracts/`.
  - **Frontend**: `Vitest` + Vue Test Utils for components; Playwright optional for the end-to-end
    swipe/list flows (later features). **Biome** lint/format gate in CI (constitution).
  - Integration tests use an ephemeral PostgreSQL (docker) and assert immutability, resumability
    (kill/resume the job), deletion guard, and audit-entry creation.
- **Rationale**: Principle IV mandates TDD and forbids live-Google calls in CI; seams make the
  safety/immutability invariants mechanically verifiable.
- **Alternatives considered**: Recorded VCR cassettes against live API — usable later, but a typed
  fake client is simpler and deterministic for v1.

## Resolved unknowns

All Technical Context items are resolved; no remaining `NEEDS CLARIFICATION`.
