/* Focused state-machine tests for pricing synchronization and BOM polling. */

import { describe, expect, it } from "vitest";

import { isBomJobTerminal, isPriceSyncTerminal } from "../lib/types";

describe("pricing and BOM job terminal states", () => {
  it.each(["queued", "pending", "running"])("keeps polling active price state %s", (status) => {
    expect(isPriceSyncTerminal(status)).toBe(false);
  });

  it.each(["completed", "failed"])("stops polling terminal price state %s", (status) => {
    expect(isPriceSyncTerminal(status)).toBe(true);
  });

  it.each(["queued", "pending", "running"])("keeps polling active BOM state %s", (status) => {
    expect(isBomJobTerminal(status)).toBe(false);
  });

  it.each(["completed", "failed"])("stops polling terminal BOM state %s", (status) => {
    expect(isBomJobTerminal(status)).toBe(true);
  });
});
