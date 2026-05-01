"use client";

/* Client-side project list and inline create workflow. */

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { FormEvent } from "react";
import { startTransition, useState } from "react";
import { ArrowRight, FolderOpen, Layers3, ShieldCheck, Trash2, User } from "lucide-react";

import { ConfirmModal } from "@/components/modal";
import { emitToast } from "@/hooks/use-toast";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Project } from "@/lib/types";

export type ProjectRow = {
  project: Project;
  rowCount: number;
};

type ProjectsPageClientProps = {
  initialProjects: ProjectRow[];
};

function isSyntheticProject(project: Project): boolean {
  const metadata = project.project_metadata;
  return metadata?.synthetic === true || metadata?.seed_type === "synthetic-enterprise";
}

export function ProjectsPageClient({ initialProjects }: ProjectsPageClientProps): JSX.Element {
  const router = useRouter();
  const [projects, setProjects] = useState<ProjectRow[]>(
    [...initialProjects].sort(
      (left, right) =>
        new Date(right.project.created_at).getTime() - new Date(left.project.created_at).getTime(),
    ),
  );
  const [showForm, setShowForm] = useState<boolean>(initialProjects.length === 0);
  const [name, setName] = useState<string>("");
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [activeProjectId, setActiveProjectId] = useState<string>("");
  const [search, setSearch] = useState<string>("");
  const [showArchived, setShowArchived] = useState<boolean>(false);
  const [archiveTarget, setArchiveTarget] = useState<{ id: string; name: string } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);
  const visibleProjects = projects.filter((row) => {
    const matchesSearch = row.project.name.toLowerCase().includes(search.trim().toLowerCase());
    const matchesArchive = showArchived || row.project.status !== "archived";
    return matchesSearch && matchesArchive;
  });
  const visibleActiveProjects = visibleProjects.filter((row) => row.project.status !== "archived");
  const visibleArchivedProjects = visibleProjects.filter((row) => row.project.status === "archived");
  const activeCount = projects.filter((row) => row.project.status === "active").length;
  const archivedCount = projects.length - activeCount;
  const totalIntegrations = projects.reduce((total, row) => total + row.rowCount, 0);
  const syntheticCount = projects.filter((row) => isSyntheticProject(row.project)).length;
  const nameCounts = visibleProjects.reduce((accumulator: Record<string, number>, row: ProjectRow) => {
    accumulator[row.project.name] = (accumulator[row.project.name] ?? 0) + 1;
    return accumulator;
  }, {});

  function mutationErrorMessage(action: string, caughtError: unknown): string {
    if (caughtError instanceof Error) {
      if (caughtError.message === "Failed to fetch") {
        return `Unable to ${action} right now. Confirm the local web and API services are running, then try again.`;
      }
      return caughtError.message;
    }
    return `Unable to ${action} right now.`;
  }

  async function handleCreateProject(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const projectName = name.trim();
    if (!projectName) {
      emitToast("error", "Project name is required.");
      return;
    }

    setSubmitting(true);
    try {
      const project = await api.createProject({ name: projectName, owner_id: "web-user" });
      setProjects((current: ProjectRow[]) => [{ project, rowCount: 0 }, ...current]);
      setName("");
      setShowForm(false);
      emitToast("success", `Project "${projectName}" created.`);
      startTransition(() => {
        router.refresh();
      });
    } catch (caughtError) {
      emitToast("error", mutationErrorMessage("create the project", caughtError));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleArchiveProject(projectId: string): Promise<void> {
    setActiveProjectId(projectId);
    try {
      const response = await api.archiveProject(projectId);
      setProjects((current: ProjectRow[]) =>
        current.map((row: ProjectRow) =>
          row.project.id === projectId ? { ...row, project: response.project } : row,
        ),
      );
      emitToast("info", "Project archived.");
      startTransition(() => {
        router.refresh();
      });
    } catch (caughtError) {
      emitToast("error", mutationErrorMessage("archive the project", caughtError));
    } finally {
      setActiveProjectId("");
    }
  }

  async function handleDeleteProject(projectId: string): Promise<void> {
    setActiveProjectId(projectId);
    try {
      await api.deleteProject(projectId);
      setProjects((current: ProjectRow[]) =>
        current.filter((row: ProjectRow) => row.project.id !== projectId),
      );
      setShowForm((current: boolean) => current || projects.length === 1);
      emitToast("success", "Project deleted.");
      startTransition(() => {
        router.refresh();
      });
    } catch (caughtError) {
      emitToast("error", mutationErrorMessage("delete the project", caughtError));
    } finally {
      setActiveProjectId("");
    }
  }

  function renderActions(row: ProjectRow): JSX.Element {
    return (
      <div className="flex flex-wrap items-center gap-2">
        {row.project.status !== "archived" ? (
          <>
            <button
              type="button"
              onClick={() => {
                setArchiveTarget({ id: row.project.id, name: row.project.name });
              }}
              disabled={activeProjectId === row.project.id}
              className="app-button-secondary px-4 py-2 text-xs text-amber-700 hover:text-amber-600 disabled:cursor-not-allowed disabled:text-[var(--color-text-muted)]"
            >
              {activeProjectId === row.project.id ? "Working…" : "Archive"}
            </button>
            <button
              type="button"
              disabled
              aria-disabled="true"
              title="Archive this workspace first to unlock permanent deletion."
              className="inline-flex cursor-not-allowed items-center gap-1.5 rounded-full border border-dashed border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-2 text-xs font-semibold text-[var(--color-text-muted)] opacity-80"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete
            </button>
          </>
        ) : null}
        {row.project.status === "archived" ? (
          <button
            type="button"
            onClick={() => {
              setDeleteTarget({ id: row.project.id, name: row.project.name });
            }}
            disabled={activeProjectId === row.project.id}
            className="app-button-secondary px-4 py-2 text-xs text-rose-700 hover:text-rose-500 disabled:cursor-not-allowed disabled:text-[var(--color-text-muted)]"
          >
            {activeProjectId === row.project.id ? "Deleting…" : "Delete"}
          </button>
        ) : null}
      </div>
    );
  }

  return (
    <div className="console-page">
      <section className="console-hero">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="app-kicker">Workspace · OCI DIS Blueprint</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[var(--color-text-primary)] md:text-4xl">
              Projects
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--color-text-secondary)]">
              Each project is an independent integration inventory with its own assumptions, dictionaries, QA rules, and topology map.
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="console-pill">{visibleProjects.length} visible</span>
              <span className="app-status-chip active">● {activeCount} active</span>
              {archivedCount > 0 ? (
                <span className="app-status-chip archived">◌ {archivedCount} archived</span>
              ) : null}
            </div>
          </div>
          <button
            type="button"
            onClick={() => setShowForm((current: boolean) => !current)}
            className="app-button-primary"
          >
            {showForm ? "Hide form" : "New project"}
          </button>
        </div>

        <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
          <label className="flex-1">
            <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-[var(--color-text-secondary)]">
              Search Projects
            </span>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Filter by project name..."
              className="app-input py-2.5"
            />
          </label>
          <label className="flex items-center gap-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-2.5 text-sm text-[var(--color-text-secondary)]">
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(event) => setShowArchived(event.target.checked)}
              className="h-4 w-4"
            />
            Show archived projects
          </label>
        </div>
      </section>

      {showForm ? (
        <section className="app-card p-5">
          <form
            onSubmit={(event) => {
              void handleCreateProject(event);
            }}
            className="flex flex-col gap-4 lg:flex-row lg:items-end"
          >
            <label className="flex-1">
              <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-[var(--color-text-secondary)]">
                Project Name
              </span>
              <input
                name="name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Phase 1 parity assessment"
                className="app-input py-2.5"
              />
            </label>
            <button
              type="submit"
              disabled={submitting}
              className="app-button-primary"
            >
              {submitting ? "Creating…" : "Create Project"}
            </button>
          </form>
        </section>
      ) : null}

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {[
          { label: "Active projects", value: activeCount, sub: "ready for assessment", icon: FolderOpen },
          { label: "Integrations tracked", value: totalIntegrations, sub: "across visible workspaces", icon: Layers3 },
          { label: "Synthetic demos", value: syntheticCount, sub: "governed validation data", icon: ShieldCheck },
          { label: "Archived", value: archivedCount, sub: "read-only workspaces", icon: Trash2 },
        ].map((stat) => {
          const Icon = stat.icon;
          return (
            <article key={stat.label} className="console-stat">
              <div className="flex items-start justify-between gap-3">
                <p className="app-label">{stat.label}</p>
                <span className="rounded-lg bg-[var(--color-surface-2)] p-2 text-[var(--color-text-secondary)]">
                  <Icon className="h-4 w-4" />
                </span>
              </div>
              <p className="mt-3 text-3xl font-semibold tracking-tight text-[var(--color-text-primary)]">
                {stat.value}
              </p>
              <p className="mt-1 text-xs text-[var(--color-text-muted)]">{stat.sub}</p>
            </article>
          );
        })}
      </section>

      {visibleProjects.length === 0 ? (
        <section className="app-card border-dashed p-10 text-center">
          <h2 className="text-2xl font-semibold text-[var(--color-text-primary)]">
            {projects.length === 0 ? "No projects yet" : "No projects match the current filters"}
          </h2>
          <p className="mt-3 text-sm text-[var(--color-text-secondary)]">
            {projects.length === 0
              ? "Start by creating a workspace, then upload the OCI workbook to populate the catalog."
              : "Adjust the search text or archived toggle to broaden the results."}
          </p>
        </section>
      ) : (
        <section className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">Active</h2>
              <p className="mt-1 text-sm text-[var(--color-text-secondary)]">
                Open assessment workspaces, ordered by most recent activity.
              </p>
            </div>
            <span className="console-pill">{visibleActiveProjects.length} workspaces</span>
          </div>
          <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
          <div className="space-y-4 p-4 md:hidden">
            {visibleActiveProjects.map((row: ProjectRow) => (
              <article
                key={row.project.id}
                className="rounded-[1.5rem] border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-sm"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-lg font-semibold text-[var(--color-text-primary)]">{row.project.name}</h3>
                      {isSyntheticProject(row.project) ? <span className="app-theme-chip">Synthetic</span> : null}
                    </div>
                    {nameCounts[row.project.name] > 1 ? (
                      <p className="mt-1 font-mono text-xs text-[var(--color-text-muted)]">
                        #{row.project.id.slice(-8)}
                      </p>
                    ) : null}
                    {isSyntheticProject(row.project) ? (
                      <p className="mt-3 text-sm text-[var(--color-text-secondary)]">
                        Governed synthetic reference project generated for end-to-end validation.
                      </p>
                    ) : (
                      <p className="mt-3 inline-flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
                        <User className="h-3.5 w-3.5" />
                        Workspace owner assigned
                      </p>
                    )}
                  </div>
                  <span className={`app-status-chip ${row.project.status === "active" ? "active" : "archived"}`}>
                    {row.project.status === "active" ? "● Active" : "◌ Archived"}
                  </span>
                </div>

                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div className="app-card-muted p-4">
                    <p className="app-label">Created</p>
                    <p className="mt-2 text-sm font-medium text-[var(--color-text-primary)]">
                      {formatDate(row.project.created_at)}
                    </p>
                  </div>
                  <div className="app-card-muted p-4">
                    <p className="app-label">Integrations</p>
                    <p className="mt-2 text-sm font-medium text-[var(--color-text-primary)]">{row.rowCount}</p>
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap gap-3">
                  <Link href={`/projects/${row.project.id}`} className="app-link">
                    Dashboard
                  </Link>
                  <Link
                    href={`/projects/${row.project.id}/catalog`}
                    className="text-sm font-medium text-[var(--color-text-secondary)] transition hover:text-[var(--color-text-primary)]"
                  >
                    Catalog
                  </Link>
                </div>

                <div className="mt-4">{renderActions(row)}</div>
              </article>
            ))}
          </div>

          <div className="hidden contents md:contents">
            {visibleActiveProjects.map((row: ProjectRow) => (
              <article
                key={row.project.id}
                className="app-card group flex min-h-[17rem] flex-col p-5 transition hover:-translate-y-0.5 hover:border-[var(--color-accent)] hover:shadow-[var(--shadow-panel)]"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--color-surface-2)] text-[var(--color-accent)]">
                      <FolderOpen className="h-4 w-4" />
                    </span>
                    <span className={`app-status-chip ${row.project.status === "active" ? "active" : "archived"}`}>
                      {row.project.status === "active" ? "● Active" : "◌ Archived"}
                    </span>
                  </div>
                  {isSyntheticProject(row.project) ? <span className="app-theme-chip">Synthetic</span> : null}
                </div>

                <div className="mt-5 min-w-0 flex-1">
                  <Link
                    href={`/projects/${row.project.id}`}
                    className="block text-lg font-semibold leading-snug tracking-tight text-[var(--color-text-primary)] transition hover:text-[var(--color-accent)]"
                  >
                    {row.project.name}
                  </Link>
                  {nameCounts[row.project.name] > 1 ? (
                    <p className="mt-1 font-mono text-xs text-[var(--color-text-muted)]">
                      #{row.project.id.slice(-8)}
                    </p>
                  ) : null}
                  <p className="mt-3 text-sm leading-6 text-[var(--color-text-secondary)]">
                    {isSyntheticProject(row.project)
                      ? "Governed synthetic reference project generated for end-to-end validation."
                      : "Independent assessment workspace with governed catalog, assumptions, and QA flow."}
                  </p>
                </div>

                <div className="mt-5 grid grid-cols-2 gap-3 border-t border-[var(--color-border)] pt-4">
                  <div>
                    <p className="app-label">Integrations</p>
                    <p className="mt-1 text-2xl font-semibold text-[var(--color-text-primary)]">{row.rowCount}</p>
                  </div>
                  <div>
                    <p className="app-label">Created</p>
                    <p className="mt-2 text-sm font-medium text-[var(--color-text-secondary)]">
                      {formatDate(row.project.created_at)}
                    </p>
                  </div>
                </div>

                <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-3">
                    <Link href={`/projects/${row.project.id}`} className="app-link inline-flex items-center gap-1">
                      Dashboard
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                    <Link
                      href={`/projects/${row.project.id}/catalog`}
                      className="text-sm font-medium text-[var(--color-text-secondary)] transition hover:text-[var(--color-text-primary)]"
                    >
                      Catalog
                    </Link>
                  </div>
                  {renderActions(row)}
                </div>
              </article>
            ))}
          </div>
          </div>

          {showArchived && visibleArchivedProjects.length > 0 ? (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                <div>
                  <h2 className="text-2xl font-semibold tracking-tight text-[var(--color-text-secondary)]">Archived</h2>
                  <p className="mt-1 text-sm text-[var(--color-text-muted)]">
                    Read-only workspaces retained for governance traceability.
                  </p>
                </div>
                <span className="console-pill">{visibleArchivedProjects.length} archived</span>
              </div>
              <div className="grid gap-4 opacity-80 lg:grid-cols-2 xl:grid-cols-3">
                {visibleArchivedProjects.map((row: ProjectRow) => (
                  <article
                    key={row.project.id}
                    className="app-card group flex min-h-[15rem] flex-col p-5 transition hover:border-[var(--color-line-strong)]"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--color-surface-2)] text-[var(--color-text-muted)]">
                        <FolderOpen className="h-4 w-4" />
                      </span>
                      <span className="app-status-chip archived">◌ Archived</span>
                    </div>
                    <div className="mt-5 flex-1">
                      <Link
                        href={`/projects/${row.project.id}`}
                        className="block text-lg font-semibold leading-snug tracking-tight text-[var(--color-text-primary)] transition hover:text-[var(--color-accent)]"
                      >
                        {row.project.name}
                      </Link>
                      <p className="mt-3 text-sm leading-6 text-[var(--color-text-secondary)]">
                        Archived workspace retained for source lineage, audit, and read-only review.
                      </p>
                    </div>
                    <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-[var(--color-border)] pt-4">
                      <span className="text-sm text-[var(--color-text-secondary)]">{row.rowCount} integrations</span>
                      {renderActions(row)}
                    </div>
                  </article>
                ))}
              </div>
            </>
          ) : null}
        </section>
      )}
      <ConfirmModal
        open={archiveTarget !== null}
        title="Archive project"
        description={`"${archiveTarget?.name}" will become read-only for governance review. You can still delete it later after archival if that workspace is no longer needed.`}
        confirmLabel="Archive project"
        cancelLabel="Keep active"
        onConfirm={() => {
          const target = archiveTarget;
          setArchiveTarget(null);
          if (target) {
            void handleArchiveProject(target.id);
          }
        }}
        onCancel={() => setArchiveTarget(null)}
      />
      <ConfirmModal
        open={deleteTarget !== null}
        title="Delete project"
        description={`"${deleteTarget?.name}" and all its imports, catalog rows, snapshots, and audit history will be permanently removed. This cannot be undone.`}
        confirmLabel="Delete permanently"
        cancelLabel="Keep it"
        danger
        onConfirm={() => {
          if (deleteTarget) {
            void handleDeleteProject(deleteTarget.id);
          }
          setDeleteTarget(null);
        }}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
