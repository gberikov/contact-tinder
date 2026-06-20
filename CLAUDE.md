<!-- SPECKIT START -->
## Active feature: 002-zingg-dedup

Read the current implementation plan for technologies, structure, and constraints:
`specs/002-zingg-dedup/plan.md`

Supporting design artifacts:
- Spec: `specs/002-zingg-dedup/spec.md`
- Research: `specs/002-zingg-dedup/research.md`
- Data model: `specs/002-zingg-dedup/data-model.md`
- API contract: `specs/002-zingg-dedup/contracts/openapi.yaml`
- Quickstart: `specs/002-zingg-dedup/quickstart.md`

Builds on feature 001 (snapshots & working copies): `specs/001-people-api-snapshots/plan.md`.

Stack: Python 3.12 / FastAPI + worker · PostgreSQL · Vue 3 + TS (Vite) · Biome. Feature 002 adds a
dedicated `dedup` container (Apache Spark + Zingg, JVM, bundled pre-trained model) that runs the
`match` phase over a working copy via Postgres JDBC; the backend talks to it through a `DedupEngine`
seam (CI uses a Spark-free `FakeDedupEngine`).
Governing principles: `.specify/memory/constitution.md` (privacy, non-destructive, human-in-loop,
test-first, auditability).
<!-- SPECKIT END -->
