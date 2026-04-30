"use client";

/* Full-width integration design canvas panel with dedicated persistence for flow editing. */

import { useRouter } from "next/navigation";
import { startTransition, useEffect, useMemo, useState } from "react";

import { IntegrationCanvas } from "@/components/integration-canvas";
import { api } from "@/lib/api";
import { evaluateCanvasInteroperability } from "@/lib/canvas-interoperability";
import {
  deriveCanvasSemantics,
  parseCanvasState,
  serializeCanvasState,
} from "@/lib/canvas-governance";
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

function buildCanvasSeed(
  additionalToolsOverlays: string | null,
  coreTools: string | null,
  selectedPattern: string | null,
  serviceProfiles: ServiceCapabilityProfile[],
  overlayOptions: DictionaryOption[],
  combinations: CanvasCombination[],
  payloadKb: number | null,
  triggerType: string | null,
  isRealTime: boolean | null,
  sourceTechnology: string | null,
  destinationTechnology: string | null,
  integrationType: string | null,
): {
  serializedValue: string;
  coreToolKeys: string[];
  hasConnectedRoute: boolean;
  hasBlockingIssues: boolean;
} {
  const parsed = parseCanvasState(
    additionalToolsOverlays,
    parseCoreTools(coreTools),
  );
  const semantics = deriveCanvasSemantics({
    nodes: parsed.nodes,
    edges: parsed.edges,
    overlayToolKeys: overlayOptions.map((option) => option.value),
    combinations,
    selectedPattern,
  });
  const interoperabilityReport = evaluateCanvasInteroperability({
    nodes: parsed.nodes,
    edges: parsed.edges,
    overlayToolKeys: overlayOptions.map((option) => option.value),
    serviceProfilesById: new Map(serviceProfiles.map((profile) => [profile.service_id, profile])),
    payloadKb,
    triggerType,
    isRealTime,
    sourceTechnology,
    destinationTechnology,
    integrationType,
  });

  return {
    serializedValue: serializeCanvasState(parsed.nodes, parsed.edges, semantics),
    coreToolKeys: parsed.coreToolKeys,
    hasConnectedRoute: semantics.hasConnectedRoute,
    hasBlockingIssues: interoperabilityReport.blockers.length > 0,
  };
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
  const normalizedCanvasSeed = useMemo(
    () =>
      buildCanvasSeed(
        integration.additional_tools_overlays,
        integration.core_tools,
        integration.selected_pattern,
        serviceProfiles,
        overlayOptions,
        combinations,
        integration.payload_per_execution_kb,
        integration.trigger_type,
        integration.is_real_time,
        integration.source_technology,
        integration.destination_technology_1,
        integration.type,
      ),
    [
      combinations,
      integration.additional_tools_overlays,
      integration.core_tools,
      integration.destination_technology_1,
      integration.is_real_time,
      integration.payload_per_execution_kb,
      integration.selected_pattern,
      integration.source_technology,
      integration.trigger_type,
      integration.type,
      overlayOptions,
      serviceProfiles,
    ],
  );

  const [canvasState, setCanvasState] = useState<string>(normalizedCanvasSeed.serializedValue);
  const [toolKeys, setToolKeys] = useState<string[]>(normalizedCanvasSeed.coreToolKeys);
  const [saving, setSaving] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [hasConnectedRoute, setHasConnectedRoute] = useState<boolean>(normalizedCanvasSeed.hasConnectedRoute);
  const [hasBlockingIssues, setHasBlockingIssues] = useState<boolean>(normalizedCanvasSeed.hasBlockingIssues);

  useEffect(() => {
    setCanvasState(normalizedCanvasSeed.serializedValue);
    setToolKeys(normalizedCanvasSeed.coreToolKeys);
    setHasConnectedRoute(normalizedCanvasSeed.hasConnectedRoute);
    setHasBlockingIssues(normalizedCanvasSeed.hasBlockingIssues);
    setStatusMessage("");
    setError("");
  }, [normalizedCanvasSeed]);

  if (!integration.source_system) {
    return null;
  }

  async function handleSaveCanvas(): Promise<void> {
    if (!hasConnectedRoute) {
      setError("Connect the source and destination through the designed pipeline before saving.");
      setStatusMessage("");
      return;
    }
    if (hasBlockingIssues) {
      setError("Resolve the Oracle-backed canvas blockers before saving.");
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
          disabled={saving || !hasConnectedRoute || hasBlockingIssues}
          className="app-button-primary"
        >
          {saving ? "Saving canvas…" : hasBlockingIssues ? "Resolve blockers to save" : "Save canvas"}
        </button>
      </div>

      <IntegrationCanvas
        projectId={projectId}
        sourceSystem={integration.source_system}
        sourceTechnology={integration.source_technology}
        destinationSystem={integration.destination_system}
        destinationTechnology={integration.destination_technology_1}
        selectedPattern={integration.selected_pattern}
        patternDetail={patternDetail}
        serviceProfiles={serviceProfiles}
        coreTools={toolKeys}
        toolOptions={toolOptions}
        overlayOptions={overlayOptions}
        combinations={combinations}
        patterns={patterns}
        payloadKb={integration.payload_per_execution_kb}
        frequency={integration.frequency}
        patternCategory={normalizePatternCategory(patternMap.get(integration.selected_pattern ?? "")?.category)}
        triggerType={integration.trigger_type}
        isRealTime={integration.is_real_time}
        integrationType={integration.type}
        value={canvasState}
        onChange={setCanvasState}
        onToolsChange={setToolKeys}
        onConnectionValidityChange={setHasConnectedRoute}
        onBlockingIssuesChange={setHasBlockingIssues}
      />

      <div className="flex flex-wrap items-center gap-4 text-sm">
        {statusMessage ? <p className="text-emerald-600">{statusMessage}</p> : null}
        {error ? <p className="text-rose-600">{error}</p> : null}
      </div>
    </section>
  );
}
