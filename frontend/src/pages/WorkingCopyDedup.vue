<script setup lang="ts">
import ClusterList from '@/components/ClusterList.vue';
import DedupRunPanel from '@/components/DedupRunPanel.vue';
import { useDedupStore } from '@/stores/dedup';
import { storeToRefs } from 'pinia';
import { RouterLink, useRoute } from 'vue-router';

const route = useRoute();
const workingCopyId = route.params.id as string;
const store = useDedupStore();
const { pendingClusters } = storeToRefs(store);

async function onMerge(clusterId: string, survivorId: string) {
  await store.merge(clusterId, survivorId);
}
async function onDismiss(clusterId: string) {
  await store.dismiss(clusterId);
}
</script>

<template>
  <section>
    <h2>Deduplicate working copy</h2>
    <DedupRunPanel :working-copy-id="workingCopyId" />
    <ClusterList :clusters="pendingClusters" @merge="onMerge" @dismiss="onDismiss" />
    <p class="next">
      Done deduplicating?
      <RouterLink :to="`/working-copies/${workingCopyId}/triage`">Start triage →</RouterLink>
    </p>
  </section>
</template>

<style scoped>
.next {
  margin-top: 1.5rem;
}
</style>
