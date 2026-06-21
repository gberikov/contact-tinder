import ExportPreview from '@/components/ExportPreview.vue';
import LabelPreview from '@/components/LabelPreview.vue';
import UndecidedWarning from '@/components/UndecidedWarning.vue';
import type { ExportContactSummary, ExportPreview as ExportPreviewT } from '@/services/api';
import { useExportStore } from '@/stores/export';
import { mount } from '@vue/test-utils';
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

function summary(id: string, name: string): ExportContactSummary {
  return { workingCopyContactId: id, displayName: name, primaryEmail: `${id}@x.io` };
}

const PREVIEW: ExportPreviewT = {
  workingCopyId: 'wc-1',
  sessionId: 's-1',
  deleteCount: 2,
  labelCount: 1,
  undecidedCount: 3,
  nothingToExport: false,
  labelName: 'Process',
  deleteSet: [summary('c1', 'Del One'), summary('c2', 'Del Two')],
  labelSet: [summary('c3', 'Proc Three')],
};

describe('export preview (US3)', () => {
  beforeEach(() => setActivePinia(createPinia()));
  afterEach(() => vi.restoreAllMocks());

  it('loads a preview into the store', async () => {
    vi.stubGlobal('fetch', mockFetch(200, PREVIEW));
    const store = useExportStore();
    await store.loadPreview('wc-1');
    expect(store.preview?.deleteCount).toBe(2);
    expect(store.hasUndecided).toBe(true);
    expect(store.nothingToExport).toBe(false);
  });

  it('renders the delete section with count and list', () => {
    const wrapper = mount(ExportPreview, {
      props: { count: PREVIEW.deleteCount, contacts: PREVIEW.deleteSet },
    });
    expect(wrapper.text()).toContain('2 contact(s) will be deleted');
    expect(wrapper.findAll('li')).toHaveLength(2);
    expect(wrapper.text()).toContain('Del One');
  });

  it('renders the label section with the label name', () => {
    const wrapper = mount(LabelPreview, {
      props: { count: PREVIEW.labelCount, labelName: 'Process', contacts: PREVIEW.labelSet },
    });
    expect(wrapper.text()).toContain('labeled “Process”');
    expect(wrapper.findAll('li')).toHaveLength(1);
  });

  it('shows the undecided warning only when there are undecided survivors', () => {
    const shown = mount(UndecidedWarning, { props: { count: 3 } });
    expect(shown.text()).toContain('excluded');
    const hidden = mount(UndecidedWarning, { props: { count: 0 } });
    expect(hidden.find('.undecided-warning').exists()).toBe(false);
  });

  it('flags the empty state when nothing is staged for either action', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetch(200, { ...PREVIEW, deleteCount: 0, labelCount: 0, nothingToExport: true }),
    );
    const store = useExportStore();
    await store.loadPreview('wc-1');
    expect(store.nothingToExport).toBe(true);
  });
});
