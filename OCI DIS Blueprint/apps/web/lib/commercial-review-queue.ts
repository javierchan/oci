import type {
  CommercialReviewEntityType,
  CommercialReviewPriority,
  CommercialReviewWorkflowStatus,
} from "@/lib/types";

export function commercialReviewEntityLabel(entityType: CommercialReviewEntityType): string {
  if (entityType === "exception") return "Exception";
  if (entityType === "mapping_candidate") return "SKU mapping";
  return "Product coverage";
}

export function commercialReviewPriorityPresentation(priority: CommercialReviewPriority): {
  label: string;
  className: string;
} {
  if (priority === "urgent") {
    return {
      label: "Urgent",
      className: "border-rose-400/50 bg-rose-500/10 text-rose-700 dark:text-rose-300",
    };
  }
  if (priority === "high") {
    return {
      label: "High",
      className: "border-amber-400/50 bg-amber-500/10 text-amber-800 dark:text-amber-300",
    };
  }
  if (priority === "normal") {
    return {
      label: "Normal",
      className: "border-sky-400/50 bg-sky-500/10 text-sky-800 dark:text-sky-300",
    };
  }
  return {
    label: "Low",
    className: "border-[var(--color-border)] bg-[var(--color-surface-2)] text-[var(--color-text-secondary)]",
  };
}

export function commercialReviewWorkflowLabel(
  status: CommercialReviewWorkflowStatus,
): string {
  if (status === "in_progress") return "In progress";
  if (status === "waiting_evidence") return "Waiting for evidence";
  if (status === "assigned") return "Assigned";
  return "Unassigned";
}

export function toDateTimeLocal(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}
