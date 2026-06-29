"use client";

import { createContext, useContext, useState, useCallback } from "react";
import { api, type SessionSummary } from "@/lib/api";

export interface ChatMessage {
  id?: string;
  role: "user" | "assistant";
  content: string;
  sources?: any[];
  confidence?: number;
  reasoning_mode?: string;
  response?: any;
  timestamp?: Date;
}

interface ChatContextValue {
  // Current session
  sessionId: string;
  messages: ChatMessage[];
  addMessage: (msg: ChatMessage) => void;

  // Session list
  sessions: SessionSummary[];
  sessionsLoading: boolean;

  // Actions
  startNewSession: () => void;
  selectSession: (sessionId: string, getToken: () => Promise<string | null>) => Promise<void>;
  deleteSession: (sessionId: string, getToken: () => Promise<string | null>) => Promise<void>;
  refreshSessions: (getToken: () => Promise<string | null>) => Promise<void>;
}

const ChatContext = createContext<ChatContextValue | null>(null);

export function useChatContext() {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChatContext must be used within ChatProvider");
  return ctx;
}

export function ChatProvider({ children }: { children: React.ReactNode }) {
  const [sessionId, setSessionId] = useState<string>(() => crypto.randomUUID());
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);

  const addMessage = useCallback((msg: ChatMessage) => {
    setMessages((prev) => [...prev, msg]);
  }, []);

  const startNewSession = useCallback(() => {
    setSessionId(crypto.randomUUID());
    setMessages([]);
  }, []);

  const refreshSessions = useCallback(async (getToken: () => Promise<string | null>) => {
    setSessionsLoading(true);
    try {
      const token = await getToken();
      if (!token) return;
      const list = await api.listSessions(token);
      setSessions(list);
    } catch (e) {
      console.error("Failed to load sessions:", e);
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  const selectSession = useCallback(
    async (id: string, getToken: () => Promise<string | null>) => {
      try {
        const token = await getToken();
        if (!token) return;
        const detail = await api.getSession(token, id);
        setSessionId(id);
        setMessages(
          detail.messages.map((m) => ({
            id: crypto.randomUUID(),
            role: m.role as "user" | "assistant",
            content: m.content,
            timestamp: new Date(),
          }))
        );
      } catch (e) {
        console.error("Failed to load session:", e);
      }
    },
    []
  );

  const deleteSession = useCallback(
    async (id: string, getToken: () => Promise<string | null>) => {
      try {
        const token = await getToken();
        if (!token) return;
        await api.deleteSession(token, id);
        setSessions((prev) => prev.filter((s) => s.session_id !== id));
        if (id === sessionId) startNewSession();
      } catch (e) {
        console.error("Failed to delete session:", e);
      }
    },
    [sessionId, startNewSession]
  );

  return (
    <ChatContext.Provider
      value={{
        sessionId,
        messages,
        addMessage,
        sessions,
        sessionsLoading,
        startNewSession,
        selectSession,
        deleteSession,
        refreshSessions,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}
