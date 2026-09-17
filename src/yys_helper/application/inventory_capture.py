from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping

from yys_helper.domain.models import Soul, Stat
from yys_helper.infrastructure.vision import OcrBox


class SoulParseError(ValueError):
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
        ordered = sorted(boxes, key=lambda box: (box.bounds[1], box.bounds[0]))
        texts = [_normalize_text(box.text) for box in ordered]
        used_confidences: list[float] = []

        set_name = set_name_override.strip()
        if not set_name:
            for box, text in zip(ordered, texts, strict=True):
                match = next((name for name in KNOWN_SOUL_SETS if name in text), None)
                if match:
                    set_name = match
                    used_confidences.append(box.confidence)
                    break

        level = None
        for box, text in zip(ordered, texts, strict=True):
            match = re.fullmatch(r"(?:强化)?\s*\+\s*([0-9]|1[0-5])", text)
            if match:
                level = int(match.group(1))
                used_confidences.append(box.confidence)
                break

        stats: list[tuple[Stat, float]] = []
        for box, text in zip(ordered, texts, strict=True):
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
