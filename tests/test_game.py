"""Game loop: answer validation, scoring and the round summary."""

from __future__ import annotations

import random

import pytest

from app import game


@pytest.fixture()
def session(seeded_db):
    return game.new_game({"slot": "all", "mode": "buttons", "length": 5}, random.Random(4))


def test_new_game_creates_questions(session):
    assert len(session.questions) == 5
    assert session.token
    assert session.current is not None


def test_check_answer_buttons(session):
    question = session.current
    ok, _ = game.check_answer(question, question.correct, "buttons")
    assert ok
    wrong_index = (question.correct + 1) % len(question.options)
    not_ok, given = game.check_answer(question, wrong_index, "buttons")
    assert not not_ok
    assert given == question.options[wrong_index]


def test_check_answer_number_allows_small_deviation(session):
    question = session.current
    ok, _ = game.check_answer(question, f"{question.answer_value + 0.1:.1f}", "number")
    assert ok
    not_ok, _ = game.check_answer(question, "999999", "number")
    assert not not_ok


def test_check_answer_handles_garbage(session):
    question = session.current
    assert game.check_answer(question, "abc", "number")[0] is False
    assert game.check_answer(question, 999, "buttons")[0] is False


def test_timeout_counts_as_a_mistake(session):
    question = session.current
    ok, given = game.check_answer(question, -1, "buttons")
    assert not ok
    assert given == "время вышло"


def test_scoring_rewards_speed_and_streak():
    fast = game.score_for(True, elapsed=0.0, streak_before=0, hint_used=False)
    slow = game.score_for(True, elapsed=game.TIME_LIMIT, streak_before=0, hint_used=False)
    assert fast > slow
    streak = game.score_for(True, elapsed=5.0, streak_before=3, hint_used=False)
    plain = game.score_for(True, elapsed=5.0, streak_before=0, hint_used=False)
    assert streak > plain
    assert game.score_for(False, elapsed=0.0, streak_before=5, hint_used=False) == 0
    with_hint = game.score_for(True, elapsed=5.0, streak_before=0, hint_used=True)
    without = game.score_for(True, elapsed=5.0, streak_before=0, hint_used=False)
    assert with_hint == without - game.HINT_PENALTY


def test_full_round_summary(session):
    for _ in range(len(session.questions)):
        question = session.current
        feedback = game.answer(session, question.correct, "buttons", elapsed=1.0)
    assert feedback["done"] is True
    summary = feedback["summary"]
    assert summary["correct"] == 5
    assert summary["total"] == 5
    assert summary["accuracy"] == 100.0
    assert summary["best_streak"] == 5
    assert summary["score"] > 0
    assert summary["mistakes"] == []


def test_wrong_answers_are_collected(session):
    question = session.current
    wrong_index = (question.correct + 1) % len(question.options)
    game.answer(session, wrong_index, "buttons", elapsed=1.0)
    summary = game.summary(session)
    assert summary["correct"] == 0
    assert len(summary["mistakes"]) == 1
    mistake = summary["mistakes"][0]
    assert mistake["item_name"] == question.item.name
    assert mistake["correct_text"] == question.answer_text


def test_hint_is_marked_and_penalises(session):
    hint = game.use_hint(session)
    assert hint
    assert session.hints_used == {0}
    feedback = game.answer(session, session.current.correct, "buttons", elapsed=1.0)
    plain = game.score_for(True, 1.0, 0, False)
    assert feedback["points"] == plain - game.HINT_PENALTY


def test_session_is_found_by_token(session):
    assert game.get_game(session.token) is session
    assert game.get_game("nope") is None
    assert game.get_game(None) is None


def test_feedback_reports_the_chosen_option(session):
    """The client needs the index of the pressed button, not its text."""
    question = session.current
    wrong_index = (question.correct + 1) % len(question.options)
    feedback = game.answer(session, wrong_index, "buttons", elapsed=1.0)
    assert feedback["given_index"] == wrong_index
    assert feedback["correct_index"] == question.correct
    assert feedback["correct"] is False

    feedback = game.answer(session, session.current.correct, "buttons", elapsed=1.0)
    assert feedback["given_index"] == feedback["correct_index"]


def test_number_answers_have_no_index(session):
    feedback = game.answer(session, "12345", "number", elapsed=1.0)
    assert feedback["given_index"] is None


def test_next_item_art_is_preloaded(session):
    payload = game.question_payload(session)
    assert payload["preload"] == session.questions[1].item.image
    assert "correct" not in payload  # the answer never leaves the server


def test_timeout_has_no_index(session):
    feedback = game.answer(session, -1, "buttons", elapsed=30.0)
    assert feedback["given_index"] is None
    assert feedback["given"] == "время вышло"
