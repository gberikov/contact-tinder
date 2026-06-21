<script setup lang="ts">
import CompletionSummary from '@/components/CompletionSummary.vue';
import ContactCard from '@/components/ContactCard.vue';
import SwipeControls from '@/components/SwipeControls.vue';
import { Button } from '@/components/ui/button';
import { useTriageStore } from '@/stores/triage';
import { RotateCcw, Undo2 } from 'lucide-vue-next';
import { storeToRefs } from 'pinia';
import { onBeforeUnmount, onMounted } from 'vue';

const store = useTriageStore();
const { summary, error, canUndo } = storeToRefs(store);

function startOver() {
  if (
    window.confirm('Start the review over? This clears all decisions and reverts staged edits.')
  ) {
    store.reset();
  }
}

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
  <div class="w-full">
    <!-- Action bar above the card: Start over pinned hard to the left edge, Undo to the right edge,
         with the Delete/Process/Keep group centred far between them so the destructive resets can't
         be hit by accident. Anchoring it here also keeps the controls still as contact detail varies
         the card's height. -->
    <div class="mb-7 flex items-start justify-between gap-3">
      <Button
        variant="outline"
        :disabled="(summary?.decided ?? 0) === 0"
        @click="startOver"
      >
        <RotateCcw /> Start over
      </Button>

      <SwipeControls
        :disabled="!store.currentCard"
        @keep="store.decide('keep')"
        @delete="store.decide('delete')"
        @process="store.decide('process', { wantsEdit: true, wantsTransliterate: true })"
      />

      <Button
        variant="outline"
        title="Undo last decision (↓ or U)"
        :disabled="!canUndo"
        @click="store.undoLast()"
      >
        <Undo2 /> Undo
      </Button>
    </div>

    <div class="mx-auto max-w-md">
      <p v-if="error" class="mb-2 text-center text-sm text-destructive">{{ error }}</p>
      <template v-if="store.currentCard">
        <ContactCard :contact="store.currentCard.contact" />
        <p v-if="summary" class="mt-3 text-center text-sm text-muted-foreground">
          {{ summary.remaining }} remaining
        </p>
      </template>
      <CompletionSummary v-else-if="summary" :summary="summary" />
    </div>
  </div>
</template>
