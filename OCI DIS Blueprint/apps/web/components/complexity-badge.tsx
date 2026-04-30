/* Complexity pill used in the catalog grid and detail views. */

import { displayComplexity } from "@/lib/format";

type ComplexityBadgeProps = {
  value: string | null;
};

const COMPLEXITY_STYLES: Record<string, string> = {
  Alto: "bg-[var(--color-complexity-alto-bg)] text-[var(--color-complexity-alto-text)]",
  Medio: "bg-[var(--color-complexity-medio-bg)] text-[var(--color-complexity-medio-text)]",
  Bajo: "bg-[var(--color-complexity-bajo-bg)] text-[var(--color-complexity-bajo-text)]",
};

export function ComplexityBadge({ value }: ComplexityBadgeProps): JSX.Element {
  if (!value) {
    return (
      <span className="inline-flex rounded-full border border-[var(--color-border)] bg-[var(--color-surface-3)] px-3 py-1 text-xs font-medium text-[var(--color-text-muted)]">
        —
      </span>
    );
  }

  return (
    <span
      className={`inline-flex rounded-full border border-transparent px-3 py-1 text-xs font-medium ${COMPLEXITY_STYLES[value] ?? "bg-[var(--color-surface-3)] text-[var(--color-text-secondary)]"}`}
    >
      {displayComplexity(value)}
    </span>
  );
}
