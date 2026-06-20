<script setup lang="ts">
import type { ContactDetail } from '@/services/api';

defineProps<{ contact: ContactDetail }>();
</script>

<template>
  <div class="card">
    <h3 class="name">{{ contact.displayName ?? '(no name)' }}</h3>
    <dl>
      <template v-if="contact.primaryEmail">
        <dt>Email</dt><dd>{{ contact.primaryEmail }}</dd>
      </template>
      <template v-if="contact.primaryPhone">
        <dt>Phone</dt><dd>{{ contact.primaryPhone }}</dd>
      </template>
      <template v-if="contact.organization">
        <dt>Org</dt><dd>{{ contact.organization }}</dd>
      </template>
    </dl>
  </div>
</template>

<style scoped>
.card { border: 1px solid #ddd; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.name { margin: 0 0 12px; }
dl { display: grid; grid-template-columns: auto 1fr; gap: 4px 12px; margin: 0; }
dt { color: #666; }
</style>
