<script setup lang="ts">
import { cn } from '@/lib/utils';
import { StepperDescription, type StepperDescriptionProps, useForwardProps } from 'reka-ui';
import { computed } from 'vue';

const props = defineProps<StepperDescriptionProps & { class?: string }>();

const delegated = computed(() => {
  const { class: _, ...rest } = props;
  return rest;
});
const forwarded = useForwardProps(delegated);
</script>

<template>
  <StepperDescription
    v-bind="forwarded"
    :class="cn('text-xs text-muted-foreground', props.class)"
  >
    <slot />
  </StepperDescription>
</template>
