# Contributing

Спасибо, что хотите помочь! Ниже — короткая памятка.

## Локальный запуск

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts\refresh.py
.\.venv\Scripts\python.exe run.py
```

Сайт откроется на http://127.0.0.1:8001

## Перед коммитом

```powershell
.\.venv\Scripts\python.exe -m pytest -q     # тесты
.\.venv\Scripts\python.exe -m ruff check app scripts tests
```

## Как устроен код

| Слой | Файл | Что делает |
|---|---|---|
| Данные | `app/api.py`, `app/ingest.py` | Тянет открытый API, нормализует предметы в SQLite |
| Логика | `app/quiz.py` | Собирает вопрос и варианты ответа |
| Игра | `app/game.py` | Состояние раунда, проверка ответов, очки |
| Веб | `app/main.py` | Роуты FastAPI, шаблоны, прокси картинок |
| Фронт | `app/static/`, `app/templates/` | CSS и JS без сборки (npm не нужен) |

## Правила

1. **Данные берутся только из API** — никаких выдуманных характеристик.
2. **Вопрос задаётся только по тому, что видно в игре**: характеристики берутся
   из `tooltip_sections`, а не из всех полей `properties`.
3. **Варианты ответа — реальные числа** того же параметра на других предметах.
4. **Интерфейс на русском**, названия предметов и характеристик — как в игре.
5. Не закоммитывайте `data/raw/`, `data/img_cache/` и `.venv/`.

## Добавление нового типа вопроса

1. Добавьте генератор кандидатов в `app/quiz.py` → `build_questions`.
2. Опишите формат в `_make_question`: промпт, правильный ответ, варианты, подсказка.
3. Покройте тестом в `tests/test_quiz.py`.

## Данные

Каталог предметов обновляется автоматически раз в неделю
(`.github/workflows/refresh-data.yml`). Локально:

```powershell
.\.venv\Scripts\python.exe scripts\refresh.py
```
