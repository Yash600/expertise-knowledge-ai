import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import Link from "next/link";
import { UserButton } from "@clerk/nextjs";
import { FileText, Settings } from "lucide-react";
import { DashboardProviders, SidebarSessionSlot } from "./providers";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { userId } = await auth();
  if (!userId) redirect("/sign-in");

  return (
    <DashboardProviders>
      <div className="flex h-screen overflow-hidden bg-bg">
        {/* Sidebar */}
        <aside className="w-56 flex-shrink-0 bg-card flex flex-col shadow-card">
          {/* Logo */}
          <div className="h-16 px-5 border-b border-border flex items-center">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 bg-coral rounded-xl flex items-center justify-center">
                <span className="text-white font-bold text-sm">EK</span>
              </div>
              <div>
                <div className="font-bold text-dark text-sm leading-tight">Enterprise</div>
                <div className="text-muted text-xs leading-tight">Knowledge AI</div>
              </div>
            </div>
          </div>

          {/* Static nav */}
          <nav className="px-3 pt-4 pb-2 space-y-1 border-b border-border">
            <NavLink href="/documents" label="Documents" icon={<FileText size={16} />} />
            <NavLink href="/admin" label="Admin" icon={<Settings size={16} />} />
          </nav>

          {/* Dynamic session list — client component inside ChatProvider */}
          <SidebarSessionSlot />

          {/* User */}
          <div className="px-4 py-4 border-t border-border flex items-center gap-3 flex-shrink-0">
            <UserButton
              appearance={{
                elements: { avatarBox: "w-8 h-8" },
              }}
            />
            <div>
              <div className="text-xs font-semibold text-dark">Account</div>
              <div className="text-xs text-muted">Operator</div>
            </div>
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-hidden flex flex-col bg-bg">
          {children}
        </main>
      </div>
    </DashboardProviders>
  );
}

function NavLink({
  href,
  label,
  icon,
}: {
  href: string;
  label: string;
  icon: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium
                 text-mid hover:bg-coral-muted hover:text-coral transition-colors group"
    >
      <span className="group-hover:text-coral text-muted transition-colors">{icon}</span>
      {label}
    </Link>
  );
}
