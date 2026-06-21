<script setup lang="ts">
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { ResolveValidationItemBody, ValidationItem } from '@/services/api';
import { ref } from 'vue';

const props = defineProps<{ item: ValidationItem }>();
const emit = defineEmits<{
  resolve: [body: ResolveValidationItemBody];
  skip: [];
  undo: [editId: string];
}>();

const ISSUE_LABEL: Record<string, string> = {
  invalid_phone: 'Invalid phone number',
  unclear_type: 'Phone type unclear',
  invalid_email: 'Invalid email',
  dead_email_domain: "Email domain can't receive mail",
  website_unreachable: 'Website not reachable',
  website_unsafe: "Website can't be safely checked",
};

const PHONE_TYPES = ['mobile', 'work', 'home', 'other'];

const editValue = ref(props.item.suggestedValue ?? props.item.originalValue);
</script>

<template>
  <div class="flex flex-col gap-2 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between">
    <div class="min-w-0">
      <div class="flex items-center gap-2">
        <Badge variant="outline">{{ ISSUE_LABEL[item.issueType] ?? item.issueType }}</Badge>
        <span class="truncate text-sm font-medium">{{ item.contactDisplayName ?? 'Contact' }}</span>
      </div>
      <div class="mt-1 truncate font-mono text-sm text-muted-foreground">{{ item.originalValue }}</div>
    </div>

    <!-- Resolved/skipped: show outcome + undo for any staged edit. -->
    <div v-if="item.status !== 'pending'" class="flex items-center gap-2">
      <Badge :variant="item.status === 'resolved' ? 'success' : 'secondary'">{{ item.status }}</Badge>
      <Button
        v-if="item.stagedEditId"
        variant="outline"
        size="sm"
        @click="emit('undo', item.stagedEditId)"
      >
        Undo
      </Button>
    </div>

    <!-- Pending unclear-type: explicit type choice. -->
    <div v-else-if="item.issueType === 'unclear_type'" class="flex flex-wrap items-center gap-1">
      <Button
        v-for="t in PHONE_TYPES"
        :key="t"
        variant="outline"
        size="sm"
        @click="emit('resolve', { action: 'set_type', type: t })"
      >
        {{ t }}
      </Button>
      <Button variant="ghost" size="sm" @click="emit('skip')">Skip</Button>
    </div>

    <!-- Pending invalid value / dead destination: edit, remove, or skip. -->
    <div v-else class="flex flex-wrap items-center gap-2">
      <Input v-model="editValue" class="h-8 w-48 font-mono" :aria-label="`Edit ${item.fieldKind}`" />
      <Button size="sm" @click="emit('resolve', { action: 'edit_value', value: editValue })">
        Save
      </Button>
      <Button
        variant="outline"
        size="sm"
        @click="emit('resolve', { action: 'remove_field' })"
      >
        Remove
      </Button>
      <Button variant="ghost" size="sm" @click="emit('skip')">Skip</Button>
    </div>
  </div>
</template>
