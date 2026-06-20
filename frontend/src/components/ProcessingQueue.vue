<script setup lang="ts">
import ContactCard from '@/components/ContactCard.vue';
import EditCardForm from '@/components/EditCardForm.vue';
import TransliterationReview from '@/components/TransliterationReview.vue';
import type { ProcessingItem } from '@/services/api';

defineProps<{ items: ProcessingItem[] }>();
const emit = defineEmits<{
  (e: 'accept-translit', contactId: string, fields: Record<string, string>): void;
  (e: 'save-edit', contactId: string, payload: Record<string, unknown>): void;
  (e: 'done', itemId: string): void;
}>();
</script>

<template>
  <ul class="queue">
    <li v-for="item in items" :key="item.id" class="item">
      <ContactCard :contact="item.contact" />
      <TransliterationReview
        v-if="item.wantsTransliterate && item.transliterationSuggestion"
        :suggestion="item.transliterationSuggestion"
        @accept="(f) => emit('accept-translit', item.workingCopyContactId, f)"
      />
      <EditCardForm
        v-if="item.wantsEdit"
        :contact="item.contact"
        @save="(p) => emit('save-edit', item.workingCopyContactId, p)"
      />
      <button type="button" class="done" @click="emit('done', item.id)">Done (keep)</button>
    </li>
    <li v-if="items.length === 0">Nothing left to process.</li>
  </ul>
</template>

<style scoped>
.queue { list-style: none; padding: 0; display: flex; flex-direction: column; gap: 20px; }
.item { border-bottom: 1px solid #eee; padding-bottom: 16px; }
.done { margin-top: 10px; }
</style>
