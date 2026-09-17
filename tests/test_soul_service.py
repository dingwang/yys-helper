import unittest
from dataclasses import replace

from yys_helper.application.souls import SoulService
from yys_helper.domain.models import BuildRequirement, Soul, Stat, UpgradeBudget


def make_soul(identifier, slot, speed=0, *, level=0, locked=False, equipped_to=None):
    return Soul(
        id=identifier,
        set_name="招财猫",
        slot=slot,
        rarity=6,
        level=level,
        main_stat=Stat.ATTACK_PCT,
        main_value=10,
        substats={Stat.SPEED: speed} if speed else {Stat.HP_PCT: 2},
        locked=locked,
        equipped_to=equipped_to,
    )


def inventory(speed_one=3, level_one=0):
    return [make_soul("candidate", 1, speed_one, level=level_one)] + [
        make_soul(f"slot-{slot}", slot, 1, level=15) for slot in range(2, 7)
    ]


class ScriptedScanner:
    def __init__(self, snapshots):
        self.snapshots = iter(snapshots)

    def scan(self):
        return next(self.snapshots)


class RecordingSoulActor:
    def __init__(self):
        self.requested_levels = []
        self.locked = []
        self.discarded = []

    def upgrade(self, soul_id, target_level):
        self.requested_levels.append(target_level)
        return True

    def lock(self, soul_id):
        self.locked.append(soul_id)
        return True

    def mark_discard(self, soul_id):
        self.discarded.append(soul_id)
        return True


class MemoryRepository:
    def __init__(self):
        self.saved = []

    def save_souls(self, souls):
        self.saved.append(list(souls))


class SoulServiceTests(unittest.TestCase):
    def test_rescans_at_plus_three_and_stops_after_bad_roll(self):
        actor = RecordingSoulActor()
        service = SoulService(
            ScriptedScanner([inventory(), inventory(speed_one=3, level_one=3)]),
            actor,
            MemoryRepository(),
        )
        outcome = service.upgrade_and_replan(
            BuildRequirement(min_stats={Stat.SPEED: 50}, weights={Stat.SPEED: 2}),
            UpgradeBudget(500_000, 20, 3, 15),
        )
        self.assertEqual([3], actor.requested_levels)
        self.assertEqual("potential_lost", outcome.stop_reason)

    def test_marking_locks_protected_and_discards_only_low_score_unprotected(self):
        protected = replace(make_soul("equipped", 1), equipped_to="鬼使黑")
        weak = Soul(
            id="weak",
            set_name="涅槃之火",
            slot=2,
            rarity=5,
            level=0,
            main_stat=Stat.DEFENSE,
            main_value=20,
            substats={Stat.DEFENSE: 2},
        )
        actor = RecordingSoulActor()
        service = SoulService(
            ScriptedScanner([[protected, weak]]), actor, MemoryRepository()
        )
        result = service.scan_and_mark("output", discard_below=10)
        self.assertEqual(["equipped"], actor.locked)
        self.assertEqual(["weak"], actor.discarded)
        self.assertEqual(1, result.protected)


if __name__ == "__main__":
    unittest.main()
