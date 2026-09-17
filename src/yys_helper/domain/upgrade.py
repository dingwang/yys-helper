from __future__ import annotations

from collections.abc import Iterable

from .models import BuildRequirement, Soul, UpgradeBudget, UpgradeCandidate
from .safety import protection_reasons


def rank_upgrade_candidates(
    souls: Iterable[Soul],
    requirement: BuildRequirement,
    budget: UpgradeBudget,
) -> list[UpgradeCandidate]:
    if budget.max_souls == 0 or budget.max_materials == 0 or budget.max_coins == 0:
        return []
    candidates: list[UpgradeCandidate] = []
    for soul in souls:
        hard_reasons = set(protection_reasons(soul, requirement.referenced_soul_ids))
        if hard_reasons.intersection({"equipped", "locked", "low_confidence", "referenced"}):
            continue
        ceiling = min(15, budget.max_level)
        if soul.level >= ceiling:
            continue
        relevance = sum(
            float(value) * float(requirement.weights.get(stat, 0.0))
            for stat, value in soul.substats.items()
        )
        relevance += sum(
            2.0 * float(requirement.weights.get(stat, 0.0))
            for stat in soul.substats
            if stat in requirement.min_stats
        )
        if relevance <= 0:
            continue
        next_level = min(ceiling, ((soul.level // 3) + 1) * 3)
        step = next_level - soul.level
        expected_gain = round(relevance * (step / 3.0) * 0.25, 4)
        if expected_gain < budget.min_expected_gain:
            continue
        candidates.append(
            UpgradeCandidate(
                soul=soul,
                next_level=next_level,
                expected_gain=expected_gain,
                relevance=round(relevance, 4),
                estimated_coins=step * 2_000 * soul.rarity,
                reasons=tuple(
                    stat.value
                    for stat in soul.substats
                    if requirement.weights.get(stat, 0.0) > 0
                ),
            )
        )
    candidates.sort(
        key=lambda candidate: (
            candidate.expected_gain / max(candidate.estimated_coins, 1),
            candidate.relevance,
            -candidate.soul.level,
        ),
        reverse=True,
    )
    return candidates[: budget.max_souls]
