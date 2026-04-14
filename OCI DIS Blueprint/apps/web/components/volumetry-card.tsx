/* Metric card for consolidated dashboard values. */

type VolumetryCardProps = {
  label: string;
  value: string;
  unit?: string;
};

export function VolumetryCard({ label, value, unit }: VolumetryCardProps): JSX.Element {
  return (
    <article className="app-card rounded-3xl p-5">
      <p className="text-xs uppercase tracking-[0.25em] text-[var(--color-text-secondary)]">{label}</p>
      <div className="mt-4 flex items-end gap-2">
        <span className="text-3xl font-semibold tracking-tight text-[var(--color-text-primary)]">{value}</span>
        {unit ? <span className="pb-1 text-sm text-[var(--color-text-muted)]">{unit}</span> : null}
      </div>
    </article>
  );
}
