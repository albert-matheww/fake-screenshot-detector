import { describe, it, expect, afterEach } from "vitest";
import axios, { AxiosError } from "axios";
import client, { analyzeImage, toApiError, ApiError } from "./api.js";

function httpError(status, data) {
  const config = { headers: {} };
  return new AxiosError(`Request failed with status code ${status}`, "ERR_BAD_REQUEST", config, {}, {
    status, data, headers: {}, config,
  });
}

describe("toApiError", () => {
  it("maps 413 to too_large and is not retryable", () => {
    const e = toApiError(httpError(413, "<html>Request Entity Too Large</html>"));
    expect(e).toBeInstanceOf(ApiError);
    expect(e.kind).toBe("too_large");
    expect(e.retryable).toBe(false);
    expect(e.message).toMatch(/too large/i);
    expect(e.message).not.toMatch(/html/i);
  });

  it("maps 400 to invalid_image and surfaces the API's own message", () => {
    const e = toApiError(httpError(400, { error: "Could not decode image" }));
    expect(e.kind).toBe("invalid_image");
    expect(e.message).toBe("Could not decode image");
  });

  it("falls back to a generic invalid-image message when the body is not JSON", () => {
    const e = toApiError(httpError(400, "<html>Bad Request</html>"));
    expect(e.kind).toBe("invalid_image");
    expect(e.message).toMatch(/could not read that file as an image/i);
  });

  it("maps 5xx to server (retryable) without leaking the raw body", () => {
    const e = toApiError(httpError(500, { error: "Traceback (most recent call last) ..." }));
    expect(e.kind).toBe("server");
    expect(e.retryable).toBe(true);
    expect(e.message).not.toMatch(/traceback/i);
  });

  it("maps 429 to rate_limited", () => {
    expect(toApiError(httpError(429, {})).kind).toBe("rate_limited");
  });

  it("maps a response-less failure to network", () => {
    const err = new AxiosError("Network Error", "ERR_NETWORK", {}, {});
    expect(toApiError(err).kind).toBe("network");
  });

  it("maps a timeout to timeout", () => {
    const err = new AxiosError("timeout of 60000ms exceeded", "ECONNABORTED", {}, {});
    expect(toApiError(err).kind).toBe("timeout");
  });

  it("maps cancellation to canceled", () => {
    expect(toApiError(new axios.CanceledError()).kind).toBe("canceled");
  });

  it("passes ApiError through and handles arbitrary errors", () => {
    const original = new ApiError("server", "x");
    expect(toApiError(original)).toBe(original);
    expect(toApiError(new Error("boom")).kind).toBe("unknown");
  });
});

describe("analyzeImage", () => {
  const originalAdapter = client.defaults.adapter;
  afterEach(() => {
    client.defaults.adapter = originalAdapter;
  });

  it("posts multipart field `image` to /analyze and returns the payload", async () => {
    let seen;
    client.defaults.adapter = async (config) => {
      seen = config;
      return { data: { verdict: "no_evidence" }, status: 200, statusText: "OK", headers: {}, config };
    };
    const file = new File(["x"], "s.png", { type: "image/png" });
    const data = await analyzeImage(file);
    expect(data).toEqual({ verdict: "no_evidence" });
    expect(seen.url).toBe("/analyze");
    expect(seen.method).toBe("post");
    expect(seen.data.get("image")).toBeInstanceOf(File);
  });

  it("throws an ApiError with kind for HTTP failures", async () => {
    client.defaults.adapter = async (config) => {
      throw httpError(413, "too big");
    };
    await expect(analyzeImage(new File(["x"], "s.png"))).rejects.toMatchObject({
      name: "ApiError",
      kind: "too_large",
      status: 413,
    });
  });
});
