<script setup lang="ts">
import CompletionSummary from '@/components/CompletionSummary.vue';
import ContactCard from '@/components/ContactCard.vue';
import SwipeControls from '@/components/SwipeControls.vue';
import { useTriageStore } from '@/stores/triage';
import { storeToRefs } from 'pinia';

const store = useTriageStore();
const { deck, summary, error } = storeToRefs(store);
</script>

<template>
  <div class="deck">
    <p v-if="error" class="error">{{ error }}</p>
    <template v-if="store.currentCard">
      <ContactCard :contact="store.currentCard.contact" />
      <SwipeControls
        @keep="store.decide('keep')"
        @delete="store.decide('delete')"
        @process="store.decide('process', { wantsEdit: true, wantsTransliterate: true })"
      />
      <p v-if="summary" class="progress">{{ summary.remaining }} remaining</p>
    </template>
    <CompletionSummary v-else-if="summary" :summary="summary" />
  </div>
</template>

<style scoped>
.deck { max-width: 420px; margin: 0 auto; }
.progress { text-align: center; color: #666; margin-top: 8px; }
.error { color: #b00020; text-align: center; }
</style>
