"use client";
import { useState, useEffect } from "react";
// sessionId & messages are now managed by ChatContext (persists across route changes)
import { useAuth } from "@clerk/nextjs";
import { FileText, Plus, BookOpen } from "lucide-react";
import ChatWindow from "@/components/ChatWindow";
import { api, type DocumentInfo } from "@/lib/api";

export default function ChatPage() {
  const { getToken } = useAuth();
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);

  useEffect(() => {
    getToken().then(async (t) => {
      if (!t) return;
      try {
        const res = await api.listDocuments(t);
        setDocuments(res.documents);
      } catch {}
    });
  }, [getToken]);

  return (
    <div className="flex h-full">
      {/* Doc sidebar */}
      <aside className="w-60 flex-shrink-0 bg-card border-r border-border flex flex-col">
        <div className="h-16 px-4 border-b border-border flex items-center justify-between">
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2">
              <BookOpen size={15} className="text-coral" />
              <span className="text-sm font-semibold text-dark">Documents</span>
            </div>
            <span className="text-xs bg-coral text-white rounded-full px-2 py-0.5 font-semibold">
              {documents.length}
            </span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2">
          {documents.length === 0 ? (
            <div className="text-center py-8">
              <div className="w-12 h-12 bg-cream rounded-2xl flex items-center justify-center mx-auto mb-3">
                <FileText size={20} className="text-muted" />
              </div>
              <p className="text-xs text-muted mb-1">No documents yet</p>
              <a href="/documents" className="text-xs text-coral font-medium hover:underline">
                Upload one →
              </a>
            </div>
          ) : (
            documents.map((doc) => (
              <div
                key={doc.doc_id}
                className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl bg-bg hover:bg-cream transition-colors"
              >
                <div className="w-7 h-7 bg-coral-muted rounded-lg flex items-center justify-center flex-shrink-0">
                  <FileText size={12} className="text-coral" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-medium text-dark truncate">{doc.filename}</p>
                  <p className="text-xs text-muted">{doc.chunk_count} chunks</p>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="px-3 py-3 border-t border-border">
          <a
            href="/documents"
            className="flex items-center justify-center gap-2 w-full py-2.5 rounded-xl border-2 border-dashed border-border text-xs font-medium text-muted hover:border-coral hover:text-coral transition-colors"
          >
            <Plus size={13} />
            Add Document
          </a>
        </div>
      </aside>

      {/* Chat */}
      <div className="flex-1 overflow-hidden">
        <ChatWindow getToken={getToken} />
      </div>
    </div>
  );
}
