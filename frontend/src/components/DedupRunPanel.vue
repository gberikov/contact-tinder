<script setup lang="ts">
import { useDedupStore } from '@/stores/dedup';
import { storeToRefs } from 'pinia';

const props = defineProps<{ workingCopyId: string }>();
const store = useDedupStore();
const { run, loading, error } = storeToRefs(store);
</script>

<template>
  <div class="panel">
    <button type="button" :disabled="loading" @click="store.startRun(props.workingCopyId)">
      {{ loading ? 'Finding duplicates…' : 'Find duplicates' }}
    </button>
    <span v-if="run" class="run-status">
      Run {{ run.status }}<template v-if="run.clusterCount != null"> — {{ run.clusterCount }} clusters</template>
    </span>
    <span v-if="error" class="error">{{ error }}</span>
  </div>
</template>

<style scoped>
.panel { display: flex; gap: 12px; align-items: center; }
.error { color: #b00020; }
</style>
