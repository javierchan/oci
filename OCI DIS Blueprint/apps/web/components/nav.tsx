"use client";

/* Sidebar navigation for the OCI DIS Blueprint workspace shell. */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Network, Settings } from "lucide-react";

import { ThemeToggle } from "@/components/theme-toggle";
import { APP_VERSION } from "@/lib/app-version";

type NavLink = {
  href: string;
  label: string;
};

function linkClasses(active: boolean): string {
  return [
    "block rounded-2xl border px-4 py-3 text-sm font-medium transition",
    active
      ? "border-[var(--color-accent)] bg-[var(--color-surface)] text-[var(--color-text-primary)] shadow-[0_0_0_1px_var(--color-accent)]"
      : "border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-secondary)] hover:border-[var(--color-accent)] hover:text-[var(--color-text-primary)]",
  ].join(" ");
}

function contextLabelFromPath(pathname: string): string {
  const pathParts = pathname.split("/").filter(Boolean);
  if (pathParts.length === 0) {
    return "Projects";
  }
  if (pathParts[0] === "admin") {
    if (pathParts[1] === "patterns") {
      return "Patterns";
    }
    if (pathParts[1] === "dictionaries") {
      return "Dictionaries";
    }
    if (pathParts[1] === "assumptions") {
      return "Assumptions";
    }
    return "Admin";
  }
  if (pathParts[0] !== "projects") {
    return "Projects";
  }
  if (pathParts.length === 1) {
    return "Projects";
  }
  if (pathParts.length === 2) {
    return "Dashboard";
  }

  const section = pathParts[2];
  if (section === "catalog" && pathParts[3]) {
    return "Integration Detail";
  }
  if (section === "capture" && pathParts[3] === "new") {
    return "Capture New";
  }
  if (section === "graph") {
    return "Graph";
  }

  return section
    .replace(/-/g, " ")
    .replace(/\b\w/g, (char: string) => char.toUpperCase());
}

export function Nav(): JSX.Element {
  const pathname = usePathname();
  const pathParts = pathname.split("/").filter(Boolean);
  const projectId = pathParts[0] === "projects" && pathParts[1] ? pathParts[1] : null;
  const sectionTitle = contextLabelFromPath(pathname);

  const baseLinks: NavLink[] = [{ href: "/projects", label: "Projects" }];
  const adminLinks: NavLink[] = [{ href: "/admin", label: "Admin" }];
  const projectLinks: NavLink[] = projectId
    ? [
        { href: `/projects/${projectId}`, label: "Dashboard" },
        { href: `/projects/${projectId}/import`, label: "Import" },
        { href: `/projects/${projectId}/capture`, label: "Capture" },
        { href: `/projects/${projectId}/catalog`, label: "Catalog" },
        { href: `/projects/${projectId}/graph`, label: "Map" },
      ]
    : [];

  return (
    <aside className="flex w-full max-w-xs flex-col border-r border-[var(--color-border)] bg-[var(--color-surface-2)] px-5 py-6 text-[var(--color-text-primary)]">
      <div className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
        <p className="text-xs uppercase tracking-[0.25em] text-[var(--color-accent)]">Oracle Cloud</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-[var(--color-text-primary)]">OCI DIS Blueprint</h1>
        <p className="mt-3 text-sm leading-6 text-[var(--color-text-secondary)]">
          Frontend workspace for import parity, QA governance, and volumetry review.
        </p>
      </div>

      <div className="mt-8">
        <p className="mb-3 text-xs uppercase tracking-[0.25em] text-[var(--color-text-muted)]">Navigation</p>
        <nav className="space-y-2">
          {baseLinks.map((link: NavLink) => (
            <Link key={link.href} href={link.href} className={linkClasses(pathname === link.href)}>
              {link.label}
            </Link>
          ))}
        </nav>
      </div>

      {projectLinks.length > 0 ? (
        <div className="mt-8">
          <p className="mb-3 text-xs uppercase tracking-[0.25em] text-[var(--color-text-muted)]">Current Project</p>
          <nav className="space-y-2">
            {projectLinks.map((link: NavLink) => (
              <Link
                key={link.href}
                href={link.href}
                className={linkClasses(pathname === link.href)}
              >
                <span className="inline-flex items-center gap-2">
                  {link.label === "Map" ? <Network className="h-4 w-4" /> : null}
                  {link.label}
                </span>
              </Link>
            ))}
          </nav>
        </div>
      ) : null}

      <div className="mt-8">
        <p className="mb-3 text-xs uppercase tracking-[0.25em] text-[var(--color-text-muted)]">Governance</p>
        <nav className="space-y-2">
          {adminLinks.map((link: NavLink) => (
            <Link
              key={link.href}
              href={link.href}
              className={linkClasses(pathname === link.href || pathname.startsWith(`${link.href}/`))}
            >
              <span className="inline-flex items-center gap-2">
                <Settings className="h-4 w-4" />
                {link.label}
              </span>
            </Link>
          ))}
        </nav>
      </div>

      <div className="mt-auto space-y-4 rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
        <ThemeToggle />
        <div>
          <p className="text-xs uppercase tracking-[0.25em] text-[var(--color-text-muted)]">Context</p>
          <p className="mt-2 text-lg font-medium text-[var(--color-text-primary)]">{sectionTitle}</p>
        </div>
        <span className="app-theme-chip">
          v{APP_VERSION}
        </span>
      </div>
    </aside>
  );
}
