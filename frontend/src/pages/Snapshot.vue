<script setup lang="ts">
import ContactTable from '@/components/ContactTable.vue';
import { type Contact, type Snapshot, api } from '@/services/api';
import { onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

const route = useRoute();
const router = useRouter();
const id = route.params.id as string;

const snapshot = ref<Snapshot | null>(null);
const contacts = ref<Contact[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 50;
const query = ref('');

async function loadContacts() {
  const res = await api.listSnapshotContacts(id, page.value, pageSize, query.value || undefined);
  contacts.value = res.items;
  total.value = res.total;
}

async function createWorkingCopy() {
  const copy = await api.createWorkingCopy(id);
  if (snapshot.value) snapshot.value.workingCopyCount += 1;
  router.push('/working-copies');
  return copy;
}

onMounted(async () => {
  snapshot.value = await api.getSnapshot(id);
  await loadContacts();
});
</script>

<template>
  <section v-if="snapshot">
    <h2>Snapshot — {{ snapshot.accountEmail }}</h2>
    <p>
      <span class="status">{{ snapshot.status }}</span>
      · {{ snapshot.contactCount ?? '—' }} contacts · {{ snapshot.workingCopyCount }} working copies
    </p>
    <button
      type="button"
      :disabled="snapshot.status !== 'complete'"
      @click="createWorkingCopy"
    >
      Create working copy
    </button>

    <div class="search">
      <input v-model="query" placeholder="Filter by name/email" @keyup.enter="loadContacts" />
      <button type="button" @click="loadContacts">Search</button>
    </div>

    <p class="readonly-note">This snapshot is read-only.</p>
    <ContactTable :contacts="contacts" />
    <p>{{ total }} total</p>
  </section>
</template>
