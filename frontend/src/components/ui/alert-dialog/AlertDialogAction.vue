<script setup lang="ts">
import { buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { AlertDialogAction, type AlertDialogActionProps } from 'reka-ui';

const props = defineProps<AlertDialogActionProps & { class?: string }>();
</script>

<template>
  <AlertDialogAction
    v-bind="props"
    :class="cn(buttonVariants(), props.class)"
  >
    <slot />
  </AlertDialogAction>
</template>
