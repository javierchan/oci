/* Presentation helpers for durable, human-readable AI review evidence. */

type CanvasEvidence = {
  coreToolKeys?: unknown;
  overlayKeys?: unknown;
};

function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
    : [];
}

export function formatAiReviewDriftValue(field: string, value: string | null): string {
  if (!value) return "Not set";
  if (field !== "additional_tools_overlays" || !value.trim().startsWith("{")) return value;

  try {
    const parsed = JSON.parse(value) as CanvasEvidence;
    const overlays = stringList(parsed.overlayKeys);
    if (overlays.length > 0) return overlays.join(", ");
    const coreTools = stringList(parsed.coreToolKeys);
    return coreTools.length > 0 ? `No overlays · route uses ${coreTools.join(", ")}` : "No overlays";
  } catch {
    return "Canvas evidence could not be summarized";
  }
}

export function isAiReviewLayoutMetadataOnlyDrift(
  field: string,
  planned: string | null,
  actual: string | null,
): boolean {
  if (
    field !== "additional_tools_overlays" ||
    !planned?.trim().startsWith("{") ||
    !actual?.trim().startsWith("{")
  ) {
    return false;
  }

  return formatAiReviewDriftValue(field, planned) === formatAiReviewDriftValue(field, actual);
}
