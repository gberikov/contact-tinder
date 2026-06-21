<script setup lang="ts">
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { ContactDetail } from '@/services/api';

defineProps<{ contact: ContactDetail }>();
</script>

<template>
  <Card>
    <CardHeader>
      <CardTitle class="name">{{ contact.displayName ?? '(no name)' }}</CardTitle>
    </CardHeader>
    <CardContent>
      <dl class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
        <template v-if="contact.primaryEmail">
          <dt class="text-muted-foreground">Email</dt>
          <dd>{{ contact.primaryEmail }}</dd>
        </template>
        <template v-if="contact.primaryPhone">
          <dt class="text-muted-foreground">Phone</dt>
          <dd>{{ contact.primaryPhone }}</dd>
        </template>
        <template v-if="contact.organization">
          <dt class="text-muted-foreground">Org</dt>
          <dd>{{ contact.organization }}</dd>
        </template>
      </dl>
    </CardContent>
  </Card>
</template>
