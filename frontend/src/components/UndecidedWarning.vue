<script setup lang="ts">
defineProps<{ count: number }>();
</script>

<template>
  <p
    v-if="count > 0"
    role="alert"
    class="rounded-lg border border-amber-300 bg-amber-50 px-4 py-2.5 text-sm text-amber-900 dark:border-amber-700/60 dark:bg-amber-950/40 dark:text-amber-200"
  >
    ⚠ {{ count }} active contact(s) have no decision yet — they are <strong>excluded</strong> from
    this export. Finish reviewing them if you want them deleted or labeled.
  </p>
</template>
