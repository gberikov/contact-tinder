<script setup lang="ts">
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import ActiveSelector from '@/components/wizard/ActiveSelector.vue';
import ConfirmDialog from '@/components/wizard/ConfirmDialog.vue';
import type { SelectorItem } from '@/components/wizard/types';
import { api } from '@/services/api';
import { useWizardStore } from '@/stores/wizard';
import { computed, ref } from 'vue';

const wizard = useWizardStore();
const label = ref('');
const error = ref<string | null>(null);
const creating = ref(false);

const items = computed<SelectorItem[]>(() =>
  wizard.workingCopiesForActiveSnapshot.map((w) => ({
    id: w.id,
    title: w.label || `Draft ${w.id.slice(0, 8)}`,
    subtitle: w.contactCount != null ? `${w.contactCount} contacts` : undefined,
    status: w.status,
  })),
);

async function createDraft() {
  if (!wizard.activeSnapshotId) return;
  creating.value = true;
  error.value = null;
  try {
    const draft = await api.createWorkingCopy(wizard.activeSnapshotId, label.value || undefined);
    await wizard.loadWorkingCopies();
    wizard.setActiveDraft(draft.id);
    label.value = '';
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    creating.value = false;
  }
}

function select(id: string) {
  wizard.setActiveDraft(id);
}

const pending = ref<{ id: string; title: string } | null>(null);

function askDelete(id: string) {
  const draft = wizard.workingCopies.find((w) => w.id === id);
  pending.value = { id, title: draft?.label || `Draft ${id.slice(0, 8)}` };
}

async function confirmDelete() {
  if (!pending.value) return;
  const id = pending.value.id;
  pending.value = null;
  try {
    await wizard.deleteDraft(id);
  } catch (e) {
    error.value = (e as Error).message;
  }
}
</script>

<template>
  <div class="space-y-4">
    <p v-if="error" class="text-sm text-destructive">{{ error }}</p>
    <ActiveSelector
      :items="items"
      :active-id="wizard.activeWorkingCopyId"
      deletable
      empty-text="No drafts yet — create one to start editing safely."
      @select="select"
      @delete="askDelete"
    />

    <ConfirmDialog
      :open="pending !== null"
      :title="`Delete ${pending?.title ?? ''}?`"
      description="This deletes the draft and all its merge, review, and export data. This cannot be undone."
      confirm-text="Delete draft"
      @update:open="(v) => { if (!v) pending = null; }"
      @confirm="confirmDelete"
    />
    <div class="flex items-end gap-2">
      <div class="flex-1 space-y-1">
        <label class="text-xs font-medium text-muted-foreground" for="draft-label">
          New draft label (optional)
        </label>
        <Input id="draft-label" v-model="label" placeholder="e.g. First pass" />
      </div>
      <Button :disabled="creating || !wizard.activeSnapshotId" @click="createDraft">
        {{ creating ? 'Creating…' : 'Create draft' }}
      </Button>
    </div>
  </div>
</template>
