import type {
  Account,
  DedupRun,
  ExportRun,
  ImportJob,
  Snapshot,
  WorkingCopy,
} from '@/services/api';
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
const snapshot = (over: Partial<Snapshot> = {}): Snapshot => ({
  id: 's1',
  accountId: 'a1',
  status: 'complete',
  source: 'google',
  workingCopyCount: 1,
  createdAt: 'now',
  ...over,
});
const workingCopy: WorkingCopy = {
  id: 'w1',
  snapshotId: 's1',
  label: 'Draft',
  status: 'ready',
  createdAt: 'now',
};

function chain() {
  const store = useWizardStore();
  store.accounts = [account];
  store.snapshots = [snapshot()];
  store.workingCopies = [workingCopy];
  store.activeAccountId = 'a1';
  store.snapshotByAccount = { a1: 's1' };
  store.workingCopyBySnapshot = { s1: 'w1' };
  return store;
}

describe('wizard running state for long jobs (FR-025)', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  it('shows Backup running while the import job runs, then completed', () => {
    const store = chain();
    store.snapshots = [snapshot({ status: 'importing' })];
    store.importJob = { snapshotId: 's1', status: 'running', fetchedCount: 10 } as ImportJob;
    expect(store.running('backup')).toBe(true);
    expect(store.displayState('backup')).toBe('running');

    // job finishes
    store.snapshots = [snapshot({ status: 'complete' })];
    store.importJob = { snapshotId: 's1', status: 'completed', fetchedCount: 20 } as ImportJob;
    expect(store.running('backup')).toBe(false);
    expect(store.completed('backup')).toBe(true);
  });

  it('shows Merge running while the dedup run runs', () => {
    const store = chain();
    store.dedupRuns = [{ status: 'running' } as DedupRun];
    expect(store.running('merge')).toBe(true);
    expect(store.displayState('merge')).toBe('running');
  });

  it('shows Export running while the export run runs, then completed', () => {
    const store = chain();
    store.exportRun = { status: 'running' } as ExportRun;
    expect(store.running('export')).toBe(true);
    expect(store.displayState('export')).toBe('running');

    store.exportRun = { status: 'completed' } as ExportRun;
    expect(store.running('export')).toBe(false);
    expect(store.completed('export')).toBe(true);
  });

  it('running overrides current in the display state', () => {
    const store = chain();
    store.currentStepKey = 'merge';
    store.dedupRuns = [{ status: 'running' } as DedupRun];
    expect(store.displayState('merge')).toBe('running');
  });
});
