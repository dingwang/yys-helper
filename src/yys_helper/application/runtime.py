from __future__ import annotations

from io import BytesIO
from time import sleep
from threading import RLock
from typing import Callable, Iterable

from PIL import Image

from yys_helper.infrastructure.adb import AdbClient
from yys_helper.infrastructure.vision import OcrBox, VisionService


class CaptureError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        stage: str,
        png: bytes,
        boxes: Iterable[OcrBox] = (),
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.png = png
        self.boxes = tuple(boxes)


_ACTION_TEXT: dict[str, tuple[str, ...]] = {
    "open_explore": ("探索",),
    "select_chapter_28_hard": ("第二十八章", "困难"),
    "tap_monster": ("挑战",),
    "open_soul_dungeon": ("御魂",),
    "start_battle": ("挑战", "准备"),
    "confirm": ("确认", "继续", "获得奖励"),
    "challenge_again": ("再次挑战",),
    "wait_battle": (),
}


def resolve_action_text(action: str) -> tuple[str, ...]:
    return _ACTION_TEXT.get(action, ())


def _contains(texts: list[str], *needles: str) -> bool:
    return any(any(needle in text for needle in needles) for text in texts)


def classify_scene(boxes: Iterable[OcrBox], min_confidence: float = 0.92) -> str | None:
    texts = [box.text for box in boxes if box.confidence >= min_confidence]
    if _contains(texts, "体力不足", "体力不够"):
        return "stamina_empty"
    if _contains(texts, "网络连接", "重新连接", "连接中断"):
        return "network_error"
    if _contains(texts, "御魂已满", "背包已满"):
        return "inventory_full"
    if _contains(texts, "登录游戏", "进入游戏"):
        return "login"
    if _contains(texts, "战斗胜利", "获得奖励", "战斗结算"):
        return "settlement"
    if _contains(texts, "第二十八章"):
        return "chapter_select"
    if _contains(texts, "御魂副本") and _contains(texts, "挑战", "准备"):
        return "soul_ready"
    if _contains(texts, "自动") and _contains(texts, "回合", "退出"):
        return "battle"
    if _contains(texts, "探索地图", "退出探索"):
        return "explore_map"
    if _contains(texts, "探索") and _contains(texts, "御魂"):
        return "home"
    return None


class OcrMumuRuntime:
    """Scene observer and text-only actor with no coordinate fallbacks."""

    def __init__(
        self,
        adb: AdbClient,
        vision: VisionService,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        self.adb = adb
        self.vision = vision
        self.sleeper = sleeper
        self.last_image = None
        self.last_capture_png: bytes | None = None
        self.last_boxes: list[OcrBox] = []
        self.last_capture_error: str | None = None
        self._io_lock = RLock()

    def _capture_with_png(self) -> tuple[bytes, Image.Image, list[OcrBox]]:
        png = self.adb.screenshot()
        try:
            image = Image.open(BytesIO(png)).convert("RGB")
        except Exception as exc:
            raise CaptureError(
                f"截图解码失败：{exc}", stage="decode", png=png
            ) from exc
        try:
            boxes = list(self.vision.read(image))
        except Exception as exc:
            raise CaptureError(
                f"OCR 识别失败：{exc}", stage="ocr", png=png
            ) from exc
        return png, image, boxes

    def _capture(self) -> tuple[Image.Image, list[OcrBox]]:
        _png, image, boxes = self._capture_with_png()
        return image, boxes

    def capture_boxes(self) -> tuple[OcrBox, ...]:
        """Capture OCR for a read-only feature without changing actor state."""
        with self._io_lock:
            _image, boxes = self._capture()
            return tuple(boxes)

    def capture_evidence(self) -> tuple[bytes, tuple[OcrBox, ...]]:
        """Return the raw screenshot and OCR without changing actor state."""
        with self._io_lock:
            png, _image, boxes = self._capture_with_png()
            return png, tuple(boxes)

    def observe(self) -> str | None:
        with self._io_lock:
            self.last_capture_error = None
            try:
                (
                    self.last_capture_png,
                    self.last_image,
                    self.last_boxes,
                ) = self._capture_with_png()
            except CaptureError as exc:
                self.last_capture_png = exc.png
                self.last_image = None
                self.last_boxes = list(exc.boxes)
                self.last_capture_error = str(exc)
                raise
            return classify_scene(self.last_boxes)

    def perform(self, action: str) -> bool:
        with self._io_lock:
            if action == "wait_battle":
                return True
            labels = resolve_action_text(action)
            if action == "select_chapter_28_hard":
                return self._perform_sequence(labels)
            for label in labels:
                target = self._find_label(label)
                if target is not None:
                    self.adb.tap(*target.center)
                    return True
            return False

    def _perform_sequence(self, labels: tuple[str, ...]) -> bool:
        for index, label in enumerate(labels):
            target = self._find_label(label)
            if target is None:
                return False
            self.adb.tap(*target.center)
            if index < len(labels) - 1:
                self.sleeper(1.0)
                self.observe()
        return True

    def _find_label(self, label: str) -> OcrBox | None:
        candidates = [
            box
            for box in self.last_boxes
            if label in box.text and box.confidence >= 0.92
        ]
        return max(candidates, key=lambda box: box.confidence, default=None)
