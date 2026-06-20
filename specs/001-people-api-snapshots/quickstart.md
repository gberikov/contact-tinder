# Quickstart & Validation: Snapshots & Working Copies

**Feature**: `001-people-api-snapshots` · **Date**: 2026-06-20

This guide proves the feature end-to-end. It validates the spec's user stories (US1–US3) and
success criteria (SC-001…SC-009). It is a run/validation guide — implementation details live in
`tasks.md` and the code.

## Prerequisites

- Docker + docker-compose.
- A Google Cloud project with the **People API enabled** and an **OAuth 2.0 Client** (Web app)
  whose redirect URI is `http://localhost:8000/api/accounts/callback`.
- OAuth consent screen configured with the scope `.../auth/contacts.readonly` and at least one
  test Google account added as a test user.
- A second Google account (for the multi-account check, SC-009) — may have 0 contacts.

## Environment

Create `.env` (git-ignored — see repo `.gitignore`):

```dotenv
DATABASE_URL=postgresql+psycopg://app:app@db:5432/contacttinder
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/accounts/callback
TOKEN_ENCRYPTION_KEY=<base64 32-byte key>   # used to encrypt OAuth tokens at rest (Principle I)
```

Never commit `.env`, tokens, or any contact export (Constitution Principle I; enforced by
`.gitignore`).

## Start the stack

```bash
docker compose up --build      # starts: db (PostgreSQL), backend (FastAPI), worker (import), web (Vue)
# backend: http://localhost:8000   web: http://localhost:5173
```

Run migrations (if not auto-applied on boot) and the test suites:

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend pytest          # backend unit/contract/integration
docker compose exec web npx vitest run       # frontend unit
docker compose exec web npx @biomejs/biome ci .   # lint/format gate (Constitution)
```

## Validation scenarios

### US1 — Connect account & capture a snapshot (P1)

1. Open the web app → **Connect Google account** → complete OAuth with read-only consent.
   - ✅ Account appears as `connected` (SC-001 path). Tokens are **not** visible anywhere in the
     UI or API responses (Principle I, FR-002).
2. Click **Create snapshot**.
   - ✅ A snapshot appears in `importing` state; `GET /api/snapshots/{id}/import` shows
     `fetchedCount` rising (FR-015).
   - ✅ When import finishes, snapshot becomes `complete` with `contactCount` equal to the
     account's personal-contact count (SC-002). For ≤5,000 contacts this completes in < 5 min
     (SC-001).
3. **Resumability check (SC-008/FR-016)**: during a large import, restart the worker
   (`docker compose restart worker`).
   - ✅ The import resumes from its stored page cursor and still finalizes with zero loss.
4. **Atomicity check (SC-006/FR-008)**: revoke the Google token mid-import (or simulate 401 in
   tests).
   - ✅ Snapshot ends `failed`, never `complete`; it is not offered as usable; account flips to
     `needs_reauth` (FR-017).

### US2 — View snapshots & contents (P2)

1. Open **Snapshots**.
   - ✅ Each row shows account email, creation date, `contactCount`, and `workingCopyCount`
     (FR-009, FR-014); newest first (SC-005).
2. Open a snapshot.
   - ✅ Contacts list/browse is read-only — no edit/delete affordance on snapshot data (FR-010).
   - ✅ Reopening later shows identical data (SC-003 — zero drift).

### US3 — Create a working copy (P3)

1. From a `complete` snapshot, click **Create working copy**.
   - ✅ A working copy is created with the same `contactCount`; the source snapshot is unchanged
     (SC-004, FR-011).
2. Create a **second** working copy from the same snapshot.
   - ✅ Both exist independently; snapshot `workingCopyCount` = 2 (FR-012/FR-013).

### Snapshot deletion (clarified scope — FR-021/FR-022)

1. Try to delete a snapshot that has working copies (`DELETE /api/snapshots/{id}?confirm=true`).
   - ✅ `409` — blocked, with a clear reason; snapshot and copies remain intact (FR-022).
2. Delete its working copies, then delete the snapshot with confirmation.
   - ✅ `204`; snapshot removed; an `snapshot.deleted` audit entry exists (FR-023).
3. Call delete without `confirm=true`.
   - ✅ `400` — deletion requires explicit confirmation (FR-021).

### Multi-account isolation (SC-009 / FR-018)

1. Connect a second Google account and snapshot it.
   - ✅ Snapshots list shows both accounts' snapshots, each labeled with its owning account; no
     account's contacts appear under another (FR-018).

### Audit & privacy spot-check (Principle I & V)

- ✅ `audit` table has entries for `snapshot.created`, `working_copy.created`, `snapshot.deleted`.
- ✅ Grep application logs and API responses: no OAuth tokens or secrets present (redacted).

## Mapping to contracts

All HTTP interactions above conform to [`contracts/openapi.yaml`](contracts/openapi.yaml);
entities are defined in [`data-model.md`](data-model.md); rationale in
[`research.md`](research.md).
