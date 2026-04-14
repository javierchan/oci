/* Metric card for consolidated dashboard values. */

type VolumetryCardProps = {
  label: string;
  value: string;
  unit?: string;
};

export function VolumetryCard({ label, value, unit }: VolumetryCardProps): JSX.Element {
  return (
    <article className="rounded-3xl border border-slate-800 bg-slate-950/70 p-5 shadow-[0_16px_40px_rgba(15,23,42,0.18)]">
      <p className="text-xs uppercase tracking-[0.25em] text-slate-500">{label}</p>
      <div className="mt-4 flex items-end gap-2">
        <span className="text-3xl font-semibold tracking-tight text-white">{value}</span>
        {unit ? <span className="pb-1 text-sm text-slate-400">{unit}</span> : null}
      </div>
    </article>
  );
}
