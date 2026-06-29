"use client";
import { useState, useRef, useCallback } from "react";
import { Upload, FileText, Trash2, Loader2, CheckCircle2, Clock } from "lucide-react";
import { api, type DocumentInfo } from "@/lib/api";

interface Props {
  getToken: () => Promise<string | null>;
  documents: DocumentInfo[];
  onUpload: (doc: DocumentInfo) => void;
  onDelete: (docId: string) => void;
}

interface JobState {
  jobId: string;
  filename: string;
  status: "pending" | "processing" | "done" | "error";
  message: string;
}

export default function DocumentUpload({ getToken, documents, onUpload, onDelete }: Props) {
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [activeJob, setActiveJob] = useState<JobState | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const pollStatus = useCallback(async (jobId: string, filename: string) => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        // Get a fresh token every poll — Clerk JWTs expire in ~60s
        const token = await getToken();
        if (!token) return;
        const job = await api.ingestStatus(token, jobId);
        setActiveJob({ jobId, filename, status: job.status, message: job.message });

        if (job.status === "done") {
          stopPolling();
          setActiveJob(null);
          if (job.document) onUpload(job.document as DocumentInfo);
        } else if (job.status === "error") {
          stopPolling();
          setError(job.error || "Ingestion failed");
          setActiveJob(null);
        }
      } catch {
        // keep polling on transient errors
      }
    }, 2000);
  }, [onUpload, getToken]);

  const handleFile = useCallback(
    async (file: File) => {
      const allowed = [
        "application/pdf",
        "text/plain",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      ];
      if (!allowed.includes(file.type) && !file.name.match(/\.(pdf|txt|docx)$/i)) {
        setError("Only PDF, TXT, and DOCX files are supported.");
        return;
      }
      if (file.size > 50 * 1024 * 1024) {
        setError("File too large. Max size: 50MB.");
        return;
      }

      setError(null);
      try {
        const token = await getToken();
        if (!token) throw new Error("Not authenticated");
        const { job_id } = await api.ingest(token, file);
        setActiveJob({ jobId: job_id, filename: file.name, status: "pending", message: "Queued..." });
        pollStatus(job_id, file.name);
      } catch (e: any) {
        setError(e.message || "Upload failed");
      }
    },
    [getToken, pollStatus]
  );

  const handleDelete = async (docId: string) => {
    setDeletingId(docId);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not authenticated");
      await api.deleteDocument(token, docId);
      onDelete(docId);
    } catch (e: any) {
      setError(e.message || "Delete failed");
    } finally {
      setDeletingId(null);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  const isProcessing = !!activeJob;

  return (
    <div className="space-y-5">
      {/* Drop zone */}
      <div
        className={`border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all ${
          isProcessing
            ? "border-coral bg-coral-muted cursor-not-allowed"
            : dragOver
            ? "border-coral bg-coral-muted"
            : "border-border hover:border-coral hover:bg-coral-muted/40"
        }`}
        onDragOver={(e) => { if (!isProcessing) { e.preventDefault(); setDragOver(true); } }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          if (!isProcessing) {
            const file = e.dataTransfer.files[0];
            if (file) handleFile(file);
          }
        }}
        onClick={() => !isProcessing && inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          accept=".pdf,.txt,.docx"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
            e.target.value = "";
          }}
        />

        {isProcessing ? (
          <div className="flex flex-col items-center gap-3">
            <div className="w-14 h-14 bg-coral-muted rounded-2xl flex items-center justify-center">
              <Loader2 size={24} className="text-coral animate-spin" />
            </div>
            <div>
              <p className="font-semibold text-dark text-sm">{activeJob!.filename}</p>
              <p className="text-xs text-coral font-medium mt-0.5">{activeJob!.message}</p>
              <p className="text-xs text-muted mt-1">
                {activeJob!.status === "processing" && activeJob!.message.includes("OCR") || activeJob!.message.includes("Embed")
                  ? "This may take a few minutes for scanned documents..."
                  : "Please wait..."}
              </p>
            </div>
            {/* Progress dots */}
            <div className="flex gap-1.5 mt-1">
              {["pending", "processing", "done"].map((s, i) => (
                <div
                  key={s}
                  className={`w-2 h-2 rounded-full transition-colors ${
                    (activeJob!.status === "pending" && i === 0) ||
                    (activeJob!.status === "processing" && i <= 1) ||
                    (activeJob!.status === "done" && i <= 2)
                      ? "bg-coral"
                      : "bg-border"
                  }`}
                />
              ))}
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <div className="w-14 h-14 bg-coral-muted rounded-2xl flex items-center justify-center">
              <Upload size={24} className="text-coral" />
            </div>
            <div>
              <p className="font-semibold text-dark text-sm">Drop file here or click to browse</p>
              <p className="text-xs text-muted mt-1">PDF · DOCX · TXT · Max 50MB</p>
              <p className="text-xs text-muted">Scanned PDFs are supported via OCR</p>
            </div>
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 px-4 py-3 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">
          <span className="font-medium">⚠ {error}</span>
          <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-600">✕</button>
        </div>
      )}

      {/* Document list */}
      {documents.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-dark text-sm">Indexed Documents</h3>
            <span className="text-xs text-muted">{documents.length} file{documents.length !== 1 ? "s" : ""}</span>
          </div>
          <div className="space-y-2">
            {documents.map((doc) => (
              <div
                key={doc.doc_id}
                className="flex items-center gap-3 px-4 py-3 rounded-xl bg-bg border border-border hover:border-coral/30 transition-colors"
              >
                <div className="w-9 h-9 bg-coral-muted rounded-xl flex items-center justify-center flex-shrink-0">
                  <FileText size={15} className="text-coral" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-dark truncate">{doc.filename}</p>
                  <p className="text-xs text-muted">
                    {doc.chunk_count} chunks · {doc.page_count} pages · {formatSize(doc.size_bytes)}
                  </p>
                </div>
                <CheckCircle2 size={14} className="text-green-500 flex-shrink-0" />
                <button
                  onClick={() => handleDelete(doc.doc_id)}
                  disabled={deletingId === doc.doc_id}
                  className="p-1.5 rounded-lg text-muted hover:text-red-500 hover:bg-red-50 transition-colors disabled:opacity-50"
                >
                  {deletingId === doc.doc_id ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <Trash2 size={14} />
                  )}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
