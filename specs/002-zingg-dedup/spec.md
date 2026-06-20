# Feature Specification: Working-Copy Deduplication with Zingg

**Feature Branch**: `002-zingg-dedup`

**Created**: 2026-06-20

**Status**: Draft

**Input**: User description: "Теперь давай реализуем дедубликацию рабочей копии контактов с помощью zingg"

## Clarifications

### Session 2026-06-20

- Q: How far should this feature go once duplicates are identified in a working copy? → A:
  Detect + merge **within the working copy** — surface clusters with confidence, and let the
  operator confirm a cluster to merge its contacts into one (field-level, reversible). The source
  snapshot is never touched and nothing is pushed to Google (a later feature).
- Q: How does the operator get a working matching model in v1? → A: Ship a **pre-configured**
  contacts model (field mapping + bundled/seed model) so deduplication runs out-of-the-box with
  **no operator labeling step**. Interactive labeling/refinement is out of scope for v1.
- Q: When a dismissed cluster ("not a duplicate") could be re-detected on a later run, is the
  dismissal remembered? → A: **Per-run only** — a dismissal applies within its own run; a new run
  re-detects and re-presents the pair as a fresh cluster to review again (no cross-run suppression).
- Q: What is the identity of the merged contact relative to the cluster's members? → A:
  **Survivor-based** — one member is designated the surviving contact (keeps its origin link/
  identity), absorbs chosen fields from the others, and the other members are retired.
- Q: What completion-time target should a full dedup run on ~50,000 contacts meet? → A:
  **Within ~30 minutes** for a 50k-contact working copy on modest self-hosted hardware.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Find duplicates in a working copy (Priority: P1)

The operator picks an existing working copy and starts a deduplication run. The system analyses
the working copy's contacts and produces groups ("clusters") of contacts that appear to be the
same person, each with a confidence score. The run reads the working copy without changing any
contact.

**Why this priority**: Detection is the irreducible core of the feature — without trustworthy
duplicate clusters there is nothing to review or merge. It is independently valuable: even with
no review UI, producing an accurate, counted list of suspected duplicate groups already tells the
operator how messy an address book is and proves the matching engine works on real data.

**Independent Test**: On a working copy seeded with known duplicate pairs, trigger a dedup run and
verify it completes, reports a cluster count, and groups the known duplicates together — while the
working copy's contacts and the source snapshot remain byte-for-byte unchanged.

**Acceptance Scenarios**:

1. **Given** a ready working copy, **When** the operator starts "Find duplicates", **Then** a
   dedup run is created, its progress is visible, and on completion it reports how many duplicate
   clusters were found.
2. **Given** a working copy containing obvious duplicates (e.g. "John Smith" and "Jon Smith" with
   the same phone), **When** a dedup run completes, **Then** those contacts appear together in one
   cluster with a confidence score.
3. **Given** a working copy with no duplicates, **When** a dedup run completes, **Then** it
   reports zero clusters and the working copy is unchanged.
4. **Given** a dedup run that fails partway (engine/resource error), **When** the operator checks
   the run, **Then** it is shown as failed with no partial clusters presented as actionable, and
   the working copy is unchanged.
5. **Given** a completed dedup run, **When** the operator inspects the source snapshot and the
   working copy contacts, **Then** neither has been modified by the run.

---

### User Story 2 - Review duplicate clusters (Priority: P2)

The operator opens a completed dedup run and reviews each suspected duplicate cluster: the member
contacts shown side by side with their distinguishing fields and the cluster's confidence score,
ordered so the most confident matches are easy to act on first.

**Why this priority**: Detection is only useful if a human can quickly judge it. A clear review
surface turns raw clusters into decisions and is the prerequisite for any safe merge. It builds
directly on US1 and delivers value on its own as a "show me my likely duplicates" view.

**Independent Test**: With a completed run present, open the review surface and confirm each
cluster lists its member contacts with key fields and a confidence score, sorted by confidence,
without any cluster being changed by merely viewing it.

**Acceptance Scenarios**:

1. **Given** a completed dedup run with clusters, **When** the operator opens it, **Then** each
   cluster shows its member contacts with names and key distinguishing fields (emails, phones) and
   a confidence score.
2. **Given** multiple clusters, **When** the operator views the run, **Then** clusters are ordered
   by confidence so the strongest matches surface first.
3. **Given** a cluster, **When** the operator inspects a member, **Then** they can see enough of
   that contact's details to decide whether the grouping is correct, in read-only form.
4. **Given** clusters of varying confidence, **When** the operator filters or sorts by confidence,
   **Then** low-confidence groups can be set aside without acting on them.

---

### User Story 3 - Resolve a cluster: merge or dismiss (Priority: P3)

For each cluster, the operator decides: **merge** the contacts into a single contact inside the
working copy, or **dismiss** the cluster as "not a duplicate". On merge, the system produces one
combined contact (proposing a merged set of fields the operator can adjust) and retires the other
members within the working copy. Every merge is reversible and never touches the source snapshot.

**Why this priority**: This is where the cleanup actually happens, but it depends on trustworthy
detection (US1) and a review surface (US2). Keeping it as a separate, reversible, per-cluster
action satisfies the human-in-the-loop and non-destructive guarantees.

**Independent Test**: From a reviewed cluster, merge its members and verify the working copy now
holds a single combined contact retaining the union of important fields, the merged-away members
are no longer presented as active, the action is recorded, and an undo restores the pre-merge
state — all with the source snapshot unchanged.

**Acceptance Scenarios**:

1. **Given** a cluster under review, **When** the operator chooses "Merge", **Then** the system
   presents a proposed combined contact (non-conflicting fields unioned; a default chosen for any
   conflicting single-value field) that the operator can adjust before confirming.
2. **Given** a proposed merge, **When** the operator confirms it, **Then** the working copy
   contains one combined contact, the other members are retired from the active set, and the
   cluster is marked resolved/merged.
3. **Given** a cluster the operator judges incorrect, **When** they choose "Not a duplicate",
   **Then** the cluster is dismissed and its members remain separate, active contacts.
4. **Given** a completed merge, **When** the operator undoes it (available for the life of the working
   copy), **Then** the original member contacts are restored exactly and the combined contact is removed.
5. **Given** any merge or dismiss action, **When** it completes, **Then** an audit entry records
   what was merged/dismissed, when, and by which action, and the source snapshot is unchanged.
6. **Given** several high-confidence clusters, **When** the operator approves them as a batch,
   **Then** each is merged using its proposed combination, but no cluster is ever merged without an
   explicit operator action (no silent/auto merges).

---

### Edge Cases

- **Concurrent runs**: starting a second dedup run on a working copy that already has one in
  progress is prevented (or queued); two runs never write conflicting cluster sets for the same
  copy at the same time.
- **Stale clusters after edits**: if the working copy changes (a merge, or edits from another
  feature) after a run completes, previously found clusters may no longer be valid. Acting on a
  cluster whose members no longer exist (already merged/removed) is blocked with a clear message,
  and the operator can re-run to refresh results; a newer run supersedes an older one's unresolved
  clusters.
- **Cluster of size one / singletons**: contacts with no match are simply not placed in any
  cluster; they are never altered.
- **Large clusters**: a single cluster may contain more than two members (e.g. three records of
  the same person); merge combines all members into one.
- **Conflicting field values on merge**: when members disagree on a single-value field (e.g. two
  different "primary" phones), the operator is shown the conflict and the proposed default, and can
  choose the value to keep before confirming.
- **Empty / tiny working copy**: running dedup on a working copy with zero or one contact completes
  immediately with zero clusters.
- **Failed/cancelled run**: a failed or cancelled run leaves no actionable clusters and no changes
  to the working copy; the operator can retry.
- **All members dismissed/merged**: once every cluster in a run is resolved, the run is shown as
  fully reviewed.

## Requirements *(mandatory)*

### Functional Requirements

#### Running deduplication

- **FR-001**: The system MUST let the operator start a deduplication run over a selected, ready
  working copy.
- **FR-002**: The system MUST run deduplication using a pre-configured contacts matching model
  (field mapping plus a bundled/seed model), requiring no operator labeling or training step in v1.
- **FR-003**: A deduplication run MUST read the working copy's contacts without modifying any
  contact, and MUST NOT read or modify any other working copy, any snapshot, or any other account's
  data.
- **FR-004**: The system MUST match on the standard contact fields available in a contact record
  (at minimum names, email addresses, and phone numbers) to identify likely-same-person records.
- **FR-005**: The system MUST group matched contacts into clusters, where each cluster is a set of
  two or more working-copy contacts believed to represent the same person, and MUST attach a
  confidence score to each cluster.
- **FR-006**: The system MUST surface run progress and a terminal state (completed or failed) to
  the operator, and MUST finalize a run's clusters only when the run completes successfully.
- **FR-007**: The system MUST prevent two concurrent in-progress runs from producing conflicting
  cluster sets for the same working copy (e.g. by blocking or queuing a second run).
- **FR-008**: The system MUST let the operator re-run deduplication on a working copy; a newer
  completed run supersedes the unresolved clusters of an older run for that copy.
- **FR-009**: The system MUST support working copies of up to at least 50,000 contacts, completing
  a run and reporting clusters without operator intervention during the run.

#### Reviewing clusters

- **FR-010**: The system MUST let the operator view the clusters of a completed run, showing each
  cluster's member contacts with key distinguishing fields and the cluster's confidence score.
- **FR-011**: The system MUST order clusters by confidence so the strongest matches are presented
  first, and MUST let the operator sort/filter by confidence to set aside low-confidence groups.
- **FR-012**: The system MUST let the operator inspect an individual cluster member's contact
  details in read-only form to judge whether the grouping is correct.
- **FR-013**: Viewing or browsing clusters MUST NOT change any cluster, contact, working copy, or
  snapshot.

#### Resolving clusters (merge / dismiss)

- **FR-014**: The system MUST let the operator resolve each cluster by either merging its members
  into a single contact within the working copy, or dismissing it as "not a duplicate".
- **FR-015**: On merge, the system MUST designate one member as the surviving contact (defaulting
  to the most complete member, overridable by the operator) and present a proposed combined contact
  that unions non-conflicting field values into the survivor and chooses a default for conflicting
  single-value fields, and MUST let the operator adjust the result before confirming.
- **FR-016**: On a confirmed merge, the system MUST produce exactly one combined contact — the
  surviving member, which retains its original-contact link/identity — and retire the other members
  from the working copy's active set, MUST mark the cluster as merged, and MUST NOT alter the source
  snapshot or any other working copy.
- **FR-017**: The system MUST NOT merge or otherwise apply any cluster automatically; every merge
  and every dismiss MUST result from an explicit operator action. Batch approval of multiple
  clusters is permitted only as an explicit operator action, never as silent/background
  application.
- **FR-018**: Every merge MUST be reversible for as long as its merge record exists (indefinitely in
  v1 — no time-based expiry); an undo MUST restore the cluster's original member contacts exactly and
  remove the combined contact, leaving the working copy as it was before the merge.
- **FR-019**: Dismissing a cluster MUST leave its members as separate, active contacts and MUST
  record the dismissal so the cluster is not re-presented as unresolved within the same run. A
  dismissal applies to its own run only: a later run MAY re-detect and re-present the same pair as a
  fresh cluster (no cross-run suppression of dismissed pairs).
- **FR-020**: Acting on a cluster whose members no longer exist in the working copy (already
  merged or removed) MUST be blocked with a clear explanation rather than producing an
  inconsistent result.

#### Auditability & isolation

- **FR-021**: The system MUST record an audit entry for each deduplication run (start, and
  terminal completion/failure with cluster count) and for each merge, undo-merge, and dismiss
  action, capturing what was affected and when, without recording any secret or token.
- **FR-022**: The system MUST keep deduplication results isolated per working copy and per account,
  so one operator/account can never see or act on another's clusters or contacts.
- **FR-023**: Contact data processed during a run MUST remain inside the self-hosted deployment
  boundary; no contact information is sent to any external third party as part of deduplication.

### Key Entities *(include if feature involves data)*

- **Dedup Run**: one execution of deduplication over a single working copy. Records which working
  copy it analysed, the matching-model version used, its status (running / completed / failed), the
  number of clusters found, and start/finish times. Multiple runs may exist per working copy; the
  most recent completed run is the active result.
- **Duplicate Cluster**: a group of two or more working-copy contacts believed to be the same
  person, belonging to one dedup run. Has a confidence score and a resolution status
  (pending / merged / dismissed / superseded).
- **Cluster Member**: the association between a duplicate cluster and one working-copy contact it
  contains; may carry a per-member match indication. Members reference existing working-copy
  contacts and never the snapshot.
- **Merge Record**: the reversible record of a confirmed merge — which member was the survivor, the
  retired members' original state (enough to restore them on undo), the surviving contact's
  pre-merge state, plus the time and the resolved cluster it came from.
- **Audit Entry** *(existing)*: extended with deduplication actions (run started/finished, cluster
  merged, merge undone, cluster dismissed); append-only, secret-free.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a seeded working copy with known duplicate pairs, a single dedup run groups at
  least 90% of the known true duplicate pairs into the same cluster.
- **SC-002**: A dedup run over a working copy of up to 50,000 contacts completes and presents
  reviewable clusters within ~30 minutes on modest self-hosted hardware, without operator
  intervention during the run.
- **SC-003**: 100% of merges are reversible: after any sequence of merges and undos, undoing all of
  them returns the working copy to its exact pre-deduplication contact set.
- **SC-004**: The source snapshot is unchanged by deduplication in 100% of cases — a snapshot
  compared before and after any run, merge, dismiss, or undo is byte-for-byte identical.
- **SC-005**: Zero clusters are ever merged or dismissed without an explicit operator action (no
  silent/automatic application), verified across the test suite.
- **SC-006**: 100% of dedup runs, merges, undos, and dismissals produce a corresponding audit
  entry that contains no secrets or tokens.
- **SC-007**: For a typical two-member cluster, the operator can go from opening the cluster to a
  confirmed resolution (merge or dismiss) in under 15 seconds of interaction. (UX-interaction target;
  validated structurally by the resolve flow being a single confirmation — open → one merge/dismiss
  action — rather than by wall-clock timing.)

## Assumptions

- **Working copies exist**: this feature builds on feature 001 (snapshots & working copies). It
  operates only on an existing, ready working copy; creating snapshots/working copies is out of
  scope here.
- **Scope of matching**: deduplication looks for duplicates only *within a single working copy*,
  not across working copies, across snapshots, or across accounts.
- **Pre-configured model**: v1 ships a fixed, bundled contacts matching model; matching quality is
  fixed for v1. Interactive labeling and model refinement are deferred to a later feature.
- **Confidence threshold**: there is a configurable minimum confidence below which candidate groups
  are not presented as clusters; the default is chosen to favour precision (fewer false duplicates)
  over recall, and every presented cluster still requires explicit human resolution.
- **Merge conflict default**: when members disagree on a single-value field, the proposed default
  is taken from the most complete / highest-confidence member, and the operator may override it
  before confirming.
- **Local-only result**: merges and dismissals affect only the working copy's local state. Pushing
  any change to Google (deletes/merges in the real address book) is explicitly out of scope and
  belongs to a later feature.
- **Retention window**: because merges are local working-copy state with no Google writes, a merge
  remains **undoable indefinitely in v1** — for as long as its merge record (and the working copy)
  exists. No time-based expiry is enforced in v1; a later Google-push feature will define its own
  commit/retention semantics. (Resolved 2026-06-20; see research D6.)
- **Single operator**: the deployment is single-operator (multiple Google accounts, one operator),
  so "explicit user action" maps to that operator.

## Out of Scope

- Pushing merges or deletions to Google (modifying the real Google address book).
- The Tinder-style keep/delete swipe triage flow (a separate feature).
- Interactive Zingg labeling/training and model refinement UI.
- Cross-working-copy or cross-snapshot deduplication, and automatic (unattended) merging.
- Editing arbitrary contact fields outside the merge-resolution flow.

## Dependencies

- Feature 001 (Google People API snapshots & working copies): provides the working copies and
  their editable contacts this feature deduplicates, plus the audit log this feature extends.
- The bundled deduplication engine and matching model run inside the self-hosted deployment
  boundary (per the project's privacy constraints).
