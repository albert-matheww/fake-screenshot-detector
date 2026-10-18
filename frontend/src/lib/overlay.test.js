import { describe, it, expect } from "vitest";
import { scaleRegion, regionToPercentBox, clamp } from "./overlay.js";

const image = { width: 1000, height: 2000 };

describe("scaleRegion", () => {
  it("is the identity when displayed size equals image size", () => {
    expect(scaleRegion({ x: 10, y: 20, w: 30, h: 40 }, image, image)).toEqual({
      left: 10, top: 20, width: 30, height: 40,
    });
  });

  it("scales each axis independently", () => {
    const box = scaleRegion({ x: 100, y: 200, w: 300, h: 400 }, image, { width: 500, height: 500 });
    expect(box.left).toBeCloseTo(50);
    expect(box.top).toBeCloseTo(50);
    expect(box.width).toBeCloseTo(150);
    expect(box.height).toBeCloseTo(100);
  });

  it("keeps boxes proportional when the display size changes (resize)", () => {
    const r = { x: 250, y: 500, w: 100, h: 100 };
    const small = scaleRegion(r, image, { width: 200, height: 400 });
    const large = scaleRegion(r, image, { width: 800, height: 1600 });
    expect(large.left / small.left).toBeCloseTo(4);
    expect(large.width / small.width).toBeCloseTo(4);
    expect(large.top / small.top).toBeCloseTo(4);
  });

  it("applies padding in original pixels and clamps to the image", () => {
    const box = scaleRegion({ x: 2, y: 1990, w: 996, h: 10 }, image, image, 5);
    expect(box).toEqual({ left: 0, top: 1985, width: 1000, height: 15 });
  });

  it("returns null for empty / invalid input", () => {
    expect(scaleRegion({ x: 0, y: 0, w: 0, h: 10 }, image, image)).toBeNull();
    expect(scaleRegion({ x: 5000, y: 0, w: 10, h: 10 }, image, image)).toBeNull();
    expect(scaleRegion({ x: 0, y: 0, w: 10, h: 10 }, { width: 0, height: 0 }, image)).toBeNull();
    expect(scaleRegion({ x: NaN, y: 0, w: 10, h: 10 }, image, image)).toBeNull();
    expect(scaleRegion(null, image, image)).toBeNull();
  });
});

describe("regionToPercentBox", () => {
  it("expresses the box as percentages of the image", () => {
    expect(regionToPercentBox({ x: 100, y: 500, w: 250, h: 100 }, image)).toEqual({
      left: "10%", top: "25%", width: "25%", height: "5%",
    });
  });
});

describe("clamp", () => {
  it("bounds values", () => {
    expect(clamp(5, 0, 3)).toBe(3);
    expect(clamp(-1, 0, 3)).toBe(0);
    expect(clamp(2, 0, 3)).toBe(2);
  });
});
