# Quickstart: Validate & Normalize (Tidy)

A runnable validation guide proving the Tidy step works end-to-end. Implementation details live in
`tasks.md`; this is a run/verify guide. Commands assume repo root and the existing docker-compose /
local dev setup from features 001–005.

## Prerequisites

- A Draft (working copy) that has completed **Review**, with a mix of kept contacts containing:
  a badly-formatted but valid phone (`+7 (701) 722-15-02`), a typeless mobile number, a typeless
  fixed-line number, an `http://` site whose `https://` works, an `http://` site that never responds,
  a contact website pointing at `http://127.0.0.1/` (SSRF probe), `mail@gmial.com`, and a valid email.
- New backend deps installed and the migration applied (steps below).

## 1. Install dependencies & migrate

```bash
# backend deps (phonenumbers, email-validator -> dnspython, httpx runtime; geoip2 optional)
cd backend && uv sync   # or: pip install -e .

# apply migration 0005_validate_normalize
alembic upgrade head
```

Expected: `validation_run` and `validation_item` tables exist; `StagedEdit` unchanged.

## 2. Run the test suites (TDD — these are written first and must pass)

```bash
# backend
cd backend && pytest -m "not slow"

# frontend
cd frontend && rtk vitest run
```

Expected coverage (all green after implementation):
- `phone_normalizer`: KZ/RU national + E.164 inputs → validity, E.164 string, `mobile` vs unclear.
- `email_validator_service`: syntax pass/fail; MX present/absent (DNS mocked).
- `website_checker`: 200/302/403/timeout/connection-error → reachable vs queue; http→https upgrade;
  SSRF guard rejects `127.0.0.1`/RFC1918/`169.254.169.254` (resolver mocked).
- `validation_service`: a seeded Draft yields the expected auto StagedEdits + ValidationItems + counts;
  re-run stages nothing new (idempotent); resolve/skip/undo behave per contract.
- frontend: `steps` has 7 entries with `tidy` between `review` and `export`; wizard derivation for
  `tidy` completed/running/passable; tidy store start→poll→summary and resolve/skip/undo; queue UI.

## 3. Drive a run via the API

```bash
# start a run for the active Draft
curl -s -X POST localhost:8000/api/working-copies/$WC/validation-runs \
  -H 'content-type: application/json' -d '{"defaultRegion":"KZ"}' | jq .

# poll until completed
curl -s localhost:8000/api/validation-runs/$RUN | jq '{status,checkedCount,autoAppliedCount,queuedCount,pendingCount}'
```

Expected on completion:
- `autoAppliedCount` ≥ 2 — the `+7 (701) 722-15-02` phone is now `+77017221502`, the working
  `http://` site is now `https://`, the typeless mobile got type `mobile` (verify on the contact
  payload / Draft).
- `queuedCount` covers: the fixed-line typeless number (`unclear_type`), `mail@gmial.com`
  (`dead_email_domain`), the dead site (`website_unreachable`), and `http://127.0.0.1/`
  (`website_unsafe`).

## 4. Verify the SSRF guard made no internal request

While step 3 runs, confirm (e.g. via worker logs or a local listener on `127.0.0.1`) that **no**
outbound request was made to `127.0.0.1` — the item is `website_unsafe` and was queued without a fetch
(FR-029, SC-010).

## 5. Work the queue

```bash
# list pending items
curl -s "localhost:8000/api/validation-runs/$RUN/items?status=pending" | jq '.[] | {issueType,originalValue}'

# resolve the unclear-type phone as work
curl -s -X POST localhost:8000/api/validation-items/$ITEM/resolve \
  -H 'content-type: application/json' -d '{"action":"set_type","type":"work"}' | jq .

# skip the dead website (keep it)
curl -s -X POST localhost:8000/api/validation-items/$SITE_ITEM/skip | jq '.status'
```

Expected: resolving creates a reversible StagedEdit (`stagedEditId` populated), the item is
`resolved`, `pendingCount` drops; skipping marks `skipped` with no edit.

## 6. Verify reversibility & audit

```bash
# undo an auto-applied normalization
curl -s -X POST localhost:8000/api/staged-edits/$EDIT/undo | jq .
```

Expected: the contact field returns to its exact pre-Tidy value; both the edit and the undo appear in
the audit log (Principle V). The frozen snapshot is unchanged (Principle II).

## 7. Verify the wizard end-to-end (UI)

1. Open the wizard; the stepper shows **7** steps, `Tidy` between `Review` and `Export`.
2. On Tidy, the current parsing **region is highlighted** (e.g. `KZ`) and changeable.
3. Start the check → the stepper shows Tidy **running**; navigate to another step and back — it keeps
   running and flips to **completed** when done.
4. With pending items remaining, click Continue → a **warning** states how many are unresolved and
   proceeding to Export is an explicit confirmed action (passable, not a hard gate — FR-004).
5. Export still shows its unchanged dry-run/snapshot/confirm/undo safeguards.

## Acceptance mapping

| Spec | Verified by |
|------|-------------|
| FR-008…FR-010 (phones) | steps 2, 3, 5 |
| FR-011…FR-013 (email) | steps 2, 3 |
| FR-014…FR-016 (websites) | steps 2, 3 |
| FR-029 / SC-010 (SSRF) | steps 2, 4 |
| FR-017…FR-020 (queue + summary) | steps 3, 5 |
| FR-021…FR-024 (reversible, audited, no Google push) | steps 2, 6 |
| FR-001…FR-005 (wizard integration, running, passable) | step 7 |
| FR-028 (region setting, highlighted) | step 7 |
