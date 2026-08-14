"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronDown, LogOut, Settings, UsersRound } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { AuthUser } from "@/lib/types";


function initials(user: AuthUser | null): string {
  const source = user?.display_name || user?.email || "Account";
  return source.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join("") || "AC";
}


export function UserMenu(): JSX.Element {
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [open, setOpen] = useState(false);

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

  useEffect(() => {
    if (!open) return;
    function close(event: MouseEvent): void {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function closeOnEscape(event: KeyboardEvent): void {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  async function handleLogout(): Promise<void> {
    await api.logout().catch(() => undefined);
    setOpen(false);
    router.replace("/login");
    router.refresh();
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-label="Open user menu"
        aria-expanded={open}
        aria-haspopup="menu"
        className="flex items-center gap-1 rounded-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
      >
        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--color-text-primary)] text-[11px] font-bold text-[var(--color-surface)]">
          {initials(user)}
        </span>
        <ChevronDown className="h-3.5 w-3.5 text-[var(--color-text-muted)]" />
      </button>
      {open ? (
        <div role="menu" className="absolute right-0 top-12 z-50 w-64 overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-xl">
          <div className="border-b border-[var(--color-border)] px-4 py-3">
            <p className="truncate font-semibold text-[var(--color-text-primary)]">{user?.display_name ?? "Account"}</p>
            <p className="mt-1 truncate text-xs text-[var(--color-text-muted)]">{user?.username ? `@${user.username} · ` : ""}{user?.email}</p>
            {user ? <span className="console-pill mt-2 inline-flex">{user.role}</span> : null}
          </div>
          <div className="p-2">
            <Link role="menuitem" href="/account" onClick={() => setOpen(false)} className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-[var(--color-hover)]">
              <Settings className="h-4 w-4" /> Account security
            </Link>
            {user?.role === "Admin" ? (
              <Link role="menuitem" href="/admin/users" onClick={() => setOpen(false)} className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-[var(--color-hover)]">
                <UsersRound className="h-4 w-4" /> User management
              </Link>
            ) : null}
            <button role="menuitem" type="button" onClick={handleLogout} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-[var(--err)] hover:bg-[var(--err-bg)]">
              <LogOut className="h-4 w-4" /> Sign out
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
