import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import { nextTick } from 'vue';
import ConfirmDialog from './ConfirmDialog.vue';

// Regression: the AlertDialog wrapper must forward reka-ui's `update:open` emit so a controlled
// dialog actually closes — both the Cancel button and the destructive Action render reka-ui's
// DialogClose, which closes via `update:open(false)`. A wrapper that drops that emit leaves the
// buttons looking dead (the dialog never closes). See AlertDialog.vue's useForwardPropsEmits.
describe('ConfirmDialog', () => {
  function open(props: Record<string, unknown> = {}) {
    return mount(ConfirmDialog, {
      props: { open: true, title: 'Delete X?', description: 'desc', ...props },
      attachTo: document.body,
    });
  }

  function findButton(label: string): HTMLButtonElement | undefined {
    return Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes(label),
    ) as HTMLButtonElement | undefined;
  }

  it('emits confirm and update:open(false) when the action button is clicked', async () => {
    const wrapper = open({ confirmText: 'Delete it' });
    await nextTick();
    await nextTick();

    findButton('Delete it')?.click();
    await nextTick();

    expect(wrapper.emitted('confirm')).toBeTruthy();
    expect(wrapper.emitted('update:open')?.at(-1)).toEqual([false]);
    wrapper.unmount();
  });

  it('emits update:open(false) when the cancel button is clicked', async () => {
    const wrapper = open();
    await nextTick();
    await nextTick();

    findButton('Cancel')?.click();
    await nextTick();

    expect(wrapper.emitted('update:open')?.at(-1)).toEqual([false]);
    expect(wrapper.emitted('confirm')).toBeFalsy();
    wrapper.unmount();
  });
});
