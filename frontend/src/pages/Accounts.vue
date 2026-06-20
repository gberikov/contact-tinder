<script setup lang="ts">
import { type Account, api } from '@/services/api';
import { onMounted, ref } from 'vue';

const accounts = ref<Account[]>([]);
const error = ref<string | null>(null);

async function load() {
  accounts.value = await api.listAccounts();
}

async function connect() {
  const { authorizationUrl } = await api.connect();
  window.location.href = authorizationUrl;
}

async function disconnect(id: string) {
  await api.disconnect(id);
  await load();
}

onMounted(load);
</script>

<template>
  <section>
    <h2>Google accounts</h2>
    <button type="button" @click="connect">Connect Google account</button>
    <p v-if="error" class="error">{{ error }}</p>
    <table v-if="accounts.length">
      <thead>
        <tr><th>Email</th><th>Status</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-for="a in accounts" :key="a.id">
          <td>{{ a.email }}</td>
          <td>
            <span class="status">{{ a.status }}</span>
            <span v-if="a.status === 'needs_reauth'"> — please reconnect</span>
          </td>
          <td><button type="button" @click="disconnect(a.id)">Disconnect</button></td>
        </tr>
      </tbody>
    </table>
    <p v-else>No accounts connected yet.</p>
  </section>
</template>
