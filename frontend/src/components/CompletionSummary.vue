<script setup lang="ts">
import { Card, CardContent } from '@/components/ui/card';
import type { SessionSummary } from '@/services/api';

defineProps<{ summary: SessionSummary }>();
</script>

<template>
  <Card class="mx-auto max-w-sm text-center">
    <CardContent class="space-y-3 p-6">
      <h3 class="text-lg font-semibold">All done 🎉</h3>
      <ul class="space-y-1 text-sm text-muted-foreground">
        <li>Kept: {{ summary.keep }}</li>
        <li>Queued for deletion: {{ summary.delete }}</li>
        <li>Sent to processing: {{ summary.processing }}</li>
        <li class="font-medium text-foreground">Total: {{ summary.total }}</li>
      </ul>
    </CardContent>
  </Card>
</template>
