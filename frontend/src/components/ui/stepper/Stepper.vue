<script setup lang="ts">
import { cn } from '@/lib/utils';
import {
  StepperRoot,
  type StepperRootEmits,
  type StepperRootProps,
  useForwardPropsEmits,
} from 'reka-ui';
import { computed } from 'vue';

const props = defineProps<StepperRootProps & { class?: string }>();
const emits = defineEmits<StepperRootEmits>();

const delegated = computed(() => {
  const { class: _, ...rest } = props;
  return rest;
});
const forwarded = useForwardPropsEmits(delegated, emits);
</script>

<template>
  <StepperRoot v-bind="forwarded" :class="cn('flex w-full gap-2', props.class)">
    <slot />
  </StepperRoot>
</template>
