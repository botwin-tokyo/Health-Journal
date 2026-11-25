import { describe, it, expect } from "vitest";
import { dateLabel, shiftDate, decimal } from "./display";
describe("clinical presentation", () => {
  it("preserves date-only membership through DST and leap day", () => {
    expect(dateLabel("2026-11-07")).toBe("Nov 07, 2026");
    expect(shiftDate("2024-03-01", -1)).toBe("2024-02-29");
    expect(shiftDate("2026-03-08", 1)).toBe("2026-03-09");
  });
  it("never turns missing or invalid values into zero", () => {
    expect(decimal("0")).toBe(0);
    expect(decimal("")).toBeNull();
    expect(decimal(null)).toBeNull();
    expect(decimal("3.820")).toBe(3.82);
  });
});
