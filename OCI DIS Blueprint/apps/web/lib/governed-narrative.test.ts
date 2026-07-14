/* Verifies bounded, scan-friendly formatting for governed model narratives. */

import { describe, expect, it } from "vitest";

import { parseGovernedNarrative } from "./governed-narrative";

describe("parseGovernedNarrative", () => {
  it("turns bullets and numbered actions into scan-friendly blocks", () => {
    const blocks = parseGovernedNarrative("Direct answer.\n- Inspect QA rows\n2. Recalculate the project");

    expect(blocks.map((block) => block.kind)).toEqual(["paragraph", "bullet", "ordered"]);
    expect(blocks[1].text).toBe("Inspect QA rows");
  });

  it("breaks a malformed one-line markdown table into bounded content", () => {
    const raw = "Architecture Decision Brief | Topic | Current Status | Evidence | Recommended Action | |---|---|---|---| Canvas | 246 warnings | EV-005 | Resolve blockers";
    const blocks = parseGovernedNarrative(raw);

    expect(blocks.length).toBeGreaterThan(4);
    expect(blocks.every((block) => !block.text.includes("|"))).toBe(true);
    expect(blocks.some((block) => block.kind === "heading" && block.text === "Canvas")).toBe(true);
    expect(blocks.some((block) => block.text === "Current Status: 246 warnings")).toBe(true);
  });

  it("caps unexpectedly verbose provider output", () => {
    const blocks = parseGovernedNarrative(Array.from({ length: 40 }, (_, index) => `Line ${index}`).join("\n"));

    expect(blocks).toHaveLength(25);
    expect(blocks.at(-1)?.kind).toBe("notice");
  });
});
