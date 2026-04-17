/* Pattern pill for assigned OCI integration patterns. */

type PatternBadgeProps = {
  patternId: string | null;
  name?: string | null;
  category?: string | null;
};

function patternColor(category: string | null | undefined): string {
  const normalized = category?.toUpperCase() ?? "";
  if (normalized.includes("SYNCHRONOUS") || normalized.includes("SÍNCRONO")) {
    return "bg-[var(--color-pat-sync-bg)] text-[var(--color-pat-sync-text)]";
  }
  if (normalized.includes("ASYNCHRONOUS") || normalized.includes("ASÍNCRONO")) {
    return "bg-[var(--color-pat-async-bg)] text-[var(--color-pat-async-text)]";
  }
  return "bg-[var(--color-pat-both-bg)] text-[var(--color-pat-both-text)]";
}

export function PatternBadge({ patternId, name, category }: PatternBadgeProps): JSX.Element {
  if (!patternId) {
    return (
      <span className="inline-flex rounded-full border border-[var(--color-border)] bg-[var(--color-surface-3)] px-3 py-1 text-xs font-medium text-[var(--color-text-muted)]">
        —
      </span>
    );
  }

  return (
    <span
      className={`inline-flex rounded-full border border-transparent px-3 py-1 text-xs font-medium ${patternColor(category)}`}
    >
      {name ? `${patternId} ${name}` : patternId}
    </span>
  );
}
