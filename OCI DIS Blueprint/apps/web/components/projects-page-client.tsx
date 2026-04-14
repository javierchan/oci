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

export function ProjectsPageClient({ initialProjects }: ProjectsPageClientProps): JSX.Element {
  const router = useRouter();
  const [projects, setProjects] = useState<ProjectRow[]>(initialProjects);
  const [showForm, setShowForm] = useState<boolean>(initialProjects.length === 0);
  const [name, setName] = useState<string>("");
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string>("");

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

  return (
    <div className="space-y-8">
      <section className="flex flex-col gap-4 rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.25em] text-sky-700">Workspace</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight text-slate-950">Projects</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
            Create an assessment workspace, import the workbook, and drill into the catalog, QA, and volumetry flows.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowForm((current: boolean) => !current)}
          className="inline-flex items-center justify-center rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
        >
          {showForm ? "Hide Form" : "New Project"}
        </button>
      </section>

      {showForm ? (
        <section className="rounded-[2rem] border border-slate-200 bg-slate-950 p-6 text-white shadow-sm">
          <form
            onSubmit={(event) => {
              void handleCreateProject(event);
            }}
            className="flex flex-col gap-4 lg:flex-row lg:items-end"
          >
            <label className="flex-1">
              <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-slate-400">
                Project Name
              </span>
              <input
                name="name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Phase 1 parity assessment"
                className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none ring-0 placeholder:text-slate-500 focus:border-sky-300/60"
              />
            </label>
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex items-center justify-center rounded-full bg-amber-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-amber-300 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
            >
              {submitting ? "Creating…" : "Create Project"}
            </button>
          </form>
          {error ? <p className="mt-3 text-sm text-rose-300">{error}</p> : null}
        </section>
      ) : null}

      {projects.length === 0 ? (
        <section className="rounded-[2rem] border border-dashed border-slate-300 bg-white p-10 text-center">
          <h2 className="text-2xl font-semibold text-slate-900">No projects yet</h2>
          <p className="mt-3 text-sm text-slate-600">
            Start by creating a workspace, then upload the OCI workbook to populate the catalog.
          </p>
        </section>
      ) : (
        <section className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-slate-200 text-left">
            <thead className="bg-slate-950 text-xs uppercase tracking-[0.25em] text-slate-400">
              <tr>
                <th className="px-6 py-4 font-medium">Project</th>
                <th className="px-6 py-4 font-medium">Status</th>
                <th className="px-6 py-4 font-medium">Created</th>
                <th className="px-6 py-4 font-medium">Rows</th>
                <th className="px-6 py-4 font-medium">Open</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {projects.map((row: ProjectRow) => (
                <tr key={row.project.id} className="text-sm text-slate-700">
                  <td className="px-6 py-5">
                    <div>
                      <p className="font-semibold text-slate-950">{row.project.name}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.2em] text-slate-400">
                        {row.project.owner_id}
                      </p>
                    </div>
                  </td>
                  <td className="px-6 py-5">
                    <span className="inline-flex rounded-full border border-slate-300 px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-slate-600">
                      {row.project.status}
                    </span>
                  </td>
                  <td className="px-6 py-5 text-slate-500">{formatDate(row.project.created_at)}</td>
                  <td className="px-6 py-5 font-medium text-slate-900">{row.rowCount}</td>
                  <td className="px-6 py-5">
                    <div className="flex flex-wrap gap-3">
                      <Link
                        href={`/projects/${row.project.id}`}
                        className="text-sm font-medium text-sky-700 hover:text-sky-500"
                      >
                        Dashboard
                      </Link>
                      <Link
                        href={`/projects/${row.project.id}/catalog`}
                        className="text-sm font-medium text-slate-600 hover:text-slate-950"
                      >
                        Catalog
                      </Link>
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
