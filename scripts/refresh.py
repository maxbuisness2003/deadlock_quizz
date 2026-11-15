"""Refresh the local item database from the free community Deadlock API.

    python scripts\refresh.py            # update the item catalogue
    python scripts\refresh.py --images   # ... and pre-download the item art
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db, images, ingest  # noqa: E402


def prefetch_images(limit: int = 0) -> int:
    """Download the item art so the site works offline afterwards."""
    rows = db.query("SELECT image FROM items WHERE image IS NOT NULL")
    urls = [row["image"] for row in rows if row["image"]]
    if limit:
        urls = urls[:limit]
    print(f"  images: {len(urls)}")
    done = 0
    for index, path in enumerate(urls, 1):
        url = f"{images.CDN_PREFIX}{path[len('/img/'):]}"
        if images.fetch(url):
            done += 1
        if index % 25 == 0:
            print(f"    {index}/{len(urls)}")
    print(f"  images cached: {done}/{len(urls)}")
    return done


def main() -> int:
    parser = argparse.ArgumentParser(description="Обновить базу предметов Deadlock Quiz")
    parser.add_argument("--images", action="store_true", help="скачать картинки предметов")
    args = parser.parse_args()

    print("Deadlock Quiz: обновление данных")
    started = time.time()
    try:
        counts = ingest.refresh(verbose=False)
    except Exception as exc:  # noqa: BLE001 - report and keep the old data
        print(f"  ! не удалось обновить: {exc}")
        print("  (старые данные в базе остались, сайт продолжит работать)")
        return 1

    print(f"  предметов: {counts.get('items', 0)}")
    print(f"  готово за {time.time() - started:.1f} с")
    if args.images:
        prefetch_images()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
