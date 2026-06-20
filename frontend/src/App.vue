<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router';
</script>

<template>
  <div class="app">
    <header>
      <h1>Contact Tinder</h1>
      <nav>
        <RouterLink to="/snapshots">Snapshots</RouterLink>
        <RouterLink to="/working-copies">Working copies</RouterLink>
        <RouterLink to="/accounts">Accounts</RouterLink>
      </nav>
    </header>
    <main>
      <RouterView />
    </main>
  </div>
</template>

<style>
.app {
  font-family: system-ui, sans-serif;
  max-width: 960px;
  margin: 0 auto;
  padding: 1rem;
}
nav a {
  margin-right: 1rem;
}
table {
  border-collapse: collapse;
  width: 100%;
}
th,
td {
  border: 1px solid #ddd;
  padding: 0.4rem 0.6rem;
  text-align: left;
}
.status {
  font-size: 0.85rem;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  background: #eee;
}
</style>
