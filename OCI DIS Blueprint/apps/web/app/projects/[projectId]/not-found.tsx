/* Not-found state for invalid or deleted project routes. */

import Link from "next/link";

export default function ProjectNotFound(): JSX.Element {
  return (
    <div className="space-y-6">
      <section className="app-card p-8">
        <p className="app-kicker">Project Not Found</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">
          This project is no longer available
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--color-text-secondary)]">
          The project may have been deleted, archived from another session, or the URL may be outdated.
        </p>
        <div className="mt-6 flex flex-wrap gap-4">
          <Link href="/projects" className="app-button-primary">
            Back to Projects
          </Link>
        </div>
      </section>
    </div>
  );
}
