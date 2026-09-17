import unittest

from yys_helper.demo import create_demo_state


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


if __name__ == "__main__":
    unittest.main()
