import type { DeckPage, TriageSession } from '@/services/api';
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

function session(remaining: number): TriageSession {
  return {
    id: 's-1',
    workingCopyId: 'wc-1',
    status: 'in_progress',
    createdAt: 'now',
    summary: { total: 2, decided: 2 - remaining, keep: 0, delete: 0, processing: 0, remaining },
  };
}

const deck: DeckPage = {
  cards: [
    { workingCopyContactId: 'c1', contact: { displayName: 'Anna', status: 'active', payload: {} } },
    {
      workingCopyContactId: 'c2',
      contact: { displayName: 'Boris', status: 'active', payload: {} },
    },
  ],
  nextCursor: null,
};

describe('triage store — swipe (US1)', () => {
  beforeEach(() => setActivePinia(createPinia()));
  afterEach(() => vi.restoreAllMocks());

  it('opens a session and shows the first card in order', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetchSequence([
        { status: 201, body: session(2) },
        { status: 200, body: deck },
      ]),
    );
    const store = useTriageStore();
    await store.open('wc-1');
    expect(store.currentCard?.contact.displayName).toBe('Anna');
    expect(store.summary?.remaining).toBe(2);
  });

  it('optimistically advances on a decision then persists it', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetchSequence([
        { status: 201, body: session(2) },
        { status: 200, body: deck },
        {
          status: 200,
          body: {
            id: 'd1',
            sessionId: 's-1',
            workingCopyContactId: 'c1',
            outcome: 'keep',
            decidedAt: 'now',
          },
        },
        { status: 200, body: session(1) },
      ]),
    );
    const store = useTriageStore();
    await store.open('wc-1');
    await store.decide('keep');
    expect(store.currentCard?.contact.displayName).toBe('Boris'); // advanced
    expect(store.summary?.remaining).toBe(1);
  });

  it('undoes the last decision (keyboard ↓ / U) and reloads the deck', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetchSequence([
        { status: 201, body: session(2) },
        { status: 200, body: deck },
        {
          status: 200,
          body: {
            id: 'd1',
            sessionId: 's-1',
            workingCopyContactId: 'c1',
            outcome: 'keep',
            decidedAt: 'now',
          },
        },
        { status: 200, body: session(1) },
        { status: 204, body: null }, // undoDecision
        { status: 200, body: session(2) },
        { status: 200, body: deck },
      ]),
    );
    const store = useTriageStore();
    await store.open('wc-1');
    await store.decide('keep');
    await store.undoLast();
    expect(store.currentCard?.contact.displayName).toBe('Anna'); // back to the start
    expect(store.summary?.remaining).toBe(2);
    expect(store.lastDecided).toBeNull();
  });
});
