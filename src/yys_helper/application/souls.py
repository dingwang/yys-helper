from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from yys_helper.domain.models import (
    BuildRequirement,
    BuildResult,
    Soul,
    UpgradeBudget,
)
from yys_helper.domain.optimizer import optimize_build
from yys_helper.domain.safety import protection_reasons
from yys_helper.domain.scoring import DEFAULT_PROFILES, score_soul
from yys_helper.domain.upgrade import rank_upgrade_candidates


class SoulScanner(Protocol):
    def scan(self) -> Sequence[Soul]: ...


class SoulActor(Protocol):
    def upgrade(self, soul_id: str, target_level: int) -> bool: ...

    def lock(self, soul_id: str) -> bool: ...

    def mark_discard(self, soul_id: str) -> bool: ...


class SoulRepository(Protocol):
    def save_souls(self, souls: Sequence[Soul]) -> None: ...


@dataclass(frozen=True, slots=True)
class UpgradeOutcome:
    build: BuildResult
    requested_levels: tuple[int, ...]
    stop_reason: str


@dataclass(frozen=True, slots=True)
class MarkOutcome:
    scanned: int
    protected: int
    discarded: int
    failed: int


def _shortfall_penalty(build: BuildResult, requirement: BuildRequirement) -> float:
    return sum(
        abs(gap)
        / max(
            abs(
                requirement.min_stats.get(
                    stat, requirement.max_stats.get(stat, 0.0)
                )
            ),
            1.0,
        )
        for stat, gap in build.shortfalls.items()
    )


class SoulService:
    def __init__(
        self, scanner: SoulScanner, actor: SoulActor, repository: SoulRepository
    ) -> None:
        self.scanner = scanner
        self.actor = actor
        self.repository = repository

    def scan_inventory(self) -> list[Soul]:
        inventory = list(self.scanner.scan())
        self.repository.save_souls(inventory)
        return inventory

    def plan(self, requirement: BuildRequirement) -> BuildResult:
        return optimize_build(self.scan_inventory(), requirement)

    def scan_and_mark(self, profile: str, *, discard_below: float) -> MarkOutcome:
        if profile not in DEFAULT_PROFILES:
            raise ValueError(f"unknown scoring profile: {profile}")
        inventory = self.scan_inventory()
        protected = discarded = failed = 0
        weights = DEFAULT_PROFILES[profile]
        for soul in inventory:
            reasons = protection_reasons(soul, set())
            if reasons:
                protected += 1
                if not soul.locked and not self.actor.lock(soul.id):
                    failed += 1
            elif score_soul(soul, weights) < discard_below:
                if self.actor.mark_discard(soul.id):
                    discarded += 1
                else:
                    failed += 1
        return MarkOutcome(len(inventory), protected, discarded, failed)

    def upgrade_and_replan(
        self, requirement: BuildRequirement, budget: UpgradeBudget
    ) -> UpgradeOutcome:
        inventory = self.scan_inventory()
        build = optimize_build(inventory, requirement)
        requested: list[int] = []
        if build.satisfied:
            return UpgradeOutcome(build, (), "satisfied")

        for _ in range(budget.max_souls):
            candidates = rank_upgrade_candidates(inventory, requirement, budget)
            if not candidates:
                return UpgradeOutcome(build, tuple(requested), "no_candidate")
            candidate = candidates[0]
            if not self.actor.upgrade(candidate.soul.id, candidate.next_level):
                return UpgradeOutcome(build, tuple(requested), "upgrade_failed")
            requested.append(candidate.next_level)
            updated = self.scan_inventory()
            new_build = optimize_build(updated, requirement)
            improved = (
                _shortfall_penalty(new_build, requirement)
                < _shortfall_penalty(build, requirement)
                or new_build.score > build.score
            )
            if new_build.satisfied:
                return UpgradeOutcome(new_build, tuple(requested), "satisfied")
            if not improved:
                return UpgradeOutcome(new_build, tuple(requested), "potential_lost")
            inventory, build = updated, new_build
        return UpgradeOutcome(build, tuple(requested), "budget_exhausted")
