<script setup lang="ts">
import type { DeleteBatch, DeletionRecord } from '@/services/api';

defineProps<{ batch: DeleteBatch | null; records: DeletionRecord[]; error: string | null }>();
const emit = defineEmits<{ (e: 'confirm'): void; (e: 'undo'): void }>();
</script>

<template>
  <div class="review">
    <p v-if="!batch">No delete batch.</p>
    <template v-else>
      <h3>{{ records.length }} contact(s) will be deleted in Google</h3>
      <ul class="records">
        <li v-for="r in records" :key="r.id">
          {{ r.contact.displayName ?? '(no name)' }} — {{ r.status }}
        </li>
      </ul>
      <p v-if="error" class="error">
        {{ error }} — re-consent with the contacts write scope is required.
      </p>
      <div class="actions">
        <button
          type="button"
          :disabled="batch.status !== 'staged' && batch.status !== 'previewed'"
          @click="emit('confirm')"
        >
          Confirm delete ({{ batch.totalCount }})
        </button>
        <button type="button" :disabled="batch.status !== 'committed'" @click="emit('undo')">
          Undo
        </button>
      </div>
      <p class="status">Batch status: {{ batch.status }}</p>
    </template>
  </div>
</template>

<style scoped>
.records { max-height: 320px; overflow: auto; }
.error { color: #b00020; }
.actions { display: flex; gap: 12px; margin-top: 12px; }
</style>
