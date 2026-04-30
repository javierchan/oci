/* Admin governance hub with entry points for patterns, dictionaries, and assumptions. */

import Link from "next/link";

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
    <div className="space-y-8">
      <section className="app-card border-[var(--color-qa-revisar-border)] bg-[var(--color-qa-revisar-bg)] p-5">
        <p className="app-kicker">Admin Governance</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">Reference Data Control</h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
          Changes here affect all projects. System patterns seeded from the workbook cannot be deleted.
        </p>
        <div className="mt-3 flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-300">
          <span className="mt-0.5">⚠️</span>
          <span>
            Changes here affect <strong>all projects</strong>. System patterns (seeded from the workbook) can be
            edited but not deleted. Dictionary and assumption changes take effect on the next recalculation.
          </span>
        </div>
        <div className="mt-4">
          <Breadcrumb items={[{ label: "Home", href: "/projects" }, { label: "Admin" }]} />
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <Link
          href="/admin/patterns"
          className="app-card p-6 transition hover:-translate-y-0.5 hover:shadow-md"
        >
          <p className="app-label">OIC Patterns</p>
          <p className="mt-4 text-4xl font-semibold text-[var(--color-text-primary)]">{patterns.total}</p>
          <p className="mt-3 text-sm text-[var(--color-text-secondary)]">Seeded and custom integration patterns.</p>
          <p className="mt-3 text-xs text-[var(--color-text-muted)]">
            Last modified: {latestPatternUpdate ? formatDate(latestPatternUpdate) : "—"}
          </p>
          <span className="mt-5 inline-flex text-sm font-semibold text-[var(--color-accent)]">Manage →</span>
        </Link>

        <Link
          href="/admin/dictionaries"
          className="app-card p-6 transition hover:-translate-y-0.5 hover:shadow-md"
        >
          <p className="app-label">Dictionaries</p>
          <p className="mt-4 text-4xl font-semibold text-[var(--color-text-primary)]">{categories.categories.length}</p>
          <p className="mt-3 text-sm text-[var(--color-text-secondary)]">Governed option sets used throughout the catalog.</p>
          <p className="mt-3 text-xs text-[var(--color-text-muted)]">
            Last modified: {latestDictionaryUpdate ? formatDate(latestDictionaryUpdate) : "—"}
          </p>
          <span className="mt-5 inline-flex text-sm font-semibold text-[var(--color-accent)]">Manage →</span>
        </Link>

        <Link
          href="/admin/assumptions"
          className="app-card p-6 transition hover:-translate-y-0.5 hover:shadow-md"
        >
          <p className="app-label">Assumptions</p>
          <p className="mt-4 text-4xl font-semibold text-[var(--color-text-primary)]">{assumptions.assumption_sets.length}</p>
          <p className="mt-3 text-sm text-[var(--color-text-secondary)]">
            Active default version: {defaultAssumption?.version ?? "None"}
          </p>
          <p className="mt-3 text-xs text-[var(--color-text-muted)]">
            Last modified: {latestAssumptionUpdate ? formatDate(latestAssumptionUpdate) : "—"}
          </p>
          <span className="mt-5 inline-flex text-sm font-semibold text-[var(--color-accent)]">Manage →</span>
        </Link>
      </section>

      <section className="app-card p-6">
        <p className="app-label">Synthetic Lab</p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">Governed Generation Control</h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
          Submit deterministic synthetic-generation jobs, monitor progress, inspect validation artifacts, and clean up
          synthetic projects from the dedicated admin surface.
        </p>
        <p className="mt-3 text-sm leading-6 text-[var(--color-text-secondary)]">
          Latest activity: {latestSyntheticUpdate ? formatDate(latestSyntheticUpdate) : "No synthetic jobs yet."}
        </p>
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <Link href="/admin/synthetic" className="app-button-primary">
            Open Synthetic Lab
          </Link>
          <Link href="/projects" className="app-button-secondary">
            Open Projects
          </Link>
          <span className="app-theme-chip inline-flex min-h-12 items-center justify-center px-4 text-center leading-none">
            {syntheticJobs.total} tracked job{syntheticJobs.total === 1 ? "" : "s"}
          </span>
        </div>
      </section>
    </div>
  );
}
