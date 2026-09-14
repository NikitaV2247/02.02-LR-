"""Юнит-тесты Task Service (pytest + fastapi.testclient).

Проверяется обязательный по заданию основной сценарий: POST /api/tasks
возвращает 201 и задачу со всеми полями контракта. Дополнительно покрыты
валидация, CRUD-поток и устойчивость к недоступности Notification Service
(обработка ошибок — Этап 3 задания).
"""
import logging
import time
import uuid as uuid_lib

TASK_PAYLOAD = {"title": "Подготовить отчет", "description": "Лабораторная работа"}


def _wait_for_log(caplog, needle: str, timeout: float = 5.0) -> bool:
    """Ждёт появления записи в логе (воркер доставляет события асинхронно)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if any(needle in record.getMessage() for record in caplog.records):
            return True
        time.sleep(0.05)
    return False


# ----------------------------------------------------------- основной сценарий


def test_create_task_returns_201_with_contract_fields(client):
    """POST /api/tasks → 201, все поля контракта заполнены сервисом."""
    response = client.post("/api/tasks", json=TASK_PAYLOAD)

    assert response.status_code == 201, response.text
    task = response.json()
    assert task["title"] == TASK_PAYLOAD["title"]
    assert task["description"] == TASK_PAYLOAD["description"]
    assert task["status"] == "new"                       # статус по умолчанию
    assert len(task["id"]) == 36
    uuid_lib.UUID(task["id"])                            # id — корректный UUID
    assert task["created_at"].endswith("+00:00")         # ISO 8601 (UTC)


def test_create_task_validation_error_empty_title(client):
    """Пустой title → 422 (контракт, раздел 3.1)."""
    response = client.post("/api/tasks", json={"title": "", "description": ""})

    assert response.status_code == 422


# ------------------------------------------------------------------- CRUD


def test_list_tasks_returns_created_tasks(client):
    first = client.post("/api/tasks", json={"title": "Задача А"}).json()
    second = client.post("/api/tasks", json={"title": "Задача Б"}).json()

    response = client.get("/api/tasks")

    assert response.status_code == 200
    ids = {task["id"] for task in response.json()}
    assert ids == {first["id"], second["id"]}


def test_update_task_status_flow(client):
    task_id = client.post("/api/tasks", json=TASK_PAYLOAD).json()["id"]

    in_progress = client.put(f"/api/tasks/{task_id}", json={"status": "in_progress"})
    assert in_progress.status_code == 200
    assert in_progress.json()["status"] == "in_progress"

    done = client.put(f"/api/tasks/{task_id}", json={"status": "done", "title": "Отчет"})
    assert done.status_code == 200
    assert done.json()["status"] == "done"
    assert done.json()["title"] == "Отчет"

    assert client.get(f"/api/tasks/{task_id}").json()["status"] == "done"


def test_delete_task_then_404(client):
    task_id = client.post("/api/tasks", json=TASK_PAYLOAD).json()["id"]

    assert client.delete(f"/api/tasks/{task_id}").status_code == 204
    assert client.get(f"/api/tasks/{task_id}").status_code == 404
    assert client.delete(f"/api/tasks/{task_id}").status_code == 404


def test_get_unknown_task_returns_404(client):
    response = client.get("/api/tasks/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404


# ------------------------------------------- устойчивость к отказу получателя


def test_task_creation_succeeds_when_notification_service_down(make_client, caplog):
    """Notification Service недоступен → создание задачи всё равно 201;
    вебхук после попыток помечается WEBHOOK_FAILED в логе, сервис не падает."""
    caplog.set_level(logging.DEBUG)
    with make_client(
        WEBHOOK_ENABLED="true",
        NOTIFICATION_SERVICE_URL="http://127.0.0.1:1/api/webhooks/task_created",
        WEBHOOK_MAX_RETRIES="2",
        WEBHOOK_BACKOFF_SECONDS="0.05",
    ) as client:
        response = client.post("/api/tasks", json={"title": "Тест устойчивости"})

        assert response.status_code == 201, response.text

        assert _wait_for_log(caplog, "WEBHOOK_FAILED", timeout=5.0), (
            "Ожидалась запись WEBHOOK_FAILED после исчерпания попыток"
        )
        retries = [r.getMessage() for r in caplog.records if "WEBHOOK_RETRY" in r.getMessage()]
        assert len(retries) >= 1, "Ожидалась хотя бы одна повторная попытка"
