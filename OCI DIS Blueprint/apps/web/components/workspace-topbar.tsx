"use client";

/* Compact workspace top bar with breadcrumb context and a non-destructive command palette. */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  Bell,
  ChevronRight,
  Command,
  FileSpreadsheet,
  FolderOpen,
  LayoutDashboard,
  List,
  Network,
  Search,
  Sparkles,
  Wand2,
  X,
} from "lucide-react";

import { APP_VERSION } from "@/lib/app-version";
import { api } from "@/lib/api";

type CommandItem = {
  label: string;
  description: string;
  href?: string;
  disabled?: boolean;
};

const PROJECT_ID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function titleCase(value: string): string {
  return value
    .replace(/-/g, " ")
    .replace(/\b\w/g, (char: string) => char.toUpperCase());
}

function pathSectionLabel(pathname: string): string {
  const parts = pathname.split("/").filter(Boolean);
  if (parts.length === 0 || parts[0] === "projects" && parts.length === 1) {
    return "Projects";
  }
  if (parts[0] === "admin") {
    return parts[1] ? titleCase(parts[1]) : "Admin";
  }
  if (parts[0] === "projects" && PROJECT_ID_PATTERN.test(parts[1] ?? "")) {
    if (parts.length === 2) {
      return "Dashboard";
    }
    if (parts[2] === "graph") {
      return "Map";
    }
    if (parts[2] === "capture" && parts[3] === "new") {
      return "New Capture";
    }
    if (parts[2] === "catalog" && parts[3]) {
      return "Integration";
    }
    return titleCase(parts[2] ?? "Project");
  }
  return titleCase(parts[0] ?? "Projects");
}

function projectIdFromPath(pathname: string): string | null {
  const parts = pathname.split("/").filter(Boolean);
  return parts[0] === "projects" && PROJECT_ID_PATTERN.test(parts[1] ?? "") ? parts[1] : null;
}

function CommandPalette({
  open,
  onClose,
  projectId,
}: {
  open: boolean;
  onClose: () => void;
  projectId: string | null;
}): JSX.Element | null {
  const [query, setQuery] = useState<string>("");
  const projectLinks: CommandItem[] = projectId
    ? [
        { label: "Project dashboard", description: "Review QA, maturity, volumetry, and risks", href: `/projects/${projectId}` },
        { label: "Catalog", description: "Open the governed integration spine", href: `/projects/${projectId}/catalog` },
        { label: "Design map", description: "Inspect systems and dependency topology", href: `/projects/${projectId}/graph` },
        { label: "Import workbook", description: "Upload and review source workbook rows", href: `/projects/${projectId}/import` },
        { label: "New integration capture", description: "Open the five-step manual wizard", href: `/projects/${projectId}/capture/new` },
      ]
    : [];
  const items: CommandItem[] = [
    { label: "Projects", description: "Return to the project hub", href: "/projects" },
    ...projectLinks,
    { label: "Admin library", description: "Governed patterns, dictionaries, assumptions", href: "/admin" },
    projectId
      ? {
          label: "Run AI review",
          description: "Open the dashboard review board launcher",
          href: `/projects/${projectId}`,
        }
      : { label: "Run AI review", description: "Open a project first to run the review board", disabled: true },
  ];
  const normalizedQuery = query.trim().toLowerCase();
  const visibleItems = normalizedQuery
    ? items.filter((item) => `${item.label} ${item.description}`.toLowerCase().includes(normalizedQuery))
    : items;

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/20 px-4 py-14 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="Command palette">
      <button type="button" className="absolute inset-0 cursor-default" aria-label="Close command palette" onClick={onClose} />
      <section className="relative mx-auto w-full max-w-2xl overflow-hidden rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-2xl">
        <div className="flex items-center gap-3 border-b border-[var(--color-border)] px-4 py-3">
          <Search className="h-4 w-4 text-[var(--color-text-muted)]" />
          <input
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Type a command, route, or workflow..."
            className="min-w-0 flex-1 bg-transparent text-sm text-[var(--color-text-primary)] outline-none placeholder:text-[var(--color-text-muted)]"
          />
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1 text-[var(--color-text-muted)] transition hover:bg-[var(--color-hover)] hover:text-[var(--color-text-primary)]"
            aria-label="Close command palette"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="max-h-[24rem] overflow-y-auto py-2">
          <p className="px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--color-text-muted)]">
            Jump to
          </p>
          {visibleItems.map((item) => {
            const content = (
              <>
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--color-surface-2)] text-[var(--color-accent)]">
                  {item.label.includes("Map") || item.label.includes("map") ? <Network className="h-4 w-4" /> : null}
                  {item.label.includes("Catalog") ? <List className="h-4 w-4" /> : null}
                  {item.label.includes("dashboard") ? <LayoutDashboard className="h-4 w-4" /> : null}
                  {item.label.includes("Import") || item.label.includes("workbook") ? <FileSpreadsheet className="h-4 w-4" /> : null}
                  {item.label.includes("capture") ? <Wand2 className="h-4 w-4" /> : null}
                  {item.label.includes("Projects") || item.label.includes("Admin") ? <FolderOpen className="h-4 w-4" /> : null}
                  {item.label.includes("AI") ? <Sparkles className="h-4 w-4" /> : null}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold text-[var(--color-text-primary)]">{item.label}</span>
                  <span className="block truncate text-xs text-[var(--color-text-muted)]">{item.description}</span>
                </span>
                {item.disabled ? <span className="console-pill">Planned</span> : <ChevronRight className="h-4 w-4 text-[var(--color-text-muted)]" />}
              </>
            );

            return item.href && !item.disabled ? (
              <Link
                key={item.label}
                href={item.href}
                onClick={onClose}
                className="flex items-center gap-3 px-4 py-2.5 transition hover:bg-[var(--color-hover)]"
              >
                {content}
              </Link>
            ) : (
              <div key={item.label} className="flex cursor-not-allowed items-center gap-3 px-4 py-2.5 opacity-70">
                {content}
              </div>
            );
          })}
          {visibleItems.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-[var(--color-text-secondary)]">No commands match that search.</p>
          ) : null}
        </div>
      </section>
    </div>
  );
}

export function WorkspaceTopBar(): JSX.Element {
  const pathname = usePathname();
  const projectId = projectIdFromPath(pathname);
  const [paletteOpen, setPaletteOpen] = useState<boolean>(false);
  const [projectName, setProjectName] = useState<string>("");
  const sectionLabel = pathSectionLabel(pathname);
  const crumbs = useMemo(() => {
    if (!projectId) {
      return ["Workspace", sectionLabel];
    }
    return ["Projects", projectName || "Project", sectionLabel];
  }, [projectId, projectName, sectionLabel]);

  useEffect(() => {
    let cancelled = false;
    if (!projectId) {
      setProjectName("");
      return () => {
        cancelled = true;
      };
    }
    void api
      .getProject(projectId)
      .then((project) => {
        if (!cancelled) {
          setProjectName(project.name);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setProjectName("Project");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent): void {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((current) => !current);
      }
      if (event.key === "Escape") {
        setPaletteOpen(false);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <>
      <header className="sticky top-0 z-30 hidden border-b border-[var(--color-border)] bg-[var(--color-surface)]/95 px-5 py-2.5 backdrop-blur lg:block">
        <div className="flex items-center justify-between gap-4">
          <nav className="flex min-w-0 items-center gap-1.5 text-sm text-[var(--color-text-secondary)]" aria-label="Current location">
            {crumbs.map((crumb, index) => (
              <span key={`${crumb}-${index}`} className="inline-flex min-w-0 items-center gap-1.5">
                {index > 0 ? <ChevronRight className="h-3.5 w-3.5 shrink-0 text-[var(--color-text-muted)]" /> : null}
                <span
                  className={[
                    "truncate",
                    index === crumbs.length - 1 ? "font-semibold text-[var(--color-text-primary)]" : "",
                  ].join(" ")}
                  title={crumb}
                >
                  {crumb}
                </span>
              </span>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setPaletteOpen(true)}
              className="hidden min-w-[18rem] items-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2 text-left text-sm text-[var(--color-text-muted)] transition hover:border-[var(--color-line-strong)] hover:bg-[var(--color-hover)] xl:flex"
            >
              <Search className="h-4 w-4" />
              <span className="flex-1">Search or jump...</span>
              <span className="console-kbd">⌘K</span>
            </button>
            <button
              type="button"
              onClick={() => setPaletteOpen(true)}
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--color-border)] text-[var(--color-text-secondary)] transition hover:bg-[var(--color-hover)] hover:text-[var(--color-text-primary)] xl:hidden"
              aria-label="Open command palette"
            >
              <Command className="h-4 w-4" />
            </button>
            <button
              type="button"
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-transparent text-[var(--color-text-secondary)] transition hover:bg-[var(--color-hover)] hover:text-[var(--color-text-primary)]"
              aria-label="Notifications"
              title="Notifications"
            >
              <Bell className="h-4 w-4" />
            </button>
            <span className="console-pill">v{APP_VERSION}</span>
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--color-text-primary)] text-[11px] font-bold text-[var(--color-surface)]">
              JC
            </span>
          </div>
        </div>
      </header>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} projectId={projectId} />
    </>
  );
}
