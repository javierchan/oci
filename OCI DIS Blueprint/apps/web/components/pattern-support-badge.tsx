/* Certification-state badge for governed integration patterns. */

import type { PatternDefinition } from "@/lib/types";

type PatternSupportBadgeProps = {
  support: PatternDefinition["support"];
};

function supportTone(status: PatternDefinition["support"]["certification_status"]): string {
  if (status === "certified") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300";
  }
  return "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300";
}

export function PatternSupportBadge({ support }: PatternSupportBadgeProps): JSX.Element {
  return (
    <span
      className={[
        "inline-flex rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em]",
        supportTone(support.certification_status),
      ].join(" ")}
    >
      {support.badge_label}
    </span>
  );
}
