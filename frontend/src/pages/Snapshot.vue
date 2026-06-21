<script setup lang="ts">
import ContactTable from '@/components/ContactTable.vue';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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

async function createDraft() {
  const copy = await api.createWorkingCopy(id);
  if (snapshot.value) snapshot.value.workingCopyCount += 1;
  router.push('/wizard/draft');
  return copy;
}

onMounted(async () => {
  snapshot.value = await api.getSnapshot(id);
  await loadContacts();
});
</script>

<template>
  <section v-if="snapshot" class="mx-auto max-w-4xl space-y-4 p-6">
    <h2 class="text-lg font-semibold">Backup — {{ snapshot.accountEmail }}</h2>
    <p class="flex items-center gap-2 text-sm text-muted-foreground">
      <Badge variant="secondary">{{ snapshot.status }}</Badge>
      · {{ snapshot.contactCount ?? '—' }} contacts · {{ snapshot.workingCopyCount }} drafts
    </p>
    <Button :disabled="snapshot.status !== 'complete'" @click="createDraft">Create draft</Button>

    <div class="flex gap-2">
      <Input v-model="query" placeholder="Filter by name/email" @keyup.enter="loadContacts" />
      <Button variant="outline" @click="loadContacts">Search</Button>
    </div>

    <p class="text-xs text-muted-foreground">This backup is read-only.</p>
    <ContactTable :contacts="contacts" />
    <p class="text-sm text-muted-foreground">{{ total }} total</p>
  </section>
</template>
