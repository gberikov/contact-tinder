<script setup lang="ts">
import { cn } from '@/lib/utils';
import { AlertDialogDescription, type AlertDialogDescriptionProps } from 'reka-ui';

const props = defineProps<AlertDialogDescriptionProps & { class?: string }>();
</script>

<template>
  <AlertDialogDescription
    v-bind="props"
    :class="cn('text-sm text-muted-foreground', props.class)"
  >
    <slot />
  </AlertDialogDescription>
</template>
