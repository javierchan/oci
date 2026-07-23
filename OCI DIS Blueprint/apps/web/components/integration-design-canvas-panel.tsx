"use client";

/* Full-width integration design canvas panel with dedicated persistence for flow editing. */

import { useRouter } from "next/navigation";
import { Calculator, Check, GitCompare, Loader2, X } from "lucide-react";
import { startTransition, useCallback, useEffect, useMemo, useState } from "react";

import { AiReviewButton } from "@/components/ai-review-button";
import { IntegrationCanvas } from "@/components/integration-canvas";
import { api } from "@/lib/api";
import { evaluateCanvasInteroperability } from "@/lib/canvas-interoperability";
import {
  deriveCanvasSemantics,
  parseCanvasState,
  serializeCanvasState,
  technicalDemandSignature,
} from "@/lib/canvas-governance";
import type {
  AiReviewCanvasDraftSelection,
  AiReviewDraftSimulation,
  CanvasCombination,
  CanvasServiceProfile,
  DictionaryOption,
  Integration,
  IntegrationTechnicalDemand,
  PatternDefinition,
} from "@/lib/types";

type PatternCategory = string;

type IntegrationDesignCanvasPanelProps = {
  projectId: string;
  integration: Integration;
  patterns: PatternDefinition[];
  patternDetail: PatternDefinition | null;
  serviceProfiles: CanvasServiceProfile[];
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
  serviceProfiles: CanvasServiceProfile[],
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
    serializedValue: serializeCanvasState(
      parsed.nodes,
      parsed.edges,
      semantics,
      parsed.endpointPositions,
    ),
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
  const [recommendationPreview, setRecommendationPreview] = useState<AiReviewCanvasDraftSelection | null>(null);
  const [simulation, setSimulation] = useState<AiReviewDraftSimulation | null>(null);
  const [simulating, setSimulating] = useState<boolean>(false);
  const [technicalDemand, setTechnicalDemand] = useState<IntegrationTechnicalDemand | null>(null);
  const [technicalDemandLoading, setTechnicalDemandLoading] = useState<boolean>(true);
  const [technicalDemandError, setTechnicalDemandError] = useState<string>("");
  const normalizedTechnicalDemandSignature = useMemo(
    () =>
      technicalDemandSignature(
        normalizedCanvasSeed.serializedValue,
        normalizedCanvasSeed.coreToolKeys,
      ),
    [normalizedCanvasSeed],
  );
  const [savedTechnicalDemandSignature, setSavedTechnicalDemandSignature] =
    useState<string>(normalizedTechnicalDemandSignature);
  const currentTechnicalDemandSignature = useMemo(
    () => technicalDemandSignature(canvasState, toolKeys),
    [canvasState, toolKeys],
  );
  const maxPeriodDelta = useMemo(
    () => Math.max(...(simulation?.commercial_impact.periods.map((item) => Math.abs(item.delta)) ?? []), 1),
    [simulation],
  );
  const canvasDirty =
    canvasState !== normalizedCanvasSeed.serializedValue ||
    toolKeys.join("|") !== normalizedCanvasSeed.coreToolKeys.join("|");
  const technicalDemandDirty =
    currentTechnicalDemandSignature !== savedTechnicalDemandSignature;

  const refreshTechnicalDemand = useCallback(async (): Promise<void> => {
    setTechnicalDemandLoading(true);
    setTechnicalDemandError("");
    try {
      setTechnicalDemand(
        await api.getIntegrationTechnicalDemand(projectId, integration.id),
      );
    } catch (caughtError) {
      setTechnicalDemand(null);
      setTechnicalDemandError(
        caughtError instanceof Error
          ? caughtError.message
          : "Unable to calculate the saved route.",
      );
    } finally {
      setTechnicalDemandLoading(false);
    }
  }, [integration.id, projectId]);

  useEffect(() => {
    void refreshTechnicalDemand();
  }, [refreshTechnicalDemand, normalizedCanvasSeed.serializedValue]);

  useEffect(() => {
    setCanvasState(normalizedCanvasSeed.serializedValue);
    setToolKeys(normalizedCanvasSeed.coreToolKeys);
    setHasConnectedRoute(normalizedCanvasSeed.hasConnectedRoute);
    setHasBlockingIssues(normalizedCanvasSeed.hasBlockingIssues);
    setStatusMessage("");
    setError("");
    setRecommendationPreview(null);
    setSimulation(null);
    setSavedTechnicalDemandSignature(normalizedTechnicalDemandSignature);
  }, [normalizedCanvasSeed, normalizedTechnicalDemandSignature]);

  useEffect(() => {
    setSimulation(null);
  }, [canvasState, toolKeys]);

  if (!integration.source_system) {
    return null;
  }

  async function handleSaveCanvas(refreshAfterSave = true): Promise<boolean> {
    if (!hasConnectedRoute) {
      setError("Connect the source and destination through the designed pipeline before saving.");
      setStatusMessage("");
      return false;
    }
    if (hasBlockingIssues) {
      setError("Resolve the Oracle-backed canvas blockers before saving.");
      setStatusMessage("");
      return false;
    }

    if (!canvasDirty) {
      setStatusMessage("Canvas is saved and ready for review.");
      setError("");
      return true;
    }

    setSaving(true);
    setStatusMessage("");
    setError("");

    try {
      await api.patchIntegration(projectId, integration.id, {
        additional_tools_overlays: canvasState,
        core_tools: toolKeys,
      });
      setSavedTechnicalDemandSignature(currentTechnicalDemandSignature);
      await refreshTechnicalDemand();
      setStatusMessage("Canvas saved.");
      if (refreshAfterSave) {
        startTransition(() => {
          router.refresh();
        });
      }
      return true;
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to save canvas.");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function handleSimulateDraft(): Promise<void> {
    if (!hasConnectedRoute) {
      setError("Connect the source and destination before simulating the draft.");
      return;
    }
    setSimulating(true);
    setStatusMessage("");
    setError("");
    try {
      const result = await api.simulateAiReviewCanvasDraft(projectId, integration.id, {
        core_tools: toolKeys,
        canvas_state: canvasState,
      });
      setSimulation(result);
      setStatusMessage("Draft impact calculated without changing the integration or creating snapshots.");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to simulate the canvas draft.");
    } finally {
      setSimulating(false);
    }
  }

  return (
    <section className="app-card min-w-0 overflow-hidden space-y-5 p-6">
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
        <div className="hidden flex-wrap items-center gap-3 sm:flex">
          <button
            type="button"
            onClick={() => void handleSimulateDraft()}
            disabled={saving || simulating || !technicalDemandDirty || !hasConnectedRoute}
            className="app-button-secondary gap-2 disabled:cursor-not-allowed disabled:opacity-60"
            title={technicalDemandDirty ? "Calculate technical and commercial impact without saving" : "Change the route to simulate a draft"}
          >
            {simulating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Calculator className="h-4 w-4" />}
            {simulating ? "Simulating…" : "Simulate impact"}
          </button>
          <AiReviewButton
            projectId={projectId}
            integrationId={integration.id}
            defaultScope="integration"
            label="Review current canvas"
            disabled={saving || !hasConnectedRoute || hasBlockingIssues}
            beforeOpen={() => handleSaveCanvas(false)}
            onPreviewCanvasRecommendation={setRecommendationPreview}
          />
          <button
            type="button"
            onClick={() => {
              void handleSaveCanvas(true);
            }}
            disabled={saving || !hasConnectedRoute || hasBlockingIssues}
            className="app-button-primary"
          >
            {saving ? "Saving canvas…" : hasBlockingIssues ? "Resolve blockers to save" : "Save canvas"}
          </button>
        </div>
      </div>

      {recommendationPreview ? (
        <section className="rounded-2xl border border-[var(--color-accent)] bg-[var(--color-surface-2)] p-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <GitCompare className="h-4 w-4 text-[var(--color-accent)]" />
                <p className="app-label">Canvas recommendation preview</p>
                <span className="app-theme-chip">{recommendationPreview.candidate.combination_code}</span>
              </div>
              <h3 className="mt-2 text-lg font-semibold text-[var(--color-text-primary)]">
                {recommendationPreview.candidate.title}
              </h3>
              <p className="mt-2 max-w-4xl text-sm leading-6 text-[var(--color-text-secondary)]">
                The dashed overlay compares this governed candidate with the saved route. Apply it to the local draft
                to edit or validate it; the integration remains unchanged until you explicitly save the canvas.
              </p>
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                {recommendationPreview.candidate.change_set.added_tools.map((tool) => (
                  <span key={`preview-add-${tool}`} className="app-status-chip active">+ {tool}</span>
                ))}
                {recommendationPreview.candidate.change_set.removed_tools.map((tool) => (
                  <span key={`preview-remove-${tool}`} className="app-status-chip archived">- {tool}</span>
                ))}
                {recommendationPreview.candidate.pattern_id !== integration.selected_pattern ? (
                  <span className="app-theme-chip">
                    Pattern proposal: {recommendationPreview.candidate.pattern_id ?? "None"} (confirm separately)
                  </span>
                ) : null}
              </div>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              <button
                type="button"
                onClick={() => {
                  setCanvasState(recommendationPreview.candidate.canvas_state);
                  setToolKeys(recommendationPreview.candidate.core_tools);
                  setRecommendationPreview(null);
                  setStatusMessage("Recommendation applied to the unsaved canvas draft. Validate it, then save when ready.");
                  setError("");
                }}
                className="app-button-primary gap-2"
              >
                <Check className="h-4 w-4" />
                Apply to draft
              </button>
              <button
                type="button"
                onClick={() => setRecommendationPreview(null)}
                className="app-button-secondary gap-2"
              >
                <X className="h-4 w-4" />
                Discard preview
              </button>
            </div>
          </div>
        </section>
      ) : null}

      {simulation ? (
        <section className="space-y-5 border-t border-[var(--color-border)] pt-5" aria-live="polite">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="app-label">Unsaved draft simulation</p>
              <h3 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">
                Technical and commercial impact before save
              </h3>
              <p className="mt-2 max-w-4xl text-sm leading-6 text-[var(--color-text-secondary)]">
                Calculated with assumptions {simulation.assumption_set_version} and Service Product rules {simulation.service_rules_version}.
                No catalog record, snapshot, or approved BOM was changed.
              </p>
            </div>
            <span className={`app-status-chip ${simulation.commercial_impact.status === "computed" ? "active" : "archived"}`}>
              {simulation.commercial_impact.status.replaceAll("_", " ")}
            </span>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {simulation.metrics.map((metric) => (
              <article key={metric.key} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
                <p className="app-label">{metric.label}</p>
                <p className="mt-2 text-lg font-semibold text-[var(--color-text-primary)]">
                  {new Intl.NumberFormat("en-US", { maximumFractionDigits: 2, notation: "compact" }).format(metric.proposed)}
                </p>
                <p className={`mt-1 text-xs font-semibold ${metric.delta > 0 ? "text-amber-600" : metric.delta < 0 ? "text-emerald-600" : "text-[var(--color-text-muted)]"}`}>
                  {metric.delta > 0 ? "+" : ""}{new Intl.NumberFormat("en-US", { maximumFractionDigits: 2, notation: "compact" }).format(metric.delta)} {metric.unit}
                </p>
              </article>
            ))}
            {simulation.metrics.length === 0 ? (
              <p className="text-sm text-[var(--color-text-secondary)]">The draft does not change consolidated technical demand.</p>
            ) : null}
          </div>

          <div className="grid gap-5 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
            <article className="rounded-2xl border border-[var(--color-border)] p-4">
              <p className="app-label">Approved scenario impact</p>
              {simulation.commercial_impact.currency ? (
                <div className="mt-3 grid gap-3 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
                  {[
                    ["Monthly", simulation.commercial_impact.monthly_delta],
                    ["Contract", simulation.commercial_impact.contract_delta],
                    ["Ramp timing", simulation.commercial_impact.ramp_deferred_delta],
                  ].map(([label, value]) => (
                    <div key={String(label)}>
                      <p className="text-xs text-[var(--color-text-muted)]">{label}</p>
                      <p className="mt-1 font-semibold text-[var(--color-text-primary)]">
                        {new Intl.NumberFormat("en-US", {
                          style: "currency",
                          currency: simulation.commercial_impact.currency ?? "USD",
                          maximumFractionDigits: 0,
                          signDisplay: "always",
                        }).format(Number(value ?? 0))}
                      </p>
                    </div>
                  ))}
                </div>
              ) : null}
              <p className="mt-3 text-sm leading-6 text-[var(--color-text-secondary)]">{simulation.commercial_impact.detail}</p>
              {simulation.commercial_impact.scenario_name ? (
                <p className="mt-2 text-xs text-[var(--color-text-muted)]">
                  Scenario: {simulation.commercial_impact.scenario_name} · {simulation.commercial_impact.consumption_model?.replaceAll("_", " ")}
                </p>
              ) : null}
            </article>

            <article className="rounded-2xl border border-[var(--color-border)] p-4">
              <p className="app-label">Monthly contract delta</p>
              {simulation.commercial_impact.periods.length > 0 ? (
                <div className="mt-4 flex h-28 items-end gap-1 overflow-hidden" aria-label="Monthly draft cost delta">
                  {simulation.commercial_impact.periods.map((period) => {
                    const height = Math.max(4, Math.abs(period.delta) / maxPeriodDelta * 100);
                    return (
                      <div key={period.period_index} className="flex min-w-0 flex-1 flex-col items-center justify-end gap-1" title={`Month ${period.period_index}: ${period.delta >= 0 ? "+" : ""}${period.delta.toFixed(2)}`}>
                        <div className={`w-full rounded-t-sm ${period.delta > 0 ? "bg-amber-500" : period.delta < 0 ? "bg-emerald-500" : "bg-[var(--color-border)]"}`} style={{ height: `${height}%` }} />
                        <span className="text-[9px] text-[var(--color-text-muted)]">{period.period_index}</span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="mt-3 text-sm text-[var(--color-text-secondary)]">Approve a deployment scenario to display monthly deltas.</p>
              )}
            </article>
          </div>

          {simulation.proposed_warnings.length > 0 || simulation.commercial_impact.warnings.length > 0 ? (
            <details className="rounded-xl border border-amber-400/45 p-4 text-sm">
              <summary className="cursor-pointer font-semibold text-amber-700 dark:text-amber-300">Review simulation caveats</summary>
              <ul className="mt-3 space-y-1.5 text-[var(--color-text-secondary)]">
                {[...simulation.proposed_warnings, ...simulation.commercial_impact.warnings].map((warning) => <li key={warning}>• {warning}</li>)}
              </ul>
            </details>
          ) : null}
        </section>
      ) : null}

      <div className="sm:hidden rounded-[1.75rem] border border-[var(--color-border)] bg-[var(--color-surface-2)] p-5 text-center">
        <p className="text-base font-semibold text-[var(--color-text-primary)]">
          Design canvas editing is optimized for tablet and desktop.
        </p>
        <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
          This integration currently routes from {integration.source_system ?? "the source system"} to{" "}
          {integration.destination_system ?? "the destination system"} using{" "}
          {toolKeys.length > 0 ? toolKeys.join(", ") : "no governed core tools yet"}.
        </p>
        <div className="mt-4 flex flex-wrap justify-center gap-2 text-xs">
          <span className={hasConnectedRoute ? "app-status-chip active" : "app-status-chip archived"}>
            {hasConnectedRoute ? "Connected Route" : "Route Pending"}
          </span>
          <span className={hasBlockingIssues ? "app-status-chip archived" : "app-status-chip active"}>
            {hasBlockingIssues ? "Blockers Open" : "No Blockers"}
          </span>
        </div>
        <p className="mt-4 text-xs text-[var(--color-text-muted)]">
          Use a wider screen to drag nodes, connect handles, zoom, pan, and save route edits safely.
        </p>
      </div>

      <div className="hidden sm:block">
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
          targetLatencySla={integration.target_latency_sla}
          patternCategory={normalizePatternCategory(patternMap.get(integration.selected_pattern ?? "")?.category)}
          triggerType={integration.trigger_type}
          isRealTime={integration.is_real_time}
          integrationType={integration.type}
          value={canvasState}
          onChange={setCanvasState}
          onToolsChange={setToolKeys}
          onConnectionValidityChange={setHasConnectedRoute}
          onBlockingIssuesChange={setHasBlockingIssues}
          recommendationPreview={recommendationPreview}
          technicalDemand={technicalDemand}
          technicalDemandLoading={technicalDemandLoading}
          technicalDemandError={technicalDemandError}
          technicalDemandStale={technicalDemandDirty}
        />
      </div>

      <div className="flex flex-wrap items-center gap-4 text-sm">
        {statusMessage ? <p className="text-emerald-600">{statusMessage}</p> : null}
        {error ? <p className="text-rose-600">{error}</p> : null}
      </div>
    </section>
  );
}
