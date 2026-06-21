import { useTidyStore } from '@/stores/tidy';
import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/services/api', () => ({
  api: { detectRegion: vi.fn() },
}));
import { api } from '@/services/api';

function setLanguage(lang: string) {
  Object.defineProperty(navigator, 'language', { value: lang, configurable: true });
}

describe('tidy store — region detection (FR-028)', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });
  afterEach(() => vi.restoreAllMocks());

  it('uses the server geoip region when available', async () => {
    vi.mocked(api.detectRegion).mockResolvedValue({ region: 'KZ', source: 'geoip' });
    const store = useTidyStore();
    await store.ensureRegion();
    expect(store.region).toBe('KZ');
  });

  it('falls back to the browser locale region when geoip returns null', async () => {
    vi.mocked(api.detectRegion).mockResolvedValue({ region: null, source: 'none' });
    setLanguage('ru-KZ');
    const store = useTidyStore();
    await store.ensureRegion();
    expect(store.region).toBe('KZ');
  });

  it('persists and does not re-detect once a region is set', async () => {
    const store = useTidyStore();
    store.setRegion('US');
    await store.ensureRegion();
    expect(api.detectRegion).not.toHaveBeenCalled();
    expect(localStorage.getItem('tidy.defaultRegion')).toBe('US');
  });
});
