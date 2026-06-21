import {
  type AutoFix,
  type ResolveValidationItemBody,
  type ValidationItem,
  type ValidationRun,
  api,
} from '@/services/api';
import { defineStore } from 'pinia';

// The operator's chosen phone-parsing region persists client-side (like the wizard active chain).
const REGION_KEY = 'tidy.defaultRegion';

function loadRegion(): string | null {
  try {
    return localStorage.getItem(REGION_KEY);
  } catch {
    return null;
  }
}

interface State {
  workingCopyId: string | null;
  run: ValidationRun | null;
  items: ValidationItem[];
  autoFixes: AutoFix[];
  region: string | null;
  loading: boolean;
  error: string | null;
  polling: boolean;
}

export const useTidyStore = defineStore('tidy', {
  state: (): State => ({
    workingCopyId: null,
    run: null,
    items: [],
    autoFixes: [],
    region: loadRegion(),
    loading: false,
    error: null,
    polling: false,
  }),

  getters: {
    pendingItems: (s): ValidationItem[] => s.items.filter((i) => i.status === 'pending'),
    isRunning: (s): boolean => s.run?.status === 'running' || s.run?.status === 'queued',
    summary: (s) =>
      s.run
        ? {
            total: s.run.totalCount,
            checked: s.run.checkedCount,
            auto: s.run.autoAppliedCount,
            queued: s.run.queuedCount,
            pending: s.run.pendingCount,
          }
        : null,
    // 0–100 progress while the run works through the kept set's field values.
    progressPct: (s): number => {
      const r = s.run;
      if (!r || r.totalCount <= 0) return r?.status === 'completed' ? 100 : 0;
      return Math.min(100, Math.round((r.checkedCount / r.totalCount) * 100));
    },
  },

  actions: {
    setRegion(region: string) {
      this.region = region;
      try {
        localStorage.setItem(REGION_KEY, region);
      } catch {
        /* storage unavailable — non-fatal */
      }
    },

    /** Initialize the highlighted default region from IP geo (server) or the browser locale. */
    async ensureRegion() {
      if (this.region) return;
      try {
        const res = await api.detectRegion();
        let region = res.region;
        if (!region) {
          const match = /[-_]([A-Za-z]{2})$/.exec(navigator.language || '');
          region = match ? match[1].toUpperCase() : null;
        }
        if (region) this.setRegion(region);
      } catch {
        /* detection is best-effort */
      }
    },

    /** Restore the latest run + its items on entering/reloading the step. */
    async restore(workingCopyId: string) {
      this.workingCopyId = workingCopyId;
      const runs = await api.listValidationRuns(workingCopyId);
      this.run = runs.length ? runs[0] : null;
      await Promise.all([this.loadItems(), this.loadAutoFixes()]);
      if (this.isRunning) await this.poll();
    },

    async loadItems() {
      this.items = this.run ? await api.listValidationItems(this.run.id, 'all') : [];
    },

    async loadAutoFixes() {
      this.autoFixes = this.workingCopyId ? await api.listAutoFixes(this.workingCopyId) : [];
    },

    async startRun(workingCopyId: string, sessionId?: string) {
      this.workingCopyId = workingCopyId;
      this.loading = true;
      this.error = null;
      try {
        this.run = await api.startValidationRun(workingCopyId, this.region ?? undefined, sessionId);
        this.items = [];
        await this.poll();
        await this.loadAutoFixes();
      } catch (e) {
        this.error = (e as Error).message;
      } finally {
        this.loading = false;
      }
    },

    async poll(intervalMs = 800, maxTicks = 600) {
      if (this.polling || !this.run) return;
      this.polling = true;
      try {
        for (let i = 0; i < maxTicks; i++) {
          this.run = await api.getValidationRun(this.run.id);
          if (this.run.status === 'completed' || this.run.status === 'failed') {
            await this.loadItems();
            break;
          }
          await new Promise((r) => setTimeout(r, intervalMs));
        }
      } finally {
        this.polling = false;
      }
    },

    async resolveItem(itemId: string, body: ResolveValidationItemBody) {
      this._replace(await api.resolveValidationItem(itemId, body));
      await this._refreshRun();
    },

    async skipItem(itemId: string) {
      this._replace(await api.skipValidationItem(itemId));
      await this._refreshRun();
    },

    async undoEdit(editId: string) {
      await api.undoStagedEdit(editId);
      await this._refreshRun();
      await Promise.all([this.loadItems(), this.loadAutoFixes()]);
    },

    async _refreshRun() {
      if (this.run) this.run = await api.getValidationRun(this.run.id);
    },

    _replace(item: ValidationItem) {
      const i = this.items.findIndex((x) => x.id === item.id);
      if (i >= 0) this.items[i] = item;
      else this.items.push(item);
    },
  },
});
