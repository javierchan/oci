import type { LucideIcon } from "lucide-react";
import {
  Boxes,
  FileCheck2,
  LayoutDashboard,
  PackageCheck,
  ShieldCheck,
} from "lucide-react";

export type PricingWorkspaceView =
  | "overview"
  | "sources"
  | "products"
  | "decisions"
  | "releases";

export interface PricingWorkspaceViewDefinition {
  id: PricingWorkspaceView;
  label: string;
  shortLabel: string;
  description: string;
  Icon: LucideIcon;
}
export const PRICING_WORKSPACE_VIEWS: PricingWorkspaceViewDefinition[] = [
  {
    id: "overview",
    label: "Overview",
    shortLabel: "Overview",
    description: "Understand current readiness and the next governed action.",
    Icon: LayoutDashboard,
  },
  {
    id: "sources",
    label: "Official Sources",
    shortLabel: "Sources",
    description: "Synchronize Oracle evidence, customer rates, and normalized price items.",
    Icon: FileCheck2,
  },
  {
    id: "products",
    label: "Products & SKUs",
    shortLabel: "Products",
    description: "Browse OCI products and review their readiness for governed BOM use.",
    Icon: Boxes,
  },
  {
    id: "decisions",
    label: "Review & Certification",
    shortLabel: "Certification",
    description: "Resolve evidence exceptions and record explicit commercial decisions.",
    Icon: ShieldCheck,
  },
  {
    id: "releases",
    label: "Releases & BOM",
    shortLabel: "Releases",
    description: "Approve immutable catalogs and map technical demand to commercial SKUs.",
    Icon: PackageCheck,
  },
];

export interface PricingReadinessInput {
  sourceCount: number;
  sourceValidationPassed: boolean;
  hasCommercialDocument: boolean;
  evidenceApproved: boolean;
  pendingDecisions: number;
  openExceptions: number;
  coverageTotal: number;
  coverageApproved: number;
  releaseCount: number;
  approvedMappings: number;
}

export interface PricingNextAction {
  view: PricingWorkspaceView;
  label: string;
  title: string;
  detail: string;
}

export function nextPricingAction(input: PricingReadinessInput): PricingNextAction {
  if (input.sourceCount === 0 || !input.sourceValidationPassed) {
    return {
      view: "sources",
      label: "Review official sources",
      title: "Establish current Oracle evidence",
      detail: "Synchronize and validate the source set before any SKU can be certified.",
    };
  }
  if (!input.hasCommercialDocument || !input.evidenceApproved) {
    return {
      view: "decisions",
      label: "Approve source evidence",
      title: "Approve the commercial evidence baseline",
      detail: "The official workbook must be accepted as immutable evidence before candidate review.",
    };
  }
  if (input.pendingDecisions > 0 || input.openExceptions > 0) {
    return {
      view: "decisions",
      label: "Continue certification",
      title: "Resolve the remaining SKU decisions",
      detail: `${input.pendingDecisions} candidate decision(s) and ${input.openExceptions} exception(s) still require disposition.`,
    };
  }
  if (input.coverageTotal === 0 || input.coverageApproved < input.coverageTotal) {
    return {
      view: "products",
      label: "Review BOM readiness",
      title: "Promote certified products into BOM capability",
      detail: `${input.coverageApproved} of ${input.coverageTotal} product proposal(s) are approved for governed use.`,
    };
  }
  if (input.releaseCount === 0 || input.approvedMappings === 0) {
    return {
      view: "releases",
      label: "Publish BOM inputs",
      title: "Complete release and mapping readiness",
      detail: "Publish the reviewed catalog and confirm the mappings used by deterministic BOM calculation.",
    };
  }
  return {
    view: "releases",
    label: "Inspect published inputs",
    title: "Commercial governance is ready for BOM use",
    detail: "Official evidence, product decisions, release scope, and approved mappings are available.",
  };
}
