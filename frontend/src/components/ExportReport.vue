<script setup lang="ts">
import { Button } from '@/components/ui/button';
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
  <div class="space-y-3">
    <h3 class="font-medium">
      Export report — <span class="font-semibold uppercase">{{ run.status }}</span>
    </h3>
    <ul class="grid grid-cols-2 gap-1 text-sm text-muted-foreground">
      <li>Deleted: {{ report.deleted }}</li>
      <li>Already gone (delete): {{ report.skippedAbsentDelete }}</li>
      <li>Labeled: {{ report.labeled }}</li>
      <li>Already gone (label): {{ report.skippedAbsentLabel }}</li>
      <li>Failed: {{ report.failed }}</li>
      <li>Excluded: {{ report.excluded }}</li>
    </ul>
    <div class="flex gap-3">
      <Button variant="outline" size="sm" :disabled="!canUndoDelete" @click="emit('undo-delete')">
        Undo deletions
      </Button>
      <Button variant="outline" size="sm" :disabled="!canUndoLabel" @click="emit('undo-label')">
        Remove “Process” label
      </Button>
    </div>
  </div>
</template>
