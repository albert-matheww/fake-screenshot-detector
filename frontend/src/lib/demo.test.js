import { describe, it, expect } from "vitest";
import { DEMO_FIXTURES, getDemoKey, receiptWordBoxes, RECEIPT } from "./demo.js";
import { normalizeResult } from "./result.js";

describe("getDemoKey", () => {
  it("accepts only known demo names", () => {
    expect(getDemoKey("?demo=evidence")).toBe("evidence");
    expect(getDemoKey("?demo=no_evidence")).toBe("no_evidence");
    expect(getDemoKey("?demo=constructor")).toBeNull();
    expect(getDemoKey("?demo=nope")).toBeNull();
    expect(getDemoKey("")).toBeNull();
  });
});

describe("fixtures", () => {
  it.each(Object.entries(DEMO_FIXTURES))("%s fixture is a valid v2 result", (key, fx) => {
    const view = normalizeResult(fx);
    expect(view).not.toBeNull();
    expect(view.regions).toHaveLength(fx.regions.length);
    expect(view.limitations).toEqual(fx.limitations);
  });

  it("covers all four verdicts", () => {
    expect(Object.values(DEMO_FIXTURES).map((f) => f.verdict).sort()).toEqual(
      ["evidence_of_editing", "inconclusive", "no_evidence", "suspicious"],
    );
  });

  it("keeps region boxes inside the image", () => {
    for (const fx of Object.values(DEMO_FIXTURES)) {
      for (const r of fx.regions) {
        expect(r.x + r.w).toBeLessThanOrEqual(fx.image.width);
        expect(r.y + r.h).toBeLessThanOrEqual(fx.image.height);
      }
    }
  });

  it("places fixture regions on words of the generated receipt", () => {
    const words = receiptWordBoxes();
    expect(RECEIPT.width).toBe(DEMO_FIXTURES.evidence.image.width);
    for (const r of DEMO_FIXTURES.evidence.regions) {
      const hit = words.some(
        (w) => r.x < w.x + w.w && w.x < r.x + r.w && r.y < w.y + w.h && w.y < r.y + r.h,
      );
      expect(hit, `region "${r.text}" overlaps a receipt word`).toBe(true);
    }
    // The headline example: "$399.901" sits on the Total row.
    const total = DEMO_FIXTURES.evidence.regions.find((r) => r.text === "$399.901");
    const totalRow = RECEIPT.rows.find((row) => row.label === "Total");
    expect(total.y).toBe(totalRow.top + 20);
  });
});
