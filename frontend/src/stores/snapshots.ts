import { type Snapshot, api } from '@/services/api';
import { defineStore } from 'pinia';

interface State {
  snapshots: Snapshot[];
  loading: boolean;
  error: string | null;
}

export const useSnapshotsStore = defineStore('snapshots', {
  state: (): State => ({ snapshots: [], loading: false, error: null }),
  actions: {
    async load() {
      this.loading = true;
      this.error = null;
      try {
        this.snapshots = await api.listSnapshots();
      } catch (e) {
        this.error = (e as Error).message;
      } finally {
        this.loading = false;
      }
    },
    async create(accountId: string, label?: string) {
      const snapshot = await api.createSnapshot(accountId, label);
      this.snapshots.unshift(snapshot);
      return snapshot;
    },
    async remove(id: string) {
      // Caller is responsible for confirmation; a 409 (working copies exist) surfaces as error.
      await api.deleteSnapshot(id);
      this.snapshots = this.snapshots.filter((s) => s.id !== id);
    },
  },
});
