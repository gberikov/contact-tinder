<script setup lang="ts">
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useDedupStore } from '@/stores/dedup';
import { storeToRefs } from 'pinia';

const props = defineProps<{ workingCopyId: string }>();
// Tell the wizard a run finished so it can re-derive Merge completion (enables Continue).
const emit = defineEmits<{ done: [] }>();
const store = useDedupStore();
const { run, loading, error } = storeToRefs(store);

async function findDuplicates() {
  await store.startRun(props.workingCopyId);
  emit('done');
}
</script>

<template>
  <div class="flex flex-wrap items-center gap-3">
    <Button :disabled="loading" @click="findDuplicates">
      {{ loading ? 'Finding duplicates…' : run ? 'Find duplicates again' : 'Find duplicates' }}
    </Button>
    <Badge v-if="run" variant="secondary">
      Run {{ run.status }}<template v-if="run.clusterCount != null"> — {{ run.clusterCount }} clusters</template>
    </Badge>
    <span v-if="error" class="text-sm text-destructive">{{ error }}</span>
  </div>
</template>
