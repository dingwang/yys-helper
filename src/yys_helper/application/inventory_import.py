from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from yys_helper.domain.models import Soul, Stat


class InventoryImportError(ValueError):
    pass


MAX_INVENTORY_FILE_BYTES = 64 * 1024 * 1024
SOUL_SET_MAP_VERSION = "2026-09-18"


class InventoryFile(Protocol):
    def stat(self): ...

    def read_bytes(self) -> bytes: ...


@dataclass(frozen=True, slots=True)
class ImportPreview:
    format_name: str
    souls: tuple[Soul, ...]
    warnings: tuple[str, ...] = ()


_SOUL_SET_IDS = {
    300074: "兵主部",
    300048: "狂骨",
    300027: "阴摩罗",
    300022: "心眼",
    300020: "鸣屋",
    300018: "狰",
    300012: "轮入道",
    300004: "蝠翼",
    300075: "青女房",
    300036: "针女",
    300031: "镇墓兽",
    300030: "破势",
    300029: "伤魂鸟",
    300026: "网切",
    300007: "三味",
    300076: "涂佛",
    300024: "树妖",
    300021: "薙魂",
    300015: "钟灵",
    300014: "镜姬",
    300009: "被服",
    300006: "涅槃之火",
    300003: "地藏像",
    300035: "魅妖",
    300032: "珍珠",
    300023: "木魅",
    300013: "日女巳时",
    300011: "反枕",
    300010: "招财猫",
    300002: "雪幽魂",
    300073: "飞缘魔",
    300034: "蚌精",
    300019: "火灵",
    300049: "幽谷响",
    300039: "返魂香",
    300033: "骰子鬼",
    300008: "魍魉之匣",
    300077: "鬼灵歌伎",
    300054: "蜃气楼",
    300053: "地震鲶",
    300052: "荒骷髅",
    300051: "胧车",
    300050: "土蜘蛛",
    300055: "片叶之苇",
    300056: "尘冢",
    300057: "油赤子",
    300058: "夜啼石",
    300059: "夜送犬",
    300060: "雨降",
    300079: "遗念火",
    300080: "共潜",
    300081: "恶楼",
    300082: "贝吹坊",
    300083: "海月火玉",
    300084: "出世螺",
    300085: "火之车",
    300086: "隐念",
    300087: "叠叩",
    300088: "应声虫",
    300089: "元兴寺",
    300090: "钓瓶火",
    300091: "夜荒魂",
    300092: "无刀取",
    300093: "奉海图",
    300094: "八咫镜",
    300095: "天羽羽斩",
    300096: "预言星盘",
    300097: "月之石",
    300098: "纺缘锤",
    300099: "稻荷穗箭",
}

_STAT_IDS = {
    "Hp": Stat.HP,
    "Defense": Stat.DEFENSE,
    "Attack": Stat.ATTACK,
    "HpRate": Stat.HP_PCT,
    "DefenseRate": Stat.DEFENSE_PCT,
    "AttackRate": Stat.ATTACK_PCT,
    "Speed": Stat.SPEED,
    "CritRate": Stat.CRIT_RATE,
    "CritPower": Stat.CRIT_DAMAGE,
    "EffectHitRate": Stat.EFFECT_HIT,
    "EffectResistRate": Stat.EFFECT_RESIST,
}

_RATE_STATS = {
    Stat.HP_PCT,
    Stat.DEFENSE_PCT,
    Stat.ATTACK_PCT,
    Stat.CRIT_RATE,
    Stat.CRIT_DAMAGE,
    Stat.EFFECT_HIT,
    Stat.EFFECT_RESIST,
}

_SINGLE_ATTR_IDS = {
    1: (Stat.ATTACK_PCT, 8.0),
    2: (Stat.HP_PCT, 8.0),
    3: (Stat.DEFENSE_PCT, 16.0),
    4: (Stat.CRIT_RATE, 8.0),
    5: (Stat.EFFECT_HIT, 8.0),
    6: (Stat.EFFECT_RESIST, 8.0),
}


def _set_name(suit_id: object) -> str:
    try:
        return _SOUL_SET_IDS[int(suit_id)]
    except (KeyError, TypeError, ValueError) as exc:
        raise InventoryImportError(f"未知御魂套装 ID：{suit_id}") from exc


def _stat_value(type_name: object, value: object) -> tuple[Stat, float]:
    try:
        stat = _STAT_IDS[str(type_name)]
        number = float(value)
    except (KeyError, TypeError, ValueError) as exc:
        raise InventoryImportError(
            f"未知或无效的属性：{type_name}={value}"
        ) from exc
    if stat in _RATE_STATS:
        number = round(number * 100.0, 6)
    return stat, number


def _source_id(prefix: str, value: object) -> str:
    source_id = str(value).strip()
    if not source_id:
        raise InventoryImportError("御魂 ID 不能为空")
    return f"{prefix}-{source_id}"


def _add_substat(substats: dict[Stat, float], stat: Stat, value: float) -> None:
    substats[stat] = round(substats.get(stat, 0.0) + value, 6)


def _parse_fluxxu(item: Mapping[str, object]) -> Soul:
    base = item["base_attr"]
    if not isinstance(base, Mapping):
        raise InventoryImportError("base_attr 必须是对象")
    main_stat, main_value = _stat_value(base.get("type"), base.get("value"))
    raw_attrs = item.get("attrs", [])
    if not isinstance(raw_attrs, Sequence) or isinstance(raw_attrs, (str, bytes)):
        raise InventoryImportError("attrs 必须是数组")
    substats: dict[Stat, float] = {}
    for raw in raw_attrs:
        if not isinstance(raw, Mapping):
            raise InventoryImportError("副属性必须是对象")
        stat, value = _stat_value(raw.get("type"), raw.get("value"))
        _add_substat(substats, stat, value)
    raw_single_attrs = item.get("single_attrs", [])
    if not isinstance(raw_single_attrs, Sequence) or isinstance(
        raw_single_attrs, (str, bytes)
    ):
        raise InventoryImportError("single_attrs 必须是数组")
    for raw in raw_single_attrs:
        if not isinstance(raw, Mapping):
            raise InventoryImportError("固有属性必须是对象")
        stat, value = _stat_value(raw.get("type"), raw.get("value"))
        _add_substat(substats, stat, value)
    return Soul(
        id=_source_id("fluxxu", item["id"]),
        set_name=_set_name(item["suit_id"]),
        slot=int(item["pos"]) + 1,
        rarity=int(item["quality"]),
        level=int(item["level"]),
        main_stat=main_stat,
        main_value=main_value,
        substats=substats,
        locked=bool(item.get("lock", False)),
        equipped_to="已装备" if item.get("weared") else None,
        marked_discard=bool(item.get("garbage", False)),
    )


def _parse_hdtr_new(item: Mapping[str, object]) -> Soul:
    base = item["base_attr"]
    attrs = item.get("rand_attr", {})
    if not isinstance(base, Mapping) or len(base) != 1:
        raise InventoryImportError("base_attr 必须只包含一个主属性")
    if not isinstance(attrs, Mapping):
        raise InventoryImportError("rand_attr 必须是对象")
    main_name, main_raw_value = next(iter(base.items()))
    main_stat, main_value = _stat_value(main_name, main_raw_value)
    substats: dict[Stat, float] = {}
    for name, value in attrs.items():
        stat, parsed_value = _stat_value(name, value)
        _add_substat(substats, stat, parsed_value)
    try:
        single_attr_id = int(item.get("single_attr", 0))
    except (TypeError, ValueError) as exc:
        raise InventoryImportError("single_attr 必须是整数") from exc
    if single_attr_id:
        try:
            stat, value = _SINGLE_ATTR_IDS[single_attr_id]
        except KeyError as exc:
            raise InventoryImportError(
                f"未知固有属性 ID：{single_attr_id}"
            ) from exc
        _add_substat(substats, stat, value)
    return Soul(
        id=_source_id("hdtr", item["id"]),
        set_name=_set_name(item["suit_id"]),
        slot=int(item["pos"]),
        rarity=int(item["quality"]),
        level=int(item["level"]),
        main_stat=main_stat,
        main_value=main_value,
        substats=substats,
        locked=bool(item.get("lock", False)),
        equipped_to="已装备" if item.get("weared") else None,
        marked_discard=bool(item.get("garbage", False)),
    )


def _parse_native(item: Mapping[str, object]) -> Soul:
    raw_substats = item.get("substats", {})
    if not isinstance(raw_substats, Mapping):
        raise InventoryImportError("substats 必须是对象")
    try:
        return Soul(
            id=_source_id("native", item["id"]),
            set_name=str(item["set_name"]),
            slot=int(item["slot"]),
            rarity=int(item["rarity"]),
            level=int(item["level"]),
            main_stat=Stat(str(item["main_stat"])),
            main_value=float(item["main_value"]),
            substats={
                Stat(str(name)): float(value)
                for name, value in raw_substats.items()
            },
            locked=bool(item.get("locked", False)),
            equipped_to=(
                str(item["equipped_to"])
                if item.get("equipped_to") is not None
                else None
            ),
            marked_discard=bool(item.get("marked_discard", False)),
            confidence=float(item.get("confidence", 1.0)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise InventoryImportError(f"标准字段无效：{exc}") from exc


def _parse_records(
    format_name: str,
    records: object,
    parser: Callable[[Mapping[str, object]], Soul],
) -> ImportPreview:
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        raise InventoryImportError("御魂列表必须是数组")
    souls: list[Soul] = []
    errors: list[str] = []
    for index, raw in enumerate(records, start=1):
        try:
            if not isinstance(raw, Mapping):
                raise InventoryImportError("记录必须是对象")
            souls.append(parser(raw))
        except (InventoryImportError, KeyError, TypeError, ValueError) as exc:
            errors.append(f"第 {index} 条：{exc}")
    id_counts = Counter(soul.id for soul in souls)
    duplicate_ids = sorted(
        soul_id for soul_id, count in id_counts.items() if count > 1
    )
    if duplicate_ids:
        errors.append("存在重复御魂 ID：" + "、".join(duplicate_ids[:3]))
    if errors:
        detail = "；".join(errors[:5])
        if len(errors) > 5:
            detail += f"；另有 {len(errors) - 5} 条错误"
        raise InventoryImportError(
            f"库存校验失败：{detail}；原库存未更改"
        )
    if not souls:
        raise InventoryImportError("文件中没有可导入的有效御魂")
    return ImportPreview(format_name, tuple(souls))


def parse_inventory_json(payload: bytes) -> ImportPreview:
    if len(payload) > MAX_INVENTORY_FILE_BYTES:
        raise InventoryImportError("JSON 文件超过 64 MB 安全上限")
    try:
        data = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InventoryImportError("不是有效的 UTF-8 JSON 文件") from exc

    if isinstance(data, Mapping) and data.get("format") == "yys-helper.inventory.v1":
        return _parse_records("yys-helper", data.get("souls"), _parse_native)
    if (
        isinstance(data, Mapping)
        and isinstance(data.get("data"), Mapping)
        and "hero_equips" in data["data"]
    ):
        return _parse_records(
            "fluxxu", data["data"]["hero_equips"], _parse_fluxxu
        )
    if isinstance(data, Mapping) and "equip_data" in data:
        return _parse_records("hdtr-new", data["equip_data"], _parse_hdtr_new)
    raise InventoryImportError(
        "不支持的御魂 JSON 格式；请选择痒痒熊、新客户端导出或御魂匠格式"
    )


def load_inventory_file(path: InventoryFile) -> ImportPreview:
    if path.stat().st_size > MAX_INVENTORY_FILE_BYTES:
        raise InventoryImportError("JSON 文件超过 64 MB 安全上限")
    return parse_inventory_json(path.read_bytes())
