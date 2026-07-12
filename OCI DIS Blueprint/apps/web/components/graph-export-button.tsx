"use client";

/* Observable, style-safe PNG export control for the system dependency graph SVG. */

import { Check, ImageDown, LoaderCircle, TriangleAlert } from "lucide-react";
import * as Tooltip from "@radix-ui/react-tooltip";
import { useState } from "react";
import type { RefObject } from "react";
import { toPng } from "html-to-image";

type GraphExportButtonProps = {
  projectId: string;
  svgRef: RefObject<SVGSVGElement>;
};

async function exportPNG(svgRef: RefObject<SVGSVGElement>, projectId: string): Promise<void> {
  const svg = svgRef.current;
  if (!svg) {
    throw new Error("Topology SVG is not available.");
  }
  const target = svg.parentElement;
  if (!target) {
    throw new Error("Topology export surface is not available.");
  }

  const rootStyles = window.getComputedStyle(document.documentElement);
  const rect = target.getBoundingClientRect();
  const width = Math.max(Math.round(rect.width), 1);
  const height = Math.max(Math.round(rect.height), 1);
  const dataUrl = await toPng(target, {
    backgroundColor: rootStyles.getPropertyValue("--color-surface").trim() || "#ffffff",
    cacheBust: true,
    pixelRatio: 2,
    width,
    height,
  });
  const png = await fetch(dataUrl).then(async (response) => response.blob());
  const downloadUrl = URL.createObjectURL(png);
  const anchor = document.createElement("a");
  anchor.download = `integration-map-${projectId}-${new Date().toISOString().slice(0, 10)}.png`;
  anchor.href = downloadUrl;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 1_000);
}

export function GraphExportButton({ projectId, svgRef }: GraphExportButtonProps): JSX.Element {
  const [status, setStatus] = useState<"idle" | "exporting" | "done" | "error">("idle");

  async function handleExport(): Promise<void> {
    setStatus("exporting");
    try {
      await exportPNG(svgRef, projectId);
      setStatus("done");
      window.setTimeout(() => setStatus("idle"), 2_000);
    } catch {
      setStatus("error");
    }
  }

  const label = status === "exporting"
    ? "Exporting topology PNG"
    : status === "done"
      ? "Topology PNG exported"
      : status === "error"
        ? "Topology PNG export failed"
        : "Export topology as PNG";

  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <button
          type="button"
          onClick={() => void handleExport()}
          disabled={status === "exporting"}
          className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-secondary)] transition hover:border-[var(--color-line-strong)] hover:text-[var(--color-text-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-accent)] disabled:cursor-wait"
          aria-label={label}
        >
          {status === "exporting" ? <LoaderCircle className="h-4 w-4 animate-spin" /> : null}
          {status === "done" ? <Check className="h-4 w-4 text-emerald-600" /> : null}
          {status === "error" ? <TriangleAlert className="h-4 w-4 text-rose-600" /> : null}
          {status === "idle" ? <ImageDown className="h-4 w-4" /> : null}
        </button>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          sideOffset={7}
          className="z-[80] rounded-md bg-[var(--color-text-primary)] px-2.5 py-1.5 text-xs font-semibold text-[var(--color-surface)] shadow-lg"
        >
          {label}
          <Tooltip.Arrow className="fill-[var(--color-text-primary)]" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}
