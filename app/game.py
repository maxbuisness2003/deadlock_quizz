"""Game session state machine.

A round of the quiz lives on the server: the browser only ever receives the
visible part of a question, never the index of the right answer.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from .quiz import Question, build_questions, load_items

TIME_LIMIT = 25.0
MAX_SESSIONS = 200
HINT_PENALTY = 30
BASE_POINTS = 100
MAX_SPEED_BONUS = 50
STREAK_STEP = 25
MAX_STREAK_MULT = 6

_SESSIONS: dict[str, "Game"] = {}


@dataclass
class AnswerRecord:
    question_id: str
    kind: str
    prompt: str
    item_name: str
    image: str | None
    slot: str
    slot_label: str
    tier: int
    given: str
    correct_text: str
    is_correct: bool
    elapsed: float
    points: int


@dataclass
class Game:
    token: str
    settings: dict[str, Any]
    questions: list[Question]
    index: int = 0
    score: int = 0
    streak: int = 0
    best_streak: int = 0
    correct: int = 0
    records: list[AnswerRecord] = field(default_factory=list)
    hints_used: set[int] = field(default_factory=set)
    started_at: float = field(default_factory=time.time)
    finished: bool = False

    @property
    def current(self) -> Question | None:
        if 0 <= self.index < len(self.questions):
            return self.questions[self.index]
        return None


# ---------------------------------------------------------------------------
# session store
# ---------------------------------------------------------------------------
def _evict() -> None:
    while len(_SESSIONS) > MAX_SESSIONS:
        oldest = min(_SESSIONS.items(), key=lambda kv: kv[1].started_at)[0]
        _SESSIONS.pop(oldest, None)


def get_game(token: str | None) -> Game | None:
    if not token:
        return None
    return _SESSIONS.get(token)


def new_game(settings: dict[str, Any], rng) -> Game:
    slot = settings.get("slot") or "all"
    mode = settings.get("mode") or "buttons"
    length = int(settings.get("length") or 15)
    kinds = settings.get("kinds") or None

    items = load_items(slot)
    if not items:
        items = load_items("all")
    questions = build_questions(items, rng, count=length, kinds=kinds)
    if not questions:
        return Game(token="", settings=settings, questions=[])

    token = secrets.token_urlsafe(16)
    game = Game(
        token=token,
        settings={"slot": slot, "mode": mode, "length": length},
        questions=questions,
    )
    _SESSIONS[token] = game
    _evict()
    return game


# ---------------------------------------------------------------------------
# answers
# ---------------------------------------------------------------------------
def _tolerance(value: float) -> float:
    return max(0.01, abs(value) * 0.005)


def check_answer(question: Question, given: Any, mode: str) -> tuple[bool, str]:
    """Validate the answer of the player.

    ``buttons`` mode sends the index of the chosen option, ``number`` mode
    sends the typed value.
    """
    if mode == "number":
        raw = str(given).strip().replace(",", ".").replace(" ", "").replace("%", "")
        try:
            value = float(raw)
        except ValueError:
            return False, str(given)
        if abs(value - question.answer_value) <= _tolerance(question.answer_value):
            return True, str(given)
        return False, str(given)
    try:
        index = int(given)
    except (TypeError, ValueError):
        return False, str(given)
    if 0 <= index < len(question.options):
        return index == question.correct, question.options[index]
    if index == -1:
        return False, "время вышло"
    return False, str(given)


def score_for(is_correct: bool, elapsed: float, streak_before: int, hint_used: bool) -> int:
    if not is_correct:
        return 0
    speed = int(MAX_SPEED_BONUS * max(0.0, 1.0 - elapsed / TIME_LIMIT))
    streak = STREAK_STEP * min(streak_before, MAX_STREAK_MULT)
    return max(0, BASE_POINTS + speed + streak - (HINT_PENALTY if hint_used else 0))


def answer(
    game: Game,
    given: Any,
    mode: str,
    elapsed: float = 0.0,
) -> dict[str, Any]:
    """Apply an answer to the game and return the feedback payload."""
    question = game.current
    if question is None:
        return {"done": True, "summary": summary(game)}

    elapsed = max(0.0, min(float(elapsed or 0.0), TIME_LIMIT))
    is_correct, given_text = check_answer(question, given, mode)
    hint_used = game.index in game.hints_used
    points = score_for(is_correct, elapsed, game.streak, hint_used)

    given_index: int | None = None
    if mode != "number":
        try:
            candidate = int(given)
        except (TypeError, ValueError):
            candidate = -1
        if 0 <= candidate < len(question.options):
            given_index = candidate

    if is_correct:
        game.streak += 1
        game.best_streak = max(game.best_streak, game.streak)
        game.correct += 1
    else:
        game.streak = 0
    game.score += points

    game.records.append(
        AnswerRecord(
            question_id=question.id,
            kind=question.kind,
            prompt=question.prompt,
            item_name=question.item.name,
            image=question.item.image,
            slot=question.item.slot,
            slot_label=question.item.slot_label,
            tier=question.item.tier,
            given=given_text,
            correct_text=question.answer_text,
            is_correct=is_correct,
            elapsed=elapsed,
            points=points,
        )
    )
    game.index += 1

    feedback = {
        "correct": is_correct,
        "given": given_text,
        "given_index": given_index,
        "correct_text": question.answer_text,
        "correct_index": question.correct,
        "options": question.options,
        "points": points,
        "elapsed": elapsed,
        "detail": question.detail,
        "item": {
            "name": question.item.name,
            "image": question.item.image,
            "slot": question.item.slot,
            "slot_label": question.item.slot_label,
            "tier": question.item.tier,
            "cost": question.item.cost,
            "description": question.item.description,
        },
        "score": game.score,
        "streak": game.streak,
        "answered": len(game.records),
        "total": len(game.questions),
    }
    if game.index >= len(game.questions):
        game.finished = True
        feedback["done"] = True
        feedback["summary"] = summary(game)
    else:
        feedback["done"] = False
        feedback["next"] = question_payload(game)
    return feedback


def use_hint(game: Game) -> str:
    question = game.current
    if question is None:
        return ""
    game.hints_used.add(game.index)
    return question.hint


def question_payload(game: Game) -> dict[str, Any] | None:
    question = game.current
    if question is None:
        return None
    # the browser preloads the art of the next item, so the swap is instant
    preload = None
    following = game.questions[game.index + 1] if game.index + 1 < len(game.questions) else None
    if following is not None:
        preload = following.item.image
    return {
        "index": game.index,
        "total": len(game.questions),
        "kind": question.kind,
        "prompt": question.prompt,
        "options": question.options,
        "item": {
            "name": question.item.name,
            "image": question.item.image,
            "slot": question.item.slot,
            "slot_label": question.item.slot_label,
            "tier": question.item.tier,
            "cost": question.item.cost,
        },
        "preload": preload,
        "time_limit": TIME_LIMIT,
        "score": game.score,
        "streak": game.streak,
        "best_streak": game.best_streak,
        "mode": game.settings.get("mode", "buttons"),
    }


def summary(game: Game) -> dict[str, Any]:
    total = len(game.records)
    accuracy = (game.correct / total * 100) if total else 0.0
    return {
        "score": game.score,
        "correct": game.correct,
        "total": total,
        "accuracy": round(accuracy, 1),
        "best_streak": game.best_streak,
        "duration": round(time.time() - game.started_at, 1),
        "mistakes": [
            {
                "item_name": r.item_name,
                "image": r.image,
                "slot": r.slot,
                "slot_label": r.slot_label,
                "tier": r.tier,
                "prompt": r.prompt,
                "given": r.given,
                "correct_text": r.correct_text,
            }
            for r in game.records
            if not r.is_correct
        ],
    }
