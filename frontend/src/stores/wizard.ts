import {
  type Account,
  type DedupRun,
  type ExportPreview,
  type ExportRun,
  type ImportJob,
  type Snapshot,
  type TriageSession,
  type WorkingCopy,
  api,
} from '@/services/api';
import { type StepKey, WIZARD_STEPS, stepByKey } from '@/wizard/steps';
import { defineStore } from 'pinia';

export type DisplayState = 'completed' | 'current' | 'upcoming' | 'running';

export interface StepState {
  key: StepKey;
  displayState: DisplayState;
  available: boolean;
  completed: boolean;
  running: boolean;
  emptyButPassable: boolean;
}

const STORAGE_KEY = 'wizard.activeChain';

interface PersistedChain {
  activeAccountId: string | null;
  snapshotByAccount: Record<string, string>;
  workingCopyBySnapshot: Record<string, string>;
  currentStepKey: StepKey;
}

interface State extends PersistedChain {
  // Fetched collections (the wizard derives its state from these; no new endpoints).
  accounts: Account[];
  snapshots: Snapshot[];
  workingCopies: WorkingCopy[];
  importJob: ImportJob | null;
  dedupRuns: DedupRun[];
  triageSessions: TriageSession[];
  exportPreview: ExportPreview | null;
  exportRun: ExportRun | null;
  loading: boolean;
  error: string | null;
}

function loadPersisted(): PersistedChain {
  const fallback: PersistedChain = {
    activeAccountId: null,
    snapshotByAccount: {},
    workingCopyBySnapshot: {},
    currentStepKey: 'connect',
  };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return fallback;
    return { ...fallback, ...(JSON.parse(raw) as Partial<PersistedChain>) };
  } catch {
    return fallback;
  }
}

export const useWizardStore = defineStore('wizard', {
  state: (): State => ({
    ...loadPersisted(),
    accounts: [],
    snapshots: [],
    workingCopies: [],
    importJob: null,
    dedupRuns: [],
    triageSessions: [],
    exportPreview: null,
    exportRun: null,
    loading: false,
    error: null,
  }),

  getters: {
    // ---- active-selection chain (per-parent memory keeps branches intact, FR-024) -------------
    activeSnapshotId(state): string | null {
      return state.activeAccountId
        ? (state.snapshotByAccount[state.activeAccountId] ?? null)
        : null;
    },
    activeWorkingCopyId(): string | null {
      const sid = this.activeSnapshotId;
      return sid ? (this.workingCopyBySnapshot[sid] ?? null) : null;
    },
    activeAccount(state): Account | null {
      return state.accounts.find((a) => a.id === state.activeAccountId) ?? null;
    },
    activeSnapshot(state): Snapshot | null {
      return state.snapshots.find((s) => s.id === this.activeSnapshotId) ?? null;
    },
    activeWorkingCopy(state): WorkingCopy | null {
      return state.workingCopies.find((w) => w.id === this.activeWorkingCopyId) ?? null;
    },

    // ---- client-side filtering over the unfiltered list endpoints (FR-020) -------------------
    snapshotsForActiveAccount(state): Snapshot[] {
      return state.snapshots.filter((s) => s.accountId === state.activeAccountId);
    },
    workingCopiesForActiveSnapshot(state): WorkingCopy[] {
      const sid = this.activeSnapshotId;
      return state.workingCopies.filter((w) => w.snapshotId === sid);
    },
    latestDedupRun(state): DedupRun | null {
      return state.dedupRuns.length ? state.dedupRuns[state.dedupRuns.length - 1] : null;
    },
    latestTriageSession(state): TriageSession | null {
      return state.triageSessions.length
        ? state.triageSessions[state.triageSessions.length - 1]
        : null;
    },

    // ---- per-step predicates (data-model.md mapping) -----------------------------------------
    completed() {
      return (key: StepKey): boolean => {
        switch (key) {
          case 'connect':
            return this.activeAccount?.status === 'connected';
          case 'backup':
            return this.activeSnapshot?.status === 'complete';
          case 'draft':
            return this.activeWorkingCopy != null;
          case 'merge':
            return this.latestDedupRun?.status === 'completed';
          case 'review':
            return this.latestTriageSession?.status === 'complete';
          case 'export':
            return this.exportRun?.status === 'completed';
        }
      };
    },
    running(state) {
      return (key: StepKey): boolean => {
        switch (key) {
          case 'backup':
            return (
              state.importJob?.status === 'running' || this.activeSnapshot?.status === 'importing'
            );
          case 'merge':
            return this.latestDedupRun?.status === 'running';
          case 'export':
            return state.exportRun?.status === 'running';
          default:
            return false;
        }
      };
    },
    available() {
      return (key: StepKey): boolean => {
        const prereq = stepByKey(key).prerequisiteKey;
        return prereq == null ? true : this.completed(prereq);
      };
    },
    emptyButPassable() {
      return (key: StepKey): boolean => {
        if (key === 'merge') {
          return (
            this.latestDedupRun?.status === 'completed' &&
            (this.latestDedupRun?.clusterCount ?? 0) === 0
          );
        }
        if (key === 'review') {
          return this.latestTriageSession?.status === 'complete'
            ? (this.latestTriageSession?.summary.total ?? 0) === 0
            : false;
        }
        return false;
      };
    },
    displayState(state) {
      return (key: StepKey): DisplayState => {
        if (this.running(key)) return 'running';
        if (key === state.currentStepKey) return 'current';
        if (this.completed(key)) return 'completed';
        return 'upcoming';
      };
    },
    stepStates(): StepState[] {
      return WIZARD_STEPS.map((s) => ({
        key: s.key,
        displayState: this.displayState(s.key),
        available: this.available(s.key),
        completed: this.completed(s.key),
        running: this.running(s.key),
        emptyButPassable: this.emptyButPassable(s.key),
      }));
    },
    currentStepIndex(state): number {
      return stepByKey(state.currentStepKey).index;
    },
  },

  actions: {
    persist() {
      const payload: PersistedChain = {
        activeAccountId: this.activeAccountId,
        snapshotByAccount: this.snapshotByAccount,
        workingCopyBySnapshot: this.workingCopyBySnapshot,
        currentStepKey: this.currentStepKey,
      };
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
      } catch {
        /* storage unavailable — non-fatal */
      }
    },

    // ---- active-selection setters (FR-021/024) ----------------------------------------------
    setActiveAccount(id: string) {
      this.activeAccountId = id;
      this.persist();
    },
    setActiveSnapshot(id: string) {
      if (!this.activeAccountId) return;
      this.snapshotByAccount[this.activeAccountId] = id;
      this.persist();
    },
    setActiveDraft(id: string) {
      const sid = this.activeSnapshotId;
      if (!sid) return;
      this.workingCopyBySnapshot[sid] = id;
      this.persist();
    },
    goToStep(key: StepKey) {
      if (!this.available(key)) return;
      this.currentStepKey = key;
      this.persist();
    },
    /** First step that is not yet completed — the natural landing step on load (FR-007). */
    firstIncompleteStep(): StepKey {
      const incomplete = WIZARD_STEPS.find((s) => !this.completed(s.key));
      return incomplete ? incomplete.key : 'export';
    },

    // ---- data loading (existing endpoints only) ---------------------------------------------
    async loadAccounts() {
      this.accounts = await api.listAccounts();
    },
    async loadSnapshots() {
      this.snapshots = await api.listSnapshots();
    },
    async loadWorkingCopies() {
      this.workingCopies = await api.listWorkingCopies();
    },
    async loadBackupJob() {
      const sid = this.activeSnapshotId;
      this.importJob = sid ? await api.getImportJob(sid) : null;
    },
    async loadMerge() {
      const wid = this.activeWorkingCopyId;
      this.dedupRuns = wid ? await api.listDedupRuns(wid) : [];
    },
    async loadReview() {
      const wid = this.activeWorkingCopyId;
      this.triageSessions = wid ? await api.listTriageSessions(wid) : [];
    },
    async loadExport() {
      const wid = this.activeWorkingCopyId;
      this.exportPreview = wid ? await api.previewExport(wid) : null;
    },

    /** Load everything reachable along the current active-selection chain (FR-007/008). */
    async hydrate() {
      this.loading = true;
      this.error = null;
      try {
        await this.loadAccounts();
        await this.loadSnapshots();
        if (this.activeSnapshotId) await this.loadBackupJob();
        await this.loadWorkingCopies();
        if (this.activeWorkingCopyId) {
          await Promise.all([this.loadMerge(), this.loadReview(), this.loadExport()]);
        }
      } catch (e) {
        this.error = (e as Error).message;
      } finally {
        this.loading = false;
      }
    },
  },
});
