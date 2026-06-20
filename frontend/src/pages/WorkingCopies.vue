<script setup lang="ts">
import { type WorkingCopy, api } from '@/services/api';
import { onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';

const copies = ref<WorkingCopy[]>([]);

onMounted(async () => {
  copies.value = await api.listWorkingCopies();
});
</script>

<template>
  <section>
    <h2>Working copies</h2>
    <table v-if="copies.length">
      <thead>
        <tr><th>Label</th><th>Source snapshot</th><th>Contacts</th><th>Status</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-for="c in copies" :key="c.id">
          <td>{{ c.label }}</td>
          <td><code>{{ c.snapshotId.slice(0, 8) }}</code></td>
          <td>{{ c.contactCount ?? '—' }}</td>
          <td><span class="status">{{ c.status }}</span></td>
          <td class="actions">
            <RouterLink
              v-if="c.status === 'ready'"
              :to="`/working-copies/${c.id}/dedup`"
            >Deduplicate →</RouterLink>
            <RouterLink
              v-if="c.status === 'ready'"
              :to="`/working-copies/${c.id}/triage`"
            >Triage →</RouterLink>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else>No working copies yet. Create one from a snapshot.</p>
  </section>
</template>

<style scoped>
.actions {
  display: flex;
  gap: 1rem;
  white-space: nowrap;
}
</style>
