"use client";

/* Visual integration design canvas for reactive architecture previews on the detail page. */

type IntegrationCanvasProps = {
  sourceSystem: string;
  sourceTechnology: string | null;
  destinationSystem: string | null;
  destinationTechnology: string | null;
  selectedPattern: string | null;
  coreTools: string[];
  payloadKb: number | null;
  frequency: string | null;
  patternCategory: "SÍNCRONO" | "ASÍNCRONO" | "SÍNCRONO + ASÍNCRONO" | null;
};

type NodeKind = "system" | "oic" | "streaming" | "functions" | "gateway" | "storage" | "db";

type CanvasNode = {
  key: string;
  label: string;
  subtitle: string | null;
  kind: NodeKind;
};

const TOOL_KINDS: Record<string, NodeKind> = {
  "OCI Gen3": "oic",
  "OCI API Gateway": "gateway",
  "OCI Streaming": "streaming",
  "OCI Queue": "streaming",
  "Oracle Functions": "functions",
  "OCI Data Integration": "oic",
  "Oracle ORDS": "db",
  ATP: "db",
  "Oracle ATP": "db",
  "Oracle DB": "db",
  SFTP: "storage",
  "OCI Object Storage": "storage",
  "OCI APM": "oic",
};

const KIND_COLORS: Record<NodeKind, { bg: string; border: string; icon: string }> = {
  system: { bg: "#dbeafe", border: "#3b82f6", icon: "🏢" },
  oic: { bg: "#ede9fe", border: "#8b5cf6", icon: "⚙" },
  streaming: { bg: "#fef3c7", border: "#f59e0b", icon: "⚡" },
  functions: { bg: "#dcfce7", border: "#22c55e", icon: "λ" },
  gateway: { bg: "#e0f2fe", border: "#0ea5e9", icon: "⇄" },
  storage: { bg: "#fce7f3", border: "#ec4899", icon: "📦" },
  db: { bg: "#fff7ed", border: "#f97316", icon: "🗄" },
};

const TOOL_ORDER: NodeKind[] = ["gateway", "oic", "streaming", "functions", "db", "storage"];

function estimateBillingMsgs(payloadKb: number | null): number | null {
  if (!payloadKb) {
    return null;
  }
  return Math.ceil(payloadKb / 50);
}

function estimateExecutionsPerDay(frequency: string | null): number | null {
  if (!frequency) {
    return null;
  }

  const normalized = frequency.trim().toLowerCase();
  if (normalized === "una vez al día") {
    return 1;
  }
  if (normalized === "cada hora") {
    return 24;
  }
  if (normalized === "tiempo real") {
    return 1440;
  }
  if (normalized === "semanal") {
    return 1 / 7;
  }
  if (normalized === "mensual") {
    return 1 / 30;
  }
  if (normalized === "dos veces al día") {
    return 2;
  }

  const hourlyMatch = normalized.match(/cada\s+(\d+)\s+hora/);
  if (hourlyMatch) {
    const hours = Number(hourlyMatch[1]);
    return hours > 0 ? 24 / hours : null;
  }

  const minuteMatch = normalized.match(/cada\s+(\d+)\s+minuto/);
  if (minuteMatch) {
    const minutes = Number(minuteMatch[1]);
    return minutes > 0 ? (24 * 60) / minutes : null;
  }

  return null;
}

function buildNodes(props: IntegrationCanvasProps): CanvasNode[] {
  const selectedTools = props.coreTools
    .map((tool) => tool.trim())
    .filter(Boolean)
    .map((tool) => ({
      label: tool,
      kind: TOOL_KINDS[tool] ?? "oic",
    }));

  const orderedTools = TOOL_ORDER.flatMap((kind) =>
    selectedTools
      .filter((tool) => tool.kind === kind)
      .map((tool) => ({
        key: `${kind}-${tool.label}`,
        label: tool.label,
        subtitle: null,
        kind,
      })),
  );

  return [
    {
      key: `source-${props.sourceSystem}`,
      label: props.sourceSystem,
      subtitle: props.sourceTechnology,
      kind: "system",
    },
    ...orderedTools,
    {
      key: `destination-${props.destinationSystem ?? "unknown"}`,
      label: props.destinationSystem ?? "Unknown Destination",
      subtitle: props.destinationTechnology,
      kind: "system",
    },
  ];
}

export function IntegrationCanvas(props: IntegrationCanvasProps): JSX.Element {
  const nodes = buildNodes(props);
  const billingMsgs = estimateBillingMsgs(props.payloadKb);
  const executionsPerDay = estimateExecutionsPerDay(props.frequency);
  const monthlyBilling =
    billingMsgs !== null && executionsPerDay !== null ? Math.ceil(billingMsgs * executionsPerDay * 30) : null;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        {nodes.map((node, index) => {
          const colors = KIND_COLORS[node.kind];
          return (
            <div key={node.key} className="flex items-center gap-3">
              <div
                className="min-w-[10rem] rounded-2xl border px-4 py-3 text-center shadow-sm"
                style={{
                  backgroundColor: colors.bg,
                  borderColor: colors.border,
                }}
              >
                <div className="text-lg">{colors.icon}</div>
                <p className="mt-2 text-sm font-semibold text-slate-900">{node.label}</p>
                <p className="mt-1 text-xs text-slate-700">{node.subtitle ?? " "}</p>
              </div>
              {index < nodes.length - 1 ? (
                <span className="text-xl font-semibold text-[var(--color-accent)]">→</span>
              ) : null}
            </div>
          );
        })}
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="app-card-muted p-4 text-sm">
          <span className="font-medium text-[var(--color-text-primary)]">Input</span>
          <p className="mt-2 text-[var(--color-text-secondary)]">{props.payloadKb ?? "?"} KB / execution</p>
          <p className="text-[var(--color-text-secondary)]">{props.frequency ?? "unknown frequency"}</p>
        </div>
        <div className="app-card-muted p-4 text-sm">
          <span className="font-medium text-[var(--color-text-primary)]">OIC Processing</span>
          <p className="mt-2 text-[var(--color-text-secondary)]">
            {billingMsgs ?? "?"} billing msg{billingMsgs === 1 ? "" : "s"} / execution
          </p>
          <p className="text-[var(--color-text-secondary)]">Pattern: {props.selectedPattern ?? "unassigned"}</p>
          <p className="text-[var(--color-text-secondary)]">
            Estimated OIC msgs/month: {monthlyBilling ?? "unknown"}
          </p>
        </div>
        <div className="app-card-muted p-4 text-sm">
          <span className="font-medium text-[var(--color-text-primary)]">Output</span>
          <p className="mt-2 text-[var(--color-text-secondary)]">→ {props.destinationSystem ?? "unknown"}</p>
          <p className="text-[var(--color-text-secondary)]">{props.destinationTechnology ?? ""}</p>
          <p className="text-[var(--color-text-secondary)]">{props.patternCategory ?? "No pattern category"}</p>
        </div>
      </div>
    </div>
  );
}
