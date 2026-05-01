/* Dictionary governance overview page grouped by category. */

import Link from "next/link";
import { BookOpen, ChevronRight } from "lucide-react";

import { Breadcrumb } from "@/components/breadcrumb";
import { api } from "@/lib/api";

export default async function AdminDictionariesPage(): Promise<JSX.Element> {
  const categories = await api.listDictionaryCategories();
  const totalOptions = categories.categories.reduce((sum, category) => sum + category.option_count, 0);

  return (
    <div className="console-page">
      <section className="console-hero">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="app-kicker">Admin Governance</p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">Dictionaries</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
              Manage the governed dropdown values used across imports, capture, catalog editing, and QA.
            </p>
            <div className="mt-4">
              <Breadcrumb
                items={[
                  { label: "Home", href: "/projects" },
                  { label: "Admin", href: "/admin" },
                  { label: "Dictionaries" },
                ]}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:min-w-[18rem]">
            <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-3">
              <p className="app-label">Categories</p>
              <p className="mt-1 text-2xl font-semibold text-[var(--color-text-primary)]">{categories.categories.length}</p>
            </div>
            <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-3">
              <p className="app-label">Options</p>
              <p className="mt-1 text-2xl font-semibold text-[var(--color-text-primary)]">{totalOptions}</p>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {categories.categories.map((category) => (
          <Link
            key={category.category}
            href={`/admin/dictionaries/${category.category}`}
            className="app-card group flex min-h-[12rem] flex-col p-5 transition hover:-translate-y-0.5 hover:border-[var(--color-accent)] hover:shadow-md"
          >
            <div className="flex items-start justify-between gap-4">
              <span className="flex h-11 w-11 items-center justify-center rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-3)] text-[var(--color-accent)]">
                <BookOpen className="h-5 w-5" />
              </span>
              <span className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface-3)] px-3 py-1 font-mono text-xs font-semibold text-[var(--color-text-secondary)]">
                {category.option_count}
              </span>
            </div>
            <p className="mt-5 app-label">Dictionary</p>
            <h2 className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">{category.category}</h2>
            <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
              {category.option_count} governed option{category.option_count === 1 ? "" : "s"} available for product workflows.
            </p>
            <span className="mt-auto inline-flex items-center gap-2 pt-5 text-sm font-semibold text-[var(--color-accent)]">
              Manage entries
              <ChevronRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
            </span>
          </Link>
        ))}
      </section>
    </div>
  );
}
