/* Unit coverage for execution-state indicator colors in Agent Operations. */

import { describe, expect, it } from "vitest";

import { agentExecutionIndicatorTone } from "../lib/agent-status";
import type { AgentRun } from "../lib/types";

function runState(
  status: AgentRun["status"],
  providerStatus?: string,
): Pick<AgentRun, "status" | "result"> {
  return {
    status,
    result: providerStatus ? { provider_status: providerStatus } : null,
  };
}

describe("agent execution indicator tone", () => {
  it("uses green only for a completed run with completed provider execution", () => {
    expect(agentExecutionIndicatorTone(runState("completed", "completed"))).toBe("success");
  });

  it.each(["skipped", "not_configured", "deterministic", undefined])(
    "uses yellow for a completed run with provider state %s",
    (providerStatus) => {
      expect(agentExecutionIndicatorTone(runState("completed", providerStatus))).toBe("warning");
    },
  );

  it.each(["pending", "running", "waiting_approval"] as const)(
    "uses yellow while run state %s is active",
    (status) => {
      expect(agentExecutionIndicatorTone(runState(status))).toBe("warning");
    },
  );

  it("uses red when provider execution failed even if deterministic work completed", () => {
    expect(agentExecutionIndicatorTone(runState("completed", "failed"))).toBe("error");
  });

  it.each(["failed", "cancelled"] as const)("uses red for terminal run state %s", (status) => {
    expect(agentExecutionIndicatorTone(runState(status))).toBe("error");
  });
});
