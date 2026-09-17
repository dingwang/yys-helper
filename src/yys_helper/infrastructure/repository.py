from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from yys_helper.domain.models import Soul, Stat


class AppRepository:
    def __init__(self, path: str | Path) -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path))
        self.connection.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS souls (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                action TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def set_setting(self, key: str, value: str) -> None:
        self.connection.execute(
            "INSERT INTO settings(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.connection.commit()

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.connection.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return str(row["value"]) if row else default

    @staticmethod
    def _soul_payload(soul: Soul) -> str:
        return json.dumps(
            {
                "id": soul.id,
                "set_name": soul.set_name,
                "slot": soul.slot,
                "rarity": soul.rarity,
                "level": soul.level,
                "main_stat": soul.main_stat.value,
                "main_value": soul.main_value,
                "substats": {key.value: value for key, value in soul.substats.items()},
                "locked": soul.locked,
                "equipped_to": soul.equipped_to,
                "marked_discard": soul.marked_discard,
                "confidence": soul.confidence,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    def save_souls(self, souls: Iterable[Soul]) -> None:
        with self.connection:
            for soul in souls:
                self.connection.execute(
                    "INSERT INTO souls(id, payload) VALUES (?, ?) "
                    "ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                    (soul.id, self._soul_payload(soul)),
                )

    def list_souls(self) -> list[Soul]:
        rows = self.connection.execute("SELECT payload FROM souls ORDER BY id").fetchall()
        result: list[Soul] = []
        for row in rows:
            data = json.loads(row["payload"])
            data["main_stat"] = Stat(data["main_stat"])
            data["substats"] = {Stat(key): value for key, value in data["substats"].items()}
            result.append(Soul(**data))
        return result

    def delete_soul(self, soul_id: str) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM souls WHERE id=?", (soul_id,))

    def add_audit(self, action: str, payload: dict[str, Any]) -> None:
        self.connection.execute(
            "INSERT INTO audit(created_at, action, payload) VALUES (?, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(),
                action,
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
            ),
        )
        self.connection.commit()

    def list_audit(self, limit: int = 200) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT created_at, action, payload FROM audit ORDER BY id LIMIT ?", (limit,)
        ).fetchall()
        return [
            {
                "created_at": row["created_at"],
                "action": row["action"],
                "payload": json.loads(row["payload"]),
            }
            for row in rows
        ]
