<script setup lang="ts">
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';

defineProps<{
  open: boolean;
  title: string;
  description: string;
  confirmText?: string;
}>();

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void;
  (e: 'confirm'): void;
}>();
</script>

<template>
  <AlertDialog :open="open" @update:open="emit('update:open', $event)">
    <AlertDialogContent>
      <AlertDialogHeader>
        <AlertDialogTitle>{{ title }}</AlertDialogTitle>
        <AlertDialogDescription>{{ description }}</AlertDialogDescription>
      </AlertDialogHeader>
      <AlertDialogFooter>
        <AlertDialogCancel>Cancel</AlertDialogCancel>
        <!-- Plain Button, NOT AlertDialogAction: the latter is a reka DialogClose that ALSO emits
             update:open(false), which races ahead of `confirm` and clears the caller's pending
             target before it runs. The caller closes the dialog itself after handling confirm. -->
        <Button variant="destructive" @click="emit('confirm')">
          {{ confirmText ?? 'Delete' }}
        </Button>
      </AlertDialogFooter>
    </AlertDialogContent>
  </AlertDialog>
</template>
