import { type Cluster, type DedupRun, api } from '@/services/api';
import { defineStore } from 'pinia';

interface State {
  run: DedupRun | null;
  clusters: Cluster[];
  minConfidence: number | null;
  loading: boolean;
  error: string | null;
}

export const useDedupStore = defineStore('dedup', {
  state: (): State => ({
    run: null,
    clusters: [],
    minConfidence: null,
    loading: false,
    error: null,
  }),
  getters: {
    // Pending clusters, strongest first (FR-011).
    pendingClusters: (s): Cluster[] =>
      [...s.clusters]
        .filter((c) => c.status === 'pending')
        .sort((a, b) => b.confidence - a.confidence),
  },
  actions: {
    /** Restore an existing run (e.g. when re-entering the Merge step) and load its clusters. */
    async adopt(run: DedupRun) {
      if (this.run?.id === run.id) return;
      this.run = run;
      if (run.status === 'completed') await this.loadClusters();
    },
    async startRun(workingCopyId: string) {
      this.loading = true;
      this.error = null;
      try {
        // Synchronous run so the UI can show clusters immediately in single-process/dev mode.
        this.run = await api.startDedupRun(workingCopyId, false);
        if (this.run.status === 'completed') await this.loadClusters();
      } catch (e) {
        this.error = (e as Error).message;
      } finally {
        this.loading = false;
      }
    },
    async loadClusters() {
      if (!this.run) return;
      this.clusters = await api.listClusters(this.run.id, this.minConfidence ?? undefined);
    },
    async merge(clusterId: string, survivorContactId?: string) {
      await api.mergeCluster(clusterId, survivorContactId);
      this.removeCluster(clusterId);
    },
    async dismiss(clusterId: string) {
      await api.dismissCluster(clusterId);
      this.removeCluster(clusterId);
    },
    removeCluster(clusterId: string) {
      this.clusters = this.clusters.filter((c) => c.id !== clusterId);
    },
  },
});
