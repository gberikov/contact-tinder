<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{ confidence: number }>();
const pct = computed(() => `${Math.round(props.confidence * 100)}%`);
const level = computed(() =>
  props.confidence >= 0.9 ? 'high' : props.confidence >= 0.7 ? 'medium' : 'low',
);
</script>

<template>
  <span class="badge" :class="level" :title="`confidence ${pct}`">{{ pct }}</span>
</template>

<style scoped>
.badge { border-radius: 4px; padding: 1px 6px; font-variant-numeric: tabular-nums; }
.high { background: #d6f5d6; }
.medium { background: #fdf2c4; }
.low { background: #f5d6d6; }
</style>
