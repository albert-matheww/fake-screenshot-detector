import { describe, it, expect, vi } from "vitest";
import { render, screen, within, fireEvent } from "@testing-library/react";
import AnalysisResults from "./AnalysisResults.jsx";
import { DEMO_FIXTURES } from "../lib/demo.js";

const renderFx = (key, props = {}) =>
  render(<AnalysisResults result={DEMO_FIXTURES[key]} imageUrl={null} onReset={() => {}} {...props} />);

describe("AnalysisResults", () => {
  it.each([
    ["evidence", "Evidence of editing found", 4, 3],
    ["suspicious", "Suspicious - review recommended", 2, 1],
    ["no_evidence", "No evidence of editing found", 0, 0],
    ["inconclusive", "Not enough readable text to analyse", 0, 0],
  ])("renders the %s state", (key, label, overlayCount, findingCount) => {
    const { container } = renderFx(key);
    expect(screen.getByRole("heading", { level: 2, name: label })).toBeInTheDocument();
    expect(screen.queryAllByTestId("region-box")).toHaveLength(overlayCount);
    expect(screen.queryAllByTestId("region-card")).toHaveLength(overlayCount);
    expect(screen.queryAllByTestId("finding")).toHaveLength(findingCount);
    expect(container.querySelector(".verdict")).toHaveClass(
      `verdict--${key}`,
    );
  });

  it.each(Object.keys(DEMO_FIXTURES))("always shows every limitation verbatim (%s)", (key) => {
    renderFx(key);
    const panel = screen.getByTestId("limitations");
    expect(within(panel).getByText(/what this cannot tell you/i)).toBeInTheDocument();
    for (const text of DEMO_FIXTURES[key].limitations) {
      expect(within(panel).getByText(text)).toBeInTheDocument();
    }
  });

  it.each(Object.keys(DEMO_FIXTURES))("never uses 'authentic' / 'genuine' / 'verified' wording (%s)", (key) => {
    const { container } = renderFx(key);
    expect(container.textContent).not.toMatch(/authentic|genuine|verified|\breal\b|is safe/i);
  });

  it("says no contradictions when there are no findings, instead of hiding the section", () => {
    renderFx("no_evidence");
    expect(screen.getByText(/no rule-based contradictions found/i)).toBeInTheDocument();
  });

  it("lists severity chips and reasons for the evidence fixture", () => {
    renderFx("evidence");
    const findings = screen.getAllByTestId("finding");
    expect(within(findings[0]).getByText(/high/i)).toBeInTheDocument();
    expect(screen.getByText(/the word "\$399\.901" looks edited/i)).toBeInTheDocument();
    expect(within(screen.getAllByTestId("region-card")[0]).getByText("93%")).toBeInTheDocument();
  });

  it("positions overlay boxes as percentages of the original image", () => {
    renderFx("evidence");
    const box = screen.getAllByTestId("region-box")[0]; // $399.901 @ 514,1080 176x44 on 750x1334, +3px pad
    expect(parseFloat(box.style.left)).toBeCloseTo(((514 - 3) / 750) * 100, 3);
    expect(parseFloat(box.style.top)).toBeCloseTo(((1080 - 3) / 1334) * 100, 3);
    expect(parseFloat(box.style.width)).toBeCloseTo(((176 + 6) / 750) * 100, 3);
    expect(parseFloat(box.style.height)).toBeCloseTo(((44 + 6) / 1334) * 100, 3);
  });

  it("links hover/click between boxes and cards", () => {
    renderFx("evidence");
    const boxes = screen.getAllByTestId("region-box");
    const cards = screen.getAllByTestId("region-card");

    fireEvent.mouseEnter(boxes[1]);
    expect(cards[1]).toHaveClass("is-active");
    expect(boxes[1]).toHaveClass("is-active");
    expect(boxes[0]).toHaveClass("is-dim");
    fireEvent.mouseLeave(boxes[1]);
    expect(cards[1]).not.toHaveClass("is-active");

    fireEvent.mouseEnter(cards[2]);
    expect(boxes[2]).toHaveClass("is-active");
    fireEvent.mouseLeave(cards[2]);

    fireEvent.click(boxes[0]);
    expect(cards[0]).toHaveClass("is-selected");
    fireEvent.click(within(cards[3]).getByRole("button"));
    expect(boxes[3]).toHaveClass("is-selected");
    expect(cards[0]).not.toHaveClass("is-selected");
  });

  it("exposes the gauge with both tier boundaries", () => {
    renderFx("suspicious");
    const meter = screen.getByRole("meter");
    expect(meter).toHaveAttribute("aria-valuenow", "52");
    expect(meter.getAttribute("aria-valuetext")).toMatch(/40%/);
    expect(meter.getAttribute("aria-valuetext")).toMatch(/70%/);
  });

  it("shows stats and offers a JSON report + new scan", () => {
    const onReset = vi.fn();
    renderFx("evidence", { onReset });
    expect(screen.getByText("Words read")).toBeInTheDocument();
    expect(screen.getByText("38")).toBeInTheDocument();
    expect(screen.getByText("8.4 s")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /json report/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /new scan/i }));
    expect(onReset).toHaveBeenCalled();
  });

  it("can hide the markers", () => {
    renderFx("evidence");
    fireEvent.click(screen.getByLabelText(/show markers/i));
    expect(screen.queryAllByTestId("region-box")).toHaveLength(0);
  });

  it("falls back to built-in limitations if the backend sends none", () => {
    render(<AnalysisResults result={{ ...DEMO_FIXTURES.no_evidence, limitations: [] }} imageUrl={null} />);
    expect(within(screen.getByTestId("limitations")).getAllByRole("listitem").length).toBeGreaterThan(0);
  });
});
