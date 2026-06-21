<script setup lang="ts">
import ExportPreview from '@/components/ExportPreview.vue';
import ExportReport from '@/components/ExportReport.vue';
import LabelPreview from '@/components/LabelPreview.vue';
import UndecidedWarning from '@/components/UndecidedWarning.vue';
import { Button } from '@/components/ui/button';
import { useExportStore } from '@/stores/export';
import { useWizardStore } from '@/stores/wizard';
import { storeToRefs } from 'pinia';
import { onMounted } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();
const wizard = useWizardStore();
// Driven by the route param on the legacy page, or by the active Draft inside the wizard.
const workingCopyId = (route.params.id as string) ?? wizard.activeWorkingCopyId ?? '';
const store = useExportStore();
const { preview, run, error, loading } = storeToRefs(store);

onMounted(() => store.loadPreview(workingCopyId));

async function run_() {
  await store.start(workingCopyId);
}

async function confirm() {
  try {
    await store.confirmDelete();
    await store.pollUntilDone();
  } catch {
    /* 403 → store.needsWriteScope drives the re-consent button below */
  }
}

async function reauthorize() {
  // One click → Google consent for the contacts write scope → back here to finish exporting.
  const url = await store.requestWriteConsent(`/working-copies/${workingCopyId}/export`);
  window.location.href = url;
}
</script>

<template>
  <section class="space-y-4">
    <p v-if="loading" class="text-sm text-muted-foreground">Loading preview…</p>

    <template v-else-if="preview">
      <p v-if="store.nothingToExport" class="text-sm text-muted-foreground">
        Nothing to export — no contacts are decided <em>delete</em> and none are in the Processing
        Queue. Review some contacts first.
      </p>

      <template v-else>
        <UndecidedWarning :count="preview.undecidedCount" />
        <ExportPreview :count="preview.deleteCount" :contacts="preview.deleteSet" />
        <LabelPreview
          :count="preview.labelCount"
          :label-name="preview.labelName"
          :contacts="preview.labelSet"
        />

        <div v-if="!run">
          <Button @click="run_">Start export</Button>
        </div>

        <div v-else class="space-y-3">
          <p v-if="run.status === 'previewing'" class="text-sm text-muted-foreground">
            Deletion needs your explicit confirmation; labeling runs alongside automatically.
          </p>
          <Button v-if="run.status === 'previewing'" variant="destructive" @click="confirm">
            Confirm &amp; run export
          </Button>

          <div
            v-if="store.needsWriteScope"
            class="space-y-2 rounded-lg border border-amber-300 bg-amber-50 p-3 dark:border-amber-700/60 dark:bg-amber-950/40"
          >
            <p class="text-sm text-amber-900 dark:text-amber-200">
              Google hasn't granted write access to contacts for this account yet.
            </p>
            <Button @click="reauthorize">Allow Google access and continue</Button>
          </div>
          <p v-else-if="error" class="text-sm text-destructive">{{ error }}</p>

          <ExportReport
            v-if="run.status !== 'previewing'"
            :run="run"
            :report="run.report"
            :can-undo-delete="store.canUndoDelete"
            :can-undo-label="store.canUndoLabel"
            @undo-delete="store.undoDelete()"
            @undo-label="store.undoLabel()"
          />
        </div>
      </template>
    </template>
  </section>
</template>
