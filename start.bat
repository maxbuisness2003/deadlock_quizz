@echo off
REM Deadlock Quiz - запуск в один клик (Windows)
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Создаю окружение...
    python -m venv .venv || goto :error
)

echo [1/3] Ставлю зависимости...
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || goto :error

echo [2/3] Обновляю каталог предметов...
".venv\Scripts\python.exe" scripts\refresh.py || goto :error

echo [3/3] Запускаю сайт: http://127.0.0.1:8001
".venv\Scripts\python.exe" run.py
goto :eof

:error
echo.
echo Не удалось запустить. Проверьте, что Python установлен и доступен в PATH.
pause
