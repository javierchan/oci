import type { DashboardRisk, DashboardSnapshot } from "@/lib/types";

export type ProjectWorkflowStepState = "complete" | "current" | "upcoming";

export type ProjectWorkflowStep = {
  id: "inventory" | "qa" | "sizing" | "topology" | "decision";
  label: string;
  description: string;
  href: string;
  state: ProjectWorkflowStepState;
};

export type ProjectNextAction = {
  label: string;
  description: string;
  href: string;
  reason: string;
};

export type ProjectWorkflowGuide = {
  nextAction: ProjectNextAction;
  steps: ProjectWorkflowStep[];
  qaRisks: DashboardRisk[];
};

type ProjectWorkflowInput = {
  projectId: string;
  catalogCount: number;
  latestSnapshotId: string | null;
  dashboard: DashboardSnapshot | null;
};

function catalogHref(projectId: string, query = ""): string {
  return `/projects/${projectId}/catalog${query}`;
}

export function deriveProjectWorkflowGuide({
  projectId,
  catalogCount,
  latestSnapshotId,
  dashboard,
}: ProjectWorkflowInput): ProjectWorkflowGuide {
  const qaOk = dashboard?.charts.completeness.qa_ok ?? 0;
  const qaReview = dashboard?.charts.completeness.qa_revisar ?? 0;
  const qaPending = dashboard?.charts.completeness.qa_pending ?? 0;
  const hasInventory = catalogCount > 0;
  const hasQaWork = qaReview + qaPending > 0;
  const hasSizing = Boolean(latestSnapshotId);
  const qaHref = catalogHref(projectId, `?qa_status=${qaPending > 0 ? "PENDING" : "REVISAR"}`);

  const nextAction = !hasInventory
    ? {
        label: "Build the inventory",
        description: "Upload a governed workbook or capture the first integration manually.",
        href: `/projects/${projectId}/import`,
        reason: "No catalog integrations are available yet.",
      }
    : hasQaWork
      ? {
          label: "Resolve the QA queue",
          description: `${qaReview + qaPending} integration${qaReview + qaPending === 1 ? " needs" : "s need"} an architect decision before the baseline is trusted.`,
          href: qaHref,
          reason: qaPending > 0 ? "Some records are still pending required information." : "Some records need an architect review.",
        }
      : !hasSizing
        ? {
            label: "Calculate the technical baseline",
            description: "Create the first immutable sizing snapshot from the governed catalog.",
            href: `/projects/${projectId}`,
            reason: "The catalog is ready, but it has not been calculated yet.",
          }
        : {
            label: "Investigate the dependency map",
            description: "Review priority paths and turn the current baseline into an architecture decision.",
            href: `/projects/${projectId}/map`,
            reason: "The governed inventory and technical baseline are ready for investigation.",
          };

  const steps: ProjectWorkflowStep[] = [
    {
      id: "inventory",
      label: "Build inventory",
      description: hasInventory ? `${catalogCount} governed integration${catalogCount === 1 ? "" : "s"} available.` : "Import a workbook or capture the first integration.",
      href: hasInventory ? catalogHref(projectId) : `/projects/${projectId}/import`,
      state: hasInventory ? "complete" : "current",
    },
    {
      id: "qa",
      label: "Resolve QA",
      description: hasQaWork ? `${qaReview} review · ${qaPending} pending.` : hasInventory ? `${qaOk} integration${qaOk === 1 ? "" : "s"} currently pass QA.` : "QA begins after inventory exists.",
      href: hasInventory ? qaHref : `/projects/${projectId}/capture/new`,
      state: !hasInventory ? "upcoming" : hasQaWork ? "current" : "complete",
    },
    {
      id: "sizing",
      label: "Calculate baseline",
      description: hasSizing ? "Latest technical sizing is available." : "Recalculate after governed inputs are ready.",
      href: `/projects/${projectId}`,
      state: hasSizing ? "complete" : hasInventory && !hasQaWork ? "current" : "upcoming",
    },
    {
      id: "topology",
      label: "Investigate topology",
      description: "Use the map to inspect systems, paths, and architecture risks.",
      href: `/projects/${projectId}/map`,
      state: hasSizing ? "current" : "upcoming",
    },
    {
      id: "decision",
      label: "Prepare decision",
      description: "Review the governed BOM only when technical evidence is ready.",
      href: `/projects/${projectId}/bom`,
      state: hasSizing ? "upcoming" : "upcoming",
    },
  ];

  return {
    nextAction,
    steps,
    qaRisks: dashboard?.risks.slice(0, 3) ?? [],
  };
}
