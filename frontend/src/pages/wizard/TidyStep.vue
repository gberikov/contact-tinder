<script setup lang="ts">
import TidyQueue from '@/components/tidy/TidyQueue.vue';
import TidyRunPanel from '@/components/tidy/TidyRunPanel.vue';
import { useTidyStore } from '@/stores/tidy';
import { useWizardStore } from '@/stores/wizard';
import { storeToRefs } from 'pinia';
import { computed, onMounted, watch } from 'vue';

const wizard = useWizardStore();
const tidy = useTidyStore();
const { run } = storeToRefs(tidy);

const workingCopyId = computed(() => wizard.activeWorkingCopyId);
const sessionId = computed(() => wizard.latestTriageSession?.id);

const pendingCount = computed(() => tidy.pendingItems.length);
const isCompleted = computed(() => run.value?.status === 'completed');
const nothingToClean = computed(
  () => isCompleted.value && (run.value?.autoAppliedCount ?? 0) === 0 && pendingCount.value === 0,
);

// Restore the latest run + queue on entry/reload (FR-003); refresh the wizard derivation too.
async function restore() {
  if (!workingCopyId.value) return;
  await tidy.ensureRegion();
  await tidy.restore(workingCopyId.value);
  await wizard.loadTidy();
}
onMounted(restore);
watch(workingCopyId, restore);
// Keep the stepper's running/completed state in sync as the run finishes.
watch(
  () => run.value?.status,
  () => wizard.loadTidy(),
);
</script>

<template>
  <section v-if="workingCopyId" class="space-y-5">
    <TidyRunPanel :working-copy-id="workingCopyId" :session-id="sessionId" />

    <!-- Passable-with-warning: continuing to Export with open items is allowed (the shared Continue
         button), but we surface the count clearly, mirroring the undecided-survivors warning. -->
    <p
      v-if="isCompleted && pendingCount > 0"
      class="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900"
    >
      <strong>{{ pendingCount }}</strong> item{{ pendingCount === 1 ? '' : 's' }} still need your
      attention. You can continue to Export, but unresolved values will be exported as-is.
    </p>

    <p v-if="nothingToClean" class="rounded-md border bg-muted/40 p-4 text-sm text-muted-foreground">
      Nothing to clean — every kept contact's phones, emails, and websites already look good.
    </p>

    <TidyQueue />
  </section>

  <p v-else class="text-sm text-muted-foreground">
    Pick a Draft first — Tidy validates the contacts that survived Review.
  </p>
</template>
