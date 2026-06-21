<script setup lang="ts">
import { useTidyStore } from '@/stores/tidy';
import { computed } from 'vue';
import TidyQueueItem from './TidyQueueItem.vue';

// Review-style deck: one card at a time with a single control set. Resolving or skipping the head
// item drops it from the pending queue, so the next card appears automatically.
const store = useTidyStore();
const pending = computed(() => store.pendingItems);
const current = computed(() => pending.value[0] ?? null);
</script>

<template>
  <div class="mx-auto max-w-md">
    <template v-if="current">
      <p class="mb-2 text-center text-sm text-muted-foreground">{{ pending.length }} to review</p>
      <div class="rounded-xl border bg-card p-4 shadow-sm">
        <TidyQueueItem
          :item="current"
          @resolve="(body) => store.resolveItem(current.id, body)"
          @skip="store.skipItem(current.id)"
          @undo="(editId) => store.undoEdit(editId)"
        />
      </div>
    </template>
    <p v-else class="rounded-md border bg-muted/40 p-6 text-center text-sm text-muted-foreground">
      All issues reviewed — nothing left in the queue.
    </p>
  </div>
</template>
