<script setup lang="ts">
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import type { Cluster } from '@/services/api';
import { ref } from 'vue';
import ConfidenceBadge from './ConfidenceBadge.vue';
import MergePreview from './MergePreview.vue';

const props = defineProps<{ cluster: Cluster }>();
const emit = defineEmits<{
  merge: [clusterId: string, survivorId: string];
  dismiss: [clusterId: string];
}>();

const showPreview = ref(false);

function onConfirm(survivorId: string) {
  showPreview.value = false;
  emit('merge', props.cluster.id, survivorId);
}
</script>

<template>
  <Card>
    <CardContent class="space-y-3 p-4">
      <header class="flex items-center gap-2">
        <ConfidenceBadge :confidence="cluster.confidence" />
        <span class="text-sm text-muted-foreground">{{ cluster.size }} contacts</span>
      </header>
      <ul class="space-y-1 text-sm">
        <li
          v-for="m in cluster.members"
          :key="m.workingCopyContactId"
          class="flex flex-wrap gap-x-3"
        >
          <strong>{{ m.contact.displayName ?? '—' }}</strong>
          <span class="text-muted-foreground">{{ m.contact.primaryEmail ?? '' }}</span>
          <span class="text-muted-foreground">{{ m.contact.primaryPhone ?? '' }}</span>
        </li>
      </ul>

      <div v-if="!showPreview" class="flex gap-2">
        <Button size="sm" @click="showPreview = true">Merge…</Button>
        <Button size="sm" variant="outline" @click="emit('dismiss', cluster.id)">
          Not a duplicate
        </Button>
      </div>
      <MergePreview v-else :cluster="cluster" @confirm="onConfirm" @cancel="showPreview = false" />
    </CardContent>
  </Card>
</template>
