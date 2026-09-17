from __future__ import annotations

from collections.abc import Collection

from .models import Soul, Stat


USEFUL_STATS = frozenset(
    {
        Stat.SPEED,
        Stat.CRIT_RATE,
        Stat.CRIT_DAMAGE,
        Stat.ATTACK_PCT,
        Stat.HP_PCT,
        Stat.DEFENSE_PCT,
        Stat.EFFECT_HIT,
        Stat.EFFECT_RESIST,
    }
)


def protection_reasons(
    soul: Soul,
    referenced_soul_ids: Collection[str],
    *,
    confidence_threshold: float = 0.92,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if soul.equipped_to:
        reasons.append("equipped")
    if soul.locked:
        reasons.append("locked")
    if soul.confidence < confidence_threshold:
        reasons.append("low_confidence")
    if soul.id in referenced_soul_ids:
        reasons.append("referenced")
    if soul.rarity == 6 and Stat.SPEED in soul.substats:
        reasons.append("six_star_speed")
    useful_count = len(USEFUL_STATS.intersection(soul.substats))
    if soul.rarity == 6 and useful_count >= 3:
        reasons.append("three_useful_substats")
    return tuple(reasons)


def may_be_consumed(soul: Soul, referenced_soul_ids: Collection[str]) -> bool:
    return not protection_reasons(soul, referenced_soul_ids)
