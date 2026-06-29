"use client";
import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@clerk/nextjs";
import { api, type FeedbackItem } from "@/lib/api";

interface RAGASScores {
  faithfulness?: number;
  answer_relevancy?: number;
  context_precision?: number;
  context_recall?: number;
  error?: string;
}

interface EvalSummary {
  query_type_accuracy: number;
  out_of_scope_refusal_accuracy: number;
  hallucination_flags: number;
  avg_confidence: number;
  avg_latency_ms: number;
}

interface EvalResults {
  evaluated_at: string;
  total_cases: number;
  successful_cases: number;
  summary: EvalSummary;
  ragas_metrics: RAGASScores;
  per_category: Record<string, { count: number; type_accuracy: number; avg_confidence: number }>;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="card p-5">
      <p className="text-xs font-medium text-muted uppercase tracking-widest mb-1">{label}</p>
      <p className="text-3xl font-bold text-dark">{value}</p>
      {sub && <p className="text-xs text-muted mt-1">{sub}</p>}
    </div>
  );
}

function ScoreBar({
  label,
  score,
  target,
}: {
  label: string;
  score: number | undefined;
  target: number;
}) {
  if (score === undefined) return null;
  const pct = Math.round(score * 100);
  const met = score >= target;
  return (
    <div>
      <div className="flex justify-between items-center mb-1.5">
        <span className="text-sm font-medium text-dark">{label}</span>
        <span className={`text-sm font-semibold ${met ? "text-emerald-600" : "text-amber-500"}`}>
          {pct}%{" "}
          <span className="text-xs font-normal text-muted">
            / target {Math.round(target * 100)}%
          </span>
        </span>
      </div>
      <div className="h-2 rounded-full bg-cream overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${
            met ? "bg-emerald-500" : "bg-amber-400"
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function SummaryMetric({ label, value, good }: { label: string; value: string; good: boolean }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-border last:border-0">
      <span className="text-sm text-mid">{label}</span>
      <span className={`text-sm font-semibold ${good ? "text-emerald-600" : "text-amber-500"}`}>
        {value}
      </span>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AdminPage() {
  const { getToken } = useAuth();
  const [feedback, setFeedback] = useState<FeedbackItem[]>([]);
  const [metrics, setMetrics] = useState<any>(null);
  const [evalResults, setEvalResults] = useState<EvalResults | null>(null);
  const [loading, setLoading] = useState(true);
  const [evalLoading, setEvalLoading] = useState(false);
  const [runningEval, setRunningEval] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [evalToast, setEvalToast] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    const t = await getToken();
    if (!t) return;

    try {
      const [fb, met] = await Promise.allSettled([
        api.getFeedback(t),
        api.getMetrics(t),
      ]);
      if (fb.status === "fulfilled") setFeedback(fb.value.feedback);
      if (met.status === "fulfilled") setMetrics(met.value);
    } catch (e: any) {
      setError(e.message);
    }

    // Load eval results — 404 is expected if not run yet
    try {
      setEvalLoading(true);
      const r = await api.getEvalResults(t);
      setEvalResults(r);
    } catch {
      // not run yet — fine
    } finally {
      setEvalLoading(false);
    }

    setLoading(false);
  }, [getToken]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRunEval = async () => {
    const t = await getToken();
    if (!t) return;
    setRunningEval(true);
    try {
      await api.runEval(t);
      setEvalToast("Evaluation started — results will appear in ~2 minutes.");
      setTimeout(async () => {
        const t2 = await getToken();
        if (!t2) return;
        try {
          const r = await api.getEvalResults(t2);
          setEvalResults(r);
          setEvalToast(null);
        } catch {}
        setRunningEval(false);
      }, 120_000);
    } catch (e: any) {
      setEvalToast(`Failed to start: ${e.message}`);
      setRunningEval(false);
    }
  };

  const thumbsUp = feedback.filter((f) => f.rating === 2).length;
  const thumbsDown = feedback.filter((f) => f.rating === 1).length;
  const thumbsPct =
    feedback.length > 0 ? `${Math.round((thumbsUp / feedback.length) * 100)}%` : "—";

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-dark">Admin Dashboard</h1>
          <p className="text-sm text-muted mt-0.5">Evaluation metrics and user feedback overview</p>
        </div>
        <button
          onClick={handleRunEval}
          disabled={runningEval}
          className="btn-coral px-5 py-2.5 text-sm"
        >
          {runningEval ? "Running…" : "Run Evaluation"}
        </button>
      </div>

      {evalToast && (
        <div className="rounded-xl bg-coral-muted border border-coral/30 text-coral px-4 py-3 text-sm">
          {evalToast}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-24">
          <div className="w-6 h-6 border-2 border-coral border-t-transparent rounded-full animate-spin" />
        </div>
      ) : error ? (
        <div className="card p-5 text-sm text-amber-600">⚠ {error}</div>
      ) : (
        <>
          {/* Stat cards */}
          {metrics && (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <StatCard label="Documents" value={metrics.total_documents} />
              <StatCard label="Chunks" value={metrics.total_chunks} />
              <StatCard label="Feedback" value={metrics.total_feedback} />
              <StatCard label="Thumbs Up" value={thumbsPct} sub={`${thumbsUp} up · ${thumbsDown} down`} />
            </div>
          )}

          {/* RAGAS scores */}
          <div className="card p-6">
            <div className="flex items-center justify-between mb-5">
              <div>
                <h2 className="font-semibold text-dark">RAGAS Evaluation Scores</h2>
                {evalResults && (
                  <p className="text-xs text-muted mt-0.5">
                    Last run: {new Date(evalResults.evaluated_at).toLocaleString()} ·{" "}
                    {evalResults.successful_cases}/{evalResults.total_cases} cases
                  </p>
                )}
              </div>
              {evalLoading && (
                <div className="w-4 h-4 border-2 border-coral border-t-transparent rounded-full animate-spin" />
              )}
            </div>

            {evalResults?.ragas_metrics && !evalResults.ragas_metrics.error ? (
              <div className="space-y-5">
                <ScoreBar label="Faithfulness" score={evalResults.ragas_metrics.faithfulness} target={0.85} />
                <ScoreBar label="Answer Relevancy" score={evalResults.ragas_metrics.answer_relevancy} target={0.8} />
                <ScoreBar label="Context Precision" score={evalResults.ragas_metrics.context_precision} target={0.7} />
                <ScoreBar label="Context Recall" score={evalResults.ragas_metrics.context_recall} target={0.7} />
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {["Faithfulness", "Answer Relevancy", "Context Precision", "Context Recall"].map((m) => (
                  <div key={m} className="rounded-xl bg-cream px-4 py-5 text-center">
                    <p className="text-xs text-muted mb-2">{m}</p>
                    <p className="text-2xl font-bold text-border">—</p>
                  </div>
                ))}
              </div>
            )}

            {/* Lightweight pipeline summary */}
            {evalResults?.summary && (
              <div className="mt-6 pt-5 border-t border-border">
                <h3 className="text-sm font-semibold text-dark mb-1">Pipeline Metrics</h3>
                <div>
                  <SummaryMetric
                    label="Query Type Accuracy"
                    value={`${Math.round(evalResults.summary.query_type_accuracy * 100)}%`}
                    good={evalResults.summary.query_type_accuracy >= 0.8}
                  />
                  <SummaryMetric
                    label="OOS Refusal Rate"
                    value={`${Math.round(evalResults.summary.out_of_scope_refusal_accuracy * 100)}%`}
                    good={evalResults.summary.out_of_scope_refusal_accuracy >= 0.9}
                  />
                  <SummaryMetric
                    label="Hallucination Flags"
                    value={String(evalResults.summary.hallucination_flags)}
                    good={evalResults.summary.hallucination_flags === 0}
                  />
                  <SummaryMetric
                    label="Avg Confidence"
                    value={`${Math.round(evalResults.summary.avg_confidence * 100)}%`}
                    good={evalResults.summary.avg_confidence >= 0.6}
                  />
                  <SummaryMetric
                    label="Avg Latency"
                    value={`${Math.round(evalResults.summary.avg_latency_ms)}ms`}
                    good={evalResults.summary.avg_latency_ms < 5000}
                  />
                </div>
              </div>
            )}

            {!evalResults && !evalLoading && (
              <p className="text-sm text-muted text-center py-4">
                No evaluation run yet.{" "}
                <button
                  onClick={handleRunEval}
                  className="text-coral underline underline-offset-2 hover:text-coral-dark"
                >
                  Run Evaluation
                </button>{" "}
                to generate scores.
              </p>
            )}
          </div>

          {/* Per-category breakdown */}
          {evalResults?.per_category && Object.keys(evalResults.per_category).length > 0 && (
            <div className="card p-6">
              <h2 className="font-semibold text-dark mb-4">Per-Category Results</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left">
                      <th className="pb-2 pr-4 font-medium text-muted">Category</th>
                      <th className="pb-2 pr-4 font-medium text-muted">Cases</th>
                      <th className="pb-2 pr-4 font-medium text-muted">Type Accuracy</th>
                      <th className="pb-2 font-medium text-muted">Avg Confidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(evalResults.per_category).map(([cat, stats]) => (
                      <tr key={cat} className="border-b border-border/50 hover:bg-cream/60 transition-colors">
                        <td className="py-2.5 pr-4 capitalize text-dark font-medium">{cat}</td>
                        <td className="py-2.5 pr-4 text-mid">{stats.count}</td>
                        <td className="py-2.5 pr-4">
                          <span
                            className={
                              stats.type_accuracy >= 0.8
                                ? "text-emerald-600 font-medium"
                                : "text-amber-500 font-medium"
                            }
                          >
                            {Math.round(stats.type_accuracy * 100)}%
                          </span>
                        </td>
                        <td className="py-2.5 text-mid">{Math.round(stats.avg_confidence * 100)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* User feedback table */}
          <div className="card p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-dark">
                User Feedback
                <span className="ml-2 text-sm font-normal text-muted">({feedback.length})</span>
              </h2>
              <div className="flex gap-4 text-sm">
                <span className="text-emerald-600 font-medium">👍 {thumbsUp}</span>
                <span className="text-red-500 font-medium">👎 {thumbsDown}</span>
              </div>
            </div>

            {feedback.length === 0 ? (
              <div className="py-10 text-center text-muted text-sm">No feedback collected yet.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left">
                      <th className="pb-2 pr-4 font-medium text-muted w-16">Rating</th>
                      <th className="pb-2 pr-4 font-medium text-muted">Question</th>
                      <th className="pb-2 pr-4 font-medium text-muted">Comment</th>
                      <th className="pb-2 font-medium text-muted whitespace-nowrap">Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {feedback.map((f) => (
                      <tr
                        key={f.id}
                        className="border-b border-border/50 hover:bg-cream/60 transition-colors"
                      >
                        <td className="py-2.5 pr-4">
                          {f.rating === 2 ? (
                            <span className="text-emerald-600">👍</span>
                          ) : (
                            <span className="text-red-500">👎</span>
                          )}
                        </td>
                        <td className="py-2.5 pr-4 max-w-[240px]">
                          <span className="text-dark line-clamp-2">{f.question}</span>
                        </td>
                        <td className="py-2.5 pr-4 text-muted">
                          {f.comment || <span className="text-border">—</span>}
                        </td>
                        <td className="py-2.5 text-muted whitespace-nowrap">
                          {new Date(f.created_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
