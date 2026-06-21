<script setup lang="ts">
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useTidyStore } from '@/stores/tidy';
import { storeToRefs } from 'pinia';
import { computed } from 'vue';

const props = defineProps<{ workingCopyId: string; sessionId?: string }>();
const store = useTidyStore();
const { run, region, loading, error } = storeToRefs(store);

const isRunning = computed(() => store.isRunning);
const summary = computed(() => store.summary);

function onRegionInput(e: Event) {
  const v = (e.target as HTMLInputElement).value.toUpperCase().slice(0, 2);
  if (v.length === 2) store.setRegion(v);
}

async function start() {
  await store.startRun(props.workingCopyId, props.sessionId);
}
</script>

<template>
  <div class="space-y-4">
    <!-- Phone-parsing region: highlighted so the operator notices which country numbers are read as. -->
    <div class="flex flex-wrap items-center gap-2 text-sm">
      <span class="text-muted-foreground">Phone region</span>
      <Badge variant="default" class="font-mono">{{ region ?? '—' }}</Badge>
      <Input
        :model-value="region ?? ''"
        maxlength="2"
        placeholder="KZ"
        class="h-8 w-16 font-mono uppercase"
        aria-label="Phone parsing region"
        @input="onRegionInput"
      />
      <span class="text-xs text-muted-foreground"
        >national-format numbers are read as this country</span
      >
    </div>

    <div class="flex flex-wrap items-center gap-3">
      <Button :disabled="loading || isRunning" @click="start">
        <template v-if="isRunning">Checking…</template>
        <template v-else-if="run">Run check again</template>
        <template v-else>Run check</template>
      </Button>

      <Badge v-if="isRunning" variant="secondary">Running…</Badge>

      <template v-if="summary && run?.status === 'completed'">
        <Badge variant="secondary">Auto-fixed {{ summary.auto }}</Badge>
        <Badge variant="secondary">To review {{ summary.pending }}</Badge>
        <Badge variant="secondary">Checked {{ summary.checked }}</Badge>
      </template>

      <span v-if="error || run?.status === 'failed'" class="text-sm text-destructive">
        {{ error ?? run?.lastError ?? 'Check failed' }}
        <Button variant="outline" size="sm" class="ml-2" @click="start">Retry</Button>
      </span>
    </div>
  </div>
</template>
