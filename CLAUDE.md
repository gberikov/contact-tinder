<!-- SPECKIT START -->
## Active feature: 004-google-contacts-export

Read the current implementation plan for technologies, structure, and constraints:
`specs/004-google-contacts-export/plan.md`

Supporting design artifacts:
- Spec: `specs/004-google-contacts-export/spec.md`
- Research: `specs/004-google-contacts-export/research.md`
- Data model: `specs/004-google-contacts-export/data-model.md`
- API contract: `specs/004-google-contacts-export/contracts/openapi.yaml`
- Quickstart: `specs/004-google-contacts-export/quickstart.md`

Builds on features 001 (snapshots/working copies), 002 (Zingg dedup), and 003 (swipe triage):
`specs/003-tinder-swipe-triage/plan.md`.

Stack: Python 3.12 / FastAPI + worker · PostgreSQL · Vue 3 + TS (Vite) · Biome. Feature 004 is the
**write-to-Google export** that commits the staged triage results on one **Export** screen, run as a
background job in the existing `worker`: (1) **delete** the `delete`-decided active survivors —
**reuses 003's** `DeleteBatch`/`DeletionRecord`/`delete_worker`/`PeopleWriteClient` (snapshot →
preview → explicit confirm → idempotent delete → undo); (2) **label** the Processing-Queue survivors
(not deleted) with a `Process` Google **contact group** so the operator can filter & re-check them —
NEW `LabelBatch`/`LabelAssignment` + `ContactLabel`, new `ensure_label`/`add_label_members`/
`remove_label_members` seam methods (+ CI fake), idempotent & reversible, `404→skipped_absent`. An
`ExportRun` derives both (disjoint) sets, **warns & excludes** undecided survivors, and reports
per-action results with undo. Staged edits/transliterations are **NOT** pushed (label only).
**No new OAuth scope** — `contactGroups` uses the same `…/auth/contacts` grant from 003; the existing
`account_has_write_scope` gate covers labeling. **No new container** (label batches in `run_all.py`).
Governing principles: `.specify/memory/constitution.md` (privacy, non-destructive, human-in-loop,
test-first, auditability).
<!-- SPECKIT END -->
