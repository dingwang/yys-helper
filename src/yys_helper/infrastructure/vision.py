from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence


@dataclass(frozen=True, slots=True)
class OcrBox:
    text: str
    confidence: float
    bounds: tuple[int, int, int, int]

    @property
    def center(self) -> tuple[int, int]:
        left, top, right, bottom = self.bounds
        return ((left + right) // 2, (top + bottom) // 2)


class OcrEngine(Protocol):
    def read(self, image: Any) -> Sequence[OcrBox]: ...


def normalized_to_pixels(
    point: tuple[float, float], frame_size: tuple[int, int]
) -> tuple[int, int]:
    x, y = point
    width, height = frame_size
    if not 0.0 <= x <= 1.0 or not 0.0 <= y <= 1.0:
        raise ValueError("normalized coordinates must be between 0 and 1")
    if width <= 0 or height <= 0:
        raise ValueError("frame size must be positive")
    return round(x * width), round(y * height)


class VisionService:
    def __init__(self, engine: OcrEngine) -> None:
        self.engine = engine

    def read(self, image: Any) -> list[OcrBox]:
        return list(self.engine.read(image))

    def find_text(
        self, image: Any, text: str, min_confidence: float = 0.92
    ) -> OcrBox | None:
        matches = [
            box
            for box in self.read(image)
            if text in box.text and box.confidence >= min_confidence
        ]
        return max(matches, key=lambda box: box.confidence, default=None)


class RapidOcrEngine:
    """Lazy adapter so unit tests do not need native OCR dependencies."""

    def __init__(self) -> None:
        self._engine = None

    def _load(self):
        if self._engine is None:
            try:
                from rapidocr import RapidOCR
            except ImportError as exc:
                raise RuntimeError("请先安装 desktop 依赖：pip install -e .[desktop]") from exc
            self._engine = RapidOCR()
        return self._engine

    def read(self, image: Any) -> list[OcrBox]:
        result = self._load()(image)
        rows = getattr(result, "txts", None)
        scores = getattr(result, "scores", None)
        boxes = getattr(result, "boxes", None)
        if rows is None or scores is None or boxes is None:
            return []
        output: list[OcrBox] = []
        for text, confidence, points in zip(rows, scores, boxes, strict=False):
            xs = [int(point[0]) for point in points]
            ys = [int(point[1]) for point in points]
            output.append(OcrBox(str(text), float(confidence), (min(xs), min(ys), max(xs), max(ys))))
        return output
