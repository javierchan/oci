"use client";

/* Assumption version governance page with clone-and-create and default promotion flows. */

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { AdminAssumptionForm } from "@/components/admin-assumption-form";
import { Breadcrumb } from "@/components/breadcrumb";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { AssumptionSet, AssumptionSetCreate } from "@/lib/types";

function bumpVersion(version: string): string {
  const parts = version.split(".");
  const last = Number(parts[parts.length - 1] ?? "0");
  if (Number.isNaN(last)) {
    return `${version}.1`;
  }
  parts[parts.length - 1] = String(last + 1);
  return parts.join(".");
}

export default function AdminAssumptionsPage(): JSX.Element {
  const searchParams = useSearchParams();
  const cloneVersion = searchParams.get("clone");
  const [assumptions, setAssumptions] = useState<AssumptionSet[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [showCreate, setShowCreate] = useState<boolean>(false);

  async function load(): Promise<void> {
    setLoading(true);
    try {
      const response = await api.listAssumptions();
      setAssumptions(response.assumption_sets);
      setError("");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to load assumptions.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    if (cloneVersion) {
      setShowCreate(true);
    }
  }, [cloneVersion]);

  const defaultAssumption = useMemo(
    () => assumptions.find((assumption) => assumption.is_default) ?? assumptions[0] ?? null,
    [assumptions],
  );
  const clonedAssumption = useMemo(
    () =>
      assumptions.find((assumption) => assumption.version === cloneVersion) ??
      defaultAssumption,
    [assumptions, cloneVersion, defaultAssumption],
  );
  const suggestedVersion = useMemo(
    () => bumpVersion(clonedAssumption?.version ?? defaultAssumption?.version ?? "1.0.0"),
    [clonedAssumption, defaultAssumption],
  );

  async function handleCreate(body: AssumptionSetCreate): Promise<void> {
    setSaving(true);
    try {
      await api.createAssumption(body);
      setShowCreate(false);
      await load();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to create assumption set.");
    } finally {
      setSaving(false);
    }
  }

  async function handleSetDefault(version: string): Promise<void> {
    setSaving(true);
    try {
      await api.setDefaultAssumption(version);
      await load();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to set default version.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <section className="app-card flex flex-col gap-4 p-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="app-kicker">Admin Governance</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">Assumptions</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
            Version the shared volumetry assumptions used across recalculations and exports.
          </p>
          <div className="mt-4">
            <Breadcrumb
              items={[
                { label: "Home", href: "/projects" },
                { label: "Admin", href: "/admin" },
                { label: "Assumptions" },
              ]}
            />
          </div>
        </div>
        <button
          type="button"
          onClick={() => {
            setShowCreate((current) => !current);
            setError("");
          }}
          className="app-button-primary"
        >
          {showCreate ? "Hide Form" : "New Version"}
        </button>
      </section>

      {showCreate ? (
        <AdminAssumptionForm
          initialValue={clonedAssumption}
          suggestedVersion={suggestedVersion}
          isLoading={saving}
          error={error}
          onSubmit={handleCreate}
          onCancel={() => {
            setShowCreate(false);
            setError("");
          }}
        />
      ) : null}

      {error && !showCreate ? (
        <p className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </p>
      ) : null}

      <section className="app-table-shell">
        <table className="min-w-full divide-y divide-[var(--color-table-border)] text-left">
          <thead className="app-table-header">
            <tr>
              <th className="px-6 py-4 font-medium">Version</th>
              <th className="px-6 py-4 font-medium">Created</th>
              <th className="px-6 py-4 font-medium">Is Default</th>
              <th className="px-6 py-4 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-table-border)] text-sm">
            {loading ? (
              <tr>
                <td className="px-6 py-8 text-[var(--color-text-secondary)]" colSpan={4}>
                  Loading versions…
                </td>
              </tr>
            ) : (
              assumptions.map((assumption) => (
                <tr
                  key={assumption.id}
                  className={[
                    "app-table-row",
                    assumption.is_default ? "bg-emerald-50/60 dark:bg-emerald-950/20" : "",
                  ].join(" ")}
                >
                  <td className="px-6 py-4 font-semibold text-[var(--color-text-primary)]">{assumption.version}</td>
                  <td className="px-6 py-4 text-[var(--color-text-secondary)]">{formatDate(assumption.created_at)}</td>
                  <td className="px-6 py-4">
                    {assumption.is_default ? (
                      <span className="inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-emerald-700">
                        Default
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-wrap items-center gap-3">
                      <Link
                        href={`/admin/assumptions/${assumption.version}`}
                          className="text-sm font-medium text-[var(--color-accent)] hover:text-[var(--color-accent-hover)]"
                      >
                        View
                      </Link>
                      {!assumption.is_default ? (
                        <button
                          type="button"
                          onClick={() => {
                            void handleSetDefault(assumption.version);
                          }}
                          disabled={saving}
                          className="text-sm font-medium text-emerald-700 hover:text-emerald-500 disabled:cursor-not-allowed disabled:text-[var(--color-text-muted)]"
                        >
                          Set as Default
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
    </div>
  );
}
