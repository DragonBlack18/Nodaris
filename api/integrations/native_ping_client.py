import asyncio
import os
import re
import subprocess
from typing import Optional


class NativePingError(Exception):
    """
    Erro interno do mecanismo de ping.

    Não significa que o equipamento está offline.
    """


class NativePingClient:

    def __init__(
        self,
        timeout_ms: int = 1500,
    ):
        self.timeout_ms = max(
            100,
            int(timeout_ms),
        )

    # =====================================================
    # PROBE
    # =====================================================

    async def probe(
        self,
        ip: str,
    ) -> dict:

        command = [
            "ping.exe",
            "-n",
            "1",
            "-w",
            str(self.timeout_ms),
            str(ip),
        ]

        creation_flags = 0

        if os.name == "nt":
            creation_flags = (
                subprocess.CREATE_NO_WINDOW
            )

        try:

            process = (
                await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    creationflags=creation_flags,
                )
            )

        except FileNotFoundError as exc:

            raise NativePingError(
                "ping.exe não foi encontrado."
            ) from exc

        except Exception as exc:

            raise NativePingError(
                f"Não foi possível iniciar ping.exe: {exc}"
            ) from exc

        # O -w controla o timeout ICMP.
        # Este timeout adicional protege contra
        # um ping.exe travado por problema local.

        process_timeout = (
            self.timeout_ms / 1000.0
            + 2.0
        )

        try:

            stdout, stderr = (
                await asyncio.wait_for(
                    process.communicate(),
                    timeout=process_timeout,
                )
            )

        except asyncio.TimeoutError:

            try:
                process.kill()
                await process.wait()

            except Exception:
                pass

            # Isso é erro do mecanismo local,
            # não prova que o IP está offline.

            raise NativePingError(
                "ping.exe excedeu o tempo "
                "máximo de execução."
            )

        output = self._decode(
            stdout
        )

        error_output = self._decode(
            stderr
        )

        # =================================================
        # ONLINE/OFFLINE
        # =================================================

        online = (
            process.returncode == 0
        )

        latency_ms = None

        if online:

            latency_ms = (
                self._extract_latency(
                    output
                )
            )

        # =================================================
        # RESULT
        # =================================================

        return {
            "ip": str(ip),

            "online": online,

            "status": (
                "ONLINE"
                if online
                else "OFFLINE"
            ),

            "latency_ms": (
                latency_ms
            ),

            "latency_source": (
                "windows_ping"
            ),

            "probe_engine": (
                "native_ping"
            ),

            "exit_code": (
                process.returncode
            ),

            # Útil para diagnóstico.
            # Não precisa ser persistido.
            "probe_output": (
                output.strip()
            ),

            "probe_error": (
                error_output.strip()
            ),
        }

    # =====================================================
    # LATENCY
    # =====================================================

    @staticmethod
    def _extract_latency(
        output: str,
    ) -> Optional[float]:

        if not output:
            return None

        # Windows PT-BR:
        #
        # tempo=3ms
        # tempo<1ms
        #
        # Windows EN:
        #
        # time=3ms
        # time<1ms

        patterns = [
            (
                r"(?:tempo|time)"
                r"\s*[=<]\s*"
                r"(\d+(?:[.,]\d+)?)"
                r"\s*ms"
            ),
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                output,
                flags=re.IGNORECASE,
            )

            if not match:
                continue

            value = (
                match.group(1)
                .replace(
                    ",",
                    ".",
                )
            )

            try:

                latency = float(
                    value
                )

            except ValueError:

                continue

            # ping.exe normalmente apresenta:
            #
            # tempo<1ms
            #
            # Nesse caso armazenamos 0.5ms
            # para manter uma série numérica
            # útil no gráfico.

            matched_text = (
                match.group(0)
                .lower()
            )

            if (
                "<" in matched_text
                and latency <= 1.0
            ):

                return 0.5

            return latency

        return None

    # =====================================================
    # DECODE
    # =====================================================

    @staticmethod
    def _decode(
        value: bytes,
    ) -> str:

        if not value:
            return ""

        # Windows brasileiro geralmente usa
        # CP850/CP437 no console.

        for encoding in (
            "cp850",
            "cp437",
            "utf-8",
            "latin-1",
        ):

            try:

                return value.decode(
                    encoding
                )

            except UnicodeDecodeError:

                continue

        return value.decode(
            errors="ignore"
        )
