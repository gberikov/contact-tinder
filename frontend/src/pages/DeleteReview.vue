<script setup lang="ts">
import DeleteBatchReview from '@/components/DeleteBatchReview.vue';
import { useTriageStore } from '@/stores/triage';
import { storeToRefs } from 'pinia';
import { onMounted } from 'vue';
import { RouterLink, useRoute } from 'vue-router';

const route = useRoute();
const workingCopyId = route.params.id as string;
const store = useTriageStore();
const { batch, preview, error } = storeToRefs(store);

onMounted(async () => {
  try {
    await store.buildDeleteBatch(workingCopyId);
  } catch {
    /* no contacts queued for deletion — batch stays null */
  }
});
</script>

<template>
  <section>
    <h2>Review deletions</h2>
    <DeleteBatchReview
      :batch="batch"
      :records="preview"
      :error="error"
      @confirm="store.confirmDelete()"
      @undo="store.undoDelete()"
    />
    <nav class="links">
      <RouterLink :to="`/working-copies/${workingCopyId}/export`">Export to Google →</RouterLink>
    </nav>
  </section>
</template>

<style scoped>
.links { margin-top: 20px; }
</style>
