from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol


class InvalidSchemeCode(ValueError):
    pass


_TEXT_CODE = re.compile(r"\|TA\|[A-Za-z0-9_-]{6,512}\Z")
_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp"})


def normalize_scheme_code(value: str) -> str:
    code = value.strip()
    if not _TEXT_CODE.fullmatch(code):
        raise InvalidSchemeCode("方案码必须是 |TA| 开头的字母数字代码")
    return code


def decode_qr_scheme(
    value: str | Path, *, decoder=None, image=None
) -> str:
    path = Path(value).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() not in _IMAGE_SUFFIXES:
        raise InvalidSchemeCode("请选择 PNG、JPG、JPEG 或 WEBP 方案码图片")
    if decoder is None or image is None:
        try:
            import cv2
        except ImportError as exc:
            raise InvalidSchemeCode("缺少二维码识别依赖，请重新运行安装脚本") from exc
        decoder = decoder or cv2.QRCodeDetector()
        image = image if image is not None else cv2.imread(str(path))
    if image is None:
        raise InvalidSchemeCode("无法读取方案码图片")
    text, points, _straight = decoder.detectAndDecode(image)
    if not text or points is None:
        raise InvalidSchemeCode("图片中没有识别到清晰的方案码")
    return normalize_scheme_code(text)


class SchemeActor(Protocol):
    def import_text(self, code: str) -> bool: ...

    def import_qr(self, path: Path) -> bool: ...


class SchemeService:
    def __init__(self, actor: SchemeActor) -> None:
        self.actor = actor

    def import_text(self, value: str) -> bool:
        return bool(self.actor.import_text(normalize_scheme_code(value)))

    def import_qr(self, value: str | Path) -> bool:
        path = Path(value).expanduser().resolve()
        if not path.is_file() or path.suffix.lower() not in _IMAGE_SUFFIXES:
            raise InvalidSchemeCode("请选择 PNG、JPG、JPEG 或 WEBP 方案码图片")
        if path.stat().st_size > 20 * 1024 * 1024:
            raise InvalidSchemeCode("方案码图片不能超过 20 MB")
        return bool(self.actor.import_qr(path))
