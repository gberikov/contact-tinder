import { ApiError, type ExportPreview, type ExportRun, api } from '@/services/api';
import { defineStore } from 'pinia';

interface State {
  preview: ExportPreview | null;
  run: ExportRun | null;
  loading: boolean;
  error: string | null;
  polling: boolean;
  // Set when confirm-delete is refused for a missing write scope — surfaces the re-consent button.
  needsWriteScope: boolean;
}

// Terminal run states — once reached, progress polling stops.
const TERMINAL = ['completed', 'failed'] as const;

export const useExportStore = defineStore('export', {
  state: (): State => ({
    preview: null,
    run: null,
    loading: false,
    error: null,
    polling: false,
    needsWriteScope: false,
  }),
  getters: {
    nothingToExport: (s): boolean => s.preview?.nothingToExport ?? false,
    hasUndecided: (s): boolean => (s.preview?.undecidedCount ?? 0) > 0,
    report: (s) => s.run?.report ?? null,
    isRunning: (s): boolean => s.run?.status === 'running',
    isComplete: (s): boolean => s.run != null && TERMINAL.includes(s.run.status as 'completed'),
    canUndoDelete: (s): boolean => s.run?.report.deleteStatus === 'committed',
    canUndoLabel: (s): boolean => s.run?.report.labelStatus === 'committed',
  },
  actions: {
    async loadPreview(workingCopyId: string) {
      this.loading = true;
      this.error = null;
      try {
        this.preview = await api.previewExport(workingCopyId);
      } catch (e) {
        this.error = (e as Error).message;
      } finally {
        this.loading = false;
      }
    },
    async start(workingCopyId: string) {
      this.error = null;
      this.run = await api.startExport(workingCopyId, this.preview?.sessionId ?? undefined);
      return this.run;
    },
    /** Confirm the destructive delete half; labeling rides alongside (FR-015). 403 ⇒ re-consent. */
    async confirmDelete() {
      if (!this.run) return;
      this.error = null;
      this.needsWriteScope = false;
      try {
        this.run = await api.confirmExportDelete(this.run.id);
      } catch (e) {
        if (e instanceof ApiError && e.code === 'write_scope_required') {
          this.needsWriteScope = true;
        }
        this.error = (e as Error).message;
        throw e;
      }
    },
    /** One-click re-consent: returns the Google URL to redirect to; comes back to `returnTo`. */
    async requestWriteConsent(returnTo: string): Promise<string> {
      const { authorizationUrl } = await api.grantWriteAccess(returnTo);
      return authorizationUrl;
    },
    async refresh() {
      if (!this.run) return;
      this.run = await api.getExportRun(this.run.id);
    },
    /** Poll the run until it reaches a terminal state, then stop (live progress, FR-019a). */
    async pollUntilDone(intervalMs = 500, maxTicks = 60) {
      if (!this.run || this.polling) return;
      this.polling = true;
      try {
        for (let i = 0; i < maxTicks; i++) {
          await this.refresh();
          if (this.isComplete) break;
          await new Promise((r) => setTimeout(r, intervalMs));
        }
      } finally {
        this.polling = false;
      }
    },
    async undoDelete() {
      if (!this.run) return;
      this.run = await api.undoExportDelete(this.run.id);
    },
    async undoLabel() {
      if (!this.run) return;
      this.run = await api.undoExportLabel(this.run.id);
    },
  },
});
