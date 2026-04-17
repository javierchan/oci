"use client";

/* Full-width integration design canvas panel with dedicated persistence for flow editing. */

import { useRouter } from "next/navigation";
import { startTransition, useMemo, useState } from "react";

import { IntegrationCanvas } from "@/components/integration-canvas";
import { api } from "@/lib/api";
import type {
  CanvasCombination,
  DictionaryOption,
  Integration,
  PatternDefinition,
  ServiceCapabilityProfile,
} from "@/lib/types";

type PatternCategory = string;

type IntegrationDesignCanvasPanelProps = {
  projectId: string;
  integration: Integration;
  patterns: PatternDefinition[];
  patternDetail: PatternDefinition | null;
  serviceProfiles: ServiceCapabilityProfile[];
  toolOptions: DictionaryOption[];
  overlayOptions: DictionaryOption[];
  combinations: CanvasCombination[];
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

function normalizePatternCategory(value: string | null | undefined): PatternCategory | null {
  return value ?? null;
}

export function IntegrationDesignCanvasPanel({
  projectId,
  integration,
  patterns,
  patternDetail,
  serviceProfiles,
  toolOptions,
  overlayOptions,
  combinations,
}: IntegrationDesignCanvasPanelProps): JSX.Element | null {
  const router = useRouter();
  const [canvasState, setCanvasState] = useState<string>(integration.additional_tools_overlays ?? "");
  const [toolKeys, setToolKeys] = useState<string[]>(parseCoreTools(integration.core_tools));
  const [saving, setSaving] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [hasConnectedRoute, setHasConnectedRoute] = useState<boolean>(true);

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
    if (!hasConnectedRoute) {
      setError("Connect the source and destination through the designed pipeline before saving.");
      setStatusMessage("");
      return;
    }

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
          disabled={saving || !hasConnectedRoute}
          className="app-button-primary"
        >
          {saving ? "Saving canvas…" : "Save canvas"}
        </button>
      </div>

      <IntegrationCanvas
        projectId={integration.project_id}
        sourceSystem={integration.source_system}
        sourceTechnology={integration.source_technology}
        destinationSystem={integration.destination_system}
        destinationTechnology={integration.destination_technology_1}
        selectedPattern={integration.selected_pattern}
        patternDetail={patternDetail}
        serviceProfiles={serviceProfiles}
        coreTools={parseCoreTools(integration.core_tools)}
        toolOptions={toolOptions}
        overlayOptions={overlayOptions}
        combinations={combinations}
        patterns={patterns}
        payloadKb={integration.payload_per_execution_kb}
        frequency={integration.frequency}
        patternCategory={normalizePatternCategory(patternMap.get(integration.selected_pattern ?? "")?.category)}
        value={canvasState || null}
        onChange={setCanvasState}
        onToolsChange={setToolKeys}
        onConnectionValidityChange={setHasConnectedRoute}
      />

      <div className="flex flex-wrap items-center gap-4 text-sm">
        {statusMessage ? <p className="text-emerald-600">{statusMessage}</p> : null}
        {error ? <p className="text-rose-600">{error}</p> : null}
      </div>
    </section>
  );
}
