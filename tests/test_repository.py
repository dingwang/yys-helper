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

    def test_replace_souls_is_atomic_when_input_iteration_fails(self):
        original = soul_fixture()
        replacement = Soul(
            id="replacement",
            set_name="火灵",
            slot=6,
            rarity=6,
            level=0,
            main_stat=Stat.CRIT_RATE,
            main_value=10,
            substats={Stat.SPEED: 3},
        )
        self.repo.save_souls([original])

        def broken_import():
            yield replacement
            raise RuntimeError("broken source")

        with self.assertRaisesRegex(RuntimeError, "broken source"):
            self.repo.replace_souls(broken_import())

        self.assertEqual([original], self.repo.list_souls())

    def test_deletes_one_soul_without_touching_others(self):
        first = soul_fixture()
        second = Soul(
            id="s-2",
            set_name="火灵",
            slot=4,
            rarity=6,
            level=0,
            main_stat=Stat.HP_PCT,
            main_value=10,
            substats={Stat.SPEED: 3},
        )
        self.repo.save_souls([first, second])

        self.repo.delete_soul(first.id)

        self.assertEqual([second], self.repo.list_souls())

    def test_round_trips_setting(self):
        self.repo.set_setting("adb_path", "C:/MuMu/adb.exe")
        self.assertEqual("C:/MuMu/adb.exe", self.repo.get_setting("adb_path"))

    def test_bulk_settings_roll_back_on_constraint_failure(self):
        import sqlite3
        self.repo.set_setting('task_rounds', '30')
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.set_settings({'task_rounds': '12', 'invalid': None})
        self.assertEqual('30', self.repo.get_setting('task_rounds'))
        self.assertIsNone(self.repo.get_setting('invalid'))

    def test_appends_audit_events_in_order(self):
        self.repo.add_audit("tap", {"x": 10, "y": 20})
        self.repo.add_audit("stop", {"reason": "cancelled"})
        self.assertEqual(["tap", "stop"], [row["action"] for row in self.repo.list_audit()])


if __name__ == "__main__":
    unittest.main()
