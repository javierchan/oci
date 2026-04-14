/* QA status pill used across dashboard, grid, and detail views. */

type QaBadgeProps = {
  status: string | null;
};

const QA_STYLES: Record<string, string> = {
  OK: "border-emerald-400/40 bg-emerald-400/15 text-emerald-200",
  REVISAR: "border-amber-400/40 bg-amber-400/15 text-amber-200",
  PENDING: "border-slate-400/30 bg-slate-400/10 text-slate-300",
};

export function QaBadge({ status }: QaBadgeProps): JSX.Element {
  const label = status ?? "PENDING";
  const style = QA_STYLES[label] ?? QA_STYLES.PENDING;

  return (
    <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] ${style}`}>
      {label}
    </span>
  );
}
