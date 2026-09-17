from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from .models import BuildRequirement, BuildResult, Soul, Stat
from .scoring import aggregate_stats, score_soul


@dataclass(slots=True)
class _Partial:
    souls: tuple[Soul, ...]
    set_counts: Counter[str]
    totals: dict[Stat, float]
    score: float


def _eligible(soul: Soul, requirement: BuildRequirement) -> bool:
    allowed = requirement.main_stats.get(soul.slot)
    return allowed is None or soul.main_stat in allowed


def _progress(partial: _Partial, requirement: BuildRequirement) -> float:
    progress = 0.0
    for stat, minimum in requirement.min_stats.items():
        if minimum > 0:
            progress += min(partial.totals.get(stat, 0.0) / minimum, 1.0) * 100.0
    for set_name, needed in requirement.set_counts.items():
        progress += min(partial.set_counts.get(set_name, 0) / needed, 1.0) * 100.0
    return progress + partial.score


def _requirement_gap(
    souls: tuple[Soul, ...], totals: dict[Stat, float], requirement: BuildRequirement
) -> tuple[dict[Stat, float], float]:
    shortfalls = {
        stat: round(max(0.0, minimum - totals.get(stat, 0.0)), 4)
        for stat, minimum in requirement.min_stats.items()
        if totals.get(stat, 0.0) < minimum
    }
    penalty = sum(
        gap / max(abs(requirement.min_stats[stat]), 1.0)
        for stat, gap in shortfalls.items()
    )
    counts = Counter(soul.set_name for soul in souls)
    for set_name, needed in requirement.set_counts.items():
        penalty += max(0, needed - counts.get(set_name, 0)) / needed
    for stat, maximum in requirement.max_stats.items():
        excess = max(0.0, totals.get(stat, 0.0) - maximum)
        penalty += excess / max(abs(maximum), 1.0)
    return shortfalls, penalty


def optimize_build(
    souls: Iterable[Soul],
    requirement: BuildRequirement,
    *,
    per_slot_limit: int = 20,
    beam_width: int = 5000,
) -> BuildResult:
    by_slot: dict[int, list[Soul]] = {slot: [] for slot in range(1, 7)}
    for soul in souls:
        if _eligible(soul, requirement):
            by_slot[soul.slot].append(soul)
    if any(not by_slot[slot] for slot in range(1, 7)):
        return BuildResult((), {}, 0.0, False, dict(requirement.min_stats))

    for slot in by_slot:
        by_slot[slot].sort(
            key=lambda soul: score_soul(soul, requirement.weights), reverse=True
        )
        by_slot[slot] = by_slot[slot][:per_slot_limit]

    partials = [_Partial((), Counter(), {}, 0.0)]
    for slot in range(1, 7):
        expanded: list[_Partial] = []
        for partial in partials:
            for soul in by_slot[slot]:
                totals = dict(partial.totals)
                for stat, value in soul.substats.items():
                    totals[stat] = totals.get(stat, 0.0) + float(value)
                totals[soul.main_stat] = totals.get(soul.main_stat, 0.0) + float(
                    soul.main_value
                )
                counts = partial.set_counts.copy()
                counts[soul.set_name] += 1
                expanded.append(
                    _Partial(
                        partial.souls + (soul,),
                        counts,
                        totals,
                        partial.score + score_soul(soul, requirement.weights),
                    )
                )
        expanded.sort(key=lambda p: _progress(p, requirement), reverse=True)
        partials = expanded[:beam_width]

    ranked = []
    for partial in partials:
        totals = aggregate_stats(partial.souls)
        shortfalls, penalty = _requirement_gap(partial.souls, totals, requirement)
        ranked.append((penalty, -partial.score, partial, totals, shortfalls))
    ranked.sort(key=lambda row: (row[0], row[1]))
    penalty, _, best, totals, shortfalls = ranked[0]
    return BuildResult(
        souls=best.souls,
        totals=totals,
        score=round(best.score, 4),
        satisfied=penalty == 0.0,
        shortfalls=shortfalls,
    )
