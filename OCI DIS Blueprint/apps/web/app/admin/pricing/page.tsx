/* Governed OCI pricing administration page. */

import { BadgeDollarSign } from "lucide-react";

import { Breadcrumb } from "@/components/breadcrumb";
import { PricingAdminPanel } from "@/components/pricing-admin-panel";

export default function AdminPricingPage(): JSX.Element {
  return (
    <div className="console-page">
      <section className="console-hero">
        <div className="flex items-start gap-4">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] text-[var(--color-accent)]">
            <BadgeDollarSign className="h-5 w-5" />
          </span>
          <div>
            <p className="app-kicker">Admin Governance · Commercial Evidence</p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">OCI Pricing</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
              Synchronize price evidence, review immutable catalogs, and govern the mappings that convert technical service demand into OCI SKUs.
            </p>
            <div className="mt-4"><Breadcrumb items={[{ label: "Home", href: "/projects" }, { label: "Admin", href: "/admin" }, { label: "Pricing" }]} /></div>
          </div>
        </div>
      </section>
      <PricingAdminPanel />
    </div>
  );
}
