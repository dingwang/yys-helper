import unittest

from yys_helper.application.inventory_capture import (
    SchemeParseError,
    SchemeRequirementParser,
    SoulDetailParser,
    SoulParseError,
)
from yys_helper.domain.models import Stat
from yys_helper.infrastructure.vision import OcrBox


def box(text, confidence, top):
    return OcrBox(text, confidence, (900, top, 1250, top + 28))


class SoulDetailParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = SoulDetailParser()

    def test_parses_complete_six_star_soul_detail(self):
        boxes = [
            box("御魂详情", 0.99, 35),
            box("招财猫", 0.99, 80),
            box("+6", 0.98, 130),
            box("攻击加成 18%", 0.97, 210),
            box("速度 +8", 0.96, 280),
            box("暴击 +6%", 0.95, 330),
            box("暴击伤害 +11%", 0.94, 380),
            box("已锁定", 0.99, 450),
            box("装备于 千姬", 0.98, 500),
        ]

        soul = self.parser.parse(boxes, slot=2, rarity=6)

        self.assertEqual("招财猫", soul.set_name)
        self.assertEqual(2, soul.slot)
        self.assertEqual(6, soul.rarity)
        self.assertEqual(6, soul.level)
        self.assertEqual(Stat.ATTACK_PCT, soul.main_stat)
        self.assertEqual(18.0, soul.main_value)
        self.assertEqual(
            {
                Stat.SPEED: 8.0,
                Stat.CRIT_RATE: 6.0,
                Stat.CRIT_DAMAGE: 11.0,
            },
            soul.substats,
        )
        self.assertTrue(soul.locked)
        self.assertEqual("千姬", soul.equipped_to)
        self.assertEqual(0.94, soul.confidence)

    def test_percentage_suffix_selects_percentage_stat(self):
        boxes = [
            box("御魂详情", 0.99, 35),
            box("海月火玉", 0.99, 80),
            box("+0", 0.98, 130),
            box("生命加成 10%", 0.97, 210),
            box("防御加成 +3%", 0.96, 280),
            box("攻击 +27", 0.95, 330),
        ]

        soul = self.parser.parse(boxes, slot=4, rarity=6)

        self.assertEqual(Stat.HP_PCT, soul.main_stat)
        self.assertEqual(
            {Stat.DEFENSE_PCT: 3.0, Stat.ATTACK: 27.0}, soul.substats
        )

    def test_parses_detail_panel_without_a_title_anchor(self):
        boxes = [
            box("招财猫", 0.97, 80),
            box("+15", 0.91, 130),
            box("速度 57", 0.89, 210),
            box("暴击 +6%", 0.87, 280),
        ]

        soul = self.parser.parse(boxes, slot=2, rarity=6)

        self.assertEqual("招财猫", soul.set_name)
        self.assertEqual(15, soul.level)
        self.assertEqual(Stat.SPEED, soul.main_stat)
        self.assertEqual({Stat.CRIT_RATE: 6.0}, soul.substats)
        self.assertEqual(0.87, soul.confidence)

    def test_override_supplies_unrecognized_set_name_and_id_is_stable(self):
        boxes = [
            box("御魂详情", 0.99, 35),
            box("+15", 0.99, 130),
            box("速度 57", 0.98, 210),
            box("效果抵抗 +8%", 0.97, 280),
        ]

        first = self.parser.parse(
            boxes, slot=2, rarity=6, set_name_override="新御魂"
        )
        second = self.parser.parse(
            list(reversed(boxes)), slot=2, rarity=6, set_name_override="新御魂"
        )

        self.assertEqual("新御魂", first.set_name)
        self.assertEqual(first.id, second.id)

    def test_rejects_detail_missing_required_fields(self):
        with self.assertRaisesRegex(SoulParseError, "套装名.*主属性"):
            self.parser.parse(
                [box("御魂详情", 0.99, 35), box("+3", 0.99, 100)],
                slot=1,
                rarity=6,
            )

    def test_rejects_fragments_from_a_non_detail_page(self):
        boxes = [
            box("招财猫", 0.99, 80),
            box("+6", 0.99, 130),
            box("速度 24", 0.99, 210),
        ]

        with self.assertRaisesRegex(SoulParseError, "不像御魂详情页"):
            self.parser.parse(boxes, slot=2, rarity=6)

    def test_ignores_stats_outside_the_anchored_detail_panel(self):
        boxes = [
            OcrBox("生命 9999", 0.99, (80, 150, 260, 180)),
            box("御魂详情", 0.99, 35),
            box("招财猫", 0.99, 80),
            box("+6", 0.99, 130),
            box("速度 24", 0.99, 210),
            box("暴击 +6%", 0.99, 280),
        ]

        soul = self.parser.parse(boxes, slot=2, rarity=6)

        self.assertEqual(Stat.SPEED, soul.main_stat)
        self.assertEqual(24.0, soul.main_value)

    def test_ignores_set_name_outside_the_anchored_detail_panel(self):
        boxes = [
            OcrBox("破势", 0.99, (80, 80, 260, 110)),
            box("御魂详情", 0.99, 35),
            box("招财猫", 0.99, 80),
            box("+6", 0.99, 130),
            box("速度 24", 0.99, 210),
            box("暴击 +6%", 0.99, 280),
        ]

        soul = self.parser.parse(boxes, slot=2, rarity=6)

        self.assertEqual("招财猫", soul.set_name)


class SchemeRequirementParserTests(unittest.TestCase):
    def test_parses_sets_slot_main_stats_and_minimums(self):
        boxes = [
            box("方案详情", 0.99, 35),
            box("招财猫 4件套", 0.99, 80),
            box("火灵×2", 0.98, 120),
            box("二号位 速度", 0.97, 180),
            box("四号位 生命加成", 0.96, 220),
            box("六号位 暴击", 0.95, 260),
            box("速度 ≥ 128", 0.94, 320),
            box("满暴", 0.93, 360),
        ]
        weights = {Stat.SPEED: 1.5, Stat.CRIT_RATE: 2.0}

        requirement = SchemeRequirementParser().parse(boxes, weights=weights)

        self.assertEqual({"招财猫": 4, "火灵": 2}, requirement.set_counts)
        self.assertEqual(frozenset({Stat.SPEED}), requirement.main_stats[2])
        self.assertEqual(frozenset({Stat.HP_PCT}), requirement.main_stats[4])
        self.assertEqual(frozenset({Stat.CRIT_RATE}), requirement.main_stats[6])
        self.assertEqual(128.0, requirement.min_stats[Stat.SPEED])
        self.assertEqual(100.0, requirement.min_stats[Stat.CRIT_RATE])
        self.assertEqual(weights, requirement.weights)

    def test_parses_above_wording_for_total_stat(self):
        requirement = SchemeRequirementParser().parse(
            [box("方案详情", 0.99, 35), box("速度128以上", 0.99, 80)],
            weights={Stat.SPEED: 1.0},
        )

        self.assertEqual({Stat.SPEED: 128.0}, requirement.min_stats)

    def test_parses_split_lines_alternatives_and_upper_bounds(self):
        boxes = [
            OcrBox("方案", 0.99, (900, 35, 980, 63)),
            OcrBox("详情", 0.99, (985, 35, 1060, 63)),
            OcrBox("六号位", 0.99, (900, 100, 1000, 128)),
            OcrBox("暴击/暴击伤害", 0.99, (1010, 100, 1240, 128)),
            OcrBox("速度", 0.99, (900, 160, 980, 188)),
            OcrBox("不超过 150", 0.99, (990, 160, 1140, 188)),
        ]

        requirement = SchemeRequirementParser().parse(
            boxes, weights={Stat.SPEED: 1.0}
        )

        self.assertEqual(
            frozenset({Stat.CRIT_RATE, Stat.CRIT_DAMAGE}),
            requirement.main_stats[6],
        )
        self.assertEqual(150.0, requirement.max_stats[Stat.SPEED])

    def test_rejects_low_confidence_or_unanchored_partial_scheme(self):
        parser = SchemeRequirementParser()
        with self.assertRaisesRegex(SchemeParseError, "方案详情页"):
            parser.parse(
                [box("方案详情", 0.80, 35), box("速度 ≥ 128", 0.99, 80)],
                weights={Stat.SPEED: 1.0},
            )
        with self.assertRaisesRegex(SchemeParseError, "方案详情页"):
            parser.parse(
                [box("速度 ≥ 128", 0.99, 80)], weights={Stat.SPEED: 1.0}
            )


if __name__ == "__main__":
    unittest.main()
