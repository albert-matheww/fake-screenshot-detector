import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "./App.jsx";

vi.mock("./services/api.js", async (orig) => {
  const actual = await orig();
  return { ...actual, getStatus: vi.fn(), analyzeImage: vi.fn() };
});
import { getStatus, analyzeImage } from "./services/api.js";

afterEach(() => {
  window.history.replaceState({}, "", "/");
  vi.clearAllMocks();
});

describe("App demo mode", () => {
  it("renders the fixture immediately without calling the backend", () => {
    window.history.replaceState({}, "", "/?demo=evidence");
    render(<App />);
    expect(screen.getByRole("heading", { level: 2, name: /evidence of editing found/i })).toBeInTheDocument();
    expect(screen.getAllByTestId("region-box")).toHaveLength(4);
    expect(getStatus).not.toHaveBeenCalled();
    expect(analyzeImage).not.toHaveBeenCalled();
    expect(screen.getByText(/demo mode/i)).toBeInTheDocument();
  });

  it("renders the no-evidence state with calm wording", () => {
    window.history.replaceState({}, "", "/?demo=no_evidence");
    const { container } = render(<App />);
    expect(screen.getByRole("heading", { level: 2, name: /no evidence of editing found/i })).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/authentic|genuine/i);
    expect(screen.getByTestId("limitations")).toBeInTheDocument();
  });
});

describe("App normal mode", () => {
  it("shows the header copy, the dropzone and the model state", async () => {
    getStatus.mockResolvedValue({ status: "ok", model: { loaded: true, test_auc: 0.9, train_images: 1200 } });
    render(<App />);
    expect(screen.getByRole("heading", { level: 1, name: "Fake Screenshot Detector" })).toBeInTheDocument();
    expect(screen.getByText(/finds signs of editing in screenshots/i)).toBeInTheDocument();
    expect(screen.getByText(/drag & drop a screenshot/i)).toBeInTheDocument();
    expect(await screen.findByText("Model loaded")).toBeInTheDocument();
  });

  it("shows an unreachable-backend state subtly", async () => {
    getStatus.mockRejectedValue(new Error("down"));
    render(<App />);
    expect(await screen.findByText("Backend unreachable")).toBeInTheDocument();
  });
});
