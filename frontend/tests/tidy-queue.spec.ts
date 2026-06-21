import TidyQueue from '@/components/tidy/TidyQueue.vue';
import TidyQueueItem from '@/components/tidy/TidyQueueItem.vue';
import type { ValidationItem } from '@/services/api';
import { useTidyStore } from '@/stores/tidy';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const item = (over: Partial<ValidationItem> = {}): ValidationItem => ({
  id: 'i1',
  workingCopyContactId: 'c1',
  contactDisplayName: 'Bob',
  fieldKind: 'phone',
  fieldIndex: 0,
  issueType: 'unclear_type',
  originalValue: '+77272501234',
  suggestedValue: '+77272501234',
  status: 'pending',
  createdAt: 'now',
  ...over,
});

describe('Tidy queue UI (US2)', () => {
  beforeEach(() => setActivePinia(createPinia()));

  it('renders one row per item', () => {
    const store = useTidyStore();
    store.items = [
      item(),
      item({ id: 'i2', issueType: 'website_unreachable', fieldKind: 'website' }),
    ];
    const wrapper = mount(TidyQueue);
    expect(wrapper.findAllComponents(TidyQueueItem)).toHaveLength(2);
  });

  it('an unclear-type item offers explicit type choices and emits resolve', async () => {
    const wrapper = mount(TidyQueueItem, { props: { item: item() } });
    const buttons = wrapper.findAll('button').filter((b) => b.text() === 'work');
    expect(buttons).toHaveLength(1);
    await buttons[0].trigger('click');
    expect(wrapper.emitted('resolve')?.[0]).toEqual([{ action: 'set_type', type: 'work' }]);
  });

  it('a broken value can be edited, removed, or skipped', async () => {
    const wrapper = mount(TidyQueueItem, {
      props: {
        item: item({
          issueType: 'website_unreachable',
          fieldKind: 'website',
          originalValue: 'http://dead/',
        }),
      },
    });
    await wrapper.find('button').trigger('click'); // first action button = Save
    expect(wrapper.emitted('resolve')).toBeTruthy();
  });

  it('resolved items expose undo', async () => {
    const wrapper = mount(TidyQueueItem, {
      props: { item: item({ status: 'resolved', stagedEditId: 'e1' }) },
    });
    const undo = wrapper.findAll('button').find((b) => b.text() === 'Undo');
    expect(undo).toBeTruthy();
    await undo?.trigger('click');
    expect(wrapper.emitted('undo')?.[0]).toEqual(['e1']);
  });
});
