<script setup lang="ts">
import CompletionSummary from '@/components/CompletionSummary.vue';
import ContactCard from '@/components/ContactCard.vue';
import SwipeControls from '@/components/SwipeControls.vue';
import { useTriageStore } from '@/stores/triage';
import { storeToRefs } from 'pinia';
import { onBeforeUnmount, onMounted } from 'vue';

const store = useTriageStore();
const { deck, summary, error } = storeToRefs(store);

// Keyboard shortcuts: ←/D delete · →/K keep · ↑/P process · ↓/U undo last.
function onKey(e: KeyboardEvent) {
  const el = e.target as HTMLElement | null;
  if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)) return;
  if (e.metaKey || e.ctrlKey || e.altKey) return;

  const key = e.key.toLowerCase();
  if (key === 'arrowdown' || key === 'u') {
    store.undoLast();
    e.preventDefault();
    return;
  }
  if (!store.currentCard) return;
  if (key === 'arrowright' || key === 'k') store.decide('keep');
  else if (key === 'arrowleft' || key === 'd') store.decide('delete');
  else if (key === 'arrowup' || key === 'p')
    store.decide('process', { wantsEdit: true, wantsTransliterate: true });
  else return;
  e.preventDefault();
}

onMounted(() => window.addEventListener('keydown', onKey));
onBeforeUnmount(() => window.removeEventListener('keydown', onKey));
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
      <p class="hints">
        <kbd>←</kbd>/<kbd>D</kbd> delete · <kbd>→</kbd>/<kbd>K</kbd> keep ·
        <kbd>↑</kbd>/<kbd>P</kbd> process · <kbd>↓</kbd>/<kbd>U</kbd> undo
      </p>
    </template>
    <CompletionSummary v-else-if="summary" :summary="summary" />
  </div>
</template>

<style scoped>
.deck { max-width: 420px; margin: 0 auto; }
.progress { text-align: center; color: #666; margin-top: 8px; }
.error { color: #b00020; text-align: center; }
.hints { text-align: center; color: #999; font-size: 13px; margin-top: 12px; }
kbd {
  background: #f1f1f1;
  border: 1px solid #ccc;
  border-radius: 4px;
  padding: 1px 5px;
  font-family: inherit;
}
</style>
