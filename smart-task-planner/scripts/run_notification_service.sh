#!/usr/bin/env bash
# Запуск Notification Service (порт 8002) из корня репозитория.
# Использование: ./scripts/run_notification_service.sh
set -euo pipefail
cd "$(dirname "$0")/.."
echo "[run] Notification Service: http://localhost:8002 (Swagger: /docs)"
exec uvicorn notification_service.main:app --host 0.0.0.0 --port 8002
