"""Юнит-тесты Notification Service (pytest + fastapi.testclient).

Проверяется обязательный по заданию основной сценарий: вебхук task_created
принимает валидный объект Task и возвращает 200 OK, уведомление фиксируется
в логе (консоль). Дополнительно — негативные сценарии валидации (422).
"""
import logging

from fastapi.testclient import TestClient

from notification_service.main import app

# Валидный объект Task по контракту (раздел 2)
TASK_PAYLOAD = {
    "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "title": "Купить молоко",
    "description": "2 литра",
    "status": "new",
    "created_at": "2026-09-14T07:15:30+00:00",
}


def test_task_created_returns_200_and_logs_notification(caplog):
    """Основной сценарий: валидный Task → 200 OK + уведомление в лог (консоль)."""
    client = TestClient(app)
    with caplog.at_level(logging.INFO, logger="notification_service"):
        response = client.post("/api/webhooks/task_created", json=TASK_PAYLOAD)

    assert response.status_code == 200, response.text
    assert response.json() == {
        "status": "ok",
        "message": "Уведомление обработано",
        "task_id": TASK_PAYLOAD["id"],
    }
    # Уведомление «отправлено» = его данные зафиксированы в логе
    logged = [record.getMessage() for record in caplog.records]
    assert any("НОВОЕ УВЕДОМЛЕНИЕ" in msg for msg in logged)
    assert any(TASK_PAYLOAD["id"] in msg for msg in logged)
    assert any(TASK_PAYLOAD["title"] in msg for msg in logged)


def test_health_endpoint():
    """Health-check отвечает 200 и идентифицирует сервис."""
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == "notification-service"


def test_webhook_rejects_invalid_status():
    """Негативный сценарий: неизвестный статус → 422 (валидация схемы Task)."""
    client = TestClient(app)
    bad_payload = {**TASK_PAYLOAD, "status": "cancelled"}

    response = client.post("/api/webhooks/task_created", json=bad_payload)

    assert response.status_code == 422


def test_webhook_rejects_missing_title():
    """Негативный сценарий: пустой title → 422."""
    client = TestClient(app)
    bad_payload = {**TASK_PAYLOAD, "title": ""}

    response = client.post("/api/webhooks/task_created", json=bad_payload)

    assert response.status_code == 422
