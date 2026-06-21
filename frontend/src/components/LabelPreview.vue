<script setup lang="ts">
import type { ExportContactSummary } from '@/services/api';

defineProps<{ count: number; labelName: string; contacts: ExportContactSummary[] }>();
</script>

<template>
  <div class="rounded-lg border bg-muted/30 p-4">
    <h3 class="font-medium">{{ count }} contact(s) will be labeled “{{ labelName }}” in Google</h3>
    <p class="mt-1 text-sm text-muted-foreground">
      Their existing data is left unchanged — the label is a marker to re-check them.
    </p>
    <ul class="mt-2 max-h-60 space-y-0.5 overflow-auto text-sm">
      <li v-for="c in contacts" :key="c.workingCopyContactId">
        {{ c.displayName ?? '(no name)' }}
        <span v-if="c.primaryEmail" class="text-muted-foreground"> — {{ c.primaryEmail }}</span>
      </li>
    </ul>
  </div>
</template>
