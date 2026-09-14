"""Task Service — управление задачами «Умного планировщика задач».

Эндпоинты (API_CONTRACT.md v1.0, раздел 3):
- POST   /api/tasks       — создание задачи (201);
- GET    /api/tasks       — список задач (200), фильтр ?status=;
- GET    /api/tasks/{id}  — задача по id (200 / 404);
- PUT    /api/tasks/{id}  — частичное обновление (200 / 404 / 422);
- DELETE /api/tasks/{id}  — удаление (204 / 404);
- GET    /health          — проверка живости.

После успешного создания задачи событие ставится в очередь вебхуков
(task_service/webhook.py) и доставляется в Notification Service асинхронно.

Запуск: uvicorn task_service.main:app --port 8001
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from .db import TaskRepository
from .models import Task, TaskCreate, TaskStatus, TaskUpdate
from .webhook import WebhookDispatcher, WebhookSettings

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("task_service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Инициализация зависимостей при старте и остановка фонового воркера."""
    settings = WebhookSettings.from_env()
    repo = TaskRepository()
    dispatcher = WebhookDispatcher(settings)
    app.state.repo = repo
    app.state.dispatcher = dispatcher
    if settings.enabled:
        dispatcher.start()
        logger.info(
            "Task Service готов: БД=%s, вебхуки → %s (попыток=%d, backoff=%.2fc)",
            repo.db_path, settings.url, settings.max_retries, settings.backoff,
        )
    else:
        logger.warning(
            "Task Service готов, но доставка вебхуков ОТКЛЮЧЕНА (WEBHOOK_ENABLED=false)"
        )
    yield
    await dispatcher.stop()


app = FastAPI(
    title="Task Service",
    description="Микросервис управления задачами «Умного планировщика задач».",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", summary="Проверка живости")
def health() -> dict:
    return {"status": "ok", "service": "task-service"}


@app.post(
    "/api/tasks",
    response_model=Task,
    status_code=201,
    summary="Создать задачу",
    responses={422: {"description": "Ошибка валидации тела запроса"}},
)
async def create_task(body: TaskCreate) -> Task:
    """Создаёт задачу и ставит событие task.created в очередь вебхуков."""
    task = app.state.repo.create(body.title, body.description)
    logger.info("TASK_CREATED id=%s title=%r", task["id"], task["title"])
    await app.state.dispatcher.enqueue(task)
    return Task(**task)


@app.get("/api/tasks", response_model=list[Task], summary="Список задач")
async def list_tasks(
    status: TaskStatus | None = Query(None, description="Фильтр по статусу")
) -> list[Task]:
    tasks = app.state.repo.list(status.value if status else None)
    return [Task(**task) for task in tasks]


@app.get(
    "/api/tasks/{task_id}",
    response_model=Task,
    summary="Получить задачу",
    responses={404: {"description": "Задача не найдена"}},
)
async def get_task(task_id: str) -> Task:
    task = app.state.repo.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return Task(**task)


@app.put(
    "/api/tasks/{task_id}",
    response_model=Task,
    summary="Изменить задачу",
    responses={404: {"description": "Задача не найдена"},
               422: {"description": "Тело не содержит изменяемых полей"}},
)
async def update_task(task_id: str, body: TaskUpdate) -> Task:
    fields = body.model_dump(exclude_none=True)
    if not fields:
        return JSONResponse(status_code=422, content={"detail": "Тело обновления пусто"})
    task = app.state.repo.update(task_id, fields)
    if task is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    logger.info("TASK_UPDATED id=%s fields=%s", task_id, list(fields))
    return Task(**task)


@app.delete(
    "/api/tasks/{task_id}",
    status_code=204,
    summary="Удалить задачу",
    responses={404: {"description": "Задача не найдена"}},
)
async def delete_task(task_id: str) -> None:
    if not app.state.repo.delete(task_id):
        raise HTTPException(status_code=404, detail="Задача не найдена")
    logger.info("TASK_DELETED id=%s", task_id)
