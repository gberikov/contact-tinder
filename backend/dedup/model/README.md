# Bundled Zingg contacts model (feature 002)

**Canonical doc** for how the deduplication matching model is built and used. `quickstart.md` and
the repo root `README.md` link here — do not duplicate the procedure elsewhere (avoids drift).

## What lives here

The pre-trained Zingg model directory (`<dedup_model_id>/`, default model id `100`). At runtime the
`dedup` container runs **only** the Zingg `match` phase against this model — there is **no operator
labeling step** (spec clarification 2026-06-20: pre-configured model).

The `dedup` container is built **FROM the official `zingg/zingg` image** (Spark + JVM + Zingg jars +
`zingg` Python API). Train the model with the SAME Zingg version as that base image so the saved
model format matches at `match` time — pin both to one version (e.g. `zingg/zingg:0.6.0`).

## Schema the model expects

Matches `contact_flatten.flatten_contact` / `dedup/field_defs.py`:

| Column | MatchType | Notes |
|--------|-----------|-------|
| `wcc_id` | `DONT_USE` | working-copy contact id (identity only) |
| `first_name` | `FUZZY` | |
| `last_name` | `FUZZY` | |
| `full_name` | `FUZZY` | |
| `email` | `EMAIL` | |
| `phone` | `FUZZY` | normalised digits |
| `organization` | `FUZZY` | |

## How the model was trained (one-time, offline — NOT at runtime)

1. Assemble a representative/synthetic contacts training set with known duplicate / non-duplicate
   pairs.
2. Run Zingg `findTrainingData` → `label` (or import the curated labels) to mark pairs.
3. Run the `train` phase with the field definitions above; Zingg writes the model under
   `zinggDir/<modelId>`.
4. Commit that model directory here as `<modelId>/`. Record the `dedup_model_version` (config) so
   each `DedupRun` is reproducible.

Only `train` needs labels; `match` reuses the saved model with no retraining (one model per schema).

## Reference performance baseline (SC-002)

A ~50,000-contact working copy completes a `match` run within ~30 min on **4 vCPU / 8 GB RAM**,
Spark local mode, driver memory 4 GB, `numPartitions=8`, Zingg blocking enabled.
