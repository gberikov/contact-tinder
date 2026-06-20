<script setup lang="ts">
import type { SessionSummary } from '@/services/api';

defineProps<{ summary: SessionSummary }>();
</script>

<template>
  <div class="summary">
    <h3>All done 🎉</h3>
    <ul>
      <li>Kept: {{ summary.keep }}</li>
      <li>Queued for deletion: {{ summary.delete }}</li>
      <li>Sent to processing: {{ summary.processing }}</li>
      <li>Total: {{ summary.total }}</li>
    </ul>
  </div>
</template>

<style scoped>
.summary { text-align: center; padding: 24px; }
ul { list-style: none; padding: 0; }
</style>
