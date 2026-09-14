#!/usr/bin/env bash
# Сквозная (end-to-end) ручная проверка — Этап 4 задания, п. 6.
# Перед запуском оба сервиса должны быть подняты: ./scripts/run_all.sh
#
# Сценарий: health-check обоих сервисов → создание задачи → пауза на доставку
# вебхука → проверка списка задач. Уведомление подтверждается В КОНСОЛИ
# Notification Service (строка «НОВОЕ УВЕДОМЛЕНИЕ»).
set -euo pipefail

TASK_URL="${TASK_SERVICE_URL:-http://localhost:8001}"
NOTIF_URL="${NOTIFICATION_SERVICE_URL:-http://localhost:8002}"

echo "==> 1. Health-check Task Service: $TASK_URL"
curl -fsS "$TASK_URL/health"; echo

echo "==> 2. Health-check Notification Service: $NOTIF_URL"
curl -fsS "$NOTIF_URL/health"; echo

echo "==> 3. POST $TASK_URL/api/tasks (создание задачи)"
CREATED=$(curl -fsS -X POST "$TASK_URL/api/tasks" \
  -H "Content-Type: application/json" \
  -d "{\"title\": \"Smoke-тест $(date +%H:%M:%S)\", \"description\": \"Создано скриптом scripts/smoke_test.sh\"}")
echo "$CREATED"

TASK_ID=$(echo "$CREATED" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
echo "    id задачи: $TASK_ID"

echo "==> 4. Ожидание доставки вебхука (2 c)..."
sleep 2

echo "==> 5. GET $TASK_URL/api/tasks/$TASK_ID (задача должна существовать)"
curl -fsS "$TASK_URL/api/tasks/$TASK_ID"; echo

echo
echo "==> ГОТОВО. Финальная проверка — вручную: в консоли Notification Service"
echo "    должна быть строка «НОВОЕ УВЕДОМЛЕНИЕ» с id=$TASK_ID"
