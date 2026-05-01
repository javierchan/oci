"use client";

/* Pattern governance page for create, edit, and delete flows. */

import Link from "next/link";
import { Eye, Lock, Pencil, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

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
  const [viewingPattern, setViewingPattern] = useState<PatternDefinition | null>(null);
  const [catalogProjectId, setCatalogProjectId] = useState<string | null>(null);
  const [lastCreatedPatternId, setLastCreatedPatternId] = useState<string>("");
  const formMode = showCreate ? "create" : editingPattern ? "edit" : null;
  const sortedPatterns = useMemo(
    () =>
      [...patterns].sort((left, right) =>
        left.pattern_id.localeCompare(right.pattern_id, undefined, { numeric: true }),
      ),
    [patterns],
  );

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
      setToolOptions(
        Array.from(
          new Set([...toolList.options, ...overlayList.options].map((option) => option.value)),
        ),
      );
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
    <div className="console-page">
      <section className="console-hero flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
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

      {formMode ? (
        <section className="app-card p-5">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="app-label">Directory Collapsed</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">
                Pattern list hidden while you {formMode === "create" ? "create" : "edit"} a pattern
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--color-text-secondary)]">
                Keeping the reference table out of the way reduces scroll fatigue and keeps the active governance form visible.
              </p>
            </div>
            <div className="app-card-muted px-4 py-3 text-sm text-[var(--color-text-secondary)]">
              {patterns.length} patterns loaded
            </div>
          </div>
        </section>
      ) : (
        <section className="space-y-6">
          {loading ? (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {Array.from({ length: 6 }).map((_, index) => (
                <article key={index} className="app-card p-5">
                  <div className="skeleton h-5 w-24" />
                  <div className="mt-4 skeleton h-6 w-3/4" />
                  <div className="mt-3 skeleton h-16 w-full" />
                  <div className="mt-5 skeleton h-9 w-32" />
                </article>
              ))}
            </div>
          ) : (
            <>
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <p className="app-label">Pattern Library</p>
                  <h2 className="mt-1 text-2xl font-semibold text-[var(--color-text-primary)]">
                    Governed pattern cards
                  </h2>
                </div>
                <span className="app-theme-chip">{sortedPatterns.length} patterns</span>
              </div>

              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {sortedPatterns.map((pattern) => (
                  <article
                    key={pattern.pattern_id}
                    className="app-card flex min-h-[18rem] flex-col p-5 transition hover:-translate-y-0.5 hover:border-[var(--color-accent)] hover:shadow-md"
                  >
                    <div className="flex items-start gap-3">
                      <span className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-3)] px-3 py-2 font-mono text-sm font-bold text-[var(--color-text-primary)]">
                        {pattern.pattern_id}
                      </span>
                      <div className="min-w-0 flex-1">
                        <h3 className="text-base font-semibold text-[var(--color-text-primary)]">
                          {pattern.name}
                        </h3>
                        <div className="mt-2 flex flex-wrap gap-2">
                          <span className="app-theme-chip">{pattern.category}</span>
                          <PatternSupportBadge support={pattern.support} />
                          {pattern.is_system ? (
                            <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-surface-3)] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--color-text-secondary)]">
                              <Lock className="h-3 w-3" />
                              System
                            </span>
                          ) : (
                            <span className="inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-300">
                              Custom
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    <p className="mt-4 line-clamp-3 text-sm leading-6 text-[var(--color-text-secondary)]">
                      {pattern.description ?? pattern.support.summary}
                    </p>

                    {pattern.oci_components ? (
                      <p className="mt-3 line-clamp-2 rounded-2xl bg-[var(--color-surface-2)] px-3 py-2 text-xs leading-5 text-[var(--color-text-muted)]">
                        {pattern.oci_components}
                      </p>
                    ) : null}

                    <div className="mt-4 grid gap-3 text-xs md:grid-cols-2">
                      <div>
                        <p className="app-label">When to use</p>
                        <p className="mt-1 line-clamp-3 text-[var(--color-text-secondary)]">
                          {pattern.when_to_use ?? "No usage guidance documented."}
                        </p>
                      </div>
                      <div>
                        <p className="app-label">Avoid</p>
                        <p className="mt-1 line-clamp-3 text-[var(--color-text-secondary)]">
                          {pattern.when_not_to_use ?? "No anti-pattern guidance documented."}
                        </p>
                      </div>
                    </div>

                    <div className="mt-auto flex flex-wrap items-center gap-3 pt-5">
                      <button
                        type="button"
                        onClick={() => setViewingPattern(pattern)}
                        className="app-button-secondary inline-flex items-center gap-2 px-4 py-2 text-sm"
                      >
                        <Eye className="h-4 w-4" />
                        View details
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setShowCreate(false);
                          setEditingPattern(pattern);
                          setError("");
                        }}
                        className="app-button-secondary inline-flex items-center gap-2 px-4 py-2 text-sm"
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
                          className="inline-flex items-center gap-2 rounded-full border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-700 transition hover:bg-rose-100"
                        >
                          <Trash2 className="h-4 w-4" />
                          Delete
                        </button>
                      ) : null}
                    </div>
                  </article>
                ))}
              </div>
            </>
          )}
        </section>
      )}

      {viewingPattern ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="pattern-detail-title"
        >
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={() => setViewingPattern(null)}
          />
          <article className="relative app-card max-h-[88vh] w-full max-w-4xl overflow-y-auto p-6 shadow-2xl">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="app-label">Pattern Detail</p>
                <h2
                  id="pattern-detail-title"
                  className="mt-2 text-3xl font-semibold tracking-tight text-[var(--color-text-primary)]"
                >
                  {viewingPattern.pattern_id} · {viewingPattern.name}
                </h2>
                <div className="mt-3 flex flex-wrap gap-2">
                  <span className="app-theme-chip">{viewingPattern.category}</span>
                  <PatternSupportBadge support={viewingPattern.support} />
                </div>
              </div>
              <button
                type="button"
                onClick={() => setViewingPattern(null)}
                className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface-2)] p-2 text-[var(--color-text-secondary)] transition hover:text-[var(--color-text-primary)]"
                aria-label="Close pattern details"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-2">
              <section className="md:col-span-2 rounded-[1.5rem] border border-[var(--color-border)] bg-[var(--color-surface-2)] p-5">
                <p className="app-label">Description</p>
                <p className="mt-2 whitespace-pre-line text-sm leading-6 text-[var(--color-text-secondary)]">
                  {viewingPattern.description ?? viewingPattern.support.summary}
                </p>
              </section>
              <section className="rounded-[1.5rem] border border-[var(--color-border)] bg-[var(--color-surface-2)] p-5">
                <p className="app-label">When to Use</p>
                <p className="mt-2 whitespace-pre-line text-sm leading-6 text-[var(--color-text-secondary)]">
                  {viewingPattern.when_to_use ?? "No usage guidance documented."}
                </p>
              </section>
              <section className="rounded-[1.5rem] border border-[var(--color-border)] bg-[var(--color-surface-2)] p-5">
                <p className="app-label">Avoid</p>
                <p className="mt-2 whitespace-pre-line text-sm leading-6 text-[var(--color-text-secondary)]">
                  {viewingPattern.when_not_to_use ?? "No anti-pattern guidance documented."}
                </p>
              </section>
              <section className="rounded-[1.5rem] border border-[var(--color-border)] bg-[var(--color-surface-2)] p-5">
                <p className="app-label">OCI Components</p>
                <p className="mt-2 whitespace-pre-line text-sm leading-6 text-[var(--color-text-secondary)]">
                  {viewingPattern.oci_components ?? "No component guidance documented."}
                </p>
              </section>
              <section className="rounded-[1.5rem] border border-[var(--color-border)] bg-[var(--color-surface-2)] p-5">
                <p className="app-label">Technical Flow</p>
                <p className="mt-2 whitespace-pre-line text-sm leading-6 text-[var(--color-text-secondary)]">
                  {viewingPattern.technical_flow ?? "No technical flow documented."}
                </p>
              </section>
              <section className="md:col-span-2 rounded-[1.5rem] border border-[var(--color-border)] bg-[var(--color-surface-2)] p-5">
                <p className="app-label">Business Value</p>
                <p className="mt-2 whitespace-pre-line text-sm leading-6 text-[var(--color-text-secondary)]">
                  {viewingPattern.business_value ?? "No business-value guidance documented."}
                </p>
              </section>
            </div>
          </article>
        </div>
      ) : null}

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
