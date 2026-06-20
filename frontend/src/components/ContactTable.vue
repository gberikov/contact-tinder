<script setup lang="ts">
import type { Contact } from '@/services/api';

defineProps<{ contacts: Contact[] }>();
</script>

<template>
  <table>
    <thead>
      <tr><th>Name</th><th>Email</th><th>Phone</th></tr>
    </thead>
    <tbody>
      <tr v-for="c in contacts" :key="c.id">
        <td>{{ c.displayName ?? '—' }}</td>
        <td>{{ c.primaryEmail ?? '—' }}</td>
        <td>{{ c.primaryPhone ?? '—' }}</td>
      </tr>
    </tbody>
  </table>
</template>
