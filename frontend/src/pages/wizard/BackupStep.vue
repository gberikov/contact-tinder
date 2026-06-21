<script setup lang="ts">
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import ActiveSelector from '@/components/wizard/ActiveSelector.vue';
import type { SelectorItem } from '@/components/wizard/types';
import { api } from '@/services/api';
import { useWizardStore } from '@/stores/wizard';
import { computed, ref } from 'vue';

const wizard = useWizardStore();
const label = ref('');
const error = ref<string | null>(null);
const creating = ref(false);

const items = computed<SelectorItem[]>(() =>
  wizard.snapshotsForActiveAccount.map((s) => ({
    id: s.id,
    title: s.label || `Backup ${s.id.slice(0, 8)}`,
    subtitle: s.contactCount != null ? `${s.contactCount} contacts` : undefined,
    status: s.status,
    statusVariant:
      s.status === 'complete' ? 'success' : s.status === 'failed' ? 'destructive' : 'secondary',
  })),
);

async function createBackup() {
  if (!wizard.activeAccountId) return;
  creating.value = true;
  error.value = null;
  try {
    const snap = await api.createSnapshot(wizard.activeAccountId, label.value || undefined);
    await wizard.loadSnapshots();
    wizard.setActiveSnapshot(snap.id);
    label.value = '';
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    creating.value = false;
  }
}

function select(id: string) {
  wizard.setActiveSnapshot(id);
}
</script>

<template>
  <div class="space-y-4">
    <p v-if="error" class="text-sm text-destructive">{{ error }}</p>
    <ActiveSelector
      :items="items"
      :active-id="wizard.activeSnapshotId"
      empty-text="No backups yet — create one to freeze your contacts."
      @select="select"
    />
    <div class="flex items-end gap-2">
      <div class="flex-1 space-y-1">
        <label class="text-xs font-medium text-muted-foreground" for="backup-label">
          New backup label (optional)
        </label>
        <Input id="backup-label" v-model="label" placeholder="e.g. Cleanup June" />
      </div>
      <Button :disabled="creating || !wizard.activeAccountId" @click="createBackup">
        {{ creating ? 'Creating…' : 'Create backup' }}
      </Button>
    </div>
  </div>
</template>
