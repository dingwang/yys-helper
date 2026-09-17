from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class Stat(str, Enum):
    ATTACK = "attack"
    HP = "hp"
    DEFENSE = "defense"
    SPEED = "speed"
    CRIT_RATE = "crit_rate"
    CRIT_DAMAGE = "crit_damage"
    ATTACK_PCT = "attack_pct"
    HP_PCT = "hp_pct"
    DEFENSE_PCT = "defense_pct"
    EFFECT_HIT = "effect_hit"
    EFFECT_RESIST = "effect_resist"


class StopReason(str, Enum):
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    UNRECOGNIZED_SCENE = "unrecognized_scene"
    INSUFFICIENT_STAMINA = "insufficient_stamina"
    MAX_ROUNDS = "max_rounds"
    MAX_DURATION = "max_duration"
    ADB_DISCONNECTED = "adb_disconnected"
    NETWORK_ERROR = "network_error"
    INVENTORY_FULL = "inventory_full"
    ACTION_FAILED = "action_failed"


@dataclass(frozen=True, slots=True)
class Soul:
    id: str
    set_name: str
    slot: int
    rarity: int
    level: int
    main_stat: Stat
    main_value: float
    substats: Mapping[Stat, float]
    locked: bool = False
    equipped_to: str | None = None
    marked_discard: bool = False
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("id must not be empty")
        if not 1 <= self.slot <= 6:
            raise ValueError("slot must be between 1 and 6")
        if not 1 <= self.rarity <= 6:
            raise ValueError("rarity must be between 1 and 6")
        if not 0 <= self.level <= 15:
            raise ValueError("level must be between 0 and 15")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

    def stat_value(self, stat: Stat) -> float:
        return float(self.substats.get(stat, 0.0)) + (
            float(self.main_value) if self.main_stat == stat else 0.0
        )


@dataclass(frozen=True, slots=True)
class BuildRequirement:
    set_counts: Mapping[str, int] = field(default_factory=dict)
    main_stats: Mapping[int, frozenset[Stat]] = field(default_factory=dict)
    min_stats: Mapping[Stat, float] = field(default_factory=dict)
    max_stats: Mapping[Stat, float] = field(default_factory=dict)
    weights: Mapping[Stat, float] = field(default_factory=dict)
    referenced_soul_ids: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if sum(self.set_counts.values()) > 6:
            raise ValueError("set requirements cannot use more than six souls")
        if any(count <= 0 or count > 6 for count in self.set_counts.values()):
            raise ValueError("set counts must be between 1 and 6")
        if any(slot not in range(1, 7) for slot in self.main_stats):
            raise ValueError("main stat slots must be between 1 and 6")


@dataclass(frozen=True, slots=True)
class BuildResult:
    souls: tuple[Soul, ...]
    totals: Mapping[Stat, float]
    score: float
    satisfied: bool
    shortfalls: Mapping[Stat, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class UpgradeBudget:
    max_coins: int
    max_materials: int
    max_souls: int
    max_level: int
    min_expected_gain: float = 0.0

    def __post_init__(self) -> None:
        numeric = (self.max_coins, self.max_materials, self.max_souls, self.max_level)
        if any(value < 0 for value in numeric):
            raise ValueError("budget limits must be non-negative")
        if self.max_level > 15:
            raise ValueError("max_level cannot exceed 15")


@dataclass(frozen=True, slots=True)
class UpgradeCandidate:
    soul: Soul
    next_level: int
    expected_gain: float
    relevance: float
    estimated_coins: int
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TaskLimits:
    max_rounds: int = 50
    max_duration_seconds: float = 3600.0
    min_stamina: int = 0

    def __post_init__(self) -> None:
        if self.max_rounds <= 0 or self.max_duration_seconds <= 0:
            raise ValueError("task limits must be positive")


@dataclass(frozen=True, slots=True)
class TaskOutcome:
    reason: StopReason
    final_state: str
    rounds: int
    elapsed_seconds: float
    message: str = ""
