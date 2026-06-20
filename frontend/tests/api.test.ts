import { ApiError, api } from '@/services/api';
import { useSnapshotsStore } from '@/stores/snapshots';
import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

function mockFetch(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    statusText: 'x',
    json: async () => body,
  });
}

describe('api client', () => {
  afterEach(() => vi.restoreAllMocks());

  it('lists snapshots', async () => {
    vi.stubGlobal('fetch', mockFetch(200, [{ id: 's1', status: 'complete' }]));
    const result = await api.listSnapshots();
    expect(result[0].id).toBe('s1');
  });

  it('maps error bodies to ApiError with code/status', async () => {
    vi.stubGlobal('fetch', mockFetch(409, { code: 'conflict', message: 'has working copies' }));
    await expect(api.deleteSnapshot('s1')).rejects.toBeInstanceOf(ApiError);
  });
});

describe('snapshots store', () => {
  beforeEach(() => setActivePinia(createPinia()));
  afterEach(() => vi.restoreAllMocks());

  it('surfaces a 409 on delete instead of removing the snapshot', async () => {
    vi.stubGlobal('fetch', mockFetch(409, { code: 'conflict', message: 'has working copies' }));
    const store = useSnapshotsStore();
    store.snapshots = [{ id: 's1', status: 'complete', workingCopyCount: 1 } as never];
    await expect(store.remove('s1')).rejects.toBeInstanceOf(ApiError);
    expect(store.snapshots).toHaveLength(1);
  });
});
