@echo off
REM ============================================================
REM   Запустить сайт И сразу получить публичную ссылку
REM   Ссылка работает, пока открыто это окно и включен ПК.
REM ============================================================
setlocal
cd /d "%~dp0"

set CF=%~dp0tools\cloudflared.exe
set PORT=8001

echo.
echo ======================================================
echo    Deadlock Quiz - локальный запуск + публичная ссылка
echo ======================================================
echo.

REM --- окружение ------------------------------------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Создаю окружение...
    python -m venv .venv || goto :error
    .\.venv\Scripts\python.exe -m pip install -q -r requirements.txt || goto :error
)

REM --- данные ---------------------------------------------------------------
if not exist "data\quiz.db" (
    echo [2/3] Загружаю каталог предметов...
    .\.venv\Scripts\python.exe scripts\refresh.py || goto :error
)

REM --- туннель --------------------------------------------------------------
if not exist "%CF%" (
    echo [3/3] Скачиваю cloudflared...
    if not exist "%~dp0tools" mkdir "%~dp0tools"
    powershell -NoProfile -Command ^
        "Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile '%CF%'" || goto :error
)

echo.
echo ======================================================
echo    Сайт:  http://127.0.0.1:%PORT%
echo    Сейчас будет публичная ссылка - скопируйте её.
echo    Чтобы сайт был доступен из интернета, оставьте
echo    это окно открытым.
echo ======================================================
echo.

start "Deadlock Quiz" /min cmd /c ".\.venv\Scripts\python.exe run.py --port %PORT%"
timeout /t 3 /nobreak >nul

"%CF%" tunnel --url http://127.0.0.1:%PORT% --no-autoupdate

echo.
echo Туннель закрыт, публичная ссылка больше не работает.
pause
exit /b 0

:error
echo.
echo [!] Что-то пошло не так. Попробуйте запустить вручную:
echo     .\.venv\Scripts\python.exe run.py
echo.
pause
exit /b 1
