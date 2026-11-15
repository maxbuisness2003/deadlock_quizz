@echo off
REM ============================================================
REM   Загрузить Deadlock Quiz на GitHub
REM   https://github.com/maxbuisness2003/deadlock_quizz
REM ============================================================
setlocal
cd /d "%~dp0"

echo.
echo ======================================================
echo    Загружаю проект на GitHub
echo ======================================================
echo.
echo    Сейчас откроется браузер с входом в GitHub.
echo    Войдите под своим аккаунтом и нажмите "Authorize".
echo    После этого скрипт сам отправит файлы.
echo.
echo    (уже настроено: репозиторий создан, файлы сохранены,
echo     адрес remote прописан - осталось только подтвердить вход)
echo.
echo    Если окно браузера не открылось - нажмите Enter
echo    и выполните вручную:  git push -u origin main
echo.

git push -u origin main
if errorlevel 1 (
    echo.
    echo [!] Не получилось отправить.
    echo.
    echo     Если GitHub попросил пароль - вводите НЕ пароль от аккаунта,
    echo     а токен: https://github.com/settings/tokens
    echo     (Repository access -> Generate token -> scope: repo)
    echo.
    pause
    exit /b 1
)

echo.
echo ======================================================
echo    Готово! Проект на GitHub:
echo    https://github.com/maxbuisness2003/deadlock_quizz
echo ======================================================
echo.
pause
