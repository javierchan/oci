"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { ContextualSupportAssistant } from "@/components/contextual-support-assistant";
import { Nav } from "@/components/nav";
import { ToastStack } from "@/components/toast";
import { WorkspaceTopBar } from "@/components/workspace-topbar";


export function WorkspaceShell({ children }: { children: ReactNode }): JSX.Element {
  const pathname = usePathname();
  const isPublicAuthPage = pathname === "/login";

  if (isPublicAuthPage) {
    return (
      <>
        {children}
        <ToastStack />
      </>
    );
  }

  return (
    <>
      <div className="min-h-screen lg:flex">
        <Nav />
        <div className="min-h-screen min-w-0 flex-1 bg-[var(--color-page-bg)]">
          <WorkspaceTopBar />
          <main className="min-w-0 px-4 py-5 sm:px-6 lg:px-8 lg:py-6">{children}</main>
        </div>
      </div>
      <ToastStack />
      <ContextualSupportAssistant />
    </>
  );
}
