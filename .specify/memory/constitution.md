<!--
SYNC IMPACT REPORT
==================
Version change: 1.0.1 → 1.1.0
Bump rationale: MINOR — new mandatory tooling obligation added: Biome as the single
                linter/formatter for the frontend, plus a CI quality gate enforcing it.
                Materially expanded mandatory guidance (new obligation), so MINOR not PATCH.

Prior versions:
  - 1.0.1 (PATCH — frontend framework constraint swapped React → Vue 3).
  - 1.0.0 (initial ratification — placeholders resolved into concrete principles/governance).

Modified principles: N/A (Technology Constraints + Quality Gates only)
Added sections:
  - Core Principles I–V (Privacy & Data Protection; Non-Destructive by Default;
    Human-in-the-Loop; Test-First; Auditability & Observability)
  - Technology Constraints
  - Development Workflow & Quality Gates
  - Governance
Removed sections: none

Templates reviewed:
  ✅ .specify/templates/plan-template.md  — Constitution Check gate is dynamic ("Gates
       determined based on constitution file"); no hardcoded principle names. No edit required.
  ✅ .specify/templates/spec-template.md  — generic; no principle coupling. No edit required.
  ✅ .specify/templates/tasks-template.md — generic; no principle coupling. No edit required.
  ✅ .specify/templates/checklist-template.md — generic. No edit required.

Deferred TODOs: none
-->

# Contact Tinder Constitution

A self-hosted web application for cleaning up Google Contacts via the Google People API:
deduplication (powered by Zingg), a swipe-style "keep / delete" triage flow, and detailed
manual resolution of ambiguous cases.

## Core Principles

### I. Privacy & Data Protection (NON-NEGOTIABLE)

Contact data and Google OAuth credentials are sensitive personal information and MUST be
treated as such at every layer.

- OAuth refresh/access tokens MUST be encrypted at rest; they MUST NEVER be logged, returned
  in API responses, or committed to the repository.
- The application MUST request the narrowest Google OAuth scopes that satisfy a feature
  (read scopes by default; write/delete scopes only where a feature provably needs them).
- Contact data MUST NOT be sent to any third party not required to deliver a feature. The
  Zingg/Spark pipeline runs inside the self-hosted boundary; no contact PII leaves it.
- Each user's data MUST be isolated; one account MUST never read or mutate another's contacts.
- Secrets MUST be supplied via environment/secret store, never hard-coded.

**Rationale:** A contact-cleanup tool concentrates an entire address book plus standing
account access. A single leak is high-impact and irreversible for the user's network.

### II. Non-Destructive by Default (NON-NEGOTIABLE)

Deletion in Google Contacts is the headline destructive action of this app and MUST be made
safe and reversible.

- No contact MUST be deleted in Google without explicit, per-batch user confirmation.
- Before any delete batch is pushed to Google, the app MUST persist a restorable snapshot
  (full contact payload) of every affected contact.
- Merges and deletes MUST support an undo path for a defined retention window; "delete" in
  the UI means staged/soft-deleted until the user commits the batch.
- A dry-run preview MUST be available for any operation that writes to Google.
- Destructive operations MUST be idempotent and safe to retry after partial failure.

**Rationale:** Users trust the tool with their address book precisely because mistakes can be
walked back. Irreversible bulk deletion would make the product unusable for its purpose.

### III. Human-in-the-Loop Decisions

Automation proposes; the human disposes. The app accelerates judgment, it does not replace it.

- Zingg produces match candidates and confidence scores; it MUST NOT auto-merge or auto-delete
  without human review of each cluster (above a configurable confidence threshold, batch
  approval is allowed, but never silent application).
- Every "keep / delete / merge" decision MUST be attributable to an explicit user action.
- Ambiguous duplicate clusters MUST be routed to the detailed manual-resolution flow rather
  than resolved by a default heuristic.

**Rationale:** Identity resolution is probabilistic. The product's value is a fast, trustworthy
review surface over Zingg's suggestions — not unattended automation that silently loses data.

### IV. Test-First (NON-NEGOTIABLE)

TDD is mandatory for all behavior with correctness or safety implications.

- Tests MUST be written and MUST fail before implementation (Red → Green → Refactor).
- Deduplication logic, merge/keep/delete decision rules, snapshot/undo, and Google People API
  adapters MUST have automated tests covering success and failure paths.
- Google People API and Zingg/Spark MUST be exercised behind seams that allow contract/
  integration tests without mutating real Google data in CI.

**Rationale:** Safety guarantees (II) and correctness of dedup (III) are only real if they are
verified mechanically and continuously, not asserted by hand.

### V. Auditability & Observability

Every change to a user's contacts MUST be reconstructable after the fact.

- Each mutation (merge, delete, edit, restore) MUST be recorded in an append-only audit log
  capturing who, what, when, the before-state reference, and the Google API result.
- Logs and metrics MUST be structured; PII and secrets MUST be redacted from them.
- Google People API interactions MUST surface rate-limit/quota handling and be traceable to
  the user action that triggered them.

**Rationale:** When a user asks "what happened to this contact?", the system must answer
precisely — both to support undo (II) and to retain trust.

## Technology Constraints

The stack is fixed by two hard external dependencies — the Google People API and Zingg
(Apache Spark / JVM) — and the chosen self-hosted, container-based deployment.

- **Deployment:** Self-hosted, containerized (docker-compose), single-tenant per deployment
  but supporting multiple Google accounts belonging to the operator.
- **Backend:** Python 3.12+ with FastAPI. Google access via `google-api-python-client` /
  Google OAuth libraries.
- **Deduplication:** Zingg via its Python API running on Apache Spark. Spark/Zingg is treated
  as a batch engine invoked by the backend; contact data stays inside the deployment boundary.
- **Frontend:** Vue 3 + TypeScript (Vite), featuring a Tinder-style swipe surface for triage
  and a detailed view for manual cluster resolution.
- **Linting/formatting:** Biome is the single linter and formatter for the TypeScript/Vue
  frontend codebase. Its checks MUST pass in CI; adding a competing linter/formatter (e.g.
  ESLint/Prettier) for the same files requires an amendment.
- **Persistence:** PostgreSQL for application state, audit log, snapshots, and staged
  decisions. OAuth tokens stored encrypted at rest.
- Introducing a new core technology (language, datastore, or dedup engine) is a constitutional
  change and MUST follow the amendment process below.

## Development Workflow & Quality Gates

- Every feature follows the Spec Kit flow: `/speckit.specify` → `/speckit.plan` →
  `/speckit.tasks` → `/speckit.implement`, with `/speckit.analyze` before implementation.
- The Constitution Check in `plan-template.md` MUST pass (or record justified, approved
  exceptions in Complexity Tracking) before implementation begins.
- No code touching Google writes, token handling, deletion, or dedup decisions merges without:
  passing tests (IV), an audit-log entry path (V), and a reviewer sign-off on Principles I–II.
- CI MUST run the automated test suite; tests MUST NOT call the live Google API against real
  user data.
- CI MUST run Biome (lint + format check) on the frontend codebase; a failing Biome check
  blocks merge.

## Governance

- This constitution supersedes other process conventions for the Contact Tinder project.
  Where a practice conflicts with a principle here, the principle wins.
- **Amendments** require: a written rationale, an explicit version bump per the policy below,
  update of any affected templates/docs in the same change, and approval by the project owner.
- **Versioning policy (semantic):**
  - **MAJOR** — removal or backward-incompatible redefinition of a principle or governance rule.
  - **MINOR** — a new principle/section, or materially expanded mandatory guidance.
  - **PATCH** — clarifications and wording that do not change obligations.
- **Compliance review:** Plans and PRs MUST verify compliance with the principles above.
  Complexity or deviation MUST be justified in writing; unjustified violations block merge.
- Runtime/agent guidance lives in the repository's agent context file (e.g. `CLAUDE.md`) and
  MUST stay consistent with this constitution.

**Version**: 1.1.0 | **Ratified**: 2026-06-20 | **Last Amended**: 2026-06-20
