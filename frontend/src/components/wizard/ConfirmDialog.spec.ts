import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import { defineComponent, nextTick, ref } from 'vue';
import ConfirmDialog from './ConfirmDialog.vue';

function findButton(label: string): HTMLButtonElement | undefined {
  return Array.from(document.querySelectorAll('button')).find((b) =>
    b.textContent?.includes(label),
  ) as HTMLButtonElement | undefined;
}

describe('ConfirmDialog', () => {
  function open(props: Record<string, unknown> = {}) {
    return mount(ConfirmDialog, {
      props: { open: true, title: 'Delete X?', description: 'desc', ...props },
      attachTo: document.body,
    });
  }

  it('emits confirm when the action button is clicked', async () => {
    const wrapper = open({ confirmText: 'Delete it' });
    await nextTick();
    await nextTick();

    findButton('Delete it')?.click();
    await nextTick();

    expect(wrapper.emitted('confirm')).toBeTruthy();
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

  // Regression: the destructive action must NOT also close the dialog via reka's DialogClose.
  // It did, and reka emits update:open BEFORE confirm — so the parent's `@update:open` handler
  // (which clears the pending target) ran first and confirmDelete then saw a null target and
  // bailed: clicking Delete deleted nothing and fired no request. The confirm handler must still
  // see the pending target intact.
  it('delivers confirm with the pending target intact (no update:open race)', async () => {
    const captured: string[] = [];
    const Harness = defineComponent({
      components: { ConfirmDialog },
      setup() {
        const pending = ref<{ id: string } | null>({ id: 'target-1' });
        function onConfirm() {
          if (pending.value) captured.push(pending.value.id);
          pending.value = null;
        }
        function onUpdateOpen(v: boolean) {
          if (!v) pending.value = null;
        }
        return { pending, onConfirm, onUpdateOpen };
      },
      template: `<ConfirmDialog :open="pending !== null" title="t" description="d"
        @update:open="onUpdateOpen" @confirm="onConfirm" />`,
    });

    mount(Harness, { attachTo: document.body });
    await nextTick();
    await nextTick();

    findButton('Delete')?.click();
    await nextTick();

    expect(captured).toEqual(['target-1']);
  });
});
