/* Admin governance hub with entry points for patterns, dictionaries, and assumptions. */

import Link from "next/link";

import { Breadcrumb } from "@/components/breadcrumb";
import { api } from "@/lib/api";

export default async function AdminHubPage(): Promise<JSX.Element> {
  const [patterns, categories, assumptions] = await Promise.all([
    api.listPatterns(),
    api.listDictionaryCategories(),
    api.listAssumptions(),
  ]);
  const defaultAssumption = assumptions.assumption_sets.find((item) => item.is_default);

  return (
    <div className="space-y-8">
      <section className="app-card border-[var(--color-qa-revisar-border)] bg-[var(--color-qa-revisar-bg)] p-5">
        <p className="app-kicker">Admin Governance</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">Reference Data Control</h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
          Changes here affect all projects. System patterns seeded from the workbook cannot be deleted.
        </p>
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
          <span className="mt-5 inline-flex text-sm font-semibold text-[var(--color-accent)]">Manage →</span>
        </Link>

        <Link
          href="/admin/dictionaries"
          className="app-card p-6 transition hover:-translate-y-0.5 hover:shadow-md"
        >
          <p className="app-label">Dictionaries</p>
          <p className="mt-4 text-4xl font-semibold text-[var(--color-text-primary)]">{categories.categories.length}</p>
          <p className="mt-3 text-sm text-[var(--color-text-secondary)]">Governed option sets used throughout the catalog.</p>
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
          <span className="mt-5 inline-flex text-sm font-semibold text-[var(--color-accent)]">Manage →</span>
        </Link>
      </section>
    </div>
  );
}
