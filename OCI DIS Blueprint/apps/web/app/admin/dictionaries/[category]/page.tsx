"use client";

/* Category-scoped dictionary governance page with create, edit, and deactivate actions. */

import { Pencil, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Breadcrumb } from "@/components/breadcrumb";
import { AdminConfirmDelete } from "@/components/admin-confirm-delete";
import { AdminDictionaryForm } from "@/components/admin-dictionary-form";
import { api } from "@/lib/api";
import type { DictOption, DictOptionCreate } from "@/lib/types";

type AdminDictionaryCategoryPageProps = {
  params: {
    category: string;
  };
};

export default function AdminDictionaryCategoryPage({
  params,
}: AdminDictionaryCategoryPageProps): JSX.Element {
  const category = params.category.toUpperCase();
  const [options, setOptions] = useState<DictOption[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [deleting, setDeleting] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [showCreate, setShowCreate] = useState<boolean>(false);
  const [editingOption, setEditingOption] = useState<DictOption | null>(null);
  const [deletingOption, setDeletingOption] = useState<DictOption | null>(null);

  async function load(): Promise<void> {
    setLoading(true);
    try {
      const response = await api.listDictionaryOptions(category);
      setOptions(
        response.options.map((option) => ({
          id: option.id,
          category: option.category,
          code: option.code,
          value: option.value,
          description: option.description,
          executions_per_day: option.executions_per_day,
        })),
      );
      setError("");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to load options.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [category]);

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

  return (
    <div className="space-y-6">
      <section className="app-card flex flex-col gap-4 p-6 lg:flex-row lg:items-end lg:justify-between">
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

      <section className="app-table-shell">
        <table className="min-w-full divide-y divide-[var(--color-table-border)] text-left">
          <thead className="app-table-header">
            <tr>
              <th className="px-6 py-4 font-medium">Code</th>
              <th className="px-6 py-4 font-medium">Value</th>
              <th className="px-6 py-4 font-medium">Description</th>
              <th className="px-6 py-4 font-medium">Executions/Day</th>
              <th className="px-6 py-4 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-table-border)] text-sm">
            {loading ? (
              <tr>
                <td className="px-6 py-8 text-[var(--color-text-secondary)]" colSpan={5}>
                  Loading options…
                </td>
              </tr>
            ) : (
              options.map((option) => (
                <tr key={option.id} className="app-table-row">
                  <td className="px-6 py-4 font-medium text-[var(--color-text-primary)]">{option.code || "—"}</td>
                  <td className="px-6 py-4 text-[var(--color-text-primary)]">{option.value}</td>
                  <td className="px-6 py-4 text-[var(--color-text-secondary)]">{option.description || "—"}</td>
                  <td className="px-6 py-4 text-[var(--color-text-secondary)]">
                    {category === "FREQUENCY" ? option.executions_per_day ?? "—" : "—"}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-wrap items-center gap-3">
                      <button
                        type="button"
                        onClick={() => {
                          setShowCreate(false);
                          setEditingOption(option);
                          setError("");
                        }}
                        className="inline-flex items-center gap-2 text-sm font-medium text-[var(--color-accent)] hover:text-[var(--color-accent-hover)]"
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
                        className="inline-flex items-center gap-2 text-sm font-medium text-rose-700 hover:text-rose-500"
                      >
                        <Trash2 className="h-4 w-4" />
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
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
