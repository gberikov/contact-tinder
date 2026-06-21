<script setup lang="ts">
import { Badge } from '@/components/ui/badge';
import { computed } from 'vue';

const props = defineProps<{ confidence: number }>();
const pct = computed(() => `${Math.round(props.confidence * 100)}%`);
const variant = computed<'success' | 'secondary' | 'destructive'>(() =>
  props.confidence >= 0.9 ? 'success' : props.confidence >= 0.7 ? 'secondary' : 'destructive',
);
</script>

<template>
  <Badge :variant="variant" class="tabular-nums" :title="`confidence ${pct}`">{{ pct }}</Badge>
</template>
