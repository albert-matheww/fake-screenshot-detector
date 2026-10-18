import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import LoadingPanel from "./LoadingPanel.jsx";
import ErrorPanel from "./ErrorPanel.jsx";
import { ApiError } from "../services/api.js";

afterEach(() => vi.useRealTimers());

describe("LoadingPanel", () => {
  it("counts elapsed seconds and mentions long waits after 8 s", () => {
    vi.useFakeTimers();
    const onCancel = vi.fn();
    render(<LoadingPanel onCancel={onCancel} />);
    expect(screen.getByRole("status")).toHaveTextContent("0s");
    expect(screen.queryByText(/up to 15 seconds/i)).toBeNull();
    act(() => vi.advanceTimersByTime(9000));
    expect(screen.getByRole("status")).toHaveTextContent("9s");
    expect(screen.getByText(/up to 15 seconds/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalled();
  });
});

describe("ErrorPanel", () => {
  it.each([
    ["network", /can't reach the server/i, true],
    ["too_large", /image too large/i, false],
    ["invalid_image", /can't be analysed/i, false],
    ["server", /server hit an error/i, true],
  ])("shows a distinct message for %s", (kind, title, retryable) => {
    const onRetry = vi.fn();
    render(<ErrorPanel error={new ApiError(kind, "details here", { retryable })} onRetry={onRetry} onClear={() => {}} />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(title)).toBeInTheDocument();
    expect(screen.getByText("details here")).toBeInTheDocument();
    expect(Boolean(screen.queryByRole("button", { name: /try again/i }))).toBe(retryable);
  });
});
