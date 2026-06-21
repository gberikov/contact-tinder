import BackupStep from '@/pages/wizard/BackupStep.vue';
import ConnectStep from '@/pages/wizard/ConnectStep.vue';
import DraftStep from '@/pages/wizard/DraftStep.vue';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/services/api', () => ({ api: {} }));

describe('wizard step consistency (FR-013/026/SC-008)', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  it('Connect step exposes a single primary action via the shadcn Button (indigo primary)', () => {
    const wrapper = mount(ConnectStep);
    const primary = wrapper.findAll('button').filter((b) => b.classes().includes('bg-primary'));
    expect(primary).toHaveLength(1);
    expect(primary[0].text()).toContain('Connect Google account');
  });

  it('Backup step uses shadcn Button + Input primitives with a clear primary action', () => {
    const wrapper = mount(BackupStep);
    expect(wrapper.find('input').exists()).toBe(true);
    const primary = wrapper.findAll('button').filter((b) => b.classes().includes('bg-primary'));
    expect(primary.some((b) => b.text().includes('Create backup'))).toBe(true);
  });

  it('Draft step uses shadcn Button + Input primitives with a clear primary action', () => {
    const wrapper = mount(DraftStep);
    expect(wrapper.find('input').exists()).toBe(true);
    const primary = wrapper.findAll('button').filter((b) => b.classes().includes('bg-primary'));
    expect(primary.some((b) => b.text().includes('Create draft'))).toBe(true);
  });
});
