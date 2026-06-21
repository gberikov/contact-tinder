<script setup lang="ts">
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useTidyStore } from '@/stores/tidy';
import { storeToRefs } from 'pinia';

// Read-only list of what Tidy auto-applied, with a per-fix Undo so the operator can correct anything
// they disagree with (the field reverts to its exact pre-fix value).
const store = useTidyStore();
const { autoFixes } = storeToRefs(store);
</script>

<template>
  <div v-if="autoFixes.length" class="space-y-2">
    <div
      v-for="f in autoFixes"
      :key="f.stagedEditId"
      class="flex flex-col gap-2 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between"
    >
      <div class="min-w-0">
        <div class="flex items-center gap-2">
          <Badge variant="success">{{ f.fieldKind }}</Badge>
          <span class="truncate text-sm font-medium">{{ f.contactDisplayName ?? 'Contact' }}</span>
        </div>
        <div class="mt-1 truncate font-mono text-xs">
          <span class="text-muted-foreground line-through">{{ f.before }}</span>
          <span class="mx-1 text-muted-foreground">→</span>
          <span class="text-foreground">{{ f.after }}</span>
        </div>
      </div>
      <Button variant="outline" size="sm" @click="store.undoEdit(f.stagedEditId)">Undo</Button>
    </div>
  </div>
  <p v-else class="rounded-md border bg-muted/40 p-4 text-sm text-muted-foreground">
    No automatic fixes were applied.
  </p>
</template>
