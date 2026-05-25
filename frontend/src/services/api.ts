const API_BASE = 'http://localhost:8000/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Request failed: ${res.status}`);
  }
  return res.json();
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
