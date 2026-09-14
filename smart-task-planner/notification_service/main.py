"""Notification Service — приём событий task_created и «отправка» уведомлений.

В рамках лабораторной работы отправка уведомления пользователю ЭМУЛИРУЕТСЯ
записью в лог (консоль, stdout) через стандартный модуль logging.

Эндпоинты (API_CONTRACT.md):
- POST /api/webhooks/task_created — приём события «создана новая задача» (200 OK);
- GET  /health                    — проверка живости сервиса (200 OK).

Локальные точки отказа сервиса описаны в
docs/failure_points_notification_service.md.

Запуск: uvicorn notification_service.main:app --port 8002
"""
import logging
import os

from fastapi import FastAPI

from .models import Task

# Лог настраивается сразу при импорте, чтобы уведомления были видны в консоли
# и при запуске через uvicorn, и при прогоне тестов.
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("notification_service")

app = FastAPI(
    title="Notification Service",
    description=(
        "Микросервис уведомлений. Подписан на событие task.created и "
        "эмулирует отправку уведомления пользователю записью в лог."
    ),
    version="1.0.0",
)


@app.get("/health", summary="Проверка живости")
def health() -> dict:
    """Используется скриптом smoke_test.sh и Task Service для диагностики."""
    return {"status": "ok", "service": "notification-service"}


@app.post(
    "/api/webhooks/task_created",
    status_code=200,
    summary="Вебхук: создана новая задача",
)
def task_created(task: Task) -> dict:
    """Принимает объект Task и «отправляет» уведомление (запись в консоль).

    Валидация тела выполняется автоматически по Pydantic-схеме Task:
    невалидный payload → 422 (см. контракт, раздел 4.1).
    """
    logger.info("=" * 64)
    logger.info("НОВОЕ УВЕДОМЛЕНИЕ: создана новая задача")
    logger.info("  id:         %s", task.id)
    logger.info("  название:   %s", task.title)
    logger.info("  описание:   %s", task.description if task.description else "—")
    logger.info("  статус:     %s", task.status)
    logger.info("  создана:    %s", task.created_at)
    logger.info("=" * 64)

    return {
        "status": "ok",
        "message": "Уведомление обработано",
        "task_id": task.id,  # ревью (А. Ковалёв): Task Service сопоставляет доставку с задачей по id
    }
