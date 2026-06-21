<script setup lang="ts">
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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
  <div class="flex items-center gap-2">
    <label class="text-sm text-muted-foreground">Display name</label>
    <Input v-model="displayName" type="text" />
    <Button size="sm" @click="save">Save edit</Button>
  </div>
</template>
