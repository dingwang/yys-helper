import unittest

from yys_helper.demo import create_demo_state, create_state
from yys_helper.domain.models import BuildRequirement, Stat


class DemoTests(unittest.TestCase):
    def test_demo_contains_inventory_build_and_upgrade_candidate(self):
        demo = create_demo_state()
        self.assertGreater(len(demo.inventory), 6)
        self.assertEqual(6, len(demo.closest_build.souls))
        self.assertGreater(len(demo.upgrade_candidates), 0)

    def test_demo_is_deterministic(self):
        first = create_demo_state()
        second = create_demo_state()
        self.assertEqual(first.inventory, second.inventory)
        self.assertEqual(first.closest_build, second.closest_build)

    def test_real_state_with_empty_inventory_never_falls_back_to_demo(self):
        requirement = BuildRequirement(
            min_stats={Stat.SPEED: 128}, weights={Stat.SPEED: 1.0}
        )

        state = create_state([], requirement)

        self.assertEqual((), state.inventory)
        self.assertEqual((), state.closest_build.souls)
        self.assertEqual((), state.upgrade_candidates)


if __name__ == "__main__":
    unittest.main()
