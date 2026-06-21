<script setup lang="ts">
import TidyAutoFixes from '@/components/tidy/TidyAutoFixes.vue';
import TidyDeck from '@/components/tidy/TidyDeck.vue';
import TidyRunPanel from '@/components/tidy/TidyRunPanel.vue';
import { Button } from '@/components/ui/button';
import { useTidyStore } from '@/stores/tidy';
import { useWizardStore } from '@/stores/wizard';
import { storeToRefs } from 'pinia';
import { computed, onMounted, ref, watch } from 'vue';

const wizard = useWizardStore();
const tidy = useTidyStore();
const { run, autoFixes } = storeToRefs(tidy);

const workingCopyId = computed(() => wizard.activeWorkingCopyId);
const sessionId = computed(() => wizard.latestTriageSession?.id);

const pendingCount = computed(() => tidy.pendingItems.length);
const isCompleted = computed(() => run.value?.status === 'completed');
const nothingToClean = computed(
  () =>
    isCompleted.value &&
    (run.value?.autoAppliedCount ?? 0) === 0 &&
    pendingCount.value === 0 &&
    autoFixes.value.length === 0,
);

const tab = ref<'queue' | 'fixes'>('queue');

async function restore() {
  if (!workingCopyId.value) return;
  await tidy.ensureRegion();
  await wizard.loadReview();
  await tidy.restore(workingCopyId.value);
  await wizard.loadTidy();
}
onMounted(restore);
watch(workingCopyId, restore);
watch(
  () => run.value?.status,
  () => wizard.loadTidy(),
);
</script>

<template>
  <section v-if="workingCopyId" class="space-y-5">
    <TidyRunPanel :working-copy-id="workingCopyId" :session-id="sessionId" />

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

    <!-- Two views: the review deck (one card at a time) and the list of auto-applied fixes. -->
    <template v-if="run && !nothingToClean">
      <div class="flex gap-2">
        <Button :variant="tab === 'queue' ? 'default' : 'outline'" size="sm" @click="tab = 'queue'">
          To review ({{ pendingCount }})
        </Button>
        <Button :variant="tab === 'fixes' ? 'default' : 'outline'" size="sm" @click="tab = 'fixes'">
          Auto-fixed ({{ autoFixes.length }})
        </Button>
      </div>

      <TidyDeck v-if="tab === 'queue'" />
      <TidyAutoFixes v-else />
    </template>
  </section>

  <p v-else class="text-sm text-muted-foreground">
    Pick a Draft first — Tidy validates the contacts that survived Review.
  </p>
</template>
