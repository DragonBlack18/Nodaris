from __future__ import annotations

import asyncio
import os
import re
import subprocess
from dataclasses import dataclass


_LATENCY_PATTERN = re.compile(
    r"(?:tempo|time)\s*[=<]\s*(\d+(?:[.,]\d+)?)\s*ms",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ProbeResult:
    ip: str
    online: bool
    latency_ms: float | None
    exit_code: int | None
    error: str | None = None


class NativePingProbe:
    """Executa um único probe ICMP usando o ping nativo do sistema."""

    def __init__(self, timeout_ms: int = 1000) -> None:
        self.timeout_ms = max(100, int(timeout_ms))

    async def probe(self, ip: str) -> ProbeResult:
        command = self._command(ip)
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=creation_flags,
            )
        except (FileNotFoundError, OSError) as exc:
            return ProbeResult(
                ip=ip,
                online=False,
                latency_ms=None,
                exit_code=None,
                error=f"unable to start system ping: {exc}",
            )

        hard_timeout = (self.timeout_ms / 1000.0) + 1.5

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=hard_timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return ProbeResult(
                ip=ip,
                online=False,
                latency_ms=None,
                exit_code=process.returncode,
                error="system ping exceeded hard timeout",
            )

        text = self._decode(stdout)
        error_text = self._decode(stderr).strip()
        online = process.returncode == 0

        return ProbeResult(
            ip=ip,
            online=online,
            latency_ms=self._extract_latency(text) if online else None,
            exit_code=process.returncode,
            error=error_text or None,
        )

    def _command(self, ip: str) -> list[str]:
        if os.name == "nt":
            return ["ping.exe", "-n", "1", "-w", str(self.timeout_ms), ip]

        timeout_seconds = max(1, round(self.timeout_ms / 1000))
        return ["ping", "-c", "1", "-W", str(timeout_seconds), ip]

    @staticmethod
    def _extract_latency(output: str) -> float | None:
        match = _LATENCY_PATTERN.search(output)
        if not match:
            return None

        value = float(match.group(1).replace(",", "."))
        if "<" in match.group(0) and value <= 1:
            return 0.5
        return value

    @staticmethod
    def _decode(raw: bytes) -> str:
        for encoding in ("utf-8", "cp850", "cp437", "latin-1"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode(errors="ignore")
