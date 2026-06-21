<script setup lang="ts">
import SwipeDeck from '@/components/SwipeDeck.vue';
import { Button } from '@/components/ui/button';
import { useTriageStore } from '@/stores/triage';
import { useWizardStore } from '@/stores/wizard';
import { RotateCcw } from 'lucide-vue-next';
import { storeToRefs } from 'pinia';
import { onMounted } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();
const wizard = useWizardStore();
// Driven by the route param on the legacy page, or by the active Draft inside the wizard.
const workingCopyId = (route.params.id as string) ?? wizard.activeWorkingCopyId ?? '';
const store = useTriageStore();
const { session } = storeToRefs(store);

onMounted(() => store.open(workingCopyId));

function startOver() {
  if (
    window.confirm('Start the review over? This clears all decisions and reverts staged edits.')
  ) {
    store.reset();
  }
}
</script>

<template>
  <section class="space-y-4">
    <div class="flex justify-end">
      <Button
        v-if="session"
        variant="outline"
        size="sm"
        :disabled="(session.summary.decided ?? 0) === 0"
        @click="startOver"
      >
        <RotateCcw /> Start over
      </Button>
    </div>
    <SwipeDeck />
  </section>
</template>
