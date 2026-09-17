from __future__ import annotations

from dataclasses import dataclass

from collections.abc import Iterable

from .domain.models import BuildRequirement, BuildResult, Soul, Stat, UpgradeCandidate, UpgradeBudget
from .domain.optimizer import optimize_build
from .domain.upgrade import rank_upgrade_candidates


@dataclass(frozen=True, slots=True)
class DemoState:
    inventory: tuple[Soul, ...]
    requirement: BuildRequirement
    closest_build: BuildResult
    upgrade_candidates: tuple[UpgradeCandidate, ...]


def _demo_soul(
    identifier: str,
    set_name: str,
    slot: int,
    speed: float,
    crit: float,
    *,
    level: int,
) -> Soul:
    return Soul(
        id=identifier,
        set_name=set_name,
        slot=slot,
        rarity=6,
        level=level,
        main_stat=Stat.SPEED if slot == 2 and identifier.endswith("a") else Stat.ATTACK_PCT,
        main_value=57 if slot == 2 and identifier.endswith("a") else 55,
        substats={Stat.SPEED: speed, Stat.CRIT_RATE: crit, Stat.CRIT_DAMAGE: crit * 1.5},
    )


def create_demo_state() -> DemoState:
    souls: list[Soul] = []
    for slot in range(1, 7):
        souls.append(_demo_soul(f"fortune-{slot}-a", "招财猫", slot, 4 + slot, 2 + slot, level=0))
        souls.append(_demo_soul(f"broken-{slot}-b", "散件", slot, 2 + slot, 6 + slot, level=12))
    requirement = BuildRequirement(
        set_counts={"招财猫": 4},
        min_stats={Stat.SPEED: 115, Stat.CRIT_RATE: 55},
        weights={Stat.SPEED: 1.5, Stat.CRIT_RATE: 2.0, Stat.CRIT_DAMAGE: 0.8},
    )
    return create_state(souls, requirement)


def create_state(
    inventory: Iterable[Soul], requirement: BuildRequirement
) -> DemoState:
    items = tuple(inventory)
    build = optimize_build(items, requirement)
    upgrades = tuple(
        rank_upgrade_candidates(
            items,
            requirement,
            UpgradeBudget(
                max_coins=800_000,
                max_materials=40,
                max_souls=5,
                max_level=15,
                min_expected_gain=0.1,
            ),
        )
    )
    return DemoState(items, requirement, build, upgrades)
