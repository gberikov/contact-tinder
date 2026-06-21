<script setup lang="ts">
import type { ResolveValidationItemBody } from '@/services/api';
import { useTidyStore } from '@/stores/tidy';
import { storeToRefs } from 'pinia';
import { computed } from 'vue';
import TidyQueueItem from './TidyQueueItem.vue';

const store = useTidyStore();
const { items } = storeToRefs(store);

// Pending first (work queue), then resolved/skipped (history, for undo).
const ordered = computed(() =>
  [...items.value].sort((a, b) => {
    if (a.status === 'pending' && b.status !== 'pending') return -1;
    if (a.status !== 'pending' && b.status === 'pending') return 1;
    return 0;
  }),
);

async function onResolve(itemId: string, body: ResolveValidationItemBody) {
  await store.resolveItem(itemId, body);
}
</script>

<template>
  <div v-if="ordered.length" class="space-y-2">
    <TidyQueueItem
      v-for="item in ordered"
      :key="item.id"
      :item="item"
      @resolve="(body) => onResolve(item.id, body)"
      @skip="store.skipItem(item.id)"
      @undo="(editId) => store.undoEdit(editId)"
    />
  </div>
</template>
