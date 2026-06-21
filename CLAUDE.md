<!-- SPECKIT START -->
## Active feature: 006-validate-normalize

Read the current implementation plan for technologies, structure, and constraints:
`specs/006-validate-normalize/plan.md`

Supporting design artifacts:
- Spec: `specs/006-validate-normalize/spec.md`
- Research: `specs/006-validate-normalize/research.md`
- Data model: `specs/006-validate-normalize/data-model.md`
- HTTP contract: `specs/006-validate-normalize/contracts/validation-api.md`
- Quickstart: `specs/006-validate-normalize/quickstart.md`

Builds on features 001–005 (snapshots/drafts, Zingg dedup, swipe triage, Google export, guided wizard).

Stack: Python 3.12 / FastAPI + worker · PostgreSQL · Vue 3 + TS (Vite) · Biome. Feature 006 adds a
**seventh wizard step, Tidy**, between **Review** and **Export**, that validates & normalizes the
active Draft's **kept** contacts. A background **ValidationRun** (combined worker, `FOR UPDATE SKIP
LOCKED`) **auto-applies** unambiguous fixes as reversible **StagedEdits** on the Draft — phone →
E.164, confident-mobile type, `http→https` when the https site is reachable — and **queues**
everything uncertain/broken as **ValidationItem** rows (invalid phone, unclear type, invalid email,
dead email domain via MX, unreachable website, SSRF-unsafe website) for explicit human resolution.
Libraries: `phonenumbers` (E.164 + type), `email-validator`/`dnspython` (syntax + MX; **no SMTP
probe**), `httpx` (reachability = any HTTP response; transport failure = queue) with a **per-redirect
SSRF guard** rejecting non-public IPs. Email depth = syntax + MX only. Default phone region is a
client-side setting (localStorage), initialized via `GET /settings/detect-region` (local GeoLite2 or
browser-locale fallback) and **highlighted** in the UI. The step shows a **running** state and is
**passable with a warning**. One migration (`0005_validate_normalize` → `validation_run`,
`validation_item`); `StagedEdit.kind` widened to include `normalize` (no DDL). Reuses StagedEdit/undo/
audit (003) and the running-state pattern (002/004/005); **no Google push, no new OAuth scope** —
edits reach Google only via the unchanged Export step. This **knowingly extends beyond 005's
frontend-only scope** (new Python deps + migration + worker + router), a scoped exception like the
005 deletion addendum — adding libraries is **not** a constitutional amendment (no new core
technology). Governing principles: `.specify/memory/constitution.md` (privacy, non-destructive,
human-in-loop, test-first, auditability). **Biome stays the single frontend linter/formatter**; CI
Biome + `vue-tsc` gates stay authoritative.
<!-- SPECKIT END -->
