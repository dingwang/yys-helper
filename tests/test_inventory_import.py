import json
import unittest

from yys_helper.application.inventory_import import (
    InventoryImportError,
    load_inventory_file,
    parse_inventory_json,
)
from yys_helper.domain.models import Stat


class InventoryImportTests(unittest.TestCase):
    def test_imports_fluxxu_snapshot(self):
        payload = {
            "data": {
                "hero_equips": [
                    {
                        "id": "abc",
                        "suit_id": 300010,
                        "pos": 1,
                        "quality": 6,
                        "level": 15,
                        "lock": True,
                        "garbage": False,
                        "base_attr": {"type": "Speed", "value": 57.0},
                        "attrs": [{"type": "CritRate", "value": 0.06}],
                        "single_attrs": [],
                    }
                ]
            }
        }

        preview = parse_inventory_json(json.dumps(payload).encode("utf-8"))

        self.assertEqual("fluxxu", preview.format_name)
        self.assertEqual(1, len(preview.souls))
        soul = preview.souls[0]
        self.assertEqual("fluxxu-abc", soul.id)
        self.assertEqual("招财猫", soul.set_name)
        self.assertEqual(2, soul.slot)
        self.assertEqual(Stat.SPEED, soul.main_stat)
        self.assertEqual(57.0, soul.main_value)
        self.assertEqual({Stat.CRIT_RATE: 6.0}, soul.substats)
        self.assertTrue(soul.locked)

    def test_fluxxu_boss_inherent_stat_is_added_to_matching_substat(self):
        payload = {
            "data": {
                "hero_equips": [
                    {
                        "id": "boss-fluxxu",
                        "suit_id": 300052,
                        "pos": 0,
                        "quality": 6,
                        "level": 15,
                        "base_attr": {"type": "Attack", "value": 486},
                        "attrs": [{"type": "CritRate", "value": 0.06}],
                        "single_attrs": [
                            {"type": "CritRate", "value": 0.08}
                        ],
                    }
                ]
            }
        }

        soul = parse_inventory_json(json.dumps(payload).encode()).souls[0]

        self.assertEqual({Stat.CRIT_RATE: 14.0}, soul.substats)

    def test_imports_new_client_export_and_marks_equipped(self):
        payload = {
            "ocr_info": {"version": 4.2},
            "equip_data": [
                {
                    "id": "new-1",
                    "suit_id": 300034,
                    "pos": 4,
                    "quality": 6,
                    "level": 15,
                    "lock": False,
                    "garbage": True,
                    "weared": True,
                    "base_attr": {"EffectHitRate": 0.55},
                    "rand_attr": {"Speed": 8.5, "HpRate": 0.03},
                    "single_attr": 0,
                }
            ],
        }

        preview = parse_inventory_json(json.dumps(payload).encode("utf-8"))

        self.assertEqual("hdtr-new", preview.format_name)
        soul = preview.souls[0]
        self.assertEqual("蚌精", soul.set_name)
        self.assertEqual(4, soul.slot)
        self.assertEqual(Stat.EFFECT_HIT, soul.main_stat)
        self.assertEqual(55.0, soul.main_value)
        self.assertEqual({Stat.SPEED: 8.5, Stat.HP_PCT: 3.0}, soul.substats)
        self.assertEqual("已装备", soul.equipped_to)
        self.assertTrue(soul.marked_discard)

    def test_new_client_boss_inherent_stat_is_added_to_matching_substat(self):
        payload = {
            "equip_data": [
                {
                    "id": "boss-new",
                    "suit_id": 300054,
                    "pos": 6,
                    "quality": 6,
                    "level": 15,
                    "base_attr": {"CritRate": 0.55},
                    "rand_attr": {"EffectResistRate": 0.04},
                    "single_attr": 6,
                }
            ]
        }

        soul = parse_inventory_json(json.dumps(payload).encode()).souls[0]

        self.assertEqual({Stat.EFFECT_RESIST: 12.0}, soul.substats)

    def test_imports_modern_soul_set_ids(self):
        payload = {
            "equip_data": [
                {
                    "id": "modern",
                    "suit_id": 300090,
                    "pos": 2,
                    "quality": 6,
                    "level": 0,
                    "base_attr": {"Speed": 12},
                    "rand_attr": {},
                    "single_attr": 0,
                }
            ]
        }

        soul = parse_inventory_json(json.dumps(payload).encode()).souls[0]

        self.assertEqual("钓瓶火", soul.set_name)

    def test_imports_native_inventory_format(self):
        payload = {
            "format": "yys-helper.inventory.v1",
            "souls": [
                {
                    "id": "native-1",
                    "set_name": "火灵",
                    "slot": 6,
                    "rarity": 6,
                    "level": 0,
                    "main_stat": "crit_rate",
                    "main_value": 10,
                    "substats": {"speed": 3},
                    "locked": False,
                }
            ],
        }

        preview = parse_inventory_json(json.dumps(payload).encode("utf-8"))

        self.assertEqual("yys-helper", preview.format_name)
        self.assertEqual("native-native-1", preview.souls[0].id)
        self.assertEqual(Stat.CRIT_RATE, preview.souls[0].main_stat)

    def test_rejects_partial_import_when_any_record_is_invalid(self):
        payload = {
            "data": {
                "hero_equips": [
                    {"id": "bad", "suit_id": 999999},
                    {
                        "id": "good",
                        "suit_id": 300010,
                        "pos": 1,
                        "quality": 6,
                        "level": 0,
                        "lock": False,
                        "garbage": False,
                        "base_attr": {"type": "Speed", "value": 12},
                        "attrs": [],
                        "single_attrs": [],
                    },
                ]
            }
        }

        with self.assertRaisesRegex(
            InventoryImportError, "第 1 条.*原库存未更改"
        ):
            parse_inventory_json(json.dumps(payload).encode("utf-8"))

    def test_rejects_duplicate_source_ids_before_database_write(self):
        soul = {
            "set_name": "火灵",
            "slot": 6,
            "rarity": 6,
            "level": 0,
            "main_stat": "crit_rate",
            "main_value": 10,
            "substats": {},
        }
        payload = {
            "format": "yys-helper.inventory.v1",
            "souls": [dict(soul, id="same"), dict(soul, id="same")],
        }

        with self.assertRaisesRegex(InventoryImportError, "重复.*原库存未更改"):
            parse_inventory_json(json.dumps(payload).encode())

    def test_checks_file_size_before_reading_payload(self):
        class OversizedPath:
            class StatResult:
                st_size = 64 * 1024 * 1024 + 1

            @staticmethod
            def stat():
                return OversizedPath.StatResult()

            @staticmethod
            def read_bytes():
                raise AssertionError("oversized file must not be read")

        with self.assertRaisesRegex(InventoryImportError, "64 MB"):
            load_inventory_file(OversizedPath())

    def test_rejects_unknown_or_empty_json(self):
        with self.assertRaisesRegex(InventoryImportError, "不支持"):
            parse_inventory_json(b'{"items": []}')
        with self.assertRaisesRegex(InventoryImportError, "没有可导入"):
            parse_inventory_json(b'{"format":"yys-helper.inventory.v1","souls":[]}')


if __name__ == "__main__":
    unittest.main()
