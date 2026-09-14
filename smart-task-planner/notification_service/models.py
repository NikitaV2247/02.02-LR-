"""Модель Task на стороне Notification Service.

Микросервисы не шарят общий код — схема продублирована локально и должна
соответствовать API_CONTRACT.md (v1.0). Это осознанный принцип approach
contract-first: единый документ-контракт является источником истины,
а не общий импортируемый модуль.
"""
from typing import Literal

from pydantic import BaseModel, Field


class Task(BaseModel):
    """Объект Task в формате, зафиксированном в API_CONTRACT.md (раздел 2)."""

    id: str = Field(..., description="UUID задачи в строковом представлении")
    title: str = Field(..., min_length=1, max_length=200, description="Название задачи")
    description: str = Field("", description="Описание задачи, может быть пустым")
    status: Literal["new", "in_progress", "done"] = Field(..., description="Статус задачи")
    created_at: str = Field(..., description="Дата/время создания, ISO 8601 (UTC)")
