// Static definitions for the six guided-wizard steps. Order, plain-verb labels (FR-010),
// plain-language descriptions (FR-012), routes, prerequisites (FR-004/006), and which steps
// run a long background job (FR-025). Pure data — no state here.

export type StepKey = 'connect' | 'backup' | 'draft' | 'merge' | 'review' | 'export';

export interface WizardStep {
  key: StepKey;
  index: number;
  label: string;
  description: string;
  route: string;
  prerequisiteKey: StepKey | null;
  isLongJob: boolean;
}

export const WIZARD_STEPS: WizardStep[] = [
  {
    key: 'connect',
    index: 1,
    label: 'Connect',
    description: 'Link your Google account',
    route: '/wizard/connect',
    prerequisiteKey: null,
    isLongJob: false,
  },
  {
    key: 'backup',
    index: 2,
    label: 'Backup',
    description: 'Pull a frozen copy of your contacts',
    route: '/wizard/backup',
    prerequisiteKey: 'connect',
    isLongJob: true,
  },
  {
    key: 'draft',
    index: 3,
    label: 'Draft',
    description: 'Your editable copy of the contacts',
    route: '/wizard/draft',
    prerequisiteKey: 'backup',
    isLongJob: false,
  },
  {
    key: 'merge',
    index: 4,
    label: 'Merge',
    description: 'Find & merge duplicates',
    route: '/wizard/merge',
    prerequisiteKey: 'draft',
    isLongJob: true,
  },
  {
    key: 'review',
    index: 5,
    label: 'Review',
    description: 'Swipe to keep or delete',
    route: '/wizard/review',
    prerequisiteKey: 'merge',
    isLongJob: false,
  },
  {
    key: 'export',
    index: 6,
    label: 'Export',
    description: 'Push your changes back to Google',
    route: '/wizard/export',
    prerequisiteKey: 'review',
    isLongJob: true,
  },
];

export const STEP_KEYS: StepKey[] = WIZARD_STEPS.map((s) => s.key);

export function stepByKey(key: StepKey): WizardStep {
  const step = WIZARD_STEPS.find((s) => s.key === key);
  if (!step) throw new Error(`Unknown wizard step: ${key}`);
  return step;
}
