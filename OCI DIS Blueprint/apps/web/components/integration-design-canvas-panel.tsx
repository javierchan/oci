"use client";

/* Full-width integration design canvas panel with dedicated persistence for flow editing. */

import { useRouter } from "next/navigation";
import { startTransition, useMemo, useState } from "react";

import { IntegrationCanvas } from "@/components/integration-canvas";
import { api } from "@/lib/api";
import type { DictionaryOption, Integration, PatternDefinition } from "@/lib/types";

type IntegrationDesignCanvasPanelProps = {
  projectId: string;
  integration: Integration;
  patterns: PatternDefinition[];
  toolOptions: DictionaryOption[];
};

function parseCoreTools(value: string | null): string[] {
  if (!value) {
    return [];
  }
  return value
    .split(",")
    .map((entry: string) => entry.trim())
    .filter(Boolean);
}

function normalizePatternCategory(value: string | null | undefined): string | null {
  return value?.trim() ? value : null;
}

export function IntegrationDesignCanvasPanel({
  projectId,
  integration,
  patterns,
  toolOptions,
}: IntegrationDesignCanvasPanelProps): JSX.Element | null {
  const router = useRouter();
  const [canvasState, setCanvasState] = useState<string>(integration.additional_tools_overlays ?? "");
  const [toolKeys, setToolKeys] = useState<string[]>(parseCoreTools(integration.core_tools));
  const [saving, setSaving] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [error, setError] = useState<string>("");

  const patternMap = useMemo(
    () =>
      new Map<string, PatternDefinition>(
        patterns.map((patternDefinition: PatternDefinition) => [
          patternDefinition.pattern_id,
          patternDefinition,
        ]),
      ),
    [patterns],
  );

  if (!integration.source_system) {
    return null;
  }

  async function handleSaveCanvas(): Promise<void> {
    setSaving(true);
    setStatusMessage("");
    setError("");

    try {
      await api.patchIntegration(projectId, integration.id, {
        additional_tools_overlays: canvasState,
        core_tools: toolKeys,
      });
      setStatusMessage("Canvas saved.");
      startTransition(() => {
        router.refresh();
      });
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to save canvas.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="app-card space-y-5 p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="app-label">Integration Design Canvas</p>
          <h2 className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">
            Design the payload route end to end
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
            Model how the payload enters, moves through OCI services, branches into additional delivery paths, and reaches the destination systems.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            void handleSaveCanvas();
          }}
          disabled={saving}
          className="app-button-primary"
        >
          {saving ? "Saving canvas…" : "Save canvas"}
        </button>
      </div>

      <IntegrationCanvas
        sourceSystem={integration.source_system}
        sourceTechnology={integration.source_technology}
        destinationSystem={integration.destination_system}
        destinationTechnology={integration.destination_technology_1}
        selectedPattern={integration.selected_pattern}
        coreTools={parseCoreTools(integration.core_tools)}
        availableTools={toolOptions.map((option: DictionaryOption) => option.value)}
        payloadKb={integration.payload_per_execution_kb}
        frequency={integration.frequency}
        patternCategory={normalizePatternCategory(patternMap.get(integration.selected_pattern ?? "")?.category)}
        value={canvasState || null}
        onChange={setCanvasState}
        onToolsChange={setToolKeys}
      />

      <div className="flex flex-wrap items-center gap-4 text-sm">
        {statusMessage ? <p className="text-emerald-600">{statusMessage}</p> : null}
        {error ? <p className="text-rose-600">{error}</p> : null}
      </div>
    </section>
  );
}
