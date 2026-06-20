import {
  type DeckCard,
  type DeleteBatch,
  type DeletionRecord,
  type Outcome,
  type ProcessingItem,
  type TriageSession,
  api,
} from '@/services/api';
import { defineStore } from 'pinia';

interface State {
  session: TriageSession | null;
  deck: DeckCard[];
  nextCursor: string | null;
  processing: ProcessingItem[];
  batch: DeleteBatch | null;
  preview: DeletionRecord[];
  loading: boolean;
  error: string | null;
}

export const useTriageStore = defineStore('triage', {
  state: (): State => ({
    session: null,
    deck: [],
    nextCursor: null,
    processing: [],
    batch: null,
    preview: [],
    loading: false,
    error: null,
  }),
  getters: {
    // The card currently shown (front of the prefetched deck).
    currentCard: (s): DeckCard | null => s.deck[0] ?? null,
    summary: (s) => s.session?.summary ?? null,
  },
  actions: {
    async open(workingCopyId: string) {
      this.loading = true;
      this.error = null;
      try {
        this.session = await api.openTriageSession(workingCopyId);
        await this.loadDeck();
      } catch (e) {
        this.error = (e as Error).message;
      } finally {
        this.loading = false;
      }
    },
    async loadDeck() {
      if (!this.session) return;
      const page = await api.getDeck(this.session.id);
      this.deck = page.cards;
      this.nextCursor = page.nextCursor ?? null;
    },
    /** Optimistically advance the card, then persist (SC-001: swipe never blocks). */
    async decide(outcome: Outcome, opts?: { wantsEdit?: boolean; wantsTransliterate?: boolean }) {
      if (!this.session) return;
      const card = this.deck[0];
      if (!card) return;
      this.deck = this.deck.slice(1); // optimistic advance
      try {
        await api.setDecision(this.session.id, card.workingCopyContactId, {
          outcome,
          wantsEdit: opts?.wantsEdit,
          wantsTransliterate: opts?.wantsTransliterate,
        });
        this.session = await api.getTriageSession(this.session.id);
        if (this.deck.length === 0) await this.loadDeck();
      } catch (e) {
        this.error = (e as Error).message;
        this.deck = [card, ...this.deck]; // roll back on failure
      }
    },
    async loadProcessing() {
      if (!this.session) return;
      this.processing = await api.listProcessing(this.session.id);
    },
    async acceptTransliteration(contactId: string, fields: Record<string, string>) {
      await api.acceptTransliteration(contactId, fields);
    },
    async applyEdit(contactId: string, payload: Record<string, unknown>) {
      await api.applyEdit(contactId, payload);
    },
    async completeProcessing(itemId: string) {
      await api.completeProcessingItem(itemId);
      this.processing = this.processing.filter((p) => p.id !== itemId);
    },
    async buildDeleteBatch(workingCopyId: string) {
      this.batch = await api.createDeleteBatch(workingCopyId, this.session?.id);
      this.preview = await api.previewDeleteBatch(this.batch.id);
      return this.batch;
    },
    async confirmDelete() {
      if (!this.batch) return;
      this.error = null;
      try {
        this.batch = await api.confirmDeleteBatch(this.batch.id);
      } catch (e) {
        // 403 → operator must grant the contacts write scope (re-consent).
        this.error = (e as Error).message;
        throw e;
      }
    },
    async undoDelete() {
      if (!this.batch) return;
      this.batch = await api.undoDeleteBatch(this.batch.id);
    },
  },
});
