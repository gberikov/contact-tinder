import type { ValidationRun } from '@/services/api';
import { useWizardStore } from '@/stores/wizard';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it } from 'vitest';

const run = (over: Partial<ValidationRun> = {}): ValidationRun => ({
  id: 'r1',
  workingCopyId: 'wc-1',
  status: 'completed',
  totalCount: 0,
  checkedCount: 0,
  autoAppliedCount: 0,
  queuedCount: 0,
  pendingCount: 0,
  createdAt: 'now',
  ...over,
});

describe('wizard store — Tidy derivation (US3)', () => {
  beforeEach(() => setActivePinia(createPinia()));

  it('no run → not completed, not running, but passable', () => {
    const w = useWizardStore();
    expect(w.completed('tidy')).toBe(false);
    expect(w.running('tidy')).toBe(false);
    expect(w.passable('tidy')).toBe(true);
  });

  it('queued or running run → running state', () => {
    const w = useWizardStore();
    w.validationRuns = [run({ status: 'running' })];
    expect(w.running('tidy')).toBe(true);
    w.validationRuns = [run({ status: 'queued' })];
    expect(w.running('tidy')).toBe(true);
  });

  it('completed run with fixes → completed, not empty', () => {
    const w = useWizardStore();
    w.validationRuns = [run({ status: 'completed', autoAppliedCount: 3 })];
    expect(w.completed('tidy')).toBe(true);
    expect(w.emptyButPassable('tidy')).toBe(false);
  });

  it('completed run with nothing to fix → emptyButPassable', () => {
    const w = useWizardStore();
    w.validationRuns = [run({ status: 'completed', autoAppliedCount: 0, queuedCount: 0 })];
    expect(w.emptyButPassable('tidy')).toBe(true);
  });

  it('Export is gated behind Tidy (passable)', () => {
    const w = useWizardStore();
    // Export depends on tidy; tidy is always passable, so export is reachable.
    expect(w.available('export')).toBe(true);
  });
});
