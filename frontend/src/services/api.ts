const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000/api').replace(/\/+$/, '');

async function request<T>(path: string, options?: RequestInit, retries = 2): Promise<T> {
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
    return res.json();
  } catch (e: any) {
    // Retry on network failures (e.g. Render free tier cold start timeout)
    if (retries > 0 && e.message === 'Failed to fetch') {
      await new Promise((r) => setTimeout(r, 3000));
      return request<T>(path, options, retries - 1);
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
