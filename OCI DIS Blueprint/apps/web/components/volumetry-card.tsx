/* Metric card for consolidated dashboard values. */

type VolumetryCardProps = {
  label: string;
  value: string;
  unit?: string;
  trend?: { delta: number; label: string } | null;
  tooltip?: string;
};

export function VolumetryCard({
  label,
  value,
  unit,
  trend,
  tooltip,
}: VolumetryCardProps): JSX.Element {
  return (
    <article className="app-card group relative p-5" title={tooltip}>
      <p className="app-label">{label}</p>
      <div className="mt-3 flex items-end gap-2">
        <span className="text-3xl font-semibold tracking-tight text-[var(--color-text-primary)]">{value}</span>
        {unit ? <span className="pb-1 text-sm text-[var(--color-text-muted)]">{unit}</span> : null}
      </div>
      {trend ? (
        <p
          className={`mt-2 text-xs font-medium ${
            trend.delta > 0
              ? "text-[var(--color-trend-up)]"
              : trend.delta < 0
                ? "text-[var(--color-trend-down)]"
                : "text-[var(--color-trend-neutral)]"
          }`}
        >
          {trend.delta > 0 ? "↑" : trend.delta < 0 ? "↓" : "="} {Math.abs(trend.delta)}% {trend.label}
        </p>
      ) : null}
      {tooltip ? (
        <span className="absolute right-4 top-3 text-xs text-[var(--color-text-muted)] opacity-0 transition-opacity group-hover:opacity-100">
          ⓘ
        </span>
      ) : null}
    </article>
  );
}
