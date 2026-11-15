"""Question engine for the Deadlock item quiz.

Every question is built from the item data of the community API:

* ``stat``    - how much a stat is worth (e.g. "Titanic Magazine gives +14% Weapon Damage")
* ``upgrade`` - the same stat after the item has been upgraded to the next tier
* ``price``   - how many souls the item costs
* ``tier``    - which shop tier the item belongs to

Distractors are drawn from the real values of the same stat on other items,
so a wrong option is always a number that actually exists in the game.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from typing import Any, Iterable

from . import db

SLOT_LABELS = {"weapon": "Оружие", "vitality": "Витальность", "spirit": "Спирит"}

# How often each kind of question shows up.
KIND_WEIGHTS = {"stat": 62, "upgrade": 20, "price": 12, "tier": 6}

UNIT_SUFFIX = {
    "%": " %",
    "s": " с",
    "m": " м",
    "x": "×",
    "/s": "/с",
    "%/s": " %/с",
    " HP/s": " HP/с",
}


# ---------------------------------------------------------------------------
# data model
# ---------------------------------------------------------------------------
@dataclass
class Item:
    id: int
    class_name: str
    name: str
    slot: str
    tier: int
    cost: int
    is_active: bool
    image: str | None
    description: str | None
    stats: list[dict[str, Any]] = field(default_factory=list)
    upgrade: dict[str, Any] = field(default_factory=dict)

    @property
    def slot_label(self) -> str:
        return SLOT_LABELS.get(self.slot, "Предмет")

    @property
    def tier_label(self) -> str:
        return f"{self.tier} тир"

    def stat_by_prop(self, prop: str) -> dict[str, Any] | None:
        for stat in self.stats:
            if stat["prop"] == prop:
                return stat
        return None


@dataclass
class Question:
    id: str
    kind: str
    item: Item
    prompt: str
    answer_value: float
    answer_text: str
    unit: str
    options: list[str]
    correct: int
    hint: str
    detail: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# formatting
# ---------------------------------------------------------------------------
def fmt_number(value: float) -> str:
    """Plain number without a trailing '.0'."""
    if value == int(value):
        return str(int(value))
    return f"{value:.1f}".rstrip("0").rstrip(".")


def fmt_value(value: float, unit: str = "") -> str:
    suffix = UNIT_SUFFIX.get(unit, f" {unit}" if unit else "")
    return f"{fmt_number(value)}{suffix}"


def fmt_cost(value: int) -> str:
    return f"{value:,}".replace(",", "\u2009") + " душ"


def fmt_tier(value: int) -> str:
    return f"{value} тир"


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------
def load_items(slot: str | None = None) -> list[Item]:
    sql = "SELECT * FROM items WHERE shopable = 1"
    params: list[Any] = []
    if slot and slot != "all":
        sql += " AND slot = ?"
        params.append(slot)
    sql += " ORDER BY name"
    items: list[Item] = []
    for row in db.query(sql, params):
        try:
            stats = json.loads(row["stats"] or "[]")
        except json.JSONDecodeError:
            stats = []
        try:
            upgrade = json.loads(row["upgrade"] or "{}")
        except json.JSONDecodeError:
            upgrade = {}
        items.append(
            Item(
                id=row["id"],
                class_name=row["class_name"],
                name=row["name"],
                slot=row["slot"] or "",
                tier=row["tier"] or 0,
                cost=row["cost"] or 0,
                is_active=bool(row["is_active"]),
                image=row["image"],
                description=row["description"],
                stats=stats,
                upgrade=upgrade,
            )
        )
    return items


# ---------------------------------------------------------------------------
# distractors
# ---------------------------------------------------------------------------
def _numeric_distractors(
    value: float,
    pool: Iterable[float],
    rng: random.Random,
    count: int = 3,
) -> list[float]:
    """Pick wrong but plausible numbers: the closest real values of the same stat."""
    others = sorted(
        {round(float(v), 4) for v in pool if abs(float(v) - value) > 1e-6},
        key=lambda v: abs(v - value),
    )
    if len(others) < count:
        others = _perturbations(value, rng)
    else:
        # draw from the closest ones, but not always the very closest -> variety
        window = others[: max(count, min(len(others), count * 3))]
        others = rng.sample(window, count) if len(window) >= count else others[:count]
    picked: list[float] = []
    for candidate in others:
        if len(picked) >= count:
            break
        if all(abs(candidate - existing) > 1e-6 for existing in picked):
            picked.append(candidate)
    while len(picked) < count:
        extra = rng.choice(_perturbations(value, rng))
        if all(abs(extra - existing) > 1e-6 for existing in picked):
            picked.append(extra)
    return picked


def _perturbations(value: float, rng: random.Random) -> list[float]:
    """Fallback numbers when a stat is unique to a single item."""
    if value <= 0:
        return [5.0, 10.0, 15.0, 20.0, 25.0, 30.0]
    step = max(1.0, round(value * 0.1))
    candidates = [
        value * 0.5,
        value * 0.75,
        value * 1.25,
        value * 1.5,
        value - step,
        value + step,
        value - step * 2,
        value + step * 2,
    ]
    rng.shuffle(candidates)
    return [c for c in candidates if c >= 0]


# ---------------------------------------------------------------------------
# question builders
# ---------------------------------------------------------------------------
def _stat_prompt(item: Item, stat: dict[str, Any], upgraded: bool) -> str:
    label = stat["label"]
    unit = stat["unit"]
    name = item.name
    if upgraded:
        next_tier = (item.upgrade or {}).get("next_tier")
        suffix = f" после прокачки до {next_tier} тира"
    else:
        suffix = ""
    if unit == "%":
        return f"Сколько процентов даёт «{label}» у {name}{suffix}?"
    if unit == "s":
        return f"Сколько секунд длится «{label}» у {name}{suffix}?"
    if unit == "m":
        return f"Сколько метров даёт «{label}» у {name}{suffix}?"
    if unit in ("/s", "%/s"):
        return f"Сколько «{label}» в секунду даёт {name}{suffix}?"
    return f"Сколько даёт «{label}» у {name}{suffix}?"


def _detail(item: Item) -> list[dict[str, Any]]:
    """The full stat sheet of an item, used for the explanation screen."""
    bonuses = (item.upgrade or {}).get("bonuses") or {}
    detail: list[dict[str, Any]] = []
    for stat in item.stats:
        if stat.get("ambiguous"):
            continue
        bonus = bonuses.get(stat["prop"])
        entry = {
            "label": stat["label"],
            "unit": stat["unit"],
            "value": fmt_value(stat["value"], stat["unit"]),
            "section": stat.get("section", "innate"),
            "elevated": bool(stat.get("elevated")),
            "bonus": fmt_value(bonus, stat["unit"]) if bonus is not None else None,
        }
        detail.append(entry)
    detail.sort(key=lambda e: (not e["elevated"], e["section"] != "innate", e["label"]))
    return detail


def build_questions(
    items: list[Item],
    rng: random.Random,
    *,
    count: int = 20,
    kinds: Iterable[str] | None = None,
) -> list[Question]:
    """Build a list of questions, shuffled and de-duplicated."""
    pools: dict[tuple[str, str], list[float]] = {}
    for item in items:
        for stat in item.stats:
            if stat.get("ambiguous"):
                continue
            pools.setdefault((stat["label"], stat["unit"]), []).append(stat["value"])
    cost_pool = {float(item.cost) for item in items} | {800.0, 1600.0, 3200.0, 6400.0, 9999.0}
    tier_pool = [1.0, 2.0, 3.0, 4.0, 5.0]

    candidates: list[tuple[str, Item, dict[str, Any] | None, float]] = []
    for item in items:
        for stat in item.stats:
            if stat.get("ambiguous"):
                continue
            candidates.append(("stat", item, stat, stat["value"]))
            bonus = (item.upgrade or {}).get("bonuses", {}).get(stat["prop"])
            next_tier = (item.upgrade or {}).get("next_tier")
            if bonus is not None and next_tier is not None:
                total = stat["value"] + bonus
                if abs(total - stat["value"]) > 1e-6:
                    candidates.append(("upgrade", item, stat, total))
        candidates.append(("price", item, None, float(item.cost)))
        candidates.append(("tier", item, None, float(item.tier)))

    wanted = list(kinds) if kinds else list(KIND_WEIGHTS)
    weighted: list[tuple[str, Item, dict[str, Any] | None, float]] = []
    for kind in wanted:
        weight = KIND_WEIGHTS.get(kind, 10)
        pool = [c for c in candidates if c[0] == kind]
        if not pool:
            continue
        # the more questions are asked, the wider the pool we sample from
        samples = max(weight * 8, int(count * 1.5))
        weighted.extend(rng.choices(pool, weights=[weight] * len(pool), k=samples))

    rng.shuffle(weighted)
    questions: list[Question] = []
    used_prompts: set[str] = set()
    for kind, item, stat, value in weighted:
        if len(questions) >= count:
            break
        question = _make_question(kind, item, stat, value, pools, cost_pool, tier_pool, rng)
        if question is None or question.prompt in used_prompts:
            continue
        used_prompts.add(question.prompt)
        questions.append(question)
    return questions


def _make_question(
    kind: str,
    item: Item,
    stat: dict[str, Any] | None,
    value: float,
    pools: dict[tuple[str, str], list[float]],
    cost_pool: list[float],
    tier_pool: list[float],
    rng: random.Random,
) -> Question | None:
    if kind in ("stat", "upgrade"):
        if stat is None:
            return None
        unit = stat["unit"]
        pool = pools.get((stat["label"], unit), [])
        wrong = _numeric_distractors(value, pool, rng)
        prompt = _stat_prompt(item, stat, upgraded=kind == "upgrade")
        answer_text = fmt_value(value, unit)
        hint = _digit_hint(value)
        options = [answer_text] + [fmt_value(w, unit) for w in wrong]
    elif kind == "price":
        wrong = _numeric_distractors(value, cost_pool, rng)
        prompt = f"Сколько душ стоит {item.name}?"
        answer_text = fmt_cost(int(value))
        hint = _digit_hint(value)
        options = [answer_text] + [fmt_cost(int(w)) for w in wrong]
    elif kind == "tier":
        wrong = _numeric_distractors(value, tier_pool, rng)
        prompt = f"На каком тире магазина продаётся {item.name}?"
        answer_text = fmt_tier(int(value))
        hint = _tier_hint(int(value))
        options = [answer_text] + [fmt_tier(int(w)) for w in wrong]
    else:  # pragma: no cover - guarded by the caller
        return None

    # de-duplicate option texts (two distractors may round to the same string)
    unique: list[str] = []
    for text in options:
        if text not in unique:
            unique.append(text)
    while len(unique) < 4:
        candidate = _extra_option(kind, value, rng, unique)
        if candidate is None:
            break
        unique.append(candidate)
    options = unique
    rng.shuffle(options)
    correct = options.index(answer_text)

    return Question(
        id=f"{kind}:{item.class_name}:{stat['prop'] if stat else kind}:{value}",
        kind=kind,
        item=item,
        prompt=prompt,
        answer_value=value,
        answer_text=answer_text,
        unit=(stat["unit"] if stat else ""),
        options=options,
        correct=correct,
        hint=hint,
        detail=_detail(item),
    )


def _extra_option(kind: str, value: float, rng: random.Random, existing: list[str]) -> str | None:
    for _ in range(24):
        if kind == "price":
            candidate = fmt_cost(int(rng.choice([800, 1600, 3200, 6400, 9999])))
        elif kind == "tier":
            candidate = fmt_tier(rng.randint(1, 5))
        else:
            candidate = fmt_value(rng.choice(_perturbations(value, rng)))
        if candidate not in existing:
            return candidate
    return None


def _digit_hint(value: float) -> str:
    text = fmt_number(abs(value))
    if value < 0:
        if text and text[0].isdigit():
            return f"Ответ отрицательный, модуль начинается с цифры «{text[0]}»"
        return "Ответ отрицательный"
    if text and text[0].isdigit():
        return f"Ответ начинается с цифры «{text[0]}»"
    return "Ответ — небольшое целое число"


def _tier_hint(tier: int) -> str:
    if tier <= 2:
        return "Ответ: тир 1 или 2"
    if tier <= 4:
        return "Ответ: тир 3 или 4"
    return "Ответ: тир 5"
