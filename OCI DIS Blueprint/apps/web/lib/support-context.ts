/* Derives bounded contextual-assistant metadata from App routes. */

import type { SupportAttachmentInput, SupportAttachmentType } from "@/lib/types";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export type SupportRouteContext = {
  pageTitle: string;
  projectId?: string;
  integrationId?: string;
  attachment: SupportAttachmentInput;
  suggestions: string[];
};

function routeLabel(section: string | undefined): string {
  if (!section) return "Project Dashboard";
  const labels: Record<string, string> = {
    import: "Workbook Import",
    capture: "Integration Capture",
    catalog: "Integration Catalog",
    map: "Integration Topology",
    graph: "Integration Topology",
    bom: "BOM & Cost",
  };
  return labels[section] ?? section.replace(/-/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

export function deriveSupportRouteContext(pathname: string): SupportRouteContext {
  const parts = pathname.split("/").filter(Boolean);
  let attachmentType: SupportAttachmentType = "page";
  let pageTitle = "Projects";
  let projectId: string | undefined;
  let integrationId: string | undefined;
  let suggestions = [
    "What can I do in this App?",
    "How should I start an integration assessment?",
  ];

  if (parts[0] === "admin") {
    attachmentType = "admin";
    pageTitle = parts[1] ? `Governance · ${routeLabel(parts[1])}` : "Governance Library";
    suggestions = ["What is governed in this section?", "How does this affect project calculations?"];
  } else if (parts[0] === "projects" && UUID_PATTERN.test(parts[1] ?? "")) {
    projectId = parts[1];
    const section = parts[2];
    pageTitle = routeLabel(section);
    attachmentType = section === "map" || section === "graph" ? "topology" : section === "bom" ? "bom" : section === "import" ? "import" : section === "catalog" ? "catalog" : section === "capture" ? "catalog" : "project";
    if (section === "catalog" && UUID_PATTERN.test(parts[3] ?? "")) {
      integrationId = parts[3];
      attachmentType = "integration";
      pageTitle = "Integration Detail";
      suggestions = ["Explain this integration and its risks.", "Is its pattern and service route appropriate?"];
    } else if (section === "bom") {
      suggestions = ["Explain the current BOM evidence.", "What inputs are still needed for a reliable estimate?"];
    } else if (section === "map" || section === "graph") {
      suggestions = ["What should I investigate in this topology?", "How do I interpret dependency risk?"];
    } else if (section === "import") {
      suggestions = ["How does workbook import work?", "What should I validate before uploading?"];
    } else if (section === "catalog") {
      suggestions = ["How should I review this catalog?", "Which QA signals need attention first?"];
    } else {
      suggestions = ["Summarize this project workspace.", "What should the architect review next?"];
    }
  }

  return {
    pageTitle,
    projectId,
    integrationId,
    attachment: {
      attachment_type: attachmentType,
      label: pageTitle,
      entity_id: integrationId ?? projectId,
      href: pathname,
      context: { route: pathname, page_title: pageTitle },
    },
    suggestions,
  };
}

export function sameSupportAttachment(
  left: SupportAttachmentInput,
  right: SupportAttachmentInput,
): boolean {
  return left.attachment_type === right.attachment_type && left.entity_id === right.entity_id && left.href === right.href;
}
