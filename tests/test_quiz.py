"""Question engine: structure, correctness of the numbers, distractors."""

from __future__ import annotations

import random

import pytest

from app import quiz


@pytest.fixture()
def items(seeded_db):
    return quiz.load_items("all")


def test_load_items_reads_stats_and_upgrades(items):
    titanic = next(i for i in items if i.name == "Titanic Magazine")
    assert titanic.cost == 1600
    assert titanic.tier == 2
    assert titanic.slot == "weapon"
    damage = titanic.stat_by_prop("BaseAttackDamagePercent")
    assert damage["value"] == 14.0
    assert damage["label"] == "Weapon Damage"
    assert titanic.upgrade["next_tier"] == 3
    assert titanic.upgrade["bonuses"]["BaseAttackDamagePercent"] == 18.0


def test_questions_have_four_unique_options(items):
    questions = quiz.build_questions(items, random.Random(1), count=40)
    assert questions
    for question in questions:
        assert len(question.options) == 4
        assert len(set(question.options)) == 4
        assert question.answer_text in question.options
        assert 0 <= question.correct < 4
        assert question.options[question.correct] == question.answer_text


def test_titanic_magazine_questions(items):
    titanic = next(i for i in items if i.name == "Titanic Magazine")
    questions = quiz.build_questions([titanic], random.Random(3), count=30)
    by_id = {q.id: q for q in questions}

    damage = by_id["stat:upgrade_titan_round:BaseAttackDamagePercent:14.0"]
    assert damage.answer_value == 14.0
    assert damage.answer_text == "14 %"
    assert "Titanic Magazine" in damage.prompt

    # the upgrade adds the tier bonus on top of the base value
    upgraded = by_id["upgrade:upgrade_titan_round:BaseAttackDamagePercent:32.0"]
    assert upgraded.answer_value == 32.0
    assert upgraded.answer_text == "32 %"

    price = by_id["price:upgrade_titan_round:price:1600.0"]
    assert price.answer_value == 1600.0
    assert price.answer_text == "1\u2009600 душ"

    tier = by_id["tier:upgrade_titan_round:tier:2.0"]
    assert tier.answer_value == 2.0
    assert tier.answer_text == "2 тир"


def test_upgrade_questions_are_skipped_without_a_next_tier(seeded_db):
    """There is no tier 6 - such items must not get an upgrade question."""
    import json

    conn = seeded_db.connect()
    conn.execute(
        "UPDATE items SET upgrade = ? WHERE class_name = 'upgrade_titan_round'",
        (json.dumps({"next_tier": None, "bonuses": {"BaseAttackDamagePercent": 18.0}}),),
    )
    conn.commit()
    conn.close()
    try:
        items = quiz.load_items("all")
        questions = quiz.build_questions(items, random.Random(5), count=40)
        assert not [q for q in questions if q.kind == "upgrade"]
    finally:
        conn = seeded_db.connect()
        conn.execute(
            "UPDATE items SET upgrade = ? WHERE class_name = 'upgrade_titan_round'",
            (
                json.dumps(
                    {
                        "next_tier": 3,
                        "bonuses": {"BaseAttackDamagePercent": 18.0, "BonusClipSizePercent": 70.0},
                    }
                ),
            ),
        )
        conn.commit()
        conn.close()


def test_slot_filter(items):
    weapons = quiz.load_items("weapon")
    assert weapons
    assert all(i.slot == "weapon" for i in weapons)


def test_distractors_never_equal_the_answer(items):
    questions = quiz.build_questions(items, random.Random(11), count=60)
    for question in questions:
        others = [text for i, text in enumerate(question.options) if i != question.correct]
        assert question.answer_text not in others


def test_formatting():
    assert quiz.fmt_number(14.0) == "14"
    assert quiz.fmt_number(1.5) == "1.5"
    assert quiz.fmt_value(14.0, "%") == "14 %"
    assert quiz.fmt_value(35.0, "s") == "35 с"
    assert quiz.fmt_value(1600, "") == "1600"
    assert quiz.fmt_cost(9999) == "9\u2009999 душ"


def test_question_kinds_are_mixed(items):
    questions = quiz.build_questions(items, random.Random(2), count=200)
    kinds = {q.kind for q in questions}
    assert {"stat", "upgrade", "price", "tier"} <= kinds
