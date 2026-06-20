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

function startOver() {
  if (window.confirm('Start triage over? This clears all decisions and reverts staged edits.')) {
    store.reset();
  }
}
</script>

<template>
  <section>
    <header class="head">
      <h2>Swipe triage</h2>
      <button
        v-if="session"
        type="button"
        class="reset"
        :disabled="(session.summary.decided ?? 0) === 0"
        @click="startOver"
      >
        ⟲ Start over
      </button>
    </header>
    <SwipeDeck />
    <nav v-if="session" class="links">
      <RouterLink :to="`/triage-sessions/${session.id}/processing`">Processing queue</RouterLink>
      <RouterLink :to="`/working-copies/${workingCopyId}/delete-review`">Review deletions</RouterLink>
    </nav>
  </section>
</template>

<style scoped>
.head { display: flex; align-items: center; justify-content: space-between; }
.reset { padding: 6px 12px; border-radius: 8px; border: 1px solid #ccc; background: #fff; cursor: pointer; }
.reset:disabled { opacity: 0.4; cursor: default; }
.links { display: flex; gap: 16px; justify-content: center; margin-top: 24px; }
</style>
