"""Снять скриншоты для README.

Требуется Playwright:

    pip install playwright
    playwright install chromium

Сайт должен быть запущен (python run.py). Скриншоты появятся в docs/.

    python scripts\\screenshots.py
"""

from __future__ import annotations

import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - optional dependency
    print("Нужен Playwright: pip install playwright && playwright install chromium")
    raise SystemExit(1)

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
BASE = "http://127.0.0.1:8001"


def shot(page, name: str, wait: float = 1.2) -> None:
    time.sleep(wait)
    path = DOCS / name
    page.screenshot(path=str(path))
    print(f"  {path.relative_to(ROOT)}")


def main() -> int:
    DOCS.mkdir(exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(
            viewport={"width": 1280, "height": 860},
            device_scale_factor=2,
        )

        print("Снимаю главную...")
        page.goto(f"{BASE}/?motion=on", wait_until="networkidle")
        page.wait_for_selector("#start-btn")
        shot(page, "home.png", wait=2.0)

        print("Снимаю вопрос...")
        page.click("#start-btn")
        page.wait_for_selector(".answer")
        shot(page, "question.png", wait=1.2)

        print("Снимаю разбор ответа...")
        page.click(".answer >> nth=0")
        page.wait_for_selector(".feedback")
        shot(page, "answer.png", wait=1.4)

        print("Снимаю итоги...")
        page.click("#q-feedback .btn")
        # проходим раунд целиком, чтобы дойти до экрана результатов
        for _ in range(40):
            if page.query_selector("#screen-result.active"):
                break
            nxt = page.query_selector("#q-feedback .btn")
            if nxt:
                nxt.click()
                time.sleep(0.4)
            options = page.query_selector_all(".answer:not([disabled])")
            if options:
                options[0].click()
                time.sleep(0.5)
        page.wait_for_selector("#screen-result.active")
        shot(page, "result.png", wait=1.6)

        browser.close()
    print("Готово.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
