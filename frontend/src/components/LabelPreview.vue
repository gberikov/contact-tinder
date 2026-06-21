<script setup lang="ts">
import type { ExportContactSummary } from '@/services/api';

defineProps<{ count: number; labelName: string; contacts: ExportContactSummary[] }>();
</script>

<template>
  <div class="export-preview label">
    <h3>{{ count }} contact(s) will be labeled “{{ labelName }}” in Google</h3>
    <p class="note">Their existing data is left unchanged — the label is a marker to re-check them.</p>
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
.note { color: #555; font-size: 0.9em; }
</style>
