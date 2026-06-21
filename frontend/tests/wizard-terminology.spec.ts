import { STEP_KEYS, WIZARD_STEPS } from '@/wizard/steps';
import { describe, expect, it } from 'vitest';

describe('wizard terminology (FR-010/011/012)', () => {
  it('uses the seven simplified plain-verb labels in order', () => {
    expect(WIZARD_STEPS.map((s) => s.label)).toEqual([
      'Connect',
      'Backup',
      'Draft',
      'Merge',
      'Review',
      'Tidy',
      'Export',
    ]);
    expect(STEP_KEYS).toEqual(['connect', 'backup', 'draft', 'merge', 'review', 'tidy', 'export']);
  });

  it('never exposes the old jargon in step labels (FR-010/011)', () => {
    const forbidden = [
      /working copy/i,
      /deduplicat/i,
      /\btriage\b/i,
      /\bsubmit\b/i,
      /\bsnapshot\b/i,
    ];
    for (const step of WIZARD_STEPS) {
      for (const term of forbidden) {
        expect(step.label, `label "${step.label}"`).not.toMatch(term);
      }
    }
  });

  it('gives every step a non-empty plain-language description (FR-012)', () => {
    for (const step of WIZARD_STEPS) {
      expect(step.description.length).toBeGreaterThan(0);
      expect(step.description).not.toMatch(/working copy/i);
    }
  });
});
