import axios from "axios";

// In dev, Vite proxies /api -> the Flask server (see vite.config.js).
// In production (Docker/nginx), set VITE_API_BASE_URL (full origin, e.g.
// "https://api.example.com") at build time, or serve the frontend behind
// the same reverse proxy as the API under /api.
//
// VITE_API_HOST is a second option for platforms whose cross-service
// variable references hand back a bare hostname rather than a full URL
// (e.g. Render's `fromService: {property: host}`) — building the origin
// here avoids depending on exactly what a given platform's reference
// syntax does or doesn't prefix.
const API_BASE_URL = import.meta.env.VITE_API_HOST
  ? `https://${import.meta.env.VITE_API_HOST}`
  : (import.meta.env.VITE_API_BASE_URL || "/api");

const client = axios.create({
  baseURL: API_BASE_URL,
  // Large screenshots can take 5-15 s to analyse; leave generous headroom.
  timeout: 60000,
});

/**
 * Error thrown by this module. `kind` is a stable machine-readable category
 * the UI can switch on; `message` is safe to show to the user.
 */
export class ApiError extends Error {
  constructor(kind, message, { status = null, retryable = true } = {}) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
    this.retryable = retryable;
  }
}

/** Map an axios error (or anything thrown) to an ApiError. Pure. */
export function toApiError(err) {
  if (err instanceof ApiError) return err;

  if (axios.isCancel?.(err) || err?.code === "ERR_CANCELED") {
    return new ApiError("canceled", "Analysis cancelled.");
  }

  const status = err?.response?.status ?? null;
  if (status == null) {
    if (err?.code === "ECONNABORTED" || err?.code === "ETIMEDOUT") {
      return new ApiError(
        "timeout",
        "The analysis took too long and was stopped. Try a smaller or cropped screenshot.",
      );
    }
    if (err?.request || err?.code === "ERR_NETWORK") {
      return new ApiError(
        "network",
        "Could not reach the analysis server. Check your connection and that the backend is running, then try again.",
      );
    }
    return new ApiError("unknown", err?.message || "Something went wrong. Please try again.");
  }

  // Only trust a plain-text error from the API itself (nginx error pages are HTML).
  const serverMessage =
    typeof err.response.data?.error === "string" ? err.response.data.error : null;

  if (status === 413) {
    return new ApiError("too_large", "That image is too large for the server (limit 10 MB). Try a smaller file.", {
      status,
      retryable: false,
    });
  }
  if (status === 400 || status === 415 || status === 422) {
    return new ApiError(
      "invalid_image",
      serverMessage || "The server could not read that file as an image. Use a PNG, JPEG or WebP screenshot.",
      { status, retryable: false },
    );
  }
  if (status === 429) {
    return new ApiError("rate_limited", "Too many requests right now. Wait a moment and try again.", { status });
  }
  if (status >= 500) {
    return new ApiError(
      "server",
      "The analysis server hit an error while processing this image. Try again; if it keeps failing, try a different screenshot.",
      { status },
    );
  }
  return new ApiError("unknown", serverMessage || `Unexpected response from the server (HTTP ${status}).`, { status });
}

export async function analyzeImage(file, { onUploadProgress, signal, type } = {}) {
  const formData = new FormData();
  formData.append("image", file);
  if (type && type !== "auto") formData.append("type", type);

  try {
    const response = await client.post("/analyze", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress,
      signal,
    });
    return response.data;
  } catch (err) {
    throw toApiError(err);
  }
}

export async function compareImages(original, suspect, { signal } = {}) {
  const formData = new FormData();
  formData.append("original", original);
  formData.append("suspect", suspect);
  try {
    const response = await client.post("/compare", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      signal,
    });
    return response.data;
  } catch (err) {
    throw toApiError(err);
  }
}

export async function reconcileImages(image, { type, sourceText, sourceImage, signal } = {}) {
  const formData = new FormData();
  formData.append("image", image);
  if (type && type !== "auto") formData.append("type", type);
  if (sourceText) formData.append("source_text", sourceText);
  if (sourceImage) formData.append("source_image", sourceImage);
  try {
    const response = await client.post("/reconcile", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 120000,
      signal,
    });
    return response.data;
  } catch (err) {
    throw toApiError(err);
  }
}

export async function getStatus({ signal } = {}) {
  const response = await client.get("/status", { timeout: 8000, signal });
  return response.data;
}

export default client;
