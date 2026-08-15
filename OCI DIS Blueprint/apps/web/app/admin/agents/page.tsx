/* Governed OCI Generative AI agent catalog and execution operations. */

import { AgentOperations } from "@/components/agent-operations";
import { api } from "@/lib/api";

export default async function AgentOperationsPage(): Promise<JSX.Element> {
  const [definitions, providerStatus, providerMetrics, valueMetrics, runList] = await Promise.all([
    api.listAgents(),
    api.getAgentProviderStatus(),
    api.getAgentProviderMetrics(),
    api.getAgentValueMetrics(),
    api.listAgentRuns({ limit: 50 }).catch(() => ({ runs: [], total: 0 })),
  ]);
  return (
    <div className="console-page">
      <section className="console-hero">
        <div>
          <p className="app-kicker">Governed OCI Generative AI</p>
          <h1 className="mt-2 text-4xl font-semibold text-[var(--color-text-primary)]">Agent Operations</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">Monitor the Docker agent runtime, authorized tools, evidence-backed outcomes, and terminal execution states. Deterministic application services remain authoritative.</p>
        </div>
      </section>
      <AgentOperations
        definitions={definitions}
        providerStatus={providerStatus}
        initialMetrics={providerMetrics}
        initialValueMetrics={valueMetrics}
        initialRuns={runList.runs}
      />
    </div>
  );
}
