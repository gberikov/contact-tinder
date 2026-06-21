<script setup lang="ts">
import { buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { AlertDialogCancel, type AlertDialogCancelProps } from 'reka-ui';

const props = defineProps<AlertDialogCancelProps & { class?: string }>();
</script>

<template>
  <AlertDialogCancel
    v-bind="props"
    :class="cn(buttonVariants({ variant: 'outline' }), props.class)"
  >
    <slot />
  </AlertDialogCancel>
</template>
