import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ComparePanel from "./ComparePanel.jsx";

vi.mock("../services/api.js", async (orig) => {
  const actual = await orig();
  return { ...actual, compareImages: vi.fn() };
});
import { compareImages } from "../services/api.js";

const file = (name) => new File(["x"], name, { type: "image/png" });

describe("ComparePanel", () => {
  it("keeps the button disabled until both images are chosen, then shows what differs", async () => {
    URL.createObjectURL = vi.fn(() => "blob:x");
    URL.revokeObjectURL = vi.fn();
    compareImages.mockResolvedValue({
      status: "differences_found", message: "The suspect image differs from the original.", caution: "",
      regions: [{ x: 5, y: 5, w: 20, h: 10, text: "2421 -> 24210", reasons: ["pixels differ"] }],
      text_changes: [{ type: "changed", original: "2421", suspect: "24210" }], image: { width: 100, height: 100 },
    });
    render(<ComparePanel />);
    const btn = screen.getByRole("button", { name: "Compare" });
    expect(btn).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Original/), { target: { files: [file("o.png")] } });
    expect(btn).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Suspect/), { target: { files: [file("s.png")] } });
    expect(btn).toBeEnabled();
    fireEvent.click(btn);
    await waitFor(() => expect(screen.getByTestId("compare-result")).toBeInTheDocument());
    expect(screen.getByText("Differences found")).toBeInTheDocument();
    expect(screen.getByText("24210")).toBeInTheDocument();
  });

  it("shows an error message when the comparison fails", async () => {
    URL.createObjectURL = vi.fn(() => "blob:x");
    compareImages.mockRejectedValue({ kind: "invalid_image", message: "A file could not be read as an image." });
    render(<ComparePanel />);
    fireEvent.change(screen.getByLabelText(/Original/), { target: { files: [file("o.png")] } });
    fireEvent.change(screen.getByLabelText(/Suspect/), { target: { files: [file("s.png")] } });
    fireEvent.click(screen.getByRole("button", { name: "Compare" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("could not be read"));
  });
});
