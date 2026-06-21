<script setup lang="ts">
import CompletionSummary from '@/components/CompletionSummary.vue';
import ContactCard from '@/components/ContactCard.vue';
import SwipeControls from '@/components/SwipeControls.vue';
import { Button } from '@/components/ui/button';
import { useTriageStore } from '@/stores/triage';
import { Undo2 } from 'lucide-vue-next';
import { storeToRefs } from 'pinia';
import { onBeforeUnmount, onMounted } from 'vue';

const store = useTriageStore();
const { summary, error, canUndo } = storeToRefs(store);

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
  <div class="mx-auto max-w-md">
    <div class="mb-2 flex min-h-8 justify-end">
      <Button variant="outline" size="sm" :disabled="!canUndo" @click="store.undoLast()">
        <Undo2 /> Undo
      </Button>
    </div>
    <p v-if="error" class="text-center text-sm text-destructive">{{ error }}</p>
    <template v-if="store.currentCard">
      <ContactCard :contact="store.currentCard.contact" />
      <SwipeControls
        @keep="store.decide('keep')"
        @delete="store.decide('delete')"
        @process="store.decide('process', { wantsEdit: true, wantsTransliterate: true })"
      />
      <p v-if="summary" class="mt-2 text-center text-sm text-muted-foreground">
        {{ summary.remaining }} remaining
      </p>
      <p
        class="mt-3 text-center text-xs text-muted-foreground [&_kbd]:rounded [&_kbd]:border [&_kbd]:bg-muted [&_kbd]:px-1.5 [&_kbd]:py-0.5"
      >
        <kbd>←</kbd>/<kbd>D</kbd> delete · <kbd>→</kbd>/<kbd>K</kbd> keep ·
        <kbd>↑</kbd>/<kbd>P</kbd> process · <kbd>↓</kbd>/<kbd>U</kbd> undo
      </p>
    </template>
    <CompletionSummary v-else-if="summary" :summary="summary" />
  </div>
</template>
