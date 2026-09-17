import unittest

from yys_helper.domain.models import BuildRequirement, Soul, Stat, UpgradeBudget
from yys_helper.domain.upgrade import rank_upgrade_candidates


def soul(identifier, slot, substats, *, level=0, locked=False):
    return Soul(
        id=identifier,
        set_name="招财猫",
        slot=slot,
        rarity=6,
        level=level,
        main_stat=Stat.ATTACK_PCT,
        main_value=10,
        substats=substats,
        locked=locked,
    )


class UpgradePlannerTests(unittest.TestCase):
    def test_prefers_relevant_low_level_embryo_and_stages_at_plus_three(self):
        inventory = [
            soul("hp-embryo", 1, {Stat.HP_PCT: 3}),
            soul("speed-embryo", 1, {Stat.SPEED: 3, Stat.CRIT_RATE: 2}),
        ]
        requirement = BuildRequirement(
            min_stats={Stat.SPEED: 50}, weights={Stat.SPEED: 2, Stat.CRIT_RATE: 1}
        )
        budget = UpgradeBudget(500_000, 20, 3, 15)
        candidates = rank_upgrade_candidates(inventory, requirement, budget)
        self.assertEqual("speed-embryo", candidates[0].soul.id)
        self.assertEqual(3, candidates[0].next_level)

    def test_excludes_locked_and_max_level_souls(self):
        inventory = [
            soul("locked", 1, {Stat.SPEED: 3}, locked=True),
            soul("maxed", 2, {Stat.SPEED: 15}, level=15),
        ]
        candidates = rank_upgrade_candidates(
            inventory,
            BuildRequirement(weights={Stat.SPEED: 1}),
            UpgradeBudget(500_000, 20, 3, 15),
        )
        self.assertEqual([], candidates)


if __name__ == "__main__":
    unittest.main()
