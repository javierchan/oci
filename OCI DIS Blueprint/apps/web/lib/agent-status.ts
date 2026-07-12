/* Pure presentation policy for Agent Operations execution indicators. */

import type { AgentRun } from "./types";

export type AgentExecutionIndicatorTone = "success" | "warning" | "error";

export function agentExecutionIndicatorTone(
  run: Pick<AgentRun, "status" | "result">,
): AgentExecutionIndicatorTone {
  const providerStatus = run.result?.provider_status?.toLowerCase();
  if (run.status === "failed" || run.status === "cancelled" || providerStatus === "failed") {
    return "error";
  }
  if (run.status === "completed" && providerStatus === "completed") {
    return "success";
  }
  return "warning";
}
