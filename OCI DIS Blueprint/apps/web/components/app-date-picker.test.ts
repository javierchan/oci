/* Deterministic coverage for the theme-aware App date picker calendar model. */

import { describe, expect, it } from "vitest";

import { buildCalendarDays, parseIsoDate, toIsoDate } from "./app-date-picker";

describe("app date picker", () => {
  it("round-trips valid local ISO dates without timezone movement", () => {
    const date = parseIsoDate("2026-06-01");
    expect(date).not.toBeNull();
    expect(date ? toIsoDate(date) : null).toBe("2026-06-01");
    expect(parseIsoDate("2026-02-30")).toBeNull();
  });

  it("builds a stable six-week month grid with adjacent days", () => {
    const days = buildCalendarDays(new Date(2026, 5, 1), new Date(2026, 5, 15));
    expect(days).toHaveLength(42);
    expect(days[0]?.iso).toBe("2026-05-31");
    expect(days[41]?.iso).toBe("2026-07-11");
    expect(days.find((day) => day.isToday)?.iso).toBe("2026-06-15");
    expect(days.filter((day) => day.inCurrentMonth)).toHaveLength(30);
  });
});
