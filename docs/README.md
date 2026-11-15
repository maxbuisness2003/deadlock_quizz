# Скриншоты

Здесь лежат картинки для README. Они генерируются автоматически:

```powershell
.\.venv\Scripts\python.exe -m pip install playwright
.\.venv\Scripts\python.exe -m playwright install chromium

# в одном окне - сайт
.\.venv\Scripts\python.exe run.py

# в другом - снимки
.\.venv\Scripts\python.exe scripts\screenshots.py
```

Получится:

| Файл | Что на нём |
|---|---|
| `home.png` | главная: настройки раунда |
| `question.png` | игровой экран с вопросом |
| `answer.png` | разбор ответа с таблицей характеристик |
| `result.png` | итоги раунда |

Папка `docs/` целиком не попадает в git (см. `.gitignore`) — картинки
подтягиваются в репозиторий вручную, когда нужно обновить README.
