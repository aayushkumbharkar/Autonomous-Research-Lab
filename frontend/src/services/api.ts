const API_BASE = (import.meta.env.VITE_API_URL || '/api').replace(/\/+$/, '');

/**
 * Track whether the backend has responded at least once this session.
 * Used to decide whether to show cold-start messaging to the user.
 */
export let backendWarm = false;

/**
 * Fire-and-forget warmup ping on module load.
 * Wakes the Render free-tier backend so the first real request is faster.
 */
(function warmup() {
  fetch(`${API_BASE}/health`, { method: 'GET' })
    .then(() => { backendWarm = true; })
    .catch(() => { /* ignore — real requests will retry */ });
})();

async function request<T>(
  path: string,
  options?: RequestInit,
  retries = 5,
  attempt = 1,
): Promise<T> {
  const url = `${API_BASE}${path}`;
  try {
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...options?.headers },
      ...options,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Request failed: ${res.status}`);
    }
    backendWarm = true;
    return res.json();
  } catch (e: any) {
    const isNetworkError =
      e.message === 'Failed to fetch' ||
      e.message === 'NetworkError when attempting to reach resource.' ||
      e.message === 'Load failed' ||
      e.name === 'TypeError';

    // Retry with exponential backoff for network failures (covers Render cold starts)
    if (retries > 0 && isNetworkError) {
      const delay = Math.min(3000 * Math.pow(1.5, attempt - 1), 15000);
      await new Promise((r) => setTimeout(r, delay));
      return request<T>(path, options, retries - 1, attempt + 1);
    }

    // Replace the cryptic "Failed to fetch" with a clear message
    if (isNetworkError) {
      throw new Error(
        'Unable to reach the server. The backend may be starting up (this can take up to 60 seconds on the free tier). Please try again in a moment.'
      );
    }
    throw e;
  }
}

// ─── Ingestion ───
export const api = {
  // Health
  health: () => request<any>('/health'),
  coverage: () => request<any>('/coverage'),

  // Ingestion
  ingestText: (text: string, filename: string, metadata?: any) =>
    request<any>('/ingest/text', {
      method: 'POST',
      body: JSON.stringify({ text, filename, metadata }),
    }),
  listTranscripts: () => request<any[]>('/ingest/transcripts'),
  getChunks: (id: string) => request<any[]>(`/ingest/transcripts/${id}/chunks`),

  // Search
  search: (query: string, topK = 10) =>
    request<any>('/search', {
      method: 'POST',
      body: JSON.stringify({ query, top_k: topK }),
    }),

  // Research
  submitQuery: (query: string, topK = 10, autoEvaluate = true, autoImprove = true) =>
    request<any>('/research/query', {
      method: 'POST',
      body: JSON.stringify({
        query,
        top_k: topK,
        auto_evaluate: autoEvaluate,
        auto_improve: autoImprove,
      }),
    }),
  listQueries: () => request<any[]>('/research/queries'),
  getQuery: (id: string) => request<any>(`/research/queries/${id}`),

  // Interview
  startSession: (topic: string) =>
    request<any>('/interview/sessions', {
      method: 'POST',
      body: JSON.stringify({ topic }),
    }),
  sendMessage: (sessionId: string, message: string) =>
    request<any>(`/interview/sessions/${sessionId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),
  endSession: (sessionId: string) =>
    request<any>(`/interview/sessions/${sessionId}/end`, { method: 'POST' }),
  listSessions: () => request<any[]>('/interview/sessions'),
  getSession: (id: string) => request<any>(`/interview/sessions/${id}`),

  // Evaluation
  evaluate: (answerId: string) =>
    request<any>('/evaluation/evaluate', {
      method: 'POST',
      body: JSON.stringify({ answer_id: answerId }),
    }),
  listEvalRuns: () => request<any[]>('/evaluation/runs'),
  getRetryComparison: (queryId: string) =>
    request<any>(`/evaluation/retry-comparison/${queryId}`),

  // Tools
  listTools: () => request<any>('/tools'),
  executeTool: (name: string, params: any) =>
    request<any>(`/tools/${name}/execute`, {
      method: 'POST',
      body: JSON.stringify({ params }),
    }),
  autoSelectTool: (query: string) =>
    request<any>('/tools/auto-select', {
      method: 'POST',
      body: JSON.stringify({ query }),
    }),
};
