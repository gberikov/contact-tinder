<script setup lang="ts">
import SwipeDeck from '@/components/SwipeDeck.vue';
import { useTriageStore } from '@/stores/triage';
import { storeToRefs } from 'pinia';
import { onMounted } from 'vue';
import { RouterLink, useRoute } from 'vue-router';

const route = useRoute();
const workingCopyId = route.params.id as string;
const store = useTriageStore();
const { session } = storeToRefs(store);

onMounted(() => store.open(workingCopyId));
</script>

<template>
  <section>
    <h2>Swipe triage</h2>
    <SwipeDeck />
    <nav v-if="session" class="links">
      <RouterLink :to="`/triage-sessions/${session.id}/processing`">Processing queue</RouterLink>
      <RouterLink :to="`/working-copies/${workingCopyId}/delete-review`">Review deletions</RouterLink>
    </nav>
  </section>
</template>

<style scoped>
.links { display: flex; gap: 16px; justify-content: center; margin-top: 24px; }
</style>
