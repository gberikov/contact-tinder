# Wizard Deletions + Passable Review + Stepper Icons — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let operators delete accounts (Connect), backups (Backup) and drafts (Draft) with a cascade warning, always continue past Review without finishing triage, and show per-step icons instead of numbers in the stepper.

**Architecture:** Cascade deletion is implemented in the **service layer** (explicit ordered ORM deletes), not via a schema migration, because backend tests run on SQLite without FK enforcement. One direction of service composition: `account_service → snapshot_service → working_copy_service`. The frontend reuses the existing wizard store + `ActiveSelector`, adds one generated shadcn-vue `AlertDialog`, one `ConfirmDialog` wrapper, a `passable` store getter for the Review gate, and an `icon` field on each wizard step.

**Tech Stack:** Python 3.12 / FastAPI + SQLAlchemy 2.x (backend), pytest (SQLite in-memory), Vue 3 + TS + Pinia + reka-ui + shadcn-vue (Mira/Indigo) + Tailwind v4, Vitest, Biome.

## Global Constraints

- **Biome is the single linter/formatter.** Frontend changes must pass `npm run lint` (`biome ci .`); generated `components/ui/**` are Biome-formatted.
- **No new read endpoints / no OAuth changes.** Only the new draft-delete write endpoint is added.
- **Cascade is service-layer, no Alembic migration.** Existing FK `RESTRICT` constraints stay as a backstop.
- **Confirmation `code` is `confirmation_required` with HTTP 400** (mirrors `delete_snapshot`).
- **Deletion is auditable:** each level records its existing audit action (`snapshot.deleted`, new `working_copy.deleted`).
- **Plain-verb wizard labels and the active-selection chain are unchanged.**
- Backend tests run from `backend/` with `pytest`; frontend from `frontend/` with `npm run test` / `npm run lint` / `npm run build`.

---

## File Structure

**Backend**
- Modify `backend/src/services/working_copy_service.py` — add `delete_working_copy`.
- Modify `backend/src/api/routers/working_copies.py` — add `DELETE` route.
- Modify `backend/src/services/snapshot_service.py` — cascade through working copies.
- Modify `backend/src/services/account_service.py` — cascade through snapshots.
- Test `backend/tests/integration/test_working_copy_delete.py` — new.
- Test `backend/tests/contract/test_working_copies_api.py` — add delete cases.
- Test `backend/tests/integration/test_snapshot_delete.py` — update the "blocked" case to "cascades".
- Test `backend/tests/contract/test_snapshot_delete_api.py` — update the "blocked" case to "cascades".
- Test `backend/tests/contract/test_accounts_api.py` — add cascade case.

**Frontend**
- Modify `frontend/src/services/api.ts` — add `deleteWorkingCopy`.
- Create `frontend/src/components/ui/alert-dialog/**` — generated shadcn-vue component.
- Create `frontend/src/components/wizard/ConfirmDialog.vue` — reusable confirm wrapper.
- Modify `frontend/src/components/wizard/ActiveSelector.vue` — optional delete affordance.
- Modify `frontend/src/stores/wizard.ts` — cascade-count getters, delete actions, `passable` getter, relaxed `available`.
- Modify `frontend/src/components/wizard/WizardLayout.vue` — `canContinue` uses `passable`.
- Modify `frontend/src/pages/wizard/ConnectStep.vue`, `BackupStep.vue`, `DraftStep.vue` — wire deletion.
- Modify `frontend/src/wizard/steps.ts` — add `icon` per step.
- Modify `frontend/src/components/wizard/WizardStepper.vue` — render icon instead of number.
- Test `frontend/src/stores/wizard.spec.ts` — new (store logic).

---

## Task 1: Backend — `delete_working_copy` service with cascade

**Files:**
- Modify: `backend/src/services/working_copy_service.py`
- Test: `backend/tests/integration/test_working_copy_delete.py`

**Interfaces:**
- Produces: `working_copy_service.delete_working_copy(session: Session, working_copy_id: uuid.UUID, *, confirm: bool) -> None` — raises `NotFoundError` (404) if missing, `ConflictError` code `confirmation_required` (400) if `not confirm`; otherwise deletes the working copy and every derived dedup/triage/export row, records audit `working_copy.deleted`, commits.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/integration/test_working_copy_delete.py`:

```python
import uuid

import pytest
from sqlalchemy import func, select

from src.core.errors import ConflictError, NotFoundError
from src.models.audit import AuditEntry
from src.models.dedup import DedupRun, DuplicateCluster
from src.models.export import ExportRun, LabelBatch
from src.models.triage import DeleteBatch, StagedEdit, TriageSession
from src.models.working_copy import WorkingCopyContact
from src.services import working_copy_service
from tests.helpers import dup_person, seed_account, seed_working_copy


def _seed_derived(db, copy):
    """Attach one row of every working-copy-derived kind, plus a child where one exists."""
    wcc_id = db.scalar(
        select(WorkingCopyContact.id).where(WorkingCopyContact.working_copy_id == copy.id)
    )
    run = DedupRun(working_copy_id=copy.id, status="completed", model_version="t")
    db.add(run)
    db.flush()
    db.add(DuplicateCluster(dedup_run_id=run.id, working_copy_id=copy.id,
                            z_cluster_key="k", confidence=0.9, size=2, status="pending"))
    session = TriageSession(working_copy_id=copy.id, status="in_progress")
    db.add(session)
    db.add(StagedEdit(working_copy_contact_id=wcc_id, working_copy_id=copy.id, kind="edit",
                      payload_before={}, payload_after={}))
    db.add(DeleteBatch(working_copy_id=copy.id, account_id=copy.snapshot.account_id))
    db.add(LabelBatch(working_copy_id=copy.id, account_id=copy.snapshot.account_id))
    db.add(ExportRun(working_copy_id=copy.id, account_id=copy.snapshot.account_id))
    db.commit()


def test_delete_requires_confirmation(db):
    account = seed_account(db)
    copy = seed_working_copy(db, account, [dup_person(0, name="A B", phone="1")])
    with pytest.raises(ConflictError) as exc:
        working_copy_service.delete_working_copy(db, copy.id, confirm=False)
    assert exc.value.status_code == 400
    assert exc.value.code == "confirmation_required"


def test_delete_unknown_raises_not_found(db):
    with pytest.raises(NotFoundError):
        working_copy_service.delete_working_copy(db, uuid.uuid4(), confirm=True)


def test_delete_cascades_and_audits(db):
    account = seed_account(db)
    copy = seed_working_copy(db, account, [dup_person(0, name="A B", phone="1")])
    cid = copy.id
    _seed_derived(db, copy)

    working_copy_service.delete_working_copy(db, cid, confirm=True)

    with pytest.raises(NotFoundError):
        working_copy_service.get_working_copy(db, cid)
    for model in (DedupRun, DuplicateCluster, TriageSession, StagedEdit, DeleteBatch,
                  LabelBatch, ExportRun, WorkingCopyContact):
        remaining = db.scalar(
            select(func.count()).select_from(model).where(model.working_copy_id == cid)
        )
        assert remaining == 0, f"{model.__name__} rows survived"
    audited = db.scalar(
        select(func.count()).select_from(AuditEntry).where(
            AuditEntry.action == "working_copy.deleted", AuditEntry.target_id == cid
        )
    )
    assert audited == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/integration/test_working_copy_delete.py -v`
Expected: FAIL with `AttributeError: module 'src.services.working_copy_service' has no attribute 'delete_working_copy'`.

- [ ] **Step 3: Write minimal implementation**

In `backend/src/services/working_copy_service.py`, update the imports at the top and append the function. Replace the existing import block:

```python
from src.core.errors import ConflictError, NotFoundError
from src.models.snapshot import Snapshot, SnapshotContact
from src.models.working_copy import WorkingCopy, WorkingCopyContact
from src.services import audit_service
```

with:

```python
from src.core.errors import ConflictError, NotFoundError
from src.models.dedup import DedupRun
from src.models.export import ExportRun, LabelBatch
from src.models.snapshot import Snapshot, SnapshotContact
from src.models.triage import DeleteBatch, StagedEdit, TriageSession
from src.models.working_copy import WorkingCopy, WorkingCopyContact
from src.services import audit_service
```

Append at the end of the file:

```python
def delete_working_copy(session: Session, working_copy_id: uuid.UUID, *, confirm: bool) -> None:
    """Delete a draft and every dedup/triage/export row derived from it (US3 cleanup).

    Cascade runs in the service layer (not via DB FK) so it fires identically on SQLite (tests)
    and Postgres. Order is FK-safe: rows that reference others (export runs; the batches/sessions)
    are deleted before their targets, and merge records (which hard-reference working_copy_contact)
    are removed via the dedup-run ORM cascade before the contacts themselves.
    """
    copy = get_working_copy(session, working_copy_id)  # 404 if missing
    if not confirm:
        raise ConflictError(
            "deletion requires explicit confirmation",
            code="confirmation_required",
            status_code=400,
        )
    label = copy.label
    n_contacts = contact_count(session, working_copy_id)

    def _purge(model) -> None:
        for obj in session.scalars(
            select(model).where(model.working_copy_id == working_copy_id)
        ):
            session.delete(obj)  # per-object delete triggers ORM "all, delete-orphan" cascade
        session.flush()

    _purge(ExportRun)
    _purge(LabelBatch)  # → label_assignment
    _purge(DeleteBatch)  # → deletion_record
    _purge(TriageSession)  # → triage_decision, processing_item
    _purge(StagedEdit)
    _purge(DedupRun)  # → duplicate_cluster → cluster_member, merge_record

    audit_service.record(
        session,
        action="working_copy.deleted",
        target_type="working_copy",
        target_id=copy.id,
        source_ref=copy.snapshot_id,
        details={"label": label, "contact_count": n_contacts},
    )
    session.delete(copy)  # → working_copy_contact (ORM cascade)
    session.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/integration/test_working_copy_delete.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/working_copy_service.py backend/tests/integration/test_working_copy_delete.py
git commit -m "feat(working-copy): cascade delete_working_copy service (drafts)"
```

---

## Task 2: Backend — `DELETE /working-copies/{id}` route

**Files:**
- Modify: `backend/src/api/routers/working_copies.py`
- Test: `backend/tests/contract/test_working_copies_api.py`

**Interfaces:**
- Consumes: `working_copy_service.delete_working_copy(session, id, *, confirm)` from Task 1.
- Produces: `DELETE /api/working-copies/{working_copy_id}?confirm=<bool>` → `204` on success, `400` without confirm, `404` unknown.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/contract/test_working_copies_api.py`:

```python
def test_delete_without_confirm_is_rejected(client, db):
    account = seed_account(db)
    snapshot = seed_complete_snapshot(db, account, count=1)
    wc = client.post(f"/api/snapshots/{snapshot.id}/working-copies", json={}).json()
    resp = client.delete(f"/api/working-copies/{wc['id']}", params={"confirm": "false"})
    assert resp.status_code == 400


def test_delete_unknown_returns_404(client, db):
    import uuid

    resp = client.delete(f"/api/working-copies/{uuid.uuid4()}", params={"confirm": "true"})
    assert resp.status_code == 404


def test_delete_succeeds_with_confirm(client, db):
    account = seed_account(db)
    snapshot = seed_complete_snapshot(db, account, count=1)
    wc = client.post(f"/api/snapshots/{snapshot.id}/working-copies", json={}).json()
    resp = client.delete(f"/api/working-copies/{wc['id']}", params={"confirm": "true"})
    assert resp.status_code == 204
    assert client.get("/api/working-copies").json() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/contract/test_working_copies_api.py -v`
Expected: FAIL — the three new tests get `405 Method Not Allowed` (route absent).

- [ ] **Step 3: Write minimal implementation**

In `backend/src/api/routers/working_copies.py`, add `Query` to the FastAPI import:

```python
from fastapi import APIRouter, Depends, Query
```

Append the route at the end of the file:

```python
@router.delete("/{working_copy_id}", status_code=204)
def delete_working_copy(
    working_copy_id: uuid.UUID,
    confirm: bool = Query(...),
    session: Session = Depends(get_session),
) -> None:
    working_copy_service.delete_working_copy(session, working_copy_id, confirm=confirm)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/contract/test_working_copies_api.py -v`
Expected: PASS (all tests, old + 3 new).

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/routers/working_copies.py backend/tests/contract/test_working_copies_api.py
git commit -m "feat(api): DELETE /working-copies/{id} with confirm guard"
```

---

## Task 3: Backend — snapshot delete cascades through working copies

**Files:**
- Modify: `backend/src/services/snapshot_service.py`
- Test: `backend/tests/integration/test_snapshot_delete.py`
- Test: `backend/tests/contract/test_snapshot_delete_api.py`

**Interfaces:**
- Consumes: `working_copy_service.delete_working_copy` from Task 1.
- Produces: `snapshot_service.delete_snapshot(session, snapshot_id, *, confirm)` now succeeds even when working copies exist, deleting them first.

- [ ] **Step 1: Update the failing/obsolete tests**

In `backend/tests/integration/test_snapshot_delete.py`, replace `test_delete_blocked_while_working_copies_exist` with:

```python
def test_delete_cascades_through_working_copies(db):
    account = seed_account(db)
    snapshot = seed_complete_snapshot(db, account, count=1)
    working_copy_service.create_working_copy(db, snapshot.id, "wc")
    sid = snapshot.id

    snapshot_service.delete_snapshot(db, sid, confirm=True)

    from src.core.errors import NotFoundError
    with pytest.raises(NotFoundError):
        snapshot_service.get_snapshot(db, sid)
    # its working copies are gone too
    assert working_copy_service.list_working_copies(db) == []
```

In `backend/tests/contract/test_snapshot_delete_api.py`, replace `test_delete_blocked_with_working_copies` with:

```python
def test_delete_cascades_through_working_copies(client, db):
    account = seed_account(db)
    snapshot = seed_complete_snapshot(db, account, count=1)
    client.post(f"/api/snapshots/{snapshot.id}/working-copies", json={})
    resp = client.delete(f"/api/snapshots/{snapshot.id}", params={"confirm": "true"})
    assert resp.status_code == 204
    assert client.get(f"/api/snapshots/{snapshot.id}").status_code == 404
    assert client.get("/api/working-copies").json() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/integration/test_snapshot_delete.py tests/contract/test_snapshot_delete_api.py -v`
Expected: FAIL — the cascade tests still hit the old `ConflictError`/409 "snapshot has working copies".

- [ ] **Step 3: Write minimal implementation**

In `backend/src/services/snapshot_service.py`, add the service import near the other `from src.services import ...` line:

```python
from src.services import audit_service, working_copy_service
```

Then replace the body of `delete_snapshot` (the working-copy guard and below) so it cascades instead of refusing. Replace:

```python
    if working_copy_count(session, snapshot_id) > 0:
        raise ConflictError("snapshot has working copies; delete them first")

    snapshot.status = "deleting"
```

with:

```python
    # Cascade: remove each working copy (and all its derived dedup/triage/export data) first,
    # so the snapshot's RESTRICT child constraint is satisfied (US Backup cleanup).
    for wc in session.scalars(
        select(WorkingCopy.id).where(WorkingCopy.snapshot_id == snapshot_id)
    ).all():
        working_copy_service.delete_working_copy(session, wc, confirm=True)

    snapshot = get_snapshot(session, snapshot_id)  # re-fetch after child commits
    snapshot.status = "deleting"
```

(The existing `if not confirm: raise ConflictError(... confirmation_required ...)` guard above stays unchanged. `WorkingCopy` and `select` are already imported in this module.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/integration/test_snapshot_delete.py tests/contract/test_snapshot_delete_api.py -v`
Expected: PASS (confirmation-required test still passes; cascade tests pass).

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/snapshot_service.py backend/tests/integration/test_snapshot_delete.py backend/tests/contract/test_snapshot_delete_api.py
git commit -m "feat(snapshot): delete cascades through working copies"
```

---

## Task 4: Backend — account delete cascades through snapshots

**Files:**
- Modify: `backend/src/services/account_service.py`
- Test: `backend/tests/contract/test_accounts_api.py`

**Interfaces:**
- Consumes: `snapshot_service.delete_snapshot` from Task 3.
- Produces: `account_service.disconnect(session, account_id)` now deletes the account's snapshots (and their drafts) first, then the account.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/contract/test_accounts_api.py`:

```python
def test_disconnect_cascades_snapshots_and_drafts(client, db):
    import uuid

    from src.models.account import Account
    from tests.helpers import seed_complete_snapshot

    client.get("/api/accounts/callback", params={"code": "c", "state": "s"},
               follow_redirects=False)
    account_id = client.get("/api/accounts").json()[0]["id"]

    account = db.get(Account, uuid.UUID(account_id))
    snapshot = seed_complete_snapshot(db, account, count=1)
    client.post(f"/api/snapshots/{snapshot.id}/working-copies", json={})

    assert client.delete(f"/api/accounts/{account_id}").status_code == 204
    assert client.get("/api/accounts").json() == []
    assert client.get("/api/snapshots").json() == []
    assert client.get("/api/working-copies").json() == []
```

(`test_disconnect_account` for the no-children case stays as-is and must keep passing.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/contract/test_accounts_api.py -v`
Expected: FAIL — deleting an account with snapshots errors (FK/`RESTRICT` on Postgres) or leaves snapshots behind on SQLite, so one of the post-assertions fails.

- [ ] **Step 3: Write minimal implementation**

In `backend/src/services/account_service.py`, replace `disconnect`:

```python
def disconnect(session: Session, account_id: uuid.UUID) -> None:
    account = get_account(session, account_id)
    session.delete(account)
    session.flush()
```

with:

```python
def disconnect(session: Session, account_id: uuid.UUID) -> None:
    account = get_account(session, account_id)
    # Cascade: delete the account's snapshots (and their drafts/derived data) first so the
    # snapshot RESTRICT child constraint is satisfied (Connect cleanup).
    from src.models.snapshot import Snapshot
    from src.services import snapshot_service

    for sid in session.scalars(
        select(Snapshot.id).where(Snapshot.account_id == account_id)
    ).all():
        snapshot_service.delete_snapshot(session, sid, confirm=True)

    account = get_account(session, account_id)  # re-fetch after child commits
    session.delete(account)
    session.flush()
```

(Imports are local to avoid any import-order coupling; `select` is already imported at module top.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/contract/test_accounts_api.py -v`
Expected: PASS (both the no-children and cascade tests).

- [ ] **Step 5: Run the full backend suite + commit**

Run: `cd backend && pytest -q`
Expected: PASS (no regressions).

```bash
git add backend/src/services/account_service.py backend/tests/contract/test_accounts_api.py
git commit -m "feat(account): disconnect cascades through snapshots and drafts"
```

---

## Task 5: Frontend — `deleteWorkingCopy` API client method

**Files:**
- Modify: `frontend/src/services/api.ts`

**Interfaces:**
- Produces: `api.deleteWorkingCopy(id: string): Promise<void>` → `DELETE /working-copies/{id}?confirm=true`.

- [ ] **Step 1: Add the method**

In `frontend/src/services/api.ts`, immediately after the `listWorkingCopies` entry (inside the `api` object), add:

```ts
  deleteWorkingCopy: (id: string) =>
    request<void>(`/working-copies/${id}?confirm=true`, { method: 'DELETE' }),
```

- [ ] **Step 2: Verify it typechecks**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/services/api.ts
git commit -m "feat(api-client): deleteWorkingCopy"
```

---

## Task 6: Frontend — generate shadcn-vue AlertDialog

**Files:**
- Create: `frontend/src/components/ui/alert-dialog/**`

**Interfaces:**
- Produces: the `@/components/ui/alert-dialog` module exporting `AlertDialog`, `AlertDialogContent`, `AlertDialogHeader`, `AlertDialogFooter`, `AlertDialogTitle`, `AlertDialogDescription`, `AlertDialogAction`, `AlertDialogCancel` (standard shadcn-vue set).

- [ ] **Step 1: Generate the component**

Run: `cd frontend && npx shadcn-vue@latest add alert-dialog`
Expected: files created under `src/components/ui/alert-dialog/`.

If the CLI is unavailable offline, create the standard shadcn-vue alert-dialog files manually from reka-ui's `AlertDialogRoot/Trigger/Portal/Overlay/Content/Title/Description/Action/Cancel` primitives (same structure the CLI emits), exporting the names listed above from `index.ts`.

- [ ] **Step 2: Biome-format the generated files**

Run: `cd frontend && npx @biomejs/biome format --write src/components/ui/alert-dialog`
Expected: files reformatted to the repo style.

- [ ] **Step 3: Verify build/lint**

Run: `cd frontend && npm run lint && npx vue-tsc --noEmit`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/alert-dialog
git commit -m "feat(ui): add shadcn-vue AlertDialog (Biome-formatted)"
```

---

## Task 7: Frontend — reusable `ConfirmDialog` wrapper

**Files:**
- Create: `frontend/src/components/wizard/ConfirmDialog.vue`

**Interfaces:**
- Consumes: `@/components/ui/alert-dialog` (Task 6), `@/components/ui/button`.
- Produces: `ConfirmDialog` with props `open: boolean`, `title: string`, `description: string`, `confirmText?: string` (default `'Delete'`); emits `update:open` (boolean) and `confirm` (void). Destructive styling on the confirm action.

- [ ] **Step 1: Create the component**

Create `frontend/src/components/wizard/ConfirmDialog.vue`:

```vue
<script setup lang="ts">
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';

defineProps<{
  open: boolean;
  title: string;
  description: string;
  confirmText?: string;
}>();

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void;
  (e: 'confirm'): void;
}>();
</script>

<template>
  <AlertDialog :open="open" @update:open="emit('update:open', $event)">
    <AlertDialogContent>
      <AlertDialogHeader>
        <AlertDialogTitle>{{ title }}</AlertDialogTitle>
        <AlertDialogDescription>{{ description }}</AlertDialogDescription>
      </AlertDialogHeader>
      <AlertDialogFooter>
        <AlertDialogCancel>Cancel</AlertDialogCancel>
        <AlertDialogAction
          :class="cn(buttonVariants({ variant: 'destructive' }))"
          @click="emit('confirm')"
        >
          {{ confirmText ?? 'Delete' }}
        </AlertDialogAction>
      </AlertDialogFooter>
    </AlertDialogContent>
  </AlertDialog>
</template>
```

- [ ] **Step 2: Verify build/lint**

Run: `cd frontend && npm run lint && npx vue-tsc --noEmit`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/wizard/ConfirmDialog.vue
git commit -m "feat(wizard): reusable ConfirmDialog (AlertDialog wrapper)"
```

---

## Task 8: Frontend — delete affordance on `ActiveSelector`

**Files:**
- Modify: `frontend/src/components/wizard/ActiveSelector.vue`

**Interfaces:**
- Produces: `ActiveSelector` gains optional prop `deletable?: boolean` and emits `delete` (id: string) in addition to `select`. The row is restructured so the trash control is a sibling of the select button (no nested `<button>`).

- [ ] **Step 1: Rewrite the component**

Replace the entire contents of `frontend/src/components/wizard/ActiveSelector.vue`:

```vue
<script setup lang="ts">
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { SelectorItem } from '@/components/wizard/types';
import { cn } from '@/lib/utils';
import { Check, Trash2 } from 'lucide-vue-next';

defineProps<{
  items: SelectorItem[];
  activeId: string | null;
  emptyText?: string;
  deletable?: boolean;
}>();

const emit = defineEmits<{
  (e: 'select', id: string): void;
  (e: 'delete', id: string): void;
}>();
</script>

<template>
  <div class="space-y-2">
    <p v-if="items.length === 0" class="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
      {{ emptyText ?? 'Nothing here yet.' }}
    </p>

    <div v-for="item in items" :key="item.id" class="flex items-center gap-2">
      <button
        type="button"
        :class="
          cn(
            'flex min-w-0 flex-1 items-center justify-between rounded-lg border p-3 text-left transition-colors hover:bg-accent/50',
            item.id === activeId ? 'border-primary ring-1 ring-primary' : 'border-border',
          )
        "
        @click="emit('select', item.id)"
      >
        <span class="min-w-0">
          <span class="block truncate font-medium">{{ item.title }}</span>
          <span v-if="item.subtitle" class="block truncate text-xs text-muted-foreground">
            {{ item.subtitle }}
          </span>
        </span>
        <span class="flex shrink-0 items-center gap-2">
          <Badge v-if="item.status" :variant="item.statusVariant ?? 'secondary'">
            {{ item.status }}
          </Badge>
          <Badge v-if="item.id === activeId" variant="default" class="gap-1">
            <Check class="size-3" /> Active
          </Badge>
          <span v-else class="text-xs text-muted-foreground">Set active</span>
        </span>
      </button>

      <Button
        v-if="deletable"
        variant="ghost"
        size="icon"
        :aria-label="`Delete ${item.title}`"
        class="shrink-0 text-muted-foreground hover:text-destructive"
        @click="emit('delete', item.id)"
      >
        <Trash2 class="size-4" />
      </Button>
    </div>
  </div>
</template>
```

- [ ] **Step 2: Verify build/lint**

Run: `cd frontend && npm run lint && npx vue-tsc --noEmit`
Expected: PASS (`ConnectStep`/`BackupStep`/`DraftStep` still compile — they don't yet pass `deletable` or listen for `delete`; that is Task 9).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/wizard/ActiveSelector.vue
git commit -m "feat(wizard): optional delete affordance on ActiveSelector"
```

---

## Task 9: Frontend — store delete actions + cascade-count getters

**Files:**
- Modify: `frontend/src/stores/wizard.ts`
- Test: `frontend/src/stores/wizard.spec.ts`

**Interfaces:**
- Consumes: `api.disconnect`, `api.deleteSnapshot`, `api.deleteWorkingCopy`.
- Produces (getters): `snapshotCountForAccount(accountId: string): number`, `draftCountForAccount(accountId: string): number`, `draftCountForSnapshot(snapshotId: string): number`.
- Produces (actions): `deleteAccount(id: string): Promise<void>`, `removeSnapshot(id: string): Promise<void>`, `deleteDraft(id: string): Promise<void>` — each calls the API, repairs the persisted active chain, and re-`hydrate()`s.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/stores/wizard.spec.ts`:

```ts
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useWizardStore } from './wizard';

function seedChain(store: ReturnType<typeof useWizardStore>) {
  store.accounts = [{ id: 'a1', email: 'x', status: 'connected', grantedScopes: [], createdAt: '' }];
  store.snapshots = [
    { id: 's1', accountId: 'a1', status: 'complete', source: 'x', workingCopyCount: 1, createdAt: '' },
    { id: 's2', accountId: 'a1', status: 'complete', source: 'x', workingCopyCount: 0, createdAt: '' },
  ];
  store.workingCopies = [
    { id: 'w1', snapshotId: 's1', label: 'd', status: 'ready', createdAt: '' },
  ];
}

describe('wizard cascade counts', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  it('counts snapshots and drafts under an account', () => {
    const store = useWizardStore();
    seedChain(store);
    expect(store.snapshotCountForAccount('a1')).toBe(2);
    expect(store.draftCountForAccount('a1')).toBe(1);
    expect(store.draftCountForSnapshot('s1')).toBe(1);
    expect(store.draftCountForSnapshot('s2')).toBe(0);
  });

  it('clears the active chain when the active draft is deleted', async () => {
    const store = useWizardStore();
    seedChain(store);
    store.setActiveAccount('a1');
    store.setActiveSnapshot('s1');
    store.setActiveDraft('w1');
    vi.spyOn(store, 'hydrate').mockResolvedValue();
    const { api } = await import('@/services/api');
    vi.spyOn(api, 'deleteWorkingCopy').mockResolvedValue();

    await store.deleteDraft('w1');

    expect(store.workingCopyBySnapshot.s1).toBeUndefined();
  });
});

describe('wizard review gate', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  it('Review is always passable even with no triage session', () => {
    const store = useWizardStore();
    store.triageSessions = [];
    expect(store.passable('review')).toBe(true);
  });

  it('export becomes available once merge is complete, regardless of triage', () => {
    const store = useWizardStore();
    store.dedupRuns = [
      { id: 'r1', workingCopyId: 'w1', status: 'completed', modelVersion: 'v', confidenceFloor: 0, createdAt: '' },
    ];
    store.triageSessions = [];
    expect(store.available('export')).toBe(true);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/stores/wizard.spec.ts`
Expected: FAIL — `snapshotCountForAccount` / `passable` / `deleteDraft` are undefined.

- [ ] **Step 3: Implement the getters**

In `frontend/src/stores/wizard.ts`, inside `getters`, after `workingCopiesForActiveSnapshot`, add:

```ts
    // ---- cascade-impact counts for the delete-confirmation warning -------------------------
    snapshotCountForAccount(state) {
      return (accountId: string): number =>
        state.snapshots.filter((s) => s.accountId === accountId).length;
    },
    draftCountForAccount(state) {
      return (accountId: string): number => {
        const snapIds = new Set(
          state.snapshots.filter((s) => s.accountId === accountId).map((s) => s.id),
        );
        return state.workingCopies.filter((w) => snapIds.has(w.snapshotId)).length;
      };
    },
    draftCountForSnapshot(state) {
      return (snapshotId: string): number =>
        state.workingCopies.filter((w) => w.snapshotId === snapshotId).length;
    },
```

- [ ] **Step 4: Implement the delete actions**

In `frontend/src/stores/wizard.ts`, inside `actions`, after `loadExport`, add:

```ts
    // ---- destructive deletions (repair the persisted active chain, then re-hydrate) --------
    async deleteAccount(id: string) {
      await api.disconnect(id);
      if (this.activeAccountId === id) this.activeAccountId = null;
      delete this.snapshotByAccount[id];
      this.persist();
      await this.hydrate();
    },
    async removeSnapshot(id: string) {
      await api.deleteSnapshot(id);
      for (const [accountId, snapshotId] of Object.entries(this.snapshotByAccount)) {
        if (snapshotId === id) delete this.snapshotByAccount[accountId];
      }
      delete this.workingCopyBySnapshot[id];
      this.persist();
      await this.hydrate();
    },
    async deleteDraft(id: string) {
      await api.deleteWorkingCopy(id);
      for (const [snapshotId, workingCopyId] of Object.entries(this.workingCopyBySnapshot)) {
        if (workingCopyId === id) delete this.workingCopyBySnapshot[snapshotId];
      }
      this.persist();
      await this.hydrate();
    },
```

- [ ] **Step 5: Run test to verify count/chain tests pass**

Run: `cd frontend && npx vitest run src/stores/wizard.spec.ts -t "cascade counts"`
Expected: PASS (the `passable`/`available` tests still fail until Task 10).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/stores/wizard.ts frontend/src/stores/wizard.spec.ts
git commit -m "feat(wizard-store): cascade-count getters + delete actions with chain repair"
```

---

## Task 10: Frontend — Review is always passable

**Files:**
- Modify: `frontend/src/stores/wizard.ts`
- Modify: `frontend/src/components/wizard/WizardLayout.vue`

**Interfaces:**
- Produces (getter): `passable(key: StepKey): boolean` — `true` for `review`, otherwise `completed(key) || emptyButPassable(key)`.
- Changes: `available(key)` uses `passable(prereq)` instead of `completed(prereq)`; `WizardLayout.canContinue` uses `passable(currentKey)`. `completed()` is unchanged (the stepper check still requires a finished triage — FR-A12).

- [ ] **Step 1: Add `passable` and relax `available`**

In `frontend/src/stores/wizard.ts`, add this getter immediately before `displayState`:

```ts
    // FR-A11/A12: Review can always be continued past (Export's undecided warning is the net);
    // every other step is passable exactly when it is completed (or empty-but-passable).
    passable() {
      return (key: StepKey): boolean => {
        if (key === 'review') return true;
        return this.completed(key) || this.emptyButPassable(key);
      };
    },
```

Then change `available` from:

```ts
    available() {
      return (key: StepKey): boolean => {
        const prereq = stepByKey(key).prerequisiteKey;
        return prereq == null ? true : this.completed(prereq);
      };
    },
```

to:

```ts
    available() {
      return (key: StepKey): boolean => {
        const prereq = stepByKey(key).prerequisiteKey;
        return prereq == null ? true : this.passable(prereq);
      };
    },
```

- [ ] **Step 2: Use `passable` in the layout's Continue gate**

In `frontend/src/components/wizard/WizardLayout.vue`, change `canContinue` from:

```ts
const canContinue = computed(
  () => wizard.completed(currentKey.value) || wizard.emptyButPassable(currentKey.value),
);
```

to:

```ts
const canContinue = computed(() => wizard.passable(currentKey.value));
```

- [ ] **Step 3: Run the store tests to verify they pass**

Run: `cd frontend && npx vitest run src/stores/wizard.spec.ts`
Expected: PASS (all tests, including the review-gate ones).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/stores/wizard.ts frontend/src/components/wizard/WizardLayout.vue
git commit -m "feat(wizard): Review is always passable to Export (FR-A11)"
```

---

## Task 11: Frontend — wire deletion into Connect, Backup, Draft

**Files:**
- Modify: `frontend/src/pages/wizard/ConnectStep.vue`
- Modify: `frontend/src/pages/wizard/BackupStep.vue`
- Modify: `frontend/src/pages/wizard/DraftStep.vue`

**Interfaces:**
- Consumes: `ActiveSelector` `deletable` + `@delete` (Task 8), `ConfirmDialog` (Task 7), store getters/actions (Task 9).

- [ ] **Step 1: ConnectStep — confirm + delete account**

In `frontend/src/pages/wizard/ConnectStep.vue`, replace the `<script setup>` body's tail (from `function select` onward) and add imports. Replace the whole file with:

```vue
<script setup lang="ts">
import { Button } from '@/components/ui/button';
import ActiveSelector from '@/components/wizard/ActiveSelector.vue';
import ConfirmDialog from '@/components/wizard/ConfirmDialog.vue';
import type { SelectorItem } from '@/components/wizard/types';
import { api } from '@/services/api';
import { useWizardStore } from '@/stores/wizard';
import { computed, ref } from 'vue';

const wizard = useWizardStore();
const error = ref<string | null>(null);
const pending = ref<{ id: string; email: string } | null>(null);

const items = computed<SelectorItem[]>(() =>
  wizard.accounts.map((a) => ({
    id: a.id,
    title: a.email,
    status: a.status,
    statusVariant:
      a.status === 'connected'
        ? 'success'
        : a.status === 'needs_reauth'
          ? 'destructive'
          : 'secondary',
  })),
);

const confirmText = computed(() => {
  if (!pending.value) return '';
  const snaps = wizard.snapshotCountForAccount(pending.value.id);
  const drafts = wizard.draftCountForAccount(pending.value.id);
  const tail =
    snaps === 0
      ? 'It has no backups.'
      : `This also deletes ${snaps} backup(s) and ${drafts} draft(s), with all their merge, review, and export data.`;
  return `${tail} This cannot be undone.`;
});

async function connect() {
  try {
    const { authorizationUrl } = await api.connect();
    window.location.href = authorizationUrl;
  } catch (e) {
    error.value = (e as Error).message;
  }
}

function select(id: string) {
  wizard.setActiveAccount(id);
}

function askDelete(id: string) {
  const account = wizard.accounts.find((a) => a.id === id);
  if (account) pending.value = { id, email: account.email };
}

async function confirmDelete() {
  if (!pending.value) return;
  const id = pending.value.id;
  pending.value = null;
  try {
    await wizard.deleteAccount(id);
  } catch (e) {
    error.value = (e as Error).message;
  }
}
</script>

<template>
  <div class="space-y-4">
    <p v-if="error" class="text-sm text-destructive">{{ error }}</p>
    <ActiveSelector
      :items="items"
      :active-id="wizard.activeAccountId"
      deletable
      empty-text="No Google accounts connected yet."
      @select="select"
      @delete="askDelete"
    />
    <Button @click="connect">Connect Google account</Button>

    <ConfirmDialog
      :open="pending !== null"
      :title="`Delete ${pending?.email ?? ''}?`"
      :description="confirmText"
      confirm-text="Delete account"
      @update:open="(v) => { if (!v) pending = null; }"
      @confirm="confirmDelete"
    />
  </div>
</template>
```

- [ ] **Step 2: BackupStep — confirm + delete backup**

In `frontend/src/pages/wizard/BackupStep.vue`, add the imports and the delete plumbing. Add to the import block:

```ts
import ConfirmDialog from '@/components/wizard/ConfirmDialog.vue';
```

Add these refs/functions to the `<script setup>` (after the existing `function select`):

```ts
const pending = ref<{ id: string; title: string } | null>(null);

const confirmText = computed(() => {
  if (!pending.value) return '';
  const drafts = wizard.draftCountForSnapshot(pending.value.id);
  const tail =
    drafts === 0
      ? 'It has no drafts.'
      : `This also deletes ${drafts} draft(s), with all their merge, review, and export data.`;
  return `${tail} This cannot be undone.`;
});

function askDelete(id: string) {
  const snapshot = wizard.snapshots.find((s) => s.id === id);
  pending.value = { id, title: snapshot?.label || `Backup ${id.slice(0, 8)}` };
}

async function confirmDelete() {
  if (!pending.value) return;
  const id = pending.value.id;
  pending.value = null;
  try {
    await wizard.removeSnapshot(id);
  } catch (e) {
    error.value = (e as Error).message;
  }
}
```

Add `computed` to the existing `vue` import (it currently imports `computed, onMounted, ref, watch` — already includes `computed`, so no change). In the template, set `deletable` and the `@delete` handler on `ActiveSelector`, and add the dialog. Change:

```html
    <ActiveSelector
      :items="items"
      :active-id="wizard.activeSnapshotId"
      empty-text="No backups yet — create one to freeze your contacts."
      @select="select"
    />
```

to:

```html
    <ActiveSelector
      :items="items"
      :active-id="wizard.activeSnapshotId"
      deletable
      empty-text="No backups yet — create one to freeze your contacts."
      @select="select"
      @delete="askDelete"
    />

    <ConfirmDialog
      :open="pending !== null"
      :title="`Delete ${pending?.title ?? ''}?`"
      :description="confirmText"
      confirm-text="Delete backup"
      @update:open="(v) => { if (!v) pending = null; }"
      @confirm="confirmDelete"
    />
```

- [ ] **Step 3: DraftStep — confirm + delete draft**

In `frontend/src/pages/wizard/DraftStep.vue`, add the import and plumbing. Add to the import block:

```ts
import ConfirmDialog from '@/components/wizard/ConfirmDialog.vue';
```

Add to `<script setup>` (after the existing `function select`):

```ts
const pending = ref<{ id: string; title: string } | null>(null);

function askDelete(id: string) {
  const draft = wizard.workingCopies.find((w) => w.id === id);
  pending.value = { id, title: draft?.label || `Draft ${id.slice(0, 8)}` };
}

async function confirmDelete() {
  if (!pending.value) return;
  const id = pending.value.id;
  pending.value = null;
  try {
    await wizard.deleteDraft(id);
  } catch (e) {
    error.value = (e as Error).message;
  }
}
```

In the template, change:

```html
    <ActiveSelector
      :items="items"
      :active-id="wizard.activeWorkingCopyId"
      empty-text="No drafts yet — create one to start editing safely."
      @select="select"
    />
```

to:

```html
    <ActiveSelector
      :items="items"
      :active-id="wizard.activeWorkingCopyId"
      deletable
      empty-text="No drafts yet — create one to start editing safely."
      @select="select"
      @delete="askDelete"
    />

    <ConfirmDialog
      :open="pending !== null"
      :title="`Delete ${pending?.title ?? ''}?`"
      description="This deletes the draft and all its merge, review, and export data. This cannot be undone."
      confirm-text="Delete draft"
      @update:open="(v) => { if (!v) pending = null; }"
      @confirm="confirmDelete"
    />
```

- [ ] **Step 4: Verify build/lint**

Run: `cd frontend && npm run lint && npx vue-tsc --noEmit`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/wizard/ConnectStep.vue frontend/src/pages/wizard/BackupStep.vue frontend/src/pages/wizard/DraftStep.vue
git commit -m "feat(wizard): delete accounts/backups/drafts with cascade-warning dialog"
```

---

## Task 12: Frontend — per-step icons in the stepper

**Files:**
- Modify: `frontend/src/wizard/steps.ts`
- Modify: `frontend/src/components/wizard/WizardStepper.vue`

**Interfaces:**
- Produces: `WizardStep.icon: Component` (a lucide icon component) on every step.
- Changes: `WizardStepper` renders `<component :is="step.icon" />` in place of `{{ step.index }}`; running→spinner and completed→check are unchanged and still take precedence (FR-A15).

- [ ] **Step 1: Add `icon` to each step**

In `frontend/src/wizard/steps.ts`, add imports at the top (after the file's opening comment):

```ts
import type { Component } from 'vue';
import {
  DatabaseBackup,
  FilePen,
  GitMerge,
  Link2,
  ListChecks,
  Upload,
} from 'lucide-vue-next';
```

Add `icon` to the interface:

```ts
export interface WizardStep {
  key: StepKey;
  index: number;
  label: string;
  description: string;
  route: string;
  prerequisiteKey: StepKey | null;
  isLongJob: boolean;
  icon: Component;
}
```

Add an `icon` line to each of the six step objects in `WIZARD_STEPS`:
- `connect`: `icon: Link2,`
- `backup`: `icon: DatabaseBackup,`
- `draft`: `icon: FilePen,`
- `merge`: `icon: GitMerge,`
- `review`: `icon: ListChecks,`
- `export`: `icon: Upload,`

(Place each `icon:` line after that step's `isLongJob` line.)

- [ ] **Step 2: Render the icon in the stepper**

In `frontend/src/components/wizard/WizardStepper.vue`, change:

```html
            <Check
              v-else-if="wizard.completed(step.key) && step.index !== currentStepIndex"
              class="size-4"
            />
            <span v-else>{{ step.index }}</span>
```

to:

```html
            <Check
              v-else-if="wizard.completed(step.key) && step.index !== currentStepIndex"
              class="size-4"
            />
            <component :is="step.icon" v-else class="size-4" />
```

- [ ] **Step 3: Verify build/lint**

Run: `cd frontend && npm run lint && npx vue-tsc --noEmit`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/wizard/steps.ts frontend/src/components/wizard/WizardStepper.vue
git commit -m "feat(wizard): per-step icons instead of numbers in the stepper"
```

---

## Task 13: Docs — annotate the frontend-only deviation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `specs/005-ui-redesign-wizard/plan.md`

- [ ] **Step 1: Annotate CLAUDE.md**

In `C:\Develop\contact-tinder\CLAUDE.md`, append one sentence to the feature-005 paragraph noting the deviation:

> Addendum (2026-06-21): the wizard adds account/backup/draft deletion and a passable Review step; draft deletion required a small backend addition (`DELETE /working-copies/{id}` + service-layer cascade), a knowing exception to the otherwise frontend-only scope. See `specs/005-ui-redesign-wizard/addendum-deletions-and-passable-review.md`.

- [ ] **Step 2: Annotate plan.md**

In `specs/005-ui-redesign-wizard/plan.md`, add the same note near its "frontend-only" statement (find the line asserting no backend changes; add a one-line addendum pointer beside it).

- [ ] **Step 3: Run the full suites one last time**

Run: `cd backend && pytest -q`
Run: `cd frontend && npm run test && npm run lint && npm run build`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md specs/005-ui-redesign-wizard/plan.md
git commit -m "docs(005): note the backend deviation for draft deletion"
```

---

## Self-Review (completed)

**Spec coverage:**
- FR-A1 → Task 1; FR-A2 → Task 2; FR-A3 → Task 3; FR-A4 → Task 4; FR-A5 → Tasks 1/3 (audit actions).
- FR-A6 → Task 5; FR-A7 → Tasks 6+7; FR-A8 → Task 8; FR-A9 → Task 9 (chain repair) + Task 11 (wiring); FR-A10 → Task 11 (inline `error`).
- FR-A11/A12 → Task 10; FR-A13 → unchanged (Export `UndecidedWarning`, no task needed).
- FR-A14/A15 → Task 12. Deviation note → Task 13.

**Placeholder scan:** No TBD/TODO; every code step shows full code. The only generated boilerplate (AlertDialog) is produced by the shadcn-vue CLI with a manual fallback described.

**Type consistency:** Store action names used in Task 11 (`deleteAccount`, `removeSnapshot`, `deleteDraft`) match Task 9. `passable` used in Task 10's `available`/`canContinue` matches its Task 10 definition. `deleteWorkingCopy` (Task 5) matches its use in Task 9. `WizardStep.icon` (Task 12) is `Component`. `confirmation_required`/400 is consistent across Tasks 1–4.

**Note for the implementer:** `removeSnapshot` (not `deleteSnapshot`) is the store action name — `api.deleteSnapshot` is the client method it calls; the names intentionally differ to avoid shadowing.
