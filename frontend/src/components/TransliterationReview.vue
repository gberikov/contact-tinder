<script setup lang="ts">
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { TransliterationSuggestion } from '@/services/api';
import { reactive } from 'vue';

const props = defineProps<{ suggestion: TransliterationSuggestion }>();
const emit = defineEmits<(e: 'accept', fields: Record<string, string>) => void>();

// Editable copy of the suggested Cyrillic fields (operator reviews before accepting, FR-015).
const fields = reactive<Record<string, string>>({ ...props.suggestion.fields });
</script>

<template>
  <div class="space-y-2 rounded-lg border bg-muted/30 p-3">
    <p v-if="!suggestion.hasSuggestion" class="text-sm text-muted-foreground">
      No transliteration suggested.
    </p>
    <template v-else>
      <div v-for="(_, key) in fields" :key="key" class="flex items-center gap-2">
        <label class="w-28 text-sm text-muted-foreground">{{ key }}</label>
        <Input v-model="fields[key]" type="text" />
      </div>
      <Button size="sm" @click="emit('accept', { ...fields })">Accept Cyrillic</Button>
    </template>
  </div>
</template>
