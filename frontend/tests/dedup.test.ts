import type { Cluster, DedupRun } from '@/services/api';
import { useDedupStore } from '@/stores/dedup';
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

const RUN: DedupRun = {
  id: 'run-1',
  workingCopyId: 'wc-1',
  status: 'completed',
  modelVersion: 'contacts-v1',
  confidenceFloor: 0.5,
  clusterCount: 2,
  createdAt: 'now',
};

function cluster(id: string, confidence: number): Cluster {
  return {
    id,
    dedupRunId: 'run-1',
    workingCopyId: 'wc-1',
    confidence,
    size: 2,
    status: 'pending',
    members: [
      {
        id: `${id}-m1`,
        workingCopyContactId: `${id}-c1`,
        isSurvivor: false,
        contact: { displayName: 'John Smith', primaryPhone: '+1', status: 'active' },
      },
      {
        id: `${id}-m2`,
        workingCopyContactId: `${id}-c2`,
        isSurvivor: false,
        contact: { displayName: 'Jon Smith', primaryPhone: '+1', status: 'active' },
      },
    ],
  };
}

describe('dedup store', () => {
  beforeEach(() => setActivePinia(createPinia()));
  afterEach(() => vi.restoreAllMocks());

  it('starts a run and loads clusters sorted by confidence (FR-011)', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetchSequence([
        { status: 202, body: RUN },
        { status: 200, body: [cluster('a', 0.7), cluster('b', 0.95)] },
      ]),
    );
    const store = useDedupStore();
    await store.startRun('wc-1');
    expect(store.run?.status).toBe('completed');
    expect(store.pendingClusters.map((c) => c.id)).toEqual(['b', 'a']);
  });

  it('removes a cluster from the pending list after merge (single confirmation)', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetchSequence([
        { status: 202, body: RUN },
        { status: 200, body: [cluster('a', 0.9)] },
        {
          status: 200,
          body: {
            mergeRecordId: 'mr',
            survivorContactId: 'a-c1',
            clusterId: 'a',
            retiredContactIds: ['a-c2'],
          },
        },
      ]),
    );
    const store = useDedupStore();
    await store.startRun('wc-1');
    expect(store.pendingClusters).toHaveLength(1);
    await store.merge('a', 'a-c1');
    expect(store.pendingClusters).toHaveLength(0);
  });

  it('removes a cluster after dismiss', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetchSequence([
        { status: 202, body: RUN },
        { status: 200, body: [cluster('a', 0.9)] },
        { status: 200, body: { ...cluster('a', 0.9), status: 'dismissed' } },
      ]),
    );
    const store = useDedupStore();
    await store.startRun('wc-1');
    await store.dismiss('a');
    expect(store.pendingClusters).toHaveLength(0);
  });
});
