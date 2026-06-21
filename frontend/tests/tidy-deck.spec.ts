import TidyAutoFixes from '@/components/tidy/TidyAutoFixes.vue';
import TidyDeck from '@/components/tidy/TidyDeck.vue';
import TidyQueueItem from '@/components/tidy/TidyQueueItem.vue';
import type { AutoFix, ValidationItem } from '@/services/api';
import { useTidyStore } from '@/stores/tidy';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const item = (over: Partial<ValidationItem> = {}): ValidationItem => ({
  id: 'i1',
  workingCopyContactId: 'c1',
  contactDisplayName: 'Bob',
  fieldKind: 'email',
  fieldIndex: 0,
  issueType: 'dead_email_domain',
  detail: "Domain 'gmial.com' does not exist",
  originalValue: 'bob@gmial.com',
  status: 'pending',
  createdAt: 'now',
  ...over,
});

describe('Tidy deck (one card at a time)', () => {
  beforeEach(() => setActivePinia(createPinia()));

  it('shows only the head pending item as a single card', () => {
    const store = useTidyStore();
    store.items = [item(), item({ id: 'i2' }), item({ id: 'i3' })];
    const wrapper = mount(TidyDeck);
    expect(wrapper.findAllComponents(TidyQueueItem)).toHaveLength(1);
    expect(wrapper.text()).toContain('3 to review');
  });

  it('shows the specific reason detail on the card', () => {
    const store = useTidyStore();
    store.items = [item()];
    const wrapper = mount(TidyDeck);
    expect(wrapper.text()).toContain('does not exist');
  });

  it('shows an empty state when nothing is pending', () => {
    const store = useTidyStore();
    store.items = [item({ status: 'resolved' })];
    const wrapper = mount(TidyDeck);
    expect(wrapper.findAllComponents(TidyQueueItem)).toHaveLength(0);
    expect(wrapper.text()).toContain('All issues reviewed');
  });
});

describe('Tidy auto-fixed list', () => {
  beforeEach(() => setActivePinia(createPinia()));

  const fix = (over: Partial<AutoFix> = {}): AutoFix => ({
    stagedEditId: 'e1',
    workingCopyContactId: 'c1',
    contactDisplayName: 'Bob',
    fieldKind: 'phone',
    before: '+7 (701) 722-15-02',
    after: '+77017221502',
    createdAt: 'now',
    ...over,
  });

  it('lists fixes with before→after and Undo', async () => {
    const store = useTidyStore();
    store.autoFixes = [fix(), fix({ stagedEditId: 'e2', fieldKind: 'website' })];
    const undo = vi.spyOn(store, 'undoEdit').mockResolvedValue();
    const wrapper = mount(TidyAutoFixes);
    expect(wrapper.text()).toContain('+77017221502');
    const undoBtn = wrapper.findAll('button').find((b) => b.text() === 'Undo');
    await undoBtn?.trigger('click');
    expect(undo).toHaveBeenCalledWith('e1');
  });
});
