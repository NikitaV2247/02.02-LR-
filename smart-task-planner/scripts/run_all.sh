#!/usr/bin/env bash
# Запуск ОБОИХ сервисов в фоновых процессах.
# Остановка: Ctrl+C (обоим процессам отправится SIGTERM).
# Использование: ./scripts/run_all.sh
set -euo pipefail
cd "$(dirname "$0")/.."

cleanup() {
  echo
  echo "[run] Остановка сервисов..."
  kill 0 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "[run] Notification Service: http://localhost:8002/docs"
uvicorn notification_service.main:app --host 0.0.0.0 --port 8002 &

echo "[run] Task Service:        http://localhost:8001/docs"
uvicorn task_service.main:app --host 0.0.0.0 --port 8001 &

echo "[run] Оба сервиса запущены. Ctrl+C — остановка."
wait
