"""Normalisation of the API payload into the quiz database."""

from __future__ import annotations

import json

from app import ingest

SAMPLE_ITEM = {
    "id": 2356412290,
    "type": "upgrade",
    "class_name": "upgrade_titan_round",
    "name": "Titanic Magazine",
    "item_slot_type": "weapon",
    "item_tier": 2,
    "cost": 1600,
    "shopable": True,
    "is_active_item": False,
    "description": {"desc": "Increases <span class=\"highlight\">Weapon Damage</span>."},
    "shop_image_webp": "https://assets-bucket.deadlock-api.com/assets-api-res/images/items/weapon/titanic_magazine.webp",
    "properties": {
        "AbilityCooldown": {"value": "0", "label": "Cooldown", "postfix": "s"},
        "BaseAttackDamagePercent": {
            "value": "14",
            "label": "Weapon Damage",
            "postfix": "%",
            "prefix": "{s:sign}",
        },
        "BonusClipSizePercent": {"value": "100", "label": "Max Ammo", "postfix": "%"},
    },
    "tooltip_sections": [
        {
            "section_type": "innate",
            "section_attributes": [
                {
                    "properties": ["BaseAttackDamagePercent"],
                    "elevated_properties": ["BonusClipSizePercent"],
                }
            ],
        }
    ],
    "upgrades": [
        {
            "property_upgrades": [
                {"name": "BaseAttackDamagePercent", "bonus": "18"},
                {"name": "BonusClipSizePercent", "bonus": "70"},
            ]
        }
    ],
}


def test_only_tooltip_properties_are_kept():
    stats = ingest._tooltip_props(SAMPLE_ITEM)
    props = {stat["prop"] for stat in stats}
    # AbilityCooldown is not shown on the tooltip -> no question about it
    assert props == {"BaseAttackDamagePercent", "BonusClipSizePercent"}
    damage = next(s for s in stats if s["prop"] == "BaseAttackDamagePercent")
    assert damage["value"] == 14.0
    assert damage["unit"] == "%"
    assert damage["elevated"] is False
    ammo = next(s for s in stats if s["prop"] == "BonusClipSizePercent")
    assert ammo["elevated"] is True


def test_upgrade_is_the_next_tier_step():
    upgrade = ingest._upgrade(SAMPLE_ITEM)
    assert upgrade["next_tier"] == 3
    assert upgrade["bonuses"] == {"BaseAttackDamagePercent": 18.0, "BonusClipSizePercent": 70.0}


def test_top_tier_has_no_upgrade():
    item = dict(SAMPLE_ITEM, item_tier=5)
    assert ingest._upgrade(item)["next_tier"] is None


def test_ambiguous_labels_are_marked():
    stats = ingest._tooltip_props(
        {
            **SAMPLE_ITEM,
            "properties": {
                **SAMPLE_ITEM["properties"],
                "TechPowerPercent": {"value": "15", "label": "Spirit Power", "postfix": "%"},
                "TechPower": {"value": "30", "label": "Spirit Power", "postfix": ""},
            },
            "tooltip_sections": [
                {
                    "section_type": "innate",
                    "section_attributes": [
                        {
                            "properties": [
                                "BaseAttackDamagePercent",
                                "TechPowerPercent",
                                "TechPower",
                            ],
                            "elevated_properties": [],
                        }
                    ],
                }
            ],
        }
    )
    ingest._mark_ambiguous(stats)
    by_prop = {stat["prop"]: stat for stat in stats}
    # same label but different unit -> still fine
    assert by_prop["TechPower"].get("ambiguous") is not True
    assert by_prop["TechPowerPercent"].get("ambiguous") is not True

    # same label AND same unit with different values -> ambiguous
    stats2 = ingest._tooltip_props(
        {
            **SAMPLE_ITEM,
            "properties": {
                **SAMPLE_ITEM["properties"],
                "TechPowerPercent2": {"value": "40", "label": "Weapon Damage", "postfix": "%"},
            },
            "tooltip_sections": [
                {
                    "section_type": "innate",
                    "section_attributes": [
                        {
                            "properties": ["BaseAttackDamagePercent", "TechPowerPercent2"],
                            "elevated_properties": [],
                        }
                    ],
                }
            ],
        }
    )
    ingest._mark_ambiguous(stats2)
    assert all(stat.get("ambiguous") for stat in stats2)


def test_description_html_is_stripped():
    from app.textutil import strip_html

    assert "highlight" not in strip_html(SAMPLE_ITEM["description"]["desc"])
    assert "Weapon Damage" in strip_html(SAMPLE_ITEM["description"]["desc"])


def test_image_is_proxied():
    from app.images import proxy_path

    url = SAMPLE_ITEM["shop_image_webp"]
    assert proxy_path(url) == "/img/images/items/weapon/titanic_magazine.webp"
    assert proxy_path(None) is None
    assert json.dumps(proxy_path(url))
