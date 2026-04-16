/* Graceful not-found surface for invalid project routes. */

import Link from "next/link";

export default function ProjectNotFoundPage(): JSX.Element {
  return (
    <div className="space-y-6">
      <section className="app-card p-8">
        <p className="app-kicker">Project</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">
          Project not found
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--color-text-secondary)]">
          The project you tried to open does not exist or is no longer available in this workspace.
        </p>
        <div className="mt-6">
          <Link href="/projects" className="app-link">
            Back to Projects →
          </Link>
        </div>
      </section>
    </div>
  );
}
