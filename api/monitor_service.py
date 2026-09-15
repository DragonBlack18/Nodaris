import asyncio
import time

from api.config import (
    MONITOR_CONCURRENCY,
    NATIVE_PING_TIMEOUT_MS,
    PROBE_PROVIDER,
)
from api.integrations.blackbox_client import (
    BlackboxClient,
    BlackboxError,
)
from api.integrations.native_ping_client import (
    NativePingClient,
    NativePingError,
)
from api.logging_config import get_logger


logger = get_logger(
    "engine",
    "monitorping-engine.log",
)


class MonitorService:

    def __init__(
        self,
        blackbox: BlackboxClient | None = None,
        concurrency: int = MONITOR_CONCURRENCY,
    ):
        self.provider_name = (
            str(
                PROBE_PROVIDER
            )
            .strip()
            .lower()
        )

        self.blackbox = (
            blackbox
            or BlackboxClient()
        )

        self.native_ping = (
            NativePingClient(
                timeout_ms=(
                    NATIVE_PING_TIMEOUT_MS
                )
            )
        )

        self.semaphore = asyncio.Semaphore(
            concurrency
        )

    async def _probe(
        self,
        ip: str,
    ) -> dict:

        if (
            self.provider_name
            == "native"
        ):

            try:

                return await (
                    self.native_ping.probe(
                        ip
                    )
                )

            except NativePingError as exc:

                return {
                    "ip": ip,
                    "online": False,
                    "status": "ERROR",
                    "latency_ms": None,
                    "latency_source": (
                        "windows_ping"
                    ),
                    "probe_engine": (
                        "native_ping"
                    ),
                    "error": str(exc),
                }

        # =====================================================
        # BLACKBOX FALLBACK
        # =====================================================

        try:

            result = await (
                self.blackbox.ping(
                    ip
                )
            )

            result.setdefault(
                "probe_engine",
                "blackbox",
            )

            return result

        except BlackboxError as exc:

            return {
                "ip": ip,
                "online": False,
                "status": "ERROR",
                "latency_ms": None,
                "latency_source": (
                    "blackbox"
                ),
                "probe_engine": (
                    "blackbox"
                ),
                "error": str(exc),
            }

    async def probe_device(
        self,
        device: dict,
    ) -> dict:

        ip = device["ip"]

        async with self.semaphore:

            result = await self._probe(
                ip
            )

            return {
                "ip": ip,
                "name": device["name"],
                "gateway": device.get(
                    "gateway",
                    "",
                ),
                **result,
                "error": result.get(
                    "error"
                ),
            }

    async def probe_devices(
        self,
        devices: list[dict],
    ) -> dict:

        started = time.perf_counter()

        tasks = [
            self.probe_device(device)
            for device in devices
        ]

        results = await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

        isolated_results = []

        for device, result in zip(
            devices,
            results,
        ):

            if isinstance(
                result,
                asyncio.CancelledError,
            ):
                raise result

            if isinstance(
                result,
                Exception,
            ):

                ip = str(
                    device.get(
                        "ip",
                        "",
                    )
                )

                logger.error(
                    "Falha inesperada no probe de %s: %s",
                    ip or "<IP ausente>",
                    result,
                    exc_info=(
                        type(result),
                        result,
                        result.__traceback__,
                    ),
                )

                isolated_results.append(
                    self._unexpected_error_result(
                        device,
                        result,
                    )
                )

                continue

            isolated_results.append(
                result
            )

        results = isolated_results

        elapsed = (
            time.perf_counter()
            - started
        )

        online = sum(
            1
            for device in results
            if device["status"] == "ONLINE"
        )

        offline = sum(
            1
            for device in results
            if device["status"] == "OFFLINE"
        )

        errors = sum(
            1
            for device in results
            if device["status"] == "ERROR"
        )

        return {
            "summary": {
                "total": len(results),
                "online": online,
                "offline": offline,
                "errors": errors,
                "scan_duration_ms": round(
                    elapsed * 1000,
                    2,
                ),
            },
            "devices": results,
        }

    def _unexpected_error_result(
        self,
        device: dict,
        error: Exception,
    ) -> dict:

        native_provider = (
            self.provider_name
            == "native"
        )

        return {
            "ip": str(
                device.get(
                    "ip",
                    "",
                )
            ),
            "name": str(
                device.get(
                    "name",
                    "",
                )
            ),
            "gateway": device.get(
                "gateway",
                "",
            ),
            "online": False,
            "status": "ERROR",
            "latency_ms": None,
            "latency_source": (
                "windows_ping"
                if native_provider
                else "blackbox"
            ),
            "probe_engine": (
                "native_ping"
                if native_provider
                else "blackbox"
            ),
            "error": (
                "Falha inesperada no probe: "
                f"{error}"
            ),
        }
