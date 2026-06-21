# Feature Specification: Validate & Normalize (Tidy step)

**Feature Branch**: `006-validate-normalize`

**Created**: 2026-06-21

**Status**: Draft

**Input**: User description: "Давай добавим еще один шаг после review. Этот шаг для нормализации и
валидации данных. Что он должен делать? 0. Проверять валидность телефонных номеров. Если телефон не
валидный то карточку с контактом надо добавить в список для ревью. 1. Нормализовать написание
телефонных номеров согласно стандарту e.164 (LibPhoneNumber). 2. Прописать тип телефонного номера,
если он не указан (work, mobile). Не все карточки можно автоматически прогнать на тип — нужен список
для ручной нормализации. 3. Валидировать адреса электронной почты (по возможности — домены; цель:
жива почта или нет). 4. Валидировать адреса сайтов (http→https, существует сайт или нет)."

## Overview

The pipeline today ends at **Review** (swipe keep/delete) and then **Export** pushes the surviving
contacts back to Google. Nothing currently checks or cleans the *content* of those contacts — phone
numbers keep whatever formatting they were imported with, missing phone types stay missing, and dead
email domains or stale `http://` websites flow straight to Google untouched.

This feature inserts one new wizard step, **Tidy**, between **Review** and **Export**. Tidy runs a
one-pass **validation & normalization** over the contacts that survived Review (those *not* marked
for deletion) and splits its findings into two buckets:

1. **Auto-applied, unambiguous fixes** — reformat valid phone numbers to E.164, upgrade `http://`
   websites to `https://` when the secure version is confirmed reachable, and set a phone's type to
   *mobile* when the number is confidently a mobile line. Each fix is a **reversible staged edit**
   against the Draft (never the frozen Backup), so everything is undoable and audited.
2. **A manual-doctoring queue** — anything uncertain or broken is *not* changed automatically; it is
   added to a per-run queue the operator works through: invalid phone numbers, phones whose type
   can't be inferred, email addresses whose domain can't receive mail, and websites that don't
   respond.

The step is **passable**: the queue is advisory. The operator may proceed to Export with items still
open (mirroring the existing "undecided survivors" warning pattern), so Tidy never becomes a hard gate.

Because phone normalization needs a phone-number library and email/website validation make real
network lookups (DNS MX records, outbound HTTP requests), this feature **deliberately adds backend
work** — new dependencies, a database migration, a background worker, and read/write endpoints. This
is a knowing, scoped exception to the otherwise frontend-only redesign (feature 005), in the same
spirit as the 005 addendum that added Draft deletion. All new mutations remain reversible staged
edits, so the constitution's non-destructive and human-in-the-loop principles hold.

The new wizard becomes a **seven-step** flow:

| # | Label   | Plain meaning                                   |
|---|---------|-------------------------------------------------|
| 1 | Connect | Link your Google account                        |
| 2 | Backup  | Pull a frozen copy of your contacts             |
| 3 | Draft   | Your editable copy of the contacts              |
| 4 | Merge   | Find & merge duplicates                         |
| 5 | Review  | Swipe to keep or delete                         |
| 6 | **Tidy**| **Clean up & check phones, emails, websites**   |
| 7 | Export  | Push your changes back to Google                |

## Clarifications

### Session 2026-06-21

- Q: How aggressively should the step apply normalizations (E.164 phone reformat, http→https)? → A:
  **Auto-apply the unambiguous fixes** (reformat a valid phone to E.164; upgrade http→https only when
  the https version is confirmed reachable) as reversible staged edits; everything ambiguous or
  broken (invalid phone, unclear type, dead email domain, dead website) goes to a **manual-doctoring
  queue** instead of being changed.
- Q: At what depth should email be validated? → A: **Syntax + the domain's MX record** (does the
  domain accept mail at all), via a DNS lookup. This catches typos (`gmial.com`) and dead domains.
  Confirming a *specific mailbox* is alive via an SMTP probe is **out of scope** — it is unreliable
  (accept-all / catch-all domains) and risks the sender IP being blacklisted.
- Q: How should websites be validated? → A: **Full reachability check + http→https.** Make a bounded,
  time-limited HTTP request following redirects; if the final reachable URL is https while the stored
  value is http, propose/apply the upgrade; if nothing responds, queue it as a dead website.
- Q: When a phone has no type, how should it be set automatically? → A: **Only set "mobile" when the
  number library confidently classifies it as a mobile line.** Fixed-line and ambiguous numbers
  (which could be work or home) go to the manual queue rather than being guessed.
- Q: Which contacts get validated and normalized? → A: **Only the contacts that survived Review**
  (kept, i.e. not marked for deletion) — the set that will actually be exported. No effort is spent
  validating contacts that are about to be deleted.
- Q: How is the default region for parsing national-format phone numbers (those without a `+`
  country code) determined? → A: It is a **configurable setting**, whose initial default is
  **auto-detected from the operator's IP geolocation**. The currently-active region MUST be
  **visibly surfaced (highlighted)** in the Tidy UI so the operator notices which country numbers are
  being interpreted as, and can change it. Numbers already in `+` international form are parsed by
  their own country code regardless of this setting.
- Q: What counts as a website being "reachable" (and therefore when is an http→https upgrade
  applied)? → A: A server response counts as reachable when it is present and serving — 2xx/3xx and
  "present but blocked" codes (401/403/429). **Refinement (operator request): `404`/`410` ("page not
  found / gone") and `5xx` ("server error") are flagged for review with the specific HTTP code**, not
  treated as healthy. Transport-level failures — DNS not resolving, connection refused, TLS handshake
  failure, or timeout — are flagged with their specific cause. An http→https upgrade applies when the
  `https://` request returns a healthy response.
- Q: How are website checks protected against SSRF (a contact URL pointing at an internal/private
  address)? → A: Tidy MUST **refuse to make requests to non-public targets** — loopback, RFC1918
  private ranges, link-local (incl. the cloud-metadata address `169.254.169.254`), and unique-local
  IPv6 — including after redirects. Such a website is **not fetched**; it is queued as *can't safely
  check* and left unchanged, never auto-modified.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Auto-clean the obvious things in one pass (Priority: P1)

After reviewing contacts, the operator reaches **Tidy**, starts the check, and the app automatically
fixes everything it can do safely — phone numbers get a single consistent E.164 format, secure
website URLs replace insecure ones where the secure site really exists, and obviously-mobile numbers
get a *mobile* type. The operator sees a clear summary of what was changed and what still needs a
human, and can undo any automatic change.

**Why this priority**: The automatic pass is the core value — it removes the bulk of formatting
inconsistency with zero per-contact effort while staying fully reversible. With only this (auto-fix +
summary + undo), the operator already exports cleaner data.

**Independent Test**: Take a Draft whose kept contacts include badly-formatted but valid phones and
`http://` sites that have working `https://` versions, run Tidy, and confirm the phones are rewritten
to E.164, the websites are upgraded, the summary counts the changes, and each change can be undone
back to its original value.

**Acceptance Scenarios**:

1. **Given** a kept contact with a valid phone written as `+7 (701) 722-15-02`, **When** Tidy runs,
   **Then** the stored value becomes its E.164 form `+77017221502` as a reversible staged edit, and
   the change is reflected in the run summary.
2. **Given** a kept contact whose website is `http://example.kz` and whose `https://example.kz`
   responds successfully, **When** Tidy runs, **Then** the value is upgraded to `https://example.kz`
   as a reversible staged edit.
3. **Given** a kept contact with a typeless phone the library classifies as mobile, **When** Tidy
   runs, **Then** the phone's type is set to *mobile* automatically.
4. **Given** any automatically-applied fix, **When** the operator undoes it, **Then** the field
   returns to its exact pre-Tidy value and the audit trail records both the edit and its undo.

---

### User Story 2 - Work a queue of things only a human can decide (Priority: P1)

For everything the app can't safely auto-fix — a phone that isn't a valid number, a phone whose type
is unclear, an email whose domain can't receive mail, a website that doesn't respond — the operator
gets a focused queue. Each item shows the contact, the field, what's wrong, and a small set of
explicit actions (set the right type, edit the value, or remove the bad field), so the operator
resolves them one at a time.

**Why this priority**: The auto-pass (US1) is worthless if broken data silently ships; the manual
queue is how uncertain findings get a human decision instead of a bad guess. Together US1+US2 are the
MVP of the step.

**Independent Test**: Build a Draft whose kept contacts include an unparseable phone, a fixed-line
phone with no type, a `mail@gmial.com` address, and a website that never responds; run Tidy; confirm
each appears as one queue item with the correct issue reason and the expected resolution controls,
and that resolving an item applies a reversible edit and removes it from the queue.

**Acceptance Scenarios**:

1. **Given** a kept contact whose phone cannot be parsed as a valid number, **When** Tidy runs,
   **Then** that contact appears in the manual queue marked *invalid phone*, and the phone is left
   unchanged until the operator acts.
2. **Given** a typeless phone the library does **not** confidently classify as mobile, **When** Tidy
   runs, **Then** it appears in the queue as *unclear type* offering an explicit type choice
   (e.g. mobile / work / home), and selecting one applies it as a reversible staged edit.
3. **Given** an email whose domain has no MX record (e.g. `mail@gmial.com`), **When** Tidy runs,
   **Then** it appears in the queue as *email domain can't receive mail* with actions to edit or
   remove the address.
4. **Given** a syntactically invalid email (e.g. `bob@@example` or `not-an-email`), **When** Tidy
   runs, **Then** it appears in the queue as *invalid email* (distinct from the dead-domain case) with
   actions to edit or remove the address, and is **not** auto-changed.
5. **Given** a website that does not respond within the time limit, **When** Tidy runs, **Then** it
   appears in the queue as *website not reachable* with actions to edit or remove it, and is **not**
   auto-changed.
6. **Given** any queue item, **When** the operator resolves or skips it, **Then** it leaves the
   pending queue, any chosen edit is applied reversibly, and the run's counts update.

---

### User Story 3 - Tidy fits the wizard like every other step (Priority: P2)

The operator experiences Tidy as a normal seventh step in the same stepper: it shows a running state
while the background check executes, lets them navigate away and come back, restores its state on
reload, and can be passed through — with a clear warning — even if some queue items remain open.

**Why this priority**: Consistency with the existing wizard (feature 005) is what makes the step feel
predictable; it depends on the functional work in US1/US2 but is required for the step to belong in
the flow rather than feel bolted on.

**Independent Test**: Start Tidy, navigate to another step while it runs and confirm the stepper keeps
showing Tidy *running*; reload mid-flow and confirm the wizard returns to Tidy with its run and queue
intact; with items still open, advance to Export and confirm a clear warning is shown rather than a
hard block.

**Acceptance Scenarios**:

1. **Given** the active Draft has kept contacts, **When** the operator opens Tidy and starts the
   check, **Then** the stepper shows Tidy in the **running** state and the operator may navigate to
   other available steps while it runs.
2. **Given** a Tidy run has finished, **When** the operator reloads or returns later, **Then** the
   wizard restores Tidy with its summary and the current pending queue rather than restarting it.
3. **Given** open items remain in the queue, **When** the operator chooses to continue to Export,
   **Then** a clear warning states how many items are still unresolved, and proceeding is an explicit
   confirmed action (the step is passable, not a hard gate).
4. **Given** the Tidy background job fails, **When** it ends, **Then** the step surfaces a visible
   error and offers to retry, consistent with the other long-running steps.

---

### Edge Cases

- **Nothing to clean**: All kept contacts are already valid and normalized → Tidy renders a clear
  "nothing to fix" empty state, records a finished run with zero changes and an empty queue, and is
  passable.
- **Contact with multiple phones/emails/websites**: Each field value is validated independently; one
  contact may contribute several auto-fixes and several queue items across different fields.
- **A field is both reformattable and typeless**: A valid phone with no type is reformatted to E.164
  (auto) *and*, if its type can't be confidently inferred, also raised as an *unclear type* queue
  item — the two findings are independent.
- **http with no working https**: If `https://` is not reachable but `http://` is, the value is left
  as-is (no downgrade, no false upgrade) and, if even http is unreachable, it is queued as a dead
  website.
- **Slow / bot-blocked websites**: Outbound checks are time-limited and bounded in concurrency. A
  site that returns a blocking response (e.g. 403/429) still counts as *reachable* (the server
  answered) and is left as-is; only a site that times out or fails at the transport level (DNS/
  connection/TLS) is queued as *not reachable*. Either way the run never crashes or hangs, and the
  operator can still keep a queued site manually.
- **Website pointing at an internal address**: A contact URL that resolves to a non-public address
  (loopback, private, link-local/metadata, IPv6 unique-local) — including via a redirect — is never
  fetched; it is queued as *can't safely check* and left unchanged, so the validator can't be used to
  probe internal infrastructure (SSRF).
- **Changing an upstream selection**: Switching the active Draft (or re-running Merge/Review)
  re-derives Tidy's state for that branch and does not destroy a previous branch's Tidy run or queue.
- **Re-running Tidy**: Starting a fresh Tidy run re-checks the current kept set; already-applied
  staged edits are not duplicated, and prior unresolved decisions are not silently lost.
- **Deletion still pending**: Contacts marked for deletion in Review are excluded from Tidy entirely,
  so no effort or network request is spent on data that won't be exported.

## Requirements *(mandatory)*

### Functional Requirements

**Step placement & wizard integration**

- **FR-001**: The wizard MUST present a new step, **Tidy**, positioned between **Review** and
  **Export**, making the stepper a seven-step flow (Connect, Backup, Draft, Merge, Review, Tidy,
  Export).
- **FR-002**: Tidy MUST reuse the existing stepper states and behaviors defined for feature 005 —
  completed / current / upcoming / **running** — including showing the running state while its
  background check executes and allowing navigation to other available steps meanwhile.
- **FR-003**: Tidy MUST restore its state (latest run, summary, and pending queue) on page reload and
  return visits for the active Draft rather than restarting the check.
- **FR-004**: Tidy MUST be **passable**: the operator MUST be able to advance to Export while queue
  items remain open, via an explicit confirmed action, with a clear warning of how many items are
  unresolved (consistent with the existing undecided-survivors warning).
- **FR-005**: Tidy MUST surface a visible error and offer a retry if its background job fails,
  consistent with the other long-running steps (Backup, Merge, Export).

**Scope of validation**

- **FR-006**: Tidy MUST validate and normalize only the contacts in the active Draft that survived
  Review (kept / not marked for deletion); contacts marked for deletion MUST be excluded.
- **FR-007**: Tidy MUST validate each phone, email, and website value on a contact independently, so
  a single contact may yield multiple auto-fixes and multiple queue items.

**Phone numbers**

- **FR-008**: Tidy MUST validate every phone number on a kept contact; a number that cannot be parsed
  as a valid phone number MUST be added to the manual queue as *invalid phone* and left unchanged.
- **FR-009**: Tidy MUST normalize every *valid* phone number to a consistent **human-readable
  international** representation (e.g. `+7 (701) 722-15-02` → `+7 701 722 1502`) as a reversible staged
  edit, applied only when the normalized value differs from the stored value. An internal/extension
  number — whether marked (`ext`, `доб`, `#`, …) or a trailing digit group with no marker (e.g.
  `+7 727 262 32 73 3230`) — MUST be preserved in the formatted value (e.g. `… ext. 3230`).
- **FR-010**: When a kept contact's phone has no type, Tidy MUST set the type to *mobile*
  automatically **only** when the number is confidently classified as a mobile line; otherwise it
  MUST add an *unclear type* item to the manual queue offering an explicit type choice, and MUST NOT
  guess the type.
- **FR-028**: The default region used to parse national-format phone numbers (those without a `+`
  country code) MUST be a configurable setting. Its initial value MUST be auto-detected from the
  operator's IP geolocation, and the currently-active region MUST be visibly surfaced in the Tidy UI
  (e.g. a highlighted country indicator the operator can change). Phone numbers already in `+`
  international form MUST be parsed by their own country code regardless of this setting.

**Email addresses**

- **FR-011**: Tidy MUST validate every email address on a kept contact for syntactic correctness and
  for whether its domain can receive mail (the domain has an MX record), via a DNS lookup.
- **FR-012**: An email that is syntactically invalid or whose domain cannot receive mail MUST be added
  to the manual queue with the corresponding reason, offering actions to edit or remove the address;
  Tidy MUST NOT auto-edit or auto-remove email values.
- **FR-013**: Tidy MUST NOT perform SMTP mailbox-existence probing; confirming a specific mailbox is
  alive is explicitly out of scope.

**Websites**

- **FR-014**: Tidy MUST check every website URL on a kept contact for reachability using a
  time-limited HTTP request that follows redirects, with bounded concurrency across the run. A URL is
  *reachable* when the server returns **any** HTTP response (2xx/3xx/4xx/5xx); only transport-level
  failures — DNS resolution failure, connection refused/unreachable, TLS handshake failure, or
  timeout — count as *not reachable*.
- **FR-015**: Tidy MUST normalize a reachable website value to its canonical form as a reversible
  staged edit: (a) if the value has **no scheme** (e.g. `www.dk-studio.kz`), add one; (b) prefer
  `https://` whenever the https version is reachable (its TLS handshake completes and it returns any
  HTTP response). It MUST NOT downgrade https→http, MUST NOT use an https URL that is not reachable,
  and MUST stage no edit when the canonical value already equals the stored value. A scheme-less value
  whose host is reachable is therefore auto-corrected (scheme added), not queued as invalid.
- **FR-016**: A website that is *not reachable* (a transport-level failure per FR-014) MUST be added
  to the manual queue as *not reachable* and left unchanged; Tidy MUST NOT auto-remove website values.
- **FR-029**: Website checks MUST guard against SSRF: Tidy MUST NOT issue a request to a non-public
  target — loopback, RFC1918 private ranges, link-local (including the cloud-metadata address
  `169.254.169.254`), or IPv6 unique-local — and MUST re-apply this guard on every redirect hop. A
  website resolving to such a target MUST NOT be fetched; it MUST be queued as *can't safely check*
  and left unchanged.

**Manual-doctoring queue**

- **FR-017**: Tidy MUST maintain, per run, a queue of items requiring human attention; each item MUST
  identify the contact, the specific field/value, and the issue reason (invalid phone, unclear type,
  invalid email, email domain can't receive mail, website not reachable, website can't safely check).
- **FR-018**: Each queue item MUST offer explicit, clearly-labeled resolution actions appropriate to
  its issue (e.g. choose a phone type, edit the value, or remove the field), and resolving an item
  MUST apply any chosen change as a reversible staged edit and remove the item from the pending queue.
- **FR-019**: The operator MUST be able to skip a queue item (leave the value as-is) without applying
  any change; skipped items leave the pending queue but their values are unchanged.
- **FR-020**: Tidy MUST present a summary of each run: how many fixes were auto-applied, how many
  items are queued for manual attention, and how many values were checked.

**Safety, reversibility & auditability**

- **FR-021**: Every change Tidy makes — automatic or via queue resolution — MUST be a reversible
  staged edit against the **Draft** only; the frozen Backup/snapshot MUST never be modified.
- **FR-022**: The operator MUST be able to undo any Tidy change (automatic or manual) and have the
  field return to its exact pre-change value.
- **FR-023**: Every Tidy change and undo MUST be recorded in the existing audit trail with enough
  detail to see what field changed, from what value, to what value, and why.
- **FR-024**: Tidy MUST NOT push any change directly to Google; its edits stay staged on the Draft and
  reach Google only through the existing Export step and its existing safeguards.
- **FR-025**: *(Umbrella — reaffirms FR-014's time/concurrency limits and FR-029's SSRF guard; not
  separate work.)* Outbound validation requests (DNS and HTTP) MUST be limited to the domains/URLs
  already present in the operator's own kept contacts, MUST be time-limited and concurrency-bounded,
  MUST NOT target non-public addresses (FR-029), and MUST NOT transmit contact data anywhere beyond
  the lookups required to validate those values.

**Terminology & UX (consistent with feature 005)**

- **FR-026**: Tidy MUST use plain language for its labels, headings, buttons, empty states, and
  confirmations, consistent with the simple/clear/predictable principles of feature 005, and MUST not
  reintroduce the term "working copy" (the editable copy is the **Draft**).
- **FR-027**: Every state-changing action in Tidy (start check, resolve item, skip item, undo,
  continue-with-open-items) MUST be triggered by an explicit labeled control and MUST produce
  immediate visible feedback (in-progress, success, or error).

### Key Entities *(include if feature involves data)*

- **Tidy run (validation run)**: One execution of the validation & normalization pass over a Draft's
  kept contacts. Has a status (pending / running / done / failed), the counts surfaced in its summary
  (auto-applied fixes, queued items, values checked), and timestamps. Scoped to one active Draft;
  re-runnable.
- **Queue item (validation item)**: One finding that needs a human decision. Identifies the contact,
  the field kind (phone / email / website), the specific value, the issue reason (invalid phone /
  unclear type / invalid email / email domain can't receive mail / website not reachable / website
  can't safely check), an optional suggested value, and a status (pending / resolved / skipped).
- **Staged edit (existing)**: The reversible before/after change record already used by the Draft for
  edits and transliterations (feature 003). Tidy's auto-fixes and queue resolutions are recorded as
  staged edits of a normalization kind, inheriting undo and audit for free; no new edit concept is
  introduced.
- **Kept contact set**: The contacts in the active Draft not marked for deletion in Review — the sole
  input to a Tidy run.
- **Default phone region setting**: The operator-configurable country used to parse national-format
  phone numbers. Initialized from IP geolocation, persisted, editable in settings, and surfaced
  (highlighted) in the Tidy UI. Affects only numbers lacking a `+` country code.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a Tidy run, 100% of kept contacts' phone numbers **deemed valid for the active
  parsing region** (FR-028) are stored in a consistent human-readable international format. (Numbers
  invalid for the active region are queued, not normalized.)
- **SC-002**: Zero contacts are auto-modified for findings the system is not confident about — every
  invalid phone, unclear-type phone, bad-domain email, and unreachable website is queued, not silently
  changed.
- **SC-003**: 100% of Tidy changes (automatic and manual) are reversible to their exact original
  value via undo, and 100% appear in the audit trail.
- **SC-004**: An `http://` website whose `https://` version is reachable is upgraded to https in 100%
  of cases; an http site with no reachable https version is upgraded in 0% of cases (no false
  upgrades, no downgrades).
- **SC-005**: Emails whose domain has no MX record are flagged for review in 100% of cases, and no
  email is auto-edited or auto-removed.
- **SC-006**: The Tidy step is passable: an operator can reach Export with open queue items in 100% of
  attempts, always after an explicit warning of how many remain.
- **SC-007**: The frozen Backup/snapshot is modified in 0% of Tidy runs; all changes land only on the
  Draft.
- **SC-008**: A website reachability check never hangs the run: every outbound check resolves within
  its time limit, and the run completes (or fails visibly) regardless of slow or blocking sites.
- **SC-009**: An operator can identify, for any queue item, what is wrong and what their options are
  within 10 seconds, from the item's on-screen reason and labeled actions alone.
- **SC-010**: Website checks issue zero outbound requests to non-public addresses (loopback, private,
  link-local/metadata, IPv6 unique-local), including across redirects; 100% of such URLs are queued as
  *can't safely check* instead.

## Assumptions

- **New backend work is in scope (knowing exception)**: Unlike feature 005 (frontend-only), Tidy adds
  backend dependencies (a phone-number library; DNS MX lookup; outbound HTTP for website checks), a
  database migration for the run and queue entities, a background worker, and read/write endpoints.
  This is an intentional, scoped exception in the spirit of the 005 deletion addendum, kept within the
  constitution because every mutation is a reversible staged edit on the Draft.
- **Reuse of existing mechanisms**: Tidy's auto-fixes and queue resolutions reuse the existing Draft
  staged-edit/undo/audit mechanism (feature 003) and the existing background-job + running-state
  pattern (features 002/004/005) rather than inventing new ones.
- **Phone normalization standard**: Valid numbers are normalized to **E.164**; the implementation uses
  a libphonenumber-equivalent library. The default region for parsing national-format numbers is a
  configurable setting (FR-028), initialized from the operator's IP geolocation and visibly surfaced
  so the operator can correct it; `+`-prefixed numbers parse by their own country code regardless.
  Resolving the geolocation lookup mechanism (service vs. bundled database) is a planning detail.
- **Email depth**: Validation is **syntax + domain MX record** only; SMTP mailbox probing is
  excluded as unreliable (accept-all/catch-all domains) and operationally risky (sender-IP
  blacklisting). "Is this exact mailbox alive" is therefore not guaranteed — only "this domain can
  receive mail."
- **Website depth**: Reachability is a best-effort, time-limited HTTP check; sites that block
  automated requests or respond slowly may produce false "not reachable" results, which is why such
  findings are *queued for a human* rather than auto-removed.
- **Phone type semantics**: Only *mobile* is inferable from a number; *work* vs *home* is a human
  judgment and is therefore always offered as a manual choice, never guessed.
- **Single-operator, own data**: Outbound DNS/HTTP lookups target only domains and URLs already
  present in the operator's own contacts; no third party is contacted beyond what validating those
  values requires. Because contact URLs can originate from third parties (synced from Google),
  website checks still apply an SSRF guard (FR-029) against non-public targets.
- **Localized UI copy**: User-facing labels follow the existing app's language conventions; the issue
  reasons and actions above are described in English in this spec but rendered in the app's UI
  language during implementation.
