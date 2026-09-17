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
