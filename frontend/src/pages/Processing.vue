<script setup lang="ts">
import ProcessingQueue from '@/components/ProcessingQueue.vue';
import { Button } from '@/components/ui/button';
import { api } from '@/services/api';
import { useTriageStore } from '@/stores/triage';
import { ChevronLeft } from 'lucide-vue-next';
import { storeToRefs } from 'pinia';
import { onMounted } from 'vue';
import { RouterLink, useRoute } from 'vue-router';

const route = useRoute();
const sessionId = route.params.id as string;
const store = useTriageStore();
const { processing } = storeToRefs(store);

async function load() {
  // Ensure the store has the session, then load its queue.
  store.session = await api.getTriageSession(sessionId);
  await store.loadProcessing();
}
onMounted(load);

async function onAcceptTranslit(contactId: string, fields: Record<string, string>) {
  await store.acceptTransliteration(contactId, fields);
}
async function onSaveEdit(contactId: string, payload: Record<string, unknown>) {
  await store.applyEdit(contactId, payload);
}
async function onDone(itemId: string) {
  await store.completeProcessing(itemId);
}
</script>

<template>
  <section class="mx-auto max-w-3xl space-y-4 p-6">
    <div class="flex items-center gap-2">
      <Button as-child variant="ghost" size="sm">
        <RouterLink to="/wizard/review"><ChevronLeft /> Review</RouterLink>
      </Button>
      <h2 class="text-lg font-semibold">Processing queue</h2>
    </div>
    <ProcessingQueue
      :items="processing"
      @accept-translit="onAcceptTranslit"
      @save-edit="onSaveEdit"
      @done="onDone"
    />
  </section>
</template>
