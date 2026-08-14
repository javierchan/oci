"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { LogOut, UserRound } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { AuthUser } from "@/lib/types";


export function AccountControl({ onNavigate }: { onNavigate?: () => void }): JSX.Element {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    let active = true;
    void api.getCurrentUser().then((session) => {
      if (active) setUser(session.user);
    }).catch(() => {
      if (active) setUser(null);
    });
    return () => {
      active = false;
    };
  }, []);

  async function handleLogout(): Promise<void> {
    await api.logout().catch(() => undefined);
    onNavigate?.();
    router.replace("/login");
    router.refresh();
  }

  return (
    <div className="mb-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
      <Link href="/account" onClick={onNavigate} className="flex items-center gap-2 rounded-md text-sm text-[var(--color-text-primary)] hover:text-[var(--accent)]">
        <UserRound className="h-4 w-4" />
        <span className="min-w-0 flex-1 truncate">{user?.display_name ?? "Account"}</span>
        {user ? <span className="text-[10px] text-[var(--color-text-muted)]">{user.role}</span> : null}
      </Link>
      <button type="button" onClick={handleLogout} className="mt-2 flex w-full items-center gap-2 rounded-md py-1 text-left text-xs text-[var(--color-text-muted)] hover:text-[var(--err)]">
        <LogOut className="h-3.5 w-3.5" />
        Sign out
      </button>
    </div>
  );
}
