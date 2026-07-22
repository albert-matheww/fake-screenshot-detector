import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ImageUpload from "./ImageUpload.jsx";

describe("ImageUpload", () => {
  it("renders the dropzone prompt", () => {
    render(<ImageUpload onFileSelected={() => {}} disabled={false} />);
    expect(screen.getByText(/drag & drop a screenshot/i)).toBeInTheDocument();
  });

  it("rejects unsupported file types without calling onFileSelected", () => {
    const onFileSelected = vi.fn();
    render(<ImageUpload onFileSelected={onFileSelected} disabled={false} />);
    const input = document.querySelector('input[type="file"]');
    const badFile = new File(["dummy"], "malware.exe", { type: "application/octet-stream" });
    fireEvent.change(input, { target: { files: [badFile] } });
    expect(onFileSelected).not.toHaveBeenCalled();
    expect(screen.getByText(/unsupported file type/i)).toBeInTheDocument();
  });

  it("accepts a valid image file", () => {
    const onFileSelected = vi.fn();
    render(<ImageUpload onFileSelected={onFileSelected} disabled={false} />);
    const input = document.querySelector('input[type="file"]');
    const goodFile = new File(["dummy"], "screenshot.png", { type: "image/png" });
    fireEvent.change(input, { target: { files: [goodFile] } });
    expect(onFileSelected).toHaveBeenCalledWith(goodFile);
  });
});
