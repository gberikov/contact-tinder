# Phase 0 Research: Validate & Normalize (Tidy)

Decisions resolving the Technical-Context choices for the Tidy step. Format per decision:
**Decision · Rationale · Alternatives considered**.

## D1 — Phone parsing, validity, E.164, and type

**Decision**: Use **`phonenumbers`** (the maintained Python port of Google's libphonenumber).
- Validity: `phonenumbers.is_valid_number(parse(value, region))` → invalid ⇒ queue *invalid_phone*.
- Normalization: `format_number(num, PhoneNumberFormat.E164)` ⇒ E.164; stage a `normalize` StagedEdit
  only when the result differs from the stored string (FR-009).
- Type: `phonenumbers.number_type(num)`. Auto-set type **only** when it is `PhoneNumberType.MOBILE`
  → set Google type `mobile` (FR-010). `FIXED_LINE`, `FIXED_LINE_OR_MOBILE`, and anything else with a
  missing type ⇒ queue *unclear_type* (operator picks mobile/work/home/other).

**Rationale**: libphonenumber is the de-facto standard the spec named; `phonenumbers` mirrors its API
exactly, is offline, and gives validity + E.164 + type in one parse. `FIXED_LINE_OR_MOBILE` is treated
as *not confidently mobile* so we never mislabel a landline.

**Alternatives**: hand-rolled regex (rejected — can't reliably validate or classify across regions);
`phonenumberslite` (rejected — drops the metadata needed for `number_type`).

## D2 — Default region for national-format numbers

**Decision**: Parsing region is a **per-run `default_region`** (ISO-3166 alpha-2) passed from the
frontend, which holds it as a client-side setting (localStorage), shows it **highlighted** in the
Tidy UI, and lets the operator change it (FR-028). Numbers in `+E.164` form ignore the region
(libphonenumber derives their country). The backend persists the region used on `validation_run` and
keeps an env fallback `phone_default_region` (default `KZ`) for safety when none is supplied.

**Rationale**: Mirrors the 005 client-side-selection pattern (no new settings table), keeps the
region visible and correctable exactly as the operator requested, and records what was used for
auditability. KZ fallback matches the operator's locale (the spec's `+7 70x` examples are KZ mobiles).

**Alternatives**: a server-side `app_setting` table (rejected — heavier than needed for one operator;
client persistence already established in 005); a single hard-coded region (rejected — fails for
mixed-country address books and isn't correctable).

## D3 — Initial region detection (the IP-geolocation requirement)

**Decision**: Layered detection behind a `GET /api/settings/detect-region` endpoint:
1. If the request's client IP is **public**, resolve it against a **local GeoLite2-Country** database
   (`geoip2`, optional `geoip_db_path`) → country.
2. If the client IP is **private/loopback/LAN** (the common self-hosted case) **or** no GeoLite2 DB is
   configured, return `null`; the frontend then falls back to the browser's region from
   `navigator.language` (e.g. `ru-KZ` → `KZ`), with `Intl.DateTimeFormat().resolvedOptions().timeZone`
   as a secondary hint.
The detected value is only the **initial default**, shown highlighted and overridable (FR-028).

**Rationale**: Honors "default from IP" for real remote deployments while staying correct for local
deployments (where the server only sees a private client IP). A **local** GeoLite2 DB avoids sending
the operator's IP to a third-party geo API, satisfying Principle I (no PII to third parties).

**Alternatives**: external IP-geo HTTP API (rejected by default — third-party PII + availability/
privacy concern; may be added later behind an explicit setting); browser-only detection (kept as the
fallback, not the primary, to respect the explicit "by IP" request when a public IP exists).

## D4 — Email validation depth

**Decision**: Use **`email-validator`**: `validate_email(addr, check_deliverability=True)` performs
syntax normalization **and** a DNS **MX** lookup (via `dnspython`). Syntax failure ⇒ queue
*invalid_email*; `EmailUndeliverableError` (no MX / dead domain) ⇒ queue *dead_email_domain*. No
auto-edit/auto-remove of email values (FR-012). **No SMTP probing** (FR-013).

**Rationale**: One library covers both required levels; its deliverability check is exactly the
"domain can receive mail" signal we want and nothing riskier. Matches the clarified scope.

**Alternatives**: split `email_validator` for syntax + raw `dnspython` MX query (rejected — redundant,
`email-validator` already wraps `dnspython`); SMTP `RCPT` probe (explicitly rejected — unreliable on
accept-all/catch-all domains and risks sender-IP blacklisting).

## D5 — Website reachability + http→https

**Decision**: Use **`httpx`** with `website_check_timeout_seconds` (default 5s) and **manual** redirect
following (auto-redirect disabled) capped at `website_check_max_redirects` (default 5).
- *Reachable* = the server returns **any** HTTP response (2xx/3xx/4xx/5xx) (FR-014).
- *Not reachable* = a transport-level failure: DNS failure, connection refused/unreachable, TLS
  handshake failure, or timeout ⇒ queue *website_unreachable* (FR-016).
- http→https upgrade: when the stored URL is `http://`, probe its `https://` equivalent; if that
  request completes its TLS handshake and returns any HTTP response, stage a `normalize` StagedEdit to
  the https URL (FR-015). Never downgrade; never upgrade to an unreachable https URL.

**Rationale**: "Any response = alive" minimizes false-dead on antibot 403/429 and soft-404s (the
clarified choice A); manual redirect control is required so the SSRF guard (D6) can run on **every**
hop rather than being bypassed by httpx's internal redirect handling.

**Alternatives**: `requests` (rejected — no first-class async; httpx is already a dep and gives a sync
*and* async client); auto-redirect with a transport hook (rejected — per-hop SSRF validation is
clearer with an explicit loop); HEAD-only (rejected — many servers mishandle HEAD; a GET with a small
read and short timeout is more reliable).

## D6 — SSRF guard

**Decision**: Before every HTTP connection (initial URL and each redirect target), resolve the host
via `socket.getaddrinfo` and **reject** if **any** resolved address is non-public —
`ipaddress.ip_address(...)` with `is_private | is_loopback | is_link_local | is_reserved |
is_unspecified`, plus an explicit block of the cloud-metadata address `169.254.169.254` and IPv6
unique-local (`fc00::/7`). A rejected URL is **not fetched**; it is queued *website_unsafe* ("can't
safely check") and left unchanged (FR-029). Only public-IP hosts are connected to.

**Rationale**: Contact URLs can originate from third parties (synced from Google), so the validator is
an SSRF surface into internal infra/cloud metadata. Resolving + checking on every hop (D5's manual
loop) closes redirect-based bypasses. Block-list of RFC1918/loopback/link-local/ULA is the standard
SSRF mitigation.

**Alternatives**: trusting input because it's "the operator's data" (rejected — URLs are often
third-party-authored); checking only the first URL (rejected — a public URL can 302 to `127.0.0.1`).

## D7 — Auto-vs-queue mapping onto existing StagedEdit/undo/audit

**Decision**: Reuse feature 003's **`StagedEdit`** for *every* mutation (auto-fix and queue
resolution), widening its allowed `kind` set to include **`normalize`** (the column is already
`String(16)`; no DDL). Auto-fixes and resolutions call the same `_stage(...)` path used by
`processing_service` (writes `payload_before/after`, updates the contact, records an `audit_service`
entry, commits). Undo reuses the existing `undo_staged_edit` path. Queue resolutions link their
resulting `StagedEdit` via `validation_item.staged_edit_id` for traceable undo.

**Rationale**: Gets reversibility (II), undo (FR-022), and audit (V) for free, and keeps Tidy's edits
indistinguishable from other Draft edits in the existing undo surface — no parallel mechanism.

**Alternatives**: a new edit/undo table (rejected — duplicates a proven mechanism); mutating payloads
without staging (rejected — violates Principle II).

## D8 — Worker placement & bounded outbound concurrency

**Decision**: Add `validation_worker.run_once` to the **combined** `workers/run_all.py` loop, claiming
one queued `ValidationRun` with `FOR UPDATE SKIP LOCKED` (same pattern as dedup/import/delete/label —
PostgreSQL stays the only queue, no Redis). Within a claimed run, phone/email work is CPU/DNS-bound
and runs inline; website checks fan out with a bounded `asyncio.Semaphore(website_check_concurrency)`
over `httpx.AsyncClient` via a single `asyncio.run(...)` for that run. Progress/counters commit so a
restart re-claims and resumes the run.

**Rationale**: No new container/service; reuses the durable claim pattern; bounded async keeps website
checks fast without unbounded sockets and guarantees the run terminates within time limits (SC-008).

**Alternatives**: a dedicated worker process (rejected — unnecessary; combined loop already hosts the
batch jobs); thread pool for HTTP (rejected — async + semaphore is simpler and already idiomatic with
httpx); per-contact sequential HTTP (rejected — too slow for thousands of contacts).

## D9 — Are the new dependencies a constitutional amendment?

**Decision**: **No.** The constitution requires an amendment only for a new **core technology**
(language, datastore, or dedup engine). `phonenumbers`, `email-validator`/`dnspython`, `httpx`, and an
optional `geoip2` are ordinary Python libraries inside the existing Python 3.12 / FastAPI / PostgreSQL
stack. They add no language, datastore, or engine. The feature is recorded as a **scoped exception to
005's frontend-only scope** (like the 005 deletion addendum), not a constitution change.

**Rationale**: Matches governance §Technology Constraints wording; avoids over-bureaucratizing routine
library additions while still flagging the deliberate scope expansion in the plan and CLAUDE.md.

**Alternatives**: filing a constitution amendment (rejected — no core-technology change occurs).

## D10 — Re-run idempotency & run independence

**Decision**: Each ValidationRun is **independent** and scoped to the current kept set; the UI shows
the **latest** run's summary + pending queue. Auto-fixes are inherently idempotent (a `normalize`
StagedEdit is staged only when the normalized value differs from the current stored value, so a second
run over already-normalized data stages nothing). Items from a prior run are not carried over; a
re-run produces a fresh queue. Switching the active Draft re-derives Tidy for that branch and never
deletes another branch's run/items (FR-024, edge cases).

**Rationale**: Simple, predictable, and safe; avoids cross-run item-merging complexity while the
"stage only on difference" rule prevents duplicate edits.

**Alternatives**: a single long-lived run mutated in place across re-runs (rejected — muddies audit
and the running-state model); carrying unresolved items forward (rejected — added complexity with no
clear operator benefit; the latest run re-discovers anything still broken).
