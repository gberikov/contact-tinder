# Implementation Plan: Working-Copy Deduplication with Zingg

**Branch**: `002-zingg-dedup` | **Date**: 2026-06-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-zingg-dedup/spec.md`

## Summary

Add deduplication to an existing **working copy** (feature 001). The operator triggers a **dedup
run**; a dedicated **Spark/Zingg batch container** reads the working copy's contacts over JDBC,
runs Zingg's `match` phase using a **pre-trained, bundled contacts model** (no operator labeling),
and writes match output (`z_cluster`, `z_minScore`, `z_maxScore`) back to Postgres. The backend
ingests that output into **DuplicateCluster**/**ClusterMember** rows with confidence scores and
surfaces them for review. The operator resolves each cluster by a **survivor-based merge** inside
the working copy (reversible via a **MergeRecord**) or a **dismiss** ("not a duplicate"). The
source snapshot is never touched and nothing is written to Google. Runs are **PG-backed jobs**
consumed by the dedup container, mirroring feature 001's `import_worker` pattern (PostgreSQL stays
the only datastore — no Redis).

## Technical Context

**Language/Version**: Python 3.12 (backend, dedup worker); TypeScript 5.x (frontend); JVM 17 +
Apache Spark 3.5 inside the dedup container only.

**Primary Dependencies**: existing — FastAPI, SQLAlchemy 2.x + Alembic, psycopg, Pydantic, Vue 3 +
Vite, Biome. New — `zingg` (Python API over Spark) + Apache Spark + PostgreSQL JDBC driver, all
isolated in a separate `dedup` image; backend depends only on a thin `DedupEngine` seam (no Spark
in the backend/web images).

**Storage**: PostgreSQL — adds `dedup_run`, `duplicate_cluster`, `cluster_member`, `merge_record`
tables, a `status` column on `working_copy_contact`, and a per-run `dedup_match_raw` staging table
Zingg writes via JDBC. Zingg's trained model is a **bundled file artifact** baked into the dedup
image (not in PG).

**Testing**: backend `pytest` with a **`DedupEngine` seam** — a deterministic fake engine in CI
(no Spark/JVM), and a slow-marked integration test that exercises the real Zingg engine outside the
default CI lane; `respx`/FastAPI `TestClient` for API contracts; frontend `Vitest` + Vue Test
Utils; Biome `ci` gate. Per Principle IV, Zingg/Spark is exercised only behind the seam.

**Target Platform**: Linux containers via docker-compose; new service `dedup` (Spark local mode +
Zingg + model + JDBC driver) alongside `db`, `backend`, `worker`, `web`.

**Performance Goals**: SC-002 — a dedup run over ≤50,000 contacts completes within ~30 min on
modest self-hosted hardware (Spark local mode, blocking on, tuned `numPartitions`/driver memory);
SC-001 — ≥90% of seeded true-duplicate pairs land in the same cluster.

**Constraints**: contact PII stays inside the compose boundary (JDBC over the internal network
only — Principle I); snapshot byte-identical before/after any run or merge (SC-004); no
auto-merge/auto-dismiss — every resolution is an explicit operator action (FR-017); merges fully
reversible (SC-003); per-working-copy/per-account isolation (FR-022); one active run per working
copy (FR-007).

**Scale/Scope**: single self-hosted operator; multiple working copies; up to ~50,000 contacts per
working copy; clusters typically 2 members, occasionally more (transitive).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How this plan complies |
|-----------|--------|------------------------|
| I. Privacy & Data Protection | ✅ PASS | Contact data flows only between `db` and the `dedup` container over the internal compose network; **no contact PII leaves the deployment** (Zingg/Spark run in-boundary, FR-023). No new Google scopes (read-only foundation from 001 unchanged; this feature makes **zero** Google calls). No secrets/tokens in clusters, audit, or logs (FR-021). Per-account/per-working-copy isolation enforced by `working_copy_id` scoping (FR-022). The JDBC credential is supplied via env/secret store, never hard-coded. |
| II. Non-Destructive by Default | ✅ PASS | Runs are read-only over the working copy; snapshot untouched and verified byte-identical (FR-003, SC-004). Merges are **staged & reversible**: non-survivors are marked `retired` (soft), a `MergeRecord` stores pre-merge state, and undo restores exactly (FR-018, SC-003). Dry-run/Google-write guarantees are N/A (no Google writes here). |
| III. Human-in-the-Loop | ✅ PASS | Zingg only **proposes** clusters + scores; nothing is merged or dismissed without an explicit operator action; batch approval is itself an explicit action, never silent (FR-017, SC-005). Ambiguous/low-confidence clusters are surfaced for manual review, never auto-resolved (FR-011/FR-014). |
| IV. Test-First | ✅ PASS | TDD throughout; the `DedupEngine` seam lets CI test ingestion, clustering, merge/undo, and audit with a deterministic fake — **no Spark/JVM in CI**; a separate slow integration test covers the real Zingg engine. Merge reversibility, isolation, and the no-auto-merge rule are covered by integration tests. |
| V. Auditability & Observability | ✅ PASS | Append-only `AuditEntry` extended with `dedup.run.started/completed/failed`, `cluster.merged`, `merge.undone`, `cluster.dismissed`, capturing target + source refs, redacted (FR-021, SC-006). Run progress/terminal state observable (FR-006); structured logs redact PII. |

**Result**: PASS — no violations. Complexity Tracking left empty. (Adding the `dedup` container is
mandated by the constitution's Technology Constraints, which fix Zingg/Spark as the dedup engine —
not new optional complexity.)

## Project Structure

### Documentation (this feature)

```text
specs/002-zingg-dedup/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── openapi.yaml      # Phase 1 output — dedup/cluster/merge REST contract
├── checklists/
│   └── requirements.md   # Spec quality checklist (from /speckit-specify)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   └── dedup.py          # NEW: DedupRun, DuplicateCluster, ClusterMember, MergeRecord
│   │                          #   (+ status column added to working_copy_contact)
│   ├── services/
│   │   ├── dedup_service.py       # NEW: create/list runs, ingest match output → clusters
│   │   ├── cluster_service.py     # NEW: review queries, merge (survivor), dismiss, undo
│   │   ├── contact_flatten.py     # NEW: Person payload → Zingg match columns
│   │   └── audit_service.py       # extend with dedup actions
│   ├── integrations/
│   │   └── dedup_engine.py        # NEW: DedupEngine seam (protocol) + FakeDedupEngine (CI)
│   ├── workers/
│   │   └── dedup_worker.py        # NEW: PG-backed run consumer (FOR UPDATE SKIP LOCKED)
│   ├── api/routers/
│   │   └── dedup.py               # NEW: routers matching contracts/openapi.yaml
│   └── core/                      # reuse config/db/logging/backoff
├── dedup/                         # NEW: Zingg/Spark job (runs only in the dedup image)
│   ├── zingg_engine.py            # ZinggDedupEngine: match phase via JDBC pipes
│   ├── field_defs.py              # contacts FieldDefinition set (FUZZY/EMAIL/…)
│   └── model/                     # bundled PRE-TRAINED Zingg model (modelId dir) + training notes
├── migrations/                    # Alembic: new tables + working_copy_contact.status
└── tests/
    ├── contract/                  # dedup API + DedupEngine seam contract
    ├── integration/               # ingest→cluster, merge/undo, isolation, no-auto-merge,
    │                              #   snapshot-immutability, (slow) real-Zingg match
    └── unit/                      # flatten, survivor-merge field union, confidence mapping

frontend/
├── src/
│   ├── components/   # DedupRunPanel, ClusterList, ClusterCard, MergePreview, ConfidenceBadge
│   ├── pages/        # WorkingCopyDedup (run + review + resolve)
│   ├── services/     # typed dedup API client (from openapi.yaml)
│   └── stores/       # Pinia: dedup run + clusters
└── tests/            # Vitest + Vue Test Utils

docker-compose.yml     # add `dedup` service (Spark+Zingg+model+JDBC driver, PG-backed consumer)
```

**Structure Decision**: Keep feature 001's web-application layout and add one **dedicated `dedup`
container** for the JVM/Spark/Zingg engine, exactly mirroring how `worker` isolates the import job.
The backend stays Spark-free and talks to the engine only through the `DedupEngine` seam (real impl
lives in `backend/dedup/`, run inside the dedup image; CI uses `FakeDedupEngine`). Data moves over
**Postgres JDBC** so PostgreSQL remains the single data hub. This honours the constitution's fixed
stack (Zingg/Spark in-boundary) and maximises testability.

## Complexity Tracking

> No constitution violations — section intentionally empty. The `dedup` container is required by
> the constitution's Technology Constraints (Zingg on Spark), not discretionary complexity.
