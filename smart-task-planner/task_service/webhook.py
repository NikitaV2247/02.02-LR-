"""Отправка вебхуков в Notification Service — «шина событий» лабораторной.

Модель устойчивости:
- событие кладётся в очередь в памяти (asyncio.Queue);
- фоновая задача-воркер доставляет события: до N попыток с экспоненциальным
  backoff (1/2/4 c) и таймаутом запроса;
- если получатель недоступен или отвечает ошибкой — Task Service НЕ падает:
  каждая неудачная попытка логируется (WEBHOOK_RETRY), после исчерпания попыток
  пишется WEBHOOK_FAILED. Задача при этом уже сохранена: уведомление — best-effort.

Локальные точки отказа Т-2/Т-3 (docs/failure_points_task_service.md):
недоступность получателя и потеря очереди при перезапуске процесса.
"""
import asyncio
import contextlib
import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger("task_service.webhook")


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass
class WebhookSettings:
    """Настройки доставки вебхуков (читаются из переменных окружения)."""

    enabled: bool
    url: str
    max_retries: int
    backoff: float
    timeout: float

    @classmethod
    def from_env(cls) -> "WebhookSettings":
        return cls(
            enabled=_env_bool("WEBHOOK_ENABLED", True),
            url=os.getenv(
                "NOTIFICATION_SERVICE_URL",
                "http://localhost:8002/api/webhooks/task_created",
            ),
            max_retries=_env_int("WEBHOOK_MAX_RETRIES", 3),
            backoff=_env_float("WEBHOOK_BACKOFF_SECONDS", 1.0),
            timeout=_env_float("WEBHOOK_TIMEOUT_SECONDS", 5.0),
        )


class WebhookDispatcher:
    """Очередь событий в памяти + фоновая доставка с повторными попытками."""

    def __init__(self, settings: WebhookSettings) -> None:
        self.settings = settings
        self.queue: "asyncio.Queue[dict[str, Any]]" = asyncio.Queue()
        self._worker_task: "asyncio.Task | None" = None

    # ------------------------------------------------------------- lifecycle

    def start(self) -> None:
        """Запускает фонового воркера (вызывается из lifespan приложения)."""
        self._worker_task = asyncio.create_task(self._worker(), name="webhook-worker")

    async def stop(self) -> None:
        """Останавливает воркера (вызывается из lifespan приложения)."""
        if self._worker_task is not None:
            self._worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task
            self._worker_task = None

    # --------------------------------------------------------------- events

    async def enqueue(self, task: dict) -> None:
        """Ставит событие в очередь сразу после успешного создания задачи."""
        await self.queue.put(dict(task))
        logger.info(
            "WEBHOOK_QUEUED task_id=%s queue_size=%d",
            task.get("id"),
            self.queue.qsize(),
        )

    # -------------------------------------------------------------- internal

    async def _worker(self) -> None:
        while True:
            task = await self.queue.get()
            try:
                await self._deliver(task)
            except asyncio.CancelledError:
                raise
            except Exception:  # защита цикла от любых неожиданных ошибок
                logger.exception("WEBHOOK_WORKER_ERROR непредвиденная ошибка воркера")
            finally:
                self.queue.task_done()

    async def _deliver(self, task: dict) -> None:
        """Доставка одного события: до max_retries попыток с backoff 1/2/4 c."""
        last_error = "n/a"
        for attempt in range(1, self.settings.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.settings.timeout) as client:
                    # Формат сообщения — по финальному контракту (раздел 5, v1.0):
                    # тело = объект Task целиком (без конверта),
                    # тип события передаётся заголовком X-Event-Type.
                    response = await client.post(
                        self.settings.url,
                        json=task,
                        headers={
                            "Content-Type": "application/json",
                            "X-Event-Type": "task.created",
                        },
                    )
                if 200 <= response.status_code < 300:
                    logger.info(
                        "WEBHOOK_DELIVERED task_id=%s attempt=%d/%d status=%d",
                        task.get("id"), attempt, self.settings.max_retries,
                        response.status_code,
                    )
                    return
                last_error = f"HTTP {response.status_code}"
                logger.warning(
                    "WEBHOOK_RETRY task_id=%s attempt=%d/%d неожидаемый статус=%d",
                    task.get("id"), attempt, self.settings.max_retries,
                    response.status_code,
                )
            except httpx.HTTPError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "WEBHOOK_RETRY task_id=%s attempt=%d/%d ошибка=%s",
                    task.get("id"), attempt, self.settings.max_retries, last_error,
                )
            if attempt < self.settings.max_retries:
                await asyncio.sleep(self.settings.backoff * 2 ** (attempt - 1))
        logger.error(
            "WEBHOOK_FAILED task_id=%s попыток=%d последняя_ошибка=%s — "
            "уведомление не доставлено (best-effort, задача сохранена)",
            task.get("id"), self.settings.max_retries, last_error,
        )
