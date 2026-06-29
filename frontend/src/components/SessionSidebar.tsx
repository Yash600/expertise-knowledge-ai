"use client";

import { useEffect, useCallback } from "react";
import { useAuth } from "@clerk/nextjs";
import { MessageSquare, Plus, Trash2, Clock } from "lucide-react";
import { useChatContext } from "@/context/ChatContext";
import { useRouter, usePathname } from "next/navigation";

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  const h = Math.floor(m / 60);
  const d = Math.floor(h / 24);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  if (h < 24) return `${h}h ago`;
  if (d < 7) return `${d}d ago`;
  return new Date(iso).toLocaleDateString();
}

export default function SessionSidebar() {
  const { getToken } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const {
    sessionId,
    sessions,
    sessionsLoading,
    startNewSession,
    selectSession,
    deleteSession,
    refreshSessions,
  } = useChatContext();

  const gt = useCallback(() => getToken(), [getToken]);

  // Load sessions on mount
  useEffect(() => {
    refreshSessions(gt);
  }, [refreshSessions, gt]);

  // Refresh after each new message (sessionId changes mean new chat was started,
  // but we also want to see the new session title appear)
  useEffect(() => {
    const interval = setInterval(() => refreshSessions(gt), 30000);
    return () => clearInterval(interval);
  }, [refreshSessions, gt]);

  const handleNew = () => {
    startNewSession();
    router.push("/chat");
  };

  const handleSelect = async (id: string) => {
    await selectSession(id, gt);
    router.push("/chat");
  };

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    await deleteSession(id, gt);
  };

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* New Chat button */}
      <div className="px-3 pb-3">
        <button
          onClick={handleNew}
          className="w-full flex items-center gap-2 px-3 py-2.5 rounded-xl text-sm font-medium
                     bg-coral text-white hover:bg-coral/90 transition-colors shadow-coral"
        >
          <Plus size={15} />
          New Chat
        </button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto px-3 space-y-0.5 pb-2">
        {sessions.length > 0 && (
          <p className="text-xs text-muted px-2 pb-1.5 pt-0.5 font-medium uppercase tracking-wide">
            Recent
          </p>
        )}

        {sessionsLoading && sessions.length === 0 && (
          <div className="flex items-center gap-2 px-2 py-3 text-xs text-muted">
            <Clock size={12} className="animate-pulse" />
            Loading...
          </div>
        )}

        {!sessionsLoading && sessions.length === 0 && (
          <p className="text-xs text-muted px-2 py-3 text-center leading-relaxed">
            Start a conversation<br />to see history here
          </p>
        )}

        {sessions.map((s) => {
          const isActive = s.session_id === sessionId;
          return (
            <div
              key={s.session_id}
              onClick={() => handleSelect(s.session_id)}
              className={`group relative flex items-start gap-2 px-2.5 py-2 rounded-xl cursor-pointer transition-colors ${
                isActive
                  ? "bg-coral-muted border border-coral/20"
                  : "hover:bg-bg"
              }`}
            >
              <MessageSquare
                size={13}
                className={`mt-0.5 flex-shrink-0 ${isActive ? "text-coral" : "text-muted"}`}
              />
              <div className="flex-1 min-w-0">
                <p
                  className={`text-xs font-medium truncate leading-snug ${
                    isActive ? "text-coral" : "text-dark"
                  }`}
                >
                  {s.title || "New Chat"}
                </p>
                <p className="text-[10px] text-muted mt-0.5">{timeAgo(s.updated_at)}</p>
              </div>

              {/* Delete button — visible on hover */}
              <button
                onClick={(e) => handleDelete(e, s.session_id)}
                className="opacity-0 group-hover:opacity-100 p-0.5 rounded text-muted
                           hover:text-red-500 transition-all flex-shrink-0 mt-0.5"
              >
                <Trash2 size={11} />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
