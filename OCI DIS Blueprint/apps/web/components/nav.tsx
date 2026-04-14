"use client";

/* Sidebar navigation for the OCI DIS Blueprint workspace shell. */

import Link from "next/link";
import { usePathname } from "next/navigation";

import { titleCaseFromPath } from "@/lib/format";

type NavLink = {
  href: string;
  label: string;
};

function linkClasses(active: boolean): string {
  return [
    "block rounded-2xl border px-4 py-3 text-sm font-medium transition",
    active
      ? "border-amber-400/70 bg-amber-400/15 text-amber-100 shadow-[0_0_0_1px_rgba(251,191,36,0.2)]"
      : "border-white/10 bg-white/5 text-slate-300 hover:border-sky-300/40 hover:bg-sky-300/10 hover:text-white",
  ].join(" ");
}

export function Nav(): JSX.Element {
  const pathname = usePathname();
  const pathParts = pathname.split("/").filter(Boolean);
  const projectId = pathParts[1] ?? null;
  const sectionTitle = pathname === "/" ? "Projects" : titleCaseFromPath(pathname);

  const baseLinks: NavLink[] = [{ href: "/projects", label: "Projects" }];
  const projectLinks: NavLink[] = projectId
    ? [
        { href: `/projects/${projectId}`, label: "Dashboard" },
        { href: `/projects/${projectId}/import`, label: "Import" },
        { href: `/projects/${projectId}/catalog`, label: "Catalog" },
      ]
    : [];

  return (
    <aside className="flex w-full max-w-xs flex-col border-r border-white/10 bg-slate-950 px-5 py-6 text-slate-100">
      <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
        <p className="text-xs uppercase tracking-[0.25em] text-sky-300">Oracle Cloud</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white">OCI DIS Blueprint</h1>
        <p className="mt-3 text-sm leading-6 text-slate-400">
          Frontend workspace for import parity, QA governance, and volumetry review.
        </p>
      </div>

      <div className="mt-8">
        <p className="mb-3 text-xs uppercase tracking-[0.25em] text-slate-500">Navigation</p>
        <nav className="space-y-2">
          {baseLinks.map((link: NavLink) => (
            <Link key={link.href} href={link.href} className={linkClasses(pathname === link.href)}>
              {link.label}
            </Link>
          ))}
        </nav>
      </div>

      {projectLinks.length > 0 ? (
        <div className="mt-8">
          <p className="mb-3 text-xs uppercase tracking-[0.25em] text-slate-500">Current Project</p>
          <nav className="space-y-2">
            {projectLinks.map((link: NavLink) => (
              <Link
                key={link.href}
                href={link.href}
                className={linkClasses(pathname === link.href)}
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
      ) : null}

      <div className="mt-auto space-y-4 rounded-3xl border border-white/10 bg-gradient-to-br from-sky-400/10 via-transparent to-emerald-400/10 p-5">
        <div>
          <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Context</p>
          <p className="mt-2 text-lg font-medium text-white">{sectionTitle}</p>
        </div>
        <span className="inline-flex rounded-full border border-emerald-300/30 bg-emerald-300/10 px-3 py-1 text-xs font-medium uppercase tracking-[0.25em] text-emerald-200">
          v1.0.0
        </span>
      </div>
    </aside>
  );
}
