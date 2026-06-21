import type { ValidationItem, ValidationRun } from '@/services/api';
import { useTidyStore } from '@/stores/tidy';
import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/services/api', () => ({
  api: {
    startValidationRun: vi.fn(),
    getValidationRun: vi.fn(),
    listValidationRuns: vi.fn(),
    listValidationItems: vi.fn(),
    resolveValidationItem: vi.fn(),
    skipValidationItem: vi.fn(),
    listAutoFixes: vi.fn(),
    undoStagedEdit: vi.fn(),
    detectRegion: vi.fn(),
  },
}));
import { api } from '@/services/api';

const run = (over: Partial<ValidationRun> = {}): ValidationRun => ({
  id: 'run-1',
  workingCopyId: 'wc-1',
  status: 'completed',
  defaultRegion: 'KZ',
  totalCount: 5,
  checkedCount: 5,
  autoAppliedCount: 3,
  queuedCount: 2,
  pendingCount: 2,
  createdAt: 'now',
  ...over,
});

const item = (over: Partial<ValidationItem> = {}): ValidationItem => ({
  id: 'i1',
  workingCopyContactId: 'c1',
  fieldKind: 'phone',
  fieldIndex: 0,
  issueType: 'unclear_type',
  originalValue: '+77272501234',
  status: 'pending',
  createdAt: 'now',
  ...over,
});

describe('tidy store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.mocked(api.getValidationRun).mockResolvedValue(run({ status: 'completed' }));
    vi.mocked(api.listValidationItems).mockResolvedValue([item()]);
    vi.mocked(api.listAutoFixes).mockResolvedValue([]);
  });
  afterEach(() => vi.restoreAllMocks());

  it('starts a run, polls to completion, and exposes a summary (US1)', async () => {
    vi.mocked(api.startValidationRun).mockResolvedValue(
      run({ status: 'running', pendingCount: 0 }),
    );
    const store = useTidyStore();
    store.region = 'KZ';

    await store.startRun('wc-1');

    expect(api.startValidationRun).toHaveBeenCalledWith('wc-1', 'KZ', undefined);
    expect(store.run?.status).toBe('completed');
    expect(store.summary).toEqual({ total: 5, checked: 5, auto: 3, queued: 2, pending: 2 });
    expect(store.pendingItems).toHaveLength(1);
  });

  it('computes progress percent from checked/total', () => {
    const store = useTidyStore();
    store.run = run({ status: 'running', totalCount: 200, checkedCount: 50 });
    expect(store.progressPct).toBe(25);
    store.run = run({ status: 'queued', totalCount: 0, checkedCount: 0 });
    expect(store.progressPct).toBe(0);
    store.run = run({ status: 'completed', totalCount: 0, checkedCount: 0 });
    expect(store.progressPct).toBe(100);
  });

  it('undoes a staged edit via undoStagedEdit (FR-022)', async () => {
    vi.mocked(api.undoStagedEdit).mockResolvedValue({ id: 'e1', status: 'undone' } as never);
    const store = useTidyStore();
    store.run = run();

    await store.undoEdit('e1');

    expect(api.undoStagedEdit).toHaveBeenCalledWith('e1');
    expect(api.getValidationRun).toHaveBeenCalled();
  });

  it('resolve and skip update the item and refresh the run', async () => {
    vi.mocked(api.resolveValidationItem).mockResolvedValue(
      item({ status: 'resolved', stagedEditId: 'e1' }),
    );
    vi.mocked(api.skipValidationItem).mockResolvedValue(item({ id: 'i2', status: 'skipped' }));
    const store = useTidyStore();
    store.run = run();
    store.items = [item(), item({ id: 'i2' })];

    await store.resolveItem('i1', { action: 'set_type', type: 'work' });
    expect(store.items.find((x) => x.id === 'i1')?.status).toBe('resolved');

    await store.skipItem('i2');
    expect(store.items.find((x) => x.id === 'i2')?.status).toBe('skipped');
    expect(store.pendingItems).toHaveLength(0);
  });
});
