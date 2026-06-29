"use client";
import { SignUp } from "@clerk/nextjs";

export default function SignUpPage() {
  return (
    <div className="min-h-screen dot-grid flex flex-col items-center justify-center p-4">
      <div className="mb-8 text-center">
        <div className="text-green-primary glow-green font-mono text-2xl font-bold mb-1">
          ▸ ENTERPRISE KNOWLEDGE ASSISTANT
        </div>
        <div className="text-text-muted text-sm font-mono">
          [ NEW OPERATOR REGISTRATION ]
        </div>
      </div>

      <div className="panel border-glow p-1 w-full max-w-md">
        <div className="bg-border px-4 py-2 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-green-primary"></span>
          <span className="text-xs text-text-muted font-mono">AUTH :: SIGN_UP</span>
        </div>
        <div className="p-6">
          <SignUp
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
              },
            }}
          />
        </div>
      </div>
    </div>
  );
}
