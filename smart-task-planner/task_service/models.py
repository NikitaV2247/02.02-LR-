"""Модели данных Task Service (Pydantic v2).

Схемы соответствуют API_CONTRACT.md (разделы 2 и 3):
- TaskCreate — тело POST /api/tasks (без id и created_at, их генерирует сервис);
- TaskUpdate — тело PUT /api/tasks/{id} (частичное обновление, None = не менять);
- Task       — объект задачи в формате контракта (ответ сервиса и тело вебхука).
"""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Статусы задачи (enum зафиксирован контрактом, раздел 2)."""

    NEW = "new"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class TaskCreate(BaseModel):
    """Тело запроса POST /api/tasks."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        examples=["Купить молоко"],
        description="Название задачи (1..200 символов)",
    )
    description: str = Field("", description="Описание задачи, может быть пустым")


class TaskUpdate(BaseModel):
    """Тело запроса PUT /api/tasks/{id} — частичное обновление."""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[TaskStatus] = None


class Task(BaseModel):
    """Задача в формате контракта (раздел 2 API_CONTRACT.md)."""

    id: str = Field(..., description="UUID задачи")
    title: str
    description: str
    status: TaskStatus
    created_at: str = Field(..., description="ISO 8601 (UTC)")
