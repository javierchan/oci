/* Pattern pill for assigned OCI integration patterns. */

type PatternBadgeProps = {
  patternId: string | null;
  name?: string | null;
};

export function PatternBadge({ patternId, name }: PatternBadgeProps): JSX.Element {
  if (!patternId) {
    return (
      <span className="inline-flex rounded-full border border-slate-400/20 bg-slate-400/10 px-3 py-1 text-xs font-medium text-slate-400">
        —
      </span>
    );
  }

  return (
    <span className="inline-flex rounded-full border border-sky-400/30 bg-sky-400/10 px-3 py-1 text-xs font-medium text-sky-100">
      {name ? `${patternId} ${name}` : patternId}
    </span>
  );
}
