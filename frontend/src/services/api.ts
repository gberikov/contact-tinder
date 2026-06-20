// Typed API client mirroring contracts/openapi.yaml. No tokens are ever returned by the API.

export interface Account {
  id: string;
  email: string;
  status: 'connected' | 'needs_reauth' | 'revoked';
  grantedScopes: string[];
  createdAt: string;
}

export interface Snapshot {
  id: string;
  accountId: string;
  accountEmail?: string | null;
  status: 'importing' | 'complete' | 'failed' | 'deleting';
  source: string;
  contactCount?: number | null;
  workingCopyCount: number;
  label?: string | null;
  createdAt: string;
  finalizedAt?: string | null;
}

export interface ImportJob {
  snapshotId: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  fetchedCount: number;
  totalEstimate?: number | null;
  lastError?: string | null;
}

export interface WorkingCopy {
  id: string;
  snapshotId: string;
  label: string;
  status: string;
  contactCount?: number | null;
  createdAt: string;
}

export interface Contact {
  id: string;
  resourceName: string;
  displayName?: string | null;
  primaryEmail?: string | null;
  primaryPhone?: string | null;
  payload: Record<string, unknown>;
}

export interface ContactPage {
  items: Contact[];
  page: number;
  pageSize: number;
  total: number;
}

// ---- Deduplication (feature 002) ----------------------------------------------------------

export interface DedupRun {
  id: string;
  workingCopyId: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  modelVersion: string;
  confidenceFloor: number;
  clusterCount?: number | null;
  lastError?: string | null;
  createdAt: string;
  startedAt?: string | null;
  finishedAt?: string | null;
}

export interface ContactSummary {
  displayName?: string | null;
  primaryEmail?: string | null;
  primaryPhone?: string | null;
  organization?: string | null;
  status: 'active' | 'retired';
}

export interface ClusterMember {
  id: string;
  workingCopyContactId: string;
  matchScore?: number | null;
  isSurvivor: boolean;
  contact: ContactSummary;
}

export interface Cluster {
  id: string;
  dedupRunId: string;
  workingCopyId: string;
  confidence: number;
  minScore?: number | null;
  size: number;
  status: 'pending' | 'merged' | 'dismissed' | 'superseded';
  mergeRecordId?: string | null;
  members: ClusterMember[];
}

export interface MergeConflict {
  field: string;
  chosen: string;
  candidates: string[];
}

export interface MergePreview {
  survivorContactId: string;
  proposedPayload: Record<string, unknown>;
  conflicts: MergeConflict[];
}

export interface MergeResult {
  mergeRecordId: string;
  survivorContactId: string;
  clusterId: string;
  retiredContactIds: string[];
}

// ---- Swipe triage (feature 003) -----------------------------------------------------------

export type Outcome = 'keep' | 'delete' | 'process';

export interface SessionSummary {
  total: number;
  decided: number;
  keep: number;
  delete: number;
  processing: number;
  remaining: number;
}

export interface TriageSession {
  id: string;
  workingCopyId: string;
  dedupRunId?: string | null;
  status: 'in_progress' | 'complete';
  createdAt: string;
  finishedAt?: string | null;
  summary: SessionSummary;
}

export interface ContactDetail {
  displayName?: string | null;
  primaryEmail?: string | null;
  primaryPhone?: string | null;
  organization?: string | null;
  status: 'active' | 'retired';
  payload: Record<string, unknown>;
}

export interface DeckCard {
  workingCopyContactId: string;
  contact: ContactDetail;
  currentOutcome?: Outcome | null;
}

export interface DeckPage {
  cards: DeckCard[];
  nextCursor?: string | null;
}

export interface TriageDecision {
  id: string;
  sessionId: string;
  workingCopyContactId: string;
  outcome: Outcome;
  decidedAt: string;
  processingItemId?: string | null;
}

export interface TransliterationSuggestion {
  hasSuggestion: boolean;
  fields: Record<string, string>;
}

export interface ProcessingItem {
  id: string;
  sessionId: string;
  workingCopyContactId: string;
  wantsEdit: boolean;
  wantsTransliterate: boolean;
  status: 'pending' | 'done';
  contact: ContactDetail;
  transliterationSuggestion?: TransliterationSuggestion | null;
}

export interface StagedEdit {
  id: string;
  workingCopyContactId: string;
  kind: 'edit' | 'transliterate';
  status: 'active' | 'undone';
  createdAt: string;
  undoneAt?: string | null;
}

export interface DeleteBatch {
  id: string;
  workingCopyId: string;
  sessionId?: string | null;
  accountId: string;
  status: 'staged' | 'previewed' | 'committing' | 'committed' | 'failed' | 'undoing' | 'undone';
  totalCount: number;
  deletedCount: number;
  failedCount: number;
  lastError?: string | null;
  createdAt: string;
  previewedAt?: string | null;
  committedAt?: string | null;
  undoneAt?: string | null;
}

export interface DeletionRecord {
  id: string;
  workingCopyContactId?: string | null;
  status: 'pending' | 'deleted' | 'skipped_absent' | 'failed' | 'restored';
  contact: ContactDetail;
  error?: string | null;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) {
    let code = 'error';
    let message = res.statusText;
    try {
      const body = await res.json();
      code = body.code ?? code;
      message = body.message ?? message;
    } catch {
      /* non-json error */
    }
    throw new ApiError(res.status, code, message);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  listAccounts: () => request<Account[]>('/accounts'),
  connect: () => request<{ authorizationUrl: string }>('/accounts/connect', { method: 'POST' }),
  disconnect: (id: string) => request<void>(`/accounts/${id}`, { method: 'DELETE' }),

  createSnapshot: (accountId: string, label?: string) =>
    request<Snapshot>(`/accounts/${accountId}/snapshots`, {
      method: 'POST',
      body: JSON.stringify({ label }),
    }),
  listSnapshots: () => request<Snapshot[]>('/snapshots'),
  getSnapshot: (id: string) => request<Snapshot>(`/snapshots/${id}`),
  getImportJob: (id: string) => request<ImportJob>(`/snapshots/${id}/import`),
  listSnapshotContacts: (id: string, page = 1, pageSize = 50, q?: string) =>
    request<ContactPage>(
      `/snapshots/${id}/contacts?page=${page}&pageSize=${pageSize}${q ? `&q=${encodeURIComponent(q)}` : ''}`,
    ),
  deleteSnapshot: (id: string) =>
    request<void>(`/snapshots/${id}?confirm=true`, { method: 'DELETE' }),

  createWorkingCopy: (snapshotId: string, label?: string) =>
    request<WorkingCopy>(`/snapshots/${snapshotId}/working-copies`, {
      method: 'POST',
      body: JSON.stringify({ label }),
    }),
  listWorkingCopies: () => request<WorkingCopy[]>('/working-copies'),

  // Deduplication
  startDedupRun: (workingCopyId: string, background = true) =>
    request<DedupRun>(`/working-copies/${workingCopyId}/dedup-runs?background=${background}`, {
      method: 'POST',
    }),
  listDedupRuns: (workingCopyId: string) =>
    request<DedupRun[]>(`/working-copies/${workingCopyId}/dedup-runs`),
  getDedupRun: (runId: string) => request<DedupRun>(`/dedup-runs/${runId}`),
  listClusters: (runId: string, minConfidence?: number) =>
    request<Cluster[]>(
      `/dedup-runs/${runId}/clusters${minConfidence != null ? `?minConfidence=${minConfidence}` : ''}`,
    ),
  getCluster: (clusterId: string) => request<Cluster>(`/clusters/${clusterId}`),
  mergePreview: (clusterId: string, survivorContactId?: string) =>
    request<MergePreview>(
      `/clusters/${clusterId}/merge-preview${survivorContactId ? `?survivorContactId=${survivorContactId}` : ''}`,
    ),
  mergeCluster: (clusterId: string, survivorContactId?: string) =>
    request<MergeResult>(`/clusters/${clusterId}/merge`, {
      method: 'POST',
      body: JSON.stringify({ survivorContactId }),
    }),
  dismissCluster: (clusterId: string) =>
    request<Cluster>(`/clusters/${clusterId}/dismiss`, { method: 'POST' }),
  undoMerge: (mergeRecordId: string) =>
    request<Cluster>(`/merge-records/${mergeRecordId}/undo`, { method: 'POST' }),

  // Swipe triage (feature 003)
  openTriageSession: (workingCopyId: string) =>
    request<TriageSession>(`/working-copies/${workingCopyId}/triage-sessions`, { method: 'POST' }),
  listTriageSessions: (workingCopyId: string) =>
    request<TriageSession[]>(`/working-copies/${workingCopyId}/triage-sessions`),
  getTriageSession: (sessionId: string) => request<TriageSession>(`/triage-sessions/${sessionId}`),
  getDeck: (sessionId: string, cursor?: string, limit = 10) =>
    request<DeckPage>(
      `/triage-sessions/${sessionId}/deck?limit=${limit}${cursor ? `&cursor=${cursor}` : ''}`,
    ),
  setDecision: (
    sessionId: string,
    contactId: string,
    body: { outcome: Outcome; wantsEdit?: boolean; wantsTransliterate?: boolean },
  ) =>
    request<TriageDecision>(`/triage-sessions/${sessionId}/decisions/${contactId}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  undoDecision: (sessionId: string, contactId: string) =>
    request<void>(`/triage-sessions/${sessionId}/decisions/${contactId}`, { method: 'DELETE' }),

  listProcessing: (sessionId: string, status: 'pending' | 'done' = 'pending') =>
    request<ProcessingItem[]>(`/triage-sessions/${sessionId}/processing?status=${status}`),
  getProcessingItem: (itemId: string) => request<ProcessingItem>(`/processing-items/${itemId}`),
  completeProcessingItem: (itemId: string) =>
    request<ProcessingItem>(`/processing-items/${itemId}/done`, { method: 'POST' }),
  getTransliterationSuggestion: (contactId: string) =>
    request<TransliterationSuggestion>(
      `/working-copy-contacts/${contactId}/transliteration-suggestion`,
    ),
  applyEdit: (contactId: string, payload: Record<string, unknown>) =>
    request<StagedEdit>(`/working-copy-contacts/${contactId}/edits`, {
      method: 'PUT',
      body: JSON.stringify({ payload }),
    }),
  acceptTransliteration: (contactId: string, fields: Record<string, string>) =>
    request<StagedEdit>(`/working-copy-contacts/${contactId}/transliteration`, {
      method: 'POST',
      body: JSON.stringify({ fields }),
    }),
  undoStagedEdit: (editId: string) =>
    request<StagedEdit>(`/staged-edits/${editId}/undo`, { method: 'POST' }),

  createDeleteBatch: (workingCopyId: string, sessionId?: string) =>
    request<DeleteBatch>(`/working-copies/${workingCopyId}/delete-batches`, {
      method: 'POST',
      body: JSON.stringify({ sessionId }),
    }),
  getDeleteBatch: (batchId: string) => request<DeleteBatch>(`/delete-batches/${batchId}`),
  previewDeleteBatch: (batchId: string) =>
    request<DeletionRecord[]>(`/delete-batches/${batchId}/preview`),
  confirmDeleteBatch: (batchId: string) =>
    request<DeleteBatch>(`/delete-batches/${batchId}/confirm`, { method: 'POST' }),
  undoDeleteBatch: (batchId: string) =>
    request<DeleteBatch>(`/delete-batches/${batchId}/undo`, { method: 'POST' }),
};
