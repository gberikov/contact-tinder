<script setup lang="ts">
import { cn } from '@/lib/utils';
import { AlertDialogOverlay, type AlertDialogOverlayProps } from 'reka-ui';

const props = defineProps<AlertDialogOverlayProps & { class?: string }>();
</script>

<template>
  <AlertDialogOverlay
    v-bind="props"
    :class="
      cn(
        'fixed inset-0 z-50 bg-black/80 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
        props.class,
      )
    "
  />
</template>
