# Feature Specification: Google People API Snapshots & Working Copies

**Feature Branch**: `001-people-api-snapshots`

**Created**: 2026-06-20

**Status**: Draft

**Input**: User description: "Давай сначала создадим интерфейс к Google People API с возможностью выгрузить в базу данных, сделать резервную копию, некий слепок, и чтобы это было видно в UI. Хочу обратить внимание, что слепок это read-only, из которого потом делается рабочая копия. Слепок нужен для того чтобы к нему можно было вернуться в случае чего. Таких слепков может быть несколько. Это будут снапшоты. Рабочие копии будут из этих снапшотов формироваться."

## Clarifications

### Session 2026-06-20

- Q: Which Google contact set should a snapshot capture? → A: Personal contacts only
  (personal connections); "Other contacts" and directory entries excluded.
- Q: What maximum address-book size must a single snapshot reliably handle? → A: Up to ~50,000
  contacts, imported as a resumable background job with visible progress.
- Q: Must v1 support connecting multiple Google accounts at once? → A: Yes, multiple accounts in
  v1 with per-account data isolation.
- Q: Can the operator delete snapshots in v1? → A: Yes, via explicit confirmation, blocked while
  the snapshot still has working copies.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Connect a Google account and capture a snapshot (Priority: P1)

The operator connects a Google account (read-only authorization) and imports all of that
account's contacts into a new, immutable snapshot stored inside the application. The snapshot
is a faithful point-in-time backup that can be returned to later.

**Why this priority**: This is the foundation of the entire product. Without a safe,
immutable backup of the source contacts, no later feature (deduplication, keep/delete triage)
can be trusted, because there would be no guaranteed way to recover the original data. It is
independently valuable as a "back up my Google Contacts" capability on its own.

**Independent Test**: Connect a test Google account, trigger a snapshot, and verify the
resulting snapshot contains every contact from the account with correct counts and metadata —
delivering a usable backup with no other feature present.

**Acceptance Scenarios**:

1. **Given** no Google account is connected, **When** the operator authorizes a Google account
   with read-only contacts access, **Then** the account appears as connected and ready.
2. **Given** a connected Google account, **When** the operator starts "create snapshot",
   **Then** all contacts are imported and stored as a new read-only snapshot recording the
   source account, creation time, and contact count.
3. **Given** an import that is interrupted or fails partway, **When** the operator checks the
   snapshot list, **Then** no partial or corrupt snapshot is presented as usable.
4. **Given** an existing snapshot for an account, **When** the operator creates another
   snapshot for the same account later, **Then** both snapshots are retained independently.

---

### User Story 2 - View snapshots and their contents in the UI (Priority: P2)

The operator sees every snapshot in the UI with its metadata and can open a snapshot to browse
the captured contacts in read-only mode.

**Why this priority**: A backup the operator cannot see or verify is not trustworthy. Surfacing
snapshots and their contents lets the operator confirm a capture succeeded and decide which
snapshot to work from. It builds directly on US1 and is required before working copies are
meaningful.

**Independent Test**: With at least one snapshot present, open the snapshots view and confirm
the list shows account, date, and contact count, and that opening a snapshot lists its contacts
without any editing affordance.

**Acceptance Scenarios**:

1. **Given** one or more snapshots exist, **When** the operator opens the snapshots view,
   **Then** each snapshot shows its source account, creation timestamp, contact count, and the
   number of working copies derived from it.
2. **Given** a snapshot, **When** the operator opens it, **Then** they can browse the contained
   contacts but have no way to edit them (read-only).
3. **Given** multiple snapshots, **When** the operator views the list, **Then** snapshots are
   ordered so the most recent capture is easy to identify.

---

### User Story 3 - Create a working copy from a snapshot (Priority: P3)

The operator creates an editable working copy from a chosen snapshot. Later features operate on
the working copy; the originating snapshot is never altered, so the operator can always return
to it or spawn another working copy.

**Why this priority**: This establishes the snapshot → working-copy relationship the rest of the
product depends on, while keeping the backup immutable. It is lower priority than capture and
viewing because those two already deliver a verifiable backup; working copies enable the *next*
features rather than this one.

**Independent Test**: From an existing snapshot, create a working copy and verify it contains
the same contacts, is marked editable, and that the source snapshot is unchanged and can still
produce additional working copies.

**Acceptance Scenarios**:

1. **Given** a snapshot, **When** the operator creates a working copy, **Then** a new editable
   copy is created containing the same contacts, and the snapshot remains unchanged.
2. **Given** a snapshot that already has a working copy, **When** the operator creates a second
   working copy, **Then** both working copies exist independently from the same snapshot.
3. **Given** a working copy, **When** it is changed (by later features), **Then** the source
   snapshot and any sibling working copies are unaffected.

---

### Edge Cases

- A connected account with zero contacts produces a valid snapshot containing zero contacts.
- A very large address book (tens of thousands of contacts) imports completely, with progress
  visible to the operator, and is only finalized when the full import succeeds.
- Google rate limits or quota exhaustion during import cause back-off and resumption without
  producing a corrupt snapshot.
- A Google token that has expired or been revoked prompts re-authorization and never leaves a
  partially written snapshot behind.
- Attempting to start a second snapshot for the same account while one is already in progress is
  prevented or queued, never resulting in two conflicting in-progress imports.
- Two snapshots that happen to contain identical contact data are still retained as separate,
  independent snapshots.
- Attempting to delete a snapshot that still has working copies is blocked, with a clear
  explanation; the snapshot and its working copies remain intact.
- Deleting a snapshot that has no working copies succeeds only after explicit confirmation and is
  recorded in the audit log.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow the operator to connect one or more Google accounts via Google
  authorization, requesting read-only access to contacts only (narrowest scope needed).
- **FR-002**: System MUST store Google credentials and tokens securely (encrypted at rest) and
  MUST NOT expose them in the UI, logs, or any export.
- **FR-003**: System MUST import all of a connected account's **personal contacts** (personal
  connections) via the Google People API into a new snapshot. "Other contacts" (auto-saved) and
  organization directory entries are excluded.
- **FR-004**: System MUST capture the standard contact fields the People API provides (names,
  phone numbers, email addresses, postal addresses, organizations, notes, and group/label
  memberships), preserving the data faithfully.
- **FR-005**: System MUST treat each snapshot as immutable and read-only once finalized; it MUST
  NOT modify a finalized snapshot's contents under any circumstances.
- **FR-006**: System MUST support multiple snapshots, including multiple snapshots captured from
  the same account at different times, retained independently.
- **FR-007**: System MUST record snapshot metadata: source account, creation timestamp, contact
  count, and import status.
- **FR-008**: System MUST finalize a snapshot only when its import completes successfully; an
  interrupted or failed import MUST NOT produce a usable snapshot.
- **FR-009**: System MUST allow the operator to view a list of all snapshots with their metadata
  in the UI.
- **FR-010**: System MUST allow the operator to browse the contacts contained in a snapshot in
  read-only mode, with no affordance to edit snapshot data.
- **FR-011**: System MUST allow the operator to create a working copy from any snapshot.
- **FR-012**: System MUST ensure working copies are independent and editable, and that changes to
  a working copy never affect its source snapshot or any other working copy.
- **FR-013**: System MUST support creating multiple working copies, including more than one
  derived from the same snapshot.
- **FR-014**: System MUST display, for each snapshot, how many working copies have been derived
  from it.
- **FR-015**: System MUST surface import progress and final completion or failure status to the
  operator.
- **FR-016**: System MUST handle Google People API pagination, rate limiting, and transient
  errors during import without corrupting or partially finalizing a snapshot. The import MUST run
  as a resumable background job that can recover and continue after a transient failure.
- **FR-017**: When a Google token is expired or revoked, the system MUST prompt the operator to
  re-authorize and MUST NOT create a partial snapshot.
- **FR-018**: System MUST keep each operator/account's data isolated, so contacts from one
  account are never shown under, or merged into, a snapshot of a different account.
- **FR-019**: System MUST record an audit entry when a snapshot is created and when a working
  copy is created (capturing what, when, and the source).
- **FR-020**: System MUST support snapshots of up to at least 50,000 personal contacts, reporting
  progress during import and completing without data loss at that scale.
- **FR-021**: System MUST allow the operator to delete a snapshot only via an explicit
  confirmation step.
- **FR-022**: System MUST block deletion of a snapshot while one or more working copies derived
  from it still exist, informing the operator why the deletion is blocked.
- **FR-023**: System MUST record an audit entry when a snapshot is deleted (capturing what and
  when).

### Key Entities *(include if feature involves data)*

- **Google Account Connection**: a Google account the operator has authorized with read-only
  contacts access. Attributes: account identifier (email), connection/authorization status,
  granted scope. References securely stored credentials (never exposed).
- **Snapshot**: an immutable, point-in-time capture of one account's contacts. Attributes:
  identifier, source account, creation timestamp, contact count, import status
  (in progress / complete / failed), read-only flag. The product's restorable backup.
- **Snapshot Contact**: a single contact as captured within a snapshot, holding the captured
  standard contact fields. Immutable for the life of the snapshot.
- **Working Copy**: an editable derivative created from exactly one snapshot. Attributes:
  identifier, source snapshot reference, creation timestamp, label, editable contact set.
  Independent of the snapshot and of sibling working copies.
- **Working Copy Contact**: an editable contact within a working copy, initially copied from the
  source snapshot.
- **Audit Entry**: an append-only record of a snapshot or working-copy creation event,
  capturing what happened, when, and the source it derived from.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can connect a Google account and create their first snapshot in under
  5 minutes for an address book of up to 5,000 contacts.
- **SC-002**: 100% of contacts present in the Google account at capture time appear in the
  resulting snapshot — no contacts are lost or silently dropped.
- **SC-003**: A snapshot's contents are stable for its entire lifetime: reopening a snapshot at
  any later time shows exactly the same data captured at creation (zero drift).
- **SC-004**: Creating a working copy reproduces 100% of the source snapshot's contacts and
  leaves the snapshot unchanged, verified by comparing counts and contents before and after.
- **SC-005**: From the UI alone, an operator can identify every snapshot together with its
  source account, capture date, and contact count, without needing any external tool.
- **SC-006**: After an interrupted or failed import, zero incomplete snapshots are presented to
  the operator as usable.
- **SC-007**: An operator can maintain multiple snapshots over time and return to any earlier
  snapshot to create a fresh working copy at any point, with no earlier snapshot becoming
  inaccessible.
- **SC-008**: A snapshot of up to 50,000 personal contacts completes successfully with visible
  progress and zero contact loss, and resumes correctly after a transient interruption.
- **SC-009**: An operator can connect at least two Google accounts and view each account's
  snapshots without any account's contacts appearing under another account.

## Assumptions

- Deployment is self-hosted for a single operator who connects multiple of their own Google
  accounts; supporting multiple connected accounts is a v1 requirement, with per-account data
  isolation (per the project constitution's deployment model).
- This feature is strictly read-only with respect to Google: it never writes back to or deletes
  Google contacts. Applying changes back to Google is a future feature.
- Deduplication, keep/delete triage, and merging are out of scope here; this feature provides the
  data foundation (snapshots and working copies) those features will build on.
- "Contacts" means the operator's personal contacts (connections). "Other contacts" and
  organization directory entries are out of scope for this feature.
- Contact photos are captured as references/metadata as provided by the People API; downloading
  and storing binary image data is out of scope for v1.
- Operator-initiated snapshot deletion is in scope for v1 (explicit confirmation; blocked while
  working copies exist). Automatic retention policies (age/count-based auto-deletion) remain out
  of scope until a dedicated retention feature is added.
- Only read-only contacts authorization is requested at this stage, consistent with the
  constitution's "narrowest scope" principle.

## Dependencies

- Requires a Google Cloud project with an OAuth client configured for the People API with
  read-only contacts scope.
- Requires the operator to grant authorization to each Google account before its contacts can be
  captured.
