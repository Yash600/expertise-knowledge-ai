"use client";
import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <div className="min-h-screen dot-grid flex flex-col items-center justify-center p-4">
      {/* Header */}
      <div className="mb-8 text-center">
        <div className="text-green-primary glow-green font-mono text-2xl font-bold mb-1">
          ▸ ENTERPRISE KNOWLEDGE ASSISTANT
        </div>
        <div className="text-text-muted text-sm font-mono">
          [ SECURE ACCESS TERMINAL v1.0 ]
        </div>
      </div>

      {/* Panel */}
      <div className="panel border-glow p-1 w-full max-w-md">
        <div className="bg-border px-4 py-2 flex items-center gap-2 mb-0">
          <span className="w-2 h-2 rounded-full bg-yellow-primary"></span>
          <span className="text-xs text-text-muted font-mono">AUTH :: SIGN_IN</span>
        </div>
        <div className="p-6">
          <SignIn
            appearance={{
              elements: {
                card: "bg-transparent shadow-none",
                headerTitle: "text-green-primary font-mono",
                headerSubtitle: "text-text-muted font-mono text-sm",
                formButtonPrimary:
                  "bg-yellow-primary text-bg font-mono font-bold hover:bg-yellow-dim transition-colors",
                formFieldInput:
                  "bg-bg border-border text-text-primary font-mono focus:border-blue-accent",
                formFieldLabel: "text-text-muted font-mono text-xs",
                footerActionLink: "text-blue-accent hover:text-green-primary",
                identityPreviewText: "text-text-primary font-mono",
                dividerLine: "bg-border",
                dividerText: "text-text-muted font-mono text-xs",
              },
            }}
          />
        </div>
      </div>

      <div className="mt-6 text-text-dim text-xs font-mono">
        © 2025 TechCorp Inc. — All rights reserved.
      </div>
    </div>
  );
}
