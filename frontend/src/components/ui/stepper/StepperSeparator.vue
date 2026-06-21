<script setup lang="ts">
import { cn } from '@/lib/utils';
import { StepperSeparator, type StepperSeparatorProps, useForwardProps } from 'reka-ui';
import { computed } from 'vue';

const props = defineProps<StepperSeparatorProps & { class?: string }>();

const delegated = computed(() => {
  const { class: _, ...rest } = props;
  return rest;
});
const forwarded = useForwardProps(delegated);
</script>

<template>
  <StepperSeparator
    v-bind="forwarded"
    :class="
      cn(
        'h-0.5 flex-1 rounded-full bg-muted group-data-[state=completed]:bg-primary',
        props.class,
      )
    "
  />
</template>
