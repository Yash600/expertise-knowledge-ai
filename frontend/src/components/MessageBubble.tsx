"use client";
import type { AskResponse } from "@/lib/api";
import SourceCard from "./SourceCard";
import FeedbackWidget from "./FeedbackWidget";
import { Bot } from "lucide-react";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  response?: AskResponse;
  timestamp: Date;
}

interface Props {
  message: Message;
  getToken: () => Promise<string | null>;
  sessionId: string;
}

export default function MessageBubble({ message, getToken, sessionId }: Props) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%]">
          <div className="bg-coral text-white rounded-2xl rounded-tr-md px-4 py-3 shadow-coral">
            <p className="text-sm leading-relaxed">{message.content}</p>
          </div>
          <p className="text-xs text-muted text-right mt-1">
            {message.timestamp ? new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""}
          </p>
        </div>
      </div>
    );
  }

  const resp = message.response;
  const isError = message.content.startsWith("Sorry, something went wrong");

  return (
    <div className="flex justify-start gap-3">
      {/* Avatar */}
      <div className="w-8 h-8 rounded-xl bg-coral-muted flex items-center justify-center flex-shrink-0 mt-1">
        <Bot size={16} className="text-coral" />
      </div>

      <div className="max-w-[80%] space-y-2">
        {/* Answer card */}
        <div className={`card px-4 py-3 ${isError ? "border border-red-200" : ""}`}>
          {resp && (
            <div className="flex items-center gap-3 mb-2 pb-2 border-b border-border">
              <span className="text-xs font-medium text-muted">
                Mode: <span className="text-coral font-semibold">{resp.reasoning_mode}</span>
              </span>
              <span className="text-xs font-medium text-muted">
                Confidence: <span className="text-coral font-semibold">{Math.round(resp.confidence * 100)}%</span>
              </span>
            </div>
          )}
          <p className="text-sm text-dark leading-relaxed whitespace-pre-wrap">{message.content}</p>
        </div>

        {/* Sources */}
        {resp && resp.sources.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-muted mb-1.5">Sources ({resp.sources.length})</p>
            <div className="flex flex-wrap gap-2">
              {resp.sources.map((src, i) => (
                <SourceCard key={src.chunk_id} source={src} index={i} />
              ))}
            </div>
          </div>
        )}

        {/* Feedback */}
        {resp && (
          <FeedbackWidget
            getToken={getToken}
            sessionId={sessionId}
            question={resp.rewritten_query || message.content}
            answer={message.content}
          />
        )}

        <p className="text-xs text-muted">
          {message.timestamp ? new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""}
        </p>
      </div>
    </div>
  );
}
