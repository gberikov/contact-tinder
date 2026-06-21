<script setup lang="ts">
import { cn } from '@/lib/utils';
import { StepperTitle, type StepperTitleProps, useForwardProps } from 'reka-ui';
import { computed } from 'vue';

const props = defineProps<StepperTitleProps & { class?: string }>();

const delegated = computed(() => {
  const { class: _, ...rest } = props;
  return rest;
});
const forwarded = useForwardProps(delegated);
</script>

<template>
  <StepperTitle v-bind="forwarded" :class="cn('text-sm font-medium', props.class)">
    <slot />
  </StepperTitle>
</template>
