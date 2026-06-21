<script setup lang="ts">
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import ActiveSelector from '@/components/wizard/ActiveSelector.vue';
import ConfirmDialog from '@/components/wizard/ConfirmDialog.vue';
import type { SelectorItem } from '@/components/wizard/types';
import { api } from '@/services/api';
import { useWizardStore } from '@/stores/wizard';
import { computed, onMounted, ref, watch } from 'vue';

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

const importing = computed(() => wizard.running('backup'));
const progress = computed(() => wizard.backupProgress);

// Start polling whenever the active backup is still importing (on entry or after switching).
function maybePoll() {
  if (importing.value) wizard.pollBackupJob();
}
onMounted(maybePoll);
watch(() => wizard.activeSnapshotId, maybePoll);

async function createBackup() {
  if (!wizard.activeAccountId) return;
  creating.value = true;
  error.value = null;
  try {
    const snap = await api.createSnapshot(wizard.activeAccountId, label.value || undefined);
    await wizard.loadSnapshots();
    wizard.setActiveSnapshot(snap.id);
    label.value = '';
    wizard.pollBackupJob(); // live progress for the fresh import
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    creating.value = false;
  }
}

function select(id: string) {
  wizard.setActiveSnapshot(id);
}

const pending = ref<{ id: string; title: string } | null>(null);

const confirmText = computed(() => {
  if (!pending.value) return '';
  const drafts = wizard.draftCountForSnapshot(pending.value.id);
  const tail =
    drafts === 0
      ? 'It has no drafts.'
      : `This also deletes ${drafts} draft(s), with all their merge, review, and export data.`;
  return `${tail} This cannot be undone.`;
});

function askDelete(id: string) {
  const snapshot = wizard.snapshots.find((s) => s.id === id);
  pending.value = { id, title: snapshot?.label || `Backup ${id.slice(0, 8)}` };
}

async function confirmDelete() {
  if (!pending.value) return;
  const id = pending.value.id;
  pending.value = null;
  try {
    await wizard.removeSnapshot(id);
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
      :active-id="wizard.activeSnapshotId"
      deletable
      empty-text="No backups yet — create one to freeze your contacts."
      @select="select"
      @delete="askDelete"
    />

    <ConfirmDialog
      :open="pending !== null"
      :title="`Delete ${pending?.title ?? ''}?`"
      :description="confirmText"
      confirm-text="Delete backup"
      @update:open="(v) => { if (!v) pending = null; }"
      @confirm="confirmDelete"
    />

    <!-- Live import progress (FR-029): "230 / 2475 (9%)" + bar -->
    <div v-if="importing && progress" class="space-y-1.5">
      <div class="flex items-center justify-between text-sm">
        <span class="text-muted-foreground">Loading contacts from Google…</span>
        <span class="tabular-nums font-medium">
          {{ progress.fetched.toLocaleString() }}<template v-if="progress.total">
            / {{ progress.total.toLocaleString() }}</template>
          <template v-if="progress.pct != null"> ({{ progress.pct }}%)</template>
        </span>
      </div>
      <div class="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          class="h-full rounded-full bg-primary transition-all duration-500"
          :class="progress.pct == null ? 'w-2/5 animate-pulse' : ''"
          :style="progress.pct != null ? { width: `${progress.pct}%` } : undefined"
        />
      </div>
    </div>

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
