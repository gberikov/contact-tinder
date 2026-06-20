# Implementation Plan: Google People API Snapshots & Working Copies

**Branch**: `001-people-api-snapshots` | **Date**: 2026-06-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-people-api-snapshots/spec.md`

## Summary

Build the data foundation of Contact Tinder: connect one or more Google accounts (read-only),
import each account's **personal contacts** via the Google People API into an **immutable
snapshot**, surface snapshots and their contents in the UI, and let the operator derive
independent, editable **working copies** from any snapshot. Imports run as a **resumable,
PostgreSQL-backed background job** (durable to ~50,000 contacts). Snapshots are deletable only via
explicit confirmation and only when no working copies remain. No data is ever written back to
Google in this feature.

## Technical Context

**Language/Version**: Python 3.12 (backend, worker); TypeScript 5.x (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.x + Alembic, `google-api-python-client` +
`google-auth-oauthlib`, `cryptography` (token encryption); Vue 3 + Vite; Biome (lint/format)

**Storage**: PostgreSQL (application state, snapshots, working copies, import jobs, audit log;
encrypted OAuth tokens). **Only datastore** — a DB-backed job queue avoids adding Redis (keeps the
constitution's Technology Constraints intact).

**Testing**: backend `pytest` with a `PeopleClient` seam (fake/recorded — no live Google in CI),
`respx` for adapter contract tests, FastAPI `TestClient` for API contracts; frontend `Vitest` +
Vue Test Utils; Biome `ci` gate.

**Target Platform**: Linux containers via docker-compose (services: `db`, `backend`, `worker`,
`web`).

**Project Type**: Web application (backend + frontend + background worker).

**Performance Goals**: Snapshot of ≤5,000 contacts in < 5 min (SC-001); reliably handle ≤50,000
contacts per snapshot with visible progress and zero loss (SC-008). People API paged at
`pageSize=1000` (~50 requests for 50k).

**Constraints**: Read-only Google access (`contacts.readonly`); OAuth tokens encrypted at rest and
never serialized/logged; per-account data isolation; snapshots immutable once `complete`;
no partial snapshot ever surfaced as usable.

**Scale/Scope**: Single self-hosted operator; multiple connected Google accounts; multiple
snapshots; multiple working copies per snapshot; up to ~50,000 contacts per snapshot.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How this plan complies |
|-----------|--------|------------------------|
| I. Privacy & Data Protection | ✅ PASS | Requests only `contacts.readonly` (narrowest scope); tokens encrypted at rest in a separate `Credential` table, never in API/logs/exports (FR-002, D5); per-account isolation via `account_id` scoping (FR-018); no contact PII leaves the deployment (Zingg not used here); secrets via env. |
| II. Non-Destructive by Default | ✅ PASS | This feature *is* the restorable-backup mechanism; snapshots are immutable (FR-005); zero writes/deletes to Google; working copies are deep, independent copies (FR-011); snapshot deletion gated by explicit confirmation + working-copy guard + audit (FR-021/022/023). Dry-run/undo for Google writes is N/A (no Google writes). |
| III. Human-in-the-Loop | ✅ PASS | No automated merge/delete of contacts; every snapshot/working-copy/delete action is an explicit operator action. (Dedup/triage are out of scope here.) |
| IV. Test-First | ✅ PASS | TDD planned; People API behind a seam so CI never calls live Google; immutability, resumability, delete-guard, and audit are covered by integration tests (D10). |
| V. Auditability & Observability | ✅ PASS | Append-only `AuditEntry` for snapshot create/delete and working-copy create (FR-019/023); structured logs with token/PII redaction; import progress observable (FR-015). |

**Result**: PASS — no violations. Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-people-api-snapshots/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── openapi.yaml      # Phase 1 output — backend REST contract
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/            # SQLAlchemy: account, credential, snapshot, import_job,
│   │                      #   snapshot_contact, working_copy, working_copy_contact, audit_entry
│   ├── services/          # snapshot_service, working_copy_service, account_service,
│   │                      #   audit_service, crypto (token encryption)
│   ├── integrations/
│   │   └── people_client.py   # PeopleClient seam over google-api-python-client
│   ├── workers/
│   │   └── import_worker.py    # PG-backed queue consumer; resumable paged import
│   ├── api/               # FastAPI routers matching contracts/openapi.yaml
│   └── core/              # config, db session, logging (redaction), backoff
├── migrations/            # Alembic
└── tests/
    ├── contract/          # API + PeopleClient adapter contract tests
    ├── integration/       # immutability, resumability, delete-guard, audit, multi-account
    └── unit/

frontend/
├── src/
│   ├── components/        # SnapshotList, SnapshotDetail, ContactTable, WorkingCopyList, ...
│   ├── pages/             # Accounts, Snapshots, Snapshot, WorkingCopies
│   ├── services/          # typed API client (generated/derived from openapi.yaml)
│   └── stores/            # Pinia stores
└── tests/                 # Vitest + Vue Test Utils

docker-compose.yml         # db, backend, worker, web
biome.json                 # frontend lint/format config
```

**Structure Decision**: Web-application layout (Option 2) plus a dedicated **worker** service for
the resumable import. Backend and worker share `backend/src` (same models/services); the worker
entrypoint is `workers/import_worker.py`. The frontend is a separate Vue 3 app. This matches the
constitution's stack and the docker-compose deployment, and keeps the People API behind a single
`PeopleClient` seam for testability.

## Complexity Tracking

> No constitution violations — section intentionally empty.
