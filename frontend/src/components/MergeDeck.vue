<script setup lang="ts">
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { type Cluster, type MergePreview, api } from '@/services/api';
import { useDedupStore } from '@/stores/dedup';
import { Combine, Loader2, Users } from 'lucide-vue-next';
import { storeToRefs } from 'pinia';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import ConfidenceBadge from './ConfidenceBadge.vue';

// One decision at a time (FR-011): the strongest pending cluster sits in the centre of the deck,
// the two fixed actions live in a stable bar below so they never move as card height changes.
const emit = defineEmits<{ change: [] }>();

const store = useDedupStore();
const { run, pendingClusters } = storeToRefs(store);

const current = computed<Cluster | null>(() => pendingClusters.value[0] ?? null);

// Progress is over this run's clusters: decided so far vs. the total we started with.
const mergedCount = ref(0);
const dismissedCount = ref(0);
const decided = computed(() => mergedCount.value + dismissedCount.value);
const total = computed(() => decided.value + pendingClusters.value.length);
const position = computed(() => Math.min(decided.value + 1, total.value));
const pct = computed(() => (total.value ? Math.round((decided.value / total.value) * 100) : 0));

// Reset the tally whenever a fresh dedup run replaces the previous one.
watch(
  () => run.value?.id,
  () => {
    mergedCount.value = 0;
    dismissedCount.value = 0;
  },
);

// Proposed merge for the active cluster: which contact is kept (survivor) and any field conflicts.
const preview = ref<MergePreview | null>(null);
const survivorId = ref('');
const previewLoading = ref(false);
const busy = ref(false);

async function loadPreview(survivor?: string) {
  const c = current.value;
  if (!c) {
    preview.value = null;
    survivorId.value = '';
    return;
  }
  previewLoading.value = true;
  try {
    preview.value = await api.mergePreview(c.id, survivor);
    survivorId.value = preview.value.survivorContactId;
  } finally {
    previewLoading.value = false;
  }
}

watch(
  current,
  (c) => {
    if (c) loadPreview();
    else preview.value = null;
  },
  { immediate: true },
);

function chooseSurvivor(id: string) {
  if (id !== survivorId.value) loadPreview(id);
}

async function doMerge() {
  const c = current.value;
  if (!c || busy.value || previewLoading.value) return;
  busy.value = true;
  try {
    await store.merge(c.id, survivorId.value || undefined);
    mergedCount.value++;
    emit('change');
  } finally {
    busy.value = false;
  }
}

async function doDismiss() {
  const c = current.value;
  if (!c || busy.value) return;
  busy.value = true;
  try {
    await store.dismiss(c.id);
    dismissedCount.value++;
    emit('change');
  } finally {
    busy.value = false;
  }
}

// Hotkeys: M = merge · N = not a duplicate. Ignore while typing in a text field.
function onKey(e: KeyboardEvent) {
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  const el = e.target as HTMLElement | null;
  const tag = el?.tagName;
  const type = (el as HTMLInputElement | null)?.type;
  if (
    el &&
    (tag === 'TEXTAREA' ||
      el.isContentEditable ||
      (tag === 'INPUT' && type !== 'radio' && type !== 'checkbox'))
  ) {
    return;
  }
  if (!current.value) return;
  const key = e.key.toLowerCase();
  if (key === 'm') doMerge();
  else if (key === 'n') doDismiss();
  else return;
  e.preventDefault();
}

onMounted(() => window.addEventListener('keydown', onKey));
onBeforeUnmount(() => window.removeEventListener('keydown', onKey));

function nameOf(c: { displayName?: string | null }, id: string) {
  return c.displayName ?? id.slice(0, 8);
}
</script>

<template>
  <div v-if="run" class="mx-auto max-w-md space-y-4">
    <!-- Progress along the run's clusters -->
    <div class="space-y-1.5">
      <div class="flex items-baseline justify-between text-sm">
        <span class="font-medium tabular-nums">
          <template v-if="current">Duplicate {{ position }} of {{ total }}</template>
          <template v-else>All reviewed</template>
        </span>
        <span class="text-muted-foreground tabular-nums">{{ decided }}/{{ total }} done</span>
      </div>
      <div class="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          class="h-full rounded-full bg-primary transition-[width] duration-300 ease-out"
          :style="{ width: `${current ? pct : 100}%` }"
        />
      </div>
    </div>

    <!-- Decision deck: fixed height keeps the action bar anchored regardless of card content -->
    <div class="h-[24rem]">
      <!-- Active cluster -->
      <div
        v-if="current"
        :key="current.id"
        class="flex h-full flex-col rounded-xl border bg-card shadow-sm"
      >
        <header class="flex items-center gap-2 border-b px-4 py-3">
          <ConfidenceBadge :confidence="current.confidence" />
          <span class="text-sm text-muted-foreground">{{ current.size }} contacts look alike</span>
          <Loader2 v-if="previewLoading" class="ml-auto size-4 animate-spin text-muted-foreground" />
        </header>

        <div class="flex-1 space-y-3 overflow-y-auto px-4 py-3">
          <p class="text-sm text-muted-foreground">
            Pick the one to keep — the rest fold into it.
          </p>
          <label
            v-for="m in current.members"
            :key="m.workingCopyContactId"
            class="flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors"
            :class="
              m.workingCopyContactId === survivorId
                ? 'border-primary bg-primary/5'
                : 'hover:bg-muted/50'
            "
          >
            <input
              type="radio"
              name="survivor"
              class="mt-1 accent-primary"
              :value="m.workingCopyContactId"
              :checked="m.workingCopyContactId === survivorId"
              @change="chooseSurvivor(m.workingCopyContactId)"
            >
            <span class="min-w-0 flex-1 space-y-0.5">
              <span class="flex items-center gap-2">
                <strong class="truncate">{{ nameOf(m.contact, m.workingCopyContactId) }}</strong>
                <Badge
                  v-if="m.workingCopyContactId === survivorId"
                  variant="success"
                  class="shrink-0"
                >
                  Kept
                </Badge>
              </span>
              <span v-if="m.contact.primaryEmail" class="block truncate text-sm text-muted-foreground">
                {{ m.contact.primaryEmail }}
              </span>
              <span v-if="m.contact.primaryPhone" class="block truncate text-sm text-muted-foreground">
                {{ m.contact.primaryPhone }}
              </span>
            </span>
          </label>

          <div v-if="preview?.conflicts.length" class="rounded-lg bg-muted/40 p-3 text-sm">
            <p class="mb-1 font-medium">Differences we'll reconcile</p>
            <ul class="list-disc space-y-0.5 pl-5 text-muted-foreground">
              <li v-for="c in preview.conflicts" :key="c.field">
                {{ c.field }}: keeping “{{ c.chosen }}”
              </li>
            </ul>
          </div>
        </div>
      </div>

      <!-- Done -->
      <div
        v-else
        class="flex h-full flex-col items-center justify-center gap-3 rounded-xl border border-dashed bg-card/50 px-6 text-center"
      >
        <div class="rounded-full bg-emerald-100 p-3 text-emerald-700">
          <Users class="size-6" />
        </div>
        <p class="text-base font-medium">
          {{ total ? 'All duplicates reviewed' : 'No duplicates found' }}
        </p>
        <p v-if="total" class="text-sm text-muted-foreground">
          Merged {{ mergedCount }} · kept {{ dismissedCount }} separate.
        </p>
        <p class="text-sm text-muted-foreground">Press <strong>Continue</strong> to move on.</p>
      </div>
    </div>

    <!-- Fixed action bar — same place every card -->
    <div class="grid grid-cols-2 gap-3">
      <Button
        size="lg"
        class="w-full bg-emerald-600 text-white shadow hover:bg-emerald-700"
        :disabled="!current || busy"
        @click="doDismiss"
      >
        <Users /> Not a duplicate
      </Button>
      <Button
        size="lg"
        class="w-full bg-amber-500 text-white shadow hover:bg-amber-600"
        :disabled="!current || busy || previewLoading"
        @click="doMerge"
      >
        <Combine /> Merge
      </Button>
    </div>

    <p
      class="text-center text-xs text-muted-foreground [&_kbd]:rounded [&_kbd]:border [&_kbd]:bg-muted [&_kbd]:px-1.5 [&_kbd]:py-0.5"
    >
      <kbd>N</kbd> not a duplicate · <kbd>M</kbd> merge
    </p>
  </div>
</template>
