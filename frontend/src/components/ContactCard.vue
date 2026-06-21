<script setup lang="ts">
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { ContactDetail } from '@/services/api';
import { computed } from 'vue';

const props = defineProps<{ contact: ContactDetail }>();

// The Draft stores each contact's raw Google People payload. We surface every field
// the reviewer might need to decide — not just the primaries — so triage is informed.
type Rec = Record<string, unknown>;
interface Row {
  sub: string | null;
  value: string;
}
interface Section {
  key: string;
  label: string;
  rows: Row[];
}

function entries(payload: Rec, key: string): Rec[] {
  const v = payload[key];
  return Array.isArray(v) ? (v as Rec[]) : [];
}
function text(v: unknown): string | null {
  return typeof v === 'string' && v.trim() ? v.trim() : null;
}
function sublabel(r: Rec): string | null {
  return text(r.formattedType) ?? text(r.type);
}
// Google People flags one entry per field as primary; show it first.
function primaryFirst(list: Rec[]): Rec[] {
  return [...list].sort((a, b) => {
    const ap = (a.metadata as Rec | undefined)?.primary === true ? 0 : 1;
    const bp = (b.metadata as Rec | undefined)?.primary === true ? 0 : 1;
    return ap - bp;
  });
}

const MONTHS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
];
function birthday(r: Rec): string | null {
  const d = r.date as Rec | undefined;
  if (d && typeof d.month === 'number' && typeof d.day === 'number') {
    const md = `${MONTHS[(d.month as number) - 1] ?? ''} ${d.day}`.trim();
    return typeof d.year === 'number' ? `${md}, ${d.year}` : md;
  }
  return text(r.text);
}

const nickname = computed<string | null>(() => {
  const first = entries(props.contact.payload as Rec, 'nicknames')[0];
  return first ? text(first.value) : null;
});

const sections = computed<Section[]>(() => {
  const p = props.contact.payload as Rec;
  const out: Section[] = [];

  const emails = primaryFirst(entries(p, 'emailAddresses'))
    .map((r): Row | null => {
      const value = text(r.value);
      return value ? { sub: sublabel(r), value } : null;
    })
    .filter((r): r is Row => r !== null);
  if (emails.length) out.push({ key: 'email', label: 'Email', rows: emails });
  else if (props.contact.primaryEmail)
    out.push({
      key: 'email',
      label: 'Email',
      rows: [{ sub: null, value: props.contact.primaryEmail }],
    });

  const phones = primaryFirst(entries(p, 'phoneNumbers'))
    .map((r): Row | null => {
      const value = text(r.value);
      return value ? { sub: sublabel(r), value } : null;
    })
    .filter((r): r is Row => r !== null);
  if (phones.length) out.push({ key: 'phone', label: 'Phone', rows: phones });
  else if (props.contact.primaryPhone)
    out.push({
      key: 'phone',
      label: 'Phone',
      rows: [{ sub: null, value: props.contact.primaryPhone }],
    });

  const orgs = entries(p, 'organizations')
    .map((r): Row | null => {
      const place = [text(r.name), text(r.department)].filter(Boolean).join(' · ');
      const value = [text(r.title), place].filter(Boolean).join(' — ');
      return value ? { sub: null, value } : null;
    })
    .filter((r): r is Row => r !== null);
  if (orgs.length) out.push({ key: 'org', label: 'Organization', rows: orgs });
  else if (props.contact.organization)
    out.push({
      key: 'org',
      label: 'Organization',
      rows: [{ sub: null, value: props.contact.organization }],
    });

  const addresses = entries(p, 'addresses')
    .map((r): Row | null => {
      const value =
        text(r.formattedValue) ??
        [text(r.streetAddress), text(r.city), text(r.region), text(r.postalCode), text(r.country)]
          .filter(Boolean)
          .join(', ');
      return value ? { sub: sublabel(r), value } : null;
    })
    .filter((r): r is Row => r !== null);
  if (addresses.length) out.push({ key: 'address', label: 'Address', rows: addresses });

  const urls = entries(p, 'urls')
    .map((r): Row | null => {
      const value = text(r.value);
      return value ? { sub: sublabel(r), value } : null;
    })
    .filter((r): r is Row => r !== null);
  if (urls.length) out.push({ key: 'url', label: 'Website', rows: urls });

  const birthdays = entries(p, 'birthdays')
    .map((r): Row | null => {
      const value = birthday(r);
      return value ? { sub: null, value } : null;
    })
    .filter((r): r is Row => r !== null);
  if (birthdays.length) out.push({ key: 'birthday', label: 'Birthday', rows: birthdays });

  const notes = entries(p, 'biographies')
    .map((r): Row | null => {
      const value = text(r.value);
      return value ? { sub: null, value } : null;
    })
    .filter((r): r is Row => r !== null);
  if (notes.length) out.push({ key: 'notes', label: 'Notes', rows: notes });

  return out;
});
</script>

<template>
  <Card>
    <CardHeader class="pb-3">
      <CardTitle class="name text-xl">{{ contact.displayName ?? '(no name)' }}</CardTitle>
      <p v-if="nickname" class="text-sm text-muted-foreground">“{{ nickname }}”</p>
    </CardHeader>
    <CardContent class="max-h-[55vh] overflow-y-auto">
      <p v-if="!sections.length" class="text-sm text-muted-foreground">No further details on file.</p>
      <div v-else class="space-y-3">
        <section v-for="s in sections" :key="s.key" class="space-y-1">
          <h4 class="text-xs font-medium uppercase tracking-wide text-muted-foreground">{{ s.label }}</h4>
          <ul class="space-y-1">
            <li
              v-for="(row, i) in s.rows"
              :key="i"
              class="flex flex-wrap items-baseline gap-x-2 text-sm"
            >
              <span v-if="row.sub" class="min-w-16 shrink-0 text-xs text-muted-foreground">{{ row.sub }}</span>
              <span class="whitespace-pre-line break-words">{{ row.value }}</span>
            </li>
          </ul>
        </section>
      </div>
    </CardContent>
  </Card>
</template>
