<script setup lang="ts">
import { Button } from '@/components/ui/button';
import { Check, Pencil, X } from 'lucide-vue-next';

defineProps<{ disabled?: boolean }>();

const emit = defineEmits<{
  (e: 'keep'): void;
  (e: 'delete'): void;
  (e: 'process'): void;
}>();
</script>

<template>
  <div
    class="flex items-start gap-2 text-center [&_kbd]:rounded [&_kbd]:border [&_kbd]:bg-muted [&_kbd]:px-1.5 [&_kbd]:py-0.5"
  >
    <div class="flex flex-col items-center gap-1.5">
      <Button
        type="button"
        variant="destructive"
        class="rounded-full"
        :disabled="disabled"
        @click="emit('delete')"
      >
        <X /> Delete
      </Button>
      <span class="text-xs text-muted-foreground"><kbd>←</kbd> / <kbd>D</kbd></span>
    </div>

    <div class="flex flex-col items-center gap-1.5">
      <Button
        type="button"
        class="rounded-full bg-blue-600 text-white shadow hover:bg-blue-700 focus-visible:ring-blue-600 dark:bg-blue-500 dark:hover:bg-blue-600"
        :disabled="disabled"
        @click="emit('process')"
      >
        <Pencil /> Process
      </Button>
      <span class="text-xs text-muted-foreground"><kbd>↑</kbd> / <kbd>P</kbd></span>
    </div>

    <div class="flex flex-col items-center gap-1.5">
      <Button
        type="button"
        class="rounded-full bg-green-600 text-white shadow hover:bg-green-700 focus-visible:ring-green-600 dark:bg-green-500 dark:hover:bg-green-600"
        :disabled="disabled"
        @click="emit('keep')"
      >
        <Check /> Keep
      </Button>
      <span class="text-xs text-muted-foreground"><kbd>→</kbd> / <kbd>K</kbd></span>
    </div>
  </div>
</template>
