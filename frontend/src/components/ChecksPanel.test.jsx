import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import ChecksPanel from "./ChecksPanel.jsx";
import { normalizeResult } from "../lib/result.js";

const checks = [
  { id: "file_metadata", name: "File metadata", status: "clear", findings: [], why: "", gate: { status: "live" } },
  { id: "layout_grid", name: "Number column spacing", status: "not_applicable", findings: [], why: "No evenly laid-out column of at least eight numbers was found.", gate: { status: "advisory", reason: "applicable on only 2 genuine real screenshots" } },
  { id: "rendering", name: "Word rendering consistency", status: "finding", findings: [{ message: "The word X is rendered differently." }], why: "", gate: { status: "advisory", reason: "false-alarm rate 3/23" } },
];

describe("ChecksPanel", () => {
  it("shows every check with what it did and whether it counts", () => {
    render(<ChecksPanel routing={{ label: "Payment receipt or transfer", status: "tentative", router_validated: false }}
      checks={checks} coverage={{ live_clear: 1, live_findings: 0, advisory_findings: 1, not_applicable: 1 }} verifySteps={["Ask the issuer."]} />);
    const rows = screen.getAllByTestId("check");
    expect(rows).toHaveLength(3);
    expect(within(rows[0]).getByText("Found nothing")).toBeInTheDocument();
    expect(within(rows[0]).getByText("counts toward verdict")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Could not examine")).toBeInTheDocument();
    expect(within(rows[2]).getByText("advisory, not counted")).toBeInTheDocument();
    expect(screen.getByTestId("routing").textContent).toMatch(/not yet been validated/);
    expect(screen.getByTestId("verify-steps")).toBeInTheDocument();
  });

  it("a check that could not examine the screenshot is never shown as a pass", () => {
    render(<ChecksPanel routing={null} checks={[checks[1]]} coverage={null} verifySteps={[]} />);
    expect(screen.queryByText("Found nothing")).toBeNull();
  });

  it("renders nothing for an old-style result without routing or checks", () => {
    const { container } = render(<ChecksPanel routing={null} checks={[]} coverage={null} verifySteps={[]} />);
    expect(container.firstChild).toBeNull();
  });
});

describe("normalizeResult v3 fields", () => {
  it("passes routing, checks and coverage through and tolerates their absence", () => {
    const base = { verdict: "inconclusive", risk_score: 0.4, reasons: [], regions: [], findings: [], limitations: ["a"], image: { width: 1, height: 1 } };
    const v = normalizeResult({ ...base, routing: { type: "chat" }, checks, coverage: { live_clear: 1 }, verify_steps: ["x"] });
    expect(v.routing.type).toBe("chat");
    expect(v.checks).toHaveLength(3);
    expect(v.verifySteps).toEqual(["x"]);
    const old = normalizeResult(base);
    expect(old.routing).toBeNull();
    expect(old.checks).toEqual([]);
  });
});
