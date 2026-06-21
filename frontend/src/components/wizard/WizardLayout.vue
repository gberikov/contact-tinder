<script setup lang="ts">
import { Button } from '@/components/ui/button';
import WizardStepper from '@/components/wizard/WizardStepper.vue';
import { useWizardStore } from '@/stores/wizard';
import { type StepKey, WIZARD_STEPS, stepByKey } from '@/wizard/steps';
import { ChevronLeft, ChevronRight } from 'lucide-vue-next';
import { computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

const wizard = useWizardStore();
const route = useRoute();
const router = useRouter();

const currentKey = computed<StepKey>(() => wizard.currentStepKey);
const currentStep = computed(() => stepByKey(currentKey.value));
const canContinue = computed(
  () => wizard.completed(currentKey.value) || wizard.emptyButPassable(currentKey.value),
);
const nextStep = computed(() => WIZARD_STEPS[currentStep.value.index] ?? null);
const prevStep = computed(() => WIZARD_STEPS[currentStep.value.index - 2] ?? null);

function syncFromRoute() {
  const key = route.path.split('/').pop() as StepKey | undefined;
  if (key && WIZARD_STEPS.some((s) => s.key === key)) {
    if (wizard.available(key)) {
      wizard.currentStepKey = key;
    } else {
      // gate: bounce to the first incomplete step (FR-006/007)
      const target = wizard.firstIncompleteStep();
      wizard.currentStepKey = target;
      router.replace(stepByKey(target).route);
    }
  }
}

function goNext() {
  if (!nextStep.value || !canContinue.value) return;
  wizard.goToStep(nextStep.value.key);
  router.push(nextStep.value.route);
}
function goBack() {
  if (!prevStep.value) return;
  wizard.goToStep(prevStep.value.key);
  router.push(prevStep.value.route);
}

onMounted(async () => {
  await wizard.hydrate();
  syncFromRoute();
});
watch(() => route.path, syncFromRoute);
</script>

<template>
  <div class="mx-auto min-h-screen max-w-5xl px-4 py-6">
    <header class="mb-6 flex items-center justify-between">
      <h1 class="text-xl font-semibold tracking-tight">Contact&nbsp;Tinder</h1>
      <span v-if="wizard.activeAccount" class="text-sm text-muted-foreground">
        {{ wizard.activeAccount.email }}
      </span>
    </header>

    <WizardStepper class="mb-8" />

    <main class="rounded-xl border bg-card p-6 shadow-sm">
      <div class="mb-4">
        <h2 class="text-lg font-semibold">{{ currentStep.label }}</h2>
        <p class="text-sm text-muted-foreground">{{ currentStep.description }}</p>
      </div>
      <RouterView />
    </main>

    <footer class="mt-6 flex items-center justify-between">
      <Button variant="outline" :disabled="!prevStep" @click="goBack">
        <ChevronLeft /> Back
      </Button>
      <Button :disabled="!canContinue || !nextStep" @click="goNext">
        Continue <ChevronRight />
      </Button>
    </footer>
  </div>
</template>
