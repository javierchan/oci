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

export const PRICING_GLOSSARY = {
  deterministic_review_gate: {
    label: "Deterministic review gate",
    definition: "A fixed set of evidence and fixture checks that must pass before a SKU can advance. The model does not decide the result.",
  },
  candidate_funnel: {
    label: "Candidate funnel",
    definition: "The path from captured OCI SKUs to quote-ready, customer-rate, input-required, or blocked outcomes.",
  },
  terminal_disposition: {
    label: "Terminal disposition",
    definition: "A recorded final review state for a proposal: approved, blocked, or rejected, with its rationale preserved.",
  },
  field_authority: {
    label: "Field authority",
    definition: "The source allowed to govern a commercial field when several sources describe the same SKU.",
  },
  change_set: {
    label: "Change set",
    definition: "A versioned comparison of official pricing evidence, including detected drift and regression results.",
  },
  quote_ready: {
    label: "Quote-ready",
    definition: "The SKU has approved evidence, a validated pricing rule, and the release coverage needed for deterministic BOM calculation.",
  },
  predicates: {
    label: "Conditions",
    definition: "Selection rules such as edition, license, or BYOL that determine when a SKU mapping applies.",
  },
} as const;

export type PricingGlossaryKey = keyof typeof PRICING_GLOSSARY;

export const PRICING_CERTIFICATION_STAGES = [
  { label: "Capture", detail: "Oracle documents, APIs, and customer rate cards", view: "sources" as const },
  { label: "Identify", detail: "Product, SKU, metric, edition, and licensing identity", view: "products" as const },
  { label: "Classify", detail: "Choose the pricing path that matches the commercial evidence", view: "decisions" as const },
  { label: "Validate", detail: "Run deterministic rule and quote fixtures", view: "decisions" as const },
  { label: "Approve", detail: "Record explicit human disposition and rationale", view: "decisions" as const },
  { label: "Release", detail: "Publish an immutable catalog scope", view: "releases" as const },
  { label: "Calculate", detail: "Let the BOM engine apply quantities, tiers, and terms", view: "releases" as const },
] as const;

export const PRICING_CLASSIFICATIONS = [
  { title: "Directly metered", detail: "A public Oracle unit price and deterministic usage rule are available. The BOM can price the measured quantity." },
  { title: "Contract rate", detail: "The SKU is valid, but the price must come from an authorized customer rate card instead of the public list." },
  { title: "Input required", detail: "Oracle bills a real unit that cannot be inferred safely. The architect must provide the missing quantity or deployment choice." },
  { title: "Dependent entitlement", detail: "The SKU is included, prerequisite-driven, or priced through another commercial component; it is not added independently." },
] as const;

function predicateLabel(key: string): string {
  const aliases: Record<string, string> = {
    byol: "BYOL",
    edition: "Edition",
    license_model: "License model",
    service_tier: "Service tier",
  };
  return aliases[key] ?? key.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function predicateValue(value: unknown): string {
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "string") return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
  if (Array.isArray(value)) return value.map(predicateValue).join(", ");
  if (value && typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, nested]) => `${predicateLabel(key)}: ${predicateValue(nested)}`)
      .join("; ");
  }
  return String(value ?? "not set");
}

export function describePricingPredicates(predicates: Record<string, unknown>): string[] {
  const entries = Object.entries(predicates);
  if (entries.length === 0) return ["No conditions"];
  return entries.map(([key, value]) => `${predicateLabel(key)}: ${predicateValue(value)}`);
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
  if (!input.hasCommercialDocument) {
    return {
      view: "sources",
      label: "Import private Oracle workbook",
      title: "Capture the commercial evidence baseline",
      detail: "Import the private Price List and Supplement workbook before beginning SKU certification.",
    };
  }
  if (!input.evidenceApproved) {
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
