<!-- SPECKIT START -->
## Active feature: 003-tinder-swipe-triage

Read the current implementation plan for technologies, structure, and constraints:
`specs/003-tinder-swipe-triage/plan.md`

Supporting design artifacts:
- Spec: `specs/003-tinder-swipe-triage/spec.md`
- Research: `specs/003-tinder-swipe-triage/research.md`
- Data model: `specs/003-tinder-swipe-triage/data-model.md`
- API contract: `specs/003-tinder-swipe-triage/contracts/openapi.yaml`
- Quickstart: `specs/003-tinder-swipe-triage/quickstart.md`

Builds on feature 001 (snapshots & working copies) and feature 002 (Zingg dedup):
`specs/002-zingg-dedup/plan.md`.

Stack: Python 3.12 / FastAPI + worker · PostgreSQL · Vue 3 + TS (Vite) · Biome. Feature 003 adds a
Tinder-style **swipe triage** over the `active` post-dedup survivors of a working copy (keep / delete /
send-to-processing), a post-swipe **processing queue** (edit card + Latin→Cyrillic name transliteration,
staged & reversible), and a snapshot-protected **delete batch** committed to Google. It is the FIRST
feature that writes to Google: it extends `people_client.py` with a `PeopleWriteClient` seam
(`deleteContact`/`createContact`, CI fake) and requires the `…/auth/contacts` write scope via
incremental consent. Deletes run in the existing PG-backed `worker` (no new container).
Governing principles: `.specify/memory/constitution.md` (privacy, non-destructive, human-in-loop,
test-first, auditability).
<!-- SPECKIT END -->
