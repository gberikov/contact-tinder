<script setup lang="ts">
import { Button } from '@/components/ui/button';
import ActiveSelector from '@/components/wizard/ActiveSelector.vue';
import ConfirmDialog from '@/components/wizard/ConfirmDialog.vue';
import type { SelectorItem } from '@/components/wizard/types';
import { api } from '@/services/api';
import { useWizardStore } from '@/stores/wizard';
import { computed, ref } from 'vue';

const wizard = useWizardStore();
const error = ref<string | null>(null);
const pending = ref<{ id: string; email: string } | null>(null);

const items = computed<SelectorItem[]>(() =>
  wizard.accounts.map((a) => ({
    id: a.id,
    title: a.email,
    status: a.status,
    statusVariant:
      a.status === 'connected'
        ? 'success'
        : a.status === 'needs_reauth'
          ? 'destructive'
          : 'secondary',
  })),
);

const confirmText = computed(() => {
  if (!pending.value) return '';
  const snaps = wizard.snapshotCountForAccount(pending.value.id);
  const drafts = wizard.draftCountForAccount(pending.value.id);
  const tail =
    snaps === 0
      ? 'It has no backups.'
      : `This also deletes ${snaps} backup(s) and ${drafts} draft(s), with all their merge, review, and export data.`;
  return `${tail} This cannot be undone.`;
});

async function connect() {
  try {
    const { authorizationUrl } = await api.connect();
    window.location.href = authorizationUrl;
  } catch (e) {
    error.value = (e as Error).message;
  }
}

function select(id: string) {
  wizard.setActiveAccount(id);
}

function askDelete(id: string) {
  const account = wizard.accounts.find((a) => a.id === id);
  if (account) pending.value = { id, email: account.email };
}

async function confirmDelete() {
  if (!pending.value) return;
  const id = pending.value.id;
  pending.value = null;
  try {
    await wizard.deleteAccount(id);
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
      :active-id="wizard.activeAccountId"
      deletable
      empty-text="No Google accounts connected yet."
      @select="select"
      @delete="askDelete"
    />
    <Button @click="connect">Connect Google account</Button>

    <ConfirmDialog
      :open="pending !== null"
      :title="`Delete ${pending?.email ?? ''}?`"
      :description="confirmText"
      confirm-text="Delete account"
      @update:open="(v) => { if (!v) pending = null; }"
      @confirm="confirmDelete"
    />
  </div>
</template>
