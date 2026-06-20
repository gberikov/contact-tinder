import ExportReport from '@/components/ExportReport.vue';
import type { ExportReport as ExportReportT, ExportRun } from '@/services/api';
import { useExportStore } from '@/stores/export';
import { mount } from '@vue/test-utils';
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

function run(status: ExportRun['status'], report: Partial<ExportReportT> = {}): ExportRun {
  return {
    id: 'run-1',
    workingCopyId: 'wc-1',
    accountId: 'acc-1',
    sessionId: 's-1',
    deleteBatchId: 'db-1',
    labelBatchId: 'lb-1',
    status,
    undecidedCount: 0,
    createdAt: 'now',
    report: {
      deleted: 0,
      skippedAbsentDelete: 0,
      labeled: 0,
      skippedAbsentLabel: 0,
      failed: 0,
      excluded: 0,
      ...report,
    },
  };
}

describe('export run + report (US3)', () => {
  beforeEach(() => setActivePinia(createPinia()));
  afterEach(() => vi.restoreAllMocks());

  it('surfaces a re-consent error when confirm-delete is rejected for missing scope', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetchSequence([
        { status: 201, body: run('previewing') },
        { status: 403, body: { code: 'write_scope_required', message: 'scope required' } },
      ]),
    );
    const store = useExportStore();
    await store.start('wc-1');
    await expect(store.confirmDelete()).rejects.toThrow();
    expect(store.error).toContain('scope');
    expect(store.needsWriteScope).toBe(true);
  });

  it('builds a one-click re-consent URL that returns to the export screen', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetchSequence([
        {
          status: 200,
          body: { authorizationUrl: 'https://accounts.google.com/o/oauth2/auth?state=t|/x/export' },
        },
      ]),
    );
    const store = useExportStore();
    const url = await store.requestWriteConsent('/working-copies/wc-1/export');
    expect(url).toContain('accounts.google.com');
  });

  it('polls until the run reaches a terminal state', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetchSequence([
        { status: 201, body: run('previewing') },
        { status: 202, body: run('running') },
        { status: 200, body: run('running') },
        { status: 200, body: run('completed', { deleted: 1, labeled: 1 }) },
      ]),
    );
    const store = useExportStore();
    await store.start('wc-1');
    await store.confirmDelete();
    await store.pollUntilDone(0, 5);
    expect(store.isComplete).toBe(true);
    expect(store.report?.deleted).toBe(1);
  });

  it('renders report counts and enables undo entry points when batches are committed', () => {
    const r = run('completed', {
      deleted: 2,
      labeled: 3,
      deleteStatus: 'committed',
      labelStatus: 'committed',
    });
    const wrapper = mount(ExportReport, {
      props: { run: r, report: r.report, canUndoDelete: true, canUndoLabel: true },
    });
    expect(wrapper.text()).toContain('Deleted: 2');
    expect(wrapper.text()).toContain('Labeled: 3');
    const buttons = wrapper.findAll('button');
    expect(buttons).toHaveLength(2);
    expect(buttons.every((b) => !b.attributes('disabled'))).toBe(true);
  });
});
