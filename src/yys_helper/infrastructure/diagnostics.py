from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from yys_helper.infrastructure.vision import OcrBox


class CaptureEvidenceWriter:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    @staticmethod
    def _purpose_name(purpose: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", purpose).strip("-")
        return cleaned or "capture"

    def write(
        self,
        purpose: str,
        png: bytes,
        boxes: Iterable[OcrBox],
        metadata: Mapping[str, object],
        *,
        error: str | None = None,
    ) -> Path:
        safe_purpose = self._purpose_name(purpose)
        captured_at = datetime.now(timezone.utc)
        folder = self.root / (
            f"{captured_at.strftime('%Y%m%dT%H%M%S.%fZ')}-"
            f"{safe_purpose}-{uuid4().hex[:8]}"
        )
        folder.mkdir(parents=True, exist_ok=False)

        screen_tmp = folder / "screen.png.tmp"
        screen_tmp.write_bytes(png)
        screen_tmp.replace(folder / "screen.png")

        payload = {
            "purpose": safe_purpose,
            "captured_at": captured_at.isoformat(),
            "metadata": dict(metadata),
            "error": error,
            "boxes": [
                {
                    "text": box.text,
                    "confidence": box.confidence,
                    "bounds": list(box.bounds),
                }
                for box in boxes
            ],
        }
        json_tmp = folder / "ocr.json.tmp"
        json_tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        json_tmp.replace(folder / "ocr.json")
        return folder
