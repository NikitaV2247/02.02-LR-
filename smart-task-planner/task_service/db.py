"""Хранилище задач на SQLite (stdlib sqlite3, без ORM — по минимуму зависимостей).

Локальная точка отказа Т-1 (см. docs/failure_points_task_service.md): файл БД.
При недоступности диска/файла операции бросают sqlite3.Error — FastAPI
транслирует это в 500, но процесс сервиса не падает.
"""
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "tasks.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'new',
    created_at  TEXT NOT NULL
);
"""

_SELECT_COLS = "id, title, description, status, created_at"


def _now_iso() -> str:
    """Текущее время в ISO 8601 (UTC) — формат поля created_at по контракту."""
    return datetime.now(timezone.utc).isoformat()


class TaskRepository:
    """CRUD-репозиторий задач.

    Потокобезопасность: FastAPI может вызывать эндпоинты из разных потоков,
    поэтому все обращения к соединению защищены Lock. Соединение одно
    (check_same_thread=False) — для учебного прототипа этого достаточно.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = Path(db_path or os.getenv("TASK_DB_PATH") or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock, self._conn:
            self._conn.execute(_SCHEMA)

    # ------------------------------------------------------------------ CRUD

    def create(self, title: str, description: str) -> dict:
        """Создаёт задачу: id/created_at генерируются сервисом, статус = new."""
        task = {
            "id": str(uuid4()),
            "title": title,
            "description": description,
            "status": "new",
            "created_at": _now_iso(),
        }
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO tasks (id, title, description, status, created_at) "
                "VALUES (:id, :title, :description, :status, :created_at)",
                task,
            )
        return task

    def list(self, status: Optional[str] = None) -> list:
        """Список задач, опционально отфильтрованный по статусу."""
        query = f"SELECT {_SELECT_COLS} FROM tasks"
        params: tuple = ()
        if status is not None:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY created_at"
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get(self, task_id: str) -> Optional[dict]:
        """Задача по id или None."""
        with self._lock:
            row = self._conn.execute(
                f"SELECT {_SELECT_COLS} FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        return dict(row) if row else None

    def update(self, task_id: str, fields: dict) -> Optional[dict]:
        """Частичное обновление задачи. Возвращает обновлённую задачу или None.

        Имена столбцов берутся только из Pydantic-модели TaskUpdate
        (title/description/status), поэтому подстановка в SQL безопасна.
        """
        if not fields:
            return self.get(task_id)
        set_clause = ", ".join(f"{column} = ?" for column in fields)
        values = list(fields.values()) + [task_id]
        with self._lock, self._conn:
            cursor = self._conn.execute(
                f"UPDATE tasks SET {set_clause} WHERE id = ?", values
            )
            if cursor.rowcount == 0:
                return None
        return self.get(task_id)

    def delete(self, task_id: str) -> bool:
        """Удаляет задачу. True — удалена, False — не найдена."""
        with self._lock, self._conn:
            cursor = self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            return cursor.rowcount > 0
