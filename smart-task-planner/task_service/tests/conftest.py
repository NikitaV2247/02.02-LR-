"""Фикстуры тестов Task Service.

Каждый тест получает изолированный экземпляр приложения с временной SQLite-БД.
По умолчанию доставка вебхуков ОТКЛЮЧЕНА (WEBHOOK_ENABLED=false), чтобы
юнит-тесты не зависели от сети; устойчивость проверяется отдельным тестом
с заведомо недоступным получателем.
"""
import contextlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def make_client(monkeypatch, tmp_path):
    """Фабрика клиентов с переопределением переменных окружения сервиса."""

    @contextlib.contextmanager
    def _make(**overrides):
        monkeypatch.setenv("TASK_DB_PATH", str(tmp_path / "tasks.db"))
        monkeypatch.setenv("WEBHOOK_ENABLED", "false")
        for key, value in overrides.items():
            monkeypatch.setenv(key, str(value))
        from task_service.main import app  # настройки читаются в lifespan

        with TestClient(app) as test_client:
            yield test_client

    return _make


@pytest.fixture()
def client(make_client):
    """Клиент с настройками по умолчанию (без сети)."""
    with make_client() as test_client:
        yield test_client
