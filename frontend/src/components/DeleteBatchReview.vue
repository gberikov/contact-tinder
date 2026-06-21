<script setup lang="ts">
import { Button } from '@/components/ui/button';
import type { DeleteBatch, DeletionRecord } from '@/services/api';

defineProps<{ batch: DeleteBatch | null; records: DeletionRecord[]; error: string | null }>();
const emit = defineEmits<{ (e: 'confirm'): void; (e: 'undo'): void }>();
</script>

<template>
  <div class="space-y-3">
    <p v-if="!batch" class="text-sm text-muted-foreground">No delete batch.</p>
    <template v-else>
      <h3 class="font-medium">{{ records.length }} contact(s) will be deleted in Google</h3>
      <ul class="max-h-80 space-y-0.5 overflow-auto text-sm">
        <li v-for="r in records" :key="r.id">
          {{ r.contact.displayName ?? '(no name)' }} —
          <span class="text-muted-foreground">{{ r.status }}</span>
        </li>
      </ul>
      <p v-if="error" class="text-sm text-destructive">
        {{ error }} — re-consent with the contacts write scope is required.
      </p>
      <div class="flex gap-3">
        <Button
          variant="destructive"
          :disabled="batch.status !== 'staged' && batch.status !== 'previewed'"
          @click="emit('confirm')"
        >
          Confirm delete ({{ batch.totalCount }})
        </Button>
        <Button variant="outline" :disabled="batch.status !== 'committed'" @click="emit('undo')">
          Undo
        </Button>
      </div>
      <p class="text-xs text-muted-foreground">Batch status: {{ batch.status }}</p>
    </template>
  </div>
</template>
