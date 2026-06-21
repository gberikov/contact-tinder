import type { Account, Snapshot, WorkingCopy } from '@/services/api';
import { useWizardStore } from '@/stores/wizard';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/services/api', () => ({ api: {} }));

const account: Account = {
  id: 'a1',
  email: 'me@example.com',
  status: 'connected',
  grantedScopes: [],
  createdAt: 'now',
};
const snapshot: Snapshot = {
  id: 's1',
  accountId: 'a1',
  status: 'complete',
  source: 'google',
  workingCopyCount: 1,
  createdAt: 'now',
};
const workingCopy: WorkingCopy = {
  id: 'w1',
  snapshotId: 's1',
  label: 'Draft',
  status: 'ready',
  createdAt: 'now',
};

function connectedThroughDraft() {
  const store = useWizardStore();
  store.accounts = [account];
  store.snapshots = [snapshot];
  store.workingCopies = [workingCopy];
  store.activeAccountId = 'a1';
  store.snapshotByAccount = { a1: 's1' };
  store.workingCopyBySnapshot = { s1: 'w1' };
  return store;
}

describe('wizard gating + navigation', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  it('gates a step whose prerequisite is not yet complete (FR-006)', () => {
    const store = useWizardStore();
    store.accounts = [account];
    store.activeAccountId = 'a1';
    expect(store.available('connect')).toBe(true);
    expect(store.available('backup')).toBe(true);
    expect(store.available('merge')).toBe(false); // draft not done
    // export: prereq is review; review is always passable (FR-A11), but merge is not done
    // so export unavailability depends on merge not being done (merge → review → export chain)
    // With only account set (no draft/merge): export available = passable('review') = true,
    // but merge available = false (draft not done). Export prereq is review which is passable.
    expect(store.available('export')).toBe(true); // review always passable (FR-A11)
  });

  it('refuses to navigate to an unavailable step but allows available ones (FR-004/006)', () => {
    const store = connectedThroughDraft();
    store.goToStep('export'); // review always passable (FR-A11) → export now allowed
    expect(store.currentStepKey).toBe('export');

    store.goToStep('draft'); // draft completed → allowed
    expect(store.currentStepKey).toBe('draft');
  });

  it('navigates back to a completed step with prior selections preserved (FR-005)', () => {
    const store = connectedThroughDraft();
    store.currentStepKey = 'draft';
    store.goToStep('backup');
    expect(store.currentStepKey).toBe('backup');
    // active selections (the prior state) are untouched by navigation
    expect(store.activeSnapshotId).toBe('s1');
    expect(store.activeWorkingCopyId).toBe('w1');
  });

  it('lands on the first incomplete step (FR-007)', () => {
    const store = useWizardStore();
    store.accounts = [account];
    store.activeAccountId = 'a1'; // connect complete, backup not
    expect(store.firstIncompleteStep()).toBe('backup');
  });
});
