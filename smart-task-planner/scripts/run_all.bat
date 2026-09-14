@echo off
rem Запуск обоих сервисов на Windows (каждый в своём окне cmd).
rem Использование: scripts\run_all.bat

start "Task Service (8001)" cmd /k uvicorn task_service.main:app --host 0.0.0.0 --port 8001
start "Notification Service (8002)" cmd /k uvicorn notification_service.main:app --host 0.0.0.0 --port 8002

echo Оба сервиса запущены в отдельных окнах:
echo   Task Service:        http://localhost:8001/docs
echo   Notification Service: http://localhost:8002/docs
