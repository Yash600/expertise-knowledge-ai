"use client";
import { ChatProvider } from "@/context/ChatContext";
import SessionSidebar from "@/components/SessionSidebar";

interface Props {
  children: React.ReactNode;
  sidebarSlot?: boolean;
}

export function DashboardProviders({ children }: { children: React.ReactNode }) {
  return <ChatProvider>{children}</ChatProvider>;
}

export function SidebarSessionSlot() {
  return <SessionSidebar />;
}

export default DashboardProviders;
