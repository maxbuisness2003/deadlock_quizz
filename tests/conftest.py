"""Test fixtures: an isolated temporary database for the quiz tests."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# The database path is resolved at import time, so the env must be set first.
TMP_DIR = Path(tempfile.mkdtemp(prefix="deadlock-quiz-tests-"))
os.environ.setdefault("DQ_DATA_DIR", str(TMP_DIR))
os.environ.setdefault("DQ_DB_PATH", str(TMP_DIR / "test.db"))

import pytest  # noqa: E402

from app import db  # noqa: E402

TITANIC_STATS = [
    {
        "prop": "BaseAttackDamagePercent",
        "label": "Weapon Damage",
        "unit": "%",
        "value": 14.0,
        "section": "innate",
        "elevated": False,
    },
    {
        "prop": "BonusClipSizePercent",
        "label": "Max Ammo",
        "unit": "%",
        "value": 100.0,
        "section": "innate",
        "elevated": True,
    },
]

TITANIC_UPGRADE = {"next_tier": 3, "bonuses": {"BaseAttackDamagePercent": 18.0, "BonusClipSizePercent": 70.0}}

BOUNDLESS_STATS = [
    {
        "prop": "BonusHealth",
        "label": "Bonus Health",
        "unit": "",
        "value": 75.0,
        "section": "innate",
        "elevated": False,
    },
    {
        "prop": "TechPower",
        "label": "Spirit Power",
        "unit": "",
        "value": 30.0,
        "section": "innate",
        "elevated": False,
    },
]


def _row(item_id, class_name, name, slot, tier, cost, stats, upgrade):
    return (
        item_id,
        class_name,
        name,
        slot,
        tier,
        cost,
        0,
        1,
        None,
        f"/img/images/items/{slot}/{class_name}.webp",
        json.dumps(stats, ensure_ascii=False),
        json.dumps(upgrade, ensure_ascii=False),
        "{}",
    )


@pytest.fixture(scope="session")
def seeded_db():
    """A tiny database with two real items from the game."""
    db.init_db()
    conn = db.connect()
    conn.executemany(
        """INSERT INTO items (id, class_name, name, slot, tier, cost, is_active, shopable,
               description, image, stats, upgrade, raw)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [
            _row(
                1, "upgrade_titan_round", "Titanic Magazine", "weapon", 2, 1600,
                TITANIC_STATS, TITANIC_UPGRADE,
            ),
            _row(
                2, "upgrade_boundless_spirit", "Boundless Spirit", "vitality", 4, 6400,
                BOUNDLESS_STATS, {},
            ),
        ],
    )
    conn.commit()
    conn.close()
    return db
