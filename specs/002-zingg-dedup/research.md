# Phase 0 Research: Working-Copy Deduplication with Zingg

**Feature**: `002-zingg-dedup` · **Date**: 2026-06-20

Resolves the Technical Context unknowns: how Zingg is invoked, how it gets a model without operator
labeling, how contact data moves between Postgres and Spark, how match output maps to clusters, how
survivor-based merge + undo work, and how all of this stays testable without Spark in CI.

---

## D1 — Zingg invocation & deployment model

**Decision**: Run Zingg in a **dedicated `dedup` container built FROM the official `zingg/zingg`
image** (which bundles Apache Spark + JVM + the Zingg distribution/jars + the `zingg` Python API).
We layer only our worker code and its non-Spark deps on top — we do **not** rebuild or pip-install
Spark/Zingg ourselves, so the Python API always matches the bundled jars/model format. The container
is a **PostgreSQL-backed job consumer** that claims `dedup_run` rows with `SELECT … FOR UPDATE SKIP
LOCKED`, exactly like feature 001's `import_worker`. The FastAPI backend never imports Spark; it
talks to the engine only through a `DedupEngine` seam.

**Launcher note**: Zingg programs are PySpark programs — a SparkSession needs the Zingg assembly jar
on its classpath. The image sets `ZINGG_HOME`; the worker is started with that jar on
`PYSPARK_SUBMIT_ARGS`, and the engine uses `ZinggWithSpark(args, options)` (which builds the Spark
session) rather than bare `Zingg(...)`.

**Rationale**: The constitution fixes Zingg/Spark as the dedup engine and requires it to be "a batch
engine invoked by the backend." A separate image keeps the backend/web images lean, isolates the
heavy JVM/Spark dependency, reuses the proven PG-queue pattern (no Redis), and gives a clean seam
for CI. Spark local mode is sufficient for a single-operator, ≤50k workload.

**Alternatives considered**: (a) Zingg in-process inside the existing `worker` — rejected: forces
Spark/JVM into the shared backend image and couples import and dedup lifecycles. (b) Building the
image FROM a slim Python base and pip-installing `pyspark`+`zingg` — rejected: fragile and
incomplete (the `zingg` pip package needs the Zingg jars/distribution, not just the wheel), and
risks version drift between the wheel and the jars. Using the official image avoids both. (c) Zingg
CLI via subprocess with JSON config — workable but the Python API is first-class and easier to
parameterise per run. (d) External managed Spark — rejected: would send contact PII outside the
deployment boundary (violates Principle I).

## D2 — Getting a model without operator labeling ("pre-configured")

**Decision**: Ship a **pre-trained Zingg model as a bundled artifact** in the dedup image. During
development we build the model **once**, offline, from a representative/synthetic contacts training
set (generated with known duplicate / non-duplicate pairs, optionally refined via Zingg
`findTrainingData` + `label`), run the `train` phase, and commit the resulting model directory
(`zinggDir/<modelId>`) under `backend/dedup/model/`. At **runtime the operator triggers only the
`match` phase**, which reuses the bundled model with **no labeling step** (spec clarification:
pre-configured, no labeling).

**Rationale**: Zingg's docs confirm a model is "trained once per schema" and `match` reuses it in
production without retraining. Baking the trained model into the image gives out-of-the-box dedup
with a fixed schema and fixed matching quality for v1 — exactly the chosen scope. Field definitions
and the model are versioned together via `model_version` recorded on each `DedupRun`.

**Alternatives considered**: (a) Operator labels then trains per working copy — rejected by spec
(adds a labeling step). (b) Pure unsupervised/threshold matching — rejected: loses Zingg's learned
blocking/scoring and the constitution mandates Zingg. (c) Re-train on every run — rejected:
slow and needs labels. **Risk noted**: a fixed model can't be improved by the operator in v1;
interactive refinement is explicitly deferred (spec Out of Scope).

## D3 — Data exchange between Postgres and Spark/Zingg

**Decision**: Use **Zingg JDBC pipes** against the same Postgres. **Input pipe** = a per-run,
flattened projection of the working copy's contacts (see D4) exposed as a stable relation
(`dbtable` = a parameterised query or a per-run staging table `dedup_input_<run>`); **output pipe** =
a per-run staging table `dedup_match_raw` (run-scoped) that Zingg writes the matched rows + `z_*`
columns into. The dedup container then ingests `dedup_match_raw` into domain tables and drops the
staging rows. The Postgres JDBC driver is added to Spark via `spark.jars`.

**Rationale**: Keeps PostgreSQL the single data hub (no shared-volume file shuffling, no extra
datastore), keeps contact data inside the compose network, and matches Zingg's documented Postgres
connector. Staging tables make a run idempotent and easy to clean up on retry.

**Alternatives considered**: Parquet/CSV on a shared volume — rejected: extra moving parts, file
lifecycle/cleanup, and weaker isolation than run-scoped tables. Direct Spark→domain-table writes —
rejected: Zingg owns the output schema (`z_*`); a staging table decouples Zingg's shape from ours.

## D4 — Flattening `Person` payloads into match columns

**Decision**: A `contact_flatten` step projects each `working_copy_contact` into Zingg input columns:
`wcc_id` (the row UUID, `MatchType.DONT_USE` — identity only), `first_name`, `last_name`,
`full_name` (FUZZY), `email` (EMAIL match type), `phone` (FUZZY on normalised digits), and
`organization` (FUZZY). It reuses/extends feature 001's `contact_fields.py` extraction logic.
Multi-valued fields (several emails/phones) are reduced to the primary value for matching; the raw
payload remains the source of truth and is never mutated by a run.

**Rationale**: Zingg matches on flat typed columns with per-field `MatchType`. Names/email/phone are
the high-signal fields for contact dedup (FR-004). Keeping a stable `wcc_id` lets us map match
output rows back to exact working-copy contacts.

**Alternatives considered**: Exploding all email/phone values into multiple rows per contact —
deferred: improves recall but complicates cluster-member mapping; revisit if SC-001 (≥90%) is not
met with primary-value matching.

## D5 — Mapping match output → clusters & confidence

**Decision**: Zingg's `match` output adds `z_cluster`, `z_minScore`, `z_maxScore` per row. Group by
`z_cluster`; **clusters of size ≥2 become `DuplicateCluster`** rows (singletons ignored). Cluster
**confidence = `z_maxScore`** (strongest in-cluster association) surfaced to the operator;
`z_minScore` is retained as a secondary signal/weak-link flag. A configurable **minimum-confidence
floor** (default favouring precision, e.g. drop clusters with `z_maxScore` below the floor) gates
which clusters are presented. Each matched row → one `ClusterMember` referencing its `wcc_id`.

**Rationale**: Matches Zingg's documented output and the spec's "confidence score per cluster"
(FR-005) and precision-favouring default (Assumptions). Transitivity (A~B, B~C ⇒ one cluster) is
handled natively by `z_cluster`, satisfying multi-member clusters (edge case).

**Open knob for /plan→config**: exact floor value and the "large cluster" review hint (Zingg docs
suggest inspecting clusters >4–5 for over-merging) are configuration, recorded on the run.

## D6 — Survivor-based merge & reversible undo

**Decision** (spec clarification: survivor-based): merging a cluster picks a **survivor** member
(default = most complete payload, operator-overridable). The system builds a **proposed merged
payload**: union of non-conflicting multi-valued fields into the survivor; for conflicting
single-value fields, default to the survivor's value with the conflict shown for override. On
confirm: the survivor's `working_copy_contact.payload` is updated to the merged payload, the other
members get `status = 'retired'` (soft, not deleted), the cluster is marked `merged`, and a
**`MergeRecord`** stores the survivor's **pre-merge payload** + each retired member's id (enough to
restore exactly). **Undo** reverts the survivor payload and flips retired members back to `active`,
then removes the merged cluster resolution. `working_copy_contact` gains a `status`
(`active`/`retired`) column; only `active` contacts are "live" in the working copy.

**Rationale**: Survivor-based keeps a stable `origin_resource_name` link for the eventual Google-push
feature and makes undo a clean restore (Principle II, FR-016/FR-018). Soft-retire + MergeRecord
gives full reversibility without touching the snapshot (SC-003/SC-004).

**Retention window (deferred clarification → decided here)**: because merges are **local
working-copy state with no Google writes**, undo remains available **as long as the MergeRecord
exists** (i.e. for the life of the working copy); no time-based expiry is needed in v1. A later
Google-push feature will introduce its own commit/retention semantics.

**Alternatives considered**: brand-new merged contact (spec rejected — option B); hard-delete
non-survivors (rejected — breaks reversibility).

## D7 — Run lifecycle, concurrency & staleness

**Decision**: `DedupRun.status`: `queued → running → completed | failed`. The dedup container claims
one run at a time per working copy; a **partial unique index** enforces **at most one active
(`queued`/`running`) run per `working_copy_id`** (FR-007) — a second request is rejected/queued. A
newer `completed` run **supersedes** the prior run's still-`pending` clusters (older pending clusters
→ `superseded`) (FR-008). Acting on a cluster whose members are no longer `active` (already
merged/retired) is **blocked** with a clear error (FR-020). Dismissals are **per-run only** (spec
clarification): a dismiss sets cluster `status = dismissed` within its run; a later run re-detects
the pair as a fresh cluster (no cross-run suppression).

**Rationale**: Mirrors feature 001's job semantics and directly encodes the spec's edge cases and
clarifications, keeping results consistent under re-runs and concurrent edits.

## D8 — Testability without Spark in CI (Principle IV)

**Decision**: Define `DedupEngine` as a protocol: `run(run_id, input_rows) -> Iterable[MatchRow]`
(where `MatchRow` carries `wcc_id`, `z_cluster`, `z_minScore`, `z_maxScore`). CI uses
**`FakeDedupEngine`** — a deterministic rule-based matcher (e.g. same normalised phone or
email-localpart ⇒ same cluster, with synthetic scores) — so ingestion, clustering, merge/undo,
isolation, no-auto-merge, and audit are all tested **without Spark/JVM**. A **slow-marked**
integration test exercises the real `ZinggDedupEngine` against an ephemeral Postgres to validate the
end-to-end Spark path and the bundled model on seeded data (SC-001). CI never needs Spark.

**Rationale**: The constitution requires Zingg/Spark to sit "behind seams that allow contract/
integration tests without" the heavy engine in the default lane (Principle IV).

## D9 — Performance for ≤50k contacts (SC-002, ~30 min)

**Decision**: Spark **local mode** in the `dedup` container with tuned `numPartitions` (start ~4–8),
sized driver memory, and Zingg's default **blocking** enabled (Zingg builds blocks so it does not
compare all O(n²) pairs). The bundled model is loaded once per run; only the `match` phase runs.
Progress is reflected by `DedupRun.status` transitions (coarse-grained; Spark batch is not
incrementally streamed).

**Rationale**: Zingg's learned blocking makes 50k tractable in minutes-to-tens-of-minutes on a
single node; ~30 min is a safe ceiling on modest hardware (spec SC-002). Tuning knobs are
config-recorded per run for reproducibility.

**Alternatives considered**: a Spark cluster — unnecessary for single-operator scale and outside the
docker-compose deployment model.

## D10 — Audit & observability extensions (Principle V)

**Decision**: Extend `AuditEntry.action` with `dedup.run.started`, `dedup.run.completed`,
`dedup.run.failed`, `cluster.merged`, `merge.undone`, `cluster.dismissed`. Entries record
`target_type`/`target_id` (run, cluster, working_copy) and `source_ref` (e.g. the run for a cluster
action), with **redacted** `details` (counts, model_version, confidence — never payloads/secrets).
Run failures store a redacted `last_error` on the run.

**Rationale**: Satisfies FR-021/SC-006 and keeps the append-only audit trail consistent with
feature 001's `audit_service`.

---

## Summary of resolved unknowns

| Topic | Decision |
|-------|----------|
| Engine deployment | Dedicated `dedup` Spark/Zingg container; PG-backed job consumer (D1) |
| Model w/o labeling | Bundled pre-trained model; runtime runs only `match` (D2) |
| Data transport | Zingg JDBC pipes to Postgres; per-run staging tables (D3) |
| Match fields | Flatten Person → name/email/phone/org typed columns; `wcc_id` identity (D4) |
| Clusters/confidence | Group by `z_cluster` (≥2); confidence = `z_maxScore`; precision floor (D5) |
| Merge/undo | Survivor-based; soft-retire + MergeRecord; reversible for working-copy life (D6) |
| Lifecycle | one active run/working copy; supersede pending; per-run dismissals (D7) |
| Testability | `DedupEngine` seam + `FakeDedupEngine`; slow real-Zingg integration test (D8) |
| Performance | Spark local mode + blocking; ≤50k within ~30 min (D9) |
| Audit | Extend `AuditEntry` actions; redacted details (D10) |
