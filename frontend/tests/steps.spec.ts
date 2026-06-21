import { STEP_KEYS, WIZARD_STEPS, stepByKey } from '@/wizard/steps';
import { describe, expect, it } from 'vitest';

describe('wizard steps (feature 006)', () => {
  it('has seven steps with Tidy between Review and Export (FR-001)', () => {
    expect(WIZARD_STEPS).toHaveLength(7);
    expect(STEP_KEYS).toEqual(['connect', 'backup', 'draft', 'merge', 'review', 'tidy', 'export']);
  });

  it('Tidy is a long job gated on Review; Export is gated on Tidy', () => {
    const tidy = stepByKey('tidy');
    expect(tidy.index).toBe(6);
    expect(tidy.prerequisiteKey).toBe('review');
    expect(tidy.isLongJob).toBe(true);
    expect(stepByKey('export').index).toBe(7);
    expect(stepByKey('export').prerequisiteKey).toBe('tidy');
  });
});
