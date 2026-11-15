"""ETL: pull the community API, normalise it and store it in SQLite.

Everything is idempotent: re-running a refresh replaces the affected table.
The heavy payload is cached on disk by `api`, so a refresh that dies half way
through can simply be re-run.

The normalisation that matters for the quiz: for every shopable item we keep
the properties that are actually shown on the item tooltip (`tooltip_sections`),
because those are the numbers a player can actually read in game.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from . import db
from .api import DeadlockAPI
from .images import proxy_path
from .textutil import trim

NUM_RE = re.compile(r"^-?\d+(\.\d+)?$")

# Properties whose tooltip entry is a status effect rather than a plain number.
_IGNORED_PROPS = {"StatusEffectInfiniteClip"}


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str) and NUM_RE.match(value.strip()):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _unit(prop: dict[str, Any]) -> str:
    unit = (prop.get("postfix") or "").strip()
    unit = unit.replace("% DPS", "%/s")
    if unit.startswith(" ") and unit.endswith(" %"):
        unit = "%"
    return unit


def _tooltip_props(item: dict[str, Any]) -> list[dict[str, Any]]:
    """Properties the player sees on the item card, in tooltip order."""
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for section in item.get("tooltip_sections") or []:
        section_type = section.get("section_type") or "innate"
        for attribute in section.get("section_attributes") or []:
            for key, elevated in (
                ("properties", False),
                ("elevated_properties", True),
                ("important_properties", False),
            ):
                for name in attribute.get(key) or []:
                    if name in seen or name in _IGNORED_PROPS:
                        continue
                    prop = (item.get("properties") or {}).get(name)
                    if not isinstance(prop, dict):
                        continue
                    value = _number(prop.get("value"))
                    if value is None:
                        continue
                    label = (prop.get("label") or name).strip()
                    seen.add(name)
                    entries.append(
                        {
                            "prop": name,
                            "label": label,
                            "unit": _unit(prop),
                            "value": value,
                            "section": section_type,
                            "elevated": elevated,
                        }
                    )
    return entries


def _upgrade(item: dict[str, Any]) -> dict[str, Any]:
    """The single tier-upgrade step of an item (Deadlock items upgrade once)."""
    steps = item.get("upgrades") or []
    bonuses: dict[str, float] = {}
    for step in steps:
        for prop in step.get("property_upgrades") or []:
            amount = _number(prop.get("bonus"))
            if amount is None:
                continue
            name = prop.get("name")
            bonuses[name] = bonuses.get(name, 0.0) + amount
    tier = item.get("item_tier")
    # Tier 5 is the top of the shop - there is nothing to upgrade into.
    next_tier = tier + 1 if isinstance(tier, int) and 0 < tier < 5 else None
    return {
        "next_tier": next_tier,
        "bonuses": bonuses,
    }


def _mark_ambiguous(stats: list[dict[str, Any]]) -> None:
    """Two different numbers behind the same label would make a broken question."""
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for stat in stats:
        buckets.setdefault((stat["label"], stat["unit"]), []).append(stat)
    for group in buckets.values():
        if len({stat["value"] for stat in group}) > 1:
            for stat in group:
                stat["ambiguous"] = True


def load_items(api: DeadlockAPI, conn) -> int:
    payload = api.items()
    rows = []
    for item in payload:
        if item.get("type") != "upgrade" or not item.get("shopable"):
            continue
        if item.get("disabled"):
            continue
        stats = _tooltip_props(item)
        _mark_ambiguous(stats)
        description = item.get("description")
        if isinstance(description, dict):
            description = description.get("desc") or description.get("description") or ""
        elif isinstance(description, list):
            description = " ".join(str(part) for part in description)
        else:
            description = description or ""
        image = proxy_path(
            item.get("shop_image_webp")
            or item.get("shop_image")
            or item.get("image_webp")
            or item.get("image")
        )
        rows.append(
            (
                item.get("id"),
                item.get("class_name", ""),
                item.get("name", ""),
                item.get("item_slot_type"),
                item.get("item_tier"),
                item.get("cost"),
                1 if item.get("is_active_item") else 0,
                1 if item.get("shopable") else 0,
                trim(description) or None,
                image,
                json.dumps(stats, ensure_ascii=False),
                json.dumps(_upgrade(item), ensure_ascii=False),
                json.dumps(item, ensure_ascii=False),
            )
        )
    conn.executemany(
        """INSERT INTO items (id, class_name, name, slot, tier, cost, is_active, shopable,
               description, image, stats, upgrade, raw)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(class_name) DO UPDATE SET
               id=excluded.id, name=excluded.name, slot=excluded.slot, tier=excluded.tier,
               cost=excluded.cost, is_active=excluded.is_active, shopable=excluded.shopable,
               description=excluded.description, image=excluded.image,
               stats=excluded.stats, upgrade=excluded.upgrade, raw=excluded.raw""",
        rows,
    )
    return len(rows)


def refresh(verbose: bool = True) -> dict[str, int]:
    """Pull the item catalogue and rebuild the local database."""
    db.init_db()
    conn = db.connect()
    counts: dict[str, int] = {}
    try:
        with DeadlockAPI() as api:
            counts["items"] = load_items(api, conn)
        conn.commit()
    finally:
        conn.close()
    db.set_meta("last_refresh", time.time())
    db.set_meta("counts", counts)
    if verbose:
        print(f"  items: {counts.get('items', 0)}")
    return counts
