#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT_DIR/.run"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"

listener_pids() {
  local port="$1"
  lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | sort -u || true
}

pid_is_listening() {
  local pid="$1"
  local port="$2"
  listener_pids "$port" | grep -Fx "$pid" >/dev/null 2>&1
}

command_is_expected() {
  local name="$1"
  local command="$2"
  case "$name" in
    后端)
      [[ "$command" == *"uvicorn"*backend.app:app* ]]
      ;;
    前端)
      [[ "$command" == *"vite"* ]] || [[ "$command" == *"npm"*run*dev* ]]
      ;;
    *)
      return 1
      ;;
  esac
}

stop_pid() {
  local name="$1"
  local pid="$2"
  local port="${3:-}"
  local source="${4:-pid}"
  local command
  command="$(ps -ww -p "$pid" -o command= 2>/dev/null || true)"
  if command_is_expected "$name" "$command"; then
    :
  elif [[ "$source" == "pid-file" && -n "$port" && -z "$command" ]] && pid_is_listening "$pid" "$port"; then
    echo "$name PID $pid 无法读取命令，但正在监听端口 $port，按 PID 文件停止"
  else
    echo "$name PID $pid 不是本项目网站服务，未停止：$command"
    return 0
  fi

  echo "停止 $name: PID $pid"
  kill "$pid" >/dev/null 2>&1 || true
  for _ in $(seq 1 20); do
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      echo "$name 已停止"
      return 0
    fi
    sleep 0.3
  done
  echo "$name 未在预期时间内退出，强制停止 PID $pid"
  kill -9 "$pid" >/dev/null 2>&1 || true
}

stop_pid_file() {
  local name="$1"
  local pid_file="$2"
  if [[ ! -f "$pid_file" ]]; then
    echo "$name 没有 PID 文件，跳过"
    return 0
  fi

  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [[ -z "$pid" ]] || ! kill -0 "$pid" >/dev/null 2>&1; then
    echo "$name 未运行，清理 PID 文件"
    rm -f "$pid_file"
    return 0
  fi

  local port="$3"
  stop_pid "$name" "$pid" "$port" "pid-file"
  rm -f "$pid_file"
}

stop_port_processes() {
  local name="$1"
  local port="$2"
  local pids
  pids="$(listener_pids "$port")"
  if [[ -z "$pids" ]]; then
    echo "$name 端口 $port 没有监听进程"
    return 0
  fi
  while IFS= read -r pid; do
    [[ -n "$pid" ]] && stop_pid "$name" "$pid" "$port" "port-scan"
  done <<< "$pids"
}

stop_pid_file "前端" "$FRONTEND_PID_FILE" "$FRONTEND_PORT"
stop_pid_file "后端" "$BACKEND_PID_FILE" "$BACKEND_PORT"
stop_port_processes "前端" "$FRONTEND_PORT"
stop_port_processes "后端" "$BACKEND_PORT"

echo "停止流程完成"
