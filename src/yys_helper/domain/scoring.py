from __future__ import annotations

from typing import Mapping

from .models import Soul, Stat


DEFAULT_PROFILES: dict[str, dict[Stat, float]] = {
    "output": {
        Stat.CRIT_RATE: 2.0,
        Stat.CRIT_DAMAGE: 1.4,
        Stat.ATTACK_PCT: 1.0,
        Stat.SPEED: 0.6,
    },
    "control": {
        Stat.EFFECT_HIT: 1.6,
        Stat.SPEED: 1.4,
        Stat.HP_PCT: 0.7,
        Stat.DEFENSE_PCT: 0.5,
    },
    "support": {
        Stat.SPEED: 1.5,
        Stat.HP_PCT: 1.0,
        Stat.EFFECT_RESIST: 0.9,
        Stat.DEFENSE_PCT: 0.6,
    },
    "speed": {
        Stat.SPEED: 3.0,
        Stat.HP_PCT: 0.15,
        Stat.EFFECT_RESIST: 0.15,
        Stat.EFFECT_HIT: 0.15,
    },
}


def score_soul(soul: Soul, weights: Mapping[Stat, float]) -> float:
    """Return a transparent weighted score from the visible soul stats."""
    return round(sum(soul.stat_value(stat) * weight for stat, weight in weights.items()), 4)


def aggregate_stats(souls: tuple[Soul, ...] | list[Soul]) -> dict[Stat, float]:
    totals: dict[Stat, float] = {}
    for soul in souls:
        for stat, value in soul.substats.items():
            totals[stat] = totals.get(stat, 0.0) + float(value)
        totals[soul.main_stat] = totals.get(soul.main_stat, 0.0) + float(soul.main_value)
    return totals
