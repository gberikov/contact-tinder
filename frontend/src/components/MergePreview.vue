<script setup lang="ts">
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
  <div class="preview" v-if="preview">
    <h4>Proposed merge</h4>
    <p>Keep as survivor:</p>
    <label v-for="m in cluster.members" :key="m.workingCopyContactId" class="survivor-opt">
      <input
        type="radio"
        :value="m.workingCopyContactId"
        :checked="m.workingCopyContactId === survivorId"
        @change="chooseSurvivor(m.workingCopyContactId)"
      />
      {{ m.contact.displayName ?? m.workingCopyContactId.slice(0, 8) }}
    </label>

    <div v-if="preview.conflicts.length" class="conflicts">
      <strong>Conflicts</strong>
      <ul>
        <li v-for="c in preview.conflicts" :key="c.field">
          {{ c.field }}: keeping “{{ c.chosen }}” (of {{ c.candidates.join(', ') }})
        </li>
      </ul>
    </div>

    <div class="actions">
      <button type="button" class="confirm" @click="emit('confirm', survivorId)">
        Merge into one contact
      </button>
      <button type="button" @click="emit('cancel')">Cancel</button>
    </div>
  </div>
</template>

<style scoped>
.survivor-opt { display: block; }
.conflicts { margin: 8px 0; }
.actions { display: flex; gap: 8px; }
</style>
