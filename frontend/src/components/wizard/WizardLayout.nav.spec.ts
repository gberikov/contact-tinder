import { useWizardStore } from '@/stores/wizard';
import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { defineComponent, h, nextTick } from 'vue';
import { createMemoryHistory, createRouter } from 'vue-router';
import WizardLayout from './WizardLayout.vue';

const Stub = defineComponent({ render: () => h('div', 'stub') });

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/wizard',
        component: WizardLayout,
        children: [
          { path: 'connect', name: 'connect', component: Stub },
          { path: 'backup', name: 'backup', component: Stub },
          { path: 'draft', name: 'draft', component: Stub },
          { path: 'merge', name: 'merge', component: Stub },
          { path: 'review', name: 'review', component: Stub },
          { path: 'export', name: 'export', component: Stub },
        ],
      },
    ],
  });
}

describe('WizardLayout Continue navigation', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  it('Continue on Review navigates to Tidy (merge complete, triage incomplete)', async () => {
    const store = useWizardStore();
    vi.spyOn(store, 'hydrate').mockResolvedValue();
    // Merge complete so Review is reachable; triage NOT complete (passable('review') is what carries).
    store.dedupRuns = [
      {
        id: 'r1',
        workingCopyId: 'w1',
        status: 'completed',
        modelVersion: 'v',
        confidenceFloor: 0,
        createdAt: '',
      },
    ];
    store.triageSessions = [];

    const router = makeRouter();
    await router.push('/wizard/review');
    await router.isReady();

    const wrapper = mount(WizardLayout, { global: { plugins: [router] } });
    await nextTick();
    await nextTick();
    expect(store.currentStepKey).toBe('review');

    const continueBtn = wrapper.findAll('button').find((b) => b.text().includes('Continue'));
    expect(continueBtn, 'Continue button not found').toBeTruthy();
    expect(continueBtn?.attributes('disabled')).toBeUndefined();

    await continueBtn?.trigger('click');
    await flushPromises();
    await nextTick();

    expect(router.currentRoute.value.path).toBe('/wizard/tidy');
    expect(store.currentStepKey).toBe('tidy');
  });
});
