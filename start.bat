@echo off
chcp 65001 >nul
cls
echo [✓] Очистка и запуск окружения...

:: Перейти в папку проекта
cd /d C:\Users\semen\inv

:: Активировать виртуальное окружение
call .venv\Scripts\activate.bat

:: Запустить бекенд
start "FastAPI Backend" cmd /k "uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

:: Перейти в папку фронта
cd front

:: Запустить фронт (обрати внимание на двойной "--")
start "Frontend (Vite)" cmd /k "npm run dev -- --host"


