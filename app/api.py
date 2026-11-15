"""HTTP client for the community Deadlock API (api.deadlock-api.com).

The API is free and needs no key. Every response is cached as raw JSON on
disk, so a refresh can be interrupted and resumed, and the quiz keeps working
when the upstream API is down.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from .db import RAW_DIR

BASE_URL = "https://api.deadlock-api.com"
USER_AGENT = "deadlock-quiz/1.0 (+fan quiz site)"


class DeadlockAPI:
    def __init__(
        self,
        base_url: str = BASE_URL,
        cache_dir: Path = RAW_DIR,
        timeout: float = 120.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self._client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "DeadlockAPI":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    def cache_path(self, path: str) -> Path:
        slug = path.strip("/").replace("/", "_").replace("?", "_").replace("&", "_").replace("=", "_")
        return self.cache_dir / f"{slug}.json"

    def get(
        self,
        path: str,
        *,
        use_cache: bool = True,
        max_age_s: float | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """GET a JSON payload, using the on-disk cache when it is fresh enough."""
        cache_file = self.cache_path(path)
        if use_cache and cache_file.exists():
            age = time.time() - cache_file.stat().st_mtime
            if max_age_s is None or age <= max_age_s:
                try:
                    with cache_file.open("r", encoding="utf-8") as fh:
                        return json.load(fh)
                except json.JSONDecodeError:
                    pass  # corrupt cache -> refetch

        url = f"{self.base_url}{path}"
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self._client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
                with cache_file.open("w", encoding="utf-8") as fh:
                    json.dump(payload, fh, ensure_ascii=False)
                return payload
            except Exception as exc:  # noqa: BLE001 - network flakiness
                last_error = exc
                time.sleep(1.5 * (attempt + 1))

        if cache_file.exists():  # serve stale data rather than fail the refresh
            with cache_file.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        raise RuntimeError(f"failed to fetch {url}: {last_error}")

    # -- endpoints used by this project -------------------------------
    def items(self) -> list[dict[str, Any]]:
        return self.get("/v1/assets/items")

    def heroes(self) -> list[dict[str, Any]]:
        return self.get("/v1/assets/heroes")
