# Feature Specification: Tinder-Style Contact Swipe Triage

**Feature Branch**: `003-tinder-swipe-triage`

**Created**: 2026-06-20

**Status**: Draft

**Input**: User description: "Давайте теперь реализуем Tinder-функционал по сортировке контактов. Свайпами будет определяться: оставить контакт, удалить или дополнительно обработать (Подредактировать карточку, Перевести на кириллицу)."

## Clarifications

### Session 2026-06-20

- Q: When a contact sent to "additional processing" has been edited/transliterated in the queue, what is its terminal disposition? → A: It defaults to "keep" once processing is done (re-decidable by the user).
- Q: Which contact fields can be transliterated to Cyrillic? → A: Name fields only (given / family / display name).
- Q: How much undo / re-decide capability is required during the swipe pass? → A: Re-decide any contact at any time (full, navigable decision history).
- Q: In what order are survivors presented in the deck? → A: A stable / deterministic order (e.g. by name) so resume is predictable.

## User Scenarios & Testing *(mandatory)*

This feature adds a fast, card-based triage surface — modelled on the swipe interaction of dating
apps — that lets a person quickly decide the fate of each contact that survived the deduplication
stage. The triage runs over the **post-dedup survivors** of a working copy (the contacts that remain
after duplicate clusters from feature 002 have been merged). Each swipe records one of three
outcomes: **keep**, **delete** (queue for deletion in Google), or **send to additional processing**.
To keep the swipe rhythm fast, "additional processing" only *tags* a contact during the swipe pass;
the actual editing and Cyrillic transliteration review happen afterwards in a dedicated processing
queue, so the user never breaks momentum mid-deck.

All decisions are staged and non-destructive: nothing is written to Google during swiping. Deletions
are committed later as an explicit, snapshot-protected batch with a confirmation step, consistent with
the project's non-destructive and human-in-the-loop principles.

### User Story 1 - Rapid swipe triage of survivors (Priority: P1)

A person opens a working copy whose duplicates have already been resolved and is shown one contact
card at a time. They swipe right to **keep**, left to **delete**, or up to **send to additional
processing**. The deck advances immediately after each decision, with a running count of how many
contacts remain. The session can be paused and resumed without losing progress.

**Why this priority**: This is the core value of the feature and the smallest viable slice. Even with
only keep/delete decisions and no downstream processing, the user already gains a fast way to clean up
their address book. Everything else builds on the decisions captured here.

**Independent Test**: Load a working copy that has post-dedup survivors, swipe each card to assign an
outcome, close and reopen the session, and confirm every decision was persisted, the deck resumed at
the correct position, and no contact was written to Google.

**Acceptance Scenarios**:

1. **Given** a working copy with N post-dedup survivors and no prior triage decisions, **When** the
   user opens the triage view, **Then** the first undecided contact is shown as a card and the
   remaining-count reads N.
2. **Given** a contact card is displayed, **When** the user swipes right (keep), **Then** the contact
   is recorded as "keep", the card advances to the next undecided contact, and the remaining-count
   decreases by one.
3. **Given** a contact card is displayed, **When** the user swipes left (delete), **Then** the contact
   is recorded as "queued for deletion" (staged, not yet sent to Google) and the deck advances.
4. **Given** a contact card is displayed, **When** the user swipes up (additional processing), **Then**
   the contact is added to the processing queue with no edit interruption and the deck advances.
5. **Given** the user has decided some but not all contacts, **When** they leave and reopen the triage
   view, **Then** the session resumes at the next undecided contact with all prior decisions intact.
6. **Given** the user has decided one or more contacts, **When** they navigate back to any decided
   contact and re-decide (or undo) it, **Then** that contact's decision is updated to the new choice
   and the latest decision takes precedence.
7. **Given** every survivor in the working copy has a decision, **When** the deck is exhausted, **Then**
   the user sees a completion summary (counts of keep / delete / processing) instead of a card.

---

### User Story 2 - Post-swipe processing queue: edit & transliterate (Priority: P2)

After (or in parallel with) finishing the swipe pass, the user opens the processing queue containing
every contact they sent to "additional processing". For each item they can **edit the contact card**
(correct fields) and/or **transliterate the name to Cyrillic**. For transliteration the system
proposes a Latin→Cyrillic version of the name; the user reviews, corrects if needed, and accepts it.
All edits are staged against the working copy and are reversible.

**Why this priority**: Deferring this work to a queue is what lets the swipe stage stay fast (the
user's explicit requirement — "не терять динамику"). It delivers the "дополнительно обработать" half of
the feature but depends on US1 having captured the processing tags first.

**Independent Test**: With several contacts tagged for processing during a swipe pass, open the queue,
accept a transliteration suggestion for one, manually edit another, and confirm both changes are
staged against the working copy, are visible on re-open, and can be undone.

**Acceptance Scenarios**:

1. **Given** contacts were sent to additional processing during swiping, **When** the user opens the
   processing queue, **Then** every such contact appears as a pending item.
2. **Given** a processing item with a Latin-script name, **When** the user chooses "transliterate to
   Cyrillic", **Then** the system shows a suggested Cyrillic rendering that the user can accept or edit
   before it is staged.
3. **Given** a transliteration suggestion is shown, **When** the user accepts it, **Then** the contact's
   name is updated in the working copy (staged), the item is marked done, and the change is reversible.
4. **Given** a processing item, **When** the user chooses "edit card", **Then** an editable form of the
   contact's fields is shown and saved edits are staged against the working copy.
5. **Given** a processed (edited or transliterated) contact, **When** the user later changes their mind,
   **Then** they can revert the staged change within the retention window.

---

### User Story 3 - Review and commit the delete batch to Google (Priority: P3)

When the user is ready, they review everything they queued for deletion as a single batch. The system
shows a dry-run preview of exactly which contacts will be deleted, takes a restorable snapshot of every
affected contact, and requires an explicit confirmation before any deletion is sent to Google. After
the batch runs, the user can see the result and undo within the retention window.

**Why this priority**: This is the destructive, outward-facing action and the riskiest step, so it is
gated behind explicit review. It is lowest priority because the staged decisions from US1 already have
value (and are safe) without the batch being committed; the commit can ship after the triage surface.

**Independent Test**: Queue several contacts for deletion via swiping, open the delete-batch review,
verify the preview lists exactly those contacts, confirm a snapshot is recorded for each, execute the
batch against a non-production / mocked Google seam, and confirm the audit log and undo path.

**Acceptance Scenarios**:

1. **Given** one or more contacts queued for deletion, **When** the user opens the delete-batch review,
   **Then** a dry-run preview lists every contact that will be deleted and nothing has been sent to
   Google yet.
2. **Given** a delete-batch preview, **When** the user confirms the batch, **Then** a restorable
   snapshot of every affected contact is persisted before any deletion call is made.
3. **Given** a confirmed delete batch, **When** the deletions are executed, **Then** each deletion is
   recorded in the append-only audit log with who, what, when, the before-state reference, and the
   Google result.
4. **Given** a delete batch that fails partway through, **When** the user retries, **Then** the
   operation is idempotent and only contacts not yet deleted are attempted again.
5. **Given** a recently committed delete batch, **When** the user triggers undo within the retention
   window, **Then** the affected contacts are restored from the snapshot.

---

### Edge Cases

- **Empty deck**: working copy has no post-dedup survivors, or every survivor is already decided — the
  user sees the completion/empty state, not a blank card.
- **Resume after interruption**: a partially triaged session reopens at the correct position with all
  decisions preserved.
- **Already-Cyrillic or mixed-script name**: transliteration is offered sensibly — a name already in
  Cyrillic should not be garbled; mixed-script names surface a reviewable suggestion rather than a
  silent change.
- **Empty / missing name fields**: a contact with no usable name can still be triaged; transliteration
  is simply unavailable or a no-op for it.
- **Ambiguous romanization**: when a Latin name has more than one plausible Cyrillic rendering, the
  user is shown an editable suggestion and is never forced to accept a wrong guess.
- **Working copy changes underneath**: if the underlying working copy / dedup result changes after a
  triage session starts (e.g. dedup re-run), the user is informed rather than silently shown stale
  cards or losing decisions.
- **Contact externally removed**: a contact queued for deletion that no longer exists in Google at
  commit time is treated as already-satisfied, not an error.
- **Google quota / rate limit during commit**: the batch surfaces the throttle and remains retryable
  and idempotent.
- **Conflicting decisions**: a contact cannot be simultaneously "keep" and "queued for deletion"; the
  latest explicit decision wins and remains attributable.
- **Processing then deciding**: a contact sent to processing defaults to a terminal "keep" disposition
  once its queued work is complete; the user may re-decide it to "delete" at any time. The flow makes
  its terminal state unambiguous (never stuck in a non-terminal limbo).

## Requirements *(mandatory)*

### Functional Requirements

#### Triage session & deck

- **FR-001**: The system MUST present, for a selected working copy, only the contacts that survived the
  deduplication stage as a one-card-at-a-time swipe deck, ordered in a stable, deterministic sequence
  (e.g. by name) so the deck position is reproducible across pause/resume.
- **FR-002**: The system MUST let the user assign exactly one of three swipe outcomes to each contact:
  **keep**, **delete (queue for Google deletion)**, or **send to additional processing**. "Send to
  additional processing" is an intermediate state; once its queued work (edit / transliterate) is done,
  the contact's terminal disposition MUST default to **keep**, which the user can still re-decide.
- **FR-003**: The system MUST advance the deck to the next undecided contact immediately after a
  decision, without requiring further input.
- **FR-004**: The system MUST display ongoing progress (e.g. remaining count and/or position in deck).
- **FR-005**: The system MUST persist every decision durably so a session can be paused and resumed
  without loss, resuming at the next undecided contact.
- **FR-006**: The system MUST allow the user to revisit and re-decide ANY previously decided contact at
  any time during the session (not only the most recent), backed by a navigable decision history, with
  the latest decision taking precedence.
- **FR-007**: The system MUST show a completion summary (counts per outcome) when every survivor has a
  decision, and an explicit empty state when the deck has no contacts to triage.
- **FR-027**: The system MUST detect when a working copy's active survivors change after a triage
  session has started (e.g. a dedup re-run retires or alters contacts) and inform the user rather than
  silently presenting stale cards or losing decisions; a decision for a contact that is no longer an
  active survivor MUST be excluded from terminal actions (it is skipped, not deleted) and surfaced in
  the relevant review.

#### Non-destructive staging

- **FR-008**: The system MUST NOT write any change to Google during the swipe pass; all swipe outcomes
  are staged decisions only.
- **FR-009**: Every decision MUST be attributable to an explicit user action and recorded with the
  acting account and a timestamp.
- **FR-010**: Each user's triage data MUST be isolated to that user's own contacts; one account MUST
  never see or affect another's deck or decisions.

#### Additional-processing queue

- **FR-011**: When a contact is swiped to "additional processing", the system MUST tag it for later
  handling WITHOUT interrupting the swipe flow (no inline editor during the swipe pass).
- **FR-012**: The system MUST provide a processing queue listing all contacts tagged for additional
  processing, reviewable after the swipe pass.
- **FR-013**: For a queued contact, the system MUST allow editing the contact's card fields, staging
  the edits against the working copy.
- **FR-014**: For a queued contact, the system MUST offer transliteration from Latin to Cyrillic of the
  name fields only (given / family / display name) by presenting a suggested rendering that the user can
  accept or correct before it is staged. Non-name fields (organization, notes, addresses) are out of
  scope for transliteration.
- **FR-015**: The system MUST NOT apply a transliteration silently during swiping; the suggestion MUST
  be reviewed (accepted or edited) before it changes the contact.
- **FR-016**: Staged edits and transliterations MUST be reversible within the defined retention window.
- **FR-017**: The system MUST handle names that are empty, already Cyrillic, or mixed-script without
  corrupting data (offering a sensible suggestion or no-op rather than a garbled result).

#### Delete batch & Google commit

- **FR-018**: The system MUST collect all "queued for deletion" decisions into a reviewable batch.
- **FR-019**: The system MUST provide a dry-run preview of the delete batch listing exactly which
  contacts will be deleted, before anything is sent to Google.
- **FR-020**: The system MUST persist a restorable snapshot of every affected contact BEFORE executing
  any deletion against Google.
- **FR-021**: The system MUST require an explicit, per-batch user confirmation before deleting in
  Google; no deletion may occur without it.
- **FR-022**: Deletion execution MUST be idempotent and safe to retry after a partial failure.
- **FR-023**: The system MUST support undo of a committed delete batch within the retention window,
  restoring affected contacts from the snapshot.
- **FR-024**: A contact already absent in Google at commit time MUST be treated as already-deleted
  (success), not a failure.

#### Auditability

- **FR-025**: Every staged decision and every committed mutation (delete, edit, transliterate, restore)
  MUST be recorded in the append-only audit log capturing who, what, when, the before-state reference,
  and (for Google writes) the API result.
- **FR-026**: Logs and any diagnostic output MUST redact contact PII and secrets.

### Key Entities *(include if feature involves data)*

- **Triage Session**: A pass over the post-dedup survivors of one working copy for one account.
  Tracks status (in-progress / complete), position/progress, and links to its decisions.
- **Triage Decision**: The outcome assigned to a single contact within a session — one of keep /
  queued-for-deletion / sent-to-processing. Carries acting account, timestamp, and supersession order
  (so re-decisions are attributable). Revisitable/undoable.
- **Processing Queue Item**: A contact tagged for additional processing, with the requested action(s)
  (edit card, transliterate to Cyrillic) and a status (pending / done).
- **Transliteration Suggestion**: For a processing item, the source (Latin) name, the proposed Cyrillic
  rendering, and the user-accepted final value.
- **Staged Edit**: A reversible change to a contact's fields (from editing or accepted transliteration)
  held against the working copy until committed/synced.
- **Delete Batch**: The set of queued-for-deletion contacts reviewed and committed together, with its
  snapshot reference, status (staged / previewed / committed / undone), and result.
- **Audit Entry**: An append-only record of a decision or mutation (who, what, when, before-state
  reference, outcome) — reused from the project-wide audit log.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can triage a deck of 100 survivors in a single sitting, with the median time to
  decide one contact under 3 seconds (the swipe interaction does not block on any per-card processing).
- **SC-002**: 100% of contacts queued for deletion have a restorable snapshot recorded before any
  deletion is sent to Google — zero deletions occur without a recoverable copy.
- **SC-003**: Closing and reopening a triage session preserves 100% of prior decisions and resumes at
  the correct position (zero lost or duplicated decisions).
- **SC-004**: Any single decision and any committed delete or edit can be undone within the retention
  window, restoring the prior state.
- **SC-005**: For every contact sent to additional processing, the user can review and accept or correct
  a transliteration suggestion before it changes the contact — no transliteration is applied without
  review.
- **SC-006**: A user can drive a working copy's deck to completion (every survivor reaches a terminal
  decision) and see an accurate summary of the counts per outcome.
- **SC-007**: 100% of staged decisions and committed mutations produce an audit entry, and no audit
  entry or log contains unredacted PII or secrets.

## Assumptions

- The feature builds directly on feature 001 (snapshots & working copies) and feature 002 (Zingg
  dedup); the swipe deck consumes the **survivors of the dedup stage** within a working copy, and the
  snapshot/undo and Google-write seams established by those features are reused rather than rebuilt.
- "Delete" means queuing the contact for deletion in **Google Contacts**, executed only via the
  guarded, snapshot-protected, explicitly confirmed batch flow (Constitution: Non-Destructive by
  Default).
- During the swipe pass the "additional processing" outcome only tags contacts; the edit and
  transliteration review happen afterwards in the processing queue, to preserve swipe momentum (per the
  user's explicit "не терять динамику" requirement).
- Transliteration direction is Latin → Cyrillic, applied to name fields only (given / family / display
  name); the exact romanization scheme is deferred to planning. Transliteration is always a reviewable
  suggestion, never an automatic silent change.
- The undo "retention window" is the **lifetime of the working copy** — undo for staged edits and for
  committed deletes stays available for as long as the working copy (and its `StagedEdit` /
  `DeletionRecord` rows) exists, with no timed expiry. This matches feature 002's merge-undo choice and
  introduces no new expiry mechanism. ("Retention window" elsewhere in this spec refers to this.)
- A contact reaches a single terminal disposition (keep or delete) per working copy; "send to
  processing" is an intermediate state that resolves to a terminal disposition, defaulting to "keep"
  once its queued work is complete (re-decidable by the user).
- Single-tenant, self-hosted deployment supporting multiple Google accounts belonging to the operator,
  consistent with the existing stack and constitution.
