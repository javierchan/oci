"use client";

/* Client-side project list and inline create workflow. */

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { FormEvent } from "react";
import { startTransition, useState } from "react";

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
  const [error, setError] = useState<string>("");
  const visibleProjects = projects.filter((row) => {
    const matchesSearch = row.project.name.toLowerCase().includes(search.trim().toLowerCase());
    const matchesArchive = showArchived || row.project.status !== "archived";
    return matchesSearch && matchesArchive;
  });
  const nameCounts = visibleProjects.reduce((accumulator: Record<string, number>, row: ProjectRow) => {
    accumulator[row.project.name] = (accumulator[row.project.name] ?? 0) + 1;
    return accumulator;
  }, {});

  async function handleCreateProject(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const projectName = name.trim();
    if (!projectName) {
      setError("Project name is required.");
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      const project = await api.createProject({ name: projectName, owner_id: "web-user" });
      setProjects((current: ProjectRow[]) => [{ project, rowCount: 0 }, ...current]);
      setName("");
      setShowForm(false);
      startTransition(() => {
        router.refresh();
      });
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to create project.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleArchiveProject(projectId: string): Promise<void> {
    setActiveProjectId(projectId);
    setError("");
    try {
      const response = await api.archiveProject(projectId);
      setProjects((current: ProjectRow[]) =>
        current.map((row: ProjectRow) =>
          row.project.id === projectId ? { ...row, project: response.project } : row,
        ),
      );
      startTransition(() => {
        router.refresh();
      });
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to archive project.");
    } finally {
      setActiveProjectId("");
    }
  }

  async function handleDeleteProject(projectId: string, projectName: string): Promise<void> {
    const confirmed = window.confirm(
      `Delete project "${projectName}" and all related imports, catalog rows, snapshots, and audit history?`,
    );
    if (!confirmed) {
      return;
    }

    setActiveProjectId(projectId);
    setError("");
    try {
      await api.deleteProject(projectId);
      setProjects((current: ProjectRow[]) =>
        current.filter((row: ProjectRow) => row.project.id !== projectId),
      );
      setShowForm((current: boolean) => current || projects.length === 1);
      startTransition(() => {
        router.refresh();
      });
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to delete project.");
    } finally {
      setActiveProjectId("");
    }
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
          {error ? <p className="mt-3 text-sm text-rose-600">{error}</p> : null}
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
          <table className="min-w-full divide-y divide-[var(--color-table-border)] text-left">
            <thead className="app-table-header">
              <tr>
                <th className="px-6 py-4">Project</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4">Created</th>
                <th className="px-6 py-4">Rows</th>
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
                      <p className="mt-1 text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]">
                        {row.project.owner_id}
                      </p>
                      {isSyntheticProject(row.project) ? (
                        <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
                          Governed synthetic reference project generated for end-to-end validation.
                        </p>
                      ) : null}
                    </div>
                  </td>
                  <td className="px-6 py-5">
                    <span className="app-theme-chip">
                      {row.project.status}
                    </span>
                  </td>
                  <td className="px-6 py-5 text-[var(--color-text-secondary)]">{formatDate(row.project.created_at)}</td>
                  <td className="px-6 py-5 font-medium text-[var(--color-text-primary)]">{row.rowCount}</td>
                  <td className="px-6 py-5">
                    <div className="flex flex-wrap gap-3">
                      <Link
                        href={`/projects/${row.project.id}`}
                        className="app-link"
                      >
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
                  <td className="px-6 py-5">
                    <div className="flex flex-wrap gap-3">
                      {row.project.status !== "archived" ? (
                        <button
                          type="button"
                          onClick={() => {
                            void handleArchiveProject(row.project.id);
                          }}
                          disabled={activeProjectId === row.project.id}
                          className="text-sm font-medium text-amber-700 hover:text-amber-500 disabled:cursor-not-allowed disabled:text-slate-400"
                        >
                          {activeProjectId === row.project.id ? "Working…" : "Archive"}
                        </button>
                      ) : null}
                      {row.project.status === "archived" ? (
                        <button
                          type="button"
                          onClick={() => {
                            void handleDeleteProject(row.project.id, row.project.name);
                          }}
                          disabled={activeProjectId === row.project.id}
                          className="text-sm font-medium text-rose-700 hover:text-rose-500 disabled:cursor-not-allowed disabled:text-slate-400"
                        >
                          {activeProjectId === row.project.id ? "Deleting…" : "Delete"}
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
