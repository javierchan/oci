"use client";

/* Client-side project list and inline create workflow. */

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { FormEvent } from "react";
import { startTransition, useState } from "react";
import { User } from "lucide-react";

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
      <div className="flex flex-wrap items-center gap-3">
        {row.project.status !== "archived" ? (
          <>
            <button
              type="button"
              onClick={() => {
                setArchiveTarget({ id: row.project.id, name: row.project.name });
              }}
              disabled={activeProjectId === row.project.id}
              className="text-sm font-medium text-amber-700 transition hover:text-amber-500 disabled:cursor-not-allowed disabled:text-[var(--color-text-muted)]"
            >
              {activeProjectId === row.project.id ? "Working…" : "Archive"}
            </button>
            <span
              className="text-xs text-[var(--color-text-muted)]"
              title="Archive first to enable deletion"
            >
              Archive to delete
            </span>
          </>
        ) : null}
        {row.project.status === "archived" ? (
          <button
            type="button"
            onClick={() => {
              setDeleteTarget({ id: row.project.id, name: row.project.name });
            }}
            disabled={activeProjectId === row.project.id}
            className="text-sm font-medium text-rose-700 transition hover:text-rose-500 disabled:cursor-not-allowed disabled:text-[var(--color-text-muted)]"
          >
            {activeProjectId === row.project.id ? "Deleting…" : "Delete"}
          </button>
        ) : null}
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <section className="app-card flex flex-col gap-4 p-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="app-kicker">Project Actions</p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight text-[var(--color-text-primary)]">Manage workspaces</h2>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--color-text-secondary)]">
            Open an existing project or create a new workspace to continue the parity workflow.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowForm((current: boolean) => !current)}
          className="app-button-primary"
        >
          {showForm ? "Hide Form" : "New Project"}
        </button>
      </section>

      <section className="app-card p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <label className="flex-1">
            <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-[var(--color-text-secondary)]">
              Search Projects
            </span>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Filter by project name..."
              className="app-input"
            />
          </label>
          <label className="flex items-center gap-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-3 text-sm text-[var(--color-text-secondary)]">
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
        <section className="app-card p-6">
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
                className="app-input"
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
        <section className="app-table-shell">
          <div className="space-y-4 p-4 md:hidden">
            {visibleProjects.map((row: ProjectRow) => (
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

          <div className="hidden overflow-x-auto md:block">
            <table className="min-w-full divide-y divide-[var(--color-table-border)] text-left">
              <thead className="app-table-header">
                <tr>
                  <th className="px-6 py-4">Project</th>
                  <th className="px-6 py-4">Status</th>
                  <th className="px-6 py-4">Created</th>
                  <th className="px-6 py-4">Integrations</th>
                  <th className="px-6 py-4">Open</th>
                  <th className="px-6 py-4">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-table-border)]">
                {visibleProjects.map((row: ProjectRow) => (
                  <tr key={row.project.id} className="app-table-row text-sm">
                    <td className="px-6 py-5">
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="font-semibold text-[var(--color-text-primary)]">{row.project.name}</p>
                          {isSyntheticProject(row.project) ? (
                            <span className="app-theme-chip">Synthetic</span>
                          ) : null}
                          {nameCounts[row.project.name] > 1 ? (
                            <span className="text-xs font-mono text-[var(--color-text-muted)]">
                              #{row.project.id.slice(-8)}
                            </span>
                          ) : null}
                        </div>
                        {isSyntheticProject(row.project) ? (
                          <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
                            Governed synthetic reference project generated for end-to-end validation.
                          </p>
                        ) : (
                          <p className="mt-2 inline-flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
                            <User className="h-3.5 w-3.5" />
                            Workspace owner assigned
                          </p>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-5">
                      <span className={`app-status-chip ${row.project.status === "active" ? "active" : "archived"}`}>
                        {row.project.status === "active" ? "● Active" : "◌ Archived"}
                      </span>
                    </td>
                    <td className="px-6 py-5 text-[var(--color-text-secondary)]">{formatDate(row.project.created_at)}</td>
                    <td className="px-6 py-5 font-medium text-[var(--color-text-primary)]">{row.rowCount}</td>
                    <td className="px-6 py-5">
                      <div className="flex flex-wrap gap-3">
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
                    </td>
                    <td className="px-6 py-5">{renderActions(row)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
