<script setup lang="ts">
import type { ExportContactSummary } from '@/services/api';

defineProps<{ count: number; contacts: ExportContactSummary[] }>();
</script>

<template>
  <div class="rounded-lg border border-destructive/30 bg-destructive/5 p-4">
    <h3 class="font-medium">{{ count }} contact(s) will be deleted in Google</h3>
    <ul class="mt-2 max-h-60 space-y-0.5 overflow-auto text-sm">
      <li v-for="c in contacts" :key="c.workingCopyContactId">
        {{ c.displayName ?? '(no name)' }}
        <span v-if="c.primaryEmail" class="text-muted-foreground"> — {{ c.primaryEmail }}</span>
      </li>
    </ul>
  </div>
</template>
