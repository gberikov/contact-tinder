<script setup lang="ts">
import type { Cluster } from '@/services/api';
import { ref } from 'vue';
import ConfidenceBadge from './ConfidenceBadge.vue';
import MergePreview from './MergePreview.vue';

const props = defineProps<{ cluster: Cluster }>();
const emit = defineEmits<{
  merge: [clusterId: string, survivorId: string];
  dismiss: [clusterId: string];
}>();

const showPreview = ref(false);

function onConfirm(survivorId: string) {
  showPreview.value = false;
  emit('merge', props.cluster.id, survivorId);
}
</script>

<template>
  <div class="cluster">
    <header>
      <ConfidenceBadge :confidence="cluster.confidence" />
      <span class="size">{{ cluster.size }} contacts</span>
    </header>
    <ul class="members">
      <li v-for="m in cluster.members" :key="m.workingCopyContactId">
        <strong>{{ m.contact.displayName ?? '—' }}</strong>
        <span>{{ m.contact.primaryEmail ?? '' }}</span>
        <span>{{ m.contact.primaryPhone ?? '' }}</span>
      </li>
    </ul>

    <div v-if="!showPreview" class="actions">
      <button type="button" class="merge" @click="showPreview = true">Merge…</button>
      <button type="button" class="dismiss" @click="emit('dismiss', cluster.id)">
        Not a duplicate
      </button>
    </div>
    <MergePreview
      v-else
      :cluster="cluster"
      @confirm="onConfirm"
      @cancel="showPreview = false"
    />
  </div>
</template>

<style scoped>
.cluster { border: 1px solid #ddd; border-radius: 8px; padding: 12px; margin-bottom: 12px; }
header { display: flex; gap: 8px; align-items: center; }
.members { list-style: none; padding: 0; }
.members li { display: flex; gap: 12px; }
.actions { display: flex; gap: 8px; }
</style>
