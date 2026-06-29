"use client";
import type { SourceCitation } from "@/lib/api";
import { FileText } from "lucide-react";

interface Props {
  source: SourceCitation;
  index: number;
}

export default function SourceCard({ source, index }: Props) {
  const confidencePct = Math.round(source.confidence * 100);
  const barColor =
    confidencePct >= 80 ? "bg-green-500" :
    confidencePct >= 60 ? "bg-yellow-400" :
    "bg-muted";

  return (
    <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-bg border border-border rounded-xl text-xs hover:border-coral/40 transition-colors">
      <div className="w-5 h-5 bg-coral-muted rounded-md flex items-center justify-center flex-shrink-0">
        <FileText size={10} className="text-coral" />
      </div>
      <span className="text-dark font-medium truncate max-w-[110px]">{source.filename}</span>
      {source.page && (
        <span className="text-muted">p.{source.page}</span>
      )}
      <span className={`font-bold ${confidencePct >= 80 ? "text-green-600" : confidencePct >= 60 ? "text-yellow-600" : "text-muted"}`}>
        {confidencePct}%
      </span>
    </div>
  );
}
