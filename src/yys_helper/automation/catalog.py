"""Declarative fixed-stage task presets; no event-map or coordinate assumptions."""
from dataclasses import dataclass, asdict
import json

from .engine import Transition, Workflow
from .workflows import COMMON_STOPS, chapter_28_workflow, soul_dungeon_workflow
from yys_helper.domain.models import StopReason


@dataclass(frozen=True)
class TaskProfile:
    title: tuple[str, ...]
    start: tuple[str, ...] = ('挑战',)
    prepare: tuple[str, ...] = ('准备',)
    settlement: tuple[str, ...] = ('战斗胜利', '获得奖励', '战斗结算')
    confirm: tuple[str, ...] = ('确认', '继续')
    repeat: tuple[str, ...] = ('再次挑战',)

    def __post_init__(self):
        for values in asdict(self).values():
            if not isinstance(values, tuple) or not 1 <= len(values) <= 12 or any(
                not isinstance(v, str) or not v.strip() or len(v) > 40 for v in values
            ):
                raise ValueError('每组识别关键词需包含 1–12 个非空词，每词最多 40 字。')
        if any(title in button for title in self.title
               for button in self.start + self.prepare + self.confirm + self.repeat):
            raise ValueError('关卡标题不能使用挑战、准备等按钮文字；请填写独立的关卡名称。')

    def to_json(self):
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, value):
        try:
            data = json.loads(value)
            if not isinstance(data, dict) or any(not isinstance(v, list) for v in data.values()):
                raise ValueError('配置格式不正确')
            return cls(**{key: tuple(values) for key, values in data.items()})
        except (TypeError, KeyError, json.JSONDecodeError) as exc:
            raise ValueError('配置格式不正确') from exc


@dataclass(frozen=True)
class TaskPreset:
    id: str
    title: str
    category: str
    description: str
    profile: TaskProfile | None = None


TASKS = (
    TaskPreset('chapter28', '困 28 · 经验', '日常', '手动进入探索地图；循环选怪、战斗和结算，不更换狗粮。'),
    TaskPreset('soul', '御魂副本', '日常', '使用当前阵容循环挑战。建议从副本挑战页开始。'),
    TaskPreset('awakening', '觉醒材料', '材料', '手动选择麒麟与层数，再从挑战页开始。', TaskProfile(('觉醒', '麒麟'))),
    TaskPreset('spirit', '御灵之境', '材料', '手动选择御灵与层数，材料不足时停止。', TaskProfile(('御灵',))),
    TaskPreset('sougenbi', '业原火', '材料', '手动选定贪、嗔或痴，使用当前队伍。', TaskProfile(('业原火',))),
    TaskPreset('sun', '日轮之陨', '材料', '固定层数循环，不自动换阵容或组队。', TaskProfile(('日轮之陨',))),
    TaskPreset('sea', '永生之海', '材料', '固定层数；请先配置好各阶段队伍。', TaskProfile(('永生之海',))),
    TaskPreset('event_tower', '活动 · 爬塔刷层', '活动', '重复已选定的同一关卡，不自动选路线或爬下一层。请配置本期关卡标题。', TaskProfile(('请填写本期关卡标题',))),
    TaskPreset('event_stage', '活动 · 单关刷取', '活动', '挑战 → 准备 → 战斗 → 奖励 → 再次挑战。请配置本期关卡标题。', TaskProfile(('请填写本期关卡标题',))),
    TaskPreset('event_boss', '活动 · 首领挑战', '活动', '重复当前可挑战的首领；不搜索新首领、不处理邀请或跨地图导航。', TaskProfile(('请填写本期关卡标题',))),
)


def get_task(task_id):
    for task in TASKS:
        if task.id == task_id:
            return task
    raise ValueError(f'未知任务：{task_id}')


def workflow_for(task_id):
    task = get_task(task_id)
    if task_id == 'chapter28':
        return chapter_28_workflow()
    if task_id == 'soul':
        return soul_dungeon_workflow()
    return Workflow(task.title, {
        'ready': Transition('task_start', ('prepare', 'battle'), poll_delay_seconds=2),
        'prepare': Transition('task_prepare', ('battle',), poll_delay_seconds=2),
        'battle': Transition('wait_battle', ('battle', 'settlement', 'repeat'), poll_delay_seconds=2),
        'settlement': Transition('task_confirm', ('settlement', 'repeat', 'ready'), round_completed=True, poll_delay_seconds=2),
        'repeat': Transition('task_repeat', ('ready', 'prepare', 'battle'), round_completed=True, poll_delay_seconds=2),
    }, stop_scenes={**COMMON_STOPS, 'resource_empty': StopReason.ACTION_FAILED,
                    'defeat': StopReason.ACTION_FAILED, 'purchase': StopReason.ACTION_FAILED},
       track_battles=True)
