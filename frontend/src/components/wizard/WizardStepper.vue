<script setup lang="ts">
import {
  Stepper,
  StepperDescription,
  StepperIndicator,
  StepperItem,
  StepperSeparator,
  StepperTitle,
  StepperTrigger,
} from '@/components/ui/stepper';
import { useWizardStore } from '@/stores/wizard';
import { STEP_KEYS, type StepKey, WIZARD_STEPS } from '@/wizard/steps';
import { Check, Loader2 } from 'lucide-vue-next';
import { storeToRefs } from 'pinia';
import { useRouter } from 'vue-router';

const wizard = useWizardStore();
const { currentStepIndex } = storeToRefs(wizard);
const router = useRouter();

function onStepChange(index: number | undefined) {
  if (index == null) return;
  const key = STEP_KEYS[index - 1];
  if (!key || !wizard.available(key)) return;
  wizard.goToStep(key);
  router.push(WIZARD_STEPS[index - 1].route);
}
</script>

<template>
  <nav aria-label="Progress">
    <!-- Compact form for narrow viewports (FR-016) -->
    <div class="mb-2 flex items-center gap-2 text-sm font-medium sm:hidden">
      <span class="text-muted-foreground">Step {{ currentStepIndex }} of 6 —</span>
      <span class="text-primary">{{ WIZARD_STEPS[currentStepIndex - 1].label }}</span>
    </div>

    <Stepper
      :model-value="currentStepIndex"
      :linear="false"
      class="hidden items-start sm:flex"
      @update:model-value="onStepChange"
    >
      <template v-for="(step, i) in WIZARD_STEPS" :key="step.key">
        <StepperItem
          :step="step.index"
          :completed="wizard.completed(step.key)"
          :disabled="!wizard.available(step.key)"
          class="flex-col"
          :data-running="wizard.running(step.key) ? '' : undefined"
        >
          <StepperTrigger :class="wizard.running(step.key) ? 'cursor-progress' : ''">
            <StepperIndicator
              :class="
                wizard.running(step.key)
                  ? 'border-running bg-running text-white animate-pulse'
                  : ''
              "
            >
              <Loader2 v-if="wizard.running(step.key)" class="size-4 animate-spin" />
              <Check v-else-if="wizard.completed(step.key) && step.index !== currentStepIndex" class="size-4" />
              <span v-else>{{ step.index }}</span>
            </StepperIndicator>
            <StepperTitle :class="step.index === currentStepIndex ? 'text-primary' : ''">
              {{ step.label }}
            </StepperTitle>
            <StepperDescription class="hidden md:block">
              {{ step.description }}
            </StepperDescription>
          </StepperTrigger>
        </StepperItem>
        <StepperSeparator
          v-if="i < WIZARD_STEPS.length - 1"
          :data-state="wizard.completed(step.key) ? 'completed' : 'inactive'"
          class="mt-4"
        />
      </template>
    </Stepper>
  </nav>
</template>
