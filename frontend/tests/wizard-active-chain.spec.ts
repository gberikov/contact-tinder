import type { Account, Snapshot, WorkingCopy } from '@/services/api';
import { useWizardStore } from '@/stores/wizard';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/services/api', () => ({ api: {} }));

const accounts: Account[] = [
  { id: 'a1', email: 'a1@x.com', status: 'connected', grantedScopes: [], createdAt: 'now' },
  { id: 'a2', email: 'a2@x.com', status: 'connected', grantedScopes: [], createdAt: 'now' },
];
const snapshots: Snapshot[] = [
  {
    id: 's1',
    accountId: 'a1',
    status: 'complete',
    source: 'g',
    workingCopyCount: 1,
    createdAt: 'now',
  },
  {
    id: 's2',
    accountId: 'a2',
    status: 'complete',
    source: 'g',
    workingCopyCount: 1,
    createdAt: 'now',
  },
];
const workingCopies: WorkingCopy[] = [
  { id: 'w1', snapshotId: 's1', label: 'Draft A', status: 'ready', createdAt: 'now' },
  { id: 'w2', snapshotId: 's2', label: 'Draft B', status: 'ready', createdAt: 'now' },
];

function seeded() {
  const store = useWizardStore();
  store.accounts = accounts;
  store.snapshots = snapshots;
  store.workingCopies = workingCopies;
  return store;
}

describe('active-selection chain (FR-021/024) + persistence (FR-007)', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  it('keeps each branch intact when switching the active account and back (FR-024)', () => {
    const store = seeded();
    store.setActiveAccount('a1');
    store.setActiveSnapshot('s1');
    store.setActiveDraft('w1');
    expect(store.activeWorkingCopyId).toBe('w1');

    // switch to account a2 and pick its own branch
    store.setActiveAccount('a2');
    store.setActiveSnapshot('s2');
    store.setActiveDraft('w2');
    expect(store.activeWorkingCopyId).toBe('w2');

    // switching BACK to a1 restores a1's branch unchanged — no artifact destroyed
    store.setActiveAccount('a1');
    expect(store.activeSnapshotId).toBe('s1');
    expect(store.activeWorkingCopyId).toBe('w1');
    expect(store.activeWorkingCopy?.label).toBe('Draft A');
  });

  it('persists the chain to localStorage and rehydrates a fresh store (FR-007)', () => {
    const store = seeded();
    store.setActiveAccount('a1');
    store.setActiveSnapshot('s1');
    store.setActiveDraft('w1');
    store.goToStep('connect');

    expect(localStorage.getItem('wizard.activeChain')).toBeTruthy();

    // a fresh pinia + store should rehydrate the persisted chain
    setActivePinia(createPinia());
    const restored = useWizardStore();
    expect(restored.activeAccountId).toBe('a1');
    expect(restored.activeSnapshotId).toBe('s1');
    expect(restored.activeWorkingCopyId).toBe('w1');
  });

  it('setting a draft requires an active snapshot (no orphan selection)', () => {
    const store = seeded();
    store.setActiveAccount('a1');
    store.setActiveDraft('w1'); // no snapshot chosen yet → ignored
    expect(store.activeWorkingCopyId).toBeNull();
  });
});
