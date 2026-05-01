"use client";

/* Category-scoped dictionary governance page with create, edit, and deactivate actions. */

import { Activity, CheckCircle2, Hash, Pencil, Trash2 } from "lucide-react";
import { use, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Breadcrumb } from "@/components/breadcrumb";
import { AdminConfirmDelete } from "@/components/admin-confirm-delete";
import { AdminDictionaryForm } from "@/components/admin-dictionary-form";
import { api } from "@/lib/api";
import { displayGovernedText, displayUiValue } from "@/lib/format";
import type { DictOption, DictOptionCreate } from "@/lib/types";

type AdminDictionaryCategoryPageProps = {
  params: Promise<{
    category: string;
  }>;
};

function formatOptional(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return String(value);
}

function normalizeDictionaryCategory(value: string): string {
  const normalized = value.toUpperCase();
  return normalized === "TOOL" ? "TOOLS" : normalized;
}

export default function AdminDictionaryCategoryPage({
  params,
}: AdminDictionaryCategoryPageProps): JSX.Element {
  const { category: rawCategory } = use(params);
  const router = useRouter();
  const category = normalizeDictionaryCategory(rawCategory);
  const [options, setOptions] = useState<DictOption[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [deleting, setDeleting] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [showCreate, setShowCreate] = useState<boolean>(false);
  const [showInactive, setShowInactive] = useState<boolean>(false);
  const [editingOption, setEditingOption] = useState<DictOption | null>(null);
  const [deletingOption, setDeletingOption] = useState<DictOption | null>(null);

  const load = useCallback(async (): Promise<void> => {
    setLoading(true);
    try {
      const response = await api.listDictionaryOptions(category, true);
      setOptions(
        response.options.map((option) => ({
          id: option.id,
          category: option.category,
          code: option.code,
          value: option.value,
          description: option.description,
          executions_per_day: option.executions_per_day,
          is_volumetric: option.is_volumetric,
          sort_order: option.sort_order,
          is_active: option.is_active,
          version: option.version,
          updated_at: option.updated_at,
        })),
      );
      setError("");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to load options.");
    } finally {
      setLoading(false);
    }
  }, [category]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (rawCategory.toUpperCase() !== category) {
      router.replace(`/admin/dictionaries/${category}`);
    }
  }, [category, rawCategory, router]);

  async function handleCreate(value: DictOptionCreate): Promise<void> {
    setSaving(true);
    try {
      await api.createDictOption(category, value);
      setShowCreate(false);
      await load();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to create option.");
    } finally {
      setSaving(false);
    }
  }

  async function handleUpdate(value: DictOptionCreate): Promise<void> {
    if (!editingOption) {
      return;
    }
    setSaving(true);
    try {
      await api.updateDictOption(category, editingOption.id, value);
      setEditingOption(null);
      await load();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to update option.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(): Promise<void> {
    if (!deletingOption) {
      return;
    }
    setDeleting(true);
    try {
      await api.deleteDictOption(category, deletingOption.id);
      setDeletingOption(null);
      await load();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to delete option.");
    } finally {
      setDeleting(false);
    }
  }

  const activeOptions = options.filter((option) => option.is_active).length;
  const volumetricOptions = options.filter((option) => option.is_volumetric).length;
  const visibleOptions = showInactive ? options : options.filter((option) => option.is_active);
  const latestVersion =
    options
      .map((option) => option.version)
      .filter((value): value is string => Boolean(value))
      .sort()
      .at(-1) ?? "—";

  return (
    <div className="console-page">
      <section className="console-hero flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="app-kicker">Admin Governance</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">{category}</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
            Add or maintain the options available to governed workflows in this category.
          </p>
          <div className="mt-4">
            <Breadcrumb
              items={[
                { label: "Home", href: "/projects" },
                { label: "Admin", href: "/admin" },
                { label: "Dictionaries", href: "/admin/dictionaries" },
                { label: category },
              ]}
            />
          </div>
        </div>
        <button
          type="button"
          onClick={() => {
            setShowCreate(true);
            setEditingOption(null);
            setError("");
          }}
          className="app-button-primary"
        >
          New Option
        </button>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <article className="app-card p-5">
          <div className="flex items-center justify-between gap-3">
            <p className="app-label">Total Options</p>
            <span className="rounded-lg bg-[var(--color-surface-2)] p-2 text-[var(--color-accent)]">
              <Hash className="h-4 w-4" />
            </span>
          </div>
          <p className="mt-3 text-3xl font-semibold text-[var(--color-text-primary)]">{options.length}</p>
        </article>
        <article className="app-card p-5">
          <div className="flex items-center justify-between gap-3">
            <p className="app-label">Active</p>
            <span className="rounded-lg bg-[var(--color-surface-2)] p-2 text-emerald-600 dark:text-emerald-300">
              <CheckCircle2 className="h-4 w-4" />
            </span>
          </div>
          <p className="mt-3 text-3xl font-semibold text-[var(--color-text-primary)]">{activeOptions}</p>
        </article>
        <article className="app-card p-5">
          <div className="flex items-center justify-between gap-3">
            <p className="app-label">Volumetric</p>
            <span className="rounded-lg bg-[var(--color-surface-2)] p-2 text-[var(--color-accent)]">
              <Activity className="h-4 w-4" />
            </span>
          </div>
          <p className="mt-3 text-3xl font-semibold text-[var(--color-text-primary)]">{volumetricOptions}</p>
        </article>
        <article className="app-card p-5">
          <p className="app-label">Latest Version</p>
          <p className="mt-3 font-mono text-3xl font-semibold text-[var(--color-text-primary)]">{latestVersion}</p>
        </article>
      </section>

      {showCreate ? (
        <AdminDictionaryForm
          category={category}
          isLoading={saving}
          error={error}
          onSubmit={handleCreate}
          onCancel={() => {
            setShowCreate(false);
            setError("");
          }}
        />
      ) : null}

      {editingOption ? (
        <AdminDictionaryForm
          category={category}
          initialValue={editingOption}
          isLoading={saving}
          error={error}
          onSubmit={handleUpdate}
          onCancel={() => {
            setEditingOption(null);
            setError("");
          }}
        />
      ) : null}

      {error && !showCreate && !editingOption ? (
        <p className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </p>
      ) : null}

      <section className="app-card overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--color-border)] px-5 py-4">
          <div>
            <p className="app-label">Governed Entries</p>
            <h2 className="mt-1 text-2xl font-semibold text-[var(--color-text-primary)]">
              {category} dictionary options
            </h2>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setShowInactive((current) => !current)}
              className="app-button-secondary px-3 py-2 text-xs"
            >
              {showInactive ? "Hide Inactive" : "Show Inactive"}
            </button>
            <span className="app-theme-chip">
              {visibleOptions.length} visible · {options.length} total
            </span>
          </div>
        </div>

        {loading ? (
          <div className="space-y-3 p-5">
            {Array.from({ length: 5 }).map((_, index) => (
              <div key={index} className="skeleton h-20 w-full" />
            ))}
          </div>
        ) : visibleOptions.length === 0 ? (
          <div className="px-5 py-12 text-center text-sm text-[var(--color-text-secondary)]">
            No active options exist for this dictionary category.
          </div>
        ) : (
          <div className="divide-y divide-[var(--color-border)]">
            {visibleOptions.map((option) => (
              <article
                key={option.id}
                className="grid gap-4 px-5 py-4 transition hover:bg-[var(--color-table-row-hover)] lg:grid-cols-[11rem_minmax(0,1fr)_18rem_auto] lg:items-center"
              >
                <div>
                  <p className="app-label">Code</p>
                  <p className="mt-1 font-mono text-sm font-semibold text-[var(--color-text-primary)]">
                    {option.code || "Uncoded"}
                  </p>
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="truncate text-base font-semibold text-[var(--color-text-primary)]">
                      {displayUiValue(option.value)}
                    </h3>
                    <span
                      className={[
                        "inline-flex rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em]",
                        option.is_active
                          ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-300"
                          : "border-[var(--color-border)] bg-[var(--color-surface-2)] text-[var(--color-text-muted)]",
                      ].join(" ")}
                    >
                      {option.is_active ? "Active" : "Inactive"}
                    </span>
                  </div>
                  <p className="mt-2 line-clamp-2 text-sm leading-6 text-[var(--color-text-secondary)]">
                    {option.description ? displayGovernedText(option.description) : "No description provided."}
                  </p>
                </div>
                <dl className="grid grid-cols-3 gap-3 text-xs">
                  <div>
                    <dt className="app-label">Exec/Day</dt>
                    <dd className="mt-1 font-mono font-semibold text-[var(--color-text-primary)]">
                      {category === "FREQUENCY" ? formatOptional(option.executions_per_day) : "—"}
                    </dd>
                  </div>
                  <div>
                    <dt className="app-label">Volumetric</dt>
                    <dd className="mt-1 font-semibold text-[var(--color-text-primary)]">
                      {option.is_volumetric ? "Yes" : "No"}
                    </dd>
                  </div>
                  <div>
                    <dt className="app-label">Version</dt>
                    <dd className="mt-1 font-mono font-semibold text-[var(--color-text-primary)]">
                      {option.version ?? "—"}
                    </dd>
                  </div>
                </dl>
                <div className="flex flex-wrap items-center gap-2 lg:justify-end">
                  <button
                    type="button"
                    onClick={() => {
                      setShowCreate(false);
                      setEditingOption(option);
                      setError("");
                    }}
                    className="app-button-secondary inline-flex items-center gap-2 px-3 py-2 text-sm"
                  >
                    <Pencil className="h-4 w-4" />
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setDeletingOption(option);
                      setError("");
                    }}
                    className="inline-flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-700 transition hover:bg-rose-100 dark:border-rose-900 dark:bg-rose-950/30 dark:text-rose-300"
                  >
                    <Trash2 className="h-4 w-4" />
                    Delete
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <AdminConfirmDelete
        open={deletingOption !== null}
        title={deletingOption ? `Delete option ${deletingOption.value}?` : "Delete option?"}
        description="This option will be deactivated for future governance actions."
        onConfirm={handleDelete}
        onCancel={() => setDeletingOption(null)}
        isLoading={deleting}
      />
    </div>
  );
}
