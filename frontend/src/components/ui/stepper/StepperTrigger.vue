<script setup lang="ts">
import { cn } from '@/lib/utils';
import { StepperTrigger, type StepperTriggerProps, useForwardProps } from 'reka-ui';
import { computed } from 'vue';

const props = defineProps<StepperTriggerProps & { class?: string }>();

const delegated = computed(() => {
  const { class: _, ...rest } = props;
  return rest;
});
const forwarded = useForwardProps(delegated);
</script>

<template>
  <StepperTrigger
    v-bind="forwarded"
    :class="
      cn(
        'inline-flex flex-col items-center gap-1.5 rounded-md p-1 text-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50',
        props.class,
      )
    "
  >
    <slot />
  </StepperTrigger>
</template>
