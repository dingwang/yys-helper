import unittest
from dataclasses import replace

from yys_helper.domain.models import Soul, Stat
from yys_helper.domain.safety import protection_reasons
from yys_helper.domain.scoring import DEFAULT_PROFILES, score_soul


def make_soul(identifier: str, substats, **changes) -> Soul:
    base = Soul(
        id=identifier,
        set_name="招财猫",
        slot=1,
        rarity=6,
        level=0,
        main_stat=Stat.ATTACK,
        main_value=100,
        substats=substats,
    )
    return replace(base, **changes)


class ScoringAndSafetyTests(unittest.TestCase):
    def test_speed_profile_values_speed_above_unrelated_health(self):
        fast = make_soul("fast", {Stat.SPEED: 12})
        tank = make_soul("tank", {Stat.HP_PCT: 18})
        self.assertGreater(
            score_soul(fast, DEFAULT_PROFILES["speed"]),
            score_soul(tank, DEFAULT_PROFILES["speed"]),
        )

    def test_equipped_soul_is_always_protected(self):
        item = make_soul("used", {}, equipped_to="鬼使黑")
        self.assertIn("equipped", protection_reasons(item, set()))

    def test_low_confidence_soul_is_protected(self):
        item = make_soul("unclear", {}, confidence=0.91)
        self.assertIn("low_confidence", protection_reasons(item, set()))

    def test_six_star_speed_embryo_is_protected(self):
        item = make_soul("speed", {Stat.SPEED: 3})
        self.assertIn("six_star_speed", protection_reasons(item, set()))

    def test_referenced_soul_is_protected(self):
        item = make_soul("saved", {})
        self.assertIn("referenced", protection_reasons(item, {"saved"}))


if __name__ == "__main__":
    unittest.main()
