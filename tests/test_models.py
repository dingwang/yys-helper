import unittest

from yys_helper.domain.models import (
    BuildRequirement,
    Soul,
    Stat,
    UpgradeBudget,
)


class ModelTests(unittest.TestCase):
    def test_soul_rejects_slot_outside_one_to_six(self):
        with self.assertRaisesRegex(ValueError, "slot"):
            Soul(
                id="x",
                set_name="招财猫",
                slot=7,
                rarity=6,
                level=0,
                main_stat=Stat.SPEED,
                main_value=57,
                substats={},
            )

    def test_soul_rejects_invalid_confidence(self):
        with self.assertRaisesRegex(ValueError, "confidence"):
            Soul(
                id="x",
                set_name="招财猫",
                slot=2,
                rarity=6,
                level=0,
                main_stat=Stat.SPEED,
                main_value=57,
                substats={},
                confidence=1.1,
            )

    def test_upgrade_budget_rejects_negative_limits(self):
        with self.assertRaisesRegex(ValueError, "non-negative"):
            UpgradeBudget(max_coins=-1, max_materials=0, max_souls=1, max_level=15)

    def test_requirement_normalizes_set_counts_and_rejects_sums_over_six(self):
        with self.assertRaisesRegex(ValueError, "six"):
            BuildRequirement(set_counts={"招财猫": 4, "火灵": 4})


if __name__ == "__main__":
    unittest.main()
