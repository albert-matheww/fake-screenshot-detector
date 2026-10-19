import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ReconcilePanel from "./ReconcilePanel.jsx";

vi.mock("../services/api.js", async (orig) => {
  const actual = await orig();
  return { ...actual, reconcileImages: vi.fn() };
});
import { reconcileImages } from "../services/api.js";

const file = (name) => new File(["x"], name, { type: "image/png" });
const ladder = [0, 1, 2, 3].map((l) => ({ level: l, label: `L${l}`, requirement: "r", reached: l === 0 }));
const base = {
  verdict: "inconclusive", verdict_label: "Inconclusive - verify with the issuer", risk_score: 0.42, reasons: [], regions: [], findings: [],
  limitations: ["x"], checks: [], image: { width: 100, height: 100, format: "PNG" }, stats: {}, meta: {},
  assurance: { level: 0, label: "Unverified", status: "conflict", reasons: ["The second source and the screenshot disagree on: refs."], next_step: "n", ladder, never_genuine: "" },
  reconcile: { status: "conflict", differs: ["refs"], matched: [], rows: [{ kind: "refs", status: "differs", source: ["628599995678"], screenshot: ["628512345678"] }] },
};

describe("ReconcilePanel", () => {
  it("needs a screenshot and a second source before it can run", () => {
    URL.createObjectURL = vi.fn(() => "blob:x");
    URL.revokeObjectURL = vi.fn();
    render(<ReconcilePanel />);
    const btn = screen.getByRole("button", { name: /Check against the second source/ });
    expect(btn).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Screenshot to check/), { target: { files: [file("a.png")] } });
    expect(btn).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/as text/), { target: { value: "Rs 500 on 12-10-2026" } });
    expect(btn).toBeEnabled();
  });

  it("sends the chosen type and text, and shows a conflict with the differing values", async () => {
    URL.createObjectURL = vi.fn(() => "blob:x");
    URL.revokeObjectURL = vi.fn();
    reconcileImages.mockResolvedValue(base);
    render(<ReconcilePanel />);
    fireEvent.change(screen.getByLabelText(/Screenshot to check/), { target: { files: [file("a.png")] } });
    fireEvent.change(screen.getByLabelText(/kind of screenshot/), { target: { value: "payment_receipt" } });
    fireEvent.change(screen.getByLabelText(/as text/), { target: { value: "Ref 628599995678" } });
    fireEvent.click(screen.getByRole("button", { name: /Check against the second source/ }));
    await waitFor(() => expect(screen.getByTestId("reconcile-result")).toBeInTheDocument());
    expect(reconcileImages.mock.calls[0][1]).toMatchObject({ type: "payment_receipt", sourceText: "Ref 628599995678" });
    expect(screen.getByTestId("reconcile-status")).toHaveTextContent(/disagree/);
    expect(screen.getByTestId("facts-table")).toHaveTextContent("628599995678");
    expect(screen.getByTestId("facts-table")).toHaveTextContent("628512345678");
    expect(screen.getByTestId("assurance-panel")).toBeInTheDocument();
  });

  it("shows an error when the request fails", async () => {
    URL.createObjectURL = vi.fn(() => "blob:x");
    URL.revokeObjectURL = vi.fn();
    reconcileImages.mockRejectedValue({ kind: "server", message: "Internal error during reconciliation." });
    render(<ReconcilePanel />);
    fireEvent.change(screen.getByLabelText(/Screenshot to check/), { target: { files: [file("a.png")] } });
    fireEvent.change(screen.getByLabelText(/as text/), { target: { value: "Rs 5.00" } });
    fireEvent.click(screen.getByRole("button", { name: /Check against the second source/ }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Internal error"));
  });
});
