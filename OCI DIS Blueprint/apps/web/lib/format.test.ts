/* Focused coverage for English US display normalization helpers. */

import { describe, expect, it } from "vitest";

import { displayGovernedText, displaySourceFieldLabel, displayUiValue } from "./format";

describe("format display helpers", () => {
  it("renders source lineage field labels in English US", () => {
    expect(displaySourceFieldLabel("Alcance Inicial")).toBe("Initial Scope");
    expect(displaySourceFieldLabel("# Destinos")).toBe("# Destinations");
    expect(displaySourceFieldLabel("Calendarización")).toBe("Scheduling");
    expect(displaySourceFieldLabel("Comentarios / Observaciones")).toBe("Comments / Observations");
    expect(displaySourceFieldLabel("Herramientas Core Cuantificables / Volumétricas")).toBe(
      "Quantifiable / Volumetric Core Tools",
    );
  });

  it("keeps imported source values English-normalized in the UI", () => {
    expect(displayUiValue("Sí")).toBe("Yes");
    expect(displayUiValue("Medio")).toBe("Medium");
    expect(displayUiValue("En Revisión")).toBe("In Review");
    expect(displayUiValue("Tiempo Real")).toBe("Real Time");
  });

  it("renders governed dictionary descriptions in English US", () => {
    expect(displayGovernedText("Tipo: Programada. Usar para: Frecuencia estándar. Estatus: Válido.")).toBe(
      "Type: Scheduled. Use for: standard frequency. Status: Valid.",
    );
  });
});
