<script setup lang="ts">
import { Button } from '@/components/ui/button';
import { type Cluster, type MergePreview, api } from '@/services/api';
import { onMounted, ref } from 'vue';

const props = defineProps<{ cluster: Cluster }>();
const emit = defineEmits<{ confirm: [survivorContactId: string]; cancel: [] }>();

const preview = ref<MergePreview | null>(null);
const survivorId = ref<string>('');

async function load(survivor?: string) {
  preview.value = await api.mergePreview(props.cluster.id, survivor);
  survivorId.value = preview.value.survivorContactId;
}

onMounted(() => load());

function chooseSurvivor(id: string) {
  load(id);
}
</script>

<template>
  <div v-if="preview" class="space-y-3 rounded-lg border bg-muted/30 p-3">
    <h4 class="font-medium">Proposed merge</h4>
    <p class="text-sm text-muted-foreground">Keep as survivor:</p>
    <label
      v-for="m in cluster.members"
      :key="m.workingCopyContactId"
      class="flex items-center gap-2 text-sm"
    >
      <input
        type="radio"
        class="accent-primary"
        :value="m.workingCopyContactId"
        :checked="m.workingCopyContactId === survivorId"
        @change="chooseSurvivor(m.workingCopyContactId)"
      >
      {{ m.contact.displayName ?? m.workingCopyContactId.slice(0, 8) }}
    </label>

    <div v-if="preview.conflicts.length" class="text-sm">
      <strong>Conflicts</strong>
      <ul class="mt-1 list-disc pl-5 text-muted-foreground">
        <li v-for="c in preview.conflicts" :key="c.field">
          {{ c.field }}: keeping “{{ c.chosen }}” (of {{ c.candidates.join(', ') }})
        </li>
      </ul>
    </div>

    <div class="flex gap-2">
      <Button size="sm" @click="emit('confirm', survivorId)">Merge into one contact</Button>
      <Button size="sm" variant="ghost" @click="emit('cancel')">Cancel</Button>
    </div>
  </div>
</template>
