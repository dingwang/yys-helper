from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Sequence


class AdbError(RuntimeError):
    pass


Runner = Callable[..., subprocess.CompletedProcess[bytes]]


def _default_runner(args: Sequence[str], *, timeout: float):
    return subprocess.run(
        list(args),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
        shell=False,
    )


def discover_adb(extra_paths: Sequence[str] = ()) -> list[str]:
    program_files = [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")]
    candidates = list(extra_paths)
    for root in filter(None, program_files):
        candidates.extend(
            [
                str(Path(root) / "Netease" / "MuMuPlayer-12.0" / "shell" / "adb.exe"),
                str(Path(root) / "Netease" / "MuMuPlayer" / "shell" / "adb.exe"),
                str(Path(root) / "MuMu" / "emulator" / "nemu" / "vmonitor" / "bin" / "adb_server.exe"),
            ]
        )
    on_path = shutil.which("adb")
    if on_path:
        candidates.append(on_path)
    found: list[str] = []
    for candidate in candidates:
        resolved = str(Path(candidate).expanduser())
        if Path(resolved).is_file() and resolved not in found:
            found.append(resolved)
    return found


class AdbClient:
    def __init__(
        self,
        executable: str,
        serial: str | None = None,
        *,
        runner: Runner = _default_runner,
        timeout: float = 15.0,
    ) -> None:
        self.executable = executable
        self.serial = serial
        self.runner = runner
        self.timeout = timeout

    def _args(self, *args: str, serial: bool = True) -> tuple[str, ...]:
        prefix = [self.executable]
        if serial and self.serial:
            prefix.extend(["-s", self.serial])
        return tuple(prefix + list(args))

    def _run(self, *args: str, serial: bool = True) -> bytes:
        command = self._args(*args, serial=serial)
        try:
            result = self.runner(command, timeout=self.timeout)
        except subprocess.TimeoutExpired as exc:
            raise AdbError(f"ADB command timed out after {self.timeout:g}s") from exc
        if result.returncode != 0:
            stderr = (result.stderr or b"").decode("utf-8", errors="replace").strip()
            raise AdbError(stderr or f"ADB command failed with code {result.returncode}")
        return bytes(result.stdout or b"")

    def devices(self) -> list[str]:
        output = self._run("devices", serial=False).decode("utf-8", errors="replace")
        ready: list[str] = []
        for line in output.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                ready.append(parts[0])
        return ready

    def connect(self, endpoint: str) -> bool:
        match = re.fullmatch(r"(?:127\.0\.0\.1|localhost):(\d{1,5})", endpoint)
        if match is None or not 1 <= int(match.group(1)) <= 65535:
            raise ValueError("ADB endpoint must be a local host and valid port")
        output = self._run("connect", endpoint, serial=False).decode(
            "utf-8", errors="replace"
        )
        return "connected to" in output.lower()

    def screenshot(self) -> bytes:
        if not self.serial:
            raise AdbError("No MuMu device is selected")
        data = self._run("exec-out", "screencap", "-p")
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise AdbError("MuMu screenshot did not return PNG data")
        return data

    def tap(self, x: int, y: int) -> None:
        if x < 0 or y < 0:
            raise ValueError("tap coordinates must be non-negative")
        self._run("shell", "input", "tap", str(x), str(y))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 350) -> None:
        if min(x1, y1, x2, y2, duration_ms) < 0:
            raise ValueError("swipe values must be non-negative")
        self._run(
            "shell",
            "input",
            "swipe",
            str(x1),
            str(y1),
            str(x2),
            str(y2),
            str(duration_ms),
        )

    def input_text(self, value: str) -> None:
        if any(ord(char) < 32 for char in value):
            raise ValueError("text cannot contain control characters")
        escaped = value.replace("%", "%25").replace(" ", "%s").replace("|", "\\|")
        self._run("shell", "input", "text", escaped)
