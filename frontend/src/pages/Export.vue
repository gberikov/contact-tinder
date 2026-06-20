<script setup lang="ts">
import ExportPreview from '@/components/ExportPreview.vue';
import ExportReport from '@/components/ExportReport.vue';
import LabelPreview from '@/components/LabelPreview.vue';
import UndecidedWarning from '@/components/UndecidedWarning.vue';
import { useExportStore } from '@/stores/export';
import { storeToRefs } from 'pinia';
import { onMounted } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();
const workingCopyId = route.params.id as string;
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
    /* 403 → re-consent surfaced via store.error */
  }
}
</script>

<template>
  <section class="export-page">
    <h1>Export to Google</h1>
    <p v-if="loading">Loading preview…</p>

    <template v-else-if="preview">
      <p v-if="store.nothingToExport" class="empty">
        Nothing to export — no contacts are decided <em>delete</em> and none are in the Processing
        Queue. Triage some contacts first.
      </p>

      <template v-else>
        <UndecidedWarning :count="preview.undecidedCount" />
        <ExportPreview :count="preview.deleteCount" :contacts="preview.deleteSet" />
        <LabelPreview
          :count="preview.labelCount"
          :label-name="preview.labelName"
          :contacts="preview.labelSet"
        />

        <div v-if="!run" class="actions">
          <button type="button" @click="run_">Start export</button>
        </div>

        <div v-else class="run">
          <p class="hint" v-if="run.status === 'previewing'">
            Deletion needs your explicit confirmation; labeling runs alongside automatically.
          </p>
          <button
            v-if="run.status === 'previewing'"
            type="button"
            class="confirm"
            @click="confirm"
          >
            Confirm &amp; run export
          </button>

          <p v-if="error" class="error">
            {{ error }} — re-consent with the contacts write scope is required.
          </p>

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

<style scoped>
.empty { color: #555; }
.actions, .run { margin-top: 16px; }
.error { color: #b00020; }
.hint { color: #555; font-size: 0.9em; }
</style>
