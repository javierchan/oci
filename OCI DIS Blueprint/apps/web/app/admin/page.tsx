/* Admin governance hub with entry points for patterns, dictionaries, and assumptions. */

import Link from "next/link";
import { BookOpen, Database, FlaskConical, Layers3 } from "lucide-react";

import { Breadcrumb } from "@/components/breadcrumb";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";

export default async function AdminHubPage(): Promise<JSX.Element> {
  const [patterns, categories, assumptions, syntheticJobs] = await Promise.all([
    api.listPatterns(),
    api.listDictionaryCategories(),
    api.listAssumptions(),
    api.listSyntheticJobs({ limit: 1 }).catch(() => ({ jobs: [], total: 0 })),
  ]);
  const dictionaries = await Promise.all(
    categories.categories.map((category) => api.listDictionaryOptions(category.category)),
  );
  const defaultAssumption = assumptions.assumption_sets.find((item) => item.is_default);
  const latestPatternUpdate = patterns.patterns
    .map((pattern) => pattern.updated_at)
    .sort()
    .at(-1);
  const latestDictionaryUpdate = dictionaries
    .flatMap((dictionary) => dictionary.options.map((option) => option.updated_at))
    .filter((value): value is string => Boolean(value))
    .sort()
    .at(-1);
  const latestAssumptionUpdate = assumptions.assumption_sets
    .map((assumption) => assumption.updated_at ?? assumption.created_at)
    .sort()
    .at(-1);
  const latestSyntheticUpdate = syntheticJobs.jobs[0]?.updated_at;

  return (
    <div className="console-page">
      <section className="console-hero flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
        <p className="app-kicker">Admin Governance</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">Library</h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
            Source of truth for patterns, dictionaries, assumptions, and deterministic synthetic validation.
        </p>
        </div>
        <div className="flex flex-col items-start gap-3 lg:items-end">
          <div className="flex flex-wrap items-center gap-2">
            <span className="app-status-chip active">Published {defaultAssumption?.version ?? "v1.0.0"}</span>
            <span className="app-theme-chip">Workbook governed</span>
          </div>
          <Breadcrumb items={[{ label: "Home", href: "/projects" }, { label: "Admin" }]} />
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-4">
        <Link
          href="/admin/patterns"
          className="app-card p-6 transition hover:-translate-y-0.5 hover:shadow-md"
        >
          <div className="flex items-start justify-between gap-3">
            <p className="app-label">OIC Patterns</p>
            <span className="rounded-lg bg-[var(--color-surface-2)] p-2 text-[var(--color-accent)]">
              <Layers3 className="h-4 w-4" />
            </span>
          </div>
          <p className="mt-4 text-4xl font-semibold text-[var(--color-text-primary)]">{patterns.total}</p>
          <p className="mt-3 text-sm text-[var(--color-text-secondary)]">Seeded and custom integration patterns.</p>
          <p className="mt-3 text-xs text-[var(--color-text-muted)]">
            Last modified: {latestPatternUpdate ? formatDate(latestPatternUpdate) : "—"}
          </p>
          <span className="mt-5 inline-flex text-sm font-semibold text-[var(--color-accent)]">Manage</span>
        </Link>

        <Link
          href="/admin/dictionaries"
          className="app-card p-6 transition hover:-translate-y-0.5 hover:shadow-md"
        >
          <div className="flex items-start justify-between gap-3">
            <p className="app-label">Dictionaries</p>
            <span className="rounded-lg bg-[var(--color-surface-2)] p-2 text-[var(--color-accent)]">
              <Database className="h-4 w-4" />
            </span>
          </div>
          <p className="mt-4 text-4xl font-semibold text-[var(--color-text-primary)]">{categories.categories.length}</p>
          <p className="mt-3 text-sm text-[var(--color-text-secondary)]">Governed option sets used throughout the catalog.</p>
          <p className="mt-3 text-xs text-[var(--color-text-muted)]">
            Last modified: {latestDictionaryUpdate ? formatDate(latestDictionaryUpdate) : "—"}
          </p>
          <span className="mt-5 inline-flex text-sm font-semibold text-[var(--color-accent)]">Manage</span>
        </Link>

        <Link
          href="/admin/assumptions"
          className="app-card p-6 transition hover:-translate-y-0.5 hover:shadow-md"
        >
          <div className="flex items-start justify-between gap-3">
            <p className="app-label">Assumptions</p>
            <span className="rounded-lg bg-[var(--color-surface-2)] p-2 text-[var(--color-accent)]">
              <BookOpen className="h-4 w-4" />
            </span>
          </div>
          <p className="mt-4 text-4xl font-semibold text-[var(--color-text-primary)]">{assumptions.assumption_sets.length}</p>
          <p className="mt-3 text-sm text-[var(--color-text-secondary)]">
            Active default version: {defaultAssumption?.version ?? "None"}
          </p>
          <p className="mt-3 text-xs text-[var(--color-text-muted)]">
            Last modified: {latestAssumptionUpdate ? formatDate(latestAssumptionUpdate) : "—"}
          </p>
          <span className="mt-5 inline-flex text-sm font-semibold text-[var(--color-accent)]">Manage</span>
        </Link>

        <Link
          href="/admin/synthetic"
          className="app-card p-6 transition hover:-translate-y-0.5 hover:shadow-md"
        >
          <div className="flex items-start justify-between gap-3">
            <p className="app-label">Synthetic Lab</p>
            <span className="rounded-lg bg-[var(--color-surface-2)] p-2 text-[var(--color-accent)]">
              <FlaskConical className="h-4 w-4" />
            </span>
          </div>
          <p className="mt-4 text-4xl font-semibold text-[var(--color-text-primary)]">{syntheticJobs.total}</p>
          <p className="mt-3 text-sm text-[var(--color-text-secondary)]">Tracked deterministic generation jobs.</p>
          <p className="mt-3 text-xs text-[var(--color-text-muted)]">
            Latest activity: {latestSyntheticUpdate ? formatDate(latestSyntheticUpdate) : "No synthetic jobs yet."}
          </p>
          <span className="mt-5 inline-flex text-sm font-semibold text-[var(--color-accent)]">
            Open Lab
          </span>
        </Link>
      </section>

      <section className="app-card border-[var(--color-qa-revisar-border)] bg-[var(--color-qa-revisar-bg)] p-5">
        <p className="app-label text-[var(--color-qa-revisar-text)]">Governance impact</p>
        <p className="mt-2 text-sm leading-6 text-[var(--color-qa-revisar-text)]">
          Changes here affect all projects. System patterns seeded from the workbook can be edited but not deleted.
          Dictionary and assumption changes take effect on the next recalculation.
        </p>
      </section>
    </div>
  );
}
