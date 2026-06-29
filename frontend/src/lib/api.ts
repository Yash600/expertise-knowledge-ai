/**
 * api.ts — Typed API client for the FastAPI backend.
 * Automatically attaches the Clerk JWT to every request.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface SourceCitation {
  filename: string;
  page: number | null;
  chunk_id: string;
  confidence: number;
}

export interface AskResponse {
  answer: string;
  sources: SourceCitation[];
  confidence: number;
  session_id: string;
  reasoning_mode: string;
  rewritten_query: string;
}

export interface DocumentInfo {
  doc_id: string;
  filename: string;
  file_type: string;
  chunk_count: number;
  page_count: number;
  ingested_at: string;
  size_bytes: number;
}

export interface IngestResponse {
  success: boolean;
  document: DocumentInfo;
  message: string;
}

export interface FeedbackPayload {
  session_id: string;
  question: string;
  answer: string;
  rating: 1 | 2;
  comment?: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface SessionSummary {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  last_preview: string;
}

export interface SessionDetail {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  messages: ChatMessage[];
}

export interface SessionResponse {
  session_id: string;
  messages: ChatMessage[];
  message_count: number;
}

export interface MetricsResponse {
  total_documents: number;
  total_chunks: number;
  total_queries: number;
  total_feedback: number;
  avg_confidence: number;
  avg_faithfulness: number | null;
  avg_answer_relevance: number | null;
}

export interface FeedbackItem {
  id: string;
  user_id: string;
  session_id: string;
  question: string;
  answer: string;
  rating: number;
  comment: string | null;
  created_at: string;
}

export interface FeedbackListResponse {
  feedback: FeedbackItem[];
  total: number;
  page: number;
  page_size: number;
}

// ── Core fetch helper ─────────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  token: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${API_URL}/api/v1${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error ${res.status}`);
  }

  return res.json();
}

// ── API methods ───────────────────────────────────────────────────────────────

export const api = {
  ask: (token: string, question: string, sessionId: string) =>
    apiFetch<AskResponse>("/ask", token, {
      method: "POST",
      body: JSON.stringify({ question, session_id: sessionId }),
    }),

  ingest: async (token: string, file: File): Promise<{ job_id: string }> => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_URL}/api/v1/ingest`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Upload error ${res.status}`);
    }
    return res.json();
  },

  ingestStatus: async (token: string, jobId: string): Promise<{
    status: "pending" | "processing" | "done" | "error";
    message: string;
    document?: DocumentInfo;
    error?: string;
  }> => {
    const res = await fetch(`${API_URL}/api/v1/ingest/status/${jobId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) throw new Error("Failed to check status");
    return res.json();
  },

  listDocuments: (token: string) =>
    apiFetch<{ documents: DocumentInfo[]; total: number }>("/documents", token),

  deleteDocument: (token: string, docId: string) =>
    apiFetch<{ success: boolean; message: string }>(`/documents/${docId}`, token, {
      method: "DELETE",
    }),

  submitFeedback: (token: string, payload: FeedbackPayload) =>
    apiFetch<{ success: boolean; feedback_id: string }>("/feedback", token, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getFeedback: (token: string, page = 1, pageSize = 20) =>
    apiFetch<FeedbackListResponse>(`/feedback?page=${page}&page_size=${pageSize}`, token),

  listSessions: (token: string) =>
    apiFetch<SessionSummary[]>("/sessions", token),

  getSession: (token: string, sessionId: string) =>
    apiFetch<SessionDetail>(`/sessions/${sessionId}`, token),

  deleteSession: (token: string, sessionId: string) =>
    apiFetch<{ success: boolean }>(`/sessions/${sessionId}`, token, {
      method: "DELETE",
    }),

  getMetrics: (token: string) =>
    apiFetch<MetricsResponse>("/metrics" .replace("/api/v1", ""), token).catch(() =>
      fetch(`${API_URL}/metrics`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((r) => r.json())
    ),

  getEvalResults: (token: string) =>
    apiFetch<{
      evaluated_at: string;
      total_cases: number;
      successful_cases: number;
      summary: {
        query_type_accuracy: number;
        out_of_scope_refusal_accuracy: number;
        hallucination_flags: number;
        avg_confidence: number;
        avg_latency_ms: number;
      };
      ragas_metrics: {
        faithfulness?: number;
        answer_relevancy?: number;
        context_precision?: number;
        context_recall?: number;
        error?: string;
      };
      per_category: Record<string, { count: number; type_accuracy: number; avg_confidence: number }>;
    }>("/eval/results", token),

  runEval: (token: string) =>
    apiFetch<{ message: string }>("/eval/run", token, { method: "POST" }),

  health: () => fetch(`${API_URL}/health`).then((r) => r.json()),
};
