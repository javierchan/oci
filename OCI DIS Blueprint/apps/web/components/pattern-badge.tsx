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
      <span className="inline-flex whitespace-nowrap rounded-md border border-[var(--color-border)] bg-[var(--color-surface-3)] px-2.5 py-1 text-xs font-medium text-[var(--color-text-muted)]">
        Unassigned
      </span>
    );
  }

  const displayName = compact && name && name.length > 18 ? `${name.slice(0, 18)}…` : name;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border border-transparent px-2.5 py-1 text-xs font-medium ${compact ? "max-w-[10rem]" : ""} ${patternColor(category)}`}
      title={name ? `${patternId} ${name}` : patternId}
    >
      <span className="shrink-0 font-mono font-bold">{patternId}</span>
      {displayName ? (
        <>
          <span className="shrink-0 opacity-40">·</span>
          <span className={compact ? "truncate" : ""}>{displayName}</span>
        </>
      ) : null}
    </span>
  );
}
