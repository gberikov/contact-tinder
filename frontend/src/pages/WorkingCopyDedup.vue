<script setup lang="ts">
import DedupRunPanel from '@/components/DedupRunPanel.vue';
import MergeDeck from '@/components/MergeDeck.vue';
import { useDedupStore } from '@/stores/dedup';
import { useWizardStore } from '@/stores/wizard';
import { storeToRefs } from 'pinia';
import { onMounted } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();
const wizard = useWizardStore();
// Driven by the route param on the legacy page, or by the active Draft inside the wizard.
const workingCopyId = (route.params.id as string) ?? wizard.activeWorkingCopyId ?? '';
const store = useDedupStore();
const { run } = storeToRefs(store);

// Re-derive Merge completion from the wizard's own run list so Continue unlocks.
async function refreshWizard() {
  await wizard.loadMerge();
}

// Re-entering the step: restore the latest completed run + its clusters into the deck.
onMounted(async () => {
  if (store.run) return;
  if (!wizard.dedupRuns.length) await wizard.loadMerge();
  const latest = wizard.latestDedupRun;
  if (latest) await store.adopt(latest);
});
</script>

<template>
  <section class="space-y-6">
    <DedupRunPanel :working-copy-id="workingCopyId" @done="refreshWizard" />
    <MergeDeck v-if="run" @change="refreshWizard" />
  </section>
</template>
