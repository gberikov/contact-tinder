<script setup lang="ts">
import { type Account, ApiError, api } from '@/services/api';
import { useSnapshotsStore } from '@/stores/snapshots';
import { onMounted, onUnmounted, ref } from 'vue';
import { useRouter } from 'vue-router';

const store = useSnapshotsStore();
const router = useRouter();
const accounts = ref<Account[]>([]);
const selectedAccount = ref<string>('');
const message = ref<string | null>(null);
let timer: number | undefined;

async function refresh() {
  await store.load();
  // Keep polling while any import is in progress (live progress, FR-015).
  const importing = store.snapshots.some((s) => s.status === 'importing');
  if (importing && timer === undefined) {
    timer = window.setInterval(refresh, 1500);
  } else if (!importing && timer !== undefined) {
    window.clearInterval(timer);
    timer = undefined;
  }
}

async function createSnapshot() {
  if (!selectedAccount.value) return;
  await store.create(selectedAccount.value);
  await refresh();
}

async function remove(id: string) {
  if (!window.confirm('Delete this snapshot? This cannot be undone.')) return;
  try {
    await store.remove(id);
    message.value = 'Snapshot deleted.';
  } catch (e) {
    message.value =
      e instanceof ApiError && e.status === 409
        ? 'Cannot delete: this snapshot still has working copies. Delete them first.'
        : (e as Error).message;
  }
}

onMounted(async () => {
  accounts.value = await api.listAccounts();
  await refresh();
});
onUnmounted(() => timer !== undefined && window.clearInterval(timer));
</script>

<template>
  <section>
    <h2>Snapshots</h2>
    <div class="create">
      <select v-model="selectedAccount">
        <option value="" disabled>Select account…</option>
        <option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.email }}</option>
      </select>
      <button type="button" :disabled="!selectedAccount" @click="createSnapshot">
        Create snapshot
      </button>
    </div>
    <p v-if="message" class="message">{{ message }}</p>
    <table v-if="store.snapshots.length">
      <thead>
        <tr><th>Account</th><th>Created</th><th>Contacts</th><th>Copies</th><th>Status</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-for="s in store.snapshots" :key="s.id">
          <td>{{ s.accountEmail }}</td>
          <td>{{ new Date(s.createdAt).toLocaleString() }}</td>
          <td>{{ s.contactCount ?? '—' }}</td>
          <td>{{ s.workingCopyCount }}</td>
          <td><span class="status">{{ s.status }}</span></td>
          <td>
            <button type="button" @click="router.push(`/snapshots/${s.id}`)">Open</button>
            <button type="button" @click="remove(s.id)">Delete</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else>No snapshots yet.</p>
  </section>
</template>
