#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT_DIR/.run"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"
BACKEND_LOG="$RUN_DIR/backend.log"
FRONTEND_LOG="$RUN_DIR/frontend.log"
FRONTEND_BIN="$ROOT_DIR/frontend/node_modules/.bin/vite"

mkdir -p "$RUN_DIR"

is_pid_alive() {
  local pid="${1:-}"
  [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1
}

port_has_service() {
  local port="$1"
  curl -fsS "http://127.0.0.1:$port" >/dev/null 2>&1
}

backend_healthy() {
  curl -fsS "http://127.0.0.1:$BACKEND_PORT/api/health" >/dev/null 2>&1
}

wait_for() {
  local name="$1"
  local check_cmd="$2"
  local log_file="$3"
  local attempts=40
  for _ in $(seq 1 "$attempts"); do
    if eval "$check_cmd"; then
      echo "$name 已启动"
      return 0
    fi
    sleep 0.5
  done
  echo "$name 启动超时，最近日志："
  tail -n 40 "$log_file" 2>/dev/null || true
  return 1
}

start_backend() {
  local pid=""
  [[ -f "$BACKEND_PID_FILE" ]] && pid="$(cat "$BACKEND_PID_FILE")"
  if is_pid_alive "$pid" && backend_healthy; then
    echo "后端已在运行: http://127.0.0.1:$BACKEND_PORT"
    return 0
  fi
  if backend_healthy; then
    echo "后端端口已有健康服务: http://127.0.0.1:$BACKEND_PORT"
    return 0
  fi
  if [[ ! -x "$ROOT_DIR/.venv/bin/uvicorn" ]]; then
    echo "未找到 .venv/bin/uvicorn，请先创建虚拟环境并安装 backend/requirements.txt"
    exit 1
  fi
  echo "启动后端: http://127.0.0.1:$BACKEND_PORT"
  pushd "$ROOT_DIR" >/dev/null
  nohup "$ROOT_DIR/.venv/bin/uvicorn" backend.app:app --host 127.0.0.1 --port "$BACKEND_PORT" >"$BACKEND_LOG" 2>&1 &
  echo $! > "$BACKEND_PID_FILE"
  popd >/dev/null
  wait_for "后端" "backend_healthy" "$BACKEND_LOG"
}

start_frontend() {
  local pid=""
  [[ -f "$FRONTEND_PID_FILE" ]] && pid="$(cat "$FRONTEND_PID_FILE")"
  if is_pid_alive "$pid" && port_has_service "$FRONTEND_PORT"; then
    echo "前端已在运行: http://127.0.0.1:$FRONTEND_PORT"
    return 0
  fi
  if port_has_service "$FRONTEND_PORT"; then
    echo "前端端口已有服务: http://127.0.0.1:$FRONTEND_PORT"
    return 0
  fi
  if [[ ! -x "$FRONTEND_BIN" ]]; then
    echo "未找到 frontend/node_modules/.bin/vite，请先在 frontend 目录执行 npm install"
    exit 1
  fi
  echo "启动前端: http://127.0.0.1:$FRONTEND_PORT"
  pushd "$ROOT_DIR/frontend" >/dev/null
  nohup "$FRONTEND_BIN" --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort >"$FRONTEND_LOG" 2>&1 &
  echo $! > "$FRONTEND_PID_FILE"
  popd >/dev/null
  wait_for "前端" "port_has_service '$FRONTEND_PORT'" "$FRONTEND_LOG"
}

start_backend
start_frontend

echo
echo "网站已启动"
echo "前端: http://127.0.0.1:$FRONTEND_PORT"
echo "后端: http://127.0.0.1:$BACKEND_PORT/api/health"
echo "日志: $RUN_DIR"
