<script setup lang="ts">
import ClusterList from '@/components/ClusterList.vue';
import DedupRunPanel from '@/components/DedupRunPanel.vue';
import { useDedupStore } from '@/stores/dedup';
import { useWizardStore } from '@/stores/wizard';
import { storeToRefs } from 'pinia';
import { useRoute } from 'vue-router';

const route = useRoute();
const wizard = useWizardStore();
// Driven by the route param on the legacy page, or by the active Draft inside the wizard.
const workingCopyId = (route.params.id as string) ?? wizard.activeWorkingCopyId ?? '';
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
  <section class="space-y-4">
    <DedupRunPanel :working-copy-id="workingCopyId" />
    <ClusterList :clusters="pendingClusters" @merge="onMerge" @dismiss="onDismiss" />
  </section>
</template>
