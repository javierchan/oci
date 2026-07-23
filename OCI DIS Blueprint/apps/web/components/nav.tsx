"use client";

/* Responsive workspace navigation with a compact mobile header and drawer. */

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import {
  BadgeDollarSign,
  Bot,
  ClipboardCheck,
  ChevronRight,
  Database,
  FolderOpen,
  LayoutDashboard,
  List,
  Menu,
  Network,
  Search,
  Settings,
  ShieldCheck,
  Upload,
  Wand2,
  X,
} from "lucide-react";

import { ThemeToggle } from "@/components/theme-toggle";
import { APP_ICON_PATH, APP_NAME, APP_TAGLINE } from "@/lib/app-brand";
import { APP_VERSION } from "@/lib/app-version";
import { api } from "@/lib/api";
import { requestOpenCommandPalette } from "@/lib/command-palette";

type NavLink = {
  href: string;
  label: string;
};

type ProjectContextState = {
  label: string;
  status: "idle" | "loading" | "ready" | "missing";
};

type NavPanelProps = {
  pathname: string;
  baseLinks: NavLink[];
  adminLinks: NavLink[];
  projectLinks: NavLink[];
  projectContext: ProjectContextState;
  hasProjectContext: boolean;
  sectionTitle: string;
  onNavigate?: () => void;
  mobile?: boolean;
};

const PROJECT_ICONS: Record<string, JSX.Element> = {
  Dashboard: <LayoutDashboard className="h-4 w-4" />,
  Import: <Upload className="h-4 w-4" />,
  Capture: <Wand2 className="h-4 w-4" />,
  "Capture Review": <ClipboardCheck className="h-4 w-4" />,
  Catalog: <List className="h-4 w-4" />,
  Map: <Network className="h-4 w-4" />,
  "BOM & Cost": <BadgeDollarSign className="h-4 w-4" />,
};

const ADMIN_ICONS: Record<string, JSX.Element> = {
  Library: <Settings className="h-4 w-4" />,
  Patterns: <List className="h-4 w-4" />,
  Dictionaries: <Database className="h-4 w-4" />,
  Assumptions: <ShieldCheck className="h-4 w-4" />,
  Pricing: <BadgeDollarSign className="h-4 w-4" />,
  Agents: <Bot className="h-4 w-4" />,
};

const PROJECT_ID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function isProjectIdSegment(segment: string | undefined): boolean {
  return typeof segment === "string" && PROJECT_ID_PATTERN.test(segment);
}

function formatProjectLabel(projectId: string): string {
  return projectId.length > 28 ? `${projectId.slice(0, 28)}…` : projectId;
}

function linkClasses(active: boolean): string {
  return [
    "relative block rounded-md px-3 py-[7px] text-sm font-medium transition",
    active
      ? "bg-[var(--surface-2)] text-[var(--ink-1)] before:absolute before:bottom-1.5 before:left-0 before:top-1.5 before:w-0.5 before:rounded-full before:bg-[var(--accent)]"
      : "text-[var(--color-text-secondary)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text-primary)]",
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
    if (pathParts[1] === "pricing") {
      return "Pricing";
    }
    if (pathParts[1] === "agents") {
      return "Agent Operations";
    }
    return "Admin";
  }
  if (pathParts[0] !== "projects") {
    return "Projects";
  }
  if (pathParts.length === 1) {
    return "Projects";
  }
  const projectSegment = pathParts[1];
  if (!isProjectIdSegment(projectSegment)) {
    if (projectSegment === "missing") {
      return "Project";
    }
    return projectSegment
      .replace(/-/g, " ")
      .replace(/\b\w/g, (char: string) => char.toUpperCase());
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
  if (section === "capture-review") {
    return "Capture Review";
  }
  if (section === "graph") {
    return "Graph";
  }
  if (section === "bom") {
    return "BOM & Cost";
  }
  if (section === "map") {
    return "Map";
  }

  return section
    .replace(/-/g, " ")
    .replace(/\b\w/g, (char: string) => char.toUpperCase());
}

function NavSection({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <div className="mt-5">
      <p className="mb-2 px-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">{title}</p>
      {children}
    </div>
  );
}

function NavPanel({
  pathname,
  baseLinks,
  adminLinks,
  projectLinks,
  projectContext,
  hasProjectContext,
  sectionTitle,
  onNavigate,
  mobile = false,
}: NavPanelProps): JSX.Element {
  const shellPadding = mobile ? "px-5 py-5" : "px-4 py-5 xl:px-5";

  return (
    <div className={`flex h-full flex-col ${shellPadding} text-[var(--color-text-primary)]`}>
      <div className="flex items-center gap-3.5 border-b border-[var(--color-border)] px-1 pb-4">
        <Image
          src={APP_ICON_PATH}
          alt=""
          aria-hidden="true"
          width={44}
          height={44}
          className="h-11 w-11 shrink-0 rounded-[14px] shadow-[0_8px_20px_rgba(199,70,52,0.18)]"
        />
        <div className="min-w-0">
          <p className="app-brand-name truncate text-[var(--color-text-primary)]">
            {APP_NAME}
          </p>
          <p className="app-brand-tagline mt-1 truncate text-[var(--color-text-muted)]">
            {APP_TAGLINE}
          </p>
        </div>
      </div>

      <button
        type="button"
        onClick={() => {
          onNavigate?.();
          requestOpenCommandPalette();
        }}
        className="mt-4 flex items-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2 text-left text-sm text-[var(--color-text-muted)] transition hover:bg-[var(--color-hover)]"
        aria-label="Open command palette"
        aria-haspopup="dialog"
        aria-keyshortcuts="Meta+K Control+K"
        title="Search commands and workspace routes"
      >
        <Search className="h-4 w-4" />
        <span className="min-w-0 flex-1 truncate">Search or jump...</span>
        <span className="console-kbd">⌘K</span>
      </button>

      <NavSection title="Workspace">
        <nav className="space-y-2">
          {baseLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              onClick={onNavigate}
              className={linkClasses(pathname === link.href)}
            >
              {link.label}
            </Link>
          ))}
        </nav>
      </NavSection>

      {projectLinks.length > 0 ? (
        <NavSection title="Current Project">
          <div className="mb-3 rounded-lg border border-[var(--line)] bg-[var(--surface-2)] px-3 py-3">
            <p className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">
              <FolderOpen className="h-3.5 w-3.5" />
              Current Project
            </p>
            <p
              className="mt-2 inline-flex items-center gap-2 text-sm font-medium text-[var(--color-text-primary)]"
              title={projectContext.label}
            >
              <ChevronRight className="h-4 w-4 text-[var(--color-text-muted)]" />
              {formatProjectLabel(projectContext.label)}
            </p>
          </div>
          <nav className="space-y-1">
            {projectLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={onNavigate}
                className={linkClasses(pathname === link.href)}
              >
                <span className="inline-flex items-center gap-2">
                  {PROJECT_ICONS[link.label] ?? null}
                  {link.label}
                </span>
              </Link>
            ))}
          </nav>
        </NavSection>
      ) : null}

      <NavSection title="Governance">
        <nav className="space-y-1">
          {adminLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              onClick={onNavigate}
              className={linkClasses(
                pathname === link.href || (link.href !== "/admin" && pathname.startsWith(`${link.href}/`)),
              )}
            >
              <span className="inline-flex items-center gap-2">
                {ADMIN_ICONS[link.label] ?? <Settings className="h-4 w-4" />}
                {link.label}
              </span>
            </Link>
          ))}
        </nav>
      </NavSection>

      <div
        className={`rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-3 ${
          mobile ? "mt-6" : "mt-auto"
        }`}
      >
        <ThemeToggle />
        <div className="mt-3 border-t border-[var(--color-border)] pt-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--color-text-muted)]">
            Context
          </p>
          <div className="mt-1.5 flex min-w-0 items-center justify-between gap-2">
            <p className="min-w-0 truncate text-sm font-medium text-[var(--color-text-primary)]">
              {hasProjectContext ? sectionTitle : sectionTitle === "Project" ? "Project" : sectionTitle}
            </p>
            <span className="shrink-0 font-mono text-[10px] font-medium text-[var(--color-text-muted)]">
              v{APP_VERSION}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export function Nav(): JSX.Element {
  const pathname = usePathname();
  const pathParts = pathname.split("/").filter(Boolean);
  const projectId = pathParts[0] === "projects" && isProjectIdSegment(pathParts[1]) ? pathParts[1] : null;
  const [projectContext, setProjectContext] = useState<ProjectContextState>(
    projectId
      ? { label: formatProjectLabel(projectId), status: "loading" }
      : { label: "Project", status: "idle" },
  );
  const [mobileOpen, setMobileOpen] = useState<boolean>(false);

  useEffect(() => {
    let cancelled = false;

    if (!projectId) {
      setProjectContext({ label: "Project", status: "idle" });
      return () => {
        cancelled = true;
      };
    }

    setProjectContext({ label: formatProjectLabel(projectId), status: "loading" });

    void api
      .getProject(projectId)
      .then((project) => {
        if (!cancelled) {
          setProjectContext({ label: project.name, status: "ready" });
        }
      })
      .catch(() => {
        if (!cancelled) {
          setProjectContext({ label: "Project", status: "missing" });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!mobileOpen) {
      return;
    }

    const originalOverflow = document.body.style.overflow;
    function handleKeyDown(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        setMobileOpen(false);
      }
    }

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = originalOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [mobileOpen]);

  const hasProjectContext = projectContext.status === "ready";
  const sectionTitle =
    projectId && !hasProjectContext ? "Project" : contextLabelFromPath(pathname);

  const baseLinks: NavLink[] = [{ href: "/projects", label: "Projects" }];
  const adminLinks: NavLink[] = [
    { href: "/admin", label: "Library" },
    { href: "/admin/patterns", label: "Patterns" },
    { href: "/admin/dictionaries", label: "Dictionaries" },
    { href: "/admin/assumptions", label: "Assumptions" },
    { href: "/admin/pricing", label: "Pricing" },
    { href: "/admin/agents", label: "Agents" },
  ];
  const projectLinks: NavLink[] = projectId && hasProjectContext
    ? [
        { href: `/projects/${projectId}`, label: "Dashboard" },
        { href: `/projects/${projectId}/import`, label: "Import" },
        { href: `/projects/${projectId}/capture`, label: "Capture" },
        { href: `/projects/${projectId}/capture-review`, label: "Capture Review" },
        { href: `/projects/${projectId}/catalog`, label: "Catalog" },
        { href: `/projects/${projectId}/map`, label: "Map" },
        { href: `/projects/${projectId}/bom`, label: "BOM & Cost" },
      ]
    : [];

  return (
    <>
      <div className="sticky top-0 z-40 border-b border-[var(--color-border)] bg-[var(--color-surface)]/95 backdrop-blur lg:hidden">
        <div className="flex items-center justify-between gap-3 px-4 py-3">
          <div className="min-w-0">
            <p className="app-brand-name app-brand-name-mobile truncate text-[var(--color-accent)]">{APP_NAME}</p>
            <p className="mt-1 truncate text-base font-semibold text-[var(--color-text-primary)]">{sectionTitle}</p>
            <p className="mt-1 truncate text-xs text-[var(--color-text-secondary)]">
              {hasProjectContext
                ? projectContext.label
                : "Import parity, QA governance, and topology review."}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            aria-label="Open navigation"
            aria-expanded={mobileOpen}
            className="inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] text-[var(--color-text-primary)] transition hover:border-[var(--color-accent)]"
          >
            <Menu className="h-5 w-5" />
          </button>
        </div>
      </div>

      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Workspace navigation">
          <button
            type="button"
            onClick={() => setMobileOpen(false)}
            aria-label="Close navigation"
            className="absolute inset-0 bg-slate-950/45 backdrop-blur-sm"
          />
          <div className="absolute inset-y-0 left-0 flex w-[19rem] max-w-[calc(100vw-1.5rem)] flex-col border-r border-[var(--color-border)] bg-[var(--color-surface-2)] shadow-2xl">
            <div className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-4">
              <p className="text-sm font-semibold text-[var(--color-text-primary)]">Workspace Menu</p>
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                aria-label="Close navigation"
                className="inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-primary)]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto">
              <NavPanel
                pathname={pathname}
                baseLinks={baseLinks}
                adminLinks={adminLinks}
                projectLinks={projectLinks}
                projectContext={projectContext}
                hasProjectContext={hasProjectContext}
                sectionTitle={sectionTitle}
                onNavigate={() => setMobileOpen(false)}
                mobile
              />
            </div>
          </div>
        </div>
      ) : null}

      <aside className="hidden border-r border-[var(--line)] bg-[var(--surface)] lg:sticky lg:top-0 lg:flex lg:h-screen lg:w-[232px] lg:shrink-0 lg:overflow-y-auto">
        <NavPanel
          pathname={pathname}
          baseLinks={baseLinks}
          adminLinks={adminLinks}
          projectLinks={projectLinks}
          projectContext={projectContext}
          hasProjectContext={hasProjectContext}
          sectionTitle={sectionTitle}
        />
      </aside>
    </>
  );
}
