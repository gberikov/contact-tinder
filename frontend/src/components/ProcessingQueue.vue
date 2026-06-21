<script setup lang="ts">
import ContactCard from '@/components/ContactCard.vue';
import EditCardForm from '@/components/EditCardForm.vue';
import TransliterationReview from '@/components/TransliterationReview.vue';
import { Button } from '@/components/ui/button';
import type { ProcessingItem } from '@/services/api';

defineProps<{ items: ProcessingItem[] }>();
const emit = defineEmits<{
  (e: 'accept-translit', contactId: string, fields: Record<string, string>): void;
  (e: 'save-edit', contactId: string, payload: Record<string, unknown>): void;
  (e: 'done', itemId: string): void;
}>();
</script>

<template>
  <ul class="flex flex-col gap-5">
    <li v-for="item in items" :key="item.id" class="space-y-3 border-b pb-4">
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
      <Button variant="secondary" size="sm" @click="emit('done', item.id)">Done (keep)</Button>
    </li>
    <li v-if="items.length === 0" class="text-sm text-muted-foreground">
      Nothing left to process.
    </li>
  </ul>
</template>
