"use client";
import { useState, useEffect } from "react";
import { useAuth } from "@clerk/nextjs";
import { FileText, Database, HardDrive, Layers } from "lucide-react";
import DocumentUpload from "@/components/DocumentUpload";
import { api, type DocumentInfo } from "@/lib/api";

export default function DocumentsPage() {
  const { getToken } = useAuth();
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getToken().then(async (t) => {
      if (!t) return;
      try {
        const res = await api.listDocuments(t);
        setDocuments(res.documents);
      } catch {}
      setLoading(false);
    });
  }, [getToken]);

  const totalChunks = documents.reduce((s, d) => s + d.chunk_count, 0);
  const totalBytes = documents.reduce((s, d) => s + d.size_bytes, 0);
  const totalSize = totalBytes < 1024 * 1024
    ? `${(totalBytes / 1024).toFixed(1)} KB`
    : `${(totalBytes / 1024 / 1024).toFixed(1)} MB`;

  const stats = [
    { label: "Total Documents", value: documents.length, icon: <FileText size={18} className="text-coral" />, },
    { label: "Total Chunks", value: totalChunks, icon: <Layers size={18} className="text-coral" />, },
    { label: "Storage Used", value: totalSize, icon: <HardDrive size={18} className="text-coral" />, },
  ];

  return (
    <div className="h-full overflow-y-auto bg-bg">
      {/* Page header */}
      <div className="bg-card border-b border-border px-8 py-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-coral rounded-2xl flex items-center justify-center shadow-coral">
            <Database size={20} className="text-white" />
          </div>
          <div>
            <h1 className="font-bold text-dark text-xl">Document Management</h1>
            <p className="text-muted text-sm">Upload and index documents for your knowledge base</p>
          </div>
        </div>
      </div>

      <div className="px-8 py-6 space-y-6">
        {/* Stats */}
        <div className="grid grid-cols-3 gap-4">
          {stats.map((stat) => (
            <div key={stat.label} className="card px-5 py-4 flex items-center gap-4">
              <div className="w-10 h-10 bg-coral-muted rounded-xl flex items-center justify-center">
                {stat.icon}
              </div>
              <div>
                <p className="text-2xl font-bold text-dark">{stat.value}</p>
                <p className="text-xs text-muted">{stat.label}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Upload + list */}
        <div className="card px-6 py-6">
          <h2 className="font-bold text-dark text-base mb-4">Upload Document</h2>
          {loading ? (
            <div className="text-center py-10 text-muted text-sm">Loading documents...</div>
          ) : (
            <DocumentUpload
              getToken={getToken}
              documents={documents}
              onUpload={(doc) => setDocuments((prev) => [doc, ...prev])}
              onDelete={(id) => setDocuments((prev) => prev.filter((d) => d.doc_id !== id))}
            />
          )}
        </div>
      </div>
    </div>
  );
}
