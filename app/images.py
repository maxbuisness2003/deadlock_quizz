"""Image proxy with a local disk cache.

The site must not depend on the community CDN being reachable (or fast) at
render time: every remote asset is fetched once, stored under data/img_cache
and served from our own domain afterwards.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import httpx

CDN_PREFIX = "https://assets-bucket.deadlock-api.com/assets-api-res/"

DATA_DIR = Path(os.environ.get("DQ_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
CACHE_DIR = DATA_DIR / "img_cache"

PLACEHOLDER = (
    "data:image/svg+xml;base64,"
    "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NDAiIGhlaWdodD0iMTYwIj4"
    "PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjE2MCIgZmlsbD0iIzE4MjEyZSIgcng9IjEwIi8+"
    "PHBhdGggZD0iTTMyIDgwaC0yNCAxNGg0bC0xNSAzMnoiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzM4NDc1"
    "IiBzdHJva2Utd2lkdGg9IjIiLz48L3N2Zz4="
)

_SUFFIXES = {".png", ".webp", ".jpg", ".jpeg", ".svg", ".gif"}


def proxy_path(url: str | None) -> str | None:
    """Convert a CDN url into a local proxy path."""
    if not url:
        return None
    if url.startswith("/"):
        return url
    if CDN_PREFIX in url:
        return "/img/" + url.split(CDN_PREFIX, 1)[1]
    return url


def cache_file(url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]
    suffix = Path(url.split("?", 1)[0]).suffix.lower()
    if suffix not in _SUFFIXES:
        suffix = ".png"
    return CACHE_DIR / f"{digest}{suffix}"


def fetch(url: str) -> bytes | None:
    """Fetch an asset and store it in the cache. Returns None on failure."""
    target = cache_file(url)
    if target.exists() and target.stat().st_size > 0:
        return target.read_bytes()
    try:
        with httpx.Client(
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": "deadlock-quiz"},
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.content
    except Exception:  # noqa: BLE001 - missing art must not break the page
        return None
    if not data:
        return None
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(target)
    return data


def prefetch(urls: list[str]) -> None:
    """Warm the cache for a set of remote urls (best effort)."""
    for url in urls:
        if url and not cache_file(url).exists():
            fetch(url)
