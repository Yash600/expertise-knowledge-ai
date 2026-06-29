"use client";
import { useState, useRef, useEffect, useCallback } from "react";
import { Send, RotateCcw, Loader2, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import MessageBubble from "./MessageBubble";
import { useChatContext } from "@/context/ChatContext";

interface Props {
  getToken: () => Promise<string | null>;
}

export default function ChatWindow({ getToken }: Props) {
  const { messages, sessionId, addMessage, startNewSession, refreshSessions } = useChatContext();
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = useCallback(async () => {
    const question = input.trim();
    if (!question || loading) return;

    addMessage({ id: crypto.randomUUID(), role: "user", content: question, timestamp: new Date() });
    setInput("");
    setLoading(true);

    try {
      const token = await getToken();
      if (!token) throw new Error("Not authenticated");
      const resp = await api.ask(token, question, sessionId);
      addMessage({ id: crypto.randomUUID(), role: "assistant", content: resp.answer, response: resp, timestamp: new Date() });
      // Refresh session list so the sidebar shows the new/updated session
      refreshSessions(getToken);
    } catch (e: any) {
      addMessage({ id: crypto.randomUUID(), role: "assistant", content: `Sorry, something went wrong: ${e.message || "Please try again."}`, timestamp: new Date() });
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }, [input, loading, getToken, sessionId, addMessage, refreshSessions]);

  const handleReset = () => {
    startNewSession();
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="h-16 flex items-center justify-between px-6 bg-card border-b border-border">
        <div>
          <h2 className="font-bold text-dark text-base">AI Assistant</h2>
          <p className="text-xs text-muted">Session · {sessionId.slice(0, 8)}...</p>
        </div>
        <button
          onClick={handleReset}
          className="flex items-center gap-1.5 text-xs font-medium text-muted hover:text-coral transition-colors px-3 py-1.5 rounded-lg hover:bg-coral-muted"
        >
          <RotateCcw size={12} />
          New Session
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-16 h-16 bg-coral rounded-3xl flex items-center justify-center mb-4 shadow-coral">
              <Sparkles size={28} className="text-white" />
            </div>
            <h3 className="font-bold text-dark text-lg mb-1">Ask anything</h3>
            <p className="text-muted text-sm max-w-xs">
              Ask questions about your indexed documents and get instant answers with source citations.
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            getToken={getToken}
            sessionId={sessionId}
          />
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="card px-4 py-3 flex items-center gap-2.5 max-w-xs">
              <Loader2 size={14} className="animate-spin text-coral" />
              <span className="text-sm text-muted">Thinking...</span>
              <span className="flex gap-0.5">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="w-1.5 h-1.5 bg-coral rounded-full pulse-dot"
                    style={{ animationDelay: `${i * 0.2}s` }}
                  />
                ))}
              </span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="px-6 py-4 bg-card border-t border-border">
        <div className="flex gap-3 items-end">
          <div className="flex-1 bg-bg rounded-2xl border border-border focus-within:border-coral transition-colors px-4 py-3">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              placeholder="Ask a question about your documents..."
              rows={2}
              className="w-full bg-transparent text-dark text-sm resize-none outline-none placeholder-muted"
            />
          </div>
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            className="btn-coral flex items-center gap-2 px-5 py-3 text-sm"
          >
            {loading ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
            Ask
          </button>
        </div>
        <p className="text-xs text-muted mt-2">↵ Send · ⇧↵ New line · {messages.length} messages</p>
      </div>
    </div>
  );
}
