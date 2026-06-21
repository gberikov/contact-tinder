import type { Account, DedupRun, Snapshot, TriageSession, WorkingCopy } from '@/services/api';
import { useWizardStore } from '@/stores/wizard';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/services/api', () => ({ api: {} }));

const account = (over: Partial<Account> = {}): Account => ({
  id: 'a1',
  email: 'me@example.com',
  status: 'connected',
  grantedScopes: [],
  createdAt: 'now',
  ...over,
});
const snapshot = (over: Partial<Snapshot> = {}): Snapshot => ({
  id: 's1',
  accountId: 'a1',
  status: 'complete',
  source: 'google',
  workingCopyCount: 1,
  createdAt: 'now',
  ...over,
});
const workingCopy = (over: Partial<WorkingCopy> = {}): WorkingCopy => ({
  id: 'w1',
  snapshotId: 's1',
  label: 'Draft',
  status: 'ready',
  createdAt: 'now',
  ...over,
});
const dedupRun = (over: Partial<DedupRun> = {}): DedupRun => ({
  id: 'd1',
  workingCopyId: 'w1',
  status: 'completed',
  modelVersion: 'v1',
  confidenceFloor: 0.5,
  clusterCount: 3,
  createdAt: 'now',
  ...over,
});
const triage = (over: Partial<TriageSession> = {}): TriageSession => ({
  id: 't1',
  workingCopyId: 'w1',
  status: 'complete',
  createdAt: 'now',
  summary: { total: 10, decided: 10, keep: 5, delete: 3, processing: 2, remaining: 0 },
  ...over,
});

function fullChain() {
  const store = useWizardStore();
  store.accounts = [account()];
  store.snapshots = [snapshot()];
  store.workingCopies = [workingCopy()];
  store.activeAccountId = 'a1';
  store.snapshotByAccount = { a1: 's1' };
  store.workingCopyBySnapshot = { s1: 'w1' };
  store.dedupRuns = [dedupRun()];
  store.triageSessions = [triage()];
  return store;
}

describe('wizard step-state derivation', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  it('derives the active-selection chain from per-parent memory', () => {
    const store = fullChain();
    expect(store.activeSnapshotId).toBe('s1');
    expect(store.activeWorkingCopyId).toBe('w1');
    expect(store.activeAccount?.id).toBe('a1');
    expect(store.activeWorkingCopy?.id).toBe('w1');
  });

  it('marks connect/backup/draft/merge/review completed when their artifacts exist', () => {
    const store = fullChain();
    expect(store.completed('connect')).toBe(true);
    expect(store.completed('backup')).toBe(true);
    expect(store.completed('draft')).toBe(true);
    expect(store.completed('merge')).toBe(true);
    expect(store.completed('review')).toBe(true);
    expect(store.completed('export')).toBe(false);
  });

  it('leaves a step upcoming when its prerequisite artifact is missing', () => {
    const store = useWizardStore();
    store.accounts = [account()];
    store.activeAccountId = 'a1';
    // no snapshot selected yet
    expect(store.completed('connect')).toBe(true);
    expect(store.completed('backup')).toBe(false);
    expect(store.available('backup')).toBe(true); // connect is done → backup reachable
    expect(store.available('draft')).toBe(false); // backup not done → draft gated
    expect(store.displayState('draft')).toBe('upcoming');
  });

  it('treats a merge run with zero clusters as completed and emptyButPassable (FR-009)', () => {
    const store = fullChain();
    store.dedupRuns = [dedupRun({ clusterCount: 0 })];
    expect(store.completed('merge')).toBe(true);
    expect(store.emptyButPassable('merge')).toBe(true);
  });

  it('exposes exactly one current step and the rest as completed/upcoming', () => {
    const store = fullChain();
    store.currentStepKey = 'review';
    const states = store.stepStates;
    expect(states.filter((s) => s.displayState === 'current')).toHaveLength(1);
    expect(states.find((s) => s.key === 'review')?.displayState).toBe('current');
    expect(states.find((s) => s.key === 'connect')?.displayState).toBe('completed');
    expect(states.find((s) => s.key === 'export')?.displayState).toBe('upcoming');
  });
});
