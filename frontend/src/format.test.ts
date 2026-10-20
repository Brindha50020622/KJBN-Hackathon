import { describe, expect, it } from "vitest";

import { fillMissingDays, formatRupees, isRangeValid } from "./format";

describe("formatRupees", () => {
  it.each([
    [0, "₹0.00"],
    [5, "₹0.05"],
    [104000, "₹1,040.00"],
    [1234567800, "₹1,23,45,678.00"],
    [-50, "-₹0.50"],
    [-54000, "-₹540.00"],
  ])("%i paise", (paise, text) => {
    expect(formatRupees(paise)).toBe(text);
  });
});

describe("isRangeValid", () => {
  it("accepts empty and ordered ranges", () => {
    expect(isRangeValid("", "")).toBe(true);
    expect(isRangeValid("2026-10-11", "")).toBe(true);
    expect(isRangeValid("2026-10-11", "2026-10-11")).toBe(true);
  });
  it("rejects from after to", () => {
    expect(isRangeValid("2026-10-12", "2026-10-11")).toBe(false);
  });
});

describe("fillMissingDays", () => {
  it("returns nothing for no days", () => {
    expect(fillMissingDays([])).toEqual([]);
  });
  it("keeps a single day", () => {
    expect(fillMissingDays([{ day: "2026-10-11", revenue_paise: 5 }])).toEqual([
      { day: "2026-10-11", revenue_paise: 5 },
    ]);
  });
  it("adds zero rows across a month end", () => {
    const result = fillMissingDays([
      { day: "2026-10-31", revenue_paise: 100 },
      { day: "2026-11-02", revenue_paise: 300 },
    ]);
    expect(result).toEqual([
      { day: "2026-10-31", revenue_paise: 100 },
      { day: "2026-11-01", revenue_paise: 0 },
      { day: "2026-11-02", revenue_paise: 300 },
    ]);
  });
});