/* Verifies bounded, scan-friendly formatting for governed model narratives. */

import { describe, expect, it } from "vitest";

import { parseGovernedNarrative } from "./governed-narrative";

describe("parseGovernedNarrative", () => {
  it("turns bullets and numbered actions into scan-friendly blocks", () => {
    const blocks = parseGovernedNarrative("Direct answer.\n- Inspect QA rows\n2. Recalculate the project");

    expect(blocks.map((block) => block.kind)).toEqual(["paragraph", "list", "list"]);
    expect(blocks[1]).toMatchObject({ kind: "list", ordered: false, items: ["Inspect QA rows"] });
    expect(blocks[2]).toMatchObject({ kind: "list", ordered: true, start: 2, items: ["Recalculate the project"] });
  });

  it("repairs orphan markers and groups consecutive steps into one ordered list", () => {
    const blocks = parseGovernedNarrative(
      "Start with a governed project.\n\n1.\nCreate or select a project\n\n2. Open Capture\n\n3) Add the first integration",
    );

    expect(blocks).toHaveLength(2);
    expect(blocks[1]).toEqual({
      kind: "list",
      ordered: true,
      start: 1,
      items: ["Create or select a project", "Open Capture", "Add the first integration"],
    });
  });

  it("breaks a malformed one-line markdown table into bounded content", () => {
    const raw = "Architecture Decision Brief | Topic | Current Status | Evidence | Recommended Action | |---|---|---|---| Canvas | 246 warnings | EV-005 | Resolve blockers";
    const blocks = parseGovernedNarrative(raw);

    expect(blocks.length).toBeGreaterThan(4);
    expect(blocks.every((block) => block.kind === "list" ? block.items.every((item) => !item.includes("|")) : !block.text.includes("|"))).toBe(true);
    expect(blocks.some((block) => block.kind === "heading" && block.text === "Canvas")).toBe(true);
    expect(blocks.some((block) => block.kind !== "list" && block.text === "Current Status: 246 warnings")).toBe(true);
  });

  it("caps unexpectedly verbose provider output", () => {
    const blocks = parseGovernedNarrative(Array.from({ length: 40 }, (_, index) => `Line ${index}`).join("\n"));

    expect(blocks).toHaveLength(25);
    expect(blocks.at(-1)?.kind).toBe("notice");
  });
});
