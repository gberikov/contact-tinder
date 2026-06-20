# Quickstart & Validation: Working-Copy Deduplication with Zingg

**Feature**: `002-zingg-dedup` · **Date**: 2026-06-20

This guide proves the feature end-to-end: run Zingg dedup over a working copy, review clusters, and
resolve them by reversible survivor-based merge or dismiss — with the source snapshot unchanged.
It references [contracts/openapi.yaml](contracts/openapi.yaml) and [data-model.md](data-model.md)
rather than restating field shapes. Implementation code lives in `tasks.md`/the implement phase.

## Prerequisites

- Feature 001 working: at least one **snapshot** and a **ready working copy** with contacts
  (including a couple of obvious duplicates, e.g. `John Smith / Jon Smith` sharing a phone).
- Docker + docker-compose; the new **`dedup`** service built (Spark local mode + Zingg + the
  **bundled pre-trained model** under `backend/dedup/model/` + Postgres JDBC driver).
- `.env` provides `DATABASE_URL` (reused) and the dedup container's JDBC connection settings.

## Start the stack

```bash
docker compose up -d db backend worker web dedup
docker compose ps        # db healthy; backend :8000; web :5173; worker + dedup running
docker compose run --rm backend alembic upgrade head   # creates dedup tables + wcc.status
```

## Scenario A — Find duplicates (User Story 1 / FR-001..009)

1. Pick a ready working copy id `WC`.
2. Start a run:
   ```bash
   curl -X POST localhost:8000/api/working-copies/$WC/dedup-runs   # → 202, DedupRun {status: queued}
   ```
3. Poll until terminal:
   ```bash
   curl localhost:8000/api/dedup-runs/$RUN_ID                      # status → running → completed
   ```
**Expected**: run reaches `completed` with a `clusterCount`; the seeded `John/Jon Smith` pair is in
one cluster. A second `POST` while a run is active returns **409** (FR-007). Verify the snapshot and
the working copy's contact payloads are **unchanged** (SC-004).

## Scenario B — Review clusters (User Story 2 / FR-010..013)

```bash
curl "localhost:8000/api/dedup-runs/$RUN_ID/clusters?status=pending"   # ordered by confidence desc
curl localhost:8000/api/clusters/$CLUSTER_ID                            # members + ContactSummary
```
**Expected**: each cluster lists members with `displayName`/email/phone and a `confidence`
(`z_maxScore`); strongest first; `minConfidence` query filters out weak groups. Viewing changes
nothing (FR-013). In the UI: open **Working Copy → Deduplicate**, see the cluster list and a
`ConfidenceBadge` per cluster.

## Scenario C — Merge a cluster, reversibly (User Story 3 / FR-014..018, SC-003)

1. Preview:
   ```bash
   curl localhost:8000/api/clusters/$CLUSTER_ID/merge-preview        # survivor + proposedPayload + conflicts
   ```
2. Confirm:
   ```bash
   curl -X POST localhost:8000/api/clusters/$CLUSTER_ID/merge \
     -H 'content-type: application/json' -d '{"survivorContactId":"'$SURVIVOR'"}'   # → MergeResult
   ```
**Expected**: one combined **survivor** contact remains `active` with the unioned fields; the other
members are `retired`; the cluster is `merged`; an `AuditEntry` `cluster.merged` is written.
3. Undo:
   ```bash
   curl -X POST localhost:8000/api/merge-records/$MERGE_RECORD_ID/undo
   ```
**Expected**: survivor payload restored exactly, retired members back to `active`, cluster back to
`pending`, `merge.undone` audited (SC-003). Snapshot still unchanged (SC-004).

## Scenario D — Dismiss "not a duplicate" (FR-019, per-run only)

```bash
curl -X POST localhost:8000/api/clusters/$CLUSTER_ID/dismiss        # → cluster {status: dismissed}
```
**Expected**: members stay separate and `active`; the cluster is not re-presented within this run.
Re-running dedup (Scenario A) **re-detects** the same pair as a fresh `pending` cluster (per-run
dismissals — clarification 2026-06-20).

## Scenario E — No-auto-merge & isolation (SC-005, FR-022)

- Confirm that after a `completed` run with clusters, **no** cluster is `merged`/`dismissed` until an
  explicit merge/dismiss call (SC-005).
- Confirm clusters/merges for working copy `WC` are never returned when querying another working
  copy/account (FR-022).

## Automated validation (maps to acceptance criteria)

| Check | Type | Asserts |
|-------|------|---------|
| ingest → clusters via `FakeDedupEngine` | integration | size-≥2 grouping, confidence mapping (D5, D8) |
| merge → survivor/retire/MergeRecord | integration | FR-016; audit `cluster.merged` |
| undo restores exact pre-merge set | integration | SC-003 / FR-018 |
| repeated merge+undo cycles | integration | working copy `active` set identical to pre-dedup |
| snapshot unchanged after run/merge/undo | integration | SC-004 |
| second active run rejected (409) | contract | FR-007 partial unique index |
| dismiss is per-run; re-run re-detects | integration | FR-019 clarification |
| resolve cluster with retired member blocked | integration | FR-020 |
| no cluster auto-resolved | integration | SC-005 |
| cross-account/working-copy access denied | integration | FR-022 (isolation) |
| JDBC/Spark path stays in-boundary (no egress) | quickstart/arch check | FR-023 |
| real Zingg `match` on seeded set ≥90% pairs | integration (slow) | SC-001 |
| 50k working copy completes ≤ ~30 min | perf (manual/slow) | SC-002 |
| frontend cluster list + merge preview | Vitest + Vue Test Utils | US2/US3 UI |
| Biome lint/format | CI gate | constitution quality gate |

Run backend tests (no Spark needed for the default lane — `FakeDedupEngine`):

```bash
docker compose run --rm backend pytest -q            # excludes slow real-Zingg/perf marks
docker compose run --rm backend pytest -q -m slow    # real ZinggDedupEngine end-to-end (SC-001)
cd frontend && npm run test && npx biome ci .
```

## Success signals

- A run over a duplicate-laden working copy returns confidence-scored clusters; obvious duplicates
  are grouped (SC-001).
- Every merge is reversible and leaves the snapshot byte-identical (SC-003/SC-004).
- Nothing is merged/dismissed without an explicit operator action (SC-005); every run/merge/undo/
  dismiss is audited with no secrets (SC-006).
