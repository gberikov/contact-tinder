<script setup lang="ts">
import { Button } from '@/components/ui/button';
import ActiveSelector from '@/components/wizard/ActiveSelector.vue';
import type { SelectorItem } from '@/components/wizard/types';
import { api } from '@/services/api';
import { useWizardStore } from '@/stores/wizard';
import { computed, ref } from 'vue';

const wizard = useWizardStore();
const error = ref<string | null>(null);

const items = computed<SelectorItem[]>(() =>
  wizard.accounts.map((a) => ({
    id: a.id,
    title: a.email,
    status: a.status,
    statusVariant:
      a.status === 'connected'
        ? 'success'
        : a.status === 'needs_reauth'
          ? 'destructive'
          : 'secondary',
  })),
);

async function connect() {
  try {
    const { authorizationUrl } = await api.connect();
    window.location.href = authorizationUrl;
  } catch (e) {
    error.value = (e as Error).message;
  }
}

function select(id: string) {
  wizard.setActiveAccount(id);
}
</script>

<template>
  <div class="space-y-4">
    <p v-if="error" class="text-sm text-destructive">{{ error }}</p>
    <ActiveSelector
      :items="items"
      :active-id="wizard.activeAccountId"
      empty-text="No Google accounts connected yet."
      @select="select"
    />
    <Button @click="connect">Connect Google account</Button>
  </div>
</template>
