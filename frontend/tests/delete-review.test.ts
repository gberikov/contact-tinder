import type { DeleteBatch, DeletionRecord } from '@/services/api';
import { useTriageStore } from '@/stores/triage';
import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

function mockFetchSequence(responses: Array<{ status: number; body: unknown }>) {
  const fn = vi.fn();
  for (const r of responses) {
    fn.mockResolvedValueOnce({
      ok: r.status >= 200 && r.status < 300,
      status: r.status,
      statusText: 'x',
      json: async () => r.body,
    });
  }
  return fn;
}

function batch(status: DeleteBatch['status']): DeleteBatch {
  return {
    id: 'b-1',
    workingCopyId: 'wc-1',
    accountId: 'acc-1',
    status,
    totalCount: 1,
    deletedCount: 0,
    failedCount: 0,
    createdAt: 'now',
  };
}

const records: DeletionRecord[] = [
  {
    id: 'r1',
    workingCopyContactId: 'c1',
    status: 'pending',
    contact: { displayName: 'Del One', status: 'active', payload: {} },
  },
];

describe('triage store — delete review (US3)', () => {
  beforeEach(() => setActivePinia(createPinia()));
  afterEach(() => vi.restoreAllMocks());

  it('builds a batch with a dry-run preview', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetchSequence([
        { status: 201, body: batch('staged') },
        { status: 200, body: records },
      ]),
    );
    const store = useTriageStore();
    await store.buildDeleteBatch('wc-1');
    expect(store.batch?.status).toBe('staged');
    expect(store.preview).toHaveLength(1);
  });

  it('surfaces a re-consent error when confirm is rejected for missing scope', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetchSequence([
        { status: 201, body: batch('staged') },
        { status: 200, body: records },
        { status: 403, body: { code: 'write_scope_required', message: 'scope required' } },
      ]),
    );
    const store = useTriageStore();
    await store.buildDeleteBatch('wc-1');
    await expect(store.confirmDelete()).rejects.toThrow();
    expect(store.error).toContain('scope');
  });
});
