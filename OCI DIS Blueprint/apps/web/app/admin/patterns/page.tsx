"use client";

/* Pattern governance page for create, edit, and delete flows. */

import Link from "next/link";
import { Lock, Pencil, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Breadcrumb } from "@/components/breadcrumb";
import { AdminConfirmDelete } from "@/components/admin-confirm-delete";
import { AdminPatternForm } from "@/components/admin-pattern-form";
import { PatternSupportBadge } from "@/components/pattern-support-badge";
import { api } from "@/lib/api";
import type { PatternDefinition, PatternDefinitionCreate } from "@/lib/types";

export default function AdminPatternsPage(): JSX.Element {
  const [patterns, setPatterns] = useState<PatternDefinition[]>([]);
  const [toolOptions, setToolOptions] = useState<string[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [deleting, setDeleting] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [showCreate, setShowCreate] = useState<boolean>(false);
  const [editingPattern, setEditingPattern] = useState<PatternDefinition | null>(null);
  const [deletingPattern, setDeletingPattern] = useState<PatternDefinition | null>(null);
  const [catalogProjectId, setCatalogProjectId] = useState<string | null>(null);
  const [lastCreatedPatternId, setLastCreatedPatternId] = useState<string>("");

  async function load(): Promise<void> {
    setLoading(true);
    try {
      const [patternList, toolList, overlayList, projects] = await Promise.all([
        api.listPatterns(),
        api.listDictionaryOptions("TOOLS"),
        api.listDictionaryOptions("OVERLAYS").catch(() => ({ category: "OVERLAYS", options: [] })),
        api.listProjects(),
      ]);
      setPatterns(patternList.patterns);
      setToolOptions([...toolList.options, ...overlayList.options].map((option) => option.value));
      setCatalogProjectId(projects.projects[0]?.id ?? null);
      setError("");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to load patterns.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleCreate(body: PatternDefinitionCreate): Promise<void> {
    setSaving(true);
    try {
      await api.createPattern(body);
      setLastCreatedPatternId(body.pattern_id);
      setShowCreate(false);
      await load();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to create pattern.");
    } finally {
      setSaving(false);
    }
  }

  async function handleUpdate(body: PatternDefinitionCreate): Promise<void> {
    if (!editingPattern) {
      return;
    }
    setSaving(true);
    try {
      await api.updatePattern(editingPattern.pattern_id, body);
      setEditingPattern(null);
      await load();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to update pattern.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(): Promise<void> {
    if (!deletingPattern) {
      return;
    }
    setDeleting(true);
    try {
      await api.deletePattern(deletingPattern.pattern_id);
      setDeletingPattern(null);
      await load();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to delete pattern.");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="space-y-6">
      <section className="app-card flex flex-col gap-4 p-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="app-kicker">Admin Governance</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">Patterns</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
            Manage the pattern catalog used across capture, catalog editing, QA, and exports.
          </p>
          <div className="mt-4">
            <Breadcrumb
              items={[
                { label: "Home", href: "/projects" },
                { label: "Admin", href: "/admin" },
                { label: "Patterns" },
              ]}
            />
          </div>
        </div>
        <button
          type="button"
          onClick={() => {
            setShowCreate(true);
            setEditingPattern(null);
            setError("");
          }}
          className="app-button-primary"
        >
          New Pattern
        </button>
      </section>

      {lastCreatedPatternId && catalogProjectId ? (
        <section className="app-card p-4">
          <Link
            href={`/projects/${catalogProjectId}/catalog?pattern=${encodeURIComponent(lastCreatedPatternId)}`}
            className="app-link inline-flex"
          >
            View integrations using this pattern →
          </Link>
        </section>
      ) : null}

      {showCreate ? (
        <AdminPatternForm
          mode="create"
          toolOptions={toolOptions}
          initialValue={null}
          isLoading={saving}
          error={error}
          onSubmit={handleCreate}
          onCancel={() => {
            setShowCreate(false);
            setError("");
          }}
        />
      ) : null}

      {editingPattern ? (
        <AdminPatternForm
          mode="edit"
          toolOptions={toolOptions}
          initialValue={editingPattern}
          isLoading={saving}
          error={error}
          onSubmit={handleUpdate}
          onCancel={() => {
            setEditingPattern(null);
            setError("");
          }}
        />
      ) : null}

      {error && !showCreate && !editingPattern ? (
        <p className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </p>
      ) : null}

      <section className="app-table-shell">
        <table className="min-w-full divide-y divide-[var(--color-table-border)] text-left">
          <thead className="app-table-header">
            <tr>
              <th className="px-6 py-4 font-medium">Pattern ID</th>
              <th className="px-6 py-4 font-medium">Name</th>
              <th className="px-6 py-4 font-medium">Category</th>
              <th className="px-6 py-4 font-medium">Support</th>
              <th className="px-6 py-4 font-medium">Guidance</th>
              <th className="px-6 py-4 font-medium">System</th>
              <th className="px-6 py-4 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-table-border)] text-sm">
            {loading ? (
              <tr>
                <td className="px-6 py-8 text-[var(--color-text-secondary)]" colSpan={7}>
                  Loading patterns…
                </td>
              </tr>
            ) : (
              patterns.map((pattern) => (
                <tr key={pattern.pattern_id} className="app-table-row">
                  <td className="px-6 py-4 font-semibold text-[var(--color-text-primary)]">{pattern.pattern_id}</td>
                  <td className="px-6 py-4">
                    <div>
                      <p className="font-medium text-[var(--color-text-primary)]">{pattern.name}</p>
                      {pattern.description ? (
                        <p className="mt-1 text-xs leading-5 text-[var(--color-text-secondary)]">{pattern.description}</p>
                      ) : null}
                      {pattern.oci_components ? (
                        <p className="mt-2 whitespace-pre-line text-xs leading-5 text-[var(--color-text-muted)]">
                          {pattern.oci_components}
                        </p>
                      ) : null}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-[var(--color-text-secondary)]">{pattern.category}</td>
                  <td className="px-6 py-4">
                    <div className="space-y-2">
                      <PatternSupportBadge support={pattern.support} />
                      <p className="max-w-xs text-xs leading-5 text-[var(--color-text-secondary)]">
                        {pattern.support.summary}
                      </p>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="space-y-2 text-xs leading-5 text-[var(--color-text-secondary)]">
                      <p>
                        <span className="font-semibold text-[var(--color-text-primary)]">Use:</span>{" "}
                        {pattern.when_to_use ?? "—"}
                      </p>
                      <p>
                        <span className="font-semibold text-[var(--color-text-primary)]">Avoid:</span>{" "}
                        {pattern.when_not_to_use ?? "—"}
                      </p>
                      <p>
                        <span className="font-semibold text-[var(--color-text-primary)]">Business value:</span>{" "}
                        {pattern.business_value ?? "—"}
                      </p>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    {pattern.is_system ? (
                      <span className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface-3)] px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-[var(--color-text-secondary)]">
                        <Lock className="h-3.5 w-3.5" />
                        System
                      </span>
                    ) : (
                      <span className="inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-emerald-700">
                        Custom
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-wrap items-center gap-3">
                      <button
                        type="button"
                        onClick={() => {
                          setShowCreate(false);
                          setEditingPattern(pattern);
                          setError("");
                        }}
                        className="inline-flex items-center gap-2 text-sm font-medium text-[var(--color-accent)] hover:text-[var(--color-accent-hover)]"
                      >
                        <Pencil className="h-4 w-4" />
                        Edit
                      </button>
                      {!pattern.is_system ? (
                        <button
                          type="button"
                          onClick={() => {
                            setDeletingPattern(pattern);
                            setError("");
                          }}
                          className="inline-flex items-center gap-2 text-sm font-medium text-rose-700 hover:text-rose-500"
                        >
                          <Trash2 className="h-4 w-4" />
                          Delete
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>

      <AdminConfirmDelete
        open={deletingPattern !== null}
        title={
          deletingPattern
            ? `Delete pattern ${deletingPattern.pattern_id} — ${deletingPattern.name}?`
            : "Delete pattern?"
        }
        description="This cannot be undone."
        onConfirm={handleDelete}
        onCancel={() => setDeletingPattern(null)}
        isLoading={deleting}
      />
    </div>
  );
}
