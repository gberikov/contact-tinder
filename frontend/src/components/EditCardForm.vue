<script setup lang="ts">
import type { ContactDetail } from '@/services/api';
import { ref } from 'vue';

const props = defineProps<{ contact: ContactDetail }>();
const emit = defineEmits<(e: 'save', payload: Record<string, unknown>) => void>();

const displayName = ref(props.contact.displayName ?? '');

function save() {
  // Stage an edited payload: update the primary name's displayName, keep the rest.
  const payload = { ...(props.contact.payload as Record<string, unknown>) };
  payload.names = [{ displayName: displayName.value, metadata: { primary: true } }];
  emit('save', payload);
}
</script>

<template>
  <div class="edit">
    <label>Display name</label>
    <input v-model="displayName" type="text" />
    <button type="button" @click="save">Save edit</button>
  </div>
</template>

<style scoped>
.edit { display: flex; gap: 8px; align-items: center; }
label { color: #666; }
</style>
