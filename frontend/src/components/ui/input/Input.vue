<script setup lang="ts">
import { cn } from '@/lib/utils';

const props = defineProps<{
  modelValue?: string | number;
  class?: string;
  placeholder?: string;
}>();

const emits = defineEmits<(e: 'update:modelValue', value: string) => void>();

function onInput(event: Event) {
  emits('update:modelValue', (event.target as HTMLInputElement).value);
}
</script>

<template>
  <input
    :value="modelValue"
    :placeholder="placeholder"
    :class="
      cn(
        'flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50',
        props.class,
      )
    "
    @input="onInput"
  >
</template>
