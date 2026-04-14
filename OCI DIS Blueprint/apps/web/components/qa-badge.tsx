/* QA status pill used across dashboard, grid, and detail views. */

type QaBadgeProps = {
  status: string | null;
};

const QA_STYLES: Record<string, string> = {
  OK: "bg-[var(--color-qa-ok-bg)] text-[var(--color-qa-ok-text)] border border-[var(--color-qa-ok-border)]",
  REVISAR:
    "bg-[var(--color-qa-revisar-bg)] text-[var(--color-qa-revisar-text)] border border-[var(--color-qa-revisar-border)]",
  PENDING:
    "bg-[var(--color-qa-pending-bg)] text-[var(--color-qa-pending-text)] border border-[var(--color-qa-pending-border)]",
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
