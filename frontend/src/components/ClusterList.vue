<script setup lang="ts">
import type { Cluster } from '@/services/api';
import ClusterCard from './ClusterCard.vue';

defineProps<{ clusters: Cluster[] }>();
defineEmits<{ merge: [clusterId: string, survivorId: string]; dismiss: [clusterId: string] }>();
</script>

<template>
  <div class="cluster-list">
    <p v-if="!clusters.length" class="empty">No duplicate clusters to review.</p>
    <ClusterCard
      v-for="c in clusters"
      :key="c.id"
      :cluster="c"
      @merge="(id, survivor) => $emit('merge', id, survivor)"
      @dismiss="(id) => $emit('dismiss', id)"
    />
  </div>
</template>
