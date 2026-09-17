import unittest

from yys_helper.domain.models import BuildRequirement, Soul, Stat
from yys_helper.domain.optimizer import optimize_build


def item(identifier, slot, set_name, speed, score_stat=0):
    return Soul(
        id=identifier,
        set_name=set_name,
        slot=slot,
        rarity=6,
        level=15,
        main_stat=Stat.ATTACK_PCT,
        main_value=55,
        substats={Stat.SPEED: speed, Stat.CRIT_RATE: score_stat},
    )


def inventory_fixture():
    result = []
    for slot in range(1, 7):
        result.append(item(f"fortune-{slot}", slot, "招财猫", 6, 2))
        result.append(item(f"broken-{slot}", slot, "散件", 2, 12))
    return result


class OptimizerTests(unittest.TestCase):
    def test_optimizer_meets_slots_set_count_and_minimum_speed(self):
        requirement = BuildRequirement(
            set_counts={"招财猫": 4},
            min_stats={Stat.SPEED: 30},
            weights={Stat.CRIT_RATE: 1, Stat.SPEED: 0.1},
        )
        result = optimize_build(inventory_fixture(), requirement)
        self.assertTrue(result.satisfied)
        self.assertEqual({1, 2, 3, 4, 5, 6}, {s.slot for s in result.souls})
        self.assertGreaterEqual(
            sum(1 for soul in result.souls if soul.set_name == "招财猫"), 4
        )
        self.assertGreaterEqual(result.totals[Stat.SPEED], 30)

    def test_optimizer_returns_smallest_gap_when_strict_solution_missing(self):
        requirement = BuildRequirement(
            min_stats={Stat.SPEED: 300}, weights={Stat.SPEED: 1}
        )
        result = optimize_build(inventory_fixture(), requirement)
        self.assertFalse(result.satisfied)
        self.assertEqual(6, len(result.souls))
        self.assertGreater(result.shortfalls[Stat.SPEED], 0)

    def test_optimizer_honors_required_main_stat(self):
        souls = inventory_fixture()
        souls.append(
            Soul(
                id="speed-main",
                set_name="散件",
                slot=2,
                rarity=6,
                level=15,
                main_stat=Stat.SPEED,
                main_value=57,
                substats={},
            )
        )
        requirement = BuildRequirement(main_stats={2: frozenset({Stat.SPEED})})
        result = optimize_build(souls, requirement)
        self.assertEqual(Stat.SPEED, next(s for s in result.souls if s.slot == 2).main_stat)


if __name__ == "__main__":
    unittest.main()
