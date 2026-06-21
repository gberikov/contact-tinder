<script setup lang="ts">
import SwipeDeck from '@/components/SwipeDeck.vue';
import { Button } from '@/components/ui/button';
import { useTriageStore } from '@/stores/triage';
import { useWizardStore } from '@/stores/wizard';
import { ListChecks, Trash2 } from 'lucide-vue-next';
import { storeToRefs } from 'pinia';
import { onMounted } from 'vue';
import { RouterLink, useRoute } from 'vue-router';

const route = useRoute();
const wizard = useWizardStore();
// Driven by the route param on the legacy page, or by the active Draft inside the wizard.
const workingCopyId = (route.params.id as string) ?? wizard.activeWorkingCopyId ?? '';
const store = useTriageStore();
// Start over and Undo now live in the deck's action bar (SwipeDeck); the page keeps the
// session only to render the sub-flow navigation below.
const { session } = storeToRefs(store);

onMounted(() => store.open(workingCopyId));
</script>

<template>
  <section class="space-y-4">
    <SwipeDeck />

    <nav v-if="session" class="mt-2 grid gap-3 border-t pt-4 sm:grid-cols-2">
      <Button as-child variant="secondary" class="h-auto justify-start gap-3 px-4 py-3">
        <RouterLink :to="`/triage-sessions/${session.id}/processing`">
          <ListChecks class="shrink-0" />
          <span class="flex flex-col items-start text-left">
            <span class="font-medium">Processing queue</span>
            <span class="text-xs font-normal text-muted-foreground">
              Edit &amp; transliterate queued contacts
            </span>
          </span>
        </RouterLink>
      </Button>
      <Button as-child variant="secondary" class="h-auto justify-start gap-3 px-4 py-3">
        <RouterLink :to="`/working-copies/${workingCopyId}/delete-review`">
          <Trash2 class="shrink-0" />
          <span class="flex flex-col items-start text-left">
            <span class="font-medium">Review deletions</span>
            <span class="text-xs font-normal text-muted-foreground">
              Confirm contacts staged to delete
            </span>
          </span>
        </RouterLink>
      </Button>
    </nav>
  </section>
</template>

