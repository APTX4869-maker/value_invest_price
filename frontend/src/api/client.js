export const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

export async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || "请求失败");
  }
  return body;
}
