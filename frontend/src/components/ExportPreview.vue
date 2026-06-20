<script setup lang="ts">
import type { ExportContactSummary } from '@/services/api';

defineProps<{ count: number; contacts: ExportContactSummary[] }>();
</script>

<template>
  <div class="export-preview delete">
    <h3>{{ count }} contact(s) will be deleted in Google</h3>
    <ul class="contacts">
      <li v-for="c in contacts" :key="c.workingCopyContactId">
        {{ c.displayName ?? '(no name)' }}
        <span v-if="c.primaryEmail" class="muted"> — {{ c.primaryEmail }}</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.contacts { max-height: 240px; overflow: auto; }
.muted { color: #777; }
</style>
