<script setup lang="ts">
import { cn } from '@/lib/utils';
import { StepperIndicator, type StepperIndicatorProps, useForwardProps } from 'reka-ui';
import { computed } from 'vue';

const props = defineProps<StepperIndicatorProps & { class?: string }>();

const delegated = computed(() => {
  const { class: _, ...rest } = props;
  return rest;
});
const forwarded = useForwardProps(delegated);
</script>

<template>
  <StepperIndicator
    v-bind="forwarded"
    :class="
      cn(
        'inline-flex size-8 shrink-0 items-center justify-center rounded-full border-2 border-muted bg-muted text-sm font-medium text-muted-foreground transition-colors',
        'group-data-[state=active]:border-primary group-data-[state=active]:bg-primary group-data-[state=active]:text-primary-foreground',
        'group-data-[state=completed]:border-primary group-data-[state=completed]:bg-primary group-data-[state=completed]:text-primary-foreground',
        props.class,
      )
    "
  >
    <slot />
  </StepperIndicator>
</template>
