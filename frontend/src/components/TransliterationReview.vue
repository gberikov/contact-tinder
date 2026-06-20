<script setup lang="ts">
import type { TransliterationSuggestion } from '@/services/api';
import { reactive } from 'vue';

const props = defineProps<{ suggestion: TransliterationSuggestion }>();
const emit = defineEmits<(e: 'accept', fields: Record<string, string>) => void>();

// Editable copy of the suggested Cyrillic fields (operator reviews before accepting, FR-015).
const fields = reactive<Record<string, string>>({ ...props.suggestion.fields });
</script>

<template>
  <div class="translit">
    <p v-if="!suggestion.hasSuggestion">No transliteration suggested.</p>
    <template v-else>
      <div v-for="(_, key) in fields" :key="key" class="row">
        <label>{{ key }}</label>
        <input v-model="fields[key]" type="text" />
      </div>
      <button type="button" @click="emit('accept', { ...fields })">Accept Cyrillic</button>
    </template>
  </div>
</template>

<style scoped>
.row { display: flex; gap: 8px; align-items: center; margin-bottom: 6px; }
label { width: 110px; color: #666; }
</style>
