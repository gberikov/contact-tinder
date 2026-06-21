# HTTP Contract: Validation (Tidy) API

New endpoints under the existing `/api` prefix, served by `src/api/routers/validation.py` and
`region_service`/`validation_service`. All are scoped to the operator's own Draft (working copy).
No existing endpoint is changed. Status/issue enums per [data-model.md](../data-model.md).

Conventions: UUIDs are strings; timestamps ISO-8601 UTC; errors use the app's existing error envelope
(`core/errors.py`) with `404` (not found), `409` (conflict, e.g. resolve an already-resolved item),
`422` (bad body). Money-shot safety rule: these endpoints **never** call Google — they only stage
reversible edits on the Draft.

## Start a validation run

`POST /api/working-copies/{working_copy_id}/validation-runs` → `201`

Request body (`StartValidationBody`):
```json
{ "sessionId": "uuid|null", "defaultRegion": "KZ" }
```
- `sessionId` (optional) — the Review session whose keep-decisions define the kept set; defaults to
  the Draft's latest session.
- `defaultRegion` (optional) — ISO-3166 alpha-2 used to parse national-format phones (D2); falls back
  to `phone_default_region`.

Behavior: creates a `queued` `ValidationRun` (rejects with `409` if one is already `queued`/`running`
for this Draft) and returns it. The combined worker picks it up.

Response (`ValidationRunOut`): see schema below.

## List validation runs for a Draft

`GET /api/working-copies/{working_copy_id}/validation-runs` → `200` `ValidationRunOut[]`

Returns the Draft's runs **newest-first**. This is how the wizard finds the **latest** run on reload
to derive Tidy's `completed`/`running`/`emptyButPassable` state (FR-003). May be empty (no run yet).

## Get a validation run (poll)

`GET /api/validation-runs/{validation_run_id}` → `200` `ValidationRunOut`

`ValidationRunOut`:
```json
{
  "id": "uuid",
  "workingCopyId": "uuid",
  "sessionId": "uuid|null",
  "status": "queued|running|completed|failed",
  "defaultRegion": "KZ|null",
  "checkedCount": 0,
  "autoAppliedCount": 0,
  "queuedCount": 0,
  "pendingCount": 0,
  "lastError": "string|null",
  "createdAt": "iso8601",
  "startedAt": "iso8601|null",
  "completedAt": "iso8601|null"
}
```
- `queuedCount` = items created by the run (stored on `validation_run`). `pendingCount` is **not
  stored** — it is computed live as `COUNT(validation_item WHERE status='pending')` at serialization
  time (drives the passability warning, FR-004). The frontend polls this to terminal status (reusing
  the existing poll-to-done pattern).

## List the manual queue

`GET /api/validation-runs/{validation_run_id}/items?status=pending` → `200` `ValidationItemOut[]`

`ValidationItemOut`:
```json
{
  "id": "uuid",
  "workingCopyContactId": "uuid",
  "contactDisplayName": "string|null",
  "fieldKind": "phone|email|website",
  "fieldIndex": 0,
  "issueType": "invalid_phone|unclear_type|invalid_email|dead_email_domain|website_unreachable|website_unsafe",
  "originalValue": "string",
  "suggestedValue": "string|null",
  "status": "pending|resolved|skipped",
  "stagedEditId": "uuid|null",
  "createdAt": "iso8601",
  "resolvedAt": "iso8601|null"
}
```
`status` query defaults to `pending`; `all` returns the full queue. `contactDisplayName` is derived
(read-only convenience) for rendering.

## Resolve a queue item

`POST /api/validation-items/{item_id}/resolve` → `200` `ValidationItemOut`

Request body (`ResolveValidationItemBody`) — exactly one action, validated per `issueType`:
```json
{ "action": "set_type",  "type": "mobile|work|home|other" }      // unclear_type
{ "action": "edit_value","value": "string" }                      // any: replace the field value
{ "action": "remove_field" }                                       // any: drop the offending value
```
Behavior: applies the change as a reversible `normalize`/`edit` `StagedEdit` on the contact, links it
via `staged_edit_id`, sets the item `resolved`, records an `audit_service` entry, and decrements
`pendingCount`. `409` if the item is already `resolved`. `edit_value` for a phone re-validates and may
itself re-queue if still invalid (returned `issueType` unchanged + `status` stays `pending`).

## Skip a queue item

`POST /api/validation-items/{item_id}/skip` → `200` `ValidationItemOut`

Leaves the value unchanged, sets the item `skipped` (FR-019), decrements `pendingCount`. No StagedEdit.

## Undo a staged edit (reuse)

`POST /api/staged-edits/{staged_edit_id}/undo` → `200`

Reverts the contact to `payload_before` (FR-022), marks the edit `undone`, audits it. This is the
**existing** triage staged-edit undo path — Tidy reuses it (the route already exists for feature 003;
if not yet exposed, this contract formalizes it). The linked `validation_item` (if any) returns to
`pending`.

## Detect the initial region (settings helper)

`GET /api/settings/detect-region` → `200`
```json
{ "region": "KZ|null", "source": "geoip|none" }
```
- `region` is non-null only when the client IP is public **and** a GeoLite2 DB is configured (D3);
  otherwise `null` and the frontend falls back to browser locale/timezone. This endpoint performs **no**
  third-party call.

## Error / edge contract

- A `website_unsafe` item is created **without** any outbound fetch (SSRF guard, FR-029); its
  `originalValue` is the offending URL.
- Starting a run on a Draft with **zero** kept contacts returns a `completed` run with all counts `0`
  (the *Nothing to clean* edge case; summary per FR-020) — the worker may complete it immediately.
- All list/resolve/skip endpoints 404 on unknown ids and never leak another account's data
  (Principle I isolation).
