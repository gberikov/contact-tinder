import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useWizardStore } from './wizard';

function seedChain(store: ReturnType<typeof useWizardStore>) {
  store.accounts = [
    { id: 'a1', email: 'x', status: 'connected', grantedScopes: [], createdAt: '' },
  ];
  store.snapshots = [
    {
      id: 's1',
      accountId: 'a1',
      status: 'complete',
      source: 'x',
      workingCopyCount: 1,
      createdAt: '',
    },
    {
      id: 's2',
      accountId: 'a1',
      status: 'complete',
      source: 'x',
      workingCopyCount: 0,
      createdAt: '',
    },
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
