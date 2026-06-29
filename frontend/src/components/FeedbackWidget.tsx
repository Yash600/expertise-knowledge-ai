"use client";
import { useState } from "react";
import { ThumbsUp, ThumbsDown, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";

interface Props {
  getToken: () => Promise<string | null>;
  sessionId: string;
  question: string;
  answer: string;
}

export default function FeedbackWidget({ getToken, sessionId, question, answer }: Props) {
  const [selected, setSelected] = useState<1 | 2 | null>(null);
  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [showComment, setShowComment] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleVote = (rating: 1 | 2) => {
    if (submitted) return;
    setSelected(rating);
    setShowComment(true);
  };

  const handleSubmit = async () => {
    if (!selected || submitted) return;
    setLoading(true);
    try {
      const token = await getToken();
      if (!token) return;
      await api.submitFeedback(token, {
        session_id: sessionId,
        question,
        answer,
        rating: selected,
        comment: comment || undefined,
      });
      setSubmitted(true);
      setShowComment(false);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <div className="flex items-center gap-1.5 text-xs text-green-600 font-medium">
        <CheckCircle2 size={13} />
        Thanks for your feedback!
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted">Was this helpful?</span>
        <button
          onClick={() => handleVote(2)}
          className={`p-1.5 rounded-lg border transition-colors ${
            selected === 2
              ? "border-green-400 bg-green-50 text-green-600"
              : "border-border text-muted hover:border-green-400 hover:text-green-600"
          }`}
        >
          <ThumbsUp size={13} />
        </button>
        <button
          onClick={() => handleVote(1)}
          className={`p-1.5 rounded-lg border transition-colors ${
            selected === 1
              ? "border-red-400 bg-red-50 text-red-500"
              : "border-border text-muted hover:border-red-400 hover:text-red-500"
          }`}
        >
          <ThumbsDown size={13} />
        </button>
      </div>

      {showComment && (
        <div className="flex gap-2">
          <input
            type="text"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Optional comment..."
            className="flex-1 bg-bg border border-border rounded-xl text-sm px-3 py-1.5 text-dark outline-none focus:border-coral transition-colors"
            onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
          />
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="btn-coral px-3 py-1.5 text-xs"
          >
            {loading ? "..." : "Send"}
          </button>
        </div>
      )}
    </div>
  );
}
