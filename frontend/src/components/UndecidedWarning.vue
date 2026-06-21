<script setup lang="ts">
defineProps<{ count: number }>();
</script>

<template>
  <p v-if="count > 0" class="undecided-warning" role="alert">
    ⚠ {{ count }} active contact(s) have no decision yet — they are <strong>excluded</strong> from this
    export. Finish triaging them if you want them deleted or labeled.
  </p>
</template>

<style scoped>
.undecided-warning {
  background: #fff7e6;
  border: 1px solid #ffd591;
  border-radius: 8px;
  padding: 10px 14px;
  color: #874d00;
}
</style>
