import unittest

from yys_helper.domain.models import Soul, Stat
from yys_helper.infrastructure.repository import AppRepository


def soul_fixture():
    return Soul(
        id="s-1",
        set_name="招财猫",
        slot=2,
        rarity=6,
        level=3,
        main_stat=Stat.SPEED,
        main_value=20,
        substats={Stat.CRIT_RATE: 3, Stat.HP_PCT: 4},
        confidence=0.99,
    )


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repo = AppRepository(":memory:")

    def tearDown(self):
        self.repo.close()

    def test_round_trips_soul_snapshot(self):
        self.repo.save_souls([soul_fixture()])
        self.assertEqual([soul_fixture()], self.repo.list_souls())

    def test_round_trips_setting(self):
        self.repo.set_setting("adb_path", "C:/MuMu/adb.exe")
        self.assertEqual("C:/MuMu/adb.exe", self.repo.get_setting("adb_path"))

    def test_appends_audit_events_in_order(self):
        self.repo.add_audit("tap", {"x": 10, "y": 20})
        self.repo.add_audit("stop", {"reason": "cancelled"})
        self.assertEqual(["tap", "stop"], [row["action"] for row in self.repo.list_audit()])


if __name__ == "__main__":
    unittest.main()
