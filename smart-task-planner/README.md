# Smart Task Planner — «Умный планировщик задач»

Учебный командный проект: прототип сервиса из двух микросервисов в рамках
лабораторной работы **«Разработка и интеграция модулей проекта (командная работа)»**.

Стек: **Python 3.10+ / FastAPI / Pydantic v2 / SQLite (stdlib) / httpx / pytest / uvicorn.**

## 1. Команда и роли (Этап 1)

| Роль | Участник | Зона ответственности | Git-автор |
|---|---|---|---|
| Архитектор / Tech Lead | Абдуллаев И. А. | API-контракт, код-ревью, merge PR, разрешение конфликтов, скрипты интеграции | `kovalev@team.dev` |
| Backend, Task Service | Орлов М. С.  | CRUD задач, SQLite-хранилище, очередь вебхуков с retry, тесты | `orlov@team.dev` |
| Backend, Notification Service | Васильев Н. С. | Приём вебхуков, уведомления, тесты | `vetrova@team.dev` |

Ветка `main` защищена: изменения попадают в неё только через PR (dev → main) после код-ревью Архитектора.

## 2. Архитектура

```
┌────────────────┐   POST /api/tasks          ┌──────────────────┐
│    Клиент      │ ──────────────────────────►│   Task Service   │──► SQLite
│ (curl/Postman) │ ◄────────── 201, Task ─────│      :8001       │   (data/tasks.db)
└────────────────┘                            └────────┬─────────┘
                                                       │  событие task.created
                                                       │  → очередь в памяти
                                                       │    (asyncio.Queue)
                                                       │  retry: до 3 попыток,
                                                       │  backoff 1/2/4 c
                                                       ▼  HTTP POST /api/webhooks/task_created
                                              ┌──────────────────┐
                                              │ Notification     │──► «отправка»
                                              │ Service  :8002   │    уведомления =
                                              └──────────────────┘    запись в консоль
```

- Единственный источник истины по взаимодействию — **[API_CONTRACT.md](API_CONTRACT.md)** (v1.0), подписанный командой до начала разработки (contract-first).
- Схема `Task` продублирована в каждом сервисе намеренно: микросервисы не шарят код, общим является только контракт.
- Обмен событиями — асинхронный через вебхук (упрощение «шины событий» из легенды проекта).

## 3. Быстрый старт

```bash
# 1) Виртуальное окружение и зависимости (Python 3.10+)
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r task_service/requirements.txt -r notification_service/requirements.txt

# 2) Запуск обоих сервисов
./scripts/run_all.sh                 # Windows: scripts\run_all.bat
# (или по отдельности: ./scripts/run_task_service.sh и ./scripts/run_notification_service.sh)
```

| Сервис | Адрес | Swagger (автодокументация) |
|---|---|---|
| Task Service | http://localhost:8001 | http://localhost:8001/docs |
| Notification Service | http://localhost:8002 | http://localhost:8002/docs |

Переменные окружения и значения по умолчанию — в [.env.example](.env.example).

## 4. Тесты

```bash
# юнит-тесты обоих сервисов
pytest task_service notification_service -v
```

- **task_service/tests** — основной сценарий (POST /api/tasks → 201 со всеми полями контракта), CRUD, валидация (422) и **устойчивость к недоступности Notification Service** (retry, затем `WEBHOOK_FAILED`, создание задачи не падает).
- **notification_service/tests** — основной сценарий вебхука (валидный Task → 200 OK + уведомление в логе), health-check, негативные сценарии валидации (422).

## 5. Ручное сквозное тестирование (Этап 4, п. 6)

```bash
./scripts/run_all.sh          # терминал 1 (оба сервиса)
./scripts/smoke_test.sh       # терминал 2
```

Скрипт проверяет health обоих сервисов, создаёт задачу через `POST /api/tasks`,
ждёт доставку вебхука и подтверждает сохранение. **Финальную точку проверяет
человек:** в консоли Notification Service появляется блок «НОВОЕ УВЕДОМЛЕНИЕ»
с id созданной задачи.

Пример ручного запроса (Postman/curl):

```bash
curl -X POST http://localhost:8001/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "Купить молоко", "description": "2 литра"}'
```

**Сценарий отказа (демо устойчивости):** остановите Notification Service и создайте
задачу — Task Service вернёт `201`, а в его логе появятся `WEBHOOK_RETRY`
(3 попытки с backoff 1/2/4 c) и затем `WEBHOOK_FAILED`. Сервис не падает.

## 6. Структура репозитория

```
smart-task-planner/
├── API_CONTRACT.md                      # контракт v1.0 (источник истины)
├── REPORT.md                            # отчет о конфликте слияния (Этап 5)
├── .env.example                         # пример переменных окружения
├── task_service/                        # модуль Орлов М. С. а
│   ├── main.py                          # FastAPI: POST/GET/PUT/DELETE /api/tasks, /health
│   ├── models.py                        # Pydantic-схемы (по контракту)
│   ├── db.py                            # SQLite-репозиторий (stdlib sqlite3)
│   ├── webhook.py                       # очередь в памяти + retry-доставка
│   └── tests/                           # pytest (7 тестов)
├── notification_service/                # модуль С. Ветровой
│   ├── main.py                          # FastAPI: POST /api/webhooks/task_created, /health
│   ├── models.py                        # локальная копия схемы Task
│   └── tests/                           # pytest (4 теста)
├── docs/
│   ├── failure_points_task_service.md          # точки отказа Т-1..Т-5
│   └── failure_points_notification_service.md  # точки отказа Н-1..Н-4
└── scripts/                             # запуск и smoke-проверка
    ├── run_task_service.sh / run_notification_service.sh / run_all.sh / run_all.bat
    └── smoke_test.sh                    # сквозная ручная проверка (curl)
```

## 7. Git-модель командной работы

```
main (защищена) ── PR ──► только merge-коммиты «Merge pull request #N»
 └── dev (интеграционная)
      ├── PR #1 ◄── feature/notifications-service (Васильев Н. С.)
      ├── PR #2 ◄── feature/tasks-service (Орлов М. С. ) — rebase на dev,
      │             ручное разрешение конфликта API_CONTRACT.md
      └── PR #3 ──► dev → main (интеграционный релиз v1.0.0)
```

Посмотреть историю:

```bash
git log --graph --oneline --all --decorate
```

На GitHub/GitLab эта же история воспроизводится пул-реквестами; локально PR
эмулированы merge-коммитами `--no-ff` со стандартными сообщениями
«Merge pull request #N from …». Разрешение конфликта выполнено через
`git rebase dev` (линейная история внутри feature-ветки) — детали в [REPORT.md](REPORT.md).

## 8. Локальные точки отказа

Задокументированы по требованию задания (Этап 3):

- [docs/failure_points_task_service.md](docs/failure_points_task_service.md) — файл БД, недоступность получателя, потеря очереди при рестарте, медленный получатель, расхождение схем;
- [docs/failure_points_notification_service.md](docs/failure_points_notification_service.md) — невалидный payload (422), пик нагрузки, вывод в консоль, «тихая» потеря при невызванном вебхуке.

## 9. Чеклист соответствия заданию

| Этап задания | Где выполнено |
|---|---|
| 1. Роли и распределение | README, раздел 1 |
| 2. Контракт (схема Task, 2 эндпоинта, формат вебхука) | `API_CONTRACT.md` v1.0 |
| 3. Параллельная разработка + тесты + обработка ошибок + точки отказа + осмысленные коммиты | ветки `feature/*`, `task_service/`, `notification_service/`, `docs/` |
| 4. PR, ревью, конфликт и его разрешение, запуск, E2E | PR #1/#2, `REPORT.md`, `scripts/smoke_test.sh` |
| 5. Отчет о конфликтах и решениях | [REPORT.md](REPORT.md) |
