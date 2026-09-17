from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping

from yys_helper.domain.models import BuildRequirement, Soul, Stat
from yys_helper.infrastructure.vision import OcrBox


class SoulParseError(ValueError):
    pass


class SchemeParseError(ValueError):
    pass


KNOWN_SOUL_SETS = (
    "雪幽魂",
    "地藏像",
    "蝠翼",
    "涅槃之火",
    "三味",
    "魍魉之匣",
    "被服",
    "镜姬",
    "钟灵",
    "破势",
    "针女",
    "树妖",
    "网切",
    "心眼",
    "反枕",
    "日女巳时",
    "薙魂",
    "狰",
    "轮入道",
    "阴摩罗",
    "伤魂鸟",
    "木魅",
    "火灵",
    "蚌精",
    "魅妖",
    "镇墓兽",
    "珍珠",
    "骰子鬼",
    "招财猫",
    "狂骨",
    "幽谷响",
    "兵主部",
    "涂佛",
    "飞缘魔",
    "青女房",
    "海月火玉",
    "遗念火",
    "共潜",
    "恶楼",
    "出世螺",
    "火之车",
    "隐念",
    "应声虫",
    "元兴寺",
    "钓瓶火",
    "叠叩",
    "散件",
)


_STAT_LABELS = (
    ("暴击伤害", Stat.CRIT_DAMAGE),
    ("暴伤", Stat.CRIT_DAMAGE),
    ("效果命中", Stat.EFFECT_HIT),
    ("效果抵抗", Stat.EFFECT_RESIST),
    ("攻击加成", Stat.ATTACK_PCT),
    ("生命加成", Stat.HP_PCT),
    ("防御加成", Stat.DEFENSE_PCT),
    ("暴击", Stat.CRIT_RATE),
    ("速度", Stat.SPEED),
    ("攻击", Stat.ATTACK),
    ("生命", Stat.HP),
    ("防御", Stat.DEFENSE),
)

_SOUL_DETAIL_ANCHORS = (
    "御魂详情",
    "御魂强化",
    "御魂属性",
)

_SCHEME_DETAIL_ANCHORS = (
    "方案详情",
    "阵容助手",
    "御魂搭配",
    "配装方案",
    "计算结果",
)


def _normalize_text(value: str) -> str:
    return (
        value.strip()
        .replace("：", ":")
        .replace("％", "%")
        .replace(",", "")
        .replace("，", "")
    )


def _parse_stat(text: str) -> tuple[Stat, float] | None:
    compact = re.sub(r"\s+", "", _normalize_text(text))
    for label, stat in _STAT_LABELS:
        match = re.search(
            rf"{re.escape(label)}:?\+?(-?\d+(?:\.\d+)?)%?", compact
        )
        if match:
            return stat, float(match.group(1))
    return None


def _stats_from_label(text: str) -> frozenset[Stat]:
    remaining = re.sub(r"\s+", "", _normalize_text(text))
    result: list[Stat] = []
    for label, stat in _STAT_LABELS:
        if label not in remaining:
            continue
        result.append(stat)
        remaining = remaining.replace(label, "", 1)
    return frozenset(result)


def _group_lines(
    boxes: Iterable[OcrBox], *, min_confidence: float = 0.92
) -> list[str]:
    accepted = [box for box in boxes if box.confidence >= min_confidence]
    ordered = sorted(accepted, key=lambda box: (box.center[1], box.bounds[0]))
    lines: list[list[OcrBox]] = []
    for box in ordered:
        center_y = box.center[1]
        height = max(1, box.bounds[3] - box.bounds[1])
        if lines:
            line_y = sum(item.center[1] for item in lines[-1]) / len(lines[-1])
            if abs(center_y - line_y) <= max(8, height * 0.75):
                lines[-1].append(box)
                continue
        lines.append([box])
    return [
        "".join(
            _normalize_text(item.text)
            for item in sorted(line, key=lambda item: item.bounds[0])
        )
        for line in lines
    ]


def _fingerprint(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "ocr-" + hashlib.sha256(encoded).hexdigest()[:24]


class SoulDetailParser:
    def parse(
        self,
        boxes: Iterable[OcrBox],
        *,
        slot: int,
        rarity: int,
        set_name_override: str = "",
    ) -> Soul:
        all_boxes = list(boxes)
        anchor = next(
            (
                box
                for box in all_boxes
                if box.confidence >= 0.92
                and any(name in _normalize_text(box.text) for name in _SOUL_DETAIL_ANCHORS)
            ),
            None,
        )
        if anchor is None:
            raise SoulParseError("当前画面不像御魂详情页，请手动打开详情后重试")

        anchor_x = anchor.center[0]
        panel_half_width = max(420, (anchor.bounds[2] - anchor.bounds[0]) * 2)
        ordered = sorted(
            (
                box
                for box in all_boxes
                if abs(box.center[0] - anchor_x) <= panel_half_width
                and box.center[1] >= anchor.bounds[1] - 12
            ),
            key=lambda box: (box.bounds[1], box.bounds[0]),
        )
        texts = [_normalize_text(box.text) for box in ordered]
        used_confidences: list[float] = [anchor.confidence]

        set_name = set_name_override.strip()
        if not set_name:
            for box, text in zip(ordered, texts, strict=True):
                match = next((name for name in KNOWN_SOUL_SETS if name in text), None)
                if match:
                    set_name = match
                    used_confidences.append(box.confidence)
                    break

        level = None
        level_bottom = None
        for box, text in zip(ordered, texts, strict=True):
            match = re.fullmatch(r"(?:强化)?\s*\+\s*([0-9]|1[0-5])", text)
            if match:
                level = int(match.group(1))
                level_bottom = box.bounds[3]
                used_confidences.append(box.confidence)
                break

        stats: list[tuple[Stat, float]] = []
        for box, text in zip(ordered, texts, strict=True):
            if level_bottom is not None and box.center[1] <= level_bottom:
                continue
            parsed = _parse_stat(text)
            if parsed is not None:
                stats.append(parsed)
                used_confidences.append(box.confidence)

        missing: list[str] = []
        if not set_name:
            missing.append("套装名")
        if level is None:
            missing.append("等级")
        if not stats:
            missing.append("主属性")
        if missing:
            raise SoulParseError("无法识别：" + "、".join(missing))

        equipped_to = None
        locked = False
        for box, text in zip(ordered, texts, strict=True):
            if "锁定" in text:
                locked = True
                used_confidences.append(box.confidence)
            match = re.search(r"装备于\s*[:：]?\s*(\S+)", text)
            if match:
                equipped_to = match.group(1)
                used_confidences.append(box.confidence)

        main_stat, main_value = stats[0]
        substats = {stat: value for stat, value in stats[1:]}
        identity = {
            "set_name": set_name,
            "slot": slot,
            "rarity": rarity,
            "level": level,
            "main_stat": main_stat.value,
            "main_value": main_value,
            "substats": {stat.value: value for stat, value in substats.items()},
        }
        confidence = min(used_confidences, default=0.0)
        return Soul(
            id=_fingerprint(identity),
            set_name=set_name,
            slot=slot,
            rarity=rarity,
            level=level,
            main_stat=main_stat,
            main_value=main_value,
            substats=substats,
            locked=locked,
            equipped_to=equipped_to,
            confidence=confidence,
        )


class SchemeRequirementParser:
    _SLOT_NUMBERS = {"二": 2, "2": 2, "四": 4, "4": 4, "六": 6, "6": 6}

    def parse(
        self,
        boxes: Iterable[OcrBox],
        *,
        weights: Mapping[Stat, float],
    ) -> BuildRequirement:
        texts = _group_lines(boxes)
        if not any(
            anchor in text
            for anchor in _SCHEME_DETAIL_ANCHORS
            for text in texts
        ):
            raise SchemeParseError("当前画面不像方案详情页，请打开计算结果后重试")
        set_counts: dict[str, int] = {}
        main_stats: dict[int, frozenset[Stat]] = {}
        minimums: dict[Stat, float] = {}
        maximums: dict[Stat, float] = {}

        for text in texts:
            compact = re.sub(r"\s+", "", text)
            for set_name in KNOWN_SOUL_SETS:
                if set_name not in compact:
                    continue
                count_match = re.search(
                    rf"{re.escape(set_name)}(?:[×xX*]([246])|([246])件套)", compact
                )
                if count_match:
                    set_counts[set_name] = int(
                        count_match.group(1) or count_match.group(2)
                    )

            slot_match = re.search(r"([二四2四六6])号?位", compact)
            if slot_match:
                slot = self._SLOT_NUMBERS.get(slot_match.group(1))
                stats = _stats_from_label(compact[slot_match.end() :])
                if slot is not None and stats:
                    main_stats[slot] = stats
                continue

            if "满暴" in compact or "暴击满" in compact:
                minimums[Stat.CRIT_RATE] = 100.0

            for label, stat in _STAT_LABELS:
                minimum_match = re.search(
                    rf"{re.escape(label)}(?:总值)?(?:"
                    rf"(?:≥|>=|>|不低于)(\d+(?:\.\d+)?)|"
                    rf"(\d+(?:\.\d+)?)(?:以上))",
                    compact,
                )
                if minimum_match:
                    minimums[stat] = float(
                        minimum_match.group(1) or minimum_match.group(2)
                    )
                    break
                maximum_match = re.search(
                    rf"{re.escape(label)}(?:总值)?(?:"
                    rf"(?:≤|<=|<|不超过)(\d+(?:\.\d+)?)|"
                    rf"(\d+(?:\.\d+)?)(?:以下))",
                    compact,
                )
                if maximum_match:
                    maximums[stat] = float(
                        maximum_match.group(1) or maximum_match.group(2)
                    )
                    break

        if not (set_counts or main_stats or minimums or maximums):
            raise SchemeParseError("当前画面没有识别到可用的方案约束")
        return BuildRequirement(
            set_counts=set_counts,
            main_stats=main_stats,
            min_stats=minimums,
            max_stats=maximums,
            weights=dict(weights),
        )
