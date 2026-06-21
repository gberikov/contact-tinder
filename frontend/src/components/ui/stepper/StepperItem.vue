<script setup lang="ts">
import { cn } from '@/lib/utils';
import { StepperItem, type StepperItemProps, useForwardProps } from 'reka-ui';
import { computed } from 'vue';

const props = defineProps<StepperItemProps & { class?: string }>();

const delegated = computed(() => {
  const { class: _, ...rest } = props;
  return rest;
});
const forwarded = useForwardProps(delegated);
</script>

<template>
  <StepperItem
    v-bind="forwarded"
    v-slot="slotProps"
    :class="cn('group flex flex-1 flex-col items-center', props.class)"
  >
    <slot v-bind="slotProps" />
  </StepperItem>
</template>
