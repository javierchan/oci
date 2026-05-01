"use client";

/* Assumption version governance page with clone-and-create and default promotion flows. */

import Link from "next/link";
import { Suspense, useEffect, useMemo, useState } from "react";
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

function AdminAssumptionsClient(): JSX.Element {
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
    <div className="console-page">
      <section className="console-hero flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
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

      <section className="space-y-4">
        {loading ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <article key={index} className="app-card p-5">
                <div className="skeleton h-5 w-28" />
                <div className="mt-4 skeleton h-8 w-20" />
                <div className="mt-4 skeleton h-16 w-full" />
              </article>
            ))}
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {assumptions.map((assumption) => (
              <article
                key={assumption.id}
                className={[
                  "app-card flex min-h-[13rem] flex-col p-5 transition hover:-translate-y-0.5 hover:border-[var(--color-accent)] hover:shadow-md",
                  assumption.is_default ? "border-emerald-200 bg-emerald-50/35 dark:border-emerald-900 dark:bg-emerald-950/15" : "",
                ].join(" ")}
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="app-label">Assumption Set</p>
                    <h2 className="mt-2 font-mono text-3xl font-semibold tracking-tight text-[var(--color-text-primary)]">
                      {assumption.version}
                    </h2>
                  </div>
                  {assumption.is_default ? (
                    <span className="inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-300">
                      Default
                    </span>
                  ) : (
                    <span className="app-theme-chip">Versioned</span>
                  )}
                </div>
                <p className="mt-4 text-sm leading-6 text-[var(--color-text-secondary)]">
                  Created {formatDate(assumption.created_at)}. Clone or inspect this immutable set before changing shared volumetry behavior.
                </p>
                <div className="mt-auto flex flex-wrap items-center gap-3 pt-5">
                  <Link
                    href={`/admin/assumptions/${assumption.version}`}
                    className="app-button-secondary px-4 py-2 text-sm"
                  >
                    View Details
                  </Link>
                  {!assumption.is_default ? (
                    <button
                      type="button"
                      onClick={() => {
                        void handleSetDefault(assumption.version);
                      }}
                      disabled={saving}
                      className="rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-700 transition hover:bg-emerald-100 disabled:cursor-not-allowed disabled:text-[var(--color-text-muted)]"
                    >
                      Set Default
                    </button>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

export default function AdminAssumptionsPage(): JSX.Element {
  return (
    <Suspense
      fallback={
        <section className="app-card p-6">
          <p className="app-kicker">Admin Governance</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">
            Assumptions
          </h1>
          <p className="mt-3 text-sm text-[var(--color-text-secondary)]">Loading assumption governance…</p>
        </section>
      }
    >
      <AdminAssumptionsClient />
    </Suspense>
  );
}
