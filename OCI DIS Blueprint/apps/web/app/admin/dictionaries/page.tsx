/* Dictionary governance overview page grouped by category. */

import Link from "next/link";

import { Breadcrumb } from "@/components/breadcrumb";
import { api } from "@/lib/api";

export default async function AdminDictionariesPage(): Promise<JSX.Element> {
  const categories = await api.listDictionaryCategories();

  return (
    <div className="space-y-6">
      <section className="app-card p-6">
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
      </section>

      <section className="space-y-4">
        {categories.categories.map((category) => (
          <article
            key={category.category}
            className="app-card p-6"
          >
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="app-label">Category</p>
                <h2 className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">{category.category}</h2>
                <p className="mt-2 text-sm text-[var(--color-text-secondary)]">{category.option_count} options available.</p>
              </div>
              <Link
                href={`/admin/dictionaries/${category.category}`}
                className="app-button-primary"
              >
                Manage
              </Link>
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}
