import WizardStepper from '@/components/wizard/WizardStepper.vue';
import { mount } from '@vue/test-utils';
import { createPinia } from 'pinia';
import { describe, expect, it, vi } from 'vitest';
import { createMemoryHistory, createRouter } from 'vue-router';

vi.mock('@/services/api', () => ({ api: {} }));

const router = createRouter({
  history: createMemoryHistory(),
  routes: [{ path: '/:rest(.*)*', component: { template: '<div />' } }],
});

describe('WizardStepper render (regression: reka-ui Separator needs StepperItem context)', () => {
  it('mounts and shows all six step labels without throwing', () => {
    const wrapper = mount(WizardStepper, {
      global: { plugins: [createPinia(), router] },
    });
    const text = wrapper.text();
    for (const label of ['Connect', 'Backup', 'Draft', 'Merge', 'Review', 'Export']) {
      expect(text).toContain(label);
    }
  });
});
