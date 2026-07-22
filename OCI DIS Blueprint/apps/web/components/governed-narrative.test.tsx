/* Verifies safe rich rendering for the contextual assistant. */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { GovernedNarrative } from "./governed-narrative";

describe("GovernedNarrative", () => {
  it("renders compact tables, emphasis, and same-origin next actions", () => {
    const html = renderToStaticMarkup(
      <GovernedNarrative
        content={[
          "**Direct answer:** The governed BOM is ready for review.",
          "",
          "| Product | Monthly cost |",
          "|---|---:|",
          "| OIC Enterprise | USD 2,400 |",
          "",
          "**Next action:** [Open BOM & Cost](/projects/project-1/bom)",
        ].join("\n")}
      />,
    );

    expect(html).toContain("<strong");
    expect(html).toContain("<table");
    expect(html).toContain("OIC Enterprise");
    expect(html).toContain('href="/projects/project-1/bom"');
  });

  it("does not make an external Markdown URL clickable", () => {
    const html = renderToStaticMarkup(
      <GovernedNarrative content="Read [an external page](https://example.com)." />,
    );

    expect(html).toContain("Read an external page.");
    expect(html).not.toContain("https://example.com");
    expect(html).not.toContain("<a");
  });
});
