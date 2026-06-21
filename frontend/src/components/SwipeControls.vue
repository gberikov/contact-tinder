<script setup lang="ts">
import { Button } from '@/components/ui/button';
import { Check, Pencil, X } from 'lucide-vue-next';

const emit = defineEmits<{
  (e: 'keep'): void;
  (e: 'delete'): void;
  (e: 'process'): void;
}>();
</script>

<template>
  <div class="mt-4 flex justify-center gap-3">
    <Button type="button" variant="destructive" class="rounded-full" @click="emit('delete')">
      <X /> Delete
    </Button>
    <Button type="button" variant="outline" class="rounded-full" @click="emit('process')">
      <Pencil /> Process
    </Button>
    <Button type="button" class="rounded-full" @click="emit('keep')">
      <Check /> Keep
    </Button>
  </div>
</template>
