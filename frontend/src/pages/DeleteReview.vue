<script setup lang="ts">
import DeleteBatchReview from '@/components/DeleteBatchReview.vue';
import { Button } from '@/components/ui/button';
import { useTriageStore } from '@/stores/triage';
import { ChevronLeft } from 'lucide-vue-next';
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
  <section class="mx-auto max-w-3xl space-y-4 p-6">
    <div class="flex items-center gap-2">
      <Button as-child variant="ghost" size="sm">
        <RouterLink to="/wizard/review"><ChevronLeft /> Review</RouterLink>
      </Button>
      <h2 class="text-lg font-semibold">Review deletions</h2>
    </div>
    <DeleteBatchReview
      :batch="batch"
      :records="preview"
      :error="error"
      @confirm="store.confirmDelete()"
      @undo="store.undoDelete()"
    />
    <nav class="border-t pt-4">
      <Button as-child variant="link">
        <RouterLink to="/wizard/export">Continue to Export →</RouterLink>
      </Button>
    </nav>
  </section>
</template>
