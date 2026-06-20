<script setup lang="ts">
const emit = defineEmits<{
  (e: 'keep'): void;
  (e: 'delete'): void;
  (e: 'process'): void;
}>();
</script>

<template>
  <div class="controls">
    <button type="button" class="del" @click="emit('delete')">✗ Delete</button>
    <button type="button" class="proc" @click="emit('process')">✎ Process</button>
    <button type="button" class="keep" @click="emit('keep')">✓ Keep</button>
  </div>
</template>

<style scoped>
.controls { display: flex; gap: 12px; justify-content: center; margin-top: 16px; }
button { padding: 10px 18px; border-radius: 999px; border: 1px solid #ccc; cursor: pointer; font-size: 15px; }
.keep { background: #e6f4ea; border-color: #34a853; }
.del { background: #fce8e6; border-color: #ea4335; }
.proc { background: #fef7e0; border-color: #f9ab00; }
</style>
