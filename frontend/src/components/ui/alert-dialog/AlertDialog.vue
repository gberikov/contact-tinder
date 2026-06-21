<script setup lang="ts">
import { type AlertDialogProps, AlertDialogRoot } from 'reka-ui';

const props = defineProps<AlertDialogProps>();
</script>

<template>
  <AlertDialogRoot v-bind="props">
    <slot />
  </AlertDialogRoot>
</template>
