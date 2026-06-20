<script setup lang="ts">
import type { ExportReport, ExportRun } from '@/services/api';

defineProps<{
  run: ExportRun;
  report: ExportReport;
  canUndoDelete: boolean;
  canUndoLabel: boolean;
}>();
const emit = defineEmits<{ (e: 'undo-delete'): void; (e: 'undo-label'): void }>();
</script>

<template>
  <div class="export-report">
    <h3>Export report — <span class="status">{{ run.status }}</span></h3>
    <ul class="counts">
      <li>Deleted: {{ report.deleted }}</li>
      <li>Already gone (delete): {{ report.skippedAbsentDelete }}</li>
      <li>Labeled: {{ report.labeled }}</li>
      <li>Already gone (label): {{ report.skippedAbsentLabel }}</li>
      <li>Failed: {{ report.failed }}</li>
      <li>Excluded: {{ report.excluded }}</li>
    </ul>
    <div class="actions">
      <button type="button" :disabled="!canUndoDelete" @click="emit('undo-delete')">
        Undo deletions
      </button>
      <button type="button" :disabled="!canUndoLabel" @click="emit('undo-label')">
        Remove “Process” label
      </button>
    </div>
  </div>
</template>

<style scoped>
.counts { list-style: none; padding: 0; display: grid; grid-template-columns: 1fr 1fr; gap: 4px; }
.status { text-transform: uppercase; font-weight: 600; }
.actions { display: flex; gap: 12px; margin-top: 12px; }
</style>
