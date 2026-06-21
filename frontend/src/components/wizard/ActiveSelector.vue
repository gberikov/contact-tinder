<script setup lang="ts">
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { SelectorItem } from '@/components/wizard/types';
import { cn } from '@/lib/utils';
import { Check, Trash2 } from 'lucide-vue-next';

defineProps<{
  items: SelectorItem[];
  activeId: string | null;
  emptyText?: string;
  deletable?: boolean;
}>();

const emit = defineEmits<{
  (e: 'select', id: string): void;
  (e: 'delete', id: string): void;
}>();
</script>

<template>
  <div class="space-y-2">
    <p v-if="items.length === 0" class="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
      {{ emptyText ?? 'Nothing here yet.' }}
    </p>

    <div v-for="item in items" :key="item.id" class="flex items-center gap-2">
      <button
        type="button"
        :class="
          cn(
            'flex min-w-0 flex-1 items-center justify-between rounded-lg border p-3 text-left transition-colors hover:bg-accent/50',
            item.id === activeId ? 'border-primary ring-1 ring-primary' : 'border-border',
          )
        "
        @click="emit('select', item.id)"
      >
        <span class="min-w-0">
          <span class="block truncate font-medium">{{ item.title }}</span>
          <span v-if="item.subtitle" class="block truncate text-xs text-muted-foreground">
            {{ item.subtitle }}
          </span>
        </span>
        <span class="flex shrink-0 items-center gap-2">
          <Badge v-if="item.status" :variant="item.statusVariant ?? 'secondary'">
            {{ item.status }}
          </Badge>
          <Badge v-if="item.id === activeId" variant="default" class="gap-1">
            <Check class="size-3" /> Active
          </Badge>
          <span v-else class="text-xs text-muted-foreground">Set active</span>
        </span>
      </button>

      <Button
        v-if="deletable"
        variant="ghost"
        size="icon"
        :aria-label="`Delete ${item.title}`"
        class="shrink-0 text-muted-foreground hover:text-destructive"
        @click="emit('delete', item.id)"
      >
        <Trash2 class="size-4" />
      </Button>
    </div>
  </div>
</template>
