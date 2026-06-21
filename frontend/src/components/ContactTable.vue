<script setup lang="ts">
import type { Contact } from '@/services/api';

defineProps<{ contacts: Contact[] }>();
</script>

<template>
  <div class="overflow-hidden rounded-lg border">
    <table class="w-full text-sm">
      <thead class="bg-muted/50 text-left text-muted-foreground">
        <tr>
          <th class="px-3 py-2 font-medium">Name</th>
          <th class="px-3 py-2 font-medium">Email</th>
          <th class="px-3 py-2 font-medium">Phone</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="c in contacts" :key="c.id" class="border-t">
          <td class="px-3 py-2">{{ c.displayName ?? '—' }}</td>
          <td class="px-3 py-2">{{ c.primaryEmail ?? '—' }}</td>
          <td class="px-3 py-2">{{ c.primaryPhone ?? '—' }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
