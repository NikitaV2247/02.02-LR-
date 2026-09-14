#!/usr/bin/env bash
# Запуск Task Service (порт 8001) из корня репозитория.
# Использование: ./scripts/run_task_service.sh
set -euo pipefail
cd "$(dirname "$0")/.."
echo "[run] Task Service: http://localhost:8001 (Swagger: /docs)"
exec uvicorn task_service.main:app --host 0.0.0.0 --port 8001
