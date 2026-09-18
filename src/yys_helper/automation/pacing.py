"""Bounded interaction pacing. Not an anti-detection or account-safety guarantee."""
from dataclasses import dataclass
from math import isfinite
from random import Random


@dataclass(frozen=True)
class PacingPolicy:
    action_seconds: tuple[float, float] = (.4, 1.2)
    poll_extra_seconds: tuple[float, float] = (.1, .6)
    rest_rounds: tuple[int, int] = (8, 12)
    rest_seconds: tuple[float, float] = (20, 45)
    click_fraction: float = .12

    def __post_init__(self):
        for pair in (self.action_seconds, self.poll_extra_seconds, self.rest_seconds):
            if len(pair) != 2 or any(not isfinite(v) for v in pair) or not 0 <= pair[0] <= pair[1] <= 120:
                raise ValueError('等待区间必须是 0–120 秒内的有限有序范围')
        if (len(self.rest_rounds) != 2 or any(type(n) is not int for n in self.rest_rounds)
                or not 1 <= self.rest_rounds[0] <= self.rest_rounds[1] <= 50):
            raise ValueError('休息轮数必须在 1–50 之间')
        if not isfinite(self.click_fraction) or not 0 <= self.click_fraction <= .15:
            raise ValueError('落点偏移不得超过识别框的 15%')

    @classmethod
    def for_mode(cls, mode: str):
        if mode == 'standard':
            return cls()
        if mode == 'relaxed':
            return cls(action_seconds=(.8, 1.8), poll_extra_seconds=(.3, 1.),
                       rest_rounds=(5, 8), rest_seconds=(30, 60))
        raise ValueError('未知节奏模式')


class PacingController:
    def __init__(self, policy: PacingPolicy | None = None, rng: Random | None = None):
        self.policy = policy or PacingPolicy()
        self.rng = rng or Random()
        self.next_rest = self.rng.randint(*self.policy.rest_rounds)

    def action_delay(self):
        return self.rng.uniform(*self.policy.action_seconds)

    def poll_delay(self, base):
        return base + self.rng.uniform(*self.policy.poll_extra_seconds)

    def rest_duration(self, completed_rounds):
        if completed_rounds < self.next_rest:
            return 0.
        self.next_rest = completed_rounds + self.rng.randint(*self.policy.rest_rounds)
        return self.rng.uniform(*self.policy.rest_seconds)

    def point(self, bounds):
        left, top, right, bottom = bounds
        if not all(isfinite(v) for v in bounds) or right <= left or bottom <= top:
            raise ValueError('无效的点击目标框')
        x, y = (left + right) / 2, (top + bottom) / 2
        dx, dy = (right - left) * self.policy.click_fraction, (bottom - top) * self.policy.click_fraction
        return (max(int(left), min(int(right) - 1, round(self.rng.uniform(x - dx, x + dx)))),
                max(int(top), min(int(bottom) - 1, round(self.rng.uniform(y - dy, y + dy)))))
