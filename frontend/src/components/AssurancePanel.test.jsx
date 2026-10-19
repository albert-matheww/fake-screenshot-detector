import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import AssurancePanel from "./AssurancePanel.jsx";
import { normalizeAssurance } from "../lib/result.js";

const ladder = (reached) => [
  { level: 0, label: "Unverified", requirement: "The screenshot alone.", reached: true },
  { level: 1, label: "No contradiction found (still unverified)", requirement: "Consistent with itself.", reached: reached >= 1 },
  { level: 2, label: "Consistent with an independent source", requirement: "A second source agrees.", reached: reached >= 2 },
  { level: 3, label: "Verified against signed data", requirement: "Not available yet.", reached: false },
];
const raw = (level, status, reasons = []) => ({ level, label: ladder(level)[level].label, status, reasons, next_step: "Add a second source.", ladder: ladder(level), never_genuine: "No level means the screenshot is genuine." });

describe("AssurancePanel", () => {
  it("shows all four levels and marks the current one", () => {
    render(<AssurancePanel assurance={normalizeAssurance(raw(1, "consistent", ["1 content check found no contradiction."]))} />);
    expect(screen.getByRole("heading", { name: /level 1 of 3/i })).toBeInTheDocument();
    const steps = screen.getAllByTestId("ladder-step");
    expect(steps).toHaveLength(4);
    expect(steps[1].className).toMatch(/is-current/);
    expect(steps[2].className).not.toMatch(/is-reached/);
    expect(screen.getByText(/Add a second source/)).toBeInTheDocument();
  });

  it("never offers a level above 2 as reached, and a conflict stays at level 0", () => {
    render(<AssurancePanel assurance={normalizeAssurance(raw(0, "conflict", ["The second source and the screenshot disagree on: refs."]))} />);
    const steps = screen.getAllByTestId("ladder-step");
    expect(steps[3].className).not.toMatch(/is-reached/);
    expect(screen.getByTestId("assurance-panel").className).toMatch(/assurance--blocked/);
    expect(screen.getByTestId("assurance-reasons")).toHaveTextContent("disagree");
  });

  it("renders nothing without assurance data (older servers)", () => {
    const { container } = render(<AssurancePanel assurance={normalizeAssurance(undefined)} />);
    expect(container).toBeEmptyDOMElement();
  });
});
