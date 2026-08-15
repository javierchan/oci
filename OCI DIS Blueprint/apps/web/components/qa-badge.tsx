/* QA status pill used across dashboard, grid, and detail views. */

import { displayQaStatus } from "@/lib/format";

type QaBadgeProps = {
  status: string | null;
};

const QA_STYLES: Record<string, string> = {
  OK: "bg-[var(--color-qa-ok-bg)] text-[var(--color-qa-ok-text)] border border-[var(--color-qa-ok-border)]",
  REVIEW:
    "bg-[var(--color-qa-review-bg)] text-[var(--color-qa-review-text)] border border-[var(--color-qa-review-border)]",
  PENDING:
    "bg-[var(--color-qa-pending-bg)] text-[var(--color-qa-pending-text)] border border-[var(--color-qa-pending-border)]",
};

export function QaBadge({ status }: QaBadgeProps): JSX.Element {
  const label = status ?? "PENDING";
  const style = QA_STYLES[label] ?? QA_STYLES.PENDING;

  return (
    <span className={`catalog-badge ${style}`}>
      {displayQaStatus(label)}
    </span>
  );
}
