<script setup lang="ts">
import { cn } from '@/lib/utils';
import { AlertDialogTitle, type AlertDialogTitleProps } from 'reka-ui';

const props = defineProps<AlertDialogTitleProps & { class?: string }>();
</script>

<template>
  <AlertDialogTitle
    v-bind="props"
    :class="cn('text-lg font-semibold', props.class)"
  >
    <slot />
  </AlertDialogTitle>
</template>
