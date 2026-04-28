/* Pattern pill for assigned OCI integration patterns. */

type PatternBadgeProps = {
  patternId: string | null;
  name?: string | null;
  category?: string | null;
  compact?: boolean;
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

export function PatternBadge({
  patternId,
  name,
  category,
  compact = false,
}: PatternBadgeProps): JSX.Element {
  if (!patternId) {
    return (
      <span className="inline-flex rounded-full border border-[var(--color-border)] bg-[var(--color-surface-3)] px-3 py-1 text-xs font-medium text-[var(--color-text-muted)]">
        Unassigned
      </span>
    );
  }

  const displayName = compact && name && name.length > 18 ? `${name.slice(0, 18)}…` : name;

  return (
    <span
      className={`inline-flex rounded-full border border-transparent px-3 py-1 text-xs font-medium ${patternColor(category)}`}
      title={name ? `${patternId} ${name}` : patternId}
    >
      <span className="font-mono font-bold">{patternId}</span>
      {displayName ? (
        <>
          <span className="opacity-40">·</span>
          <span>{displayName}</span>
        </>
      ) : null}
    </span>
  );
}
