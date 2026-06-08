"use client";

/* PNG export control for the system dependency graph SVG. */

import type { RefObject } from "react";
import { Download } from "lucide-react";

type GraphExportButtonProps = {
  projectId: string;
  svgRef: RefObject<SVGSVGElement>;
};

function exportPNG(svgRef: RefObject<SVGSVGElement>, projectId: string): void {
  const svg = svgRef.current;
  if (!svg) {
    return;
  }
  const serializer = new XMLSerializer();
  const svgStr = serializer.serializeToString(svg);
  const img = new Image();
  img.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = svg.clientWidth * 2;
    canvas.height = svg.clientHeight * 2;
    const context = canvas.getContext("2d");
    if (!context) {
      return;
    }
    context.scale(2, 2);
    context.drawImage(img, 0, 0);
    const anchor = document.createElement("a");
    anchor.download = `integration-map-${projectId}-${new Date().toISOString().slice(0, 10)}.png`;
    anchor.href = canvas.toDataURL("image/png");
    anchor.click();
  };
  img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svgStr)}`;
}

export function GraphExportButton({
  projectId,
  svgRef,
}: GraphExportButtonProps): JSX.Element {
  return (
    <button
      type="button"
      onClick={() => exportPNG(svgRef, projectId)}
      className="inline-flex min-h-9 items-center justify-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1 text-xs font-semibold text-[var(--color-text-secondary)] transition hover:border-[var(--color-line-strong)] hover:text-[var(--color-text-primary)]"
    >
      <Download className="h-4 w-4" />
      Export PNG
    </button>
  );
}
