# Implementation Plan: Validate & Normalize (Tidy step)

**Branch**: `006-validate-normalize` | **Date**: 2026-06-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/006-validate-normalize/spec.md`

## Summary

Insert a new seventh wizard step, **Tidy**, between **Review** and **Export**. A background
**ValidationRun** over the active Draft's *kept* contacts (those not marked for deletion) does two
things: (1) **auto-applies** unambiguous fixes — reformat valid phones to E.164, set *mobile* type
when the number is confidently mobile, upgrade `http://`→`https://` when the https site is reachable —
each as a reversible **StagedEdit** on the Draft; and (2) **queues** everything uncertain or broken
(invalid phone, unclear type, invalid email, dead email domain, unreachable website, SSRF-unsafe
website) as **ValidationItem** rows the operator resolves one at a time. The step is **passable** with
a warning, shows a **running** state like Backup/Merge/Export, and reuses the existing
StagedEdit/undo/audit machinery so the constitution's non-destructive + human-in-the-loop guarantees
hold. Phone parsing uses `phonenumbers`; email uses `email-validator` (syntax + MX via `dnspython`);
websites use `httpx` with a per-hop SSRF guard. This knowingly extends beyond 005's frontend-only
scope (new deps, one migration, one worker, one router) — the same kind of scoped exception as the
005 deletion addendum.

## Technical Context

**Language/Version**: Backend Python 3.12 (FastAPI); Frontend TypeScript 5.6, Vue 3.5 (`<script setup>`)

**Primary Dependencies**:
- **New backend** — `phonenumbers` (libphonenumber port; E.164 + validity + number type),
  `email-validator` (syntax + deliverability/MX, pulls `dnspython`), `httpx` (website reachability;
  already a dev-dep → promoted to runtime). Optional `geoip2` + a local GeoLite2-Country DB for
  region detection (falls back to client locale/timezone when absent — see research D7).
- **Existing reused** — SQLAlchemy 2 + Alembic, PostgreSQL, the StagedEdit/undo/audit services
  (feature 003), the combined worker loop (`workers/run_all.py`), the background-job + `running`-state
  pattern (features 002/004/005).
- **New frontend** — none; reuses Pinia, Vue Router, shadcn-vue/Tailwind from 005.

**Storage**: PostgreSQL. One migration `0005_validate_normalize` adds `validation_run` and
`validation_item`. No existing table is altered except widening `StagedEdit.kind`'s allowed value set
to include `normalize` (the column is already `String(16)`; no DDL change).

**Testing**: Backend `pytest` (+ `respx` for httpx mocking — already a dev-dep; DNS/geoip mocked via
monkeypatch). Frontend `vitest` + `@vue/test-utils` (jsdom). TDD: failing tests first (Principle IV).

**Target Platform**: Self-hosted containers (docker-compose); evergreen browsers (desktop + mobile).

**Project Type**: Web application — backend (FastAPI) + frontend (Vue). This feature touches both.

**Performance Goals**: A ValidationRun must never hang: every website check is time-limited
(`website_check_timeout_seconds`, default 5s) and concurrency-bounded
(`website_check_concurrency`, default 8); the run completes or fails visibly regardless of slow/
blocking sites (SC-008). Wizard transitions stay <100ms perceived; existing poll cadences preserved.

**Constraints**: Biome stays the single frontend linter/formatter and must pass in CI; `vue-tsc` build
stays green. New Python deps stay within the Python/FastAPI/PostgreSQL stack — no new *core* technology
(language/datastore/dedup engine), so no constitutional amendment is required (research D9). Outbound
network limited to the operator's own contact values; SSRF guard on every redirect hop.

**Scale/Scope**: 1 operator, multi-account; per Draft typically up to a few thousand kept contacts,
each with 0–N phones/emails/websites. 1 migration, ~3 new backend services/modules + 1 worker + 1
router; ~1 new frontend step page + 1 store + api additions; the stepper grows 6 → 7 steps.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment | Status |
|-----------|-----------|--------|
| I. Privacy & Data Protection | No new OAuth scope; tokens untouched and never rendered. Outbound DNS/HTTP target only the operator's own contact values and are required to validate them (no third-party data sharing). Region detection uses a **local** GeoLite2 DB or client locale — no contact PII or IP sent to a third-party geo service by default. SSRF guard (FR-029) prevents the validator from reaching internal infra. Per-account isolation unchanged. | Pass |
| II. Non-Destructive by Default | Every change (auto-fix or queue resolution) is a reversible **StagedEdit** on the **Draft**; the frozen snapshot is never touched (FR-021). Undo returns the exact prior value (FR-022). Tidy pushes nothing to Google — edits reach Google only via the unchanged Export step and its existing dry-run/snapshot/confirm/undo safeguards (FR-024). | Pass |
| III. Human-in-the-Loop | Auto-apply is limited to unambiguous transforms; every uncertain/broken finding is queued for an explicit human decision (FR-008…FR-019). The step is passable only via an explicit, warned action (FR-004). No silent data changes. | Pass |
| IV. Test-First (NON-NEGOTIABLE) | TDD: failing `pytest` specs for phone/email/website validators, the validation service (auto + queue + counts + idempotent re-run), resolution/skip/undo, the worker, and API contract; failing `vitest` specs for the 7-step stepper, tidy store derivation, and queue UI — all before implementation. | Pass (committed) |
| V. Auditability & Observability | Each auto-fix, queue resolution, and undo records an append-only audit entry (who/what/before→after/why) via the existing `audit_service` (FR-023). Logs structured; no secrets/PII leaked. | Pass |
| Tech Constraints — core stack | Adds Python libraries only (`phonenumbers`, `email-validator`/`dnspython`, `httpx`, optional `geoip2`); no new language, datastore, or dedup engine. Stays FastAPI + PostgreSQL. Therefore **not** a constitutional amendment (governance §Technology Constraints). | Pass |
| Tech Constraints — Biome only | Frontend additions are Biome-formatted; the CI Biome gate stays authoritative; no competing linter/formatter introduced. | Pass |
| Scope exception (frontend-only) | Feature 005 was frontend-only; Tidy knowingly adds backend work. This is recorded as an explicit, scoped exception (like the 005 deletion addendum), justified because phone/email/website validation cannot be done correctly client-side. Not a constitution violation — all principles above still hold. | Pass (noted) |

**Result**: No violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/006-validate-normalize/
├── plan.md              # This file
├── spec.md              # Feature spec (written + clarified)
├── research.md          # Phase 0 — library/approach decisions
├── data-model.md        # Phase 1 — ValidationRun / ValidationItem + StagedEdit reuse
├── quickstart.md        # Phase 1 — runnable end-to-end validation guide
└── contracts/
    └── validation-api.md # Phase 1 — HTTP contract for the new endpoints
```

### Source Code (repository root)

```text
backend/
├── pyproject.toml                         # + phonenumbers, email-validator, httpx (runtime); geoip2 optional
├── migrations/versions/
│   └── 0005_validate_normalize.py         # NEW — validation_run, validation_item
├── src/
│   ├── core/config.py                     # + website-check + region-fallback settings
│   ├── models/
│   │   └── validation.py                  # NEW — ValidationRun, ValidationItem (+ status/issue sets)
│   │   └── triage.py                      # widen EDIT_KINDS to include "normalize" (no DDL)
│   ├── services/
│   │   ├── phone_normalizer.py            # NEW — parse/validate/E.164/type via phonenumbers
│   │   ├── email_validator_service.py     # NEW — syntax + MX via email-validator/dnspython
│   │   ├── website_checker.py             # NEW — httpx reachability + http→https + SSRF guard
│   │   ├── region_service.py              # NEW — detect default region (geoip/local, fallback)
│   │   └── validation_service.py          # NEW — orchestrate a run: auto-fix (StagedEdit) + queue; resolve/skip
│   ├── api/
│   │   ├── routers/validation.py          # NEW — run + items + resolve/skip endpoints
│   │   ├── routers/__init__.py            # + validation
│   │   ├── schemas.py                      # + Validation* request/response models
│   │   └── main.py                         # include validation.router
│   └── workers/
│       ├── validation_worker.py           # NEW — claim queued ValidationRun (FOR UPDATE SKIP LOCKED), run to terminal
│       └── run_all.py                      # + validation_worker.run_once in the combined loop
└── tests/
    ├── unit/ (phone_normalizer, email_validator_service, website_checker, region_service)
    ├── integration/ (validation_service: auto+queue+counts+rerun; resolve/skip/undo; worker)
    └── contract/ (validation router)

frontend/
├── src/
│   ├── wizard/steps.ts                     # + 'tidy' (index 6); Export → index 7, prereq 'tidy'
│   ├── stores/
│   │   ├── wizard.ts                        # + tidy completed/running/passable derivation; Export prereq=tidy
│   │   └── tidy.ts                          # NEW — run lifecycle, poll, queue, resolve/skip/undo
│   ├── services/api.ts                      # + validation endpoints + detectRegion
│   ├── pages/wizard/TidyStep.vue            # NEW — start/running/summary + queue host
│   ├── components/tidy/
│   │   ├── TidyRunPanel.vue                 # NEW — start button, running, summary counts, region indicator
│   │   ├── TidyQueue.vue                    # NEW — pending-item list
│   │   └── TidyQueueItem.vue                # NEW — per-issue labeled actions (set type / edit / remove / skip)
│   └── router/index.ts                      # + /wizard/tidy child route (before export)
└── tests/ (src/**/*.spec.ts)                # steps(7), wizard tidy derivation, tidy store, queue UI, region
```

**Structure Decision**: Web application touching **both** tiers. The backend gains a self-contained
validation slice (model → 4 stateless checker/normalizer services → orchestrating `validation_service`
→ worker → router) mirroring the existing dedup/export slices, and reuses StagedEdit/undo/audit
verbatim. The frontend adds one wizard step (page + components + store) and extends the wizard
derivation, following the 005 step pattern. No existing endpoint or table is changed (only
`StagedEdit.kind`'s allowed-value set widens, no DDL).

## Phase 0 — Research

See [research.md](./research.md). Resolves: phone library + region default (`phonenumbers`, E.164,
`number_type` for mobile-only auto-typing); email depth (`email-validator` syntax + MX, no SMTP);
website reachability semantics (any HTTP response = reachable; transport failure = queue) and the
SSRF guard (resolve + reject non-public IPs on every hop); the auto-vs-queue split mapped to
StagedEdit reuse; worker placement (combined loop, bounded async fan-out for HTTP); region detection
(local GeoLite2 with client locale/timezone fallback; per-run `default_region`); and why the new
Python deps are not a constitutional amendment.

## Phase 1 — Design & Contracts

- [data-model.md](./data-model.md) — `ValidationRun` and `ValidationItem` schemas, the `StagedEdit`
  reuse (`kind="normalize"`), status/issue-type enumerations, the run state machine, and the
  auto-vs-queue decision table per field.
- [contracts/validation-api.md](./contracts/validation-api.md) — HTTP contract for start-run,
  list-runs (newest-first, for wizard restore), get-run, list-items, resolve-item, skip-item, undo,
  and detect-region (served at `GET /api/settings/detect-region`, though implemented in
  `validation.py`); request/response shapes (incl. the derived `pendingCount`); error modes (incl.
  the SSRF-unsafe and not-reachable issue types).
- [quickstart.md](./quickstart.md) — install deps, run the migration, drive a Tidy run end-to-end
  over a seeded Draft, and verify auto-fixes, the queue, resolution/undo, passability, and the SSRF
  guard.
- **Agent context**: update the active-feature pointer in `CLAUDE.md` to this plan.

## Complexity Tracking

No constitution violations — section intentionally empty.
