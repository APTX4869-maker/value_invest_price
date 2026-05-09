export const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

function backendConnectionError(error) {
  const detail = error?.message ? `原始错误：${error.message}` : "原始错误：网络请求失败";
  return [
    `无法连接后端服务 ${API_BASE}。`,
    "请确认后端已启动：.venv/bin/uvicorn backend.app:app --port 8000。",
    "如果后端运行在其他地址，请检查 VITE_API_BASE 配置。",
    detail,
  ].join(" ");
}

export async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
  } catch (error) {
    throw new Error(backendConnectionError(error));
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || "请求失败");
  }
  return body;
}
