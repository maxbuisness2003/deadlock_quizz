"""Tiny HTML helpers: the API ships descriptions with inline tags."""

from __future__ import annotations

import html
import re

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def strip_html(text: str | None) -> str:
    """Turn an API description into plain readable text."""
    if not text:
        return ""
    cleaned = _TAG_RE.sub(" ", text)
    cleaned = html.unescape(cleaned)
    cleaned = _SPACE_RE.sub(" ", cleaned)
    return cleaned.strip()


def trim(text: str | None, limit: int = 240) -> str:
    """Shorten a description to a single line."""
    clean = strip_html(text)
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "…"
