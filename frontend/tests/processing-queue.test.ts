import type { ProcessingItem, TriageSession } from '@/services/api';
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

const SESSION: TriageSession = {
  id: 's-1',
  workingCopyId: 'wc-1',
  status: 'in_progress',
  createdAt: 'now',
  summary: { total: 1, decided: 1, keep: 0, delete: 0, processing: 1, remaining: 0 },
};

function item(id: string): ProcessingItem {
  return {
    id,
    sessionId: 's-1',
    workingCopyContactId: `${id}-c`,
    wantsEdit: false,
    wantsTransliterate: true,
    status: 'pending',
    contact: { displayName: 'Boris', status: 'active', payload: {} },
    transliterationSuggestion: { hasSuggestion: true, fields: { givenName: 'Борис' } },
  };
}

describe('triage store — processing (US2)', () => {
  beforeEach(() => setActivePinia(createPinia()));
  afterEach(() => vi.restoreAllMocks());

  it('loads the queue and removes an item when marked done', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetchSequence([
        { status: 200, body: [item('p1'), item('p2')] },
        { status: 200, body: { ...item('p1'), status: 'done' } },
      ]),
    );
    const store = useTriageStore();
    store.session = SESSION;
    await store.loadProcessing();
    expect(store.processing).toHaveLength(2);
    await store.completeProcessing('p1');
    expect(store.processing.map((p) => p.id)).toEqual(['p2']);
  });
});
