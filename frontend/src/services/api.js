import axios from "axios";

// In dev, Vite proxies /api -> the Flask server (see vite.config.js).
// In production (Docker/nginx), set VITE_API_BASE_URL at build time, or
// serve the frontend behind the same reverse proxy as the API under /api.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

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
