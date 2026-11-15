"""Deadlock Quiz - web application.

A fan quiz for Deadlock: the site picks a random item from the game and asks
you to guess one of its numbers (how much damage does the Titanic Magazine
give, what does it cost, which tier it belongs to). All data comes from the
free community API and is cached locally, so the game works offline too.
"""

from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import db, game, images
from .quiz import SLOT_LABELS

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

class RevalidatingStaticFiles(StaticFiles):
    """Serve static files but always let the browser revalidate them."""

    def file_response(self, *args: Any, **kwargs: Any):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response


app = FastAPI(title="Deadlock Quiz", docs_url="/api/docs", redoc_url=None)
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount(
    "/static",
    RevalidatingStaticFiles(directory=str(STATIC_DIR)),
    name="static",
)

COOKIE = "dq_token"

MEDIA_TYPES = {
    ".png": "image/png",
    ".webp": "image/webp",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".gif": "image/gif",
}


def _cookie_value(request: Request, name: str) -> str | None:
    return request.cookies.get(name)


def _static_version() -> str:
    """Cache-busting token for the css/js: changes whenever a file changes."""
    newest = 0.0
    for path in STATIC_DIR.rglob("*"):
        if path.is_file():
            newest = max(newest, path.stat().st_mtime)
    return str(int(newest))


# ---------------------------------------------------------------------------
# pages
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    count = db.items_count()
    last_refresh = db.get_meta("last_refresh")
    response = templates.TemplateResponse(
        request,
        "index.html",
        {
            "items_count": count,
            "has_data": count > 0,
            "slots": [{"key": key, "label": label} for key, label in SLOT_LABELS.items()],
            "last_refresh": (
                time.strftime("%d.%m.%Y %H:%M", time.localtime(last_refresh)) if last_refresh else None
            ),
            "time_limit": game.TIME_LIMIT,
            "best": request.cookies.get("dq_best", "0"),
            "static_version": _static_version(),
        },
    )
    # the html carries the cache-busting token for css/js - it must not be stale
    response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


# ---------------------------------------------------------------------------
# api
# ---------------------------------------------------------------------------
async def _json_body(request: Request) -> dict[str, Any]:
    """Read a JSON body without blowing up on a broken request."""
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001 - any malformed body is just an empty one
        return {}
    return payload if isinstance(payload, dict) else {}


@app.post("/api/start")
async def api_start(request: Request):
    payload = await _json_body(request)
    try:
        length = int(payload.get("length") or 15)
    except (TypeError, ValueError):
        length = 15
    settings = {
        "slot": str(payload.get("slot") or "all"),
        "mode": "number" if payload.get("mode") == "number" else "buttons",
        "length": max(1, min(length, 100)),
    }
    kinds = payload.get("kinds") or None
    if kinds:
        settings["kinds"] = kinds

    session = game.new_game(settings, random.Random())
    if not session.questions:
        return JSONResponse(
            {"error": "Нет данных. Выполните: python scripts/refresh.py"}, status_code=503
        )

    response = JSONResponse({"question": game.question_payload(session), "token": session.token})
    response.set_cookie(
        COOKIE,
        session.token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 12,
    )
    return response


@app.post("/api/answer")
async def api_answer(request: Request):
    payload = await _json_body(request)
    session = game.get_game(_cookie_value(request, COOKIE))
    if session is None:
        return JSONResponse({"error": "Раунд не найден, начните заново"}, status_code=404)

    try:
        elapsed = float(payload.get("elapsed") or 0.0)
    except (TypeError, ValueError):
        elapsed = 0.0

    feedback = game.answer(
        session,
        payload.get("answer"),
        session.settings.get("mode", "buttons"),
        elapsed,
    )
    response = JSONResponse(feedback)
    if feedback.get("done"):
        best = max(int(request.cookies.get("dq_best", "0") or 0), int(feedback["summary"]["score"]))
        response.set_cookie("dq_best", str(best), httponly=False, samesite="lax", max_age=60 * 60 * 24 * 30)
    return response


@app.get("/api/hint")
async def api_hint(request: Request):
    session = game.get_game(_cookie_value(request, COOKIE))
    if session is None:
        return JSONResponse({"error": "Раунд не найден"}, status_code=404)
    return JSONResponse({"hint": game.use_hint(session)})


@app.get("/api/stats")
def api_stats():
    return {
        "items": db.items_count(),
        "last_refresh": db.get_meta("last_refresh"),
        "counts": db.get_meta("counts"),
    }


# ---------------------------------------------------------------------------
# images
# ---------------------------------------------------------------------------
@app.get("/img/{path:path}")
def proxy_image(path: str):
    url = f"{images.CDN_PREFIX}{path}"
    data = images.fetch(url)
    if data is None:
        return Response(images.PLACEHOLDER, media_type="image/svg+xml")
    suffix = Path(path).suffix.lower()
    return Response(
        data,
        media_type=MEDIA_TYPES.get(suffix, "image/png"),
        headers={"Cache-Control": "public, max-age=604800"},
    )


@app.get("/healthz")
def healthz():
    return {"ok": True, "items": db.items_count()}
