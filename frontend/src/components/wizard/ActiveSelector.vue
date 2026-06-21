<script setup lang="ts">
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { SelectorItem } from '@/components/wizard/types';
import { cn } from '@/lib/utils';
import { Check } from 'lucide-vue-next';

defineProps<{
  items: SelectorItem[];
  activeId: string | null;
  emptyText?: string;
}>();

const emit = defineEmits<(e: 'select', id: string) => void>();
</script>

<template>
  <div class="space-y-2">
    <p v-if="items.length === 0" class="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
      {{ emptyText ?? 'Nothing here yet.' }}
    </p>

    <button
      v-for="item in items"
      :key="item.id"
      type="button"
      :class="
        cn(
          'flex w-full items-center justify-between rounded-lg border p-3 text-left transition-colors hover:bg-accent/50',
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
        <Button v-else variant="ghost" size="sm">Set active</Button>
      </span>
    </button>
  </div>
</template>
