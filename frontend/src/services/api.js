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
  timeout: 30000,
});

export async function analyzeImage(file, { onUploadProgress } = {}) {
  const formData = new FormData();
  formData.append("image", file);

  const response = await client.post("/analyze", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress,
  });
  return response.data;
}

export async function getStatus() {
  const response = await client.get("/status");
  return response.data;
}

export default client;
