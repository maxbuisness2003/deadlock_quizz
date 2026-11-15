#!/usr/bin/env bash
# Загрузить проект на GitHub: https://github.com/maxbuisness2003/deadlock_quizz
set -euo pipefail
cd "$(dirname "$0")"

REPO_URL="https://github.com/maxbuisness2003/deadlock_quizz.git"
REMOTE_NAME="origin"

if ! command -v git >/dev/null 2>&1; then
    echo "Git не найден. Установите его: https://git-scm.com/downloads"
    exit 1
fi

if [ ! -d .git ]; then
    echo "[1/4] Инициализирую репозиторий..."
    git init -b main
else
    echo "[1/4] Репозиторий уже инициализирован."
fi

echo "[2/4] Настраиваю remote..."
git remote remove "$REMOTE_NAME" >/dev/null 2>&1 || true
git remote add "$REMOTE_NAME" "$REPO_URL"
git remote -v

echo
echo "[3/4] Что попадёт в коммит:"
git status --short
echo
read -r -p "  Продолжить? (y/N): " answer
case "$answer" in
    [yY]) ;;
    *) echo "Отменено."; exit 0 ;;
esac

echo
echo "[4/4] Коммичу и отправляю..."
git add -A
git commit -m "feat: Deadlock Quiz - викторина по предметам Deadlock"
git push -u "$REMOTE_NAME" main

echo
echo "Готово! Проект: $REPO_URL"
